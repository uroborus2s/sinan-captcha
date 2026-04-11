"""Offline autolabel flows for reviewed-seed and pseudo-auto datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import shutil

from common.images import get_image_size
from common.jsonl import read_jsonl, write_jsonl
from dataset.validation import (
    get_group1_scene_targets,
    get_group2_query_image,
    get_group2_scene_image,
    get_group2_target,
    set_group1_scene_targets,
    set_group2_target,
    validate_group1_row,
    validate_group2_row,
)


@dataclass(frozen=True)
class AutolabelRequest:
    task: str
    mode: str
    input_dir: Path
    output_dir: Path
    limit: int | None = None
    jitter_pixels: int = 4


@dataclass(frozen=True)
class AutolabelResult:
    task: str
    mode: str
    output_dir: Path
    labels_path: Path
    processed_count: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["output_dir"] = str(self.output_dir)
        payload["labels_path"] = str(self.labels_path)
        return payload


def run_autolabel(request: AutolabelRequest) -> AutolabelResult:
    rows = read_jsonl(request.input_dir / "labels.jsonl")
    selected_rows = _apply_limit(rows, request.limit)
    output_rows: list[dict[str, object]] = []

    for raw_row in selected_rows:
        copied_row = dict(raw_row)
        if request.task == "group1":
            row = validate_group1_row(copied_row)
            transformed = _transform_group1_row(row, request)
        elif request.task == "group2":
            row = validate_group2_row(copied_row)
            transformed = _transform_group2_row(row, request)
        else:
            raise ValueError(f"unsupported autolabel task: {request.task}")

        if request.task == "group1":
            _copy_asset(request.input_dir, request.output_dir, Path(str(transformed["query_image"])))
            _copy_asset(request.input_dir, request.output_dir, Path(str(transformed["scene_image"])))
        else:
            _copy_asset(request.input_dir, request.output_dir, Path(get_group2_query_image(transformed)))
            _copy_asset(request.input_dir, request.output_dir, Path(get_group2_scene_image(transformed)))
        output_rows.append(transformed)

    labels_path = request.output_dir / "labels.jsonl"
    write_jsonl(labels_path, output_rows)
    return AutolabelResult(
        task=request.task,
        mode=request.mode,
        output_dir=request.output_dir,
        labels_path=labels_path,
        processed_count=len(output_rows),
    )


def _apply_limit(rows: list[dict[str, object]], limit: int | None) -> list[dict[str, object]]:
    ordered = sorted(rows, key=lambda row: str(row["sample_id"]))
    if limit is None or limit >= len(ordered):
        return ordered
    return ordered[:limit]


def _transform_group1_row(row: dict[str, object], request: AutolabelRequest) -> dict[str, object]:
    if request.mode == "seed-review":
        result = dict(row)
        result["label_source"] = "reviewed"
        return result
    if request.mode != "warmup-auto":
        raise ValueError(f"unsupported group1 autolabel mode: {request.mode}")

    scene_path = request.input_dir / str(row["scene_image"])
    image_width, image_height = get_image_size(scene_path)
    result = dict(row)
    result = set_group1_scene_targets(
        result,
        [
        _perturb_object(
            obj,
            sample_id=str(row["sample_id"]),
            image_width=image_width,
            image_height=image_height,
            jitter_pixels=request.jitter_pixels,
            salt=f"target:{index}",
        )
        for index, obj in enumerate(get_group1_scene_targets(row))
        ],
    )
    result["distractors"] = [
        _perturb_object(
            obj,
            sample_id=str(row["sample_id"]),
            image_width=image_width,
            image_height=image_height,
            jitter_pixels=request.jitter_pixels,
            salt=f"distractor:{index}",
        )
        for index, obj in enumerate(row["distractors"])
    ]
    result["label_source"] = "auto"
    return result


def _transform_group2_row(row: dict[str, object], request: AutolabelRequest) -> dict[str, object]:
    if request.mode != "rule-auto":
        raise ValueError(f"unsupported group2 autolabel mode: {request.mode}")

    scene_path = request.input_dir / get_group2_scene_image(row)
    image_width, image_height = get_image_size(scene_path)
    result = set_group2_target(
        row,
        _perturb_object(
            get_group2_target(row),
            sample_id=str(row["sample_id"]),
            image_width=image_width,
            image_height=image_height,
            jitter_pixels=request.jitter_pixels,
            salt="group2-target",
        ),
    )
    result["label_source"] = "auto"
    return result


def _perturb_object(
    obj: dict[str, object],
    *,
    sample_id: str,
    image_width: int,
    image_height: int,
    jitter_pixels: int,
    salt: str,
) -> dict[str, object]:
    x1, y1, x2, y2 = [int(value) for value in obj["bbox"]]
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)

    dx = _stable_offset(sample_id, salt, "dx", jitter_pixels)
    dy = _stable_offset(sample_id, salt, "dy", jitter_pixels)
    grow = _stable_offset(sample_id, salt, "grow", max(1, jitter_pixels // 2))

    new_x1 = _clamp(x1 + dx - grow, 0, image_width - 2)
    new_y1 = _clamp(y1 + dy - grow, 0, image_height - 2)
    new_x2 = _clamp(x1 + dx + width + grow, new_x1 + 1, image_width)
    new_y2 = _clamp(y1 + dy + height + grow, new_y1 + 1, image_height)

    updated = dict(obj)
    updated["bbox"] = [new_x1, new_y1, new_x2, new_y2]
    updated["center"] = [(new_x1 + new_x2) // 2, (new_y1 + new_y2) // 2]
    return updated


def _stable_offset(sample_id: str, salt: str, axis: str, magnitude: int) -> int:
    if magnitude <= 0:
        return 0
    digest = hashlib.sha256(f"{sample_id}:{salt}:{axis}".encode("utf-8")).digest()
    span = magnitude * 2 + 1
    return int(digest[0] % span) - magnitude


def _copy_asset(input_dir: Path, output_dir: Path, relative_path: Path) -> None:
    source = input_dir / relative_path
    destination = output_dir / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))
