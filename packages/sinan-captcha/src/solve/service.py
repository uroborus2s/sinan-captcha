"""Unified local solver service for group1/group2 bundles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from inference.service import Group1ClickTarget, map_group1_instances
from solve.bundle import SolverBundle, load_solver_bundle
from solve import group2_runtime
from solve.contracts import (
    Group1SolveInputs,
    Group2SolveInputs,
    SolveRequest,
    SolveResponse,
    create_error_response,
)

GROUP1_IMGSZ = 640
GROUP1_CONF = 0.25


@dataclass(frozen=True)
class RouteDecision:
    task: str
    route_source: str


class UnifiedSolverService:
    def __init__(self, bundle: SolverBundle) -> None:
        self.bundle = bundle
        self._proposal_model: Any | None = None
        self._query_model: Any | None = None
        self._group1_embedder_cache: dict[str, Any] = {}
        self._group2_cache: dict[str, tuple[Any, int, Any]] = {}

    @classmethod
    def from_bundle_dir(cls, bundle_dir: Path) -> "UnifiedSolverService":
        return cls(load_solver_bundle(bundle_dir))

    def solve(self, request: SolveRequest) -> SolveResponse:
        try:
            route = resolve_route(request)
        except Exception as exc:
            return create_error_response(
                request_id=request.request_id,
                task=request.task_hint or request.input_task,
                route_source="task_hint" if request.task_hint else "input_shape",
                bundle_version=self.bundle.bundle_version,
                code="invalid_request",
                message=str(exc),
            )

        try:
            if route.task == "group1":
                result = self._run_group1(request.inputs, device=request.device, return_debug=request.return_debug)
            else:
                result = self._run_group2(request.inputs, device=request.device, return_debug=request.return_debug)
        except FileNotFoundError as exc:
            return create_error_response(
                request_id=request.request_id,
                task=route.task,
                route_source=route.route_source,
                bundle_version=self.bundle.bundle_version,
                code="missing_input",
                message=str(exc),
            )
        except Exception as exc:
            return create_error_response(
                request_id=request.request_id,
                task=route.task,
                route_source=route.route_source,
                bundle_version=self.bundle.bundle_version,
                code="runtime_error",
                message=str(exc),
            )

        return SolveResponse(
            request_id=request.request_id,
            task=route.task,
            status="ok",
            route_source=route.route_source,
            bundle_version=self.bundle.bundle_version,
            result=result,
        )

    def _run_group1(self, inputs: Group1SolveInputs | Group2SolveInputs, *, device: str, return_debug: bool) -> dict[str, Any]:
        if not isinstance(inputs, Group1SolveInputs):
            raise RuntimeError("group1 求解收到错误的输入类型。")
        if not inputs.query_image.exists():
            raise FileNotFoundError(f"未找到 query_image：{inputs.query_image}")
        if not inputs.scene_image.exists():
            raise FileNotFoundError(f"未找到 scene_image：{inputs.scene_image}")

        proposal_model, query_model = self._load_group1_models()
        embedding_provider = self._load_group1_embedder(device)
        started = time.perf_counter()
        query_result = query_model.predict(
            source=str(inputs.query_image),
            imgsz=GROUP1_IMGSZ,
            conf=GROUP1_CONF,
            device=device,
            verbose=False,
        )[0]
        proposal_result = proposal_model.predict(
            source=str(inputs.scene_image),
            imgsz=GROUP1_IMGSZ,
            conf=GROUP1_CONF,
            device=device,
            verbose=False,
        )[0]
        inference_ms = (time.perf_counter() - started) * 1000.0

        query_items = _serialize_yolo_detections(query_result, ordered=True)
        scene_detections = _serialize_yolo_detections(proposal_result, ordered=False)
        matcher_kwargs: dict[str, Any] = {
            "query_image_path": inputs.query_image,
            "scene_image_path": inputs.scene_image,
        }
        if embedding_provider is not None:
            matcher_kwargs["embedding_provider"] = embedding_provider
        mapping = map_group1_instances(query_items, scene_detections, **matcher_kwargs)
        payload: dict[str, Any] = {
            "matcher_status": mapping.status,
            "ordered_clicks": _ordered_clicks_payload(mapping.ordered_targets),
            "missing_orders": list(mapping.missing_orders),
            "ambiguous_orders": list(mapping.ambiguous_orders),
            "inference_ms": round(inference_ms, 4),
        }
        if return_debug:
            payload["query_items"] = query_items
            payload["scene_detections"] = scene_detections
            payload["ordered_targets"] = [_ordered_target_payload(item) for item in mapping.ordered_targets]
        return payload

    def _run_group2(self, inputs: Group1SolveInputs | Group2SolveInputs, *, device: str, return_debug: bool) -> dict[str, Any]:
        if not isinstance(inputs, Group2SolveInputs):
            raise RuntimeError("group2 求解收到错误的输入类型。")
        if not inputs.master_image.exists():
            raise FileNotFoundError(f"未找到 master_image：{inputs.master_image}")
        if not inputs.tile_image.exists():
            raise FileNotFoundError(f"未找到 tile_image：{inputs.tile_image}")

        model, imgsz, torch_device = self._load_group2_model(device)
        master_tensor, tile_tensor, meta = group2_runtime.prepare_inputs(
            master_path=inputs.master_image,
            tile_path=inputs.tile_image,
            imgsz=imgsz,
        )
        started = time.perf_counter()
        with group2_runtime.torch_no_grad():
            response = model(master_tensor.to(torch_device), tile_tensor.to(torch_device))[0]
        inference_ms = (time.perf_counter() - started) * 1000.0
        bbox = group2_runtime.decode_bbox(response, meta)
        center = group2_runtime.bbox_center(bbox)
        payload: dict[str, Any] = {
            "target_bbox": bbox,
            "target_center": center,
            "inference_ms": round(inference_ms, 4),
        }
        if inputs.tile_start_bbox is not None:
            payload["offset_x"] = int(bbox[0]) - int(inputs.tile_start_bbox[0])
            payload["offset_y"] = int(bbox[1]) - int(inputs.tile_start_bbox[1])
        if return_debug and inputs.tile_start_bbox is not None:
            payload["tile_start_bbox"] = list(inputs.tile_start_bbox)
        return payload

    def _load_group1_models(self) -> tuple[Any, Any]:
        if self._proposal_model is not None and self._query_model is not None:
            return self._proposal_model, self._query_model
        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - import path depends on host env
            raise RuntimeError("当前环境缺少 `ultralytics`，无法加载 group1 solver bundle。") from exc
        self._proposal_model = YOLO(str(self.bundle.proposal_model_path))
        self._query_model = YOLO(str(self.bundle.query_model_path))
        return self._proposal_model, self._query_model

    def _load_group1_embedder(self, device: str) -> Any:
        if device not in self._group1_embedder_cache:
            from train.group1.embedder import load_icon_embedder_runtime

            self._group1_embedder_cache[device] = load_icon_embedder_runtime(
                self.bundle.icon_embedder_model_path,
                device_name=device,
            )
        return self._group1_embedder_cache[device]

    def _load_group2_model(self, device: str) -> tuple[Any, int, Any]:
        if device in self._group2_cache:
            return self._group2_cache[device]
        payload = group2_runtime.load_model(self.bundle.group2_model_path, device)
        self._group2_cache[device] = payload
        return payload


def resolve_route(request: SolveRequest) -> RouteDecision:
    if request.task_hint is not None:
        if request.task_hint != request.input_task:
            raise ValueError("task_hint 与输入形态冲突。")
        return RouteDecision(task=request.task_hint, route_source="task_hint")
    return RouteDecision(task=request.input_task, route_source="input_shape")


def _ordered_clicks_payload(targets: list[Group1ClickTarget]) -> list[dict[str, Any]]:
    return [
        {
            "order": item.order,
            "x": int(item.center[0]),
            "y": int(item.center[1]),
            "score": item.score,
        }
        for item in targets
    ]


def _ordered_target_payload(target: Group1ClickTarget) -> dict[str, Any]:
    return {
        "order": target.order,
        "bbox": list(target.bbox),
        "center": list(target.center),
        "score": target.score,
    }


def _serialize_yolo_detections(result: Any, *, ordered: bool) -> list[dict[str, Any]]:
    boxes = result.boxes
    if boxes is None:
        return []
    names = result.names if isinstance(result.names, dict) else {}
    detections: list[dict[str, Any]] = []
    xyxy = boxes.xyxy.tolist()
    cls_ids = boxes.cls.tolist()
    confidences = boxes.conf.tolist()
    for index, (bbox, class_id, score) in enumerate(zip(xyxy, cls_ids, confidences, strict=False), start=1):
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        center_x = int(round((x1 + x2) / 2))
        center_y = int(round((y1 + y2) / 2))
        detection = {
            "order": index,
            "bbox": [x1, y1, x2, y2],
            "center": [center_x, center_y],
            "score": float(score),
        }
        raw_name = names.get(int(class_id))
        if isinstance(raw_name, str) and raw_name.strip():
            detection["class_guess"] = raw_name.strip()
        detections.append(detection)
    if not ordered:
        return detections
    detections.sort(key=lambda item: (int(item["center"][0]), int(item["center"][1])))
    for order, detection in enumerate(detections, start=1):
        detection["order"] = order
    return detections
