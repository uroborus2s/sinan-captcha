"""Internal bridge metadata for the staged Rust native extension."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

from .errors import SolverRuntimeError

NATIVE_EXTENSION_MODULE = "sinanz_ext"
BRIDGE_MODULE = "sinanz.native_bridge"
RUNTIME_TARGET = "rust-onnxruntime"
CARGO_WORKSPACE_MANIFEST = "Cargo.toml"
CRATE_MANIFEST = "native/sinanz_ext/Cargo.toml"
FEATURE_FLAGS = ("python-extension", "onnx-runtime")
STAGE = "group2-onnx-bridge"


@dataclass(frozen=True)
class NativeRuntimeStatus:
    module_name: str
    runtime_target: str
    bridge_module: str
    stage: str
    feature_flags: tuple[str, ...]
    cargo_workspace_manifest: str
    crate_manifest: str


@dataclass(frozen=True)
class NativeSliderGapMatch:
    target_bbox: tuple[int, int, int, int]
    execution_provider: str | None = None


def native_runtime_status() -> NativeRuntimeStatus:
    return NativeRuntimeStatus(
        module_name=NATIVE_EXTENSION_MODULE,
        runtime_target=RUNTIME_TARGET,
        bridge_module=BRIDGE_MODULE,
        stage=STAGE,
        feature_flags=FEATURE_FLAGS,
        cargo_workspace_manifest=CARGO_WORKSPACE_MANIFEST,
        crate_manifest=CRATE_MANIFEST,
    )


def load_native_module() -> ModuleType:
    try:
        return importlib.import_module(NATIVE_EXTENSION_MODULE)
    except ModuleNotFoundError as exc:
        raise SolverRuntimeError(
            f"Native extension `{NATIVE_EXTENSION_MODULE}` is not available yet. "
            "Complete TASK-SOLVER-MIG-008/009/011 to wire pyo3, ONNX Runtime, and wheel packaging."
        ) from exc


def match_slider_gap(
    *,
    model_path: Path,
    background_image_path: Path,
    puzzle_piece_image_path: Path,
    device: str,
) -> NativeSliderGapMatch:
    module = load_native_module()
    handler = getattr(module, "match_slider_gap", None)
    if handler is None:
        raise SolverRuntimeError(
            f"Native extension `{NATIVE_EXTENSION_MODULE}` does not expose `match_slider_gap` yet."
        )
    response = handler(
        model_path=str(model_path),
        background_image_path=str(background_image_path),
        puzzle_piece_image_path=str(puzzle_piece_image_path),
        device=device,
    )
    return _normalize_slider_gap_response(response)


def _normalize_slider_gap_response(response: Any) -> NativeSliderGapMatch:
    if not isinstance(response, dict):
        raise SolverRuntimeError("Native `match_slider_gap` must return a dict payload.")
    target_bbox = response.get("target_bbox")
    if not isinstance(target_bbox, list | tuple) or len(target_bbox) != 4:
        raise SolverRuntimeError("Native `match_slider_gap` response is missing `target_bbox`.")
    try:
        normalized_bbox = tuple(int(value) for value in target_bbox)
    except (TypeError, ValueError) as exc:
        raise SolverRuntimeError("Native `match_slider_gap` returned a non-integer `target_bbox`.") from exc
    execution_provider = response.get("execution_provider")
    if execution_provider is not None and not isinstance(execution_provider, str):
        raise SolverRuntimeError("Native `match_slider_gap` returned an invalid `execution_provider`.")
    return NativeSliderGapMatch(
        target_bbox=normalized_bbox,
        execution_provider=execution_provider,
    )
