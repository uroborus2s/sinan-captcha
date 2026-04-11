"""Group1 ONNX Runtime orchestration for standalone click-target solving."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from sinanz_errors import SolverRuntimeError

DEFAULT_DETECT_IMGSZ = 640
DEFAULT_EMBEDDER_IMGSZ = 64
DETECTION_CONFIDENCE_THRESHOLD = 0.25
RUNTIME_TARGET = "python-onnxruntime"
PREFERRED_EXECUTION_PROVIDERS = ("CUDAExecutionProvider", "CPUExecutionProvider")


@dataclass(frozen=True, slots=True)
class DetectedTarget:
    order: int
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    score: float
    class_id: int = 0
    class_name: str = ""


@dataclass(frozen=True, slots=True)
class MatchedClickTarget:
    query_order: int
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    score: float
    class_id: int
    class_name: str


@dataclass(frozen=True, slots=True)
class ClickTargetsRuntimeResult:
    ordered_targets: list[MatchedClickTarget]
    missing_orders: list[int]
    ambiguous_orders: list[int]
    execution_provider: str | None = None
    runtime_target: str = RUNTIME_TARGET


def match_click_targets(
    *,
    proposal_model_path: Path,
    query_model_path: Path,
    embedder_model_path: Path,
    query_image_path: Path,
    background_image_path: Path,
    device: str,
) -> ClickTargetsRuntimeResult:
    ort = _load_onnxruntime()
    providers = _select_execution_providers(ort, device)
    proposal_session = ort.InferenceSession(str(proposal_model_path), providers=providers)
    query_session = ort.InferenceSession(str(query_model_path), providers=providers)
    embedder_session = ort.InferenceSession(str(embedder_model_path), providers=providers)

    np, image_cls = _load_image_modules()
    query_image = _load_rgb_image(image_cls, query_image_path)
    background_image = _load_rgb_image(image_cls, background_image_path)

    query_detections = _run_detection_session(np, query_session, query_image, ordered=True)
    scene_detections = _run_detection_session(np, proposal_session, background_image, ordered=False)
    query_embeddings = [
        _embed_detection(np, embedder_session, query_image, detection)
        for detection in query_detections
    ]
    scene_embeddings = [
        _embed_detection(np, embedder_session, background_image, detection)
        for detection in scene_detections
    ]
    assignment = assign_ordered_targets(
        query_detections=query_detections,
        scene_detections=scene_detections,
        query_embeddings=query_embeddings,
        scene_embeddings=scene_embeddings,
    )
    return ClickTargetsRuntimeResult(
        ordered_targets=assignment.ordered_targets,
        missing_orders=assignment.missing_orders,
        ambiguous_orders=assignment.ambiguous_orders,
        execution_provider=providers[0] if providers else None,
    )


def assign_ordered_targets(
    *,
    query_detections: list[DetectedTarget],
    scene_detections: list[DetectedTarget],
    query_embeddings: list[list[float]],
    scene_embeddings: list[list[float]],
    similarity_threshold: float = 0.9,
    ambiguity_margin: float = 0.015,
) -> ClickTargetsRuntimeResult:
    ordered_query = sorted(query_detections, key=lambda item: (item.order, item.center[0], item.center[1]))
    if not ordered_query:
        return ClickTargetsRuntimeResult(ordered_targets=[], missing_orders=[], ambiguous_orders=[])
    if not scene_detections:
        return ClickTargetsRuntimeResult(
            ordered_targets=[],
            missing_orders=[item.order for item in ordered_query],
            ambiguous_orders=[],
        )

    similarity_matrix = [
        [_cosine_similarity(query_vector, scene_vector) for scene_vector in scene_embeddings]
        for query_vector in query_embeddings
    ]
    assignment = _best_global_assignment(similarity_matrix)

    ordered_targets: list[MatchedClickTarget] = []
    missing_orders: list[int] = []
    ambiguous_orders: list[int] = []
    for query_target, assigned_index, similarities in zip(
        ordered_query,
        assignment,
        similarity_matrix,
        strict=False,
    ):
        if assigned_index is None:
            missing_orders.append(query_target.order)
            continue
        assigned_score = similarities[assigned_index]
        alternative_scores = [score for index, score in enumerate(similarities) if index != assigned_index]
        next_best_score = max(alternative_scores) if alternative_scores else None
        if assigned_score < similarity_threshold:
            missing_orders.append(query_target.order)
            continue
        if next_best_score is not None and (assigned_score - next_best_score) < ambiguity_margin:
            ambiguous_orders.append(query_target.order)
        scene_target = scene_detections[assigned_index]
        ordered_targets.append(
            MatchedClickTarget(
                query_order=query_target.order,
                bbox=scene_target.bbox,
                center=scene_target.center,
                score=round(float(assigned_score), 6),
                class_id=query_target.order - 1,
                class_name=f"query_item_{query_target.order:02d}",
            )
        )

    return ClickTargetsRuntimeResult(
        ordered_targets=ordered_targets,
        missing_orders=missing_orders,
        ambiguous_orders=ambiguous_orders,
    )


def _run_detection_session(np: Any, session: Any, image: Any, *, ordered: bool) -> list[DetectedTarget]:
    input_name = session.get_inputs()[0].name
    image_size = _resolve_session_image_size(session, default=DEFAULT_DETECT_IMGSZ)
    inputs, meta = _prepare_detection_input(np, image, image_size=image_size)
    outputs = session.run(None, {input_name: inputs})
    if not outputs:
        raise SolverRuntimeError("group1 onnxruntime 未返回检测输出。")
    detections = _decode_detections(np, outputs, meta)
    if ordered:
        detections.sort(key=lambda item: (item.center[0], item.center[1]))
        detections = [
            DetectedTarget(
                order=index,
                bbox=item.bbox,
                center=item.center,
                score=item.score,
                class_id=index - 1,
                class_name=f"query_item_{index:02d}",
            )
            for index, item in enumerate(detections, start=1)
        ]
    return detections


def _embed_detection(np: Any, session: Any, image: Any, detection: DetectedTarget) -> list[float]:
    input_name = session.get_inputs()[0].name
    image_size = _resolve_session_image_size(session, default=DEFAULT_EMBEDDER_IMGSZ)
    tensor = _prepare_embedder_input(np, image, detection, image_size=image_size)
    outputs = session.run(None, {input_name: tensor})
    if not outputs:
        raise SolverRuntimeError("group1 onnxruntime 未返回 embedding 输出。")
    vector = np.asarray(outputs[0], dtype=np.float32).reshape(-1).tolist()
    return _normalize_vector([float(value) for value in vector])


def _prepare_detection_input(np: Any, image: Any, *, image_size: int) -> tuple[Any, dict[str, float | int]]:
    width, height = image.size
    scale = min(image_size / float(width), image_size / float(height))
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized = image.resize((resized_width, resized_height))
    canvas = np.full((image_size, image_size, 3), 114.0, dtype=np.float32)
    offset_x = int((image_size - resized_width) / 2)
    offset_y = int((image_size - resized_height) / 2)
    resized_pixels = np.asarray(resized, dtype=np.float32)
    canvas[offset_y:offset_y + resized_height, offset_x:offset_x + resized_width, :] = resized_pixels
    tensor = (canvas / 255.0).transpose(2, 0, 1)[None, :, :, :]
    return tensor.astype(np.float32), {
        "image_size": image_size,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "scale": scale,
        "width": width,
        "height": height,
    }


def _prepare_embedder_input(np: Any, image: Any, detection: DetectedTarget, *, image_size: int) -> Any:
    width, height = image.size
    x1 = max(0, min(width, int(detection.bbox[0])))
    y1 = max(0, min(height, int(detection.bbox[1])))
    x2 = max(x1 + 1, min(width, int(detection.bbox[2])))
    y2 = max(y1 + 1, min(height, int(detection.bbox[3])))
    crop = image.crop((x1, y1, x2, y2)).resize((image_size, image_size))
    tensor = np.asarray(crop, dtype=np.float32).transpose(2, 0, 1)[None, :, :, :] / 255.0
    return tensor.astype(np.float32)


def _decode_detections(np: Any, outputs: list[Any], meta: dict[str, float | int]) -> list[DetectedTarget]:
    rows = _coerce_detection_rows(np, outputs)
    detections: list[DetectedTarget] = []
    for row in rows:
        candidate = _parse_detection_row(np, row)
        if candidate is None or candidate["score"] < DETECTION_CONFIDENCE_THRESHOLD:
            continue
        bbox = _restore_bbox(candidate["bbox"], meta)
        center = (
            int(round((bbox[0] + bbox[2]) / 2)),
            int(round((bbox[1] + bbox[3]) / 2)),
        )
        detections.append(
            DetectedTarget(
                order=len(detections) + 1,
                bbox=bbox,
                center=center,
                score=float(candidate["score"]),
                class_id=int(candidate["class_id"]),
                class_name=str(candidate["class_name"]),
            )
        )
    return detections


def _coerce_detection_rows(np: Any, outputs: list[Any]) -> Any:
    for output in outputs:
        array = np.asarray(output)
        if array.size == 0:
            continue
        if array.ndim == 3 and array.shape[0] == 1 and array.shape[2] == 6:
            return array[0]
        if array.ndim == 2 and array.shape[1] == 6:
            return array
        if array.ndim == 3 and array.shape[0] == 1:
            return array[0].T
        if array.ndim == 2 and array.shape[0] < array.shape[1]:
            return array.T
        if array.ndim == 2:
            return array
    return np.empty((0, 6), dtype=np.float32)


def _parse_detection_row(np: Any, row: Any) -> dict[str, Any] | None:
    values = [float(value) for value in np.asarray(row, dtype=np.float32).reshape(-1).tolist()]
    if len(values) < 5:
        return None
    if len(values) == 6:
        x1, y1, x2, y2, score, class_id = values
        return {
            "bbox": (x1, y1, x2, y2),
            "score": score,
            "class_id": int(class_id),
            "class_name": f"class_{int(class_id)}",
        }

    x_center, y_center, width, height = values[:4]
    class_scores = values[4:]
    if not class_scores:
        return None
    class_index = int(np.argmax(class_scores))
    score = float(class_scores[class_index])
    return {
        "bbox": (
            x_center - width / 2.0,
            y_center - height / 2.0,
            x_center + width / 2.0,
            y_center + height / 2.0,
        ),
        "score": score,
        "class_id": class_index,
        "class_name": f"class_{class_index}",
    }


def _restore_bbox(
    bbox: tuple[float, float, float, float],
    meta: dict[str, float | int],
) -> tuple[int, int, int, int]:
    scale = float(meta["scale"])
    offset_x = float(meta["offset_x"])
    offset_y = float(meta["offset_y"])
    width = int(meta["width"])
    height = int(meta["height"])
    x1 = max(0, min(width, int(round((bbox[0] - offset_x) / scale))))
    y1 = max(0, min(height, int(round((bbox[1] - offset_y) / scale))))
    x2 = max(x1 + 1, min(width, int(round((bbox[2] - offset_x) / scale))))
    y2 = max(y1 + 1, min(height, int(round((bbox[3] - offset_y) / scale))))
    return (x1, y1, x2, y2)


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))


def _best_global_assignment(similarity_matrix: list[list[float]]) -> list[int | None]:
    query_count = len(similarity_matrix)
    candidate_count = len(similarity_matrix[0]) if similarity_matrix else 0
    best_score = float("-inf")
    best_assignment: list[int | None] = [None] * query_count

    def backtrack(
        query_index: int,
        used_candidates: set[int],
        current_assignment: list[int | None],
        current_score: float,
    ) -> None:
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


def _load_rgb_image(image_cls: Any, image_path: Path) -> Any:
    with image_cls.open(image_path) as image:
        return image.convert("RGB").copy()


def _load_image_modules() -> tuple[Any, Any]:
    try:
        import numpy as np
        from PIL import Image
    except Exception as exc:  # pragma: no cover - host env dependent
        raise SolverRuntimeError("当前环境缺少 `numpy` / `Pillow`，无法准备点选求解输入。") from exc
    return np, Image


def _load_onnxruntime() -> Any:
    try:
        import onnxruntime as ort
    except Exception as exc:  # pragma: no cover - host env dependent
        raise SolverRuntimeError("当前环境缺少 `onnxruntime`，无法执行点选推理。") from exc
    return ort


def _resolve_session_image_size(session: Any, *, default: int) -> int:
    inputs = session.get_inputs()
    if not inputs:
        return default
    shape = getattr(inputs[0], "shape", None)
    if not isinstance(shape, (list, tuple)) or len(shape) < 4:
        return default
    height = shape[2]
    width = shape[3]
    if isinstance(height, int) and isinstance(width, int) and height > 0 and width > 0 and height == width:
        return int(height)
    return default


def _select_execution_providers(ort: Any, device: str) -> list[str]:
    available = set(str(provider) for provider in ort.get_available_providers())
    normalized = device.strip().lower()
    if normalized == "cpu":
        return ["CPUExecutionProvider"]

    preferred = list(PREFERRED_EXECUTION_PROVIDERS)
    if normalized not in ("", "auto", "cpu"):
        preferred = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    selected = [provider for provider in preferred if provider in available]
    if selected:
        return selected
    if "CPUExecutionProvider" in available:
        return ["CPUExecutionProvider"]
    return list(available)
