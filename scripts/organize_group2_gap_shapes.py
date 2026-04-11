"""Organize captured group2 gap tiles into semantic representatives."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from solve import group2_runtime

ROOT_DIR = Path(__file__).resolve().parents[1]
WORK_HOME_DIR = ROOT_DIR / "work_home"
DEFAULT_INPUT_ROOT = WORK_HOME_DIR / "materials" / "result"
DEFAULT_OUTPUT_DIR = WORK_HOME_DIR / "materials" / "incoming" / "group2"
DEFAULT_MANIFEST_NAME = "manifest.json"
SHORT_CODE_LENGTH = 8
LONG_CODE_LENGTH = 12
FAMILY_ALIASES = {
    "heart_sticker": "heart",
    "diamond_badge": "diamond",
    "round_badge": "round",
    "shield_badge": "shield",
    "rounded_rectangle_badge": "rect",
    "tall_badge": "tall",
    "rounded_square_badge": "square",
    "rounded_badge": "badge",
}


@dataclass(frozen=True)
class ShapeFeatures:
    width: int
    height: int
    aspect_ratio: float
    fill_ratio: float
    vertical_symmetry: float
    horizontal_symmetry: float
    compactness: float
    top_width_ratio: float
    middle_width_ratio: float
    bottom_width_ratio: float
    upper_max_segments: int
    center_top_fill_ratio: float
    row_profile: tuple[int, ...]
    column_profile: tuple[int, ...]


@dataclass(frozen=True)
class ShapeCandidate:
    source_path: Path
    shape_family: str
    semantic_name: str
    fingerprint: str
    features: ShapeFeatures
    mask: tuple[tuple[bool, ...], ...]


@dataclass
class ShapeRecord:
    output_name: str
    shape_family: str
    semantic_name: str
    fingerprint: str
    source_path: str
    duplicate_sources: list[str]
    features: dict[str, Any]


def _load_image_module() -> Any:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - host env dependent
        raise RuntimeError("当前环境缺少 Pillow，请先执行 `uv sync --extra train`。") from exc
    return Image


def _iter_gap_paths(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.glob("*/gap.jpg")
        if path.is_file()
    )


def _alpha_mask_from_image(image: Any) -> tuple[tuple[bool, ...], ...]:
    alpha = image.getchannel("A")
    width, height = alpha.size
    pixels = list(alpha.getdata())
    mask: list[tuple[bool, ...]] = []
    for row_index in range(height):
        start = row_index * width
        row = tuple(pixels[start + column] > 0 for column in range(width))
        mask.append(row)
    return tuple(mask)


def _mask_bbox(mask: tuple[tuple[bool, ...], ...]) -> tuple[int, int, int, int]:
    ys = [row_index for row_index, row in enumerate(mask) if any(row)]
    if not ys:
        raise ValueError("mask does not contain any positive pixels")
    xs = [
        column_index
        for column_index in range(len(mask[0]))
        if any(mask[row_index][column_index] for row_index in range(len(mask)))
    ]
    return min(xs), min(ys), max(xs), max(ys)


def _crop_mask(
    mask: tuple[tuple[bool, ...], ...],
    bbox: tuple[int, int, int, int],
) -> tuple[tuple[bool, ...], ...]:
    x1, y1, x2, y2 = bbox
    return tuple(
        tuple(mask[row_index][x1 : x2 + 1])
        for row_index in range(y1, y2 + 1)
    )


def _positive_count(mask: tuple[tuple[bool, ...], ...]) -> int:
    return sum(1 for row in mask for value in row if value)


def _row_width(mask: tuple[tuple[bool, ...], ...], row_index: int) -> int:
    return sum(1 for value in mask[row_index] if value)


def _column_height(mask: tuple[tuple[bool, ...], ...], column_index: int) -> int:
    return sum(1 for row in mask if row[column_index])


def _row_segment_count(mask: tuple[tuple[bool, ...], ...], row_index: int) -> int:
    segments = 0
    in_segment = False
    for value in mask[row_index]:
        if value and not in_segment:
            segments += 1
            in_segment = True
        elif not value:
            in_segment = False
    return segments


def _sample_indices(length: int, sample_count: int) -> list[int]:
    if sample_count <= 1:
        return [0]
    if length <= 1:
        return [0] * sample_count
    return [
        min(length - 1, max(0, int(round((length - 1) * index / (sample_count - 1)))))
        for index in range(sample_count)
    ]


def _profile(values: list[float], sample_count: int = 7) -> tuple[int, ...]:
    indices = _sample_indices(len(values), sample_count)
    return tuple(int(round(values[index] * 12.0)) for index in indices)


def _sample_ratio(values: list[float], rel: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * rel))))
    return values[index]


def _symmetry_score(mask: tuple[tuple[bool, ...], ...], *, vertical: bool) -> float:
    height = len(mask)
    width = len(mask[0])
    matched = 0
    total = 0
    if vertical:
        for row in mask:
            for column in range(width // 2):
                total += 1
                if row[column] == row[width - 1 - column]:
                    matched += 1
    else:
        for row_index in range(height // 2):
            top = mask[row_index]
            bottom = mask[height - 1 - row_index]
            for column in range(width):
                total += 1
                if top[column] == bottom[column]:
                    matched += 1
    if total == 0:
        return 1.0
    return matched / float(total)


def _boundary_pixel_count(mask: tuple[tuple[bool, ...], ...]) -> int:
    height = len(mask)
    width = len(mask[0])
    boundary = 0
    for row_index in range(height):
        for column_index in range(width):
            if not mask[row_index][column_index]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx = column_index + dx
                ny = row_index + dy
                if nx < 0 or ny < 0 or nx >= width or ny >= height or not mask[ny][nx]:
                    boundary += 1
                    break
    return boundary


def extract_shape_features(mask: tuple[tuple[bool, ...], ...]) -> ShapeFeatures:
    height = len(mask)
    width = len(mask[0])
    area = _positive_count(mask)
    if area <= 0:
        raise ValueError("mask must contain shape pixels")

    row_ratios = [_row_width(mask, row_index) / float(width) for row_index in range(height)]
    column_ratios = [_column_height(mask, column_index) / float(height) for column_index in range(width)]
    perimeter = _boundary_pixel_count(mask)
    compactness = 0.0
    if perimeter > 0:
        compactness = max(0.0, min(1.0, 4.0 * math.pi * area / float(perimeter * perimeter)))

    upper_rows = _sample_indices(max(1, int(round(height * 0.35))), min(height, max(1, int(round(height * 0.35)))))
    upper_max_segments = max(_row_segment_count(mask, row_index) for row_index in upper_rows)

    top_slice = max(1, int(round(height * 0.25)))
    center_start = max(0, int(round(width * 0.35)))
    center_end = min(width, max(center_start + 1, int(round(width * 0.65))))
    center_top_pixels = 0
    center_top_total = max(1, top_slice * max(1, center_end - center_start))
    for row_index in range(top_slice):
        for column_index in range(center_start, center_end):
            if mask[row_index][column_index]:
                center_top_pixels += 1

    return ShapeFeatures(
        width=width,
        height=height,
        aspect_ratio=width / float(height),
        fill_ratio=area / float(width * height),
        vertical_symmetry=_symmetry_score(mask, vertical=True),
        horizontal_symmetry=_symmetry_score(mask, vertical=False),
        compactness=compactness,
        top_width_ratio=_sample_ratio(row_ratios, 0.12),
        middle_width_ratio=_sample_ratio(row_ratios, 0.50),
        bottom_width_ratio=_sample_ratio(row_ratios, 0.88),
        upper_max_segments=upper_max_segments,
        center_top_fill_ratio=center_top_pixels / float(center_top_total),
        row_profile=_profile(row_ratios),
        column_profile=_profile(column_ratios),
    )


def build_shape_fingerprint(features: ShapeFeatures) -> str:
    parts = [
        f"ar{int(round(features.aspect_ratio * 100))}",
        f"fill{int(round(features.fill_ratio * 100))}",
        f"vs{int(round(features.vertical_symmetry * 100))}",
        f"hs{int(round(features.horizontal_symmetry * 100))}",
        f"cp{int(round(features.compactness * 100))}",
        f"top{int(round(features.top_width_ratio * 100))}",
        f"mid{int(round(features.middle_width_ratio * 100))}",
        f"bot{int(round(features.bottom_width_ratio * 100))}",
        f"seg{features.upper_max_segments}",
        f"ct{int(round(features.center_top_fill_ratio * 100))}",
        "rp" + "-".join(str(value) for value in features.row_profile),
        "cpf" + "-".join(str(value) for value in features.column_profile),
    ]
    return "_".join(parts)


def suggest_shape_family(features: ShapeFeatures) -> str:
    if (
        0.72 <= features.aspect_ratio <= 1.60
        and features.vertical_symmetry >= 0.82
        and features.upper_max_segments >= 2
        and features.bottom_width_ratio <= 0.45
        and features.middle_width_ratio >= 0.55
        and features.center_top_fill_ratio <= 0.75
        and features.fill_ratio <= 0.72
    ):
        return "heart_sticker"

    if (
        0.80 <= features.aspect_ratio <= 1.20
        and features.vertical_symmetry >= 0.90
        and features.horizontal_symmetry >= 0.88
        and features.top_width_ratio <= 0.36
        and features.bottom_width_ratio <= 0.36
        and features.fill_ratio <= 0.66
    ):
        return "diamond_badge"

    if (
        0.78 <= features.aspect_ratio <= 1.22
        and features.vertical_symmetry >= 0.90
        and features.horizontal_symmetry >= 0.86
        and features.fill_ratio >= 0.72
        and features.compactness >= 0.74
    ):
        return "round_badge"

    if (
        features.vertical_symmetry >= 0.88
        and features.top_width_ratio >= 0.70
        and features.middle_width_ratio >= 0.74
        and features.bottom_width_ratio <= 0.24
    ):
        return "shield_badge"

    if features.aspect_ratio >= 1.35:
        return "rounded_rectangle_badge"
    if features.aspect_ratio <= 0.72:
        return "tall_badge"
    if (
        0.80 <= features.aspect_ratio <= 1.20
        and features.vertical_symmetry >= 0.85
        and features.horizontal_symmetry >= 0.80
        and features.fill_ratio >= 0.76
    ):
        return "rounded_square_badge"
    return "rounded_badge"


def _encode_fingerprint_alpha(fingerprint: str, length: int = 10) -> str:
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()
    alphabet = "abcdefghijklmnop"
    letters = [alphabet[int(char, 16)] for char in digest[:length]]
    return "".join(letters)


def build_semantic_name(shape_family: str, fingerprint: str, *, code_length: int = SHORT_CODE_LENGTH) -> str:
    family_alias = FAMILY_ALIASES.get(shape_family, "badge")
    feature_code = _encode_fingerprint_alpha(fingerprint, length=code_length)
    return f"{family_alias}_{feature_code}"


def _candidate_from_gap(path: Path) -> ShapeCandidate:
    Image = _load_image_module()
    with Image.open(path) as source:
        normalized = group2_runtime.normalize_tile_rgba_image(source)
        rgba = normalized.copy()
    full_mask = _alpha_mask_from_image(rgba)
    bbox = _mask_bbox(full_mask)
    cropped_mask = _crop_mask(full_mask, bbox)
    features = extract_shape_features(cropped_mask)
    shape_family = suggest_shape_family(features)
    fingerprint = build_shape_fingerprint(features)
    return ShapeCandidate(
        source_path=path,
        shape_family=shape_family,
        semantic_name=build_semantic_name(shape_family, fingerprint),
        fingerprint=fingerprint,
        features=features,
        mask=cropped_mask,
    )


def collect_unique_candidates(paths: list[Path]) -> tuple[list[ShapeCandidate], dict[str, list[str]]]:
    unique: dict[str, ShapeCandidate] = {}
    duplicates: dict[str, list[str]] = {}
    for path in paths:
        candidate = _candidate_from_gap(path)
        if candidate.fingerprint not in unique:
            unique[candidate.fingerprint] = candidate
            duplicates[candidate.fingerprint] = []
            continue
        duplicates[candidate.fingerprint].append(str(path))
    return list(unique.values()), duplicates


def build_output_plan(
    candidates: list[ShapeCandidate],
    duplicates: dict[str, list[str]],
) -> list[ShapeRecord]:
    sorted_candidates = sorted(candidates, key=lambda item: str(item.source_path))
    assigned_names: dict[str, str] = {}
    used_names: set[str] = set()
    for candidate in sorted_candidates:
        short_name = build_semantic_name(candidate.shape_family, candidate.fingerprint, code_length=SHORT_CODE_LENGTH)
        semantic_name = short_name
        if semantic_name in used_names:
            semantic_name = build_semantic_name(
                candidate.shape_family,
                candidate.fingerprint,
                code_length=LONG_CODE_LENGTH,
            )
        if semantic_name in used_names:
            raise RuntimeError(
                f"语义命名冲突，无法为 {candidate.source_path} 生成唯一文件名：{semantic_name}"
            )
        used_names.add(semantic_name)
        assigned_names[candidate.fingerprint] = semantic_name

    records: list[ShapeRecord] = []
    output_names: set[str] = set()
    for candidate in sorted_candidates:
        semantic_name = assigned_names[candidate.fingerprint]
        output_name = f"{semantic_name}.png"
        if output_name in output_names:
            raise RuntimeError(f"语义命名冲突，无法为 {candidate.source_path} 生成唯一文件名：{output_name}")
        output_names.add(output_name)
        records.append(
            ShapeRecord(
                output_name=output_name,
                shape_family=candidate.shape_family,
                semantic_name=semantic_name,
                fingerprint=candidate.fingerprint,
                source_path=str(candidate.source_path),
                duplicate_sources=duplicates.get(candidate.fingerprint, []),
                features=asdict(candidate.features),
            )
        )
    return records


def _crop_rgba_to_mask(path: Path) -> Any:
    Image = _load_image_module()
    with Image.open(path) as source:
        normalized = group2_runtime.normalize_tile_rgba_image(source)
        rgba = normalized.copy()
    bbox = _mask_bbox(_alpha_mask_from_image(rgba))
    x1, y1, x2, y2 = bbox
    return rgba.crop((x1, y1, x2 + 1, y2 + 1))


def _remove_previous_outputs(output_dir: Path, manifest_path: Path) -> None:
    if not manifest_path.exists():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    records = payload.get("records")
    if not isinstance(records, list):
        return
    for item in records:
        if not isinstance(item, dict):
            continue
        output_name = item.get("output_name")
        if not isinstance(output_name, str):
            continue
        target = output_dir / output_name
        if target.exists():
            target.unlink()


def organize_group2_gaps(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
) -> dict[str, Any]:
    gap_paths = _iter_gap_paths(input_root)
    if not gap_paths:
        raise RuntimeError(f"未在 {input_root} 下找到任何 */gap.jpg")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / manifest_name
    _remove_previous_outputs(output_dir, manifest_path)

    candidates, duplicates = collect_unique_candidates(gap_paths)
    records = build_output_plan(candidates, duplicates)

    for record in records:
        source = Path(record.source_path)
        cropped = _crop_rgba_to_mask(source)
        cropped.save(output_dir / record.output_name)

    payload = {
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "total_gap_images": len(gap_paths),
        "unique_shapes": len(records),
        "deduplicated_images": len(gap_paths) - len(records),
        "records": [asdict(record) for record in records],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按轮廓特征整理 materials/result/*/gap.jpg 到 materials/incoming/group2/"
    )
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    summary = organize_group2_gaps(
        input_root=args.input_root,
        output_dir=args.output_dir,
        manifest_name=args.manifest_name,
    )
    print(f"已扫描 {summary['total_gap_images']} 张 gap 图")
    print(f"保留 {summary['unique_shapes']} 个唯一轮廓")
    print(f"去重 {summary['deduplicated_images']} 张重复图")
    print(f"输出目录: {args.output_dir}")
    print(f"清单文件: {args.output_dir / args.manifest_name}")


if __name__ == "__main__":
    main()
