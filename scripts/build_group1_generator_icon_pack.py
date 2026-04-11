from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image

DEFAULT_MAPPING_FILE = Path("work_home/materials/incoming/group1_query_clusters/semantic_candidates.json")
DEFAULT_CANDIDATES_ROOT = Path("work_home/materials/incoming/group1_icon_candidates")
DEFAULT_OUTPUT_DIR = Path("work_home/materials/incoming/group1_icon_pack")
DEFAULT_OLD_ROOT = Path("work_home/materials/incoming/old")

LUCIDE_VARIANTS: dict[str, list[str]] = {
    "icon_smile": ["smile", "laugh"],
    "icon_mail": ["mail", "mail-open"],
    "icon_check_circle": ["badge-check", "circle-check-big"],
    "icon_briefcase": ["briefcase", "briefcase-business"],
    "icon_flag": ["flag"],
    "icon_inbox": ["inbox"],
    "icon_bell": ["bell", "bell-ring"],
    "icon_heart": ["heart"],
    "icon_bolt": ["bolt", "zap"],
    "icon_train": ["train-front"],
    "icon_shopping_cart": ["shopping-cart"],
    "icon_cloud_download": ["cloud-download", "cloud"],
    "icon_star": ["star", "sparkles"],
    "icon_compass": ["compass"],
    "icon_key": ["key", "key-round"],
    "icon_anchor": ["anchor"],
    "icon_christmas_tree": ["tree-pine", "trees"],
    "icon_headset": ["headset"],
    "icon_speedboat": ["ship"],
    "icon_luggage": ["luggage"],
    "icon_flame": ["flame"],
    "icon_microphone": ["mic"],
    "icon_shield_plus": ["shield-plus"],
    "icon_plane": ["plane"],
    "icon_users": ["users"],
    "icon_bicycle": ["bike"],
    "icon_camera": ["camera"],
    "icon_car": ["car", "car-front"],
    "icon_flower": ["flower-2", "flower"],
    "icon_gift": ["gift"],
    "icon_globe": ["globe", "globe-2"],
    "icon_house": ["house"],
    "icon_leaf": ["leaf"],
    "icon_lock": ["lock", "lock-keyhole"],
    "icon_music": ["music", "music-2"],
    "icon_paw": ["paw-print"],
    "icon_ship": ["ship-wheel"],
    "icon_tree": ["tree-pine", "trees"],
    "icon_umbrella": ["umbrella"],
}

LEGACY_OLD_CLASS_META: dict[str, str] = {
    "icon_bell": "铃铛",
    "icon_bicycle": "自行车",
    "icon_camera": "相机",
    "icon_car": "汽车",
    "icon_flag": "旗帜",
    "icon_flower": "花朵",
    "icon_gift": "礼物",
    "icon_globe": "地球",
    "icon_heart": "心形",
    "icon_house": "房子",
    "icon_key": "钥匙",
    "icon_leaf": "叶子",
    "icon_lock": "锁",
    "icon_music": "音乐",
    "icon_paw": "爪印",
    "icon_plane": "飞机",
    "icon_ship": "轮船",
    "icon_star": "星星",
    "icon_tree": "树",
    "icon_umbrella": "雨伞",
}

TABLER_SLUG_MAP: dict[str, str] = {
    "icon_bicycle": "bike",
    "icon_house": "home",
    "icon_paw": "paw",
}


def load_mapping(mapping_file: Path) -> dict:
    return json.loads(mapping_file.read_text(encoding="utf-8"))


