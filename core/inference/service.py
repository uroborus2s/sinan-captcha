"""Inference output contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClickPoint:
    x: int
    y: int


@dataclass(frozen=True)
class Group1ClickTarget:
    order: int
    class_id: int
    class_name: str
    bbox: list[int]
    center: list[int]
    score: float | None = None


@dataclass(frozen=True)
class Group1MappingResult:
    status: str
    ordered_targets: list[Group1ClickTarget]
    ordered_clicks: list[ClickPoint]
    missing_orders: list[int]
    ambiguous_orders: list[int]


def map_group1_clicks(
    query_targets: list[dict[str, Any]],
    scene_detections: list[dict[str, Any]],
) -> Group1MappingResult:
    ordered_query = sorted(query_targets, key=_query_sort_key)
    scene_by_class: dict[int, list[dict[str, Any]]] = {}
    for detection in scene_detections:
        class_id = int(detection["class_id"])
        scene_by_class.setdefault(class_id, []).append(detection)
    for detections in scene_by_class.values():
        detections.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)

    ordered_targets: list[Group1ClickTarget] = []
    ordered_clicks: list[ClickPoint] = []
    missing_orders: list[int] = []
    ambiguous_orders: list[int] = []
    used_candidates: set[tuple[int, tuple[int, int, int, int]]] = set()

    for expected_order, query_target in enumerate(ordered_query, start=1):
        class_id = int(query_target["class_id"])
        candidates = list(scene_by_class.get(class_id, []))
        available = [candidate for candidate in candidates if _candidate_key(candidate) not in used_candidates]
        if not available:
            missing_orders.append(expected_order)
            continue
        if len(available) > 1:
            ambiguous_orders.append(expected_order)
        chosen = available[0]
        used_candidates.add(_candidate_key(chosen))
        target = Group1ClickTarget(
            order=expected_order,
            class_id=class_id,
            class_name=str(chosen["class"]),
            bbox=[int(value) for value in chosen["bbox"]],
            center=[int(value) for value in chosen["center"]],
            score=float(chosen["score"]) if "score" in chosen and chosen["score"] is not None else None,
        )
        ordered_targets.append(target)
        ordered_clicks.append(ClickPoint(x=target.center[0], y=target.center[1]))

    status = "ok"
    if missing_orders:
        status = "missing_class"
    elif ambiguous_orders:
        status = "ambiguous_match"
    return Group1MappingResult(
        status=status,
        ordered_targets=ordered_targets,
        ordered_clicks=ordered_clicks,
        missing_orders=missing_orders,
        ambiguous_orders=ambiguous_orders,
    )


def map_group2_center() -> ClickPoint:
    raise NotImplementedError("Group2 center mapping is not implemented yet.")


def _query_sort_key(target: dict[str, Any]) -> tuple[int, float, float]:
    if "order" in target and target["order"] is not None:
        return int(target["order"]), float(target["center"][0]), float(target["center"][1])
    center = target.get("center", [0, 0])
    return 10**9, float(center[0]), float(center[1])


def _candidate_key(target: dict[str, Any]) -> tuple[int, tuple[int, int, int, int]]:
    return int(target["class_id"]), tuple(int(value) for value in target["bbox"])
