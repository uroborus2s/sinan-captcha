"""Group1 service for standalone click-target solving."""

from __future__ import annotations

from pathlib import Path

from sinanz_errors import SolverAssetError, SolverInputError
from sinanz_image_io import require_pathlike_image
import sinanz_group1_runtime as group1_runtime
from sinanz_resources import models_root
from sinanz_types import (
    ClickCaptchaDebugInfo,
    ImageInput,
    OrderedClickTarget,
    OrderedClickTargetsResult,
)

GROUP1_PROPOSAL_MODEL_FILENAME = "click_proposal_detector.onnx"
GROUP1_QUERY_MODEL_FILENAME = "click_query_parser.onnx"
GROUP1_EMBEDDER_MODEL_FILENAME = "click_icon_embedder.onnx"


def solve_click_targets(
    *,
    query_icons_image: ImageInput,
    background_image: ImageInput,
    device: str,
    asset_root: Path | None,
    return_debug: bool,
) -> OrderedClickTargetsResult:
    proposal_model_path, query_model_path, embedder_model_path = _resolve_group1_models(asset_root)
    query_path = require_pathlike_image(query_icons_image, field="query_icons_image")
    background_path = require_pathlike_image(background_image, field="background_image")
    if not query_path.exists():
        raise SolverInputError(f"未找到 query 图文件：{query_path}")
    if not background_path.exists():
        raise SolverInputError(f"未找到背景图文件：{background_path}")

    runtime_result = group1_runtime.match_click_targets(
        proposal_model_path=proposal_model_path,
        query_model_path=query_model_path,
        embedder_model_path=embedder_model_path,
        query_image_path=query_path,
        background_image_path=background_path,
        device=device,
    )
    ordered_targets = [
        OrderedClickTarget(
            query_order=query_order,
            center=(int(target.center[0]), int(target.center[1])),
            class_id=_resolve_class_id(target, query_order=query_order),
            class_name=_resolve_class_name(target, query_order=query_order),
            score=float(target.score),
        )
        for target in runtime_result.ordered_targets
        for query_order in [int(target.query_order)]
    ]
    debug = None
    if return_debug:
        notes = [
            f"device={device}",
            f"runtime={runtime_result.runtime_target}",
            f"model={GROUP1_PROPOSAL_MODEL_FILENAME}",
            f"query-model={GROUP1_QUERY_MODEL_FILENAME}",
            f"embedder={GROUP1_EMBEDDER_MODEL_FILENAME}",
        ]
        if runtime_result.execution_provider:
            notes.append(f"provider={runtime_result.execution_provider}")
        debug = ClickCaptchaDebugInfo(notes=notes)
    return OrderedClickTargetsResult(
        ordered_target_centers=[target.center for target in ordered_targets],
        ordered_targets=ordered_targets,
        missing_query_orders=[int(order) for order in runtime_result.missing_orders],
        ambiguous_query_orders=[int(order) for order in runtime_result.ambiguous_orders],
        debug=debug,
    )


def _resolve_group1_models(asset_root: Path | None) -> tuple[Path, Path, Path]:
    if asset_root is not None:
        return (
            _require_model(asset_root / GROUP1_PROPOSAL_MODEL_FILENAME, label="点选 proposal"),
            _require_model(asset_root / GROUP1_QUERY_MODEL_FILENAME, label="点选 query"),
            _require_model(asset_root / GROUP1_EMBEDDER_MODEL_FILENAME, label="点选 embedder"),
        )

    embedded_root = models_root()
    return (
        _require_model(
            embedded_root / GROUP1_PROPOSAL_MODEL_FILENAME,
            label="内嵌点选 proposal",
        ),
        _require_model(
            embedded_root / GROUP1_QUERY_MODEL_FILENAME,
            label="内嵌点选 query",
        ),
        _require_model(
            embedded_root / GROUP1_EMBEDDER_MODEL_FILENAME,
            label="内嵌点选 embedder",
        ),
    )


def _require_model(path: Path, *, label: str) -> Path:
    if not path.is_file():
        raise SolverAssetError(
            f"未找到{label}模型文件：{path}。"
            "请先执行 release export-solver-assets + stage-solver-assets，"
            "或显式提供包含新规范 group1 ONNX 资产的 `asset_root`。"
        )
    return path


def _resolve_class_id(target: object, *, query_order: int) -> int:
    raw_class_id = getattr(target, "class_id", None)
    if isinstance(raw_class_id, (int, float)):
        return int(raw_class_id)
    return query_order - 1


def _resolve_class_name(target: object, *, query_order: int) -> str:
    raw_class_name = getattr(target, "class_name", None)
    if isinstance(raw_class_name, str) and raw_class_name.strip():
        return raw_class_name
    return f"query_item_{query_order:02d}"
