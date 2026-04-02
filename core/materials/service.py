"""Build local offline materials packs for the generator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import os
from pathlib import Path
import re
import shutil
import tomllib
from typing import Any, Sequence
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import zipfile


DEFAULT_GOOGLE_ICONS_ARCHIVE_URL = "https://github.com/google/material-design-icons/archive/refs/heads/master.zip"
DEFAULT_PEXELS_API_URL = "https://api.pexels.com/v1/search"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class BackgroundSourceConfig:
    provider: str
    queries: tuple[str, ...] = ()
    per_query: int = 10
    orientation: str = "landscape"
    api_key_env: str = "PEXELS_API_KEY"
    source_dir: Path | None = None
    limit: int | None = None


@dataclass(frozen=True)
class IconSourceConfig:
    provider: str
    archive_url: str = DEFAULT_GOOGLE_ICONS_ARCHIVE_URL
    archive_path: Path | None = None


@dataclass(frozen=True)
class ClassSpec:
    id: int
    name: str
    zh_name: str
    source_icons: tuple[str, ...]


@dataclass(frozen=True)
class MaterialsPackSpec:
    backgrounds: BackgroundSourceConfig
    icons: IconSourceConfig
    classes: tuple[ClassSpec, ...]


@dataclass(frozen=True)
class BuildMaterialsPackResult:
    output_root: Path
    class_count: int
    background_count: int
    icon_file_count: int
    backgrounds_manifest: Path
    icons_manifest: Path
    classes_manifest: Path

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("output_root", "backgrounds_manifest", "icons_manifest", "classes_manifest"):
            payload[key] = str(payload[key])
        return payload


def load_materials_pack_spec(path: Path) -> MaterialsPackSpec:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))

    backgrounds_payload = _require_mapping(payload, "backgrounds")
    icons_payload = _require_mapping(payload, "icons")
    classes_payload = payload.get("classes")
    if not isinstance(classes_payload, list) or not classes_payload:
        raise ValueError("spec must define at least one [[classes]] entry")

    backgrounds = BackgroundSourceConfig(
        provider=_require_str(backgrounds_payload, "provider"),
        queries=_optional_str_tuple(backgrounds_payload.get("queries")),
        per_query=_optional_int(backgrounds_payload.get("per_query"), default=10),
        orientation=_optional_str(backgrounds_payload.get("orientation"), default="landscape"),
        api_key_env=_optional_str(backgrounds_payload.get("api_key_env"), default="PEXELS_API_KEY"),
        source_dir=_optional_path(backgrounds_payload.get("source_dir")),
        limit=_optional_int_or_none(backgrounds_payload.get("limit")),
    )
    icons = IconSourceConfig(
        provider=_require_str(icons_payload, "provider"),
        archive_url=_optional_str(
            icons_payload.get("archive_url"),
            default=DEFAULT_GOOGLE_ICONS_ARCHIVE_URL,
        ),
        archive_path=_optional_path(icons_payload.get("archive_path")),
    )
    classes = tuple(_parse_class_spec(item) for item in classes_payload)
    _validate_pack_spec(backgrounds, icons, classes)
    return MaterialsPackSpec(backgrounds=backgrounds, icons=icons, classes=classes)


def build_offline_pack(
    spec: MaterialsPackSpec,
    *,
    output_root: Path,
    cache_dir: Path,
) -> BuildMaterialsPackResult:
    output_root.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    backgrounds_dir = output_root / "backgrounds"
    icons_dir = output_root / "icons"
    manifests_dir = output_root / "manifests"
    backgrounds_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    background_rows = _sync_backgrounds(spec.backgrounds, backgrounds_dir)
    icon_rows = _sync_icons(spec.icons, spec.classes, icons_dir, cache_dir)
    if not background_rows:
        raise ValueError("materials pack build produced no background images")
    if not icon_rows:
        raise ValueError("materials pack build produced no icon images")
    classes_manifest = manifests_dir / "classes.yaml"
    backgrounds_manifest = manifests_dir / "backgrounds.csv"
    icons_manifest = manifests_dir / "icons.csv"

    _write_classes_manifest(classes_manifest, spec.classes)
    _write_csv(backgrounds_manifest, background_rows)
    _write_csv(icons_manifest, icon_rows)

    return BuildMaterialsPackResult(
        output_root=output_root,
        class_count=len(spec.classes),
        background_count=len(background_rows),
        icon_file_count=len(icon_rows),
        backgrounds_manifest=backgrounds_manifest,
        icons_manifest=icons_manifest,
        classes_manifest=classes_manifest,
    )


def choose_best_google_icon_entry(entries: Sequence[str], icon_name: str) -> str:
    normalized_name = _normalize_tokens(icon_name)
    candidates: list[tuple[int, int, str]] = []

    for entry in entries:
        lowered = entry.lower()
        if entry.endswith("/") or Path(lowered).suffix not in IMAGE_EXTENSIONS:
            continue
        if "/png/" not in lowered:
            continue
        if not _normalized_path_contains_icon(lowered, normalized_name):
            continue
        candidates.append((_score_google_icon_entry(lowered), -len(entry), entry))

    if not candidates:
        raise ValueError(f"could not find Google icon asset for '{icon_name}' in archive")
    candidates.sort(reverse=True)
    return candidates[0][2]


def _validate_pack_spec(
    backgrounds: BackgroundSourceConfig,
    icons: IconSourceConfig,
    classes: tuple[ClassSpec, ...],
) -> None:
    if backgrounds.provider not in {"pexels", "local"}:
        raise ValueError(f"unsupported backgrounds provider: {backgrounds.provider}")
    if backgrounds.provider == "pexels" and not backgrounds.queries:
        raise ValueError("pexels backgrounds provider requires at least one query")
    if backgrounds.provider == "local" and backgrounds.source_dir is None:
        raise ValueError("local backgrounds provider requires source_dir")

    if icons.provider not in {"google_material_design_icons"}:
        raise ValueError(f"unsupported icons provider: {icons.provider}")

    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for class_spec in classes:
        if class_spec.id in seen_ids:
            raise ValueError(f"duplicate class id: {class_spec.id}")
        if class_spec.name in seen_names:
            raise ValueError(f"duplicate class name: {class_spec.name}")
        if not class_spec.source_icons:
            raise ValueError(f"class must declare at least one source icon: {class_spec.name}")
        seen_ids.add(class_spec.id)
        seen_names.add(class_spec.name)


def _parse_class_spec(payload: object) -> ClassSpec:
    if not isinstance(payload, dict):
        raise ValueError("each [[classes]] item must be a table")
    source_icons = _optional_str_tuple(payload.get("source_icons"))
    if not source_icons:
        raise ValueError("class spec must define source_icons")
    return ClassSpec(
        id=_require_int(payload, "id"),
        name=_require_str(payload, "name"),
        zh_name=_require_str(payload, "zh_name"),
        source_icons=source_icons,
    )


def _sync_backgrounds(config: BackgroundSourceConfig, backgrounds_dir: Path) -> list[dict[str, str]]:
    if config.provider == "local":
        return _copy_local_backgrounds(config, backgrounds_dir)
    if config.provider == "pexels":
        return _download_pexels_backgrounds(config, backgrounds_dir)
    raise ValueError(f"unsupported backgrounds provider: {config.provider}")


def _copy_local_backgrounds(config: BackgroundSourceConfig, backgrounds_dir: Path) -> list[dict[str, str]]:
    assert config.source_dir is not None
    source_files = sorted(
        path
        for path in config.source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if config.limit is not None:
        source_files = source_files[: config.limit]

    rows: list[dict[str, str]] = []
    for index, source in enumerate(source_files, start=1):
        destination = backgrounds_dir / f"bg_local_{index:04d}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        rows.append(
            {
                "background_id": destination.stem,
                "provider": "local",
                "query": "",
                "author": "",
                "license": "local",
                "source_url": str(source),
                "file_name": destination.name,
            }
        )
    return rows


def _download_pexels_backgrounds(config: BackgroundSourceConfig, backgrounds_dir: Path) -> list[dict[str, str]]:
    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        raise ValueError(f"missing Pexels API key in environment variable: {config.api_key_env}")

    rows: list[dict[str, str]] = []
    seen_ids: set[int] = set()

    for query in config.queries:
        collected = 0
        page = 1
        while collected < config.per_query:
            page_size = min(80, config.per_query - collected)
            payload = _search_pexels(
                query=query,
                api_key=api_key,
                orientation=config.orientation,
                per_page=page_size,
                page=page,
            )
            photos = payload.get("photos")
            if not isinstance(photos, list) or not photos:
                break

            for photo in photos:
                if not isinstance(photo, dict):
                    continue
                photo_id = photo.get("id")
                if not isinstance(photo_id, int) or photo_id in seen_ids:
                    continue
                src = photo.get("src")
                if not isinstance(src, dict):
                    continue
                image_url = _choose_pexels_image_url(src)
                if image_url is None:
                    continue
                extension = _guess_extension_from_url(image_url)
                destination = backgrounds_dir / f"bg_pexels_{photo_id}{extension}"
                _download_binary(image_url, destination)
                seen_ids.add(photo_id)
                rows.append(
                    {
                        "background_id": destination.stem,
                        "provider": "pexels",
                        "query": query,
                        "author": str(photo.get("photographer", "")),
                        "license": "Pexels License",
                        "source_url": image_url,
                        "file_name": destination.name,
                    }
                )
                collected += 1
                if collected >= config.per_query:
                    break
            page += 1
    return rows


def _sync_icons(
    config: IconSourceConfig,
    classes: tuple[ClassSpec, ...],
    icons_dir: Path,
    cache_dir: Path,
) -> list[dict[str, str]]:
    if config.provider != "google_material_design_icons":
        raise ValueError(f"unsupported icons provider: {config.provider}")

    archive_path = _ensure_google_icons_archive(config, cache_dir)
    rows: list[dict[str, str]] = []
    with zipfile.ZipFile(archive_path, "r") as archive:
        entries = archive.namelist()
        for class_spec in classes:
            class_dir = icons_dir / class_spec.name
            class_dir.mkdir(parents=True, exist_ok=True)
            for index, source_icon in enumerate(class_spec.source_icons, start=1):
                entry = choose_best_google_icon_entry(entries, source_icon)
                destination = class_dir / f"{index:03d}.png"
                with archive.open(entry, "r") as source, destination.open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                rows.append(
                    {
                        "class_id": str(class_spec.id),
                        "class_name": class_spec.name,
                        "provider": "google_material_design_icons",
                        "source_icon": source_icon,
                        "archive_entry": entry,
                        "file_name": destination.relative_to(icons_dir).as_posix(),
                    }
                )
    return rows


def _ensure_google_icons_archive(config: IconSourceConfig, cache_dir: Path) -> Path:
    if config.archive_path is not None:
        return config.archive_path
    parsed = urlparse(config.archive_url)
    archive_name = Path(parsed.path).name or "material-design-icons.zip"
    destination = cache_dir / archive_name
    if destination.exists():
        return destination
    _download_binary(config.archive_url, destination)
    return destination


def _search_pexels(
    *,
    query: str,
    api_key: str,
    orientation: str,
    per_page: int,
    page: int,
) -> dict[str, Any]:
    params = urlencode(
        {
            "query": query,
            "orientation": orientation,
            "per_page": per_page,
            "page": page,
        }
    )
    url = f"{DEFAULT_PEXELS_API_URL}?{params}"
    request = Request(
        url,
        headers={
            "Authorization": api_key,
            "User-Agent": "sinan-captcha-materials/0.1",
        },
    )
    with urlopen(request) as response:
        content = response.read()
    payload = json.loads(content.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("unexpected Pexels API response shape")
    return payload


def _choose_pexels_image_url(src: dict[str, Any]) -> str | None:
    for key in ("large2x", "large", "original"):
        value = src.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _download_binary(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "sinan-captcha-materials/0.1"})
    with urlopen(request) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _write_classes_manifest(path: Path, classes: tuple[ClassSpec, ...]) -> None:
    lines = ["classes:"]
    for class_spec in sorted(classes, key=lambda item: item.id):
        lines.extend(
            [
                f"  - id: {class_spec.id}",
                f"    name: {class_spec.name}",
                f"    zh_name: {class_spec.zh_name}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _normalized_path_contains_icon(path: str, normalized_name: str) -> bool:
    normalized_path = _normalize_tokens(path)
    return f" {normalized_name} " in f" {normalized_path} "


def _normalize_tokens(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(part for part in normalized.split() if part)


def _score_google_icon_entry(entry: str) -> int:
    score = 0
    if "/png/" in entry:
        score += 1000
    if "/materialicons/" in entry:
        score += 250
    if "/materialsymbols" in entry:
        score += 150
    for scale, points in {"4x_web": 400, "3x_web": 300, "2x_web": 200, "1x_web": 100}.items():
        if f"/{scale}/" in entry:
            score += points
            break
    if "baseline_" in entry or "ic_" in entry:
        score += 50
    match = re.search(r"(\d+)dp", entry)
    if match is not None:
        score += int(match.group(1))
    return score


def _guess_extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return suffix
    return ".jpg"


def _require_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing or invalid [{key}] section")
    return value


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or invalid string field: {key}")
    return value.strip()


def _optional_str(value: object, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a non-empty string")
    return value.strip()


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"missing or invalid integer field: {key}")
    return value


def _optional_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError("expected an integer value")
    return value


def _optional_int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("expected an integer value")
    return value


def _optional_path(value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a non-empty path string")
    return Path(value)


def _optional_str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("expected a list of non-empty strings")
    return tuple(item.strip() for item in value)
