"""Prediction-to-X-AnyLabeling export helpers for reviewed exam workspaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from core.common.images import get_image_size
from core.common.jsonl import read_jsonl, write_jsonl
from core.train.group1.service import (
    Group1PredictionJob,
    build_group1_prediction_job,
    run_group1_prediction_job,
)
from core.train.group2.service import (
    Group2PredictionJob,
    build_group2_prediction_job,
    run_group2_prediction_job,
)


@dataclass(frozen=True)
class Group1PrelabelRequest:
    exam_root: Path
    dataset_config: Path
    scene_model_path: Path
    query_model_path: Path
    project_dir: Path
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


def build_group1_prelabel_plan(request: Group1PrelabelRequest) -> Group1PrelabelPlan:
    source_labels_path = _generated_dir(request.exam_root, "group1") / "source.jsonl"
    job = build_group1_prediction_job(
        dataset_config=request.dataset_config,
        scene_model_path=request.scene_model_path,
        query_model_path=request.query_model_path,
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
                "query_targets": [],
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
                _build_rectangle_shape(label=str(target["class"]), bbox=_coerce_bbox(target["bbox"]))
                for target in row.get("query_targets", [])
            ],
        )
        _write_labelme_annotation(
            review_scene_dir / f"{sample_id}.json",
            image_path=scene_image.name,
            image_width=get_image_size(scene_image)[0],
            image_height=get_image_size(scene_image)[1],
            shapes=[
                _build_rectangle_shape(
                    label=f"{int(target['order']):02d}|{target['class']}",
                    bbox=_coerce_bbox(target["bbox"]),
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


def _copy_review_asset(source: Path, review_dir: Path) -> Path:
    review_dir.mkdir(parents=True, exist_ok=True)
    destination = review_dir / source.name
    shutil.copy2(source, destination)
    return destination


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


def _write_labelme_annotation(
    path: Path,
    *,
    image_path: str,
    image_width: int,
    image_height: int,
    shapes: list[dict[str, object]],
) -> None:
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


def _build_rectangle_shape(*, label: str, bbox: list[int]) -> dict[str, object]:
    x1, y1, x2, y2 = bbox
    return {
        "label": label,
        "shape_type": "rectangle",
        "points": [[x1, y1], [x2, y2]],
        "flags": {},
    }


def _coerce_bbox(raw_bbox: Any) -> list[int]:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        raise RuntimeError(f"预测 bbox 非法：{raw_bbox!r}")
    return [int(value) for value in raw_bbox]


def _bbox_center(bbox: list[int]) -> list[int]:
    return [int(round((bbox[0] + bbox[2]) / 2)), int(round((bbox[1] + bbox[3]) / 2))]
