"""Rule-based query splitter for group1 instance matching."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MIN_FOREGROUND_ALPHA = 16
BACKGROUND_DISTANCE_THRESHOLD = 28.0
BACKGROUND_LUMA_THRESHOLD = 12.0
MAX_BRIDGE_GAP_PX = 2
MIN_ICON_WIDTH_PX = 4
MIN_ICON_HEIGHT_PX = 4


def split_group1_query_image(query_image_path: Path) -> list[dict[str, Any]]:
    image_module = _load_pillow_image()
    with image_module.open(query_image_path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        mask = _build_foreground_mask(rgba)

    spans = _find_column_spans(mask, width)
    items: list[dict[str, Any]] = []
    for order, (start_x, end_x) in enumerate(spans, start=1):
        bbox = _resolve_bbox(mask, start_x=start_x, end_x=end_x, image_width=width, image_height=height)
        if bbox is None:
            continue
        x1, y1, x2, y2 = bbox
        items.append(
            {
                "order": order,
                "bbox": [x1, y1, x2, y2],
                "center": [int(round((x1 + x2) / 2)), int(round((y1 + y2) / 2))],
                "score": 1.0,
            }
        )
    return items


def _load_pillow_image():
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("group1 query splitter 需要 `pillow`。") from exc
    return Image


def _build_foreground_mask(image: Any) -> list[list[bool]]:
    width, height = image.size
    pixels = image.load()
    border_pixels = _border_pixels(pixels, width=width, height=height)
    if any(alpha < MIN_FOREGROUND_ALPHA for _, _, _, alpha in border_pixels):
        return [
            [int(pixels[x, y][3]) >= MIN_FOREGROUND_ALPHA for x in range(width)]
            for y in range(height)
        ]

    background_rgb = _median_rgb(border_pixels)
    mask = [
        [
            int(pixels[x, y][3]) >= MIN_FOREGROUND_ALPHA
            and _color_distance(pixels[x, y][:3], background_rgb) >= BACKGROUND_DISTANCE_THRESHOLD
            for x in range(width)
        ]
        for y in range(height)
    ]
    if _foreground_pixel_count(mask) > 0:
        return mask

    background_luma = _luma(background_rgb)
    return [
        [
            int(pixels[x, y][3]) >= MIN_FOREGROUND_ALPHA
            and abs(_luma(pixels[x, y][:3]) - background_luma) >= BACKGROUND_LUMA_THRESHOLD
            for x in range(width)
        ]
        for y in range(height)
    ]


def _border_pixels(pixels: Any, *, width: int, height: int) -> list[tuple[int, int, int, int]]:
    items: list[tuple[int, int, int, int]] = []
    for x in range(width):
        items.append(tuple(int(value) for value in pixels[x, 0]))
        if height > 1:
            items.append(tuple(int(value) for value in pixels[x, height - 1]))
    for y in range(1, max(1, height - 1)):
        items.append(tuple(int(value) for value in pixels[0, y]))
        if width > 1:
            items.append(tuple(int(value) for value in pixels[width - 1, y]))
    return items


def _median_rgb(pixels: list[tuple[int, int, int, int]]) -> tuple[int, int, int]:
    red = sorted(item[0] for item in pixels)
    green = sorted(item[1] for item in pixels)
    blue = sorted(item[2] for item in pixels)
    middle = len(pixels) // 2
    return red[middle], green[middle], blue[middle]


def _foreground_pixel_count(mask: list[list[bool]]) -> int:
    return sum(1 for row in mask for value in row if value)


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)) ** 0.5


def _luma(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return (0.2126 * float(red)) + (0.7152 * float(green)) + (0.0722 * float(blue))


def _find_column_spans(mask: list[list[bool]], image_width: int) -> list[tuple[int, int]]:
    active_columns = [any(row[x] for row in mask) for x in range(image_width)]
    bridged_columns = _bridge_small_gaps(active_columns)
    spans: list[tuple[int, int]] = []
    span_start: int | None = None
    for x, is_active in enumerate(bridged_columns):
        if is_active and span_start is None:
            span_start = x
            continue
        if span_start is not None and not is_active:
            spans.append((span_start, x))
            span_start = None
    if span_start is not None:
        spans.append((span_start, image_width))
    return spans


def _bridge_small_gaps(active_columns: list[bool]) -> list[bool]:
    bridged = list(active_columns)
    index = 0
    total = len(active_columns)
    while index < total:
        if active_columns[index]:
            index += 1
            continue
        gap_start = index
        while index < total and not active_columns[index]:
            index += 1
        gap_end = index
        gap_length = gap_end - gap_start
        if (
            gap_start > 0
            and gap_end < total
            and active_columns[gap_start - 1]
            and active_columns[gap_end]
            and gap_length <= MAX_BRIDGE_GAP_PX
        ):
            for fill_index in range(gap_start, gap_end):
                bridged[fill_index] = True
    return bridged


def _resolve_bbox(
    mask: list[list[bool]],
    *,
    start_x: int,
    end_x: int,
    image_width: int,
    image_height: int,
) -> list[int] | None:
    foreground_x: list[int] = []
    foreground_y: list[int] = []
    for y in range(image_height):
        for x in range(start_x, min(end_x, image_width)):
            if not mask[y][x]:
                continue
            foreground_x.append(x)
            foreground_y.append(y)
    if not foreground_x or not foreground_y:
        return None
    x1 = min(foreground_x)
    y1 = min(foreground_y)
    x2 = max(foreground_x) + 1
    y2 = max(foreground_y) + 1
    if (x2 - x1) < MIN_ICON_WIDTH_PX or (y2 - y1) < MIN_ICON_HEIGHT_PX:
        return None
    return [x1, y1, x2, y2]
