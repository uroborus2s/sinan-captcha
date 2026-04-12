"""Prediction-to-X-AnyLabeling export helpers for reviewed exam workspaces."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from auto_train.json_extract import extract_json_object
from common.images import get_image_size
from common.jsonl import read_jsonl, write_jsonl
from inference.query_splitter import split_group1_query_image
from materials.query_audit import (
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_URL,
    _extract_ollama_message_content,
    _post_json,
)
from train.base import _ensure_training_dependencies
from train.group1.service import (
    Group1PredictionJob,
    build_group1_prediction_job,
    run_group1_prediction_job,
)
from train.group2.service import (
    Group2PredictionJob,
    build_group2_prediction_job,
    run_group2_prediction_job,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class Group1PrelabelRequest:
    exam_root: Path
    dataset_config: Path
    proposal_model_path: Path
    project_dir: Path
    embedder_model_path: Path | None = None
    run_name: str = "prelabel"
    conf: float = 0.25
    imgsz: int = 640
    device: str = "0"
    limit: int | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class Group2PrelabelRequest:
    exam_root: Path
    dataset_config: Path
    model_path: Path
    project_dir: Path
    run_name: str = "prelabel"
    imgsz: int = 192
    device: str = "0"
    limit: int | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class Group1QueryDirectoryPrelabelRequest:
    input_dir: Path
    project_dir: Path
    run_name: str = "prelabel-query"
    limit: int | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class Group1VlmPrelabelRequest:
    pair_root: Path
    model: str
    project_dir: Path
    ollama_url: str = DEFAULT_OLLAMA_URL
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS
    limit: int | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class PrelabelResult:
    task: str
    exam_root: Path
    review_dir: Path
    source_labels_path: Path
    prediction_labels_path: Path
    sample_count: int
    annotation_count: int
    prediction_command: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["exam_root"] = str(self.exam_root)
        payload["review_dir"] = str(self.review_dir)
        payload["source_labels_path"] = str(self.source_labels_path)
        payload["prediction_labels_path"] = str(self.prediction_labels_path)
        return payload


@dataclass(frozen=True)
class Group1PrelabelPlan:
    prediction_job: Group1PredictionJob
    source_labels_path: Path


@dataclass(frozen=True)
class Group2PrelabelPlan:
    prediction_job: Group2PredictionJob
    source_labels_path: Path


@dataclass(frozen=True)
class Group1QueryDirectoryPrelabelPlan:
    input_dir: Path
    project_dir: Path
    output_dir: Path
    run_name: str
    limit: int | None
    overwrite: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "input_dir": str(self.input_dir),
            "query_splitter_strategy": "rule_based_v1",
            "project_dir": str(self.project_dir),
            "output_dir": str(self.output_dir),
            "run_name": self.run_name,
            "limit": self.limit,
            "overwrite": self.overwrite,
        }


@dataclass(frozen=True)
class Group1VlmPrelabelPlan:
    pair_root: Path
    project_dir: Path
    review_dir: Path
    process_dir: Path
    process_index_path: Path
    source_labels_path: Path
    prediction_labels_path: Path
    trace_path: Path
    model: str
    ollama_url: str
    timeout_seconds: int
    limit: int | None
    overwrite: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "pair_root": str(self.pair_root),
            "project_dir": str(self.project_dir),
            "review_dir": str(self.review_dir),
            "process_dir": str(self.process_dir),
            "process_index_path": str(self.process_index_path),
            "source_labels_path": str(self.source_labels_path),
            "prediction_labels_path": str(self.prediction_labels_path),
            "trace_path": str(self.trace_path),
            "model": self.model,
            "ollama_url": self.ollama_url,
            "timeout_seconds": self.timeout_seconds,
            "limit": self.limit,
            "overwrite": self.overwrite,
        }


@dataclass(frozen=True)
class Group1QueryDirectoryPrelabelResult:
    input_dir: Path
    output_dir: Path
    prediction_labels_path: Path
    sample_count: int
    annotation_count: int
    splitter_strategy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "prediction_labels_path": str(self.prediction_labels_path),
            "sample_count": self.sample_count,
            "annotation_count": self.annotation_count,
            "query_splitter_strategy": self.splitter_strategy,
        }


def build_group1_prelabel_plan(request: Group1PrelabelRequest) -> Group1PrelabelPlan:
    source_labels_path = _generated_dir(request.exam_root, "group1") / "source.jsonl"
    job = build_group1_prediction_job(
        dataset_config=request.dataset_config,
        proposal_model_path=request.proposal_model_path,
        embedder_model_path=request.embedder_model_path,
        source=source_labels_path,
        project_dir=request.project_dir,
        run_name=request.run_name,
        conf=request.conf,
        imgsz=request.imgsz,
        device=request.device,
    )
    return Group1PrelabelPlan(prediction_job=job, source_labels_path=source_labels_path)


def build_group2_prelabel_plan(request: Group2PrelabelRequest) -> Group2PrelabelPlan:
    source_labels_path = _generated_dir(request.exam_root, "group2") / "source.jsonl"
    job = build_group2_prediction_job(
        dataset_config=request.dataset_config,
        model_path=request.model_path,
        source=source_labels_path,
        project_dir=request.project_dir,
        run_name=request.run_name,
        imgsz=request.imgsz,
        device=request.device,
    )
    return Group2PrelabelPlan(prediction_job=job, source_labels_path=source_labels_path)


def build_group1_query_directory_prelabel_plan(
    request: Group1QueryDirectoryPrelabelRequest,
) -> Group1QueryDirectoryPrelabelPlan:
    output_dir = request.project_dir / request.run_name
    return Group1QueryDirectoryPrelabelPlan(
        input_dir=request.input_dir,
        project_dir=request.project_dir,
        output_dir=output_dir,
        run_name=request.run_name,
        limit=request.limit,
        overwrite=request.overwrite,
    )


def build_group1_vlm_prelabel_plan(
    request: Group1VlmPrelabelRequest,
) -> Group1VlmPrelabelPlan:
    return Group1VlmPrelabelPlan(
        pair_root=request.pair_root,
        project_dir=request.project_dir,
        review_dir=request.project_dir / "reviewed",
        process_dir=request.project_dir / "process",
        process_index_path=request.project_dir / "process" / "index.json",
        source_labels_path=request.project_dir / "source.jsonl",
        prediction_labels_path=request.project_dir / "labels.jsonl",
        trace_path=request.project_dir / "trace.jsonl",
        model=request.model,
        ollama_url=request.ollama_url,
        timeout_seconds=request.timeout_seconds,
        limit=request.limit,
        overwrite=request.overwrite,
    )


def run_group1_prelabel(request: Group1PrelabelRequest) -> PrelabelResult:
    samples = _select_manifest_samples(exam_root=request.exam_root, expected_task="group1", limit=request.limit)
    review_query_dir = request.exam_root / "reviewed" / "query"
    review_scene_dir = request.exam_root / "reviewed" / "scene"
    _ensure_annotation_targets(
        sample_ids=[str(sample["sample_id"]) for sample in samples],
        annotation_dirs=[review_query_dir, review_scene_dir],
        overwrite=request.overwrite,
    )

    source_rows: list[dict[str, object]] = []
    review_query_images: dict[str, Path] = {}
    review_scene_images: dict[str, Path] = {}
    for sample in samples:
        sample_id = str(sample["sample_id"])
        query_source = _resolve_sample_asset(request.exam_root, sample, "query_image")
        scene_source = _resolve_sample_asset(request.exam_root, sample, "scene_image")
        review_query_image = _copy_review_asset(query_source, review_query_dir)
        review_scene_image = _copy_review_asset(scene_source, review_scene_dir)
        review_query_images[sample_id] = review_query_image
        review_scene_images[sample_id] = review_scene_image
        source_rows.append(
            {
                "sample_id": sample_id,
                "query_image": str(query_source),
                "scene_image": str(scene_source),
                "query_items": [],
                "scene_targets": [],
                "distractors": [],
                "label_source": "seed",
                "source_batch": request.exam_root.name,
            }
        )

    plan = build_group1_prelabel_plan(request)
    write_jsonl(plan.source_labels_path, source_rows)
    prediction_result = run_group1_prediction_job(plan.prediction_job)
    predictions = read_jsonl(prediction_result.labels_path)
    annotation_count = 0
    for row in predictions:
        sample_id = str(row["sample_id"])
        query_image = review_query_images[sample_id]
        scene_image = review_scene_images[sample_id]
        _write_labelme_annotation(
            review_query_dir / f"{sample_id}.json",
            image_path=query_image.name,
            image_width=get_image_size(query_image)[0],
            image_height=get_image_size(query_image)[1],
            shapes=[
                _build_rectangle_shape(
                    label="query_item",
                    bbox=_coerce_bbox(target["bbox"]),
                    flags=_group1_shape_flags(target),
                )
                for target in _group1_query_items(row)
            ],
        )
        _write_labelme_annotation(
            review_scene_dir / f"{sample_id}.json",
            image_path=scene_image.name,
            image_width=get_image_size(scene_image)[0],
            image_height=get_image_size(scene_image)[1],
            shapes=[
                _build_rectangle_shape(
                    label=f"{int(target['order']):02d}",
                    bbox=_coerce_bbox(target["bbox"]),
                    flags=_group1_shape_flags(target),
                )
                for target in row.get("scene_targets", [])
            ],
        )
        annotation_count += 2

    return PrelabelResult(
        task="group1",
        exam_root=request.exam_root,
        review_dir=request.exam_root / "reviewed",
        source_labels_path=plan.source_labels_path,
        prediction_labels_path=prediction_result.labels_path,
        sample_count=len(predictions),
        annotation_count=annotation_count,
        prediction_command=prediction_result.command,
    )


def run_group2_prelabel(request: Group2PrelabelRequest) -> PrelabelResult:
    samples = _select_manifest_samples(exam_root=request.exam_root, expected_task="group2", limit=request.limit)
    review_master_dir = request.exam_root / "reviewed" / "master"
    review_tile_dir = request.exam_root / "reviewed" / "tile"
    _ensure_annotation_targets(
        sample_ids=[str(sample["sample_id"]) for sample in samples],
        annotation_dirs=[review_master_dir],
        overwrite=request.overwrite,
    )

    source_rows: list[dict[str, object]] = []
    review_master_images: dict[str, Path] = {}
    for sample in samples:
        sample_id = str(sample["sample_id"])
        master_source = _resolve_sample_asset(request.exam_root, sample, "master_image")
        tile_source = _resolve_sample_asset(request.exam_root, sample, "tile_image")
        review_master_images[sample_id] = _copy_review_asset(master_source, review_master_dir)
        _copy_review_asset(tile_source, review_tile_dir)

        master_width, master_height = get_image_size(master_source)
        tile_width, tile_height = get_image_size(tile_source)
        bbox_width = max(1, min(tile_width, master_width))
        bbox_height = max(1, min(tile_height, master_height))
        dummy_bbox = [0, 0, bbox_width, bbox_height]
        source_rows.append(
            {
                "sample_id": sample_id,
                "master_image": str(master_source),
                "tile_image": str(tile_source),
                "target_gap": {
                    "class": "slider_gap",
                    "class_id": 0,
                    "bbox": dummy_bbox,
                    "center": _bbox_center(dummy_bbox),
                },
                "tile_bbox": [0, 0, tile_width, tile_height],
                "offset_x": 0,
                "offset_y": 0,
                "label_source": "seed",
                "source_batch": request.exam_root.name,
            }
        )

    plan = build_group2_prelabel_plan(request)
    write_jsonl(plan.source_labels_path, source_rows)
    prediction_labels_path, predictions, prediction_command = _run_group2_prelabel_predictions(
        request=request,
        plan=plan,
        source_rows=source_rows,
    )
    for row in predictions:
        sample_id = str(row["sample_id"])
        master_image = review_master_images[sample_id]
        target = row["target_gap"]
        _write_labelme_annotation(
            review_master_dir / f"{sample_id}.json",
            image_path=master_image.name,
            image_width=get_image_size(master_image)[0],
            image_height=get_image_size(master_image)[1],
            shapes=[
                _build_rectangle_shape(
                    label=str(target["class"]),
                    bbox=_coerce_bbox(target["bbox"]),
                )
            ],
        )

    return PrelabelResult(
        task="group2",
        exam_root=request.exam_root,
        review_dir=request.exam_root / "reviewed",
        source_labels_path=plan.source_labels_path,
        prediction_labels_path=prediction_labels_path,
        sample_count=len(predictions),
        annotation_count=len(predictions),
        prediction_command=prediction_command,
    )


def run_group1_vlm_prelabel(request: Group1VlmPrelabelRequest) -> PrelabelResult:
    _emit_group1_vlm_log(
        "start "
        f"pair_root={request.pair_root} "
        f"project_dir={request.project_dir} "
        f"model={request.model} "
        f"ollama_url={request.ollama_url}"
    )
    if not request.pair_root.exists():
        raise RuntimeError(f"未找到 group1 成对图片目录：{request.pair_root}")
    if not request.pair_root.is_dir():
        raise RuntimeError(f"group1 成对图片输入路径不是目录：{request.pair_root}")
    query_dir = request.pair_root / "query"
    if not query_dir.exists():
        raise RuntimeError(f"未找到 group1 query 目录：{query_dir}")
    if not query_dir.is_dir():
        raise RuntimeError(f"group1 query 输入路径不是目录：{query_dir}")
    scene_dir = _resolve_group1_scene_dir(request.pair_root)
    pairs = _discover_group1_vlm_pairs(query_dir=query_dir, scene_dir=scene_dir, limit=request.limit)
    if not pairs:
        raise RuntimeError(f"group1 成对图片目录为空：{request.pair_root}")
    _emit_group1_vlm_log(
        f"discovered sample_count={len(pairs)} query_dir={query_dir} scene_dir={scene_dir}"
    )

    plan = build_group1_vlm_prelabel_plan(request)
    plan.project_dir.mkdir(parents=True, exist_ok=True)
    plan.process_dir.mkdir(parents=True, exist_ok=True)
    existing_index = _read_json_if_exists(plan.process_index_path)
    if isinstance(existing_index, dict):
        _emit_group1_vlm_log(
            "resume scan "
            f"process_index={plan.process_index_path} "
            f"status_counts={existing_index.get('status_counts', {})}"
        )
    _write_group1_vlm_process_index(
        plan=plan,
        pairs=pairs,
        query_dir=query_dir,
        scene_dir=scene_dir,
        source_batch=request.pair_root.name,
        model=request.model,
        ollama_url=request.ollama_url,
        timeout_seconds=request.timeout_seconds,
    )

    total_pairs = len(pairs)
    failed_sample_ids: list[str] = []
    processed_sample_ids: set[str] = set()
    for index, pair in enumerate(pairs, start=1):
        process_paths = _group1_vlm_sample_process_paths(plan.process_dir, pair.sample_id)
        if _can_reuse_group1_vlm_sample(process_paths):
            _emit_group1_vlm_log(
                f"[{index}/{total_pairs}] sample_id={pair.sample_id} reuse completed process artifacts"
            )
            continue

        _ensure_group1_vlm_review_targets(
            pair=pair,
            review_dir=plan.review_dir,
            overwrite=request.overwrite,
        )
        try:
            _run_group1_vlm_prelabel_sample(
                sample_index=index,
                sample_total=total_pairs,
                sample_id=pair.sample_id,
                query_image=pair.query_image,
                scene_image=pair.scene_image,
                model=request.model,
                ollama_url=request.ollama_url,
                timeout_seconds=request.timeout_seconds,
                source_batch=request.pair_root.name,
                process_paths=process_paths,
            )
            processed_sample_ids.add(pair.sample_id)
        except Exception as exc:
            failed_sample_ids.append(pair.sample_id)
            _emit_group1_vlm_log(
                f"[{index}/{total_pairs}] sample_id={pair.sample_id} failed error={exc}"
            )
        finally:
            _write_group1_vlm_process_index(
                plan=plan,
                pairs=pairs,
                query_dir=query_dir,
                scene_dir=scene_dir,
                source_batch=request.pair_root.name,
                model=request.model,
                ollama_url=request.ollama_url,
                timeout_seconds=request.timeout_seconds,
            )

    source_rows, prediction_rows, trace_rows, status_counts = _rebuild_group1_vlm_outputs(
        plan=plan,
        pairs=pairs,
        source_batch=request.pair_root.name,
        processed_sample_ids=processed_sample_ids,
        overwrite=request.overwrite,
    )
    annotation_count = len(prediction_rows) * 2

    write_jsonl(plan.source_labels_path, source_rows)
    write_jsonl(plan.prediction_labels_path, prediction_rows)
    write_jsonl(plan.trace_path, trace_rows)
    (plan.project_dir / "summary.json").write_text(
        json.dumps(
            {
                "task": "group1_vlm_prelabel",
                "pair_root": str(request.pair_root),
                "query_dir": str(query_dir),
                "scene_dir": str(scene_dir),
                "review_dir": str(plan.review_dir),
                "process_dir": str(plan.process_dir),
                "sample_count": len(pairs),
                "completed_sample_count": len(prediction_rows),
                "failed_sample_count": status_counts.get("failed", 0),
                "partial_sample_count": status_counts.get("partial", 0),
                "status_counts": status_counts,
                "source_labels_path": str(plan.source_labels_path),
                "prediction_labels_path": str(plan.prediction_labels_path),
                "trace_path": str(plan.trace_path),
                "model": request.model,
                "ollama_url": request.ollama_url,
                "timeout_seconds": request.timeout_seconds,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _emit_group1_vlm_log(
        "finished "
        f"completed_sample_count={len(prediction_rows)} "
        f"failed_sample_count={status_counts.get('failed', 0)} "
        f"prediction_labels_path={plan.prediction_labels_path} "
        f"trace_path={plan.trace_path}"
    )
    _write_group1_vlm_process_index(
        plan=plan,
        pairs=pairs,
        query_dir=query_dir,
        scene_dir=scene_dir,
        source_batch=request.pair_root.name,
        model=request.model,
        ollama_url=request.ollama_url,
        timeout_seconds=request.timeout_seconds,
    )

    if failed_sample_ids:
        failed_display = ", ".join(sorted(set(failed_sample_ids)))
        raise RuntimeError(f"group1 VLM 预标注存在失败样本：{failed_display}")

    return PrelabelResult(
        task="group1",
        exam_root=request.pair_root,
        review_dir=plan.review_dir,
        source_labels_path=plan.source_labels_path,
        prediction_labels_path=plan.prediction_labels_path,
        sample_count=len(prediction_rows),
        annotation_count=annotation_count,
        prediction_command=(
            f"ollama api/chat model={request.model} url={request.ollama_url} mode=group1-prelabel-vlm"
        ),
    )


def run_group1_query_directory_prelabel(
    request: Group1QueryDirectoryPrelabelRequest,
) -> Group1QueryDirectoryPrelabelResult:
    if not request.input_dir.exists():
        raise RuntimeError(f"未找到 query 图片目录：{request.input_dir}")
    if not request.input_dir.is_dir():
        raise RuntimeError(f"query 输入路径不是目录：{request.input_dir}")

    image_paths = _list_annotation_images(request.input_dir, limit=request.limit)
    if not image_paths:
        raise RuntimeError(f"query 图片目录为空：{request.input_dir}")
    _ensure_query_annotation_targets(image_paths=image_paths, overwrite=request.overwrite)
    plan = build_group1_query_directory_prelabel_plan(request)
    plan.output_dir.mkdir(parents=True, exist_ok=True)

    prediction_rows: list[dict[str, object]] = []
    for image_path in image_paths:
        detections = split_group1_query_image(image_path)
        width, height = get_image_size(image_path)
        _write_labelme_annotation(
            request.input_dir / f"{image_path.stem}.json",
            image_path=image_path.name,
            image_width=width,
            image_height=height,
            shapes=[
                _build_rectangle_shape(
                    label="query_item",
                    bbox=_coerce_bbox(target["bbox"]),
                    flags=_group1_shape_flags(target),
                )
                for target in detections
            ],
        )
        prediction_rows.append(
            {
                "image_path": str(image_path),
                "annotation_path": str(request.input_dir / f"{image_path.stem}.json"),
                "query_items": detections,
                "label_source": "pred",
            }
        )

    prediction_labels_path = plan.output_dir / "labels.jsonl"
    write_jsonl(prediction_labels_path, prediction_rows)
    (plan.output_dir / "summary.json").write_text(
        json.dumps(
            {
                "task": "group1_query_prelabel",
                "input_dir": str(request.input_dir),
                "query_splitter_strategy": "rule_based_v1",
                "sample_count": len(prediction_rows),
                "prediction_labels_path": str(prediction_labels_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return Group1QueryDirectoryPrelabelResult(
        input_dir=request.input_dir,
        output_dir=plan.output_dir,
        prediction_labels_path=prediction_labels_path,
        sample_count=len(prediction_rows),
        annotation_count=len(prediction_rows),
        splitter_strategy="rule_based_v1",
    )


def _run_group2_prelabel_predictions(
    *,
    request: Group2PrelabelRequest,
    plan: Group2PrelabelPlan,
    source_rows: list[dict[str, object]],
) -> tuple[Path, list[dict[str, object]], str]:
    aggregate_output_dir = plan.prediction_job.output_dir()
    aggregate_output_dir.mkdir(parents=True, exist_ok=True)
    per_sample_source_dir = plan.source_labels_path.parent / "per_sample"

    predictions: list[dict[str, object]] = []
    commands: list[str] = []
    for row in source_rows:
        sample_id = str(row["sample_id"])
        sample_source_path = per_sample_source_dir / f"{sample_id}.jsonl"
        write_jsonl(sample_source_path, [row])
        prediction_job = build_group2_prediction_job(
            dataset_config=plan.prediction_job.dataset_config,
            model_path=plan.prediction_job.model_path,
            source=sample_source_path,
            project_dir=aggregate_output_dir,
            run_name=sample_id,
            imgsz=plan.prediction_job.imgsz,
            device=plan.prediction_job.device,
        )
        prediction_result = run_group2_prediction_job(prediction_job)
        sample_predictions = read_jsonl(prediction_result.labels_path)
        if len(sample_predictions) != 1:
            raise RuntimeError(
                "group2 prelabel 单样本预测返回了非法结果数量："
                f"sample_id={sample_id} count={len(sample_predictions)}"
            )
        predictions.extend(sample_predictions)
        commands.append(prediction_result.command)

    aggregate_labels_path = aggregate_output_dir / "labels.jsonl"
    write_jsonl(aggregate_labels_path, predictions)
    (aggregate_output_dir / "summary.json").write_text(
        json.dumps(
            {
                "mode": "per_sample_group2_prelabel_predict",
                "dataset_config": str(plan.prediction_job.dataset_config),
                "source": str(plan.source_labels_path),
                "model": str(plan.prediction_job.model_path),
                "sample_count": len(predictions),
                "labels_path": str(aggregate_labels_path),
                "per_sample_source_dir": str(per_sample_source_dir),
                "per_sample_output_dir": str(aggregate_output_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return aggregate_labels_path, predictions, _render_group2_prelabel_prediction_command(commands)


def _render_group2_prelabel_prediction_command(commands: list[str]) -> str:
    if not commands:
        return "per-sample group2 prediction skipped: no samples"
    if len(commands) == 1:
        return commands[0]
    return (
        f"per-sample group2 prediction x{len(commands)}; "
        f"first command: {commands[0]}"
    )


def _generated_dir(exam_root: Path, task: str) -> Path:
    return exam_root / ".sinan" / "prelabel" / task


@dataclass(frozen=True)
class Group1VlmPair:
    sample_id: str
    query_image: Path
    scene_image: Path


@dataclass(frozen=True)
class Group1VlmSampleProcessPaths:
    sample_root: Path
    status_path: Path
    request_path: Path
    response_path: Path
    normalized_path: Path
    error_path: Path


@dataclass(frozen=True)
class Group1VlmPreparedSampleRequest:
    prompt: str
    query_width: int
    query_height: int
    scene_width: int
    scene_height: int
    request_payload: dict[str, object]


def _resolve_group1_scene_dir(pair_root: Path) -> Path:
    for dirname in ("scene", "scence"):
        candidate = pair_root / dirname
        if candidate.exists():
            if not candidate.is_dir():
                raise RuntimeError(f"group1 scene 输入路径不是目录：{candidate}")
            return candidate
    raise RuntimeError(
        "未找到 group1 scene 目录，当前仅支持 `scene/` 或历史拼写 `scence/`："
        f"{pair_root}"
    )


def _discover_group1_vlm_pairs(*, query_dir: Path, scene_dir: Path, limit: int | None) -> list[Group1VlmPair]:
    query_images = _index_images_by_stem(_list_annotation_images(query_dir, limit=None), label="query")
    scene_images = _index_images_by_stem(_list_annotation_images(scene_dir, limit=None), label="scene")
    if not query_images:
        return []
    missing_scene = sorted(stem for stem in query_images if stem not in scene_images)
    missing_query = sorted(stem for stem in scene_images if stem not in query_images)
    if missing_scene:
        raise RuntimeError(f"这些 query 图片缺少同名 scene 图片：{', '.join(missing_scene[:10])}")
    if missing_query:
        raise RuntimeError(f"这些 scene 图片缺少同名 query 图片：{', '.join(missing_query[:10])}")
    pairs = [
        Group1VlmPair(
            sample_id=stem,
            query_image=query_images[stem],
            scene_image=scene_images[stem],
        )
        for stem in sorted(query_images)
    ]
    if limit is None or limit >= len(pairs):
        return pairs
    return pairs[:limit]


def _index_images_by_stem(image_paths: list[Path], *, label: str) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for image_path in image_paths:
        if image_path.stem in indexed:
            raise RuntimeError(
                f"group1 {label} 目录存在同名不同扩展名图片，当前不支持："
                f"{indexed[image_path.stem]} / {image_path}"
            )
        indexed[image_path.stem] = image_path
    return indexed


def _list_annotation_images(input_dir: Path, limit: int | None) -> list[Path]:
    images = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if limit is None or limit >= len(images):
        return images
    return images[:limit]


def _select_manifest_samples(*, exam_root: Path, expected_task: str, limit: int | None) -> list[dict[str, object]]:
    manifest_path = exam_root / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"未找到试卷 manifest：{manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"试卷 manifest 格式非法：{manifest_path}")
    if str(payload.get("task", "")) != expected_task:
        raise RuntimeError(f"试卷 manifest 任务不匹配：期望 {expected_task}，实际 {payload.get('task')}")
    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list):
        raise RuntimeError(f"试卷 manifest 缺少 samples：{manifest_path}")
    ordered_samples = sorted(
        (item for item in raw_samples if isinstance(item, dict)),
        key=lambda item: str(item.get("sample_id", "")),
    )
    if limit is None or limit >= len(ordered_samples):
        return ordered_samples
    return ordered_samples[:limit]


def _resolve_sample_asset(exam_root: Path, sample: dict[str, object], key: str) -> Path:
    raw_value = sample.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise RuntimeError(f"试卷样本缺少 {key}：{sample}")
    candidate = Path(raw_value)
    resolved = candidate if candidate.is_absolute() else (exam_root / candidate).resolve()
    if not resolved.exists():
        raise RuntimeError(f"未找到试卷样本图片：{resolved}")
    return resolved


def _copy_review_asset(source: Path, review_dir: Path, *, overwrite: bool = True) -> Path:
    review_dir.mkdir(parents=True, exist_ok=True)
    destination = review_dir / source.name
    if overwrite or not destination.exists():
        shutil.copy2(source, destination)
    return destination


def _group1_vlm_sample_process_paths(process_dir: Path, sample_id: str) -> Group1VlmSampleProcessPaths:
    sample_root = process_dir / "samples" / sample_id
    return Group1VlmSampleProcessPaths(
        sample_root=sample_root,
        status_path=sample_root / "status.json",
        request_path=sample_root / "request.json",
        response_path=sample_root / "response.json",
        normalized_path=sample_root / "normalized.json",
        error_path=sample_root / "error.json",
    )


def _group1_vlm_status_counts_template() -> dict[str, int]:
    return {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "partial": 0,
    }


def _group1_vlm_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_document(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_group1_vlm_status(
    *,
    sample_id: str,
    process_paths: Group1VlmSampleProcessPaths,
) -> str:
    status_payload = _read_json_if_exists(process_paths.status_path)
    status = ""
    if isinstance(status_payload, dict):
        raw_status = status_payload.get("status")
        if isinstance(raw_status, str):
            status = raw_status.strip().lower()
    if status == "completed" and process_paths.normalized_path.exists():
        return "completed"
    if status == "completed":
        return "partial"
    if status in {"running", "failed", "partial", "pending"}:
        return status
    if any(
        artifact.exists()
        for artifact in (
            process_paths.request_path,
            process_paths.response_path,
            process_paths.normalized_path,
            process_paths.error_path,
        )
    ):
        return "partial"
    _ = sample_id
    return "pending"


def _can_reuse_group1_vlm_sample(process_paths: Group1VlmSampleProcessPaths) -> bool:
    return (
        _normalize_group1_vlm_status(
            sample_id=process_paths.sample_root.name,
            process_paths=process_paths,
        )
        == "completed"
    )


def _reset_group1_vlm_sample_process(process_paths: Group1VlmSampleProcessPaths) -> None:
    process_paths.sample_root.mkdir(parents=True, exist_ok=True)
    for artifact in (
        process_paths.request_path,
        process_paths.response_path,
        process_paths.normalized_path,
        process_paths.error_path,
    ):
        if artifact.exists():
            artifact.unlink()


def _write_group1_vlm_status(
    *,
    process_paths: Group1VlmSampleProcessPaths,
    sample_id: str,
    status: str,
    attempt_count: int,
    query_image: Path,
    scene_image: Path,
    model: str,
    ollama_url: str,
    timeout_seconds: int,
    error_message: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "sample_id": sample_id,
        "status": status,
        "attempt_count": attempt_count,
        "updated_at": _group1_vlm_now(),
        "query_image": str(query_image),
        "scene_image": str(scene_image),
        "model": model,
        "ollama_url": ollama_url,
        "timeout_seconds": timeout_seconds,
        "artifacts": {
            "request": str(process_paths.request_path),
            "response": str(process_paths.response_path),
            "normalized": str(process_paths.normalized_path),
            "error": str(process_paths.error_path),
        },
    }
    if error_message:
        payload["error_message"] = error_message
    _write_json_document(process_paths.status_path, payload)


def _write_group1_vlm_process_index(
    *,
    plan: Group1VlmPrelabelPlan,
    pairs: list[Group1VlmPair],
    query_dir: Path,
    scene_dir: Path,
    source_batch: str,
    model: str,
    ollama_url: str,
    timeout_seconds: int,
) -> None:
    status_counts = _group1_vlm_status_counts_template()
    samples: list[dict[str, object]] = []
    for pair in pairs:
        process_paths = _group1_vlm_sample_process_paths(plan.process_dir, pair.sample_id)
        status = _normalize_group1_vlm_status(sample_id=pair.sample_id, process_paths=process_paths)
        status_counts[status] += 1
        samples.append(
            {
                "sample_id": pair.sample_id,
                "status": status,
                "query_image": str(pair.query_image),
                "scene_image": str(pair.scene_image),
                "sample_root": str(process_paths.sample_root),
                "status_path": str(process_paths.status_path),
                "request_path": str(process_paths.request_path),
                "response_path": str(process_paths.response_path),
                "normalized_path": str(process_paths.normalized_path),
                "error_path": str(process_paths.error_path),
            }
        )
    _write_json_document(
        plan.process_index_path,
        {
            "task": "group1_vlm_prelabel",
            "updated_at": _group1_vlm_now(),
            "pair_root": str(plan.pair_root),
            "query_dir": str(query_dir),
            "scene_dir": str(scene_dir),
            "project_dir": str(plan.project_dir),
            "review_dir": str(plan.review_dir),
            "process_dir": str(plan.process_dir),
            "source_batch": source_batch,
            "sample_count": len(pairs),
            "status_counts": status_counts,
            "model": model,
            "ollama_url": ollama_url,
            "timeout_seconds": timeout_seconds,
            "samples": samples,
        },
    )


def _ensure_group1_vlm_review_targets(
    *,
    pair: Group1VlmPair,
    review_dir: Path,
    overwrite: bool,
) -> None:
    if overwrite:
        return
    for annotation_path in (
        review_dir / "query" / f"{pair.sample_id}.json",
        review_dir / "scene" / f"{pair.sample_id}.json",
    ):
        if annotation_path.exists():
            raise RuntimeError(
                "发现已存在的 reviewed 标注文件，已停止以避免覆盖人工复核结果："
                f"{annotation_path}\n如确需重跑，请显式传入 --overwrite。"
            )


def _build_group1_vlm_source_row(*, pair: Group1VlmPair, source_batch: str) -> dict[str, object]:
    return {
        "sample_id": pair.sample_id,
        "query_image": str(pair.query_image),
        "scene_image": str(pair.scene_image),
        "query_items": [],
        "scene_targets": [],
        "distractors": [],
        "label_source": "seed",
        "source_batch": source_batch,
    }


def _load_group1_vlm_prediction_from_process(
    *,
    pair: Group1VlmPair,
    process_paths: Group1VlmSampleProcessPaths,
) -> dict[str, object]:
    payload = _read_json_if_exists(process_paths.normalized_path)
    if not isinstance(payload, dict):
        raise RuntimeError(
            "group1 VLM 过程工件缺少有效 normalized.json："
            f"sample_id={pair.sample_id} path={process_paths.normalized_path}"
        )
    prediction = payload.get("prediction")
    if not isinstance(prediction, dict):
        raise RuntimeError(
            "group1 VLM 过程工件 normalized.json 缺少 prediction："
            f"sample_id={pair.sample_id} path={process_paths.normalized_path}"
        )
    return prediction


def _build_group1_vlm_trace_from_process(
    *,
    pair: Group1VlmPair,
    process_paths: Group1VlmSampleProcessPaths,
) -> dict[str, object]:
    request_payload = _read_json_if_exists(process_paths.request_path)
    response_payload = _read_json_if_exists(process_paths.response_path)
    trace_row: dict[str, object] = {
        "sample_id": pair.sample_id,
        "query_image": str(pair.query_image),
        "scene_image": str(pair.scene_image),
    }
    if isinstance(request_payload, dict):
        if isinstance(request_payload.get("model"), str):
            trace_row["model"] = request_payload["model"]
        if isinstance(request_payload.get("ollama_url"), str):
            trace_row["ollama_url"] = request_payload["ollama_url"]
        if isinstance(request_payload.get("prompt"), str):
            trace_row["prompt"] = request_payload["prompt"]
    if isinstance(response_payload, dict):
        if isinstance(response_payload.get("raw_output"), str):
            trace_row["raw_output"] = response_payload["raw_output"]
        if "response_payload" in response_payload:
            trace_row["response_payload"] = response_payload["response_payload"]
    return trace_row


def _write_group1_vlm_reviewed_sample(
    *,
    pair: Group1VlmPair,
    prediction_row: dict[str, object],
    review_dir: Path,
    overwrite: bool,
) -> None:
    review_query_dir = review_dir / "query"
    review_scene_dir = review_dir / "scene"
    review_query_image = _copy_review_asset(pair.query_image, review_query_dir, overwrite=overwrite)
    review_scene_image = _copy_review_asset(pair.scene_image, review_scene_dir, overwrite=overwrite)
    query_width, query_height = get_image_size(review_query_image)
    scene_width, scene_height = get_image_size(review_scene_image)
    _write_labelme_annotation(
        review_query_dir / f"{pair.sample_id}.json",
        image_path=review_query_image.name,
        image_width=query_width,
        image_height=query_height,
        shapes=[
            _build_rectangle_shape(
                label="query_item",
                bbox=_coerce_bbox(target["bbox"]),
                flags=_group1_shape_flags(target),
            )
            for target in _group1_query_items(prediction_row)
        ],
        overwrite=overwrite,
    )
    _write_labelme_annotation(
        review_scene_dir / f"{pair.sample_id}.json",
        image_path=review_scene_image.name,
        image_width=scene_width,
        image_height=scene_height,
        shapes=[
            _build_rectangle_shape(
                label=f"{int(target['order']):02d}",
                bbox=_coerce_bbox(target["bbox"]),
                flags=_group1_shape_flags(target),
            )
            for target in prediction_row.get("scene_targets", [])
            if isinstance(target, dict)
        ],
        overwrite=overwrite,
    )


def _rebuild_group1_vlm_outputs(
    *,
    plan: Group1VlmPrelabelPlan,
    pairs: list[Group1VlmPair],
    source_batch: str,
    processed_sample_ids: set[str],
    overwrite: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    source_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    trace_rows: list[dict[str, object]] = []
    status_counts = _group1_vlm_status_counts_template()

    for pair in pairs:
        source_rows.append(_build_group1_vlm_source_row(pair=pair, source_batch=source_batch))
        process_paths = _group1_vlm_sample_process_paths(plan.process_dir, pair.sample_id)
        status = _normalize_group1_vlm_status(sample_id=pair.sample_id, process_paths=process_paths)
        status_counts[status] += 1
        if status != "completed":
            continue
        prediction_row = _load_group1_vlm_prediction_from_process(pair=pair, process_paths=process_paths)
        prediction_rows.append(prediction_row)
        trace_rows.append(_build_group1_vlm_trace_from_process(pair=pair, process_paths=process_paths))
        _write_group1_vlm_reviewed_sample(
            pair=pair,
            prediction_row=prediction_row,
            review_dir=plan.review_dir,
            overwrite=overwrite or pair.sample_id in processed_sample_ids,
        )

    return source_rows, prediction_rows, trace_rows, status_counts


def _ensure_annotation_targets(*, sample_ids: list[str], annotation_dirs: list[Path], overwrite: bool) -> None:
    if overwrite:
        return
    for annotation_dir in annotation_dirs:
        for sample_id in sample_ids:
            existing = annotation_dir / f"{sample_id}.json"
            if existing.exists():
                raise RuntimeError(
                    "发现已存在的 reviewed 标注文件，已停止以避免覆盖人工复核结果："
                    f"{existing}\n如确需重跑，请显式传入 --overwrite。"
                )


def _ensure_query_annotation_targets(*, image_paths: list[Path], overwrite: bool) -> None:
    if overwrite:
        return
    for image_path in image_paths:
        existing = image_path.with_suffix(".json")
        if existing.exists():
            raise RuntimeError(
                "发现已存在的 query 标注文件，已停止以避免覆盖人工复核结果："
                f"{existing}\n如确需重跑，请显式传入 --overwrite。"
            )


def _write_labelme_annotation(
    path: Path,
    *,
    image_path: str,
    image_width: int,
    image_height: int,
    shapes: list[dict[str, object]],
    overwrite: bool = True,
) -> None:
    if not overwrite and path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "5.5.0",
        "flags": {},
        "shapes": shapes,
        "imagePath": image_path,
        "imageData": None,
        "imageHeight": image_height,
        "imageWidth": image_width,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_rectangle_shape(
    *,
    label: str,
    bbox: list[int],
    flags: dict[str, object] | None = None,
) -> dict[str, object]:
    x1, y1, x2, y2 = bbox
    return {
        "label": label,
        "shape_type": "rectangle",
        "points": [[x1, y1], [x2, y2]],
        "flags": dict(flags or {}),
    }


def _coerce_bbox(raw_bbox: Any) -> list[int]:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        raise RuntimeError(f"预测 bbox 非法：{raw_bbox!r}")
    return [int(value) for value in raw_bbox]


def _bbox_center(bbox: list[int]) -> list[int]:
    return [int(round((bbox[0] + bbox[2]) / 2)), int(round((bbox[1] + bbox[3]) / 2))]


def _prepare_group1_vlm_prelabel_request(
    *,
    sample_id: str,
    query_image: Path,
    scene_image: Path,
    model: str,
) -> Group1VlmPreparedSampleRequest:
    query_width, query_height = get_image_size(query_image)
    scene_width, scene_height = get_image_size(scene_image)
    prompt = _build_group1_vlm_prelabel_prompt(
        sample_id=sample_id,
        query_width=query_width,
        query_height=query_height,
        scene_width=scene_width,
        scene_height=scene_height,
    )
    return Group1VlmPreparedSampleRequest(
        prompt=prompt,
        query_width=query_width,
        query_height=query_height,
        scene_width=scene_width,
        scene_height=scene_height,
        request_payload={
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [
                        base64.b64encode(query_image.read_bytes()).decode("ascii"),
                        base64.b64encode(scene_image.read_bytes()).decode("ascii"),
                    ],
                }
            ],
        },
    )


def _run_group1_vlm_prelabel_sample(
    *,
    sample_index: int,
    sample_total: int,
    sample_id: str,
    query_image: Path,
    scene_image: Path,
    model: str,
    ollama_url: str,
    timeout_seconds: int,
    source_batch: str,
    process_paths: Group1VlmSampleProcessPaths,
) -> None:
    previous_status = _read_json_if_exists(process_paths.status_path)
    attempt_count = 1
    if isinstance(previous_status, dict):
        previous_attempt_count = previous_status.get("attempt_count")
        if isinstance(previous_attempt_count, int) and previous_attempt_count > 0:
            attempt_count = previous_attempt_count + 1
    _reset_group1_vlm_sample_process(process_paths)

    _emit_group1_vlm_log(
        f"[{sample_index}/{sample_total}] sample_id={sample_id} build prompt "
        f"query_image={query_image} scene_image={scene_image}"
    )
    prepared_request = _prepare_group1_vlm_prelabel_request(
        sample_id=sample_id,
        query_image=query_image,
        scene_image=scene_image,
        model=model,
    )
    request_record = {
        "sample_id": sample_id,
        "attempt_count": attempt_count,
        "created_at": _group1_vlm_now(),
        "query_image": str(query_image),
        "scene_image": str(scene_image),
        "query_size": {
            "width": prepared_request.query_width,
            "height": prepared_request.query_height,
        },
        "scene_size": {
            "width": prepared_request.scene_width,
            "height": prepared_request.scene_height,
        },
        "model": model,
        "ollama_url": ollama_url,
        "timeout_seconds": timeout_seconds,
        "source_batch": source_batch,
        "prompt": prepared_request.prompt,
        "request_payload": prepared_request.request_payload,
    }
    _write_group1_vlm_status(
        process_paths=process_paths,
        sample_id=sample_id,
        status="running",
        attempt_count=attempt_count,
        query_image=query_image,
        scene_image=scene_image,
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
    )
    _write_json_document(process_paths.request_path, request_record)
    _emit_group1_vlm_block(
        title=f"[{sample_index}/{sample_total}] sample_id={sample_id} prompt",
        content=prepared_request.prompt,
    )
    _emit_group1_vlm_log(
        f"[{sample_index}/{sample_total}] sample_id={sample_id} sending request "
        f"model={model} url={ollama_url.rstrip('/')}/api/chat"
    )
    try:
        raw_response = _post_json(
            f"{ollama_url.rstrip('/')}/api/chat",
            prepared_request.request_payload,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        _write_json_document(
            process_paths.error_path,
            {
                "sample_id": sample_id,
                "attempt_count": attempt_count,
                "stage": "request",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "updated_at": _group1_vlm_now(),
            },
        )
        _write_group1_vlm_status(
            process_paths=process_paths,
            sample_id=sample_id,
            status="failed",
            attempt_count=attempt_count,
            query_image=query_image,
            scene_image=scene_image,
            model=model,
            ollama_url=ollama_url,
            timeout_seconds=timeout_seconds,
            error_message=str(exc),
        )
        raise
    _emit_group1_vlm_block(
        title=f"[{sample_index}/{sample_total}] sample_id={sample_id} raw response payload",
        content=json.dumps(raw_response, ensure_ascii=False, indent=2, default=str),
    )
    raw_output = _extract_ollama_message_content(raw_response)
    _write_json_document(
        process_paths.response_path,
        {
            "sample_id": sample_id,
            "attempt_count": attempt_count,
            "received_at": _group1_vlm_now(),
            "response_payload": raw_response,
            "raw_output": raw_output,
        },
    )
    _emit_group1_vlm_block(
        title=f"[{sample_index}/{sample_total}] sample_id={sample_id} model content",
        content=raw_output,
    )
    try:
        payload = extract_json_object(raw_output, required_keys={"query_items", "scene_targets"})
        query_items = _normalize_vlm_query_items(
            payload.get("query_items"),
            image_width=prepared_request.query_width,
            image_height=prepared_request.query_height,
        )
        scene_targets = _normalize_vlm_scene_targets(
            payload.get("scene_targets"),
            image_width=prepared_request.scene_width,
            image_height=prepared_request.scene_height,
        )
        if not query_items:
            raise RuntimeError(f"group1 VLM 预标注未返回有效 query_items：sample_id={sample_id}")
    except Exception as exc:
        _write_json_document(
            process_paths.error_path,
            {
                "sample_id": sample_id,
                "attempt_count": attempt_count,
                "stage": "normalize",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "updated_at": _group1_vlm_now(),
            },
        )
        _write_group1_vlm_status(
            process_paths=process_paths,
            sample_id=sample_id,
            status="partial",
            attempt_count=attempt_count,
            query_image=query_image,
            scene_image=scene_image,
            model=model,
            ollama_url=ollama_url,
            timeout_seconds=timeout_seconds,
            error_message=str(exc),
        )
        raise
    _emit_group1_vlm_log(
        f"[{sample_index}/{sample_total}] sample_id={sample_id} normalized "
        f"query_items={len(query_items)} scene_targets={len(scene_targets)}"
    )
    prediction_row = {
        "sample_id": sample_id,
        "query_image": str(query_image),
        "scene_image": str(scene_image),
        "query_items": query_items,
        "scene_targets": scene_targets,
        "distractors": [],
        "label_source": "vlm_pred",
        "source_batch": source_batch,
    }
    _write_json_document(
        process_paths.normalized_path,
        {
            "sample_id": sample_id,
            "attempt_count": attempt_count,
            "updated_at": _group1_vlm_now(),
            "prediction": prediction_row,
        },
    )
    if process_paths.error_path.exists():
        process_paths.error_path.unlink()
    _write_group1_vlm_status(
        process_paths=process_paths,
        sample_id=sample_id,
        status="completed",
        attempt_count=attempt_count,
        query_image=query_image,
        scene_image=scene_image,
        model=model,
        ollama_url=ollama_url,
        timeout_seconds=timeout_seconds,
    )


def _build_group1_vlm_prelabel_prompt(
    *,
    sample_id: str,
    query_width: int,
    query_height: int,
    scene_width: int,
    scene_height: int,
) -> str:
    return (
        "你在为 group1 click captcha 做预标注。现在给你两张图：\n"
        f"- 第 1 张图是 query 图，尺寸 {query_width}x{query_height}。\n"
        f"- 第 2 张图是 scene 图，尺寸 {scene_width}x{scene_height}。\n"
        f"- 当前样本编号是 {sample_id}。\n\n"
        "任务要求：\n"
        "1. 在 query 图中找出所有小图标，从左到右排序。\n"
        "2. 对每个 query 图标，在 scene 图中找出对应实例。\n"
        "3. 坐标必须使用各自原图像素坐标，bbox 格式严格为 [x1, y1, x2, y2]。\n"
        "4. x2 必须大于 x1，y2 必须大于 y1。\n"
        "5. class_guess 只写一个简短英文猜测，例如 icon_lock / icon_star；不确定时可以省略。\n"
        "6. 只输出 JSON，不要输出 markdown，不要解释。\n\n"
        "输出格式：\n"
        "{\n"
        '  "query_items": [\n'
        '    {"order": 1, "bbox": [5, 8, 29, 30], "class_guess": "icon_lock", "confidence": 0.92}\n'
        "  ],\n"
        '  "scene_targets": [\n'
        '    {"order": 1, "bbox": [100, 40, 132, 72], "class_guess": "icon_lock", "confidence": 0.88}\n'
        "  ]\n"
        "}"
    )


def _normalize_vlm_query_items(
    raw_items: Any,
    *,
    image_width: int,
    image_height: int,
) -> list[dict[str, object]]:
    items = _normalize_vlm_targets(raw_items, image_width=image_width, image_height=image_height)
    items.sort(key=lambda item: (int(item["center"][0]), int(item["center"][1])))
    for order, item in enumerate(items, start=1):
        item.pop("_raw_order", None)
        item["order"] = order
    return items


def _normalize_vlm_scene_targets(
    raw_items: Any,
    *,
    image_width: int,
    image_height: int,
) -> list[dict[str, object]]:
    items = _normalize_vlm_targets(raw_items, image_width=image_width, image_height=image_height)
    items.sort(
        key=lambda item: (
            int(item.get("_raw_order", 10**9)),
            int(item["center"][0]),
            int(item["center"][1]),
        )
    )
    used_orders: set[int] = set()
    next_fallback_order = 1
    for item in items:
        raw_order = item.pop("_raw_order", None)
        if isinstance(raw_order, int) and raw_order > 0 and raw_order not in used_orders:
            item["order"] = raw_order
            used_orders.add(raw_order)
            continue
        while next_fallback_order in used_orders:
            next_fallback_order += 1
        item["order"] = next_fallback_order
        used_orders.add(next_fallback_order)
        next_fallback_order += 1
    items.sort(key=lambda item: (int(item["order"]), int(item["center"][0]), int(item["center"][1])))
    return items


def _normalize_vlm_targets(
    raw_items: Any,
    *,
    image_width: int,
    image_height: int,
) -> list[dict[str, object]]:
    if not isinstance(raw_items, list):
        raise RuntimeError("group1 VLM 预标注输出缺少目标列表。")
    normalized: list[dict[str, object]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            continue
        raw_bbox = raw_item.get("bbox")
        try:
            bbox = _normalize_vlm_bbox(raw_bbox, image_width=image_width, image_height=image_height)
        except RuntimeError:
            continue
        item: dict[str, object] = {
            "bbox": bbox,
            "center": _bbox_center(bbox),
        }
        raw_order = raw_item.get("order")
        if isinstance(raw_order, int) and raw_order > 0:
            item["_raw_order"] = raw_order
        class_guess = raw_item.get("class_guess")
        if isinstance(class_guess, str) and class_guess.strip():
            item["class_guess"] = class_guess.strip()
        score = raw_item.get("confidence", raw_item.get("score"))
        if isinstance(score, (int, float)):
            item["score"] = round(float(score), 6)
        normalized.append(item)
    return normalized


def _normalize_vlm_bbox(raw_bbox: Any, *, image_width: int, image_height: int) -> list[int]:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        raise RuntimeError(f"VLM bbox 非法：{raw_bbox!r}")
    x1_raw, y1_raw, x2_raw, y2_raw = [int(round(float(value))) for value in raw_bbox]
    left, right = sorted((x1_raw, x2_raw))
    top, bottom = sorted((y1_raw, y2_raw))
    x1 = max(0, min(image_width - 1, left))
    y1 = max(0, min(image_height - 1, top))
    x2 = max(x1 + 1, min(image_width, right))
    y2 = max(y1 + 1, min(image_height, bottom))
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError(f"VLM bbox 非法：{raw_bbox!r}")
    return [x1, y1, x2, y2]


def _emit_group1_vlm_log(message: str) -> None:
    print(f"[group1 prelabel-vlm] {message}", file=sys.stderr, flush=True)


def _emit_group1_vlm_block(*, title: str, content: str) -> None:
    _emit_group1_vlm_log(title)
    if not content:
        _emit_group1_vlm_log("  (empty)")
        return
    for line in str(content).splitlines():
        _emit_group1_vlm_log(f"  {line}")


def _group1_query_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    query_items = row.get("query_items", [])
    if not isinstance(query_items, list):
        return []
    return [target for target in query_items if isinstance(target, dict)]


def _group1_shape_flags(target: dict[str, Any]) -> dict[str, object]:
    class_guess = target.get("class_guess")
    if not isinstance(class_guess, str) or not class_guess.strip():
        return {}
    return {"class_guess": class_guess.strip()}
