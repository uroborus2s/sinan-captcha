"""Public result types for standalone solver calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ImageInput = str | Path | bytes
BBox = tuple[int, int, int, int]
Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class SliderGapDebugInfo:
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ClickCaptchaDebugInfo:
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SliderGapCenterResult:
    target_center: Point
    target_bbox: BBox
    puzzle_piece_offset: Point | None = None
    debug: SliderGapDebugInfo | None = None


@dataclass(frozen=True, slots=True)
class OrderedClickTarget:
    query_order: int
    center: Point
    class_id: int
    class_name: str
    score: float


@dataclass(frozen=True, slots=True)
class OrderedClickTargetsResult:
    ordered_target_centers: list[Point]
    ordered_targets: list[OrderedClickTarget]
    missing_query_orders: list[int] = field(default_factory=list)
    ambiguous_query_orders: list[int] = field(default_factory=list)
    debug: ClickCaptchaDebugInfo | None = None
