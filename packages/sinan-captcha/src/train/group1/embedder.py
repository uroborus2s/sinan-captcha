"""Metric-learning icon embedder for group1 instance matching."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import time
from typing import Any, Callable

from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset

from auto_train import embedder_review_protocol
from common.jsonl import read_jsonl, write_jsonl
from train.group1.dataset import Group1DatasetConfig, resolve_group1_path

ICON_EMBEDDER_ARCHITECTURE_VERSION = 2
DEFAULT_EMBEDDING_DIM = 128
DEFAULT_RECALL_K_VALUES = (1, 3)
DEFAULT_EVAL_EMBED_BATCH_SIZE = 128
DEFAULT_EARLY_STOP_MIN_EPOCHS = 12
DEFAULT_EARLY_STOP_PATIENCE = 10
DEFAULT_EARLY_STOP_MIN_DELTA = 0.001
DEFAULT_LEARNING_RATE = 3e-4
DEFAULT_TRIPLET_MARGIN = 0.25
DEFAULT_TRIPLET_LOSS_WEIGHT = 0.5
DEFAULT_CONTRASTIVE_LOSS_WEIGHT = 1.0
DEFAULT_CONTRASTIVE_TEMPERATURE = 0.07
ZERO_TRIPLET_LOSS_EPS = 1e-8
ZERO_TRIPLET_GUARDRAIL_MAX_EXACT_RECALL_AT_1 = 0.10
ZERO_TRIPLET_GUARDRAIL_MIN_POSITIVE_RANK_MEAN = 50.0
HARD_SCENE_EXACT_PLATEAU_WINDOW = 3
HARD_SCENE_EXACT_PLATEAU_MAX_EXACT_RECALL_AT_1 = 0.02
HARD_SCENE_EXACT_PLATEAU_MAX_EXACT_SPREAD = 0.0025
HARD_SCENE_EXACT_PLATEAU_MIN_SCENE_RECALL_AT_1 = 0.80
HARD_SCENE_EXACT_PLATEAU_MIN_POSITIVE_RANK_MEAN = 200.0
HARD_SCENE_EXACT_PLATEAU_MAX_TRIPLET_LOSS = 1e-3
HARD_SCENE_EXACT_PLATEAU_MIN_SCENE_EXACT_GAP_RATE = 0.75
HARD_SCENE_EXACT_PLATEAU_MIN_SAME_TEMPLATE_CONFUSION_RATE = 0.40
DEFAULT_FAILURE_AUDIT_SAMPLE_LIMIT = 12


@dataclass(frozen=True)
class IconEmbedderTrainingResult:
    run_dir: Path
    weights_dir: Path
    best_checkpoint: Path
    last_checkpoint: Path
    summary_path: Path
    metrics: dict[str, float | None]
    sample_count: int
    review: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("run_dir", "weights_dir", "best_checkpoint", "last_checkpoint", "summary_path"):
            payload[key] = str(payload[key])
        return payload


class ResidualBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        if in_channels == out_channels:
            self.shortcut = nn.Identity()
        else:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False),
                nn.BatchNorm2d(out_channels),
            )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        residual = self.shortcut(inputs)
        outputs = self.conv1(inputs)
        outputs = self.bn1(outputs)
        outputs = F.relu(outputs, inplace=True)
        outputs = self.conv2(outputs)
        outputs = self.bn2(outputs)
        outputs = outputs + residual
        return F.relu(outputs, inplace=True)


class IconEmbedder(nn.Module):
    """Residual CNN that maps icon crops to L2-normalized retrieval embeddings."""

    def __init__(self, embedding_dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim
        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )
        self.features = nn.Sequential(
            ResidualBlock(32, 32),
            nn.MaxPool2d(kernel_size=2),
            ResidualBlock(32, 64),
            nn.MaxPool2d(kernel_size=2),
            ResidualBlock(64, 128),
            nn.MaxPool2d(kernel_size=2),
            ResidualBlock(128, 128),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.projection = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(p=0.1),
            nn.Linear(128, embedding_dim),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.stem(inputs)
        features = self.features(features)
        return F.normalize(self.projection(features), dim=1)


@dataclass(frozen=True)
class IconEmbedderRuntime:
    checkpoint_path: Path
    model: IconEmbedder
    image_size: int
    device: torch.device

    def embed_crop(self, image_path: Path, target: dict[str, Any]) -> list[float]:
        self.model.eval()
        with torch.no_grad():
            tensor = _load_target_crop_tensor(image_path, target, self.image_size).unsqueeze(0).to(self.device)
            vector = self.model(tensor).detach().cpu().flatten().tolist()
        return [float(value) for value in vector]


def load_icon_embedder_runtime(checkpoint_path: Path, *, device_name: str = "cpu") -> IconEmbedderRuntime:
    device = _resolve_device(device_name)
    checkpoint = _load_checkpoint(checkpoint_path, device)
    embedding_dim = int(checkpoint.get("embedding_dim", DEFAULT_EMBEDDING_DIM))
    image_size = int(checkpoint.get("imgsz", 64))
    model = IconEmbedder(embedding_dim=embedding_dim).to(device)
    try:
        model.load_state_dict(checkpoint["model_state"])
    except RuntimeError as exc:
        checkpoint_version = int(checkpoint.get("architecture_version", 1))
        raise RuntimeError(
            "group1 icon embedder 检查点与当前模型结构不兼容："
            f"{checkpoint_path} (checkpoint_version={checkpoint_version}, current_version={ICON_EMBEDDER_ARCHITECTURE_VERSION})。"
            "请改用 fresh 重新训练 icon-embedder。"
        ) from exc
    model.eval()
    return IconEmbedderRuntime(
        checkpoint_path=checkpoint_path,
        model=model,
        image_size=image_size,
        device=device,
    )


class Group1TripletDataset(Dataset[dict[str, Any]]):
    def __init__(self, dataset_root: Path, records: list[dict[str, Any]], image_size: int) -> None:
        self.dataset_root = dataset_root
        self.records = records
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        anchor_path = resolve_group1_path(self.dataset_root, Path(str(record["anchor_image"])))
        positive_path = resolve_group1_path(self.dataset_root, Path(str(record["positive_image"])))
        negative_path = resolve_group1_path(self.dataset_root, Path(str(record["negative_image"])))
        return {
            "anchor": _load_crop_tensor(anchor_path, self.image_size),
            "positive": _load_crop_tensor(positive_path, self.image_size),
            "negative": _load_crop_tensor(negative_path, self.image_size),
            "metadata": {
                "sample_id": str(record["sample_id"]),
                "anchor_image": str(record["anchor_image"]),
                "positive_image": str(record["positive_image"]),
                "negative_image": str(record["negative_image"]),
                "anchor_identity": _object_identity(record.get("anchor")),
                "positive_identity": _object_identity(record.get("positive")),
                "negative_identity": _object_identity(record.get("negative")),
                "negative_role": str(record.get("negative_role", "")),
            },
        }


def load_embedding_triplets(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    required = [
        "split",
        "sample_id",
        "anchor_image",
        "positive_image",
        "negative_image",
        "anchor",
        "positive",
        "negative",
    ]
    for row in rows:
        for field in required:
            if field not in row:
                raise RuntimeError(f"group1 embedding triplet 缺少字段 {field}: {path}")
        for image_field in ("anchor_image", "positive_image", "negative_image"):
            if not isinstance(row[image_field], str) or not str(row[image_field]).strip():
                raise RuntimeError(f"group1 embedding triplet {image_field} 必须是非空字符串: {path}")
    return rows


def evaluate_retrieval(
    *,
    query_embeddings: dict[str, list[float]],
    candidate_embeddings: dict[str, list[float]],
    positives: dict[str, str],
    scene_candidates_by_query: dict[str, list[str]] | None = None,
    query_metadata: dict[str, dict[str, Any]] | None = None,
    candidate_metadata: dict[str, dict[str, Any]] | None = None,
    k_values: tuple[int, ...] = DEFAULT_RECALL_K_VALUES,
) -> dict[str, float | None]:
    metrics, _ = evaluate_retrieval_with_audit(
        query_embeddings=query_embeddings,
        candidate_embeddings=candidate_embeddings,
        positives=positives,
        scene_candidates_by_query=scene_candidates_by_query,
        query_metadata=query_metadata,
        candidate_metadata=candidate_metadata,
        k_values=k_values,
        sample_limit=0,
    )
    return metrics


def evaluate_retrieval_with_audit(
    *,
    query_embeddings: dict[str, list[float]],
    candidate_embeddings: dict[str, list[float]],
    positives: dict[str, str],
    scene_candidates_by_query: dict[str, list[str]] | None = None,
    query_metadata: dict[str, dict[str, Any]] | None = None,
    candidate_metadata: dict[str, dict[str, Any]] | None = None,
    k_values: tuple[int, ...] = DEFAULT_RECALL_K_VALUES,
    sample_limit: int = DEFAULT_FAILURE_AUDIT_SAMPLE_LIMIT,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    valid_queries = [
        query_id
        for query_id, positive_id in positives.items()
        if query_id in query_embeddings and positive_id in candidate_embeddings
    ]
    metrics: dict[str, float | None] = {}
    failure_audit: dict[str, Any] = _build_retrieval_failure_audit(
        valid_queries=[],
        failure_rows=[],
        sample_limit=DEFAULT_FAILURE_AUDIT_SAMPLE_LIMIT,
    )
    exact_hits_by_k = {k: 0 for k in k_values}
    identity_hits_by_k = {k: 0 for k in k_values}
    positive_ranks: list[int] = []
    top1_error_scene_target = 0
    top1_error_distractor = 0
    top1_error_false_positive = 0
    top1_error_other = 0
    same_template_top1_error = 0
    failure_rows: list[dict[str, Any]] = []
    for k in k_values:
        if not valid_queries:
            metrics[f"embedding_recall_at_{k}"] = None
            metrics[f"embedding_identity_recall_at_{k}"] = None
    if not valid_queries:
        metrics["embedding_positive_rank_mean"] = None
        metrics["embedding_positive_rank_median"] = None
        metrics["embedding_top1_error_scene_target_rate"] = None
        metrics["embedding_top1_error_distractor_rate"] = None
        metrics["embedding_top1_error_false_positive_rate"] = None
        metrics["embedding_top1_error_other_rate"] = None
        metrics["embedding_same_template_top1_error_rate"] = None
        return metrics, _build_retrieval_failure_audit(
            valid_queries=valid_queries,
            failure_rows=failure_rows,
            sample_limit=sample_limit,
        )

    for query_id in valid_queries:
        positive_id = positives[query_id]
        ranked = sorted(
            candidate_embeddings,
            key=lambda candidate_id: _cosine_similarity(
                query_embeddings[query_id],
                candidate_embeddings[candidate_id],
            ),
            reverse=True,
        )
        positive_rank = ranked.index(positive_id) + 1
        positive_ranks.append(positive_rank)
        expected_identity = _retrieval_identity(
            (candidate_metadata or {}).get(positive_id),
            fallback=(query_metadata or {}).get(query_id),
        )
        for k in k_values:
            top_k = ranked[:k]
            if positive_id in top_k:
                exact_hits_by_k[k] += 1
            if expected_identity and any(
                _retrieval_identity((candidate_metadata or {}).get(candidate_id)) == expected_identity
                for candidate_id in top_k
            ):
                identity_hits_by_k[k] += 1
        top1_id = ranked[0]
        top1_similarity = _cosine_similarity(query_embeddings[query_id], candidate_embeddings[top1_id])
        positive_similarity = _cosine_similarity(query_embeddings[query_id], candidate_embeddings[positive_id])
        if top1_id == positive_id:
            continue
        top1_meta = (candidate_metadata or {}).get(top1_id)
        top1_role = str((top1_meta or {}).get("role", ""))
        if top1_role.startswith("scene_target"):
            top1_error_scene_target += 1
        elif top1_role.startswith("distractor"):
            top1_error_distractor += 1
        elif top1_role.startswith("false_positive"):
            top1_error_false_positive += 1
        else:
            top1_error_other += 1
        positive_meta = (candidate_metadata or {}).get(positive_id)
        positive_template = _retrieval_template_id(positive_meta)
        top1_template = _retrieval_template_id(top1_meta)
        top1_identity = _retrieval_identity(top1_meta)
        same_template_confusion = bool(positive_template and positive_template == top1_template)
        if same_template_confusion:
            same_template_top1_error += 1
        scene_positive_rank: int | None = None
        scene_top1_id: str | None = None
        top1_in_scene: bool | None = None
        if scene_candidates_by_query is not None:
            scene_candidates = [
                candidate_id
                for candidate_id in scene_candidates_by_query.get(query_id, [])
                if candidate_id in candidate_embeddings
            ]
            if positive_id in scene_candidates:
                scene_ranked = sorted(
                    scene_candidates,
                    key=lambda candidate_id: _cosine_similarity(
                        query_embeddings[query_id],
                        candidate_embeddings[candidate_id],
                    ),
                    reverse=True,
                )
                scene_positive_rank = scene_ranked.index(positive_id) + 1
                scene_top1_id = scene_ranked[0]
                top1_in_scene = top1_id in scene_candidates
        same_identity_confusion = bool(expected_identity and top1_identity == expected_identity)
        scene_exact_gap = scene_positive_rank == 1 and positive_rank > 1
        failure_rows.append(
            {
                "query_id": query_id,
                "positive_id": positive_id,
                "top1_id": top1_id,
                "positive_rank": positive_rank,
                "scene_positive_rank": scene_positive_rank,
                "scene_top1_id": scene_top1_id,
                "top1_in_scene": top1_in_scene,
                "top1_role": top1_role or "other",
                "expected_identity": expected_identity,
                "top1_identity": top1_identity,
                "positive_template_id": positive_template,
                "top1_template_id": top1_template,
                "positive_similarity": round(float(positive_similarity), 6),
                "top1_similarity": round(float(top1_similarity), 6),
                "scene_exact_gap": scene_exact_gap,
                "same_identity_confusion": same_identity_confusion,
                "same_template_confusion": same_template_confusion,
                "error_reason": _retrieval_failure_reason(
                    top1_role=top1_role,
                    scene_exact_gap=scene_exact_gap,
                    same_identity_confusion=same_identity_confusion,
                    same_template_confusion=same_template_confusion,
                ),
            }
        )

    for k in k_values:
        metrics[f"embedding_recall_at_{k}"] = exact_hits_by_k[k] / len(valid_queries)
        metrics[f"embedding_identity_recall_at_{k}"] = identity_hits_by_k[k] / len(valid_queries)
    metrics["embedding_positive_rank_mean"] = sum(positive_ranks) / len(positive_ranks)
    metrics["embedding_positive_rank_median"] = _median(positive_ranks)
    metrics["embedding_top1_error_scene_target_rate"] = top1_error_scene_target / len(valid_queries)
    metrics["embedding_top1_error_distractor_rate"] = top1_error_distractor / len(valid_queries)
    metrics["embedding_top1_error_false_positive_rate"] = top1_error_false_positive / len(valid_queries)
    metrics["embedding_top1_error_other_rate"] = top1_error_other / len(valid_queries)
    metrics["embedding_same_template_top1_error_rate"] = same_template_top1_error / len(valid_queries)
    if scene_candidates_by_query is not None:
        metrics.update(
            _evaluate_scene_retrieval(
                query_embeddings=query_embeddings,
                candidate_embeddings=candidate_embeddings,
                positives=positives,
                scene_candidates_by_query=scene_candidates_by_query,
                k_values=k_values,
            )
        )
    return metrics, _build_retrieval_failure_audit(
        valid_queries=valid_queries,
        failure_rows=failure_rows,
        sample_limit=sample_limit,
    )


def train_icon_embedder(
    *,
    dataset_config: Group1DatasetConfig,
    run_dir: Path,
    model_path: Path | None,
    epochs: int,
    batch_size: int,
    image_size: int,
    device_name: str,
    resume: bool,
    early_stopping_min_epochs: int = DEFAULT_EARLY_STOP_MIN_EPOCHS,
    early_stopping_patience: int = DEFAULT_EARLY_STOP_PATIENCE,
    early_stopping_min_delta: float = DEFAULT_EARLY_STOP_MIN_DELTA,
    review_callback: Callable[[embedder_review_protocol.EmbedderReviewContext], embedder_review_protocol.EmbedderReviewRecord]
    | None = None,
    review_stage: str = "TRAIN_EMBEDDER_BASE",
    review_study_name: str = "standalone",
    review_task: str = "group1",
    review_trial_id: str | None = None,
    review_train_name: str | None = None,
    review_min_epochs: int = embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_MIN_EPOCHS,
    review_window: int = embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_WINDOW,
    review_rebuild_count: int = 0,
    interim_trial_dir: Path | None = None,
    interim_primary_metric: str | None = None,
) -> IconEmbedderTrainingResult:
    if not dataset_config.is_instance_matching or dataset_config.embedding is None:
        raise RuntimeError("当前 group1 dataset.json 未提供 embedding 数据，无法训练 icon embedder。")
    records = load_embedding_triplets(dataset_config.embedding.triplets_jsonl)
    train_records = _records_for_split(records, "train")
    val_records = _records_for_split(records, "val") or _records_for_split(records, "test") or train_records
    if not train_records:
        raise RuntimeError("group1 icon embedder 训练集为空。")

    device = _resolve_device(device_name)
    _icon_embedder_log(
        (
            "start "
            f"triplets={len(train_records)} "
            f"val_triplets={len(val_records)} "
            f"batch={batch_size} "
            f"image_size={image_size} "
            f"device={device} "
            f"resume={resume}"
        )
    )
    model = IconEmbedder().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=DEFAULT_LEARNING_RATE)
    criterion = nn.TripletMarginLoss(margin=DEFAULT_TRIPLET_MARGIN)
    weights_dir = run_dir / "icon-embedder" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "icon-embedder" / "summary.json"

    start_epoch = 0
    best_score = -1.0
    best_epoch: int | None = None
    if model_path is not None and model_path.suffix == ".pt":
        checkpoint = _load_checkpoint(model_path, device)
        try:
            model.load_state_dict(checkpoint["model_state"])
        except RuntimeError as exc:
            checkpoint_version = int(checkpoint.get("architecture_version", 1))
            raise RuntimeError(
                "group1 icon embedder 检查点与当前训练架构不兼容："
                f"{model_path} (checkpoint_version={checkpoint_version}, current_version={ICON_EMBEDDER_ARCHITECTURE_VERSION})。"
                "请删除该 run 后重新 fresh 训练，或显式指定兼容检查点。"
            ) from exc
        raw_best_epoch = checkpoint.get("best_epoch")
        checkpoint_best_epoch = raw_best_epoch if isinstance(raw_best_epoch, int) and raw_best_epoch >= 1 else None
        checkpoint_best_score = float(checkpoint.get("best_score", -1.0))
        checkpoint_epoch = int(checkpoint.get("epoch", -1)) + 1 if isinstance(checkpoint.get("epoch"), int) else None
        if resume:
            best_score = checkpoint_best_score
            best_epoch = checkpoint_best_epoch
            optimizer_state = checkpoint.get("optimizer_state")
            if optimizer_state is not None:
                optimizer.load_state_dict(optimizer_state)
            start_epoch = int(checkpoint.get("epoch", 0)) + 1
        _icon_embedder_log(
            (
                "init "
                f"checkpoint={model_path} "
                f"checkpoint_epoch={checkpoint_epoch} "
                f"checkpoint_best_epoch={checkpoint_best_epoch} "
                f"checkpoint_best_score={checkpoint_best_score:.6f} "
                f"restore_optimizer={resume}"
            )
        )
    else:
        _icon_embedder_log("init checkpoint=(none) restore_optimizer=False")

    train_loader = DataLoader(
        Group1TripletDataset(dataset_config.root, train_records, image_size),
        batch_size=max(1, min(batch_size, len(train_records))),
        shuffle=True,
        collate_fn=_collate_triplets,
    )
    val_loader = DataLoader(
        Group1TripletDataset(dataset_config.root, val_records, image_size),
        batch_size=max(1, min(batch_size, len(val_records))),
        shuffle=False,
        collate_fn=_collate_triplets,
    )

    history: list[dict[str, float | int | None]] = []
    metrics: dict[str, float | None] = {}
    failure_audit: dict[str, Any] = _build_retrieval_failure_audit(
        valid_queries=[],
        failure_rows=[],
        sample_limit=DEFAULT_FAILURE_AUDIT_SAMPLE_LIMIT,
    )
    epochs_without_improvement = 0
    early_stop_triggered = False
    stopped_epoch: int | None = None
    last_review: dict[str, Any] | None = None
    review_history: list[dict[str, Any]] = []
    training_stop_reason = "completed"
    review_decision_mode = (
        embedder_review_protocol.DEFAULT_EMBEDDER_REVIEW_DECISION_MODE
        if review_callback is not None
        else embedder_review_protocol.EMBEDDER_REVIEW_DECISION_MODE_GUARDRAIL_OVERRIDE
    )
    llm_controls_progress = (
        review_callback is not None
        and review_decision_mode == embedder_review_protocol.EMBEDDER_REVIEW_DECISION_MODE_LLM_FIRST
    )
    _write_interim_trial_artifacts(
        summary_path=summary_path,
        interim_trial_dir=interim_trial_dir,
        interim_primary_metric=interim_primary_metric,
        dataset_config=dataset_config,
        run_dir=run_dir,
        model_path=model_path,
        epochs=epochs,
        batch_size=batch_size,
        image_size=image_size,
        device_name=device_name,
        resume=resume,
        review_stage=review_stage,
        review_decision_mode=review_decision_mode,
        review_study_name=review_study_name,
        review_task=review_task,
        review_trial_id=review_trial_id or run_dir.name,
        review_train_name=review_train_name or run_dir.name,
        review_rebuild_count=review_rebuild_count,
        metrics=metrics,
        history=history,
        failure_audit=failure_audit,
        last_review=last_review,
        review_history=review_history,
        training_stop_reason="in_progress",
        stopped_epoch=stopped_epoch,
        finalized=False,
    )
    for epoch in range(start_epoch, epochs):
        train_epoch = _normalize_train_epoch_result(
            _train_one_epoch(
                model,
                train_loader,
                optimizer,
                criterion,
                device,
                triplet_loss_weight=DEFAULT_TRIPLET_LOSS_WEIGHT,
                contrastive_loss_weight=DEFAULT_CONTRASTIVE_LOSS_WEIGHT,
                contrastive_temperature=DEFAULT_CONTRASTIVE_TEMPERATURE,
                epoch_index=epoch,
                total_epochs=epochs,
            )
        )
        train_loss = train_epoch["loss"]
        val_loss = _evaluate_triplet_loss(
            model,
            val_loader,
            criterion,
            device,
            epoch_index=epoch,
            total_epochs=epochs,
        )
        metrics, failure_audit = _normalize_retrieval_evaluation_result(
            _evaluate_model_retrieval(
                model=model,
                records=val_records,
                dataset_root=dataset_config.root,
                image_size=image_size,
                device=device,
                epoch_index=epoch,
                total_epochs=epochs,
            )
        )
        score = float(
            metrics.get("embedding_scene_recall_at_1")
            or metrics.get("embedding_identity_recall_at_1")
            or metrics.get("embedding_recall_at_1")
            or 0.0
        )
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "train_triplet_loss": train_epoch["triplet_loss"],
                "train_contrastive_loss": train_epoch["contrastive_loss"],
                "val_loss": val_loss,
                "embedding_recall_at_1": metrics.get("embedding_recall_at_1"),
                "embedding_recall_at_3": metrics.get("embedding_recall_at_3"),
                "embedding_scene_recall_at_1": metrics.get("embedding_scene_recall_at_1"),
                "embedding_scene_recall_at_3": metrics.get("embedding_scene_recall_at_3"),
                "embedding_identity_recall_at_1": metrics.get("embedding_identity_recall_at_1"),
                "embedding_identity_recall_at_3": metrics.get("embedding_identity_recall_at_3"),
                "embedding_positive_rank_mean": metrics.get("embedding_positive_rank_mean"),
                "embedding_scene_positive_rank_mean": metrics.get("embedding_scene_positive_rank_mean"),
                "embedding_same_template_top1_error_rate": metrics.get("embedding_same_template_top1_error_rate"),
                "embedding_top1_error_scene_target_rate": metrics.get("embedding_top1_error_scene_target_rate"),
                "embedding_top1_error_false_positive_rate": metrics.get("embedding_top1_error_false_positive_rate"),
            }
        )
        _icon_embedder_log(
            (
                f"train_loss={train_loss:.6f} "
                f"train_triplet_loss={train_epoch['triplet_loss']:.6f} "
                f"train_contrastive_loss={train_epoch['contrastive_loss']:.6f} "
                f"val_loss={val_loss:.6f} "
                f"embedding_recall_at_1={metrics.get('embedding_recall_at_1')} "
                f"embedding_recall_at_3={metrics.get('embedding_recall_at_3')} "
                f"embedding_scene_recall_at_1={metrics.get('embedding_scene_recall_at_1')} "
                f"embedding_scene_recall_at_3={metrics.get('embedding_scene_recall_at_3')} "
                f"embedding_identity_recall_at_1={metrics.get('embedding_identity_recall_at_1')} "
                f"embedding_identity_recall_at_3={metrics.get('embedding_identity_recall_at_3')} "
                f"embedding_positive_rank_mean={metrics.get('embedding_positive_rank_mean')}"
            ),
            epoch_index=epoch,
            total_epochs=epochs,
        )

        improved = best_epoch is None or score >= (best_score + early_stopping_min_delta)
        if improved:
            best_score = score
            best_epoch = epoch + 1
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        _save_checkpoint(
            weights_dir / "last.pt",
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            image_size=image_size,
            best_score=best_score,
            best_epoch=best_epoch,
            metrics=metrics,
        )
        if improved:
            _save_checkpoint(
                weights_dir / "best.pt",
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                image_size=image_size,
                best_score=best_score,
                best_epoch=best_epoch,
                metrics=metrics,
            )
        guardrail_alerts: list[str] = []
        force_review = False
        if _should_stop_base_for_zero_triplet_regression(
            history=history,
            review_stage=review_stage,
        ):
            guardrail_alerts.append("guardrail=base_zero_triplet_exact_regression")
            if llm_controls_progress:
                force_review = True
                _icon_embedder_log(
                    (
                        "guardrail-alert "
                        "reason=base_zero_triplet_exact_regression "
                        f"embedding_recall_at_1={metrics.get('embedding_recall_at_1')} "
                        f"embedding_recall_at_3={metrics.get('embedding_recall_at_3')} "
                        f"embedding_identity_recall_at_1={metrics.get('embedding_identity_recall_at_1')} "
                        f"embedding_positive_rank_mean={metrics.get('embedding_positive_rank_mean')}"
                    ),
                    epoch_index=epoch,
                    total_epochs=epochs,
                )
            else:
                stopped_epoch = epoch + 1
                training_stop_reason = "guardrail:base_zero_triplet_exact_regression"
                _icon_embedder_log(
                    (
                        "guardrail-stop "
                        "reason=base_zero_triplet_exact_regression "
                        f"embedding_recall_at_1={metrics.get('embedding_recall_at_1')} "
                        f"embedding_recall_at_3={metrics.get('embedding_recall_at_3')} "
                        f"embedding_identity_recall_at_1={metrics.get('embedding_identity_recall_at_1')} "
                        f"embedding_positive_rank_mean={metrics.get('embedding_positive_rank_mean')}"
                    ),
                    epoch_index=epoch,
                    total_epochs=epochs,
                )
        if _should_stop_hard_for_scene_exact_plateau(
            history=history,
            review_stage=review_stage,
            failure_audit=failure_audit,
        ):
            guardrail_alerts.append("guardrail=hard_scene_exact_plateau")
            if llm_controls_progress:
                force_review = True
                _icon_embedder_log(
                    (
                        "guardrail-alert "
                        "reason=hard_scene_exact_plateau "
                        f"embedding_scene_recall_at_1={metrics.get('embedding_scene_recall_at_1')} "
                        f"embedding_recall_at_1={metrics.get('embedding_recall_at_1')} "
                        f"embedding_positive_rank_mean={metrics.get('embedding_positive_rank_mean')} "
                        f"scene_exact_gap_rate={failure_audit.get('scene_exact_gap_rate')} "
                        f"same_template_confusion_rate={failure_audit.get('same_template_confusion_rate')}"
                    ),
                    epoch_index=epoch,
                    total_epochs=epochs,
                )
            else:
                stopped_epoch = epoch + 1
                training_stop_reason = "guardrail:hard_scene_exact_plateau"
                _icon_embedder_log(
                    (
                        "guardrail-stop "
                        "reason=hard_scene_exact_plateau "
                        f"embedding_scene_recall_at_1={metrics.get('embedding_scene_recall_at_1')} "
                        f"embedding_recall_at_1={metrics.get('embedding_recall_at_1')} "
                        f"embedding_positive_rank_mean={metrics.get('embedding_positive_rank_mean')} "
                        f"scene_exact_gap_rate={failure_audit.get('scene_exact_gap_rate')} "
                        f"same_template_confusion_rate={failure_audit.get('same_template_confusion_rate')}"
                    ),
                    epoch_index=epoch,
                    total_epochs=epochs,
                )
        should_run_review = review_callback is not None and (
            force_review
            or embedder_review_protocol.should_run_embedder_review(
                epoch=epoch + 1,
                min_epochs=review_min_epochs,
                window=review_window,
            )
        )
        if should_run_review:
            review_context = embedder_review_protocol.EmbedderReviewContext(
                study_name=review_study_name,
                task=review_task,
                trial_id=review_trial_id or run_dir.name,
                train_name=review_train_name or run_dir.name,
                stage=review_stage,
                epoch=epoch + 1,
                review_window=review_window,
                rebuild_count=review_rebuild_count,
                dataset_config=str(dataset_config.path),
                image_size=image_size,
                batch_size=batch_size,
                best_epoch=best_epoch,
                best_embedding_recall_at_1=best_score if best_epoch is not None else None,
                current_metrics=metrics,
                recent_history=[dict(item) for item in history[-review_window:]],
                review_history=[dict(item) for item in review_history],
                decision_mode=review_decision_mode,
                guardrail_alerts=guardrail_alerts,
            )
            review_record = review_callback(review_context)
            last_review = review_record.to_dict()
            review_history.append(last_review)
            _icon_embedder_log(
                (
                    "review "
                    f"stage={review_stage} "
                    f"decision={review_record.decision} "
                    f"reason={review_record.reason} "
                    f"confidence={review_record.confidence:.3f}"
                ),
                epoch_index=epoch,
                total_epochs=epochs,
            )
            if review_record.decision != embedder_review_protocol.EMBEDDER_REVIEW_DECISION_CONTINUE:
                stopped_epoch = epoch + 1
                training_stop_reason = f"review:{review_record.decision}"
                _icon_embedder_log(
                    (
                        "review-stop "
                        f"decision={review_record.decision} "
                        f"target={review_record.next_action.get('target_stage')}"
                    ),
                    epoch_index=epoch,
                    total_epochs=epochs,
                )
            else:
                _icon_embedder_log(
                    (
                        "review-continue "
                        f"decision={review_record.decision} "
                        f"target={review_record.next_action.get('target_stage')}"
                    ),
                    epoch_index=epoch,
                    total_epochs=epochs,
                )
        _write_training_summary(
            summary_path=summary_path,
            dataset_config=dataset_config,
            weights_dir=weights_dir,
            image_size=image_size,
            train_records=train_records,
            val_records=val_records,
            model=model,
            metrics=metrics,
            history=history,
            early_stopping_min_epochs=early_stopping_min_epochs,
            early_stopping_patience=early_stopping_patience,
            early_stopping_min_delta=early_stopping_min_delta,
            best_epoch=best_epoch,
            best_score=best_score,
            stopped_epoch=epoch + 1,
            early_stop_triggered=early_stop_triggered,
            review_enabled=review_callback is not None,
            review_stage=review_stage,
            review_decision_mode=review_decision_mode,
            review_min_epochs=review_min_epochs,
            review_window=review_window,
            review_rebuild_count=review_rebuild_count,
            last_review=last_review,
            review_history=review_history,
            training_stop_reason="in_progress" if stopped_epoch is None else training_stop_reason,
            failure_audit=failure_audit,
            finalized=False,
        )
        _write_interim_trial_artifacts(
            summary_path=summary_path,
            interim_trial_dir=interim_trial_dir,
            interim_primary_metric=interim_primary_metric,
            dataset_config=dataset_config,
            run_dir=run_dir,
            model_path=model_path,
            epochs=epochs,
            batch_size=batch_size,
            image_size=image_size,
            device_name=device_name,
            resume=resume,
            review_stage=review_stage,
            review_decision_mode=review_decision_mode,
            review_study_name=review_study_name,
            review_task=review_task,
            review_trial_id=review_trial_id or run_dir.name,
            review_train_name=review_train_name or run_dir.name,
            review_rebuild_count=review_rebuild_count,
            metrics=metrics,
            history=history,
            failure_audit=failure_audit,
            last_review=last_review,
            review_history=review_history,
            training_stop_reason="in_progress" if stopped_epoch is None else training_stop_reason,
            stopped_epoch=epoch + 1,
            finalized=False,
        )
        if stopped_epoch is not None:
            break
        if (
            early_stopping_patience > 0
            and (epoch + 1) >= max(1, early_stopping_min_epochs)
            and epochs_without_improvement >= early_stopping_patience
        ):
            early_stop_triggered = True
            stopped_epoch = epoch + 1
            training_stop_reason = "early_stop"
            _icon_embedder_log(
                (
                    "early-stop "
                    f"best_epoch={best_epoch} "
                    f"best_embedding_recall_at_1={best_score:.6f} "
                    f"patience={early_stopping_patience} "
                    f"min_delta={early_stopping_min_delta:.6f}"
                ),
                epoch_index=epoch,
                total_epochs=epochs,
            )
            _write_training_summary(
                summary_path=summary_path,
                dataset_config=dataset_config,
                weights_dir=weights_dir,
                image_size=image_size,
                train_records=train_records,
                val_records=val_records,
                model=model,
                metrics=metrics,
                history=history,
                early_stopping_min_epochs=early_stopping_min_epochs,
                early_stopping_patience=early_stopping_patience,
                early_stopping_min_delta=early_stopping_min_delta,
                best_epoch=best_epoch,
                best_score=best_score,
                stopped_epoch=stopped_epoch,
                early_stop_triggered=early_stop_triggered,
                review_enabled=review_callback is not None,
                review_stage=review_stage,
                review_decision_mode=review_decision_mode,
                review_min_epochs=review_min_epochs,
                review_window=review_window,
                review_rebuild_count=review_rebuild_count,
                last_review=last_review,
                review_history=review_history,
                training_stop_reason=training_stop_reason,
                failure_audit=failure_audit,
                finalized=False,
            )
            _write_interim_trial_artifacts(
                summary_path=summary_path,
                interim_trial_dir=interim_trial_dir,
                interim_primary_metric=interim_primary_metric,
                dataset_config=dataset_config,
                run_dir=run_dir,
                model_path=model_path,
                epochs=epochs,
                batch_size=batch_size,
                image_size=image_size,
                device_name=device_name,
                resume=resume,
                review_stage=review_stage,
                review_decision_mode=review_decision_mode,
                review_study_name=review_study_name,
                review_task=review_task,
                review_trial_id=review_trial_id or run_dir.name,
                review_train_name=review_train_name or run_dir.name,
                review_rebuild_count=review_rebuild_count,
                metrics=metrics,
                history=history,
                failure_audit=failure_audit,
                last_review=last_review,
                review_history=review_history,
                training_stop_reason=training_stop_reason,
                stopped_epoch=stopped_epoch,
                finalized=False,
            )
            break

    if not metrics:
        metrics, failure_audit = _normalize_retrieval_evaluation_result(
            _evaluate_model_retrieval(
                model=model,
                records=val_records,
                dataset_root=dataset_config.root,
                image_size=image_size,
                device=device,
            )
        )
    if stopped_epoch is None and history:
        stopped_epoch = int(history[-1]["epoch"])

    _write_training_summary(
        summary_path=summary_path,
        dataset_config=dataset_config,
        weights_dir=weights_dir,
        image_size=image_size,
        train_records=train_records,
        val_records=val_records,
        model=model,
        metrics=metrics,
        history=history,
        early_stopping_min_epochs=early_stopping_min_epochs,
        early_stopping_patience=early_stopping_patience,
        early_stopping_min_delta=early_stopping_min_delta,
        best_epoch=best_epoch,
        best_score=best_score,
        stopped_epoch=stopped_epoch,
        early_stop_triggered=early_stop_triggered,
        review_enabled=review_callback is not None,
        review_stage=review_stage,
        review_decision_mode=review_decision_mode,
        review_min_epochs=review_min_epochs,
        review_window=review_window,
        review_rebuild_count=review_rebuild_count,
        last_review=last_review,
        review_history=review_history,
        training_stop_reason=training_stop_reason,
        failure_audit=failure_audit,
        finalized=True,
    )
    _write_interim_trial_artifacts(
        summary_path=summary_path,
        interim_trial_dir=interim_trial_dir,
        interim_primary_metric=interim_primary_metric,
        dataset_config=dataset_config,
        run_dir=run_dir,
        model_path=model_path,
        epochs=epochs,
        batch_size=batch_size,
        image_size=image_size,
        device_name=device_name,
        resume=resume,
        review_stage=review_stage,
        review_decision_mode=review_decision_mode,
        review_study_name=review_study_name,
        review_task=review_task,
        review_trial_id=review_trial_id or run_dir.name,
        review_train_name=review_train_name or run_dir.name,
        review_rebuild_count=review_rebuild_count,
        metrics=metrics,
        history=history,
        failure_audit=failure_audit,
        last_review=last_review,
        review_history=review_history,
        training_stop_reason=training_stop_reason,
        stopped_epoch=stopped_epoch,
        finalized=True,
    )
    return IconEmbedderTrainingResult(
        run_dir=run_dir / "icon-embedder",
        weights_dir=weights_dir,
        best_checkpoint=weights_dir / "best.pt",
        last_checkpoint=weights_dir / "last.pt",
        summary_path=summary_path,
        metrics=metrics,
        sample_count=len(train_records),
        review=last_review,
    )


def _records_for_split(records: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    return [record for record in records if str(record.get("split", "")) == split]


def _collate_triplets(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "anchor": torch.stack([item["anchor"] for item in items]),
        "positive": torch.stack([item["positive"] for item in items]),
        "negative": torch.stack([item["negative"] for item in items]),
        "metadata": [item["metadata"] for item in items],
    }


def _train_one_epoch(
    model: IconEmbedder,
    loader: DataLoader[dict[str, Any]],
    optimizer: torch.optim.Optimizer,
    criterion: nn.TripletMarginLoss,
    device: torch.device,
    *,
    triplet_loss_weight: float,
    contrastive_loss_weight: float,
    contrastive_temperature: float,
    epoch_index: int,
    total_epochs: int,
) -> dict[str, float]:
    model.train()
    total_loss = 0.0
    total_triplet_loss = 0.0
    total_contrastive_loss = 0.0
    total_items = 0
    total_batches = len(loader)
    started = time.perf_counter()
    for batch_index, batch in enumerate(loader, start=1):
        optimizer.zero_grad()
        anchor = model(batch["anchor"].to(device))
        positive = model(batch["positive"].to(device))
        negative = model(batch["negative"].to(device))
        triplet_loss = criterion(anchor, positive, negative)
        contrastive_loss = _in_batch_contrastive_loss(
            anchor=anchor,
            positive=positive,
            negative=negative,
            metadata=batch["metadata"],
            temperature=contrastive_temperature,
        )
        loss = (triplet_loss_weight * triplet_loss) + (contrastive_loss_weight * contrastive_loss)
        loss.backward()
        optimizer.step()
        item_count = int(batch["anchor"].shape[0])
        total_loss += float(loss.item()) * item_count
        total_triplet_loss += float(triplet_loss.item()) * item_count
        total_contrastive_loss += float(contrastive_loss.item()) * item_count
        total_items += item_count
        if batch_index == 1 or batch_index % 200 == 0 or batch_index == total_batches:
            elapsed = time.perf_counter() - started
            avg_loss = total_loss / max(1, total_items)
            _icon_embedder_log(
                (
                    f"step {batch_index}/{total_batches} "
                    f"loss={float(loss.item()):.6f} "
                    f"triplet_loss={float(triplet_loss.item()):.6f} "
                    f"contrastive_loss={float(contrastive_loss.item()):.6f} "
                    f"avg_loss={avg_loss:.6f} "
                    f"elapsed_s={elapsed:.1f}"
                ),
                epoch_index=epoch_index,
                total_epochs=total_epochs,
            )
    denominator = max(1, total_items)
    return {
        "loss": total_loss / denominator,
        "triplet_loss": total_triplet_loss / denominator,
        "contrastive_loss": total_contrastive_loss / denominator,
    }


def _normalize_train_epoch_result(result: Any) -> dict[str, float]:
    if isinstance(result, dict):
        loss = float(result.get("loss", 0.0))
        triplet_loss = float(result.get("triplet_loss", loss))
        contrastive_loss = float(result.get("contrastive_loss", loss))
        return {
            "loss": loss,
            "triplet_loss": triplet_loss,
            "contrastive_loss": contrastive_loss,
        }
    scalar = float(result)
    return {
        "loss": scalar,
        "triplet_loss": scalar,
        "contrastive_loss": scalar,
    }


def _should_stop_base_for_zero_triplet_regression(
    *,
    history: list[dict[str, float | int | None]],
    review_stage: str,
) -> bool:
    if review_stage != "TRAIN_EMBEDDER_BASE":
        return False
    if len(history) < 2:
        return False
    previous = history[-2]
    current = history[-1]

    previous_triplet = _history_float(previous, "train_triplet_loss")
    current_triplet = _history_float(current, "train_triplet_loss")
    if previous_triplet > ZERO_TRIPLET_LOSS_EPS or current_triplet > ZERO_TRIPLET_LOSS_EPS:
        return False

    current_exact_recall_at_1 = _history_float(current, "embedding_recall_at_1")
    current_positive_rank_mean = _history_float(current, "embedding_positive_rank_mean")
    if current_exact_recall_at_1 > ZERO_TRIPLET_GUARDRAIL_MAX_EXACT_RECALL_AT_1:
        return False
    if current_positive_rank_mean < ZERO_TRIPLET_GUARDRAIL_MIN_POSITIVE_RANK_MEAN:
        return False

    worsening_signals = 0
    if _history_float(current, "embedding_recall_at_3") < _history_float(previous, "embedding_recall_at_3"):
        worsening_signals += 1
    if _history_float(current, "embedding_identity_recall_at_1") < _history_float(previous, "embedding_identity_recall_at_1"):
        worsening_signals += 1
    if _history_float(current, "embedding_scene_recall_at_1") < _history_float(previous, "embedding_scene_recall_at_1"):
        worsening_signals += 1
    if current_positive_rank_mean > _history_float(previous, "embedding_positive_rank_mean"):
        worsening_signals += 1
    if _history_float(current, "embedding_same_template_top1_error_rate") > _history_float(previous, "embedding_same_template_top1_error_rate"):
        worsening_signals += 1
    return worsening_signals >= 2


def _should_stop_hard_for_scene_exact_plateau(
    *,
    history: list[dict[str, float | int | None]],
    review_stage: str,
    failure_audit: dict[str, Any],
) -> bool:
    if review_stage != "TRAIN_EMBEDDER_HARD":
        return False
    if len(history) < HARD_SCENE_EXACT_PLATEAU_WINDOW:
        return False
    window = history[-HARD_SCENE_EXACT_PLATEAU_WINDOW:]
    exact_values = [_history_float(record, "embedding_recall_at_1") for record in window]
    if max(exact_values) > HARD_SCENE_EXACT_PLATEAU_MAX_EXACT_RECALL_AT_1:
        return False
    if (max(exact_values) - min(exact_values)) > HARD_SCENE_EXACT_PLATEAU_MAX_EXACT_SPREAD:
        return False
    scene_values = [_history_float(record, "embedding_scene_recall_at_1") for record in window]
    if min(scene_values) < HARD_SCENE_EXACT_PLATEAU_MIN_SCENE_RECALL_AT_1:
        return False
    if _history_float(window[-1], "embedding_positive_rank_mean") < HARD_SCENE_EXACT_PLATEAU_MIN_POSITIVE_RANK_MEAN:
        return False
    triplet_window = window[-2:]
    if any(_history_float(record, "train_triplet_loss") > HARD_SCENE_EXACT_PLATEAU_MAX_TRIPLET_LOSS for record in triplet_window):
        return False
    scene_exact_gap_rate = _audit_float(failure_audit, "scene_exact_gap_rate")
    same_template_confusion_rate = _audit_float(failure_audit, "same_template_confusion_rate")
    return (
        scene_exact_gap_rate >= HARD_SCENE_EXACT_PLATEAU_MIN_SCENE_EXACT_GAP_RATE
        or same_template_confusion_rate >= HARD_SCENE_EXACT_PLATEAU_MIN_SAME_TEMPLATE_CONFUSION_RATE
    )


def _history_float(record: dict[str, float | int | None], key: str) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _audit_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _write_training_summary(
    *,
    summary_path: Path,
    dataset_config: Group1DatasetConfig,
    weights_dir: Path,
    image_size: int,
    train_records: list[dict[str, Any]],
    val_records: list[dict[str, Any]],
    model: IconEmbedder,
    metrics: dict[str, float | None],
    history: list[dict[str, float | int | None]],
    early_stopping_min_epochs: int,
    early_stopping_patience: int,
    early_stopping_min_delta: float,
    best_epoch: int | None,
    best_score: float,
    stopped_epoch: int | None,
    early_stop_triggered: bool,
    review_enabled: bool,
    review_stage: str,
    review_decision_mode: str,
    review_min_epochs: int,
    review_window: int,
    review_rebuild_count: int,
    last_review: dict[str, Any] | None,
    review_history: list[dict[str, Any]],
    training_stop_reason: str,
    failure_audit: dict[str, Any],
    finalized: bool,
) -> None:
    effective_stopped_epoch = stopped_epoch
    if effective_stopped_epoch is None and history:
        last_epoch = history[-1].get("epoch")
        if isinstance(last_epoch, int):
            effective_stopped_epoch = last_epoch
    summary = {
        "component": "icon-embedder",
        "finalized": finalized,
        "dataset_config": str(dataset_config.path),
        "triplets_jsonl": str(dataset_config.embedding.triplets_jsonl),
        "sample_count": len(train_records),
        "validation_sample_count": len(val_records),
        "image_size": image_size,
        "weights": {
            "best": str(weights_dir / "best.pt"),
            "last": str(weights_dir / "last.pt"),
        },
        "metrics": metrics,
        "history": history,
        "early_stopping": {
            "min_epochs": early_stopping_min_epochs,
            "patience": early_stopping_patience,
            "min_delta": early_stopping_min_delta,
            "best_epoch": best_epoch,
            "best_embedding_recall_at_1": best_score if best_epoch is not None else None,
            "stopped_epoch": effective_stopped_epoch,
            "triggered": early_stop_triggered,
        },
        "training": {
            "architecture_version": ICON_EMBEDDER_ARCHITECTURE_VERSION,
            "embedding_dim": model.embedding_dim,
            "learning_rate": DEFAULT_LEARNING_RATE,
            "loss": {
                "triplet_margin": DEFAULT_TRIPLET_MARGIN,
                "triplet_weight": DEFAULT_TRIPLET_LOSS_WEIGHT,
                "contrastive_weight": DEFAULT_CONTRASTIVE_LOSS_WEIGHT,
                "contrastive_temperature": DEFAULT_CONTRASTIVE_TEMPERATURE,
            },
        },
        "review_settings": {
            "enabled": review_enabled,
            "stage": review_stage,
            "decision_mode": review_decision_mode,
            "min_epochs": review_min_epochs,
            "window": review_window,
            "rebuild_count": review_rebuild_count,
        },
        "review": last_review,
        "review_history": review_history,
        "failure_audit": {
            **failure_audit,
            "file_path": str(summary_path.parent / "failure_audit.jsonl"),
        },
        "training_stop": {
            "reason": training_stop_reason if finalized else "in_progress",
            "stopped_epoch": effective_stopped_epoch,
        },
    }
    _write_failure_audit_jsonl(summary_path.parent / "failure_audit.jsonl", failure_audit.get("rows"))
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_interim_trial_artifacts(
    *,
    summary_path: Path,
    interim_trial_dir: Path | None,
    interim_primary_metric: str | None,
    dataset_config: Group1DatasetConfig,
    run_dir: Path,
    model_path: Path | None,
    epochs: int,
    batch_size: int,
    image_size: int,
    device_name: str,
    resume: bool,
    review_stage: str,
    review_decision_mode: str,
    review_study_name: str,
    review_task: str,
    review_trial_id: str,
    review_train_name: str,
    review_rebuild_count: int,
    metrics: dict[str, float | None],
    history: list[dict[str, float | int | None]],
    failure_audit: dict[str, Any],
    last_review: dict[str, Any] | None,
    review_history: list[dict[str, Any]],
    training_stop_reason: str,
    stopped_epoch: int | None,
    finalized: bool,
) -> None:
    if interim_trial_dir is None:
        return
    interim_trial_dir.mkdir(parents=True, exist_ok=True)
    status = "completed" if finalized else "starting" if not history else "in_progress"
    current_epoch = int(history[-1]["epoch"]) if history else 0
    surrogate_metric = "embedding_scene_recall_at_1"
    surrogate_score = metrics.get(surrogate_metric) if isinstance(metrics.get(surrogate_metric), (int, float)) else None
    compact_failure_audit = _compact_failure_audit(failure_audit, summary_path=summary_path)
    failure_patterns = _build_interim_failure_patterns(metrics=metrics, failure_audit=compact_failure_audit)
    result_summary = {
        "interim": True,
        "study_name": review_study_name,
        "task": review_task,
        "trial_id": review_trial_id,
        "train_name": review_train_name,
        "stage": review_stage,
        "decision_mode": review_decision_mode,
        "status": status,
        "finalized": finalized,
        "current_epoch": current_epoch,
        "primary_metric": interim_primary_metric or "full_sequence_hit_rate",
        "primary_score": None,
        "primary_metric_status": "pending_business_eval",
        "surrogate_primary_metric": surrogate_metric,
        "surrogate_primary_score": surrogate_score,
        "metrics": metrics,
        "failure_patterns": failure_patterns,
        "recommended_focus": compact_failure_audit.get("recommended_focus", []),
        "reason_counts": compact_failure_audit.get("reason_counts", {}),
        "training_stop": {
            "reason": training_stop_reason,
            "stopped_epoch": stopped_epoch if stopped_epoch is not None else current_epoch,
        },
        "summary_path": str(summary_path),
        "failure_audit_file": compact_failure_audit.get("file_path"),
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "evidence": _build_interim_evidence(
            review_stage=review_stage,
            status=status,
            metrics=metrics,
            failure_audit=compact_failure_audit,
            training_stop_reason=training_stop_reason,
        ),
    }
    interim_analysis = {
        "interim": True,
        "study_name": review_study_name,
        "task": review_task,
        "trial_id": review_trial_id,
        "train_name": review_train_name,
        "stage": review_stage,
        "status": status,
        "current_params": {
            "dataset_config": str(dataset_config.path),
            "run_dir": str(run_dir),
            "model_path": None if model_path is None else str(model_path),
            "epochs": epochs,
            "batch": batch_size,
            "imgsz": image_size,
            "device": device_name,
            "resume": resume,
            "review_rebuild_count": review_rebuild_count,
        },
        "component_diagnostics": {
            "icon-embedder": {
                "summary_path": str(summary_path),
                "status": status,
                "metrics": metrics,
                "signal_summary": _build_interim_signal_summary(metrics=metrics, failure_audit=compact_failure_audit),
                "failure_audit": compact_failure_audit,
                "training_stop": {
                    "reason": training_stop_reason,
                    "stopped_epoch": stopped_epoch if stopped_epoch is not None else current_epoch,
                },
                "review": last_review,
                "recent_history": history[-3:],
                "review_history_size": len(review_history),
            }
        },
        "evidence": _build_interim_evidence(
            review_stage=review_stage,
            status=status,
            metrics=metrics,
            failure_audit=compact_failure_audit,
            training_stop_reason=training_stop_reason,
        ),
    }
    (interim_trial_dir / "interim_result_summary.json").write_text(
        json.dumps(result_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (interim_trial_dir / "interim_trial_analysis.json").write_text(
        json.dumps(interim_analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _compact_failure_audit(
    failure_audit: dict[str, Any],
    *,
    summary_path: Path,
) -> dict[str, Any]:
    compact = {
        key: value
        for key, value in failure_audit.items()
        if key != "rows"
    }
    compact["file_path"] = str(summary_path.parent / "failure_audit.jsonl")
    return compact


def _build_interim_failure_patterns(
    *,
    metrics: dict[str, float | None],
    failure_audit: dict[str, Any],
) -> list[str]:
    patterns: list[str] = []
    scene_recall = _metric_float(metrics, "embedding_scene_recall_at_1")
    exact_recall = _metric_float(metrics, "embedding_recall_at_1")
    same_template_error = _metric_float(metrics, "embedding_same_template_top1_error_rate")
    if scene_recall < 0.85:
        patterns.append("embedder_scene_recall_gap")
    if scene_recall >= 0.85 and exact_recall < 0.1:
        patterns.append("embedder_global_exact_gap")
    if same_template_error > 0.25 or _audit_float(failure_audit, "same_template_confusion_rate") > 0.25:
        patterns.append("embedder_same_template_confusion")
    if _audit_float(failure_audit, "scene_exact_gap_rate") > 0.5:
        patterns.append("scene_exact_gap")
    if _audit_float(failure_audit, "outside_scene_top1_rate") > 0.5:
        patterns.append("outside_scene_top1")
    return sorted(set(patterns))


def _build_interim_signal_summary(
    *,
    metrics: dict[str, float | None],
    failure_audit: dict[str, Any],
) -> list[str]:
    summary: list[str] = []
    for key in (
        "embedding_scene_recall_at_1",
        "embedding_recall_at_1",
        "embedding_identity_recall_at_1",
        "embedding_positive_rank_mean",
        "embedding_same_template_top1_error_rate",
    ):
        value = _metric_float(metrics, key)
        if value > 0:
            summary.append(f"{key}={value:.6f}")
    for key in ("scene_exact_gap_rate", "same_template_confusion_rate", "outside_scene_top1_rate"):
        value = _audit_float(failure_audit, key)
        if value > 0:
            summary.append(f"{key}={value:.6f}")
    return summary


def _build_interim_evidence(
    *,
    review_stage: str,
    status: str,
    metrics: dict[str, float | None],
    failure_audit: dict[str, Any],
    training_stop_reason: str,
) -> list[str]:
    evidence = [
        f"stage={review_stage}",
        f"status={status}",
        f"training_stop_reason={training_stop_reason}",
    ]
    scene_recall = _metric_float(metrics, "embedding_scene_recall_at_1")
    exact_recall = _metric_float(metrics, "embedding_recall_at_1")
    if scene_recall > 0:
        evidence.append(f"embedding_scene_recall_at_1={scene_recall:.6f}")
    if exact_recall > 0:
        evidence.append(f"embedding_recall_at_1={exact_recall:.6f}")
    scene_exact_gap_rate = _audit_float(failure_audit, "scene_exact_gap_rate")
    if scene_exact_gap_rate > 0:
        evidence.append(f"scene_exact_gap_rate={scene_exact_gap_rate:.6f}")
    return evidence


def _metric_float(metrics: dict[str, float | None], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _in_batch_contrastive_loss(
    *,
    anchor: torch.Tensor,
    positive: torch.Tensor,
    negative: torch.Tensor,
    metadata: list[dict[str, Any]],
    temperature: float,
) -> torch.Tensor:
    if anchor.ndim != 2 or positive.ndim != 2 or negative.ndim != 2:
        raise RuntimeError("group1 icon embedder contrastive loss 需要二维 embedding 张量。")
    if anchor.shape != positive.shape or anchor.shape != negative.shape:
        raise RuntimeError("group1 icon embedder contrastive loss 需要同形状的 anchor/positive/negative embedding。")

    candidate_embeddings = torch.cat([positive, negative], dim=0)
    candidate_identities = [str(item.get("positive_identity", "")) for item in metadata] + [
        str(item.get("negative_identity", "")) for item in metadata
    ]
    logits = torch.matmul(anchor, candidate_embeddings.T) / max(1e-6, temperature)
    losses: list[torch.Tensor] = []

    for index, item in enumerate(metadata):
        anchor_identity = str(item.get("anchor_identity", ""))
        positive_mask = torch.zeros(candidate_embeddings.shape[0], dtype=torch.bool, device=anchor.device)
        if anchor_identity:
            for candidate_index, candidate_identity in enumerate(candidate_identities):
                if candidate_identity == anchor_identity:
                    positive_mask[candidate_index] = True
        positive_mask[index] = True

        sample_logits = logits[index]
        positive_logits = sample_logits[positive_mask]
        denominator = torch.logsumexp(sample_logits, dim=0)
        numerator = torch.logsumexp(positive_logits, dim=0)
        losses.append(denominator - numerator)

    return torch.stack(losses).mean() if losses else logits.new_tensor(0.0)


def _evaluate_triplet_loss(
    model: IconEmbedder,
    loader: DataLoader[dict[str, Any]],
    criterion: nn.TripletMarginLoss,
    device: torch.device,
    *,
    epoch_index: int | None = None,
    total_epochs: int | None = None,
) -> float:
    model.eval()
    total_loss = 0.0
    total_items = 0
    total_batches = len(loader)
    started = time.perf_counter()
    print(
        f"{_icon_embedder_log_prefix(epoch_index, total_epochs)} validation-triplet-loss start batches={total_batches}",
        flush=True,
    )
    with torch.no_grad():
        for batch_index, batch in enumerate(loader, start=1):
            anchor = model(batch["anchor"].to(device))
            positive = model(batch["positive"].to(device))
            negative = model(batch["negative"].to(device))
            loss = criterion(anchor, positive, negative)
            item_count = int(batch["anchor"].shape[0])
            total_loss += float(loss.item()) * item_count
            total_items += item_count
            if batch_index == 1 or batch_index % 50 == 0 or batch_index == total_batches:
                elapsed = time.perf_counter() - started
                avg_loss = total_loss / max(1, total_items)
                print(
                    (
                        f"{_icon_embedder_log_prefix(epoch_index, total_epochs)} "
                        f"validation-triplet-loss {batch_index}/{total_batches} "
                        f"avg_loss={avg_loss:.6f} "
                        f"elapsed_s={elapsed:.1f}"
                    ),
                    flush=True,
                )
    return total_loss / max(1, total_items)


def _evaluate_model_retrieval(
    *,
    model: IconEmbedder,
    records: list[dict[str, Any]],
    dataset_root: Path,
    image_size: int,
    device: torch.device,
    epoch_index: int | None = None,
    total_epochs: int | None = None,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    query_images: dict[str, Path] = {}
    candidate_images: dict[str, Path] = {}
    positives: dict[str, str] = {}
    scene_candidates_by_query: dict[str, set[str]] = {}
    query_metadata: dict[str, dict[str, Any]] = {}
    candidate_metadata: dict[str, dict[str, Any]] = {}
    for record in records:
        anchor_id = str(record["anchor_image"])
        positive_id = str(record["positive_image"])
        negative_id = str(record["negative_image"])
        query_images[anchor_id] = resolve_group1_path(dataset_root, Path(anchor_id))
        candidate_images[positive_id] = resolve_group1_path(dataset_root, Path(positive_id))
        candidate_images[negative_id] = resolve_group1_path(dataset_root, Path(negative_id))
        positives[anchor_id] = positive_id
        scene_candidates_by_query.setdefault(anchor_id, set()).add(positive_id)
        scene_candidates_by_query.setdefault(anchor_id, set()).add(negative_id)
        query_metadata[anchor_id] = _retrieval_metadata(record.get("anchor"), role="query")
        candidate_metadata.setdefault(positive_id, _retrieval_metadata(record.get("positive"), role="positive"))
        candidate_metadata.setdefault(
            negative_id,
            _retrieval_metadata(record.get("negative"), role=str(record.get("negative_role", ""))),
        )

    print(
        (
            f"{_icon_embedder_log_prefix(epoch_index, total_epochs)} retrieval start "
            f"queries={len(query_images)} "
            f"candidates={len(candidate_images)}"
        ),
        flush=True,
    )
    query_embeddings = _embed_image_paths(
        model,
        query_images,
        image_size,
        device,
        stage_name="retrieval-query-embeddings",
        epoch_index=epoch_index,
        total_epochs=total_epochs,
    )
    candidate_embeddings = _embed_image_paths(
        model,
        candidate_images,
        image_size,
        device,
        stage_name="retrieval-candidate-embeddings",
        epoch_index=epoch_index,
        total_epochs=total_epochs,
    )
    return evaluate_retrieval_with_audit(
        query_embeddings=query_embeddings,
        candidate_embeddings=candidate_embeddings,
        positives=positives,
        scene_candidates_by_query={
            query_id: sorted(candidate_ids)
            for query_id, candidate_ids in scene_candidates_by_query.items()
        },
        query_metadata=query_metadata,
        candidate_metadata=candidate_metadata,
        k_values=DEFAULT_RECALL_K_VALUES,
        sample_limit=DEFAULT_FAILURE_AUDIT_SAMPLE_LIMIT,
    )


def _embed_image_paths(
    model: IconEmbedder,
    paths: dict[str, Path],
    image_size: int,
    device: torch.device,
    *,
    stage_name: str,
    epoch_index: int | None = None,
    total_epochs: int | None = None,
    batch_size: int = DEFAULT_EVAL_EMBED_BATCH_SIZE,
) -> dict[str, list[float]]:
    model.eval()
    embeddings: dict[str, list[float]] = {}
    items = list(paths.items())
    if not items:
        return embeddings
    total_images = len(items)
    total_batches = math.ceil(total_images / max(1, batch_size))
    started = time.perf_counter()
    print(
        (
            f"{_icon_embedder_log_prefix(epoch_index, total_epochs)} {stage_name} start "
            f"images={total_images} "
            f"batch={batch_size}"
        ),
        flush=True,
    )
    with torch.no_grad():
        for batch_index, offset in enumerate(range(0, total_images, max(1, batch_size)), start=1):
            batch_items = items[offset : offset + max(1, batch_size)]
            tensors = torch.stack([_load_crop_tensor(path, image_size) for _, path in batch_items]).to(device)
            vectors = model(tensors).detach().cpu().tolist()
            for (image_id, _), vector in zip(batch_items, vectors, strict=False):
                embeddings[image_id] = [float(value) for value in vector]
            processed = min(total_images, offset + len(batch_items))
            if batch_index == 1 or batch_index % 20 == 0 or processed == total_images:
                elapsed = time.perf_counter() - started
                print(
                    (
                        f"{_icon_embedder_log_prefix(epoch_index, total_epochs)} {stage_name} "
                        f"{processed}/{total_images} "
                        f"batches={batch_index}/{total_batches} "
                        f"elapsed_s={elapsed:.1f}"
                    ),
                    flush=True,
                )
    return embeddings


def _load_crop_tensor(path: Path, image_size: int) -> torch.Tensor:
    with Image.open(path) as image:
        rgb = image.convert("RGB").resize((image_size, image_size))
        pixels = list(rgb.tobytes())
    tensor = torch.tensor(pixels, dtype=torch.float32).view(image_size, image_size, 3)
    return tensor.permute(2, 0, 1) / 255.0


def _load_target_crop_tensor(image_path: Path, target: dict[str, Any], image_size: int) -> torch.Tensor:
    bbox = target.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise RuntimeError("group1 icon embedder runtime 需要合法 bbox。")
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        x1 = max(0, min(width, int(bbox[0])))
        y1 = max(0, min(height, int(bbox[1])))
        x2 = max(x1 + 1, min(width, int(bbox[2])))
        y2 = max(y1 + 1, min(height, int(bbox[3])))
        crop = rgb.crop((x1, y1, x2, y2)).resize((image_size, image_size))
        pixels = list(crop.tobytes())
    tensor = torch.tensor(pixels, dtype=torch.float32).view(image_size, image_size, 3)
    return tensor.permute(2, 0, 1) / 255.0


def _object_identity(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    raw_asset_id = value.get("asset_id")
    if isinstance(raw_asset_id, str) and raw_asset_id.strip():
        return raw_asset_id
    raw_template_id = value.get("template_id")
    raw_variant_id = value.get("variant_id")
    if isinstance(raw_template_id, str) and isinstance(raw_variant_id, str):
        return f"{raw_template_id}:{raw_variant_id}"
    return ""


def _retrieval_metadata(value: Any, *, role: str) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"identity": "", "template_id": "", "variant_id": "", "role": role}
    return {
        "identity": _object_identity(value),
        "template_id": str(value.get("template_id", "")),
        "variant_id": str(value.get("variant_id", "")),
        "role": role,
    }


def _retrieval_identity(
    metadata: dict[str, Any] | None,
    *,
    fallback: dict[str, Any] | None = None,
) -> str:
    if isinstance(metadata, dict):
        identity = str(metadata.get("identity", "")).strip()
        if identity:
            return identity
    if isinstance(fallback, dict):
        return str(fallback.get("identity", "")).strip()
    return ""


def _retrieval_template_id(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("template_id", "")).strip()


def _retrieval_failure_reason(
    *,
    top1_role: str,
    scene_exact_gap: bool,
    same_identity_confusion: bool,
    same_template_confusion: bool,
) -> str:
    if same_template_confusion:
        return "same_template_confusion"
    if scene_exact_gap:
        return "scene_exact_gap"
    if same_identity_confusion:
        return "same_identity_confusion"
    if top1_role.startswith("scene_target"):
        return "scene_target_confusion"
    if top1_role.startswith("distractor"):
        return "distractor_confusion"
    if top1_role.startswith("false_positive"):
        return "false_positive_confusion"
    return "other_confusion"


def _build_retrieval_failure_audit(
    *,
    valid_queries: list[str],
    failure_rows: list[dict[str, Any]],
    sample_limit: int,
) -> dict[str, Any]:
    query_count = len(valid_queries)
    failure_count = len(failure_rows)
    scene_exact_gap_count = sum(1 for row in failure_rows if bool(row.get("scene_exact_gap")))
    same_identity_confusion_count = sum(1 for row in failure_rows if bool(row.get("same_identity_confusion")))
    same_template_confusion_count = sum(1 for row in failure_rows if bool(row.get("same_template_confusion")))
    outside_scene_top1_count = sum(1 for row in failure_rows if row.get("top1_in_scene") is False)
    reason_counts: dict[str, int] = {}
    for row in failure_rows:
        reason = str(row.get("error_reason", "")).strip()
        if not reason:
            continue
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    ordered_rows = sorted(
        failure_rows,
        key=lambda row: (
            int(bool(row.get("scene_exact_gap"))),
            int(bool(row.get("same_template_confusion"))),
            int(bool(row.get("same_identity_confusion"))),
            int(row.get("positive_rank", 0)),
        ),
        reverse=True,
    )
    return {
        "query_count": query_count,
        "failure_count": failure_count,
        "exact_failure_rate": _safe_ratio(failure_count, query_count),
        "scene_exact_gap_count": scene_exact_gap_count,
        "scene_exact_gap_rate": _safe_ratio(scene_exact_gap_count, query_count),
        "same_identity_confusion_count": same_identity_confusion_count,
        "same_identity_confusion_rate": _safe_ratio(same_identity_confusion_count, query_count),
        "same_template_confusion_count": same_template_confusion_count,
        "same_template_confusion_rate": _safe_ratio(same_template_confusion_count, query_count),
        "outside_scene_top1_count": outside_scene_top1_count,
        "outside_scene_top1_rate": _safe_ratio(outside_scene_top1_count, query_count),
        "reason_counts": reason_counts,
        "recommended_focus": _recommended_retrieval_focus(
            query_count=query_count,
            scene_exact_gap_count=scene_exact_gap_count,
            same_identity_confusion_count=same_identity_confusion_count,
            same_template_confusion_count=same_template_confusion_count,
            outside_scene_top1_count=outside_scene_top1_count,
        ),
        "examples": ordered_rows[: max(0, sample_limit)],
        "rows": ordered_rows,
    }


def _recommended_retrieval_focus(
    *,
    query_count: int,
    scene_exact_gap_count: int,
    same_identity_confusion_count: int,
    same_template_confusion_count: int,
    outside_scene_top1_count: int,
) -> list[str]:
    focus: list[str] = []
    if _safe_ratio(scene_exact_gap_count, query_count) >= 0.15:
        focus.append("shift_gate_to_scene_and_business")
    if _safe_ratio(same_template_confusion_count, query_count) >= 0.10:
        focus.append("increase_same_template_hard_negatives")
    if _safe_ratio(same_identity_confusion_count, query_count) >= 0.10:
        focus.append("audit_identity_labels_and_variant_definitions")
    if _safe_ratio(outside_scene_top1_count, query_count) >= 0.10:
        focus.append("inspect_detector_candidate_noise")
    if not focus:
        focus.append("continue_current_metric_learning")
    return focus


def _normalize_retrieval_evaluation_result(
    result: object,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    if isinstance(result, tuple) and len(result) == 2:
        metrics, failure_audit = result
        if isinstance(metrics, dict) and isinstance(failure_audit, dict):
            return metrics, failure_audit
    if isinstance(result, dict):
        return result, _build_retrieval_failure_audit(
            valid_queries=[],
            failure_rows=[],
            sample_limit=DEFAULT_FAILURE_AUDIT_SAMPLE_LIMIT,
        )
    raise RuntimeError("group1 icon embedder retrieval 评估结果格式非法。")


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _write_failure_audit_jsonl(path: Path, rows: object) -> None:
    if not isinstance(rows, list):
        write_jsonl(path, [])
        return
    write_jsonl(path, [row for row in rows if isinstance(row, dict)])


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def _evaluate_scene_retrieval(
    *,
    query_embeddings: dict[str, list[float]],
    candidate_embeddings: dict[str, list[float]],
    positives: dict[str, str],
    scene_candidates_by_query: dict[str, list[str]],
    k_values: tuple[int, ...],
) -> dict[str, float | None]:
    valid_queries: list[str] = []
    for query_id, positive_id in positives.items():
        if query_id not in query_embeddings or positive_id not in candidate_embeddings:
            continue
        scene_candidates = [
            candidate_id
            for candidate_id in scene_candidates_by_query.get(query_id, [])
            if candidate_id in candidate_embeddings
        ]
        if positive_id not in scene_candidates:
            continue
        valid_queries.append(query_id)

    metrics: dict[str, float | None] = {}
    hits_by_k = {k: 0 for k in k_values}
    positive_ranks: list[int] = []
    for k in k_values:
        if not valid_queries:
            metrics[f"embedding_scene_recall_at_{k}"] = None
    if not valid_queries:
        metrics["embedding_scene_positive_rank_mean"] = None
        metrics["embedding_scene_positive_rank_median"] = None
        return metrics

    for query_id in valid_queries:
        positive_id = positives[query_id]
        scene_candidates = [
            candidate_id
            for candidate_id in scene_candidates_by_query.get(query_id, [])
            if candidate_id in candidate_embeddings
        ]
        ranked = sorted(
            scene_candidates,
            key=lambda candidate_id: _cosine_similarity(
                query_embeddings[query_id],
                candidate_embeddings[candidate_id],
            ),
            reverse=True,
        )
        positive_rank = ranked.index(positive_id) + 1
        positive_ranks.append(positive_rank)
        for k in k_values:
            if positive_id in ranked[:k]:
                hits_by_k[k] += 1

    for k in k_values:
        metrics[f"embedding_scene_recall_at_{k}"] = hits_by_k[k] / len(valid_queries)
    metrics["embedding_scene_positive_rank_mean"] = sum(positive_ranks) / len(positive_ranks)
    metrics["embedding_scene_positive_rank_median"] = _median(positive_ranks)
    return metrics


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (left_norm * right_norm)


def _resolve_device(device_name: str) -> torch.device:
    if device_name == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device(f"cuda:{device_name}" if device_name.isdigit() else device_name)
    return torch.device("cpu")


def _icon_embedder_log_prefix(epoch_index: int | None, total_epochs: int | None) -> str:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    if epoch_index is None or total_epochs is None:
        return f"{timestamp} icon-embedder"
    return f"{timestamp} icon-embedder epoch {epoch_index + 1}/{total_epochs}"


def _icon_embedder_log(
    message: str,
    *,
    epoch_index: int | None = None,
    total_epochs: int | None = None,
) -> None:
    print(f"{_icon_embedder_log_prefix(epoch_index, total_epochs)} {message}", flush=True)


def _load_checkpoint(checkpoint_path: Path, device: torch.device) -> dict[str, Any]:
    if not checkpoint_path.exists():
        raise RuntimeError(f"未找到 group1 icon embedder 检查点：{checkpoint_path}")
    try:
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    except TypeError:  # pragma: no cover - compatibility with older torch
        checkpoint = torch.load(checkpoint_path, map_location=device)
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise RuntimeError(f"group1 icon embedder 检查点格式非法：{checkpoint_path}")
    return checkpoint


def _save_checkpoint(
    path: Path,
    *,
    model: IconEmbedder,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    image_size: int,
    best_score: float,
    best_epoch: int | None,
    metrics: dict[str, float | None],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "architecture_version": ICON_EMBEDDER_ARCHITECTURE_VERSION,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "epoch": epoch,
            "imgsz": image_size,
            "embedding_dim": model.embedding_dim,
            "best_score": best_score,
            "best_epoch": best_epoch,
            "metrics": metrics,
        },
        path,
    )
