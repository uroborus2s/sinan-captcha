"""Group2 service for standalone slider-gap solving."""

from __future__ import annotations

from importlib.resources import as_file
from pathlib import Path
from typing import Any

from ..errors import SolverAssetError, SolverInputError
from ..image_io import require_pathlike_image
from .. import native_bridge
from ..resources import models_root
from ..types import BBox, ImageInput, SliderGapCenterResult, SliderGapDebugInfo

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
    model_ref = _resolve_group2_model(asset_root)
    background_path = require_pathlike_image(background_image, field="background_image")
    puzzle_piece_path = require_pathlike_image(puzzle_piece_image, field="puzzle_piece_image")
    if not background_path.exists():
        raise SolverInputError(f"未找到背景图文件：{background_path}")
    if not puzzle_piece_path.exists():
        raise SolverInputError(f"未找到拼图块文件：{puzzle_piece_path}")

    if isinstance(model_ref, Path):
        model_path = model_ref
    else:
        with as_file(model_ref) as model_path:
            native_result = native_bridge.match_slider_gap(
                model_path=model_path,
                background_image_path=background_path,
                puzzle_piece_image_path=puzzle_piece_path,
                device=device,
            )
            return _build_result(
                bbox=native_result.target_bbox,
                execution_provider=native_result.execution_provider,
                puzzle_piece_start_bbox=puzzle_piece_start_bbox,
                device=device,
                return_debug=return_debug,
            )
    native_result = native_bridge.match_slider_gap(
        model_path=model_path,
        background_image_path=background_path,
        puzzle_piece_image_path=puzzle_piece_path,
        device=device,
    )
    return _build_result(
        bbox=native_result.target_bbox,
        execution_provider=native_result.execution_provider,
        puzzle_piece_start_bbox=puzzle_piece_start_bbox,
        device=device,
        return_debug=return_debug,
    )


def _build_result(
    *,
    bbox: tuple[int, int, int, int],
    execution_provider: str | None,
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
        notes = [f"device={device}", f"runtime=rust-onnxruntime", f"model={GROUP2_MODEL_FILENAME}"]
        if execution_provider:
            notes.append(f"provider={execution_provider}")
        debug = SliderGapDebugInfo(notes=notes)
    return SliderGapCenterResult(
        target_center=(int(center[0]), int(center[1])),
        target_bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
        puzzle_piece_offset=offset,
        debug=debug,
    )


def _resolve_group2_model(asset_root: Path | None) -> Any:
    if asset_root is not None:
        model_path = asset_root / GROUP2_MODEL_FILENAME
        if not model_path.is_file():
            raise SolverAssetError(f"未找到滑块模型文件：{model_path}")
        return model_path

    embedded_model = models_root().joinpath(GROUP2_MODEL_FILENAME)
    if not embedded_model.is_file():
        raise SolverAssetError(
            f"未找到内嵌滑块模型文件：{GROUP2_MODEL_FILENAME}。"
            "请先完成 TASK-SOLVER-MIG-011 或显式提供 `asset_root`。"
        )
    return embedded_model
