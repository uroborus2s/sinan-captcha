"""Dataset helpers for the paired-input group2 contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from common.jsonl import read_jsonl
from dataset.validation import validate_group2_row


@dataclass(frozen=True)
class Group2DatasetConfig:
    path: Path
    task: str
    format: str
    splits: dict[str, Path]

    @property
    def root(self) -> Path:
        return self.path.parent


def load_group2_dataset_config(path: Path) -> Group2DatasetConfig:
    if not path.exists():
        raise RuntimeError(f"未找到 group2 数据集配置文件：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"group2 数据集配置文件格式非法：{path}")

    task = str(payload.get("task", ""))
    data_format = str(payload.get("format", ""))
    if task != "group2":
        raise RuntimeError(f"group2 数据集配置文件 task 非法：{path}")
    if data_format != "sinan.group2.paired.v1":
        raise RuntimeError(
            f"group2 数据集配置文件 format 非法：{data_format or '<empty>'}，"
            "当前只支持 sinan.group2.paired.v1。"
        )

    raw_splits = payload.get("splits")
    if not isinstance(raw_splits, dict):
        raise RuntimeError(f"group2 数据集配置文件缺少 splits：{path}")

    splits: dict[str, Path] = {}
    for split_name in ("train", "val", "test"):
        raw_value = raw_splits.get(split_name)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise RuntimeError(f"group2 数据集配置文件缺少 splits.{split_name}：{path}")
        splits[split_name] = resolve_group2_path(path.parent, Path(raw_value))

    return Group2DatasetConfig(path=path, task=task, format=data_format, splits=splits)


def resolve_group2_source(config: Group2DatasetConfig, source: Path | None, *, split: str = "val") -> Path:
    if source is None:
        return config.splits[split]
    if source.is_dir():
        candidate = source / "labels.jsonl"
        if candidate.exists():
            return candidate
        raise RuntimeError(f"group2 预测输入目录缺少 labels.jsonl：{source}")
    return source


def load_group2_rows(config: Group2DatasetConfig, source: Path | None, *, split: str = "val") -> list[dict[str, Any]]:
    source_path = resolve_group2_source(config, source, split=split)
    rows = read_jsonl(source_path)
    return [validate_group2_row(row) for row in rows]


def resolve_group2_path(root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()

