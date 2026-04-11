"""Validation helpers for JSONL source-of-truth files."""

from __future__ import annotations

from typing import Any


class DatasetValidationError(ValueError):
    """Raised when a JSONL sample does not satisfy the project contract."""


def validate_group1_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    required = [
        "sample_id",
        "query_image",
        "scene_image",
        "query_items",
        "scene_targets",
        "distractors",
        "label_source",
        "source_batch",
    ]
    _require_fields(normalized, required)

    query_items = normalized["query_items"]
    scene_targets = normalized["scene_targets"]
    distractors = normalized["distractors"]
    if not isinstance(query_items, list):
        raise DatasetValidationError("group1 query_items must be a list")
    if not isinstance(scene_targets, list):
        raise DatasetValidationError("group1 scene_targets must be a list")
    if not isinstance(distractors, list):
        raise DatasetValidationError("group1 distractors must be a list")
    if normalized["label_source"] == "gold":
        if not query_items:
            raise DatasetValidationError("group1 gold query_items must be a non-empty list")
        if not scene_targets:
            raise DatasetValidationError("group1 gold scene_targets must be a non-empty list")
        if len(query_items) != len(scene_targets):
            raise DatasetValidationError("group1 gold query_items and scene_targets must have the same length")

    label_source = str(normalized["label_source"])
    for target in query_items:
        _validate_group1_object(
            target,
            require_order=True,
            allow_order_bbox_only=label_source != "gold",
        )
    for target in scene_targets:
        _validate_group1_object(
            target,
            require_order=True,
            allow_order_bbox_only=label_source == "reviewed",
        )
    for distractor in distractors:
        _validate_group1_object(distractor, require_order=False, allow_order_bbox_only=False)

    return normalized


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


def get_group1_query_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    query_items = row.get("query_items")
    if not isinstance(query_items, list):
        raise DatasetValidationError("group1 query_items must be a list")
    return list(query_items)


def get_group1_scene_targets(row: dict[str, Any]) -> list[dict[str, Any]]:
    scene_targets = row.get("scene_targets")
    if not isinstance(scene_targets, list):
        raise DatasetValidationError("group1 scene_targets must be a list")
    return list(scene_targets)


def set_group1_scene_targets(row: dict[str, Any], targets: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["scene_targets"] = targets
    return normalized


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


def _validate_group1_object(
    obj: dict[str, Any],
    *,
    require_order: bool,
    allow_order_bbox_only: bool,
) -> None:
    if not isinstance(obj, dict):
        raise DatasetValidationError("group1 object must be an object")
    required = ["bbox", "center"]
    if require_order:
        required.insert(0, "order")
    _require_fields(obj, required)

    _validate_bbox_and_center(obj)
    identity_fields = ("asset_id", "template_id", "variant_id")
    has_any_identity = any(field in obj for field in identity_fields)
    has_all_identity = all(isinstance(obj.get(field), str) and str(obj.get(field)).strip() for field in identity_fields)

    if has_any_identity and not has_all_identity:
        raise DatasetValidationError("group1 object must provide a complete asset_id/template_id/variant_id identity")
    if "class" in obj or "class_id" in obj:
        raise DatasetValidationError("group1 object no longer accepts class/class_id; use class_guess only")
    if not has_all_identity and not allow_order_bbox_only:
        raise DatasetValidationError("group1 object must provide asset identity")
    if "class_guess" in obj and (not isinstance(obj["class_guess"], str) or not str(obj["class_guess"]).strip()):
        raise DatasetValidationError("class_guess must be a non-empty string when provided")


def _validate_object(obj: dict[str, Any], *, require_order: bool) -> None:
    required = ["class", "class_id", "bbox", "center"]
    if require_order:
        required.insert(0, "order")
    _require_fields(obj, required)

    _validate_bbox_and_center(obj)


def _validate_bbox_and_center(obj: dict[str, Any]) -> None:
    bbox = obj["bbox"]
    center = obj["center"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise DatasetValidationError("bbox must be a list of four integers")
    if not isinstance(center, list) or len(center) != 2:
        raise DatasetValidationError("center must be a list of two integers")
