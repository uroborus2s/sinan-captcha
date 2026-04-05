"""Dataset helpers for the group1 two-model pipeline contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from core.common.jsonl import read_jsonl
from core.dataset.validation import validate_group1_row


@dataclass(frozen=True)
class Group1ComponentConfig:
    format: str
    dataset_yaml: Path


@dataclass(frozen=True)
class Group1DatasetConfig:
    path: Path
    task: str
    format: str
    splits: dict[str, Path]
    components: dict[str, Group1ComponentConfig]
    matcher_strategy: str
    classes: dict[int, str]

    @property
    def root(self) -> Path:
        return self.path.parent


def load_group1_dataset_config(path: Path) -> Group1DatasetConfig:
    if not path.exists():
        raise RuntimeError(f"未找到 group1 数据集配置文件：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"group1 数据集配置文件格式非法：{path}")

    task = str(payload.get("task", ""))
    data_format = str(payload.get("format", ""))
    if task != "group1":
        raise RuntimeError(f"group1 数据集配置文件 task 非法：{path}")
    if data_format != "sinan.group1.pipeline.v1":
        raise RuntimeError(
            f"group1 数据集配置文件 format 非法：{data_format or '<empty>'}，"
            "当前只支持 sinan.group1.pipeline.v1。"
        )

    raw_splits = payload.get("splits")
    if not isinstance(raw_splits, dict):
        raise RuntimeError(f"group1 数据集配置文件缺少 splits：{path}")
    splits: dict[str, Path] = {}
    for split_name in ("train", "val", "test"):
        raw_value = raw_splits.get(split_name)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise RuntimeError(f"group1 数据集配置文件缺少 splits.{split_name}：{path}")
        splits[split_name] = resolve_group1_path(path.parent, Path(raw_value))

    raw_components = payload.get("components")
    if not isinstance(raw_components, dict):
        raise RuntimeError(f"group1 数据集配置文件缺少 components：{path}")
    components: dict[str, Group1ComponentConfig] = {}
    for component_name in ("scene_detector", "query_parser"):
        raw_component = raw_components.get(component_name)
        if not isinstance(raw_component, dict):
            raise RuntimeError(f"group1 数据集配置文件缺少 components.{component_name}：{path}")
        component_format = str(raw_component.get("format", ""))
        dataset_yaml = raw_component.get("dataset_yaml")
        if component_format != "yolo.detect.v1":
            raise RuntimeError(
                f"group1 组件 {component_name} 的 format 非法：{component_format or '<empty>'}，"
                "当前只支持 yolo.detect.v1。"
            )
        if not isinstance(dataset_yaml, str) or not dataset_yaml.strip():
            raise RuntimeError(f"group1 数据集配置文件缺少 components.{component_name}.dataset_yaml：{path}")
        components[component_name] = Group1ComponentConfig(
            format=component_format,
            dataset_yaml=resolve_group1_path(path.parent, Path(dataset_yaml)),
        )

    raw_matcher = payload.get("matcher")
    matcher_strategy = ""
    if isinstance(raw_matcher, dict):
        matcher_strategy = str(raw_matcher.get("strategy", ""))
    if matcher_strategy != "ordered_class_match_v1":
        raise RuntimeError(
            f"group1 matcher.strategy 非法：{matcher_strategy or '<empty>'}，"
            "当前只支持 ordered_class_match_v1。"
        )

    raw_classes = payload.get("classes", {})
    classes: dict[int, str] = {}
    if isinstance(raw_classes, dict):
        for raw_key, raw_value in raw_classes.items():
            if not isinstance(raw_value, str) or not raw_value.strip():
                continue
            try:
                class_id = int(raw_key)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"group1 数据集 classes 含非法键：{raw_key!r}") from exc
            classes[class_id] = raw_value

    return Group1DatasetConfig(
        path=path,
        task=task,
        format=data_format,
        splits=splits,
        components=components,
        matcher_strategy=matcher_strategy,
        classes=classes,
    )


def resolve_group1_source(config: Group1DatasetConfig, source: Path | None, *, split: str = "val") -> Path:
    if source is None:
        return config.splits[split]
    if source.is_dir():
        candidate = source / "labels.jsonl"
        if candidate.exists():
            return candidate
        raise RuntimeError(f"group1 预测输入目录缺少 labels.jsonl：{source}")
    return source


def load_group1_rows(config: Group1DatasetConfig, source: Path | None, *, split: str = "val") -> list[dict[str, Any]]:
    source_path = resolve_group1_source(config, source, split=split)
    rows = read_jsonl(source_path)
    return [validate_group1_row(row) for row in rows]


def resolve_group1_path(root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()
