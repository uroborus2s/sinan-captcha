"""Metric-learning icon embedder for group1 instance matching."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset

from common.jsonl import read_jsonl
from train.group1.dataset import Group1DatasetConfig, resolve_group1_path

DEFAULT_EMBEDDING_DIM = 64
DEFAULT_RECALL_K_VALUES = (1, 3)


@dataclass(frozen=True)
class IconEmbedderTrainingResult:
    run_dir: Path
    weights_dir: Path
    best_checkpoint: Path
    last_checkpoint: Path
    summary_path: Path
    metrics: dict[str, float | None]
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("run_dir", "weights_dir", "best_checkpoint", "last_checkpoint", "summary_path"):
            payload[key] = str(payload[key])
        return payload


class IconEmbedder(nn.Module):
    """Small CNN that maps icon crops to L2-normalized embeddings."""

    def __init__(self, embedding_dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim
        self.features = nn.Sequential(
            nn.Conv2d(3, 24, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(24, 48, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(48, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.projection = nn.Linear(64, embedding_dim)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.features(inputs).flatten(1)
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
    model.load_state_dict(checkpoint["model_state"])
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
    k_values: tuple[int, ...] = DEFAULT_RECALL_K_VALUES,
) -> dict[str, float | None]:
    valid_queries = [
        query_id
        for query_id, positive_id in positives.items()
        if query_id in query_embeddings and positive_id in candidate_embeddings
    ]
    metrics: dict[str, float | None] = {}
    for k in k_values:
        if not valid_queries:
            metrics[f"embedding_recall_at_{k}"] = None
            continue
        hits = 0
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
            if positive_id in ranked[:k]:
                hits += 1
        metrics[f"embedding_recall_at_{k}"] = hits / len(valid_queries)
    return metrics


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
) -> IconEmbedderTrainingResult:
    if not dataset_config.is_instance_matching or dataset_config.embedding is None:
        raise RuntimeError("当前 group1 dataset.json 未提供 embedding 数据，无法训练 icon embedder。")
    records = load_embedding_triplets(dataset_config.embedding.triplets_jsonl)
    train_records = _records_for_split(records, "train")
    val_records = _records_for_split(records, "val") or _records_for_split(records, "test") or train_records
    if not train_records:
        raise RuntimeError("group1 icon embedder 训练集为空。")

    device = _resolve_device(device_name)
    model = IconEmbedder().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    criterion = nn.TripletMarginLoss(margin=0.25)
    weights_dir = run_dir / "icon-embedder" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)

    start_epoch = 0
    best_score = -1.0
    if model_path is not None and model_path.suffix == ".pt":
        checkpoint = _load_checkpoint(model_path, device)
        model.load_state_dict(checkpoint["model_state"])
        best_score = float(checkpoint.get("best_score", -1.0))
        if resume:
            optimizer_state = checkpoint.get("optimizer_state")
            if optimizer_state is not None:
                optimizer.load_state_dict(optimizer_state)
            start_epoch = int(checkpoint.get("epoch", 0)) + 1

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
    for epoch in range(start_epoch, epochs):
        train_loss = _train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss = _evaluate_triplet_loss(model, val_loader, criterion, device)
        metrics = _evaluate_model_retrieval(
            model=model,
            records=val_records,
            dataset_root=dataset_config.root,
            image_size=image_size,
            device=device,
        )
        score = float(metrics.get("embedding_recall_at_1") or 0.0)
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "embedding_recall_at_1": metrics.get("embedding_recall_at_1"),
                "embedding_recall_at_3": metrics.get("embedding_recall_at_3"),
            }
        )
        _save_checkpoint(
            weights_dir / "last.pt",
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            image_size=image_size,
            best_score=max(best_score, score),
            metrics=metrics,
        )
        if score >= best_score:
            best_score = score
            _save_checkpoint(
                weights_dir / "best.pt",
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                image_size=image_size,
                best_score=best_score,
                metrics=metrics,
            )

    if not metrics:
        metrics = _evaluate_model_retrieval(
            model=model,
            records=val_records,
            dataset_root=dataset_config.root,
            image_size=image_size,
            device=device,
        )

    summary_path = run_dir / "icon-embedder" / "summary.json"
    summary = {
        "component": "icon-embedder",
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
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return IconEmbedderTrainingResult(
        run_dir=run_dir / "icon-embedder",
        weights_dir=weights_dir,
        best_checkpoint=weights_dir / "best.pt",
        last_checkpoint=weights_dir / "last.pt",
        summary_path=summary_path,
        metrics=metrics,
        sample_count=len(train_records),
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
) -> float:
    model.train()
    total_loss = 0.0
    total_items = 0
    for batch in loader:
        optimizer.zero_grad()
        anchor = model(batch["anchor"].to(device))
        positive = model(batch["positive"].to(device))
        negative = model(batch["negative"].to(device))
        loss = criterion(anchor, positive, negative)
        loss.backward()
        optimizer.step()
        item_count = int(batch["anchor"].shape[0])
        total_loss += float(loss.item()) * item_count
        total_items += item_count
    return total_loss / max(1, total_items)


def _evaluate_triplet_loss(
    model: IconEmbedder,
    loader: DataLoader[dict[str, Any]],
    criterion: nn.TripletMarginLoss,
    device: torch.device,
) -> float:
    model.eval()
    total_loss = 0.0
    total_items = 0
    with torch.no_grad():
        for batch in loader:
            anchor = model(batch["anchor"].to(device))
            positive = model(batch["positive"].to(device))
            negative = model(batch["negative"].to(device))
            loss = criterion(anchor, positive, negative)
            item_count = int(batch["anchor"].shape[0])
            total_loss += float(loss.item()) * item_count
            total_items += item_count
    return total_loss / max(1, total_items)


def _evaluate_model_retrieval(
    *,
    model: IconEmbedder,
    records: list[dict[str, Any]],
    dataset_root: Path,
    image_size: int,
    device: torch.device,
) -> dict[str, float | None]:
    query_images: dict[str, Path] = {}
    candidate_images: dict[str, Path] = {}
    positives: dict[str, str] = {}
    for record in records:
        anchor_id = str(record["anchor_image"])
        positive_id = str(record["positive_image"])
        negative_id = str(record["negative_image"])
        query_images[anchor_id] = resolve_group1_path(dataset_root, Path(anchor_id))
        candidate_images[positive_id] = resolve_group1_path(dataset_root, Path(positive_id))
        candidate_images[negative_id] = resolve_group1_path(dataset_root, Path(negative_id))
        positives[anchor_id] = positive_id

    query_embeddings = _embed_image_paths(model, query_images, image_size, device)
    candidate_embeddings = _embed_image_paths(model, candidate_images, image_size, device)
    return evaluate_retrieval(
        query_embeddings=query_embeddings,
        candidate_embeddings=candidate_embeddings,
        positives=positives,
        k_values=DEFAULT_RECALL_K_VALUES,
    )


def _embed_image_paths(
    model: IconEmbedder,
    paths: dict[str, Path],
    image_size: int,
    device: torch.device,
) -> dict[str, list[float]]:
    model.eval()
    embeddings: dict[str, list[float]] = {}
    with torch.no_grad():
        for image_id, path in paths.items():
            tensor = _load_crop_tensor(path, image_size).unsqueeze(0).to(device)
            vector = model(tensor).detach().cpu().flatten().tolist()
            embeddings[image_id] = [float(value) for value in vector]
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
    metrics: dict[str, float | None],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "epoch": epoch,
            "imgsz": image_size,
            "embedding_dim": model.embedding_dim,
            "best_score": best_score,
            "metrics": metrics,
        },
        path,
    )
