"""Stable PT->ONNX export contracts for the standalone sinanz solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SOLVER_ASSET_FORMAT = "sinan.solver.assets.v1"
RUNTIME_TARGET = "python-onnxruntime"
PYTHON_PACKAGE_NAME = "sinanz"
PREFERRED_EXECUTION_PROVIDERS = ("CUDAExecutionProvider", "CPUExecutionProvider")
PIXEL_FORMAT = "RGB"
TENSOR_LAYOUT = "NCHW"
INPUT_DTYPE = "float32"
NORMALIZATION = "zero_to_one"
METADATA_FILES = {
    "click_matcher": "metadata/click_matcher.json",
    "export_report": "metadata/export_report.json",
}
MODEL_FILENAMES = {
    "click_proposal_detector": "click_proposal_detector.onnx",
    "click_query_parser": "click_query_parser.onnx",
    "click_icon_embedder": "click_icon_embedder.onnx",
    "slider_gap_locator": "slider_gap_locator.onnx",
}
MODEL_METADATA_FILENAMES = {
    model_id: f"metadata/{model_id}.json" for model_id in MODEL_FILENAMES
}


@dataclass(frozen=True)
class SolverOnnxModelAsset:
    model_id: str
    task: str
    component: str
    opset: int
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]
    image_size: tuple[int, int]
    postprocess: str
    format: str = "onnx"
    pixel_format: str = PIXEL_FORMAT
    tensor_layout: str = TENSOR_LAYOUT
    input_dtype: str = INPUT_DTYPE
    normalization: str = NORMALIZATION
    preferred_execution_providers: tuple[str, ...] = PREFERRED_EXECUTION_PROVIDERS

    def model_path(self) -> str:
        return f"models/{_model_filename(self.model_id)}"

    def metadata_path(self) -> str:
        return _model_metadata_path(self.model_id)

    def to_manifest_entry(self) -> dict[str, Any]:
        width, height = self.image_size
        return {
            "task": self.task,
            "component": self.component,
            "format": self.format,
            "opset": self.opset,
            "path": self.model_path(),
            "metadata": self.metadata_path(),
            "input": {
                "names": list(self.input_names),
                "image_size": [width, height],
                "layout": self.tensor_layout,
                "pixel_format": self.pixel_format,
                "dtype": self.input_dtype,
                "normalization": self.normalization,
            },
            "output": {
                "names": list(self.output_names),
                "postprocess": self.postprocess,
            },
            "preferred_execution_providers": list(self.preferred_execution_providers),
        }

    def to_metadata_payload(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "task": self.task,
            "component": self.component,
            "runtime_target": RUNTIME_TARGET,
            "format": self.format,
            "opset": self.opset,
            "input": self.to_manifest_entry()["input"],
            "output": self.to_manifest_entry()["output"],
            "preferred_execution_providers": list(self.preferred_execution_providers),
        }


@dataclass(frozen=True)
class SolverAssetManifest:
    asset_version: str
    exported_at: str
    model_assets: tuple[SolverOnnxModelAsset, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_format": SOLVER_ASSET_FORMAT,
            "asset_version": self.asset_version,
            "exported_at": self.exported_at,
            "runtime": {
                "target": RUNTIME_TARGET,
                "python_package": PYTHON_PACKAGE_NAME,
                "preferred_execution_providers": list(PREFERRED_EXECUTION_PROVIDERS),
            },
            "models": {asset.model_id: asset.to_manifest_entry() for asset in self.model_assets},
            "metadata_files": dict(METADATA_FILES),
        }


@dataclass(frozen=True)
class ExportedModelRecord:
    model_id: str
    source_checkpoint: str
    exported_model_path: str
    exported_metadata_path: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "source_checkpoint": self.source_checkpoint,
            "exported_model_path": self.exported_model_path,
            "exported_metadata_path": self.exported_metadata_path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class SolverAssetExportReport:
    asset_version: str
    group1_run: str
    group2_run: str
    exported_at: str
    exported_models: tuple[ExportedModelRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_format": SOLVER_ASSET_FORMAT,
            "asset_version": self.asset_version,
            "group1_run": self.group1_run,
            "group2_run": self.group2_run,
            "exported_at": self.exported_at,
            "runtime_target": RUNTIME_TARGET,
            "exported_models": [record.to_dict() for record in self.exported_models],
        }


def _model_filename(model_id: str) -> str:
    try:
        return MODEL_FILENAMES[model_id]
    except KeyError as exc:
        raise ValueError(f"unsupported solver model id: {model_id}") from exc


def _model_metadata_path(model_id: str) -> str:
    try:
        return MODEL_METADATA_FILENAMES[model_id]
    except KeyError as exc:
        raise ValueError(f"unsupported solver model id: {model_id}") from exc
