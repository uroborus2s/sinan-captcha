"""Group2 service for standalone slider-gap solving."""

from __future__ import annotations

from pathlib import Path

import sinanz_group2_runtime as group2_runtime
from sinanz_errors import SolverAssetError
from sinanz_image_io import resolved_image_path
from sinanz_resources import models_root
from sinanz_types import BBox, ImageInput, SliderGapCenterResult, SliderGapDebugInfo

GROUP2_MODEL_FILENAME = "slider_gap_locator.onnx"


def solve_slider_gap(
    *,
    background_image: ImageInput,
    puzzle_piece_image: ImageInput,
    puzzle_piece_start_bbox: BBox | None,
    device: str,
    asset_root: Path | None,
    return_debug: bool,
) -> SliderGapCenterResult:
    model_path = _resolve_group2_model(asset_root)
    with (
        resolved_image_path(background_image, field="background_image") as background_path,
        resolved_image_path(puzzle_piece_image, field="puzzle_piece_image") as puzzle_piece_path,
    ):
        runtime_result = group2_runtime.match_slider_gap(
            model_path=model_path,
            background_image_path=background_path,
            puzzle_piece_image_path=puzzle_piece_path,
            device=device,
        )
    return _build_result(
        bbox=runtime_result.target_bbox,
        execution_provider=runtime_result.execution_provider,
        runtime_target=runtime_result.runtime_target,
        puzzle_piece_start_bbox=puzzle_piece_start_bbox,
        device=device,
        return_debug=return_debug,
    )


def _build_result(
    *,
    bbox: tuple[int, int, int, int],
    execution_provider: str | None,
    runtime_target: str,
    puzzle_piece_start_bbox: BBox | None,
    device: str,
    return_debug: bool,
) -> SliderGapCenterResult:
    center = (
        int((int(bbox[0]) + int(bbox[2])) / 2),
        int((int(bbox[1]) + int(bbox[3])) / 2),
    )
    offset = None
    if puzzle_piece_start_bbox is not None:
        offset = (
            int(bbox[0]) - int(puzzle_piece_start_bbox[0]),
            int(bbox[1]) - int(puzzle_piece_start_bbox[1]),
        )
    debug = None
    if return_debug:
        notes = [f"device={device}", f"runtime={runtime_target}", f"model={GROUP2_MODEL_FILENAME}"]
        if execution_provider:
            notes.append(f"provider={execution_provider}")
        debug = SliderGapDebugInfo(notes=notes)
    return SliderGapCenterResult(
        target_center=(int(center[0]), int(center[1])),
        target_bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
        puzzle_piece_offset=offset,
        debug=debug,
    )


def _resolve_group2_model(asset_root: Path | None) -> Path:
    if asset_root is not None:
        model_path = asset_root / GROUP2_MODEL_FILENAME
        if not model_path.is_file():
            raise SolverAssetError(f"未找到滑块模型文件：{model_path}")
        return model_path

    embedded_model = models_root() / GROUP2_MODEL_FILENAME
    if not embedded_model.is_file():
        raise SolverAssetError(
            f"未找到内嵌滑块模型文件：{GROUP2_MODEL_FILENAME}。"
            "请先完成 TASK-SOLVER-MIG-011 或显式提供 `asset_root`。"
        )
    return embedded_model
