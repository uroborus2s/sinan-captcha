"""Prediction-to-X-AnyLabeling export helpers for reviewed exam workspaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from core.common.images import get_image_size
from core.common.jsonl import read_jsonl, write_jsonl
from core.train.base import _ensure_training_dependencies
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

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class Group1PrelabelRequest:
    exam_root: Path
    dataset_config: Path
    proposal_model_path: Path
    query_model_path: Path
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
    query_model_path: Path
    project_dir: Path
    run_name: str = "prelabel-query"
    conf: float = 0.25
    imgsz: int = 640
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


@dataclass(frozen=True)
class Group1QueryDirectoryPrelabelPlan:
    input_dir: Path
    query_model_path: Path
    project_dir: Path
    output_dir: Path
    run_name: str
    conf: float
    imgsz: int
    device: str
    limit: int | None
    overwrite: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "input_dir": str(self.input_dir),
            "query_model_path": str(self.query_model_path),
            "project_dir": str(self.project_dir),
            "output_dir": str(self.output_dir),
            "run_name": self.run_name,
            "conf": self.conf,
            "imgsz": self.imgsz,
            "device": self.device,
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
    model_path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "prediction_labels_path": str(self.prediction_labels_path),
            "sample_count": self.sample_count,
            "annotation_count": self.annotation_count,
            "model_path": str(self.model_path),
        }


def build_group1_prelabel_plan(request: Group1PrelabelRequest) -> Group1PrelabelPlan:
    source_labels_path = _generated_dir(request.exam_root, "group1") / "source.jsonl"
    job = build_group1_prediction_job(
        dataset_config=request.dataset_config,
        proposal_model_path=request.proposal_model_path,
        query_model_path=request.query_model_path,
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
        query_model_path=request.query_model_path,
        project_dir=request.project_dir,
        output_dir=output_dir,
        run_name=request.run_name,
        conf=request.conf,
        imgsz=request.imgsz,
        device=request.device,
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
                for target in _group1_query_targets(row)
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


def run_group1_query_directory_prelabel(
    request: Group1QueryDirectoryPrelabelRequest,
) -> Group1QueryDirectoryPrelabelResult:
    _ensure_training_dependencies()
    if not request.input_dir.exists():
        raise RuntimeError(f"未找到 query 图片目录：{request.input_dir}")
    if not request.input_dir.is_dir():
        raise RuntimeError(f"query 输入路径不是目录：{request.input_dir}")
    if not request.query_model_path.exists():
        raise RuntimeError(f"未找到 group1 query parser 权重：{request.query_model_path}")

    image_paths = _list_annotation_images(request.input_dir, limit=request.limit)
    if not image_paths:
        raise RuntimeError(f"query 图片目录为空：{request.input_dir}")
    _ensure_query_annotation_targets(image_paths=image_paths, overwrite=request.overwrite)

    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - host environment dependent
        raise RuntimeError(
            "当前环境缺少 `ultralytics`，无法执行 group1 query 目录预标注。"
        ) from exc

    model = YOLO(str(request.query_model_path))
    plan = build_group1_query_directory_prelabel_plan(request)
    plan.output_dir.mkdir(parents=True, exist_ok=True)

    prediction_rows: list[dict[str, object]] = []
    for image_path in image_paths:
        prediction = model.predict(
            source=str(image_path),
            imgsz=request.imgsz,
            conf=request.conf,
            device=request.device,
            verbose=False,
        )[0]
        detections = _serialize_query_detections(prediction)
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
                "query_targets": detections,
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
                "query_model_path": str(request.query_model_path),
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
        model_path=request.query_model_path,
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


def _group1_query_targets(row: dict[str, Any]) -> list[dict[str, Any]]:
    query_targets = row.get("query_items", row.get("query_targets", []))
    if not isinstance(query_targets, list):
        return []
    return [target for target in query_targets if isinstance(target, dict)]


def _group1_shape_flags(target: dict[str, Any]) -> dict[str, object]:
    class_guess = target.get("class_guess")
    if not isinstance(class_guess, str) or not class_guess.strip():
        raw_class = target.get("class")
        if isinstance(raw_class, str) and raw_class.strip():
            class_guess = raw_class.strip()
    if not isinstance(class_guess, str) or not class_guess.strip():
        return {}
    return {"class_guess": class_guess.strip()}


def _serialize_query_detections(result: Any) -> list[dict[str, Any]]:
    boxes = result.boxes
    if boxes is None:
        return []
    names = result.names if isinstance(result.names, dict) else {}
    detections: list[dict[str, Any]] = []
    xyxy = boxes.xyxy.tolist()
    cls_ids = boxes.cls.tolist()
    confidences = boxes.conf.tolist()
    for bbox, class_id, score in zip(xyxy, cls_ids, confidences, strict=False):
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        center_x = int(round((x1 + x2) / 2))
        center_y = int(round((y1 + y2) / 2))
        numeric_class_id = int(class_id)
        class_name = str(names.get(numeric_class_id, numeric_class_id))
        detections.append(
            {
                "class": class_name,
                "class_id": numeric_class_id,
                "bbox": [x1, y1, x2, y2],
                "center": [center_x, center_y],
                "score": float(score),
            }
        )
    detections.sort(key=lambda item: (int(item["center"][0]), int(item["center"][1])))
    for order, detection in enumerate(detections, start=1):
        detection["order"] = order
    return detections
