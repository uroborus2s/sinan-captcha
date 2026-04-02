"""Validation helpers for JSONL source-of-truth files."""

from __future__ import annotations

from typing import Any


class DatasetValidationError(ValueError):
    """Raised when a JSONL sample does not satisfy the project contract."""


def validate_group1_row(row: dict[str, Any]) -> dict[str, Any]:
    required = ["sample_id", "query_image", "scene_image", "targets", "distractors", "label_source", "source_batch"]
    _require_fields(row, required)

    targets = row["targets"]
    distractors = row["distractors"]
    if not isinstance(targets, list) or not targets:
        raise DatasetValidationError("group1 targets must be a non-empty list")
    if not isinstance(distractors, list):
        raise DatasetValidationError("group1 distractors must be a list")

    for target in targets:
        _validate_object(target, require_order=True)
    for distractor in distractors:
        _validate_object(distractor, require_order=False)

    return row


def validate_group2_row(row: dict[str, Any]) -> dict[str, Any]:
    if "target_gap" in row or "master_image" in row or "tile_image" in row:
        required = [
            "sample_id",
            "master_image",
            "tile_image",
            "target_gap",
            "tile_bbox",
            "offset_x",
            "offset_y",
            "label_source",
            "source_batch",
        ]
        _require_fields(row, required)
        target = row["target_gap"]
        tile_bbox = row["tile_bbox"]
        if not isinstance(tile_bbox, list) or len(tile_bbox) != 4:
            raise DatasetValidationError("tile_bbox must be a list of four integers")
    else:
        required = ["sample_id", "query_image", "scene_image", "target", "label_source", "source_batch"]
        _require_fields(row, required)
        target = row["target"]
    if not isinstance(target, dict):
        raise DatasetValidationError("group2 target must be an object")
    _validate_object(target, require_order=False)
    return row


def collect_group1_classes(rows: list[dict[str, Any]]) -> dict[int, str]:
    classes: dict[int, str] = {}
    for row in rows:
        for obj in row["targets"] + row["distractors"]:
            classes[int(obj["class_id"])] = str(obj["class"])
    return classes


def collect_group2_classes(rows: list[dict[str, Any]]) -> dict[int, str]:
    classes: dict[int, str] = {}
    for row in rows:
        target = get_group2_target(row)
        classes[int(target["class_id"])] = str(target["class"])
    return classes


def get_group2_scene_image(row: dict[str, Any]) -> str:
    if "master_image" in row:
        return str(row["master_image"])
    return str(row["scene_image"])


def get_group2_query_image(row: dict[str, Any]) -> str:
    if "tile_image" in row:
        return str(row["tile_image"])
    return str(row["query_image"])


def get_group2_target(row: dict[str, Any]) -> dict[str, Any]:
    if "target_gap" in row:
        target = row["target_gap"]
    else:
        target = row["target"]
    if not isinstance(target, dict):
        raise DatasetValidationError("group2 target must be an object")
    return target


def set_group2_target(row: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    if "target_gap" in updated:
        updated["target_gap"] = target
    else:
        updated["target"] = target
    return updated


def _require_fields(row: dict[str, Any], required: list[str]) -> None:
    for field in required:
        if field not in row:
            raise DatasetValidationError(f"missing required field: {field}")


def _validate_object(obj: dict[str, Any], *, require_order: bool) -> None:
    required = ["class", "class_id", "bbox", "center"]
    if require_order:
        required.insert(0, "order")
    _require_fields(obj, required)

    bbox = obj["bbox"]
    center = obj["center"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise DatasetValidationError("bbox must be a list of four integers")
    if not isinstance(center, list) or len(center) != 2:
        raise DatasetValidationError("center must be a list of two integers")
