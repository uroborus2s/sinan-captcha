"""Inference output contracts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Protocol


class Group1EmbeddingProvider(Protocol):
    def embed_crop(self, image_path: Path, target: dict[str, Any]) -> list[float]:
        """Return a normalized embedding for one target crop."""


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


def map_group1_instances(
    query_targets: list[dict[str, Any]],
    scene_detections: list[dict[str, Any]],
    *,
    query_image_path: Path | None = None,
    scene_image_path: Path | None = None,
    embedding_provider: Group1EmbeddingProvider | None = None,
    similarity_threshold: float = 0.9,
    ambiguity_margin: float = 0.015,
) -> Group1MappingResult:
    if not query_targets:
        return Group1MappingResult(
            status="missing_query",
            ordered_targets=[],
            ordered_clicks=[],
            missing_orders=[],
            ambiguous_orders=[],
        )

    ordered_query = sorted(query_targets, key=_query_sort_key)
    if not scene_detections:
        missing_orders = [int(target.get("order", index)) for index, target in enumerate(ordered_query, start=1)]
        return Group1MappingResult(
            status="missing_candidate",
            ordered_targets=[],
            ordered_clicks=[],
            missing_orders=missing_orders,
            ambiguous_orders=[],
        )

    query_vectors = [
        _embedding_vector(query_target, fallback_image_path=query_image_path, embedding_provider=embedding_provider)
        for query_target in ordered_query
    ]
    scene_vectors = [
        _embedding_vector(scene_detection, fallback_image_path=scene_image_path, embedding_provider=embedding_provider)
        for scene_detection in scene_detections
    ]
    similarity_matrix = [
        [_cosine_similarity(query_vector, scene_vector) for scene_vector in scene_vectors]
        for query_vector in query_vectors
    ]
    assignment = _best_global_assignment(similarity_matrix)

    ordered_targets: list[Group1ClickTarget] = []
    ordered_clicks: list[ClickPoint] = []
    missing_orders: list[int] = []
    ambiguous_orders: list[int] = []
    for expected_order, (query_target, assigned_index, similarities) in enumerate(
        zip(ordered_query, assignment, similarity_matrix),
        start=1,
    ):
        if assigned_index is None:
            missing_orders.append(expected_order)
            continue
        assigned_score = similarities[assigned_index]
        alternative_scores = [
            score for scene_index, score in enumerate(similarities)
            if scene_index != assigned_index
        ]
        next_best_score = max(alternative_scores) if alternative_scores else None
        if assigned_score < similarity_threshold:
            missing_orders.append(expected_order)
            continue
        if next_best_score is not None and (assigned_score - next_best_score) < ambiguity_margin:
            ambiguous_orders.append(expected_order)

        chosen = scene_detections[assigned_index]
        class_id, class_name = _target_label(query_target, order=expected_order)
        target = Group1ClickTarget(
            order=expected_order,
            class_id=class_id,
            class_name=class_name,
            bbox=[int(value) for value in chosen["bbox"]],
            center=[int(value) for value in chosen["center"]],
            score=round(float(assigned_score), 6),
        )
        ordered_targets.append(target)
        ordered_clicks.append(ClickPoint(x=target.center[0], y=target.center[1]))

    status = "ok"
    if missing_orders:
        status = "missing_candidate"
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


def _embedding_vector(
    target: dict[str, Any],
    *,
    fallback_image_path: Path | None,
    embedding_provider: Group1EmbeddingProvider | None,
) -> list[float]:
    image_path = _resolve_target_image_path(target, fallback_image_path=fallback_image_path)
    if embedding_provider is not None:
        return _normalize_vector(embedding_provider.embed_crop(image_path, target))
    crop = _load_target_crop(image_path, target)
    pixels = list(crop.convert("RGB").resize((16, 16)).getdata())
    vector = [float(channel) / 255.0 for pixel in pixels for channel in pixel]
    return _normalize_vector(vector)


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _resolve_target_image_path(target: dict[str, Any], *, fallback_image_path: Path | None) -> Path:
    raw_image_path = target.get("image_path")
    if isinstance(raw_image_path, str) and raw_image_path.strip():
        return Path(raw_image_path)
    if fallback_image_path is not None:
        return fallback_image_path
    raise RuntimeError("group1 instance matcher 缺少 image_path。")


def _load_target_crop(image_path: Path, target: dict[str, Any]):
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("group1 instance matcher 需要 `pillow`。") from exc

    bbox = target.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise RuntimeError("group1 instance matcher 需要合法 bbox。")

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        x1 = max(0, min(width, int(bbox[0])))
        y1 = max(0, min(height, int(bbox[1])))
        x2 = max(x1 + 1, min(width, int(bbox[2])))
        y2 = max(y1 + 1, min(height, int(bbox[3])))
        return rgb.crop((x1, y1, x2, y2)).copy()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


def _best_global_assignment(similarity_matrix: list[list[float]]) -> list[int | None]:
    query_count = len(similarity_matrix)
    candidate_count = len(similarity_matrix[0]) if similarity_matrix else 0
    best_score = float("-inf")
    best_assignment: list[int | None] = [None] * query_count

    def backtrack(query_index: int, used_candidates: set[int], current_assignment: list[int | None], current_score: float) -> None:
        nonlocal best_score, best_assignment
        if query_index >= query_count:
            if current_score > best_score:
                best_score = current_score
                best_assignment = list(current_assignment)
            return

        current_assignment.append(None)
        backtrack(query_index + 1, used_candidates, current_assignment, current_score)
        current_assignment.pop()

        for candidate_index in range(candidate_count):
            if candidate_index in used_candidates:
                continue
            current_assignment.append(candidate_index)
            used_candidates.add(candidate_index)
            backtrack(
                query_index + 1,
                used_candidates,
                current_assignment,
                current_score + similarity_matrix[query_index][candidate_index],
            )
            used_candidates.remove(candidate_index)
            current_assignment.pop()

    backtrack(0, set(), [], 0.0)
    return best_assignment


def _target_label(target: dict[str, Any], *, order: int) -> tuple[int, str]:
    raw_class_id = target.get("class_id")
    raw_class_name = target.get("class")
    class_id = int(raw_class_id) if isinstance(raw_class_id, int) else order - 1
    class_name = str(raw_class_name) if isinstance(raw_class_name, str) and raw_class_name.strip() else f"query_item_{order:02d}"
    return class_id, class_name
