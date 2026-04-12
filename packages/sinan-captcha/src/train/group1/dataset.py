"""Dataset helpers for the group1 instance-matching pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from common.jsonl import read_jsonl
from dataset.validation import validate_group1_row

INSTANCE_MATCHING_FORMAT = "sinan.group1.instance_matching.v1"
YOLO_DETECT_FORMAT = "yolo.detect.v1"
EMBEDDING_FORMAT = "sinan.group1.embedding.v1"
EVAL_FORMAT = "sinan.group1.eval.v1"


@dataclass(frozen=True)
class Group1ComponentConfig:
    format: str
    dataset_yaml: Path


@dataclass(frozen=True)
class Group1EmbeddingConfig:
    format: str
    queries_dir: Path
    candidates_dir: Path
    pairs_jsonl: Path
    triplets_jsonl: Path


@dataclass(frozen=True)
class Group1EvalConfig:
    format: str
    labels_jsonl: Path


@dataclass(frozen=True)
class Group1DatasetConfig:
    path: Path
    task: str
    format: str
    splits: dict[str, Path]
    query_component: Group1ComponentConfig | None
    proposal_component: Group1ComponentConfig
    embedding: Group1EmbeddingConfig | None
    eval: Group1EvalConfig | None

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def proposal_dataset_yaml(self) -> Path:
        return self.proposal_component.dataset_yaml

    @property
    def query_dataset_yaml(self) -> Path | None:
        if self.query_component is None:
            return None
        return self.query_component.dataset_yaml

    @property
    def embedding_pairs_path(self) -> Path | None:
        if self.embedding is None:
            return None
        return self.embedding.pairs_jsonl

    @property
    def eval_labels_path(self) -> Path | None:
        if self.eval is None:
            return None
        return self.eval.labels_jsonl

    @property
    def is_instance_matching(self) -> bool:
        return self.format == INSTANCE_MATCHING_FORMAT


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
    if data_format != INSTANCE_MATCHING_FORMAT:
        raise RuntimeError(
            f"group1 数据集配置文件 format 非法：{data_format or '<empty>'}，"
            f"当前只支持 {INSTANCE_MATCHING_FORMAT}。"
        )

    splits = _load_group1_splits(payload, path)
    query_component = _load_optional_named_component(payload, path, field="query_detector")
    proposal_component = _load_named_component(payload, path, field="proposal_detector")
    embedding = _load_embedding_config(payload, path)
    eval_config = _load_eval_config(payload, path)

    return Group1DatasetConfig(
        path=path,
        task=task,
        format=data_format,
        splits=splits,
        query_component=query_component,
        proposal_component=proposal_component,
        embedding=embedding,
        eval=eval_config,
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


def _load_group1_splits(payload: dict[str, Any], path: Path) -> dict[str, Path]:
    raw_splits = payload.get("splits")
    if not isinstance(raw_splits, dict):
        raise RuntimeError(f"group1 数据集配置文件缺少 splits：{path}")
    splits: dict[str, Path] = {}
    for split_name in ("train", "val", "test"):
        raw_value = raw_splits.get(split_name)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise RuntimeError(f"group1 数据集配置文件缺少 splits.{split_name}：{path}")
        splits[split_name] = resolve_group1_path(path.parent, Path(raw_value))
    return splits


def _load_named_component(payload: dict[str, Any], path: Path, *, field: str) -> Group1ComponentConfig:
    raw_component = payload.get(field)
    if not isinstance(raw_component, dict):
        raise RuntimeError(f"group1 数据集配置文件缺少 {field}：{path}")
    return _parse_component(raw_component, path, component_name=field)


def _load_optional_named_component(payload: dict[str, Any], path: Path, *, field: str) -> Group1ComponentConfig | None:
    raw_component = payload.get(field)
    if raw_component is None:
        return None
    if not isinstance(raw_component, dict):
        raise RuntimeError(f"group1 数据集配置文件字段 {field} 格式非法：{path}")
    return _parse_component(raw_component, path, component_name=field)


def _parse_component(raw_component: dict[str, Any], path: Path, *, component_name: str) -> Group1ComponentConfig:
    component_format = str(raw_component.get("format", ""))
    dataset_yaml = raw_component.get("dataset_yaml")
    if component_format != YOLO_DETECT_FORMAT:
        raise RuntimeError(
            f"group1 组件 {component_name} 的 format 非法：{component_format or '<empty>'}，"
            f"当前只支持 {YOLO_DETECT_FORMAT}。"
        )
    if not isinstance(dataset_yaml, str) or not dataset_yaml.strip():
        raise RuntimeError(f"group1 数据集配置文件缺少 {component_name}.dataset_yaml：{path}")
    return Group1ComponentConfig(
        format=component_format,
        dataset_yaml=resolve_group1_path(path.parent, Path(dataset_yaml)),
    )


def _load_embedding_config(payload: dict[str, Any], path: Path) -> Group1EmbeddingConfig:
    raw_embedding = payload.get("embedding")
    if not isinstance(raw_embedding, dict):
        raise RuntimeError(f"group1 数据集配置文件缺少 embedding：{path}")
    embedding_format = str(raw_embedding.get("format", ""))
    if embedding_format != EMBEDDING_FORMAT:
        raise RuntimeError(
            f"group1 embedding.format 非法：{embedding_format or '<empty>'}，"
            f"当前只支持 {EMBEDDING_FORMAT}。"
        )
    queries_dir = _require_relative_path(raw_embedding, path, field="embedding.queries_dir")
    candidates_dir = _require_relative_path(raw_embedding, path, field="embedding.candidates_dir")
    pairs_jsonl = _require_relative_path(raw_embedding, path, field="embedding.pairs_jsonl")
    triplets_jsonl = _require_relative_path(raw_embedding, path, field="embedding.triplets_jsonl")
    return Group1EmbeddingConfig(
        format=embedding_format,
        queries_dir=queries_dir,
        candidates_dir=candidates_dir,
        pairs_jsonl=pairs_jsonl,
        triplets_jsonl=triplets_jsonl,
    )


def _load_eval_config(payload: dict[str, Any], path: Path) -> Group1EvalConfig:
    raw_eval = payload.get("eval")
    if not isinstance(raw_eval, dict):
        raise RuntimeError(f"group1 数据集配置文件缺少 eval：{path}")
    eval_format = str(raw_eval.get("format", ""))
    if eval_format != EVAL_FORMAT:
        raise RuntimeError(
            f"group1 eval.format 非法：{eval_format or '<empty>'}，"
            f"当前只支持 {EVAL_FORMAT}。"
        )
    labels_jsonl = _require_relative_path(raw_eval, path, field="eval.labels_jsonl")
    return Group1EvalConfig(
        format=eval_format,
        labels_jsonl=labels_jsonl,
    )
def _require_relative_path(raw_payload: dict[str, Any], path: Path, *, field: str) -> Path:
    key = field.split(".")[-1]
    raw_value = raw_payload.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise RuntimeError(f"group1 数据集配置文件缺少 {field}：{path}")
    return resolve_group1_path(path.parent, Path(raw_value))
