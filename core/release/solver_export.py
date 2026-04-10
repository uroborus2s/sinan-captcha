"""PT -> ONNX export helpers for standalone sinanz solver assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from core.release.solver_asset_contract import (
    METADATA_FILES,
    MODEL_FILENAMES,
    SolverAssetExportReport,
    SolverAssetManifest,
    SolverOnnxModelAsset,
    ExportedModelRecord,
)

GROUP2_MODEL_ID = "slider_gap_locator"
GROUP2_COMPONENT = "locator"
GROUP2_INPUT_NAMES = ("master_image", "tile_image")
GROUP2_OUTPUT_NAMES = ("response_map",)
GROUP2_POSTPROCESS = "paired_gap_bbox_v1"
GROUP2_DEFAULT_OPSET = 17
GROUP1_PENDING_STATUS = "pending_TASK-SOLVER-MIG-009"


@dataclass(frozen=True)
class ExportGroup2SolverAssetsRequest:
    project_dir: Path
    group2_checkpoint: Path
    output_dir: Path
    asset_version: str
    group2_run: str
    group1_run: str = ""
    exported_at: str | None = None
    source_checkpoint: str | None = None
    opset: int = GROUP2_DEFAULT_OPSET


@dataclass(frozen=True)
class ExportGroup2SolverAssetsResult:
    output_dir: Path
    manifest_path: Path
    model_path: Path
    model_metadata_path: Path
    export_report_path: Path


@dataclass(frozen=True)
class ExportedOnnxInfo:
    image_size: int
    opset: int


def export_group2_solver_assets(request: ExportGroup2SolverAssetsRequest) -> ExportGroup2SolverAssetsResult:
    exported_at = request.exported_at or _utc_now()
    model_dir = request.output_dir / "models"
    metadata_dir = request.output_dir / "metadata"
    model_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / MODEL_FILENAMES[GROUP2_MODEL_ID]
    exported_onnx = _export_group2_onnx_from_checkpoint(
        checkpoint_path=request.group2_checkpoint,
        output_path=model_path,
        opset=request.opset,
    )
    model_asset = SolverOnnxModelAsset(
        model_id=GROUP2_MODEL_ID,
        task="group2",
        component=GROUP2_COMPONENT,
        opset=exported_onnx.opset,
        input_names=GROUP2_INPUT_NAMES,
        output_names=GROUP2_OUTPUT_NAMES,
        image_size=(exported_onnx.image_size, exported_onnx.image_size),
        postprocess=GROUP2_POSTPROCESS,
    )
    model_metadata_path = request.output_dir / model_asset.metadata_path()
    model_metadata_path.write_text(
        json.dumps(model_asset.to_metadata_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_group1_pending_metadata(metadata_dir)

    manifest_path = request.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            SolverAssetManifest(
                asset_version=request.asset_version,
                exported_at=exported_at,
                model_assets=(model_asset,),
            ).to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    export_report_path = request.output_dir / METADATA_FILES["export_report"]
    export_report_path.write_text(
        json.dumps(
            SolverAssetExportReport(
                asset_version=request.asset_version,
                group1_run=request.group1_run,
                group2_run=request.group2_run,
                exported_at=exported_at,
                exported_models=(
                    ExportedModelRecord(
                        model_id=GROUP2_MODEL_ID,
                        source_checkpoint=_normalize_source_checkpoint(
                            request.group2_checkpoint,
                            project_dir=request.project_dir,
                            explicit_source=request.source_checkpoint,
                        ),
                        exported_model_path=str(model_asset.model_path()),
                        exported_metadata_path=str(model_asset.metadata_path()),
                        sha256=_sha256_hex(model_path),
                    ),
                ),
            ).to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return ExportGroup2SolverAssetsResult(
        output_dir=request.output_dir,
        manifest_path=manifest_path,
        model_path=model_path,
        model_metadata_path=model_metadata_path,
        export_report_path=export_report_path,
    )


def _write_group1_pending_metadata(metadata_dir: Path) -> None:
    placeholder_payload = {
        "status": GROUP1_PENDING_STATUS,
        "message": "group1 ONNX assets will be exported in TASK-SOLVER-MIG-009.",
    }
    (metadata_dir / "click_matcher.json").write_text(
        json.dumps(placeholder_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (metadata_dir / "class_names.json").write_text(
        json.dumps(
            {
                "status": GROUP1_PENDING_STATUS,
                "group1_class_names": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _export_group2_onnx_from_checkpoint(*, checkpoint_path: Path, output_path: Path, opset: int) -> ExportedOnnxInfo:
    torch, model_cls = _load_group2_export_backend()
    checkpoint = _load_torch_checkpoint(torch, checkpoint_path)
    imgsz = int(checkpoint.get("imgsz", 192))
    model = model_cls()
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    tile_extent = max(16, imgsz // 4)
    master = torch.zeros((1, 1, imgsz, imgsz), dtype=torch.float32)
    tile = torch.zeros((1, 1, tile_extent, tile_extent), dtype=torch.float32)
    dynamic_shapes = {
        "master": {0: 1, 1: 1, 2: imgsz, 3: imgsz},
        "tile": {
            0: 1,
            1: 1,
            2: torch.export.Dim("tile_h", min=16, max=max(16, imgsz)),
            3: torch.export.Dim("tile_w", min=16, max=max(16, imgsz)),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        (master, tile),
        output_path,
        dynamo=True,
        input_names=list(GROUP2_INPUT_NAMES),
        output_names=list(GROUP2_OUTPUT_NAMES),
        dynamic_shapes=dynamic_shapes,
        opset_version=opset,
    )
    return ExportedOnnxInfo(
        image_size=imgsz,
        opset=_read_exported_model_opset(output_path),
    )


def _load_group2_export_backend() -> tuple[Any, type[Any]]:
    try:
        torch = importlib.import_module("torch")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group2 ONNX export requires `torch`. Install the training extras before exporting solver assets."
        ) from exc

    try:
        importlib.import_module("onnx")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group2 ONNX export requires `onnx`. Install the training extras before exporting solver assets."
        ) from exc

    try:
        runner = importlib.import_module("core.train.group2.runner")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group2 ONNX export requires the training runtime dependencies to import `core.train.group2.runner`."
        ) from exc

    return torch, runner.PairedGapLocator


def _load_torch_checkpoint(torch: Any, checkpoint_path: Path) -> dict[str, Any]:
    if not checkpoint_path.is_file():
        raise ValueError(f"group2 checkpoint does not exist: {checkpoint_path}")
    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except TypeError:  # pragma: no cover - compatibility with older torch
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise ValueError(f"group2 checkpoint format is invalid: {checkpoint_path}")
    return checkpoint


def _normalize_source_checkpoint(
    checkpoint_path: Path,
    *,
    project_dir: Path,
    explicit_source: str | None,
) -> str:
    if explicit_source:
        return explicit_source
    try:
        return str(checkpoint_path.relative_to(project_dir))
    except ValueError:
        return checkpoint_path.name


def _sha256_hex(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_exported_model_opset(path: Path) -> int:
    try:
        onnx = importlib.import_module("onnx")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError("group2 ONNX export requires `onnx` to inspect the exported model opset.") from exc
    model = onnx.load(path)
    if not model.opset_import:
        raise ValueError(f"exported ONNX model has no opset_import entries: {path}")
    return int(model.opset_import[0].version)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
