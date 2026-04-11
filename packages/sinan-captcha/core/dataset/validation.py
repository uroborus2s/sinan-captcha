"""Validation helpers for JSONL source-of-truth files."""

from __future__ import annotations

from typing import Any


class DatasetValidationError(ValueError):
    """Raised when a JSONL sample does not satisfy the project contract."""


def validate_group1_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_group1_aliases(row)
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

    for target in query_items:
        _validate_group1_object(target, require_order=True)
    for target in scene_targets:
        _validate_group1_object(target, require_order=True)
    for distractor in distractors:
        _validate_group1_object(distractor, require_order=False)

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


def collect_group1_classes(rows: list[dict[str, Any]]) -> dict[int, str]:
    classes: dict[int, str] = {}
    for row in rows:
        normalized = _normalize_group1_aliases(row)
        for obj in normalized["query_targets"] + normalized["scene_targets"] + normalized["distractors"]:
            class_id = obj.get("class_id")
            class_name = obj.get("class")
            if not isinstance(class_id, int):
                continue
            if not isinstance(class_name, str) or not class_name.strip():
                continue
            classes[int(class_id)] = class_name
    return classes


def get_group1_query_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = _normalize_group1_aliases(row)
    return list(normalized["query_items"])


def get_group1_query_targets(row: dict[str, Any]) -> list[dict[str, Any]]:
    return get_group1_query_items(row)


def get_group1_scene_targets(row: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = _normalize_group1_aliases(row)
    return list(normalized["scene_targets"])


def set_group1_scene_targets(row: dict[str, Any], targets: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = _normalize_group1_aliases(row)
    normalized["scene_targets"] = targets
    normalized["targets"] = targets
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


def _normalize_group1_aliases(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if "query_items" not in normalized and "query_targets" in normalized:
        normalized["query_items"] = normalized["query_targets"]
    if "query_targets" not in normalized and "query_items" in normalized:
        normalized["query_targets"] = normalized["query_items"]
    if "scene_targets" not in normalized and "targets" in normalized:
        normalized["scene_targets"] = normalized["targets"]
    if "targets" not in normalized and "scene_targets" in normalized:
        normalized["targets"] = normalized["scene_targets"]
    return normalized


def _validate_group1_object(obj: dict[str, Any], *, require_order: bool) -> None:
    required = ["bbox", "center"]
    if require_order:
        required.insert(0, "order")
    _require_fields(obj, required)

    _validate_bbox_and_center(obj)
    identity_fields = ("asset_id", "template_id", "variant_id")
    has_any_identity = any(field in obj for field in identity_fields)
    has_all_identity = all(isinstance(obj.get(field), str) and str(obj.get(field)).strip() for field in identity_fields)
    has_legacy_class = isinstance(obj.get("class"), str) and str(obj.get("class")).strip() and isinstance(obj.get("class_id"), int)

    if has_any_identity and not has_all_identity:
        raise DatasetValidationError("group1 object must provide a complete asset_id/template_id/variant_id identity")
    if not has_all_identity and not has_legacy_class:
        raise DatasetValidationError("group1 object must provide asset identity or legacy class/class_id")
    if "class" in obj and (not isinstance(obj["class"], str) or not str(obj["class"]).strip()):
        raise DatasetValidationError("class must be a non-empty string when provided")
    if "class_id" in obj and not isinstance(obj["class_id"], int):
        raise DatasetValidationError("class_id must be an integer when provided")


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
