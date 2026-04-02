"""Typed dataset contracts for generator output and downstream pipelines."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    def as_list(self) -> list[int]:
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass(frozen=True)
class SceneObject:
    class_name: str
    class_id: int
    bbox: BoundingBox
    center: tuple[int, int]


@dataclass(frozen=True)
class OrderedTarget(SceneObject):
    order: int


@dataclass(frozen=True)
class Group1Sample:
    sample_id: str
    query_image: str
    scene_image: str
    targets: list[OrderedTarget]
    distractors: list[SceneObject]
    label_source: str
    source_batch: str
    seed: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["targets"] = [_scene_object_to_dict(target) | {"order": target.order} for target in self.targets]
        payload["distractors"] = [_scene_object_to_dict(obj) for obj in self.distractors]
        return payload


@dataclass(frozen=True)
class Group2Sample:
    sample_id: str
    master_image: str
    tile_image: str
    target_gap: SceneObject
    tile_bbox: BoundingBox
    offset_x: int
    offset_y: int
    label_source: str
    source_batch: str
    seed: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["target_gap"] = _scene_object_to_dict(self.target_gap)
        payload["tile_bbox"] = self.tile_bbox.as_list()
        return payload


def _scene_object_to_dict(obj: SceneObject) -> dict[str, object]:
    return {
        "class": obj.class_name,
        "class_id": obj.class_id,
        "bbox": obj.bbox.as_list(),
        "center": [obj.center[0], obj.center[1]],
    }
