"""Root-level PT -> ONNX export helpers for standalone sinanz solver assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .repo_solver_asset_contract import (
    ExportedModelRecord,
    METADATA_FILES,
    MODEL_FILENAMES,
    SolverAssetExportReport,
    SolverAssetManifest,
    SolverOnnxModelAsset,
)

GROUP1_PROPOSAL_MODEL_ID = "click_proposal_detector"
GROUP1_QUERY_MODEL_ID = "click_query_parser"
GROUP1_EMBEDDER_MODEL_ID = "click_icon_embedder"
GROUP2_MODEL_ID = "slider_gap_locator"

GROUP1_DETECT_INPUT_NAMES = ("images",)
GROUP1_DETECT_OUTPUT_NAMES = ("predictions",)
GROUP1_DETECT_POSTPROCESS = "yolo_detect_v1"
GROUP1_EMBEDDER_INPUT_NAMES = ("icon_crop",)
GROUP1_EMBEDDER_OUTPUT_NAMES = ("embedding",)
GROUP1_EMBEDDER_POSTPROCESS = "normalized_embedding_v1"
GROUP2_INPUT_NAMES = ("master_image", "tile_image")
GROUP2_OUTPUT_NAMES = ("response_map",)
GROUP2_POSTPROCESS = "paired_gap_bbox_v1"

GROUP1_PROPOSAL_COMPONENT = "proposal_detector"
GROUP1_QUERY_COMPONENT = "query_parser"
GROUP1_EMBEDDER_COMPONENT = "icon_embedder"
GROUP2_COMPONENT = "locator"

GROUP1_DETECT_DEFAULT_IMGSZ = 640
GROUP2_DEFAULT_OPSET = 17
GROUP1_SIMILARITY_THRESHOLD = 0.9
GROUP1_AMBIGUITY_MARGIN = 0.015
GROUP1_MATCHER_STRATEGY = "global_assignment_match_v1"
GROUP1_PENDING_STATUS = "pending_TASK-SOLVER-MIG-009"


@dataclass(frozen=True)
class ExportSolverAssetsRequest:
    project_dir: Path
    group2_checkpoint: Path
    output_dir: Path
    asset_version: str
    group2_run: str
    group1_run: str = ""
    group1_proposal_checkpoint: Path | None = None
    group1_query_checkpoint: Path | None = None
    group1_embedder_checkpoint: Path | None = None
    exported_at: str | None = None
    source_checkpoint: str | None = None
    group1_proposal_source_checkpoint: str | None = None
    group1_query_source_checkpoint: str | None = None
    group1_embedder_source_checkpoint: str | None = None
    opset: int = GROUP2_DEFAULT_OPSET


@dataclass(frozen=True)
class ExportSolverAssetsResult:
    output_dir: Path
    manifest_path: Path
    export_report_path: Path
    model_paths: dict[str, Path]
    metadata_paths: dict[str, Path]


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


def export_solver_assets(request: ExportSolverAssetsRequest) -> ExportSolverAssetsResult:
    exported_at = request.exported_at or _utc_now()
    _validate_group1_export_request(request)

    model_dir = request.output_dir / "models"
    metadata_dir = request.output_dir / "metadata"
    model_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    model_assets: list[SolverOnnxModelAsset] = []
    exported_models: list[ExportedModelRecord] = []
    model_paths: dict[str, Path] = {}
    metadata_paths: dict[str, Path] = {}

    if _has_group1_assets(request):
        group1_assets = _export_group1_assets(request, model_dir=model_dir, metadata_dir=metadata_dir)
        model_assets.extend(group1_assets["model_assets"])
        exported_models.extend(group1_assets["exported_models"])
        model_paths.update(group1_assets["model_paths"])
        metadata_paths.update(group1_assets["metadata_paths"])
        _write_group1_ready_metadata(metadata_dir)
    else:
        _write_group1_pending_metadata(metadata_dir)

    group2_asset, group2_record, group2_model_path, group2_metadata_path = _export_group2_asset(
        request,
        model_dir=model_dir,
        metadata_dir=metadata_dir,
    )
    model_assets.append(group2_asset)
    exported_models.append(group2_record)
    model_paths[group2_asset.model_id] = group2_model_path
    metadata_paths[group2_asset.model_id] = group2_metadata_path

    manifest_path = request.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            SolverAssetManifest(
                asset_version=request.asset_version,
                exported_at=exported_at,
                model_assets=tuple(model_assets),
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
                exported_models=tuple(exported_models),
            ).to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return ExportSolverAssetsResult(
        output_dir=request.output_dir,
        manifest_path=manifest_path,
        export_report_path=export_report_path,
        model_paths=model_paths,
        metadata_paths=metadata_paths,
    )


def export_group2_solver_assets(request: ExportGroup2SolverAssetsRequest) -> ExportGroup2SolverAssetsResult:
    result = export_solver_assets(
        ExportSolverAssetsRequest(
            project_dir=request.project_dir,
            group2_checkpoint=request.group2_checkpoint,
            output_dir=request.output_dir,
            asset_version=request.asset_version,
            group2_run=request.group2_run,
            group1_run=request.group1_run,
            exported_at=request.exported_at,
            source_checkpoint=request.source_checkpoint,
            opset=request.opset,
        )
    )
    return ExportGroup2SolverAssetsResult(
        output_dir=result.output_dir,
        manifest_path=result.manifest_path,
        model_path=result.model_paths[GROUP2_MODEL_ID],
        model_metadata_path=result.metadata_paths[GROUP2_MODEL_ID],
        export_report_path=result.export_report_path,
    )


def _validate_group1_export_request(request: ExportSolverAssetsRequest) -> None:
    provided = [
        request.group1_proposal_checkpoint is not None,
        request.group1_query_checkpoint is not None,
        request.group1_embedder_checkpoint is not None,
    ]
    if any(provided) and not all(provided):
        raise ValueError(
            "group1 solver 资产导出必须同时提供 proposal/query/embedder 三个 checkpoint。"
        )
    if all(provided) and not request.group1_run.strip():
        raise ValueError("group1 solver 资产导出缺少 group1_run。")


def _has_group1_assets(request: ExportSolverAssetsRequest) -> bool:
    return (
        request.group1_proposal_checkpoint is not None
        and request.group1_query_checkpoint is not None
        and request.group1_embedder_checkpoint is not None
    )


def _export_group1_assets(
    request: ExportSolverAssetsRequest,
    *,
    model_dir: Path,
    metadata_dir: Path,
) -> dict[str, Any]:
    assets: list[SolverOnnxModelAsset] = []
    records: list[ExportedModelRecord] = []
    model_paths: dict[str, Path] = {}
    metadata_paths: dict[str, Path] = {}

    for model_id, component, checkpoint_path, explicit_source in (
        (
            GROUP1_PROPOSAL_MODEL_ID,
            GROUP1_PROPOSAL_COMPONENT,
            request.group1_proposal_checkpoint,
            request.group1_proposal_source_checkpoint,
        ),
        (
            GROUP1_QUERY_MODEL_ID,
            GROUP1_QUERY_COMPONENT,
            request.group1_query_checkpoint,
            request.group1_query_source_checkpoint,
        ),
    ):
        assert checkpoint_path is not None
        model_path = model_dir / MODEL_FILENAMES[model_id]
        exported_onnx = _export_yolo_onnx_from_checkpoint(
            checkpoint_path=checkpoint_path,
            output_path=model_path,
            opset=request.opset,
        )
        model_asset = SolverOnnxModelAsset(
            model_id=model_id,
            task="group1",
            component=component,
            opset=exported_onnx.opset,
            input_names=GROUP1_DETECT_INPUT_NAMES,
            output_names=GROUP1_DETECT_OUTPUT_NAMES,
            image_size=(exported_onnx.image_size, exported_onnx.image_size),
            postprocess=GROUP1_DETECT_POSTPROCESS,
        )
        metadata_path = _write_model_metadata(
            output_dir=request.output_dir,
            metadata_dir=metadata_dir,
            model_asset=model_asset,
        )
        assets.append(model_asset)
        records.append(
            _build_export_record(
                model_asset=model_asset,
                checkpoint_path=checkpoint_path,
                project_dir=request.project_dir,
                explicit_source=explicit_source,
                model_path=model_path,
            )
        )
        model_paths[model_id] = model_path
        metadata_paths[model_id] = metadata_path

    embedder_model_path = model_dir / MODEL_FILENAMES[GROUP1_EMBEDDER_MODEL_ID]
    assert request.group1_embedder_checkpoint is not None
    embedder_onnx = _export_icon_embedder_onnx_from_checkpoint(
        checkpoint_path=request.group1_embedder_checkpoint,
        output_path=embedder_model_path,
        opset=request.opset,
    )
    embedder_asset = SolverOnnxModelAsset(
        model_id=GROUP1_EMBEDDER_MODEL_ID,
        task="group1",
        component=GROUP1_EMBEDDER_COMPONENT,
        opset=embedder_onnx.opset,
        input_names=GROUP1_EMBEDDER_INPUT_NAMES,
        output_names=GROUP1_EMBEDDER_OUTPUT_NAMES,
        image_size=(embedder_onnx.image_size, embedder_onnx.image_size),
        postprocess=GROUP1_EMBEDDER_POSTPROCESS,
    )
    embedder_metadata_path = _write_model_metadata(
        output_dir=request.output_dir,
        metadata_dir=metadata_dir,
        model_asset=embedder_asset,
    )
    assets.append(embedder_asset)
    records.append(
        _build_export_record(
            model_asset=embedder_asset,
            checkpoint_path=request.group1_embedder_checkpoint,
            project_dir=request.project_dir,
            explicit_source=request.group1_embedder_source_checkpoint,
            model_path=embedder_model_path,
        )
    )
    model_paths[GROUP1_EMBEDDER_MODEL_ID] = embedder_model_path
    metadata_paths[GROUP1_EMBEDDER_MODEL_ID] = embedder_metadata_path

    return {
        "model_assets": assets,
        "exported_models": records,
        "model_paths": model_paths,
        "metadata_paths": metadata_paths,
    }


def _export_group2_asset(
    request: ExportSolverAssetsRequest,
    *,
    model_dir: Path,
    metadata_dir: Path,
) -> tuple[SolverOnnxModelAsset, ExportedModelRecord, Path, Path]:
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
    metadata_path = _write_model_metadata(
        output_dir=request.output_dir,
        metadata_dir=metadata_dir,
        model_asset=model_asset,
    )
    record = _build_export_record(
        model_asset=model_asset,
        checkpoint_path=request.group2_checkpoint,
        project_dir=request.project_dir,
        explicit_source=request.source_checkpoint,
        model_path=model_path,
    )
    return model_asset, record, model_path, metadata_path


def _write_model_metadata(*, output_dir: Path, metadata_dir: Path, model_asset: SolverOnnxModelAsset) -> Path:
    metadata_path = output_dir / model_asset.metadata_path()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(model_asset.to_metadata_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata_dir / Path(model_asset.metadata_path()).name


def _build_export_record(
    *,
    model_asset: SolverOnnxModelAsset,
    checkpoint_path: Path,
    project_dir: Path,
    explicit_source: str | None,
    model_path: Path,
) -> ExportedModelRecord:
    return ExportedModelRecord(
        model_id=model_asset.model_id,
        source_checkpoint=_normalize_source_checkpoint(
            checkpoint_path,
            project_dir=project_dir,
            explicit_source=explicit_source,
        ),
        exported_model_path=model_asset.model_path(),
        exported_metadata_path=model_asset.metadata_path(),
        sha256=_sha256_hex(model_path),
    )


def _write_group1_ready_metadata(metadata_dir: Path) -> None:
    (metadata_dir / "click_matcher.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "strategy": GROUP1_MATCHER_STRATEGY,
                "models": {
                    "proposal_detector": GROUP1_PROPOSAL_MODEL_ID,
                    "query_parser": GROUP1_QUERY_MODEL_ID,
                    "icon_embedder": GROUP1_EMBEDDER_MODEL_ID,
                },
                "similarity_threshold": GROUP1_SIMILARITY_THRESHOLD,
                "ambiguity_margin": GROUP1_AMBIGUITY_MARGIN,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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


def _export_yolo_onnx_from_checkpoint(*, checkpoint_path: Path, output_path: Path, opset: int) -> ExportedOnnxInfo:
    if not checkpoint_path.is_file():
        raise ValueError(f"group1 checkpoint does not exist: {checkpoint_path}")
    yolo_cls = _load_group1_yolo_export_backend()
    with tempfile.TemporaryDirectory(prefix="sinan-g1-yolo-export-") as tmpdir:
        model = yolo_cls(str(checkpoint_path))
        exported_path = Path(
            str(
                model.export(
                    format="onnx",
                    imgsz=GROUP1_DETECT_DEFAULT_IMGSZ,
                    opset=opset,
                    nms=True,
                    simplify=False,
                    dynamic=False,
                    project=tmpdir,
                    name="export",
                    exist_ok=True,
                    verbose=False,
                )
            )
        )
        if not exported_path.is_file():
            raise ValueError(f"failed to export group1 ONNX asset from checkpoint: {checkpoint_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exported_path, output_path)
    return ExportedOnnxInfo(
        image_size=GROUP1_DETECT_DEFAULT_IMGSZ,
        opset=_read_exported_model_opset(output_path),
    )


def _export_icon_embedder_onnx_from_checkpoint(
    *,
    checkpoint_path: Path,
    output_path: Path,
    opset: int,
) -> ExportedOnnxInfo:
    torch, embedder_module = _load_group1_embedder_export_backend()
    checkpoint = embedder_module._load_checkpoint(checkpoint_path, torch.device("cpu"))
    embedding_dim = int(checkpoint.get("embedding_dim", embedder_module.DEFAULT_EMBEDDING_DIM))
    image_size = int(checkpoint.get("imgsz", 64))
    model = embedder_module.IconEmbedder(embedding_dim=embedding_dim)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    dummy_input = torch.zeros((1, 3, image_size, image_size), dtype=torch.float32)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=list(GROUP1_EMBEDDER_INPUT_NAMES),
        output_names=list(GROUP1_EMBEDDER_OUTPUT_NAMES),
        dynamic_axes={"icon_crop": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=opset,
    )
    return ExportedOnnxInfo(
        image_size=image_size,
        opset=_read_exported_model_opset(output_path),
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


def _load_group1_yolo_export_backend() -> type[Any]:
    try:
        ultralytics = importlib.import_module("ultralytics")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group1 ONNX export requires `ultralytics`. Install the training extras before exporting solver assets."
        ) from exc

    try:
        importlib.import_module("onnx")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group1 ONNX export requires `onnx`. Install the training extras before exporting solver assets."
        ) from exc
    return ultralytics.YOLO


def _load_group1_embedder_export_backend() -> tuple[Any, Any]:
    try:
        torch = importlib.import_module("torch")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group1 icon embedder ONNX export requires `torch`. Install the training extras before exporting."
        ) from exc

    try:
        importlib.import_module("onnx")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group1 icon embedder ONNX export requires `onnx`. Install the training extras before exporting."
        ) from exc

    try:
        embedder_module = importlib.import_module("train.group1.embedder")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group1 icon embedder ONNX export requires `train.group1.embedder` dependencies."
        ) from exc
    return torch, embedder_module


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
        runner = importlib.import_module("train.group2.runner")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ValueError(
            "group2 ONNX export requires the training runtime dependencies to import `train.group2.runner`."
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
        raise ValueError("solver ONNX export requires `onnx` to inspect the exported model opset.") from exc
    model = onnx.load(path)
    if not model.opset_import:
        raise ValueError(f"exported ONNX model has no opset_import entries: {path}")
    return int(model.opset_import[0].version)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
