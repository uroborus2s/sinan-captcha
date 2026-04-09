"""Prepare reviewed business exam sources and export reviewed labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from core.common.images import get_image_size
from core.common.jsonl import read_jsonl, write_jsonl


@dataclass(frozen=True)
class ExamPrepareResult:
    task: str
    output_dir: Path
    manifest_path: Path
    sample_count: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["output_dir"] = str(self.output_dir)
        payload["manifest_path"] = str(self.manifest_path)
        return payload


@dataclass(frozen=True)
class ReviewedExportResult:
    task: str
    labels_path: Path
    sample_count: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["labels_path"] = str(self.labels_path)
        return payload


@dataclass(frozen=True)
class Group2PrelabelYoloResult:
    output_dir: Path
    dataset_yaml: Path
    sample_count: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["output_dir"] = str(self.output_dir)
        payload["dataset_yaml"] = str(self.dataset_yaml)
        return payload


def prepare_group1_exam_sources(*, materials_root: Path, output_dir: Path) -> ExamPrepareResult:
    source_root = materials_root / "group1"
    if not source_root.exists():
        raise RuntimeError(f"未找到 group1 原始素材目录：{source_root}")
    query_dir = output_dir / "import" / "query"
    scene_dir = output_dir / "import" / "scene"
    query_dir.mkdir(parents=True, exist_ok=True)
    scene_dir.mkdir(parents=True, exist_ok=True)

    samples: list[dict[str, str]] = []
    for case_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        sample_id = case_dir.name
        icon_path = case_dir / "icon.jpg"
        bg_path = case_dir / "bg.jpg"
        if not icon_path.exists() or not bg_path.exists():
            continue
        query_target = query_dir / f"{sample_id}{icon_path.suffix.lower()}"
        scene_target = scene_dir / f"{sample_id}{bg_path.suffix.lower()}"
        shutil.copy2(icon_path, query_target)
        shutil.copy2(bg_path, scene_target)
        samples.append(
            {
                "sample_id": sample_id,
                "source_case_dir": str(case_dir),
                "query_image": str(query_target.relative_to(output_dir)),
                "scene_image": str(scene_target.relative_to(output_dir)),
            }
        )

    return _write_exam_manifest(task="group1", output_dir=output_dir, samples=samples)


def prepare_group2_exam_sources(*, materials_root: Path, output_dir: Path) -> ExamPrepareResult:
    source_root = materials_root / "result"
    if not source_root.exists():
        raise RuntimeError(f"未找到 group2 原始素材目录：{source_root}")
    master_dir = output_dir / "import" / "master"
    tile_dir = output_dir / "import" / "tile"
    master_dir.mkdir(parents=True, exist_ok=True)
    tile_dir.mkdir(parents=True, exist_ok=True)

    samples: list[dict[str, str]] = []
    for case_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        sample_id = case_dir.name
        master_path = case_dir / "bg.jpg"
        tile_path = case_dir / "gap.jpg"
        if not master_path.exists() or not tile_path.exists():
            continue
        master_target = master_dir / f"{sample_id}{master_path.suffix.lower()}"
        tile_target = tile_dir / f"{sample_id}{tile_path.suffix.lower()}"
        shutil.copy2(master_path, master_target)
        shutil.copy2(tile_path, tile_target)
        samples.append(
            {
                "sample_id": sample_id,
                "source_case_dir": str(case_dir),
                "master_image": str(master_target.relative_to(output_dir)),
                "tile_image": str(tile_target.relative_to(output_dir)),
            }
        )

    return _write_exam_manifest(task="group2", output_dir=output_dir, samples=samples)


def export_group1_reviewed_labels(*, exam_root: Path) -> ReviewedExportResult:
    query_dir = exam_root / "reviewed" / "query"
    scene_dir = exam_root / "reviewed" / "scene"
    if not query_dir.exists() or not scene_dir.exists():
        raise RuntimeError(f"未找到 group1 reviewed 标注目录：{exam_root / 'reviewed'}")

    sample_ids = sorted(
        path.stem
        for path in query_dir.glob("*.json")
        if (scene_dir / f"{path.stem}.json").exists()
    )
    class_map = _group1_class_map(query_dir=query_dir, scene_dir=scene_dir, sample_ids=sample_ids)
    rows: list[dict[str, object]] = []
    for sample_id in sample_ids:
        query_image = _find_image_for_sample(query_dir, sample_id)
        scene_image = _find_image_for_sample(scene_dir, sample_id)
        query_targets = _load_group1_query_targets(
            query_dir / f"{sample_id}.json",
            class_map=class_map,
        )
        scene_targets = _load_group1_scene_targets(
            scene_dir / f"{sample_id}.json",
            class_map=class_map,
        )
        rows.append(
            {
                "sample_id": sample_id,
                "query_image": f"query/{query_image.name}",
                "scene_image": f"scene/{scene_image.name}",
                "query_targets": query_targets,
                "scene_targets": scene_targets,
                "distractors": [],
                "label_source": "reviewed",
                "source_batch": exam_root.name,
            }
        )

    labels_path = exam_root / "reviewed" / "labels.jsonl"
    write_jsonl(labels_path, rows)
    return ReviewedExportResult(task="group1", labels_path=labels_path, sample_count=len(rows))


def export_group2_reviewed_labels(*, exam_root: Path) -> ReviewedExportResult:
    master_dir = exam_root / "reviewed" / "master"
    tile_dir = exam_root / "reviewed" / "tile"
    if not master_dir.exists() or not tile_dir.exists():
        raise RuntimeError(f"未找到 group2 reviewed 标注目录：{exam_root / 'reviewed'}")

    rows: list[dict[str, object]] = []
    for annotation_path in sorted(master_dir.glob("*.json")):
        sample_id = annotation_path.stem
        master_image = _find_image_for_sample(master_dir, sample_id)
        tile_image = _find_image_for_sample(tile_dir, sample_id)
        gap_bbox = _load_single_rectangle(annotation_path, expected_label="slider_gap")
        tile_width, tile_height = get_image_size(tile_image)
        rows.append(
            {
                "sample_id": sample_id,
                "master_image": f"master/{master_image.name}",
                "tile_image": f"tile/{tile_image.name}",
                "target_gap": {
                    "class": "slider_gap",
                    "class_id": 0,
                    "bbox": gap_bbox,
                    "center": _bbox_center(gap_bbox),
                },
                "tile_bbox": [0, 0, tile_width, tile_height],
                "offset_x": int(gap_bbox[0]),
                "offset_y": int(gap_bbox[1]),
                "label_source": "reviewed",
                "source_batch": exam_root.name,
            }
        )

    labels_path = exam_root / "reviewed" / "labels.jsonl"
    write_jsonl(labels_path, rows)
    return ReviewedExportResult(task="group2", labels_path=labels_path, sample_count=len(rows))


def build_group2_prelabel_yolo_dataset(*, source_dir: Path, output_dir: Path) -> Group2PrelabelYoloResult:
    labels_path = source_dir / "labels.jsonl"
    if not labels_path.exists():
        raise RuntimeError(f"未找到 group2 reviewed labels.jsonl：{labels_path}")
    rows = read_jsonl(labels_path)
    image_dir = output_dir / "images" / "all"
    label_dir = output_dir / "labels" / "all"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    sample_count = 0
    for row in rows:
        sample_id = str(row["sample_id"])
        master_relative = Path(str(row["master_image"]))
        master_source = source_dir / master_relative
        if not master_source.exists():
            raise RuntimeError(f"未找到 group2 master 图片：{master_source}")
        bbox = [int(value) for value in row["target_gap"]["bbox"]]
        width, height = get_image_size(master_source)
        image_target = image_dir / master_source.name
        shutil.copy2(master_source, image_target)
        yolo_line = _yolo_bbox_line(class_id=0, bbox=bbox, image_width=width, image_height=height)
        (label_dir / f"{sample_id}.txt").write_text(yolo_line + "\n", encoding="utf-8")
        sample_count += 1

    dataset_yaml = output_dir / "dataset.yaml"
    dataset_yaml.write_text(
        "\n".join(
            [
                f"path: {output_dir.as_posix()}",
                "train: images/all",
                "val: images/all",
                "test: images/all",
                "names:",
                "  0: slider_gap",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return Group2PrelabelYoloResult(output_dir=output_dir, dataset_yaml=dataset_yaml, sample_count=sample_count)


def _write_exam_manifest(*, task: str, output_dir: Path, samples: list[dict[str, str]]) -> ExamPrepareResult:
    manifest_path = output_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": task,
        "sample_count": len(samples),
        "samples": samples,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ExamPrepareResult(task=task, output_dir=output_dir, manifest_path=manifest_path, sample_count=len(samples))


def _group1_class_map(*, query_dir: Path, scene_dir: Path, sample_ids: list[str]) -> dict[str, int]:
    class_names: set[str] = set()
    for sample_id in sample_ids:
        class_names.update(_query_shape_labels(query_dir / f"{sample_id}.json"))
        class_names.update(_scene_shape_class_names(scene_dir / f"{sample_id}.json"))
    return {name: index for index, name in enumerate(sorted(class_names))}


def _query_shape_labels(path: Path) -> list[str]:
    payload = _load_labelme_payload(path)
    labels: list[str] = []
    for shape in _shape_list(payload):
        labels.append(str(shape["label"]))
    return labels


def _scene_shape_class_names(path: Path) -> list[str]:
    payload = _load_labelme_payload(path)
    labels: list[str] = []
    for shape in _shape_list(payload):
        _, class_name = _parse_scene_label(str(shape["label"]))
        labels.append(class_name)
    return labels


def _load_group1_query_targets(path: Path, *, class_map: dict[str, int]) -> list[dict[str, object]]:
    payload = _load_labelme_payload(path)
    targets: list[dict[str, object]] = []
    for shape in _shape_list(payload):
        label = str(shape["label"])
        bbox = _shape_bbox(shape)
        targets.append(
            {
                "order": 0,
                "class": label,
                "class_id": class_map[label],
                "bbox": bbox,
                "center": _bbox_center(bbox),
            }
        )
    targets.sort(key=lambda item: (int(item["center"][0]), int(item["center"][1])))
    for order, target in enumerate(targets, start=1):
        target["order"] = order
    return targets


def _load_group1_scene_targets(path: Path, *, class_map: dict[str, int]) -> list[dict[str, object]]:
    payload = _load_labelme_payload(path)
    targets: list[dict[str, object]] = []
    for shape in _shape_list(payload):
        order, class_name = _parse_scene_label(str(shape["label"]))
        bbox = _shape_bbox(shape)
        targets.append(
            {
                "order": order,
                "class": class_name,
                "class_id": class_map[class_name],
                "bbox": bbox,
                "center": _bbox_center(bbox),
            }
        )
    targets.sort(key=lambda item: int(item["order"]))
    return targets


def _load_single_rectangle(path: Path, *, expected_label: str) -> list[int]:
    payload = _load_labelme_payload(path)
    shapes = _shape_list(payload)
    if len(shapes) != 1:
        raise RuntimeError(f"标注文件必须且只能包含一个矩形：{path}")
    label = str(shapes[0]["label"])
    if label != expected_label:
        raise RuntimeError(f"标注文件标签非法：{path}，期望 {expected_label}，实际 {label}")
    return _shape_bbox(shapes[0])


def _load_labelme_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"标注文件格式非法：{path}")
    return payload


def _shape_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_shapes = payload.get("shapes")
    if not isinstance(raw_shapes, list):
        raise RuntimeError("标注文件缺少 shapes")
    shapes: list[dict[str, Any]] = []
    for item in raw_shapes:
        if isinstance(item, dict):
            shapes.append(item)
    return shapes


def _shape_bbox(shape: dict[str, Any]) -> list[int]:
    points = shape.get("points")
    if not isinstance(points, list) or len(points) < 2:
        raise RuntimeError("矩形标注缺少 points")
    x_values = [float(point[0]) for point in points if isinstance(point, list) and len(point) >= 2]
    y_values = [float(point[1]) for point in points if isinstance(point, list) and len(point) >= 2]
    if len(x_values) < 2 or len(y_values) < 2:
        raise RuntimeError("矩形标注 points 非法")
    x1 = int(round(min(x_values)))
    y1 = int(round(min(y_values)))
    x2 = int(round(max(x_values)))
    y2 = int(round(max(y_values)))
    return [x1, y1, x2, y2]


def _bbox_center(bbox: list[int]) -> list[int]:
    return [int(round((bbox[0] + bbox[2]) / 2)), int(round((bbox[1] + bbox[3]) / 2))]


def _parse_scene_label(label: str) -> tuple[int, str]:
    prefix, separator, suffix = label.partition("|")
    if separator != "|" or not prefix.isdigit() or not suffix.strip():
        raise RuntimeError(f"group1 scene 标签必须是 NN|class 形式，实际：{label}")
    return int(prefix), suffix.strip()


def _find_image_for_sample(directory: Path, sample_id: str) -> Path:
    candidates = sorted(path for path in directory.glob(f"{sample_id}.*") if path.suffix.lower() != ".json")
    if not candidates:
        raise RuntimeError(f"未找到样本图片：{directory / sample_id}")
    return candidates[0]


def _yolo_bbox_line(*, class_id: int, bbox: list[int], image_width: int, image_height: int) -> str:
    x1, y1, x2, y2 = [int(value) for value in bbox]
    bbox_width = max(1, x2 - x1)
    bbox_height = max(1, y2 - y1)
    center_x = x1 + (bbox_width / 2.0)
    center_y = y1 + (bbox_height / 2.0)
    return " ".join(
        [
            str(class_id),
            _fmt_float(center_x / image_width),
            _fmt_float(center_y / image_height),
            _fmt_float(bbox_width / image_width),
            _fmt_float(bbox_height / image_height),
        ]
    )


def _fmt_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")

