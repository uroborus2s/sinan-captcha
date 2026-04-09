"""Extract and cluster captured group1 query icons into reusable representatives."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = ROOT_DIR / "materials" / "business_exams" / "group1" / "reviewed-v1" / "import" / "query"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "materials" / "incoming" / "group1_query_clusters"
DEFAULT_MANIFEST_NAME = "manifest.json"
NORMALIZED_MASK_SIZE = 24
DEFAULT_DARK_THRESHOLD = 180
DEFAULT_MIN_PIXELS = 20
DEFAULT_MAX_HAMMING_DISTANCE = 56
DEFAULT_ASPECT_RATIO_DELTA = 0.45
DEFAULT_FILL_RATIO_DELTA = 0.20


@dataclass(frozen=True)
class QueryIconFeatures:
    width: int
    height: int
    aspect_ratio: float
    fill_ratio: float
    vertical_symmetry: float
    horizontal_symmetry: float
    row_profile: tuple[int, ...]
    column_profile: tuple[int, ...]


@dataclass(frozen=True)
class QueryIconCandidate:
    source_path: Path
    sample_id: str
    order: int
    bbox: tuple[int, int, int, int]
    features: QueryIconFeatures
    normalized_bits: str
    fingerprint: str
    mask: tuple[tuple[bool, ...], ...]


@dataclass(frozen=True)
class QueryIconCluster:
    cluster_id: str
    representative: QueryIconCandidate
    members: tuple[QueryIconCandidate, ...]


@dataclass
class QueryIconRecord:
    cluster_id: str
    output_name: str
    fingerprint: str
    representative: dict[str, Any]
    members: list[dict[str, Any]]
    features: dict[str, Any]


def _load_pillow() -> tuple[Any, Any, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - host env dependent
        raise RuntimeError("当前环境缺少 Pillow，请先执行 `uv sync --extra train`。") from exc
    return Image, ImageDraw, ImageFont


def _iter_query_paths(input_root: Path) -> list[Path]:
    return sorted(path for path in input_root.iterdir() if path.is_file())


def _gray_mask_from_image(image: Any, *, dark_threshold: int) -> tuple[tuple[bool, ...], ...]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.getdata())
    rows: list[tuple[bool, ...]] = []
    for row_index in range(height):
        row: list[bool] = []
        start = row_index * width
        for red, green, blue, alpha in pixels[start : start + width]:
            gray = int(round(red * 0.299 + green * 0.587 + blue * 0.114))
            row.append(alpha > 0 and gray <= dark_threshold)
        rows.append(tuple(row))
    return tuple(rows)


def extract_query_icon_components(
    mask: tuple[tuple[bool, ...], ...],
    *,
    min_pixels: int = DEFAULT_MIN_PIXELS,
) -> list[tuple[int, int, int, int]]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    visited = [[False] * width for _ in range(height)]
    components: list[tuple[int, int, int, int]] = []

    for row_index in range(height):
        for column_index in range(width):
            if not mask[row_index][column_index] or visited[row_index][column_index]:
                continue
            stack = [(column_index, row_index)]
            visited[row_index][column_index] = True
            points: list[tuple[int, int]] = []
            while stack:
                x, y = stack.pop()
                points.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if visited[ny][nx] or not mask[ny][nx]:
                        continue
                    visited[ny][nx] = True
                    stack.append((nx, ny))
            if len(points) < min_pixels:
                continue
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            components.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1))

    components.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return components


def _crop_mask(
    mask: tuple[tuple[bool, ...], ...],
    bbox: tuple[int, int, int, int],
) -> tuple[tuple[bool, ...], ...]:
    x1, y1, x2, y2 = bbox
    return tuple(tuple(row[x1:x2]) for row in mask[y1:y2])


def extract_query_icon_features(mask: tuple[tuple[bool, ...], ...]) -> QueryIconFeatures:
    height = len(mask)
    width = len(mask[0]) if height else 0
    if width <= 0 or height <= 0:
        raise ValueError("mask must be non-empty")
    area = _positive_count(mask)
    if area <= 0:
        raise ValueError("mask must contain positive pixels")
    row_ratios = [_row_width(mask, row_index) / float(width) for row_index in range(height)]
    column_ratios = [_column_height(mask, column_index) / float(height) for column_index in range(width)]

    return QueryIconFeatures(
        width=width,
        height=height,
        aspect_ratio=round(width / float(height), 4),
        fill_ratio=round(area / float(width * height), 4),
        vertical_symmetry=round(_symmetry_score(mask, vertical=True), 4),
        horizontal_symmetry=round(_symmetry_score(mask, vertical=False), 4),
        row_profile=_profile(row_ratios),
        column_profile=_profile(column_ratios),
    )


def build_query_icon_fingerprint(features: QueryIconFeatures, normalized_bits: str) -> str:
    payload = {
        "aspect_ratio": features.aspect_ratio,
        "fill_ratio": features.fill_ratio,
        "vertical_symmetry": features.vertical_symmetry,
        "horizontal_symmetry": features.horizontal_symmetry,
        "row_profile": features.row_profile,
        "column_profile": features.column_profile,
        "bits": normalized_bits,
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:12]


def build_query_icon_candidates(
    image_path: Path,
    *,
    dark_threshold: int = DEFAULT_DARK_THRESHOLD,
    min_pixels: int = DEFAULT_MIN_PIXELS,
) -> list[QueryIconCandidate]:
    Image, _, _ = _load_pillow()
    image = Image.open(image_path)
    mask = _gray_mask_from_image(image, dark_threshold=dark_threshold)
    candidates: list[QueryIconCandidate] = []
    for order, bbox in enumerate(extract_query_icon_components(mask, min_pixels=min_pixels), start=1):
        cropped = _crop_mask(mask, bbox)
        normalized = _resize_mask(cropped, NORMALIZED_MASK_SIZE, NORMALIZED_MASK_SIZE)
        bits = _mask_bits(normalized)
        features = extract_query_icon_features(cropped)
        candidates.append(
            QueryIconCandidate(
                source_path=image_path,
                sample_id=image_path.stem,
                order=order,
                bbox=bbox,
                features=features,
                normalized_bits=bits,
                fingerprint=build_query_icon_fingerprint(features, bits),
                mask=cropped,
            )
        )
    return candidates


def cluster_query_icon_candidates(
    candidates: list[QueryIconCandidate],
    *,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
    aspect_ratio_delta: float = DEFAULT_ASPECT_RATIO_DELTA,
    fill_ratio_delta: float = DEFAULT_FILL_RATIO_DELTA,
) -> list[QueryIconCluster]:
    clusters: list[list[QueryIconCandidate]] = []
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.features.aspect_ratio,
            item.features.fill_ratio,
            item.source_path.name,
            item.order,
        ),
    )
    for candidate in ordered:
        selected_cluster: list[QueryIconCandidate] | None = None
        selected_distance: int | None = None
        for cluster in clusters:
            representative = cluster[0]
            if abs(candidate.features.aspect_ratio - representative.features.aspect_ratio) > aspect_ratio_delta:
                continue
            if abs(candidate.features.fill_ratio - representative.features.fill_ratio) > fill_ratio_delta:
                continue
            distance = hamming_distance(candidate.normalized_bits, representative.normalized_bits)
            if distance > max_hamming_distance:
                continue
            if selected_distance is None or distance < selected_distance:
                selected_cluster = cluster
                selected_distance = distance
        if selected_cluster is None:
            clusters.append([candidate])
        else:
            selected_cluster.append(candidate)

    result: list[QueryIconCluster] = []
    for index, members in enumerate(sorted(clusters, key=len, reverse=True), start=1):
        cluster_id = f"cluster_{index:03d}"
        representative = _pick_cluster_representative(members)
        ordered_members = sorted(
            members,
            key=lambda item: (item.source_path.name, item.order, item.fingerprint),
        )
        result.append(
            QueryIconCluster(
                cluster_id=cluster_id,
                representative=representative,
                members=tuple(ordered_members),
            )
        )
    return result


def build_output_plan(clusters: list[QueryIconCluster]) -> list[QueryIconRecord]:
    records: list[QueryIconRecord] = []
    for cluster in clusters:
        representative = cluster.representative
        records.append(
            QueryIconRecord(
                cluster_id=cluster.cluster_id,
                output_name=f"{cluster.cluster_id}.png",
                fingerprint=representative.fingerprint,
                representative=_candidate_payload(representative),
                members=[_candidate_payload(member) for member in cluster.members],
                features=asdict(representative.features),
            )
        )
    return records


def organize_query_icons(
    *,
    input_root: Path,
    output_dir: Path,
    dark_threshold: int = DEFAULT_DARK_THRESHOLD,
    min_pixels: int = DEFAULT_MIN_PIXELS,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> dict[str, Any]:
    query_paths = _iter_query_paths(input_root)
    if not query_paths:
        raise RuntimeError(f"未找到 group1 query 图片：{input_root}")

    all_candidates: list[QueryIconCandidate] = []
    for path in query_paths:
        all_candidates.extend(
            build_query_icon_candidates(
                path,
                dark_threshold=dark_threshold,
                min_pixels=min_pixels,
            )
        )
    if not all_candidates:
        raise RuntimeError(f"未能从 query 图片中提取任何图标：{input_root}")

    clusters = cluster_query_icon_candidates(
        all_candidates,
        max_hamming_distance=max_hamming_distance,
    )
    records = build_output_plan(clusters)
    output_dir.mkdir(parents=True, exist_ok=True)
    representative_dir = output_dir / "representatives"
    representative_dir.mkdir(parents=True, exist_ok=True)

    for record, cluster in zip(records, clusters, strict=False):
        _write_representative_crop(cluster.representative, representative_dir / record.output_name)

    overview_path = output_dir / "overview.png"
    _write_overview_sheet(clusters, representative_dir, overview_path)
    manifest_path = output_dir / DEFAULT_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(
            {
                "input_root": str(input_root),
                "output_dir": str(output_dir),
                "query_count": len(query_paths),
                "icon_count": len(all_candidates),
                "cluster_count": len(records),
                "clusters": [asdict(record) for record in records],
                "overview_image": str(overview_path.relative_to(output_dir)),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "query_count": len(query_paths),
        "icon_count": len(all_candidates),
        "cluster_count": len(records),
        "manifest_path": str(manifest_path),
        "overview_path": str(overview_path),
    }


def _positive_count(mask: tuple[tuple[bool, ...], ...]) -> int:
    return sum(1 for row in mask for value in row if value)


def _row_width(mask: tuple[tuple[bool, ...], ...], row_index: int) -> int:
    return sum(1 for value in mask[row_index] if value)


def _column_height(mask: tuple[tuple[bool, ...], ...], column_index: int) -> int:
    return sum(1 for row in mask if row[column_index])


def _symmetry_score(mask: tuple[tuple[bool, ...], ...], *, vertical: bool) -> float:
    height = len(mask)
    width = len(mask[0])
    matched = 0
    total = 0
    if vertical:
        for row in mask:
            for column_index in range(width // 2):
                total += 1
                if row[column_index] == row[width - 1 - column_index]:
                    matched += 1
    else:
        for row_index in range(height // 2):
            top = mask[row_index]
            bottom = mask[height - 1 - row_index]
            for column_index in range(width):
                total += 1
                if top[column_index] == bottom[column_index]:
                    matched += 1
    if total == 0:
        return 1.0
    return matched / float(total)


def _profile(values: list[float], sample_count: int = 7) -> tuple[int, ...]:
    if not values:
        return tuple()
    if len(values) == 1:
        return tuple(int(round(values[0] * 12.0)) for _ in range(sample_count))
    result: list[int] = []
    for index in range(sample_count):
        position = int(round((len(values) - 1) * index / max(1, sample_count - 1)))
        result.append(int(round(values[position] * 12.0)))
    return tuple(result)


def _resize_mask(
    mask: tuple[tuple[bool, ...], ...],
    width: int,
    height: int,
) -> tuple[tuple[bool, ...], ...]:
    source_height = len(mask)
    source_width = len(mask[0]) if source_height else 0
    if source_width <= 0 or source_height <= 0:
        raise ValueError("mask must be non-empty")
    rows: list[tuple[bool, ...]] = []
    for row_index in range(height):
        source_y = min(source_height - 1, int(math.floor(row_index * source_height / float(height))))
        row: list[bool] = []
        for column_index in range(width):
            source_x = min(source_width - 1, int(math.floor(column_index * source_width / float(width))))
            row.append(mask[source_y][source_x])
        rows.append(tuple(row))
    return tuple(rows)


def _mask_bits(mask: tuple[tuple[bool, ...], ...]) -> str:
    return "".join("1" if value else "0" for row in mask for value in row)


def hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("bit strings must have the same length")
    return sum(a != b for a, b in zip(left, right, strict=False))


def _pick_cluster_representative(members: list[QueryIconCandidate]) -> QueryIconCandidate:
    best_member = members[0]
    best_score: tuple[float, float, str, int] | None = None
    for member in members:
        score = (
            -member.features.vertical_symmetry,
            -member.features.fill_ratio,
            member.source_path.name,
            member.order,
        )
        if best_score is None or score < best_score:
            best_score = score
            best_member = member
    return best_member


def _candidate_payload(candidate: QueryIconCandidate) -> dict[str, Any]:
    return {
        "source_path": str(candidate.source_path),
        "sample_id": candidate.sample_id,
        "order": candidate.order,
        "bbox": list(candidate.bbox),
        "fingerprint": candidate.fingerprint,
    }


def _write_representative_crop(candidate: QueryIconCandidate, output_path: Path) -> None:
    Image, _, _ = _load_pillow()
    image = Image.open(candidate.source_path).convert("RGBA")
    x1, y1, x2, y2 = candidate.bbox
    padding = 2
    crop = image.crop((max(0, x1 - padding), max(0, y1 - padding), x2 + padding, y2 + padding))
    crop.save(output_path)


def _write_overview_sheet(
    clusters: list[QueryIconCluster],
    representative_dir: Path,
    overview_path: Path,
) -> None:
    Image, ImageDraw, ImageFont = _load_pillow()
    cell_width = 120
    cell_height = 120
    columns = 4
    rows = max(1, math.ceil(len(clusters) / columns))
    overview = Image.new("RGBA", (columns * cell_width, rows * cell_height), (248, 250, 252, 255))
    draw = ImageDraw.Draw(overview)
    font = ImageFont.load_default()

    for index, cluster in enumerate(clusters):
        representative_path = representative_dir / f"{cluster.cluster_id}.png"
        image = Image.open(representative_path).convert("RGBA")
        image.thumbnail((88, 88))
        column = index % columns
        row = index // columns
        origin_x = column * cell_width
        origin_y = row * cell_height
        image_x = origin_x + (cell_width - image.width) // 2
        image_y = origin_y + 8
        overview.alpha_composite(image, (image_x, image_y))
        draw.text((origin_x + 8, origin_y + 96), cluster.cluster_id, fill=(32, 40, 54, 255), font=font)
        draw.text(
            (origin_x + 8, origin_y + 108),
            f"n={len(cluster.members)}",
            fill=(90, 99, 110, 255),
            font=font,
        )
    overview.save(overview_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract and cluster captured group1 query icons.")
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dark-threshold", type=int, default=DEFAULT_DARK_THRESHOLD)
    parser.add_argument("--min-pixels", type=int, default=DEFAULT_MIN_PIXELS)
    parser.add_argument("--max-hamming-distance", type=int, default=DEFAULT_MAX_HAMMING_DISTANCE)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = organize_query_icons(
        input_root=args.input_root,
        output_dir=args.output_dir,
        dark_threshold=args.dark_threshold,
        min_pixels=args.min_pixels,
        max_hamming_distance=args.max_hamming_distance,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