def resolve_workspace_path(path_value: str | Path, *, base_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return base_dir / path


def fetch_binary(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; sinan-captcha/0.1; "
                "+https://github.com/openai)"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def ensure_lucide_svgs(*, class_name: str, class_dir: Path, timeout: float) -> list[Path]:
    downloaded: list[Path] = []
    for slug in LUCIDE_VARIANTS.get(class_name, []):
        svg_path = class_dir / f"lucide_{slug}.svg"
        if not svg_path.exists():
            url = f"https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{slug}.svg"
            try:
                svg_path.write_bytes(fetch_binary(url, timeout))
            except Exception:
                continue
        downloaded.append(svg_path)
    return downloaded


def ensure_tabler_filled_svg(*, entry: dict, class_dir: Path, timeout: float) -> list[Path]:
    slug = resolve_tabler_slug(entry)
    if not slug:
        return []

    svg_path = class_dir / f"tabler_filled_{slug}.svg"
    if not svg_path.exists():
        url = f"https://raw.githubusercontent.com/tabler/tabler-icons/master/icons/filled/{slug}.svg"
        try:
            svg_path.write_bytes(fetch_binary(url, timeout))
        except Exception:
            return []
    return [svg_path]


def ensure_tabler_outline_svg(*, entry: dict, class_dir: Path, timeout: float) -> list[Path]:
    slug = resolve_tabler_slug(entry)
    if not slug:
        return []

    svg_path = class_dir / f"tabler_outline_{slug}.svg"
    if not svg_path.exists():
        url = f"https://raw.githubusercontent.com/tabler/tabler-icons/master/icons/outline/{slug}.svg"
        try:
            svg_path.write_bytes(fetch_binary(url, timeout))
        except Exception:
            return []
    return [svg_path]


def resolve_tabler_slug(entry: dict) -> str | None:
    selected = entry.get("selected_source") or {}
    if selected.get("library") == "tabler" and selected.get("slug"):
        return str(selected["slug"])
    class_name = entry.get("class_name")
    if not class_name:
        return None
    if class_name in TABLER_SLUG_MAP:
        return TABLER_SLUG_MAP[class_name]
    if class_name.startswith("icon_"):
        return class_name.removeprefix("icon_")
    return None


def rasterize_svg(svg_path: Path, output_png: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="sinan-svg-") as temp_dir:
        temp_root = Path(temp_dir)
        subprocess.run(
            ["qlmanage", "-t", "-s", "256", "-o", str(temp_root), str(svg_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        generated = temp_root / f"{svg_path.name}.png"
        if not generated.exists():
            raise FileNotFoundError(f"qlmanage did not produce png for {svg_path}")
        processed = normalize_icon_png(Image.open(generated).convert("RGBA"))
        output_png.parent.mkdir(parents=True, exist_ok=True)
        processed.save(output_png)


def normalize_icon_png(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if red >= 245 and green >= 245 and blue >= 245:
                pixels[x, y] = (255, 255, 255, 0)
            elif red >= 210 and green >= 210 and blue >= 210:
                pixels[x, y] = (0, 0, 0, max(0, 255 - max(red, green, blue)))

    alpha_bbox = img.getchannel("A").getbbox()
    if alpha_bbox is None:
        return img

    cropped = img.crop(alpha_bbox)
    pad = 8
    canvas = Image.new("RGBA", (cropped.width + pad * 2, cropped.height + pad * 2), (255, 255, 255, 0))
    canvas.paste(cropped, (pad, pad), cropped)
    return canvas


def extract_member_icon(*, source_path: Path, bbox: list[int] | tuple[int, int, int, int]) -> Image.Image:
    src = Image.open(source_path).convert("RGBA")
    x1, y1, x2, y2 = [int(value) for value in bbox]
    crop = src.crop((x1, y1, x2, y2))
    return normalize_icon_png(crop)


def write_manifests(output_dir: Path, entries: list[dict]) -> None:
    manifests_dir = output_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    (manifests_dir / "materials.yaml").write_text("schema_version: 2\n", encoding="utf-8")

    lines = ["classes:"]
    for index, entry in enumerate(entries):
        lines.append(f"  - id: {index}")
        lines.append(f"    name: {entry['class_name']}")
        lines.append(f"    zh_name: {entry['zh_name']}")
    (manifests_dir / "group1.classes.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def old_manifest_entries(old_root: Path) -> list[dict]:
    entries: list[dict] = []
    for class_dir in sorted(old_root.glob("icon_*")):
        if not class_dir.is_dir():
            continue
        class_name = class_dir.name
        entries.append(
            {
                "class_name": class_name,
                "zh_name": LEGACY_OLD_CLASS_META.get(class_name, class_name),
            }
        )
    return entries


def selected_cluster_members(entry: dict, cluster: dict) -> list[dict]:
    members = list(cluster.get("members", []))
    fingerprints = entry.get("member_fingerprints") or []
    if not fingerprints:
        return members
    wanted = set(fingerprints)
    return [member for member in members if member.get("fingerprint") in wanted]


def build_generator_icon_pack(
    *,
    mapping_file: Path,
    candidates_root: Path,
    old_root: Path,
    output_dir: Path,
    timeout: float,
    overwrite: bool,
) -> dict:
    mapping = load_mapping(mapping_file)
    cluster_manifest_path = resolve_workspace_path(
        mapping.get("source_manifest", "work_home/materials/incoming/group1_query_clusters/manifest.json"),
        base_dir=mapping_file.parent,
    )
    cluster_manifest = json.loads(cluster_manifest_path.read_text(encoding="utf-8"))
    clusters = {cluster["cluster_id"]: cluster for cluster in cluster_manifest.get("clusters", [])}
    output_dir.mkdir(parents=True, exist_ok=True)
    icons_root = output_dir / "group1" / "icons"
    icons_root.mkdir(parents=True, exist_ok=True)

    included_entries = [
        entry
        for entry in mapping.get("entries", [])
        if entry.get("selected_source") or entry.get("include_real_cluster")
    ]
    manifest_entries = list(included_entries)
    existing_manifest_names = {entry["class_name"] for entry in manifest_entries}
    added_legacy_classes = 0
    for legacy_entry in old_manifest_entries(old_root):
        if legacy_entry["class_name"] in existing_manifest_names:
            continue
        manifest_entries.append(legacy_entry)
        existing_manifest_names.add(legacy_entry["class_name"])
        added_legacy_classes += 1

    downloaded_lucide: list[str] = []
    downloaded_tabler_filled: list[str] = []
    downloaded_tabler_outline: list[str] = []
    generated_pngs: list[str] = []
    generated_real_pngs: list[str] = []
    generated_old_pngs: list[str] = []

    for entry in manifest_entries:
        class_name = entry["class_name"]
        source_dir = candidates_root / class_name
        source_dir.mkdir(parents=True, exist_ok=True)
        for svg_path in ensure_lucide_svgs(class_name=class_name, class_dir=source_dir, timeout=timeout):
            downloaded_lucide.append(str(svg_path))
        for svg_path in ensure_tabler_outline_svg(entry=entry, class_dir=source_dir, timeout=timeout):
            downloaded_tabler_outline.append(str(svg_path))
        for svg_path in ensure_tabler_filled_svg(entry=entry, class_dir=source_dir, timeout=timeout):
            downloaded_tabler_filled.append(str(svg_path))

        target_dir = icons_root / class_name
        target_dir.mkdir(parents=True, exist_ok=True)
        cluster_id = entry.get("cluster_id")
        cluster = clusters.get(cluster_id) if cluster_id else None
        if cluster:
            for index, member in enumerate(selected_cluster_members(entry, cluster), start=1):
                output_png = target_dir / f"real_{cluster_id}_{index:02d}.png"
                if output_png.exists() and not overwrite:
                    generated_pngs.append(str(output_png))
                    generated_real_pngs.append(str(output_png))
                    continue
                source_path = resolve_workspace_path(member["source_path"], base_dir=cluster_manifest_path.parent)
                processed = extract_member_icon(source_path=source_path, bbox=member["bbox"])
                processed.save(output_png)
                generated_pngs.append(str(output_png))
                generated_real_pngs.append(str(output_png))
        for svg_path in sorted(source_dir.glob("*.svg")):
            output_png = target_dir / f"{svg_path.stem}.png"
            if output_png.exists() and not overwrite:
                generated_pngs.append(str(output_png))
                continue
            rasterize_svg(svg_path, output_png)
            generated_pngs.append(str(output_png))

    for legacy_entry in old_manifest_entries(old_root):
        class_name = legacy_entry["class_name"]
        source_dir = old_root / class_name
        if not source_dir.exists():
            continue
        target_dir = icons_root / class_name
        target_dir.mkdir(parents=True, exist_ok=True)
        for source_png in sorted(source_dir.glob("*.png")):
            output_png = target_dir / f"legacy_{source_png.name}"
            if output_png.exists() and not overwrite:
                generated_pngs.append(str(output_png))
                generated_old_pngs.append(str(output_png))
                continue
            processed = normalize_icon_png(Image.open(source_png).convert("RGBA"))
            processed.save(output_png)
            generated_pngs.append(str(output_png))
            generated_old_pngs.append(str(output_png))

    write_manifests(output_dir, manifest_entries)
    result = {
        "mapping_file": str(mapping_file),
        "candidates_root": str(candidates_root),
        "old_root": str(old_root),
        "output_dir": str(output_dir),
        "class_count": len(manifest_entries),
        "added_legacy_class_count": added_legacy_classes,
        "png_count": len(generated_pngs),
        "generated_real_png_count": len(generated_real_pngs),
        "generated_old_png_count": len(generated_old_pngs),
        "downloaded_lucide_svg_count": len(downloaded_lucide),
        "downloaded_tabler_outline_svg_count": len(downloaded_tabler_outline),
        "downloaded_tabler_filled_svg_count": len(downloaded_tabler_filled),
        "generator_icons_root": str(icons_root),
    }
    (output_dir / "build_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a group1 icon material pack for the generator from candidate icon sources."
    )
    parser.add_argument(
        "--mapping-file",
        type=Path,
        default=DEFAULT_MAPPING_FILE,
        help=f"Semantic candidate mapping file. Default: {DEFAULT_MAPPING_FILE}",
    )
    parser.add_argument(
        "--candidates-root",
        type=Path,
        default=DEFAULT_CANDIDATES_ROOT,
        help=f"Candidate icon root. Default: {DEFAULT_CANDIDATES_ROOT}",
    )
    parser.add_argument(
        "--old-root",
        type=Path,
        default=DEFAULT_OLD_ROOT,
        help=f"Legacy icon root to merge. Default: {DEFAULT_OLD_ROOT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output material pack directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds for Lucide downloads. Default: 20",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing png files.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = build_generator_icon_pack(
        mapping_file=args.mapping_file,
        candidates_root=args.candidates_root,
        old_root=args.old_root,
        output_dir=args.output_dir,
        timeout=args.timeout,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
