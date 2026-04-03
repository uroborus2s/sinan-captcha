"""Build local offline materials packs for the generator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import os
from pathlib import Path
import re
import shutil
from http.client import IncompleteRead, RemoteDisconnected
import ssl
import tomllib
import time
from typing import Any, Sequence
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


DEFAULT_GOOGLE_ICONS_ARCHIVE_URL = "https://github.com/google/material-design-icons/archive/refs/heads/master.zip"
DEFAULT_GOOGLE_ICONS_TREE_API_BASE_URL = "https://api.github.com/repos/google/material-design-icons/git/trees"
DEFAULT_GOOGLE_ICONS_ROOT_TREE_API_URL = f"{DEFAULT_GOOGLE_ICONS_TREE_API_BASE_URL}/master"
DEFAULT_GOOGLE_ICONS_RAW_URL_PREFIX = "https://raw.githubusercontent.com/google/material-design-icons/master/"
DEFAULT_PEXELS_API_URL = "https://api.pexels.com/v1/search"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DEFAULT_NETWORK_RETRIES = 8
DEFAULT_NETWORK_TIMEOUT_SECONDS = 30
RETRYABLE_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


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
    candidates: list[tuple[int, int, int, str]] = []

    for entry in entries:
        lowered = entry.lower()
        if entry.endswith("/") or Path(lowered).suffix not in IMAGE_EXTENSIONS:
            continue
        if "/png/" not in lowered and not lowered.startswith("png/"):
            continue
        exact_match = _entry_has_exact_icon_name(lowered, normalized_name)
        partial_match = _normalized_path_contains_icon(lowered, normalized_name)
        if not exact_match and not partial_match:
            continue
        candidates.append(
            (
                1 if exact_match else 0,
                _score_google_icon_entry(lowered),
                -len(entry),
                entry,
            )
        )

    if not candidates:
        raise ValueError(f"could not find Google icon asset for '{icon_name}'")
    candidates.sort(reverse=True)
    return candidates[0][3]


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
    source_dir = config.source_dir.resolve()
    target_dir = backgrounds_dir.resolve()
    reuse_existing_files = source_dir == target_dir
    source_files = sorted(
        path
        for path in config.source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if config.limit is not None:
        source_files = source_files[: config.limit]

    rows: list[dict[str, str]] = []
    for index, source in enumerate(source_files, start=1):
        if reuse_existing_files:
            destination = source
        else:
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
                if not destination.exists():
                    try:
                        _download_binary(image_url, destination)
                    except (RemoteDisconnected, URLError, ssl.SSLError, OSError):
                        continue
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

    if config.archive_path is None:
        return _sync_icons_from_repo(classes, icons_dir, cache_dir)
    return _sync_icons_from_archive(config, classes, icons_dir, cache_dir)


def _sync_icons_from_repo(
    classes: tuple[ClassSpec, ...],
    icons_dir: Path,
    cache_dir: Path,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for class_spec in classes:
        class_dir = icons_dir / class_spec.name
        class_dir.mkdir(parents=True, exist_ok=True)
        resolved_count = 0
        for source_icon in class_spec.source_icons:
            try:
                entry = _resolve_google_icon_entry(source_icon, cache_dir)
            except ValueError:
                continue
            resolved_count += 1
            destination = class_dir / f"{resolved_count:03d}.png"
            _download_binary(f"{DEFAULT_GOOGLE_ICONS_RAW_URL_PREFIX}{entry}", destination)
            rows.append(
                {
                    "class_id": str(class_spec.id),
                    "class_name": class_spec.name,
                    "provider": "google_material_design_icons",
                    "source_icon": source_icon,
                    "source_path": entry,
                    "file_name": destination.relative_to(icons_dir).as_posix(),
                }
            )
        if resolved_count == 0:
            raise ValueError(f"could not resolve any Google icon assets for class '{class_spec.name}'")
    return rows


def _sync_icons_from_archive(
    config: IconSourceConfig,
    classes: tuple[ClassSpec, ...],
    icons_dir: Path,
    cache_dir: Path,
) -> list[dict[str, str]]:
    archive_path = _ensure_google_icons_archive(config, cache_dir)
    rows: list[dict[str, str]] = []
    with zipfile.ZipFile(archive_path, "r") as archive:
        entries = archive.namelist()
        for class_spec in classes:
            class_dir = icons_dir / class_spec.name
            class_dir.mkdir(parents=True, exist_ok=True)
            resolved_count = 0
            for source_icon in class_spec.source_icons:
                try:
                    entry = choose_best_google_icon_entry(entries, source_icon)
                except ValueError:
                    continue
                resolved_count += 1
                destination = class_dir / f"{resolved_count:03d}.png"
                with archive.open(entry, "r") as source, destination.open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                rows.append(
                    {
                        "class_id": str(class_spec.id),
                        "class_name": class_spec.name,
                        "provider": "google_material_design_icons",
                        "source_icon": source_icon,
                        "source_path": entry,
                        "file_name": destination.relative_to(icons_dir).as_posix(),
                    }
                )
            if resolved_count == 0:
                raise ValueError(f"could not resolve any Google icon assets for class '{class_spec.name}'")
    return rows


def _resolve_google_icon_entry(icon_name: str, cache_dir: Path) -> str:
    category_shas = _load_google_icons_png_category_shas(cache_dir)
    preferred_categories = _preferred_google_icon_categories(icon_name)
    seen_categories: set[str] = set()

    for category in (*preferred_categories, *category_shas.keys()):
        if category in seen_categories:
            continue
        seen_categories.add(category)
        category_sha = category_shas.get(category)
        if category_sha is None:
            continue
        entries = _load_google_icons_category_entries(category, category_sha, cache_dir)
        try:
            return choose_best_google_icon_entry(entries, icon_name)
        except ValueError:
            continue
    raise ValueError(f"could not find Google icon asset for '{icon_name}'")


def _load_google_icons_png_category_shas(cache_dir: Path) -> dict[str, str]:
    root_payload = _load_google_icons_json(
        cache_dir / "google-material-icons-root.json",
        DEFAULT_GOOGLE_ICONS_ROOT_TREE_API_URL,
        description="download Google icons repository root tree",
    )
    png_sha = _extract_google_icons_tree_sha(root_payload, "png")
    png_payload = _load_google_icons_json(
        cache_dir / "google-material-icons-png-root.json",
        f"{DEFAULT_GOOGLE_ICONS_TREE_API_BASE_URL}/{png_sha}",
        description="download Google icons png root tree",
    )

    category_shas: dict[str, str] = {}
    tree = png_payload.get("tree")
    if not isinstance(tree, list):
        raise ValueError("invalid Google icons png root payload: missing tree")
    for item in tree:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tree":
            continue
        path = item.get("path")
        sha = item.get("sha")
        if isinstance(path, str) and isinstance(sha, str):
            category_shas[path] = sha
    return category_shas


def _load_google_icons_category_entries(category: str, category_sha: str, cache_dir: Path) -> tuple[str, ...]:
    payload = _load_google_icons_json(
        cache_dir / f"google-material-icons-{category}.json",
        f"{DEFAULT_GOOGLE_ICONS_TREE_API_BASE_URL}/{category_sha}?recursive=1",
        description=f"download Google icons {category} tree",
    )
    entries = _parse_google_icon_tree_payload(payload)
    return tuple(f"png/{category}/{entry}" for entry in entries)


def _load_google_icons_json(cache_path: Path, url: str, *, description: str) -> dict[str, Any]:
    if cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache_path.unlink()
        else:
            if isinstance(payload, dict):
                return payload
            raise ValueError(f"invalid cached payload at {cache_path}")

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sinan-captcha-materials/0.1",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, DEFAULT_NETWORK_RETRIES + 1):
        try:
            with _open_with_retries(request, description=description) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except (IncompleteRead, json.JSONDecodeError, UnicodeDecodeError) as error:
            last_error = error
            if attempt == DEFAULT_NETWORK_RETRIES:
                raise
            time.sleep(min(5, attempt))
    else:
        assert last_error is not None
        raise last_error

    temporary_cache_path = cache_path.with_suffix(".json.part")
    temporary_cache_path.write_text(json.dumps(payload), encoding="utf-8")
    temporary_cache_path.replace(cache_path)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid payload for {description}")
    return payload


def _parse_google_icon_tree_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError("invalid Google icons tree payload")
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise ValueError("invalid Google icons tree payload: missing tree")

    entries: list[str] = []
    for item in tree:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "blob":
            continue
        path = item.get("path")
        if not isinstance(path, str):
            continue
        entries.append(path)
    return entries


def _extract_google_icons_tree_sha(payload: dict[str, Any], path_name: str) -> str:
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise ValueError("invalid Google icons tree payload: missing tree")
    for item in tree:
        if not isinstance(item, dict):
            continue
        if item.get("path") != path_name:
            continue
        sha = item.get("sha")
        if isinstance(sha, str):
            return sha
    raise ValueError(f"could not find Google icons tree sha for '{path_name}'")


def _preferred_google_icon_categories(icon_name: str) -> tuple[str, ...]:
    mapping = {
        "home": ("action", "home"),
        "house": ("action", "home"),
        "eco": ("image", "social"),
        "energy_savings_leaf": ("action", "device", "image"),
        "directions_boat": ("maps",),
        "sailing": ("maps",),
        "flight": ("maps", "device"),
        "airplanemode_active": ("device",),
        "directions_car": ("maps",),
        "directions_bike": ("maps",),
        "key": ("communication", "action"),
        "vpn_key": ("communication", "action"),
        "lock": ("action",),
        "lock_open": ("action",),
        "camera_alt": ("image",),
        "photo_camera": ("image",),
        "star": ("toggle", "action"),
        "grade": ("action", "toggle"),
        "favorite": ("action",),
        "favorite_border": ("action",),
        "pets": ("action",),
        "park": ("maps", "places"),
        "local_florist": ("maps", "places"),
        "redeem": ("action",),
        "card_giftcard": ("action",),
        "music_note": ("av",),
        "audiotrack": ("av",),
        "notifications": ("notification", "social"),
        "notifications_active": ("notification", "social"),
        "umbrella": ("maps", "places"),
        "flag": ("content", "navigation"),
        "outlined_flag": ("content", "navigation"),
        "public": ("social",),
        "language": ("social",),
    }
    return mapping.get(icon_name, ())


def _ensure_google_icons_archive(config: IconSourceConfig, cache_dir: Path) -> Path:
    if config.archive_path is not None:
        return config.archive_path
    parsed = urlparse(config.archive_url)
    archive_name = Path(parsed.path).name or "material-design-icons.zip"
    destination = cache_dir / archive_name
    temporary_destination = destination.with_suffix(destination.suffix + ".part")

    for _ in range(1, DEFAULT_NETWORK_RETRIES + 1):
        if destination.exists():
            if _is_valid_zip_archive(destination):
                return destination
            if temporary_destination.exists():
                temporary_destination.unlink()
            destination.replace(temporary_destination)

        _download_binary(config.archive_url, destination)
        if destination.exists() and _is_valid_zip_archive(destination):
            return destination
        if destination.exists():
            if temporary_destination.exists():
                temporary_destination.unlink()
            destination.replace(temporary_destination)

    raise ValueError(f"downloaded Google icons archive is invalid: {destination}")


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
    with _open_with_retries(request, description=f"Pexels search query='{query}' page={page}") as response:
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
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_destination = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None

    for attempt in range(1, DEFAULT_NETWORK_RETRIES + 1):
        current_size = temporary_destination.stat().st_size if temporary_destination.exists() else 0
        request_headers = {"User-Agent": "sinan-captcha-materials/0.1"}
        if current_size > 0:
            request_headers["Range"] = f"bytes={current_size}-"
        request = Request(url, headers=request_headers)

        try:
            with _open_with_retries(request, description=f"download {url}") as response:
                supports_resume = bool(response.headers.get("Content-Range")) or getattr(response, "status", None) == 206
                write_mode = "ab" if current_size > 0 and supports_resume else "wb"
                with temporary_destination.open(write_mode) as handle:
                    while True:
                        try:
                            chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                        except IncompleteRead as error:
                            if error.partial:
                                handle.write(error.partial)
                            raise
                        if not chunk:
                            break
                        handle.write(chunk)
            temporary_destination.replace(destination)
            return
        except HTTPError as error:
            if error.code == 416 and temporary_destination.exists():
                temporary_destination.replace(destination)
                return
            last_error = error
        except (IncompleteRead, RemoteDisconnected, URLError, ssl.SSLError, OSError) as error:
            last_error = error

        if attempt == DEFAULT_NETWORK_RETRIES:
            break
        time.sleep(min(5, attempt))

    assert last_error is not None
    raise last_error


def _open_with_retries(request: Request, *, description: str):
    last_error: Exception | None = None
    for attempt in range(1, DEFAULT_NETWORK_RETRIES + 1):
        try:
            return urlopen(request, timeout=DEFAULT_NETWORK_TIMEOUT_SECONDS)
        except HTTPError as error:
            if error.code not in RETRYABLE_HTTP_STATUS_CODES or attempt == DEFAULT_NETWORK_RETRIES:
                raise
            last_error = error
        except (RemoteDisconnected, URLError, ssl.SSLError, OSError) as error:
            if attempt == DEFAULT_NETWORK_RETRIES:
                raise
            last_error = error
        time.sleep(min(5, attempt))
    assert last_error is not None
    raise last_error


def _is_valid_zip_archive(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            archive.infolist()
    except (FileNotFoundError, OSError, zipfile.BadZipFile):
        return False
    return True


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


def _entry_has_exact_icon_name(path: str, normalized_name: str) -> bool:
    parts = path.split("/")
    skip_indexes: set[int] = set()
    if parts and parts[0] == "png":
        skip_indexes.update({0, 1})
    for index, part in enumerate(parts):
        if index in skip_indexes:
            continue
        if _normalize_tokens(part) == normalized_name:
            return True
    return False


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
    for density, points in {"48dp": 480, "36dp": 360, "24dp": 240, "18dp": 180}.items():
        if f"/{density}/" in entry:
            score += points
            break
    for scale, points in {"2x": 80, "1x": 40}.items():
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
