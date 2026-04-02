"""Conversion contracts from JSONL source-of-truth files to YOLO datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from core.common.images import get_image_size
from core.common.jsonl import read_jsonl
from core.dataset.validation import (
    DatasetValidationError,
    collect_group1_classes,
    collect_group2_classes,
    get_group2_scene_image,
    get_group2_target,
    validate_group1_row,
    validate_group2_row,
)


@dataclass(frozen=True)
class ConversionRequest:
    task: str
    version: str
    source_dir: Path
    output_dir: Path
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1


def build_yolo_dataset(request: ConversionRequest) -> None:
    """Convert JSONL source-of-truth files into a YOLO dataset directory."""

    rows = read_jsonl(request.source_dir / "labels.jsonl")
    if not rows:
        raise DatasetValidationError("labels.jsonl is empty")

    if request.task == "group1":
        validated_rows = [validate_group1_row(row) for row in rows]
        class_map = collect_group1_classes(validated_rows)
    elif request.task == "group2":
        validated_rows = [validate_group2_row(row) for row in rows]
        class_map = collect_group2_classes(validated_rows)
    else:
        raise DatasetValidationError(f"unsupported task: {request.task}")

    _prepare_output_dirs(request.output_dir)

    assignments = _split_rows(validated_rows, request)
    for split_name, row in assignments:
        _write_row(request, row, split_name)

    _write_dataset_yaml(request.output_dir, class_map)


def _prepare_output_dirs(output_dir: Path) -> None:
    for split_name in ("train", "val", "test"):
        (output_dir / "images" / split_name).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split_name).mkdir(parents=True, exist_ok=True)


def _split_rows(rows: list[dict[str, object]], request: ConversionRequest) -> list[tuple[str, dict[str, object]]]:
    ordered_rows = sorted(rows, key=lambda row: str(row["sample_id"]))
    total = len(ordered_rows)
    if total == 1:
        return [("train", ordered_rows[0])]
    if total == 2:
        return [("train", ordered_rows[0]), ("val", ordered_rows[1])]

    val_count = max(1, int(round(total * request.val_ratio)))
    test_count = max(1, int(round(total * request.test_ratio)))
    train_count = total - val_count - test_count
    if train_count < 1:
        train_count = 1
        overflow = val_count + test_count - (total - 1)
        if overflow > 0:
            if test_count >= overflow:
                test_count -= overflow
            else:
                overflow -= test_count
                test_count = 0
                val_count = max(1, val_count - overflow)

    assignments: list[tuple[str, dict[str, object]]] = []
    for index, row in enumerate(ordered_rows):
        if index < train_count:
            split_name = "train"
        elif index < train_count + val_count:
            split_name = "val"
        else:
            split_name = "test"
        assignments.append((split_name, row))
    return assignments


def _write_row(request: ConversionRequest, row: dict[str, object], split_name: str) -> None:
    scene_key = str(row["scene_image"]) if request.task == "group1" else get_group2_scene_image(row)
    scene_path = request.source_dir / scene_key
    if not scene_path.exists():
        raise DatasetValidationError(f"scene image not found: {scene_path}")

    width, height = get_image_size(scene_path)
    destination_image = request.output_dir / "images" / split_name / scene_path.name
    destination_label = request.output_dir / "labels" / split_name / f"{scene_path.stem}.txt"
    shutil.copy2(scene_path, destination_image)

    if request.task == "group1":
        objects = list(row["targets"]) + list(row["distractors"])  # type: ignore[arg-type]
    else:
        objects = [get_group2_target(row)]

    lines = [_to_yolo_line(obj, width, height) for obj in objects]  # type: ignore[arg-type]
    destination_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _to_yolo_line(obj: dict[str, object], width: int, height: int) -> str:
    class_id = int(obj["class_id"])
    x1, y1, x2, y2 = [int(value) for value in obj["bbox"]]  # type: ignore[index]
    bbox_width = x2 - x1
    bbox_height = y2 - y1
    center_x = x1 + bbox_width / 2
    center_y = y1 + bbox_height / 2
    return " ".join(
        [
            str(class_id),
            _fmt(center_x / width),
            _fmt(center_y / height),
            _fmt(bbox_width / width),
            _fmt(bbox_height / height),
        ]
    )


def _write_dataset_yaml(output_dir: Path, class_map: dict[int, str]) -> None:
    lines = [
        f"path: {output_dir.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    for class_id in sorted(class_map):
        lines.append(f"  {class_id}: {class_map[class_id]}")
    (output_dir / "dataset.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")
