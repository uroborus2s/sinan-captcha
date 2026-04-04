"""Paired-input training and prediction runner for group2."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
from typing import Any

import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset

from core.common.jsonl import write_jsonl
from core.dataset.validation import get_group2_target, set_group2_target, validate_group2_row
from core.train.group2.dataset import load_group2_dataset_config, load_group2_rows, resolve_group2_path

FEATURE_STRIDE = 4


class CorrelationEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(32, 48, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(48, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


class PairedGapLocator(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.master_encoder = CorrelationEncoder()
        self.tile_encoder = CorrelationEncoder()

    def forward(self, master: torch.Tensor, tile: torch.Tensor) -> torch.Tensor:
        master_features = F.normalize(self.master_encoder(master), dim=1)
        tile_features = self.tile_encoder(tile)

        responses: list[torch.Tensor] = []
        for index in range(master_features.shape[0]):
            kernel = tile_features[index : index + 1]
            kernel = kernel / kernel.flatten(1).norm(dim=1, keepdim=True).clamp_min(1e-6).view(1, 1, 1, 1)
            responses.append(F.conv2d(master_features[index : index + 1], kernel))
        return torch.cat(responses, dim=0)


class Group2PairDataset(Dataset[dict[str, Any]]):
    def __init__(self, dataset_root: Path, rows: list[dict[str, Any]], imgsz: int) -> None:
        self.dataset_root = dataset_root
        self.rows = rows
        self.imgsz = imgsz

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = validate_group2_row(dict(self.rows[index]))
        master_path = resolve_group2_path(self.dataset_root, Path(str(row["master_image"])))
        tile_path = resolve_group2_path(self.dataset_root, Path(str(row["tile_image"])))

        master_image = Image.open(master_path).convert("L")
        tile_image = Image.open(tile_path).convert("RGBA")
        master_width, master_height = master_image.size
        tile_width, tile_height = tile_image.size

        scale_x = self.imgsz / float(master_width)
        scale_y = self.imgsz / float(master_height)
        resized_tile_width = max(1, int(round(tile_width * scale_x)))
        resized_tile_height = max(1, int(round(tile_height * scale_y)))

        master_tensor = _image_to_tensor(master_image.resize((self.imgsz, self.imgsz)))
        tile_tensor = _rgba_tile_to_tensor(tile_image.resize((resized_tile_width, resized_tile_height)))

        target = get_group2_target(row)
        response_width = _response_extent(self.imgsz, resized_tile_width)
        response_height = _response_extent(self.imgsz, resized_tile_height)
        target_x = min(
            response_width - 1,
            max(0, int(round(int(target["bbox"][0]) * scale_x / FEATURE_STRIDE))),
        )
        target_y = min(
            response_height - 1,
            max(0, int(round(int(target["bbox"][1]) * scale_y / FEATURE_STRIDE))),
        )

        return {
            "master": master_tensor,
            "tile": tile_tensor,
            "target_index": target_y * response_width + target_x,
            "row": row,
            "meta": {
                "master_width": master_width,
                "master_height": master_height,
                "tile_width": tile_width,
                "tile_height": tile_height,
                "scale_x": scale_x,
                "scale_y": scale_y,
                "response_width": response_width,
                "response_height": response_height,
            },
        }


def collate_group2_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "master": torch.stack([item["master"] for item in items]),
        "tile": torch.stack([item["tile"] for item in items]),
        "target_index": torch.tensor([int(item["target_index"]) for item in items], dtype=torch.long),
        "rows": [item["row"] for item in items],
        "metas": [item["meta"] for item in items],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run paired-input train/predict flows for group2.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="train the paired group2 model")
    train_parser.add_argument("--dataset-config", type=Path, required=True)
    train_parser.add_argument("--project", type=Path, required=True)
    train_parser.add_argument("--name", required=True)
    train_parser.add_argument("--model", default="paired_cnn_v1")
    train_parser.add_argument("--epochs", type=int, default=100)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--imgsz", type=int, default=192)
    train_parser.add_argument("--device", default="0")
    train_parser.add_argument("--resume", action="store_true")

    predict_parser = subparsers.add_parser("predict", help="run paired group2 prediction")
    predict_parser.add_argument("--dataset-config", type=Path, required=True)
    predict_parser.add_argument("--model", type=Path, required=True)
    predict_parser.add_argument("--source", type=Path, required=True)
    predict_parser.add_argument("--project", type=Path, required=True)
    predict_parser.add_argument("--name", required=True)
    predict_parser.add_argument("--imgsz", type=int, default=192)
    predict_parser.add_argument("--device", default="0")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "train":
            _run_train(args)
        elif args.command == "predict":
            _run_predict(args)
        else:  # pragma: no cover - argparse guards
            raise RuntimeError(f"unsupported command: {args.command}")
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    return 0


def _run_train(args: argparse.Namespace) -> None:
    dataset_config = load_group2_dataset_config(args.dataset_config)
    train_rows = load_group2_rows(dataset_config, dataset_config.splits["train"])
    val_rows = load_group2_rows(dataset_config, dataset_config.splits["val"])
    if not train_rows:
        raise RuntimeError("group2 训练集为空，无法开始训练。")

    device = _resolve_device(args.device)
    model = PairedGapLocator().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()
    run_dir = args.project / args.name
    weights_dir = run_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)

    start_epoch = 0
    best_score = -1.0
    if str(args.model).endswith(".pt"):
        checkpoint = _load_checkpoint(Path(args.model), device)
        model.load_state_dict(checkpoint["model_state"])
        best_score = float(checkpoint.get("best_score", -1.0))
        if args.resume:
            optimizer_state = checkpoint.get("optimizer_state")
            if optimizer_state is not None:
                optimizer.load_state_dict(optimizer_state)
            start_epoch = int(checkpoint.get("epoch", 0)) + 1

    train_loader = DataLoader(
        Group2PairDataset(dataset_config.root, train_rows, args.imgsz),
        batch_size=max(1, min(args.batch, len(train_rows))),
        shuffle=True,
        collate_fn=collate_group2_batch,
    )
    val_loader = DataLoader(
        Group2PairDataset(dataset_config.root, val_rows or train_rows, args.imgsz),
        batch_size=max(1, min(args.batch, len(val_rows or train_rows))),
        shuffle=False,
        collate_fn=collate_group2_batch,
    )

    history: list[dict[str, float | int | None]] = []
    for epoch in range(start_epoch, args.epochs):
        train_loss = _train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_metrics = _evaluate(model, val_loader, criterion, device)
        score = float(val_metrics["mean_iou"] or 0.0)
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "point_hit_rate": val_metrics["point_hit_rate"],
                "mean_center_error_px": val_metrics["mean_center_error_px"],
                "mean_iou": val_metrics["mean_iou"],
                "val_loss": val_metrics["val_loss"],
            }
        )
        _save_checkpoint(
            weights_dir / "last.pt",
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            imgsz=args.imgsz,
            best_score=max(best_score, score),
        )
        if score >= best_score:
            best_score = score
            _save_checkpoint(
                weights_dir / "best.pt",
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                imgsz=args.imgsz,
                best_score=best_score,
            )
        print(
            "epoch"
            f" {epoch + 1}/{args.epochs}"
            f" train_loss={train_loss:.4f}"
            f" point_hit_rate={_fmt_metric(val_metrics['point_hit_rate'])}"
            f" mean_iou={_fmt_metric(val_metrics['mean_iou'])}"
        )

    summary = {
        "dataset_config": str(args.dataset_config),
        "run_dir": str(run_dir),
        "weights": {
            "best": str(weights_dir / "best.pt"),
            "last": str(weights_dir / "last.pt"),
        },
        "best_score": best_score,
        "history": history,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_predict(args: argparse.Namespace) -> None:
    dataset_config = load_group2_dataset_config(args.dataset_config)
    rows = load_group2_rows(dataset_config, args.source)
    if not rows:
        raise RuntimeError("group2 预测输入为空。")

    device = _resolve_device(args.device)
    checkpoint = _load_checkpoint(args.model, device)
    model = PairedGapLocator().to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    dataset = Group2PairDataset(dataset_config.root, rows, int(checkpoint.get("imgsz", args.imgsz)))
    loader = DataLoader(
        dataset,
        batch_size=max(1, min(16, len(rows))),
        shuffle=False,
        collate_fn=collate_group2_batch,
    )

    output_dir = args.project / args.name
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions: list[dict[str, Any]] = []

    with torch.no_grad():
        for batch in loader:
            master = batch["master"].to(device)
            tile = batch["tile"].to(device)
            started = time.perf_counter()
            responses = model(master, tile)
            elapsed_ms = (time.perf_counter() - started) * 1000.0 / max(1, master.shape[0])
            for index, row in enumerate(batch["rows"]):
                bbox = _decode_bbox(responses[index], batch["metas"][index])
                predictions.append(_build_prediction_row(row, bbox, elapsed_ms))

    write_jsonl(output_dir / "labels.jsonl", predictions)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "dataset_config": str(args.dataset_config),
                "source": str(args.source),
                "model": str(args.model),
                "sample_count": len(predictions),
                "labels_path": str(output_dir / "labels.jsonl"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _train_one_epoch(
    model: PairedGapLocator,
    loader: DataLoader[dict[str, Any]],
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    total_batches = 0
    for batch in loader:
        master = batch["master"].to(device)
        tile = batch["tile"].to(device)
        target_index = batch["target_index"].to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(master, tile).flatten(start_dim=1)
        loss = criterion(logits, target_index)
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu())
        total_batches += 1
    return total_loss / max(1, total_batches)


def _evaluate(
    model: PairedGapLocator,
    loader: DataLoader[dict[str, Any]],
    criterion: nn.Module,
    device: torch.device,
) -> dict[str, float | None]:
    model.eval()
    total_loss = 0.0
    total_batches = 0
    center_errors: list[float] = []
    ious: list[float] = []
    hits = 0
    samples = 0

    with torch.no_grad():
        for batch in loader:
            master = batch["master"].to(device)
            tile = batch["tile"].to(device)
            target_index = batch["target_index"].to(device)
            responses = model(master, tile)
            loss = criterion(responses.flatten(start_dim=1), target_index)
            total_loss += float(loss.detach().cpu())
            total_batches += 1

            for index, row in enumerate(batch["rows"]):
                predicted_bbox = _decode_bbox(responses[index], batch["metas"][index])
                target = get_group2_target(row)
                center_error = _distance(target["center"], _bbox_center(predicted_bbox))
                iou = _iou(target["bbox"], predicted_bbox)
                center_errors.append(center_error)
                ious.append(iou)
                hits += 1 if center_error <= 12 else 0
                samples += 1

    return {
        "point_hit_rate": hits / samples if samples else 0.0,
        "mean_center_error_px": _mean(center_errors),
        "mean_iou": _mean(ious),
        "val_loss": total_loss / max(1, total_batches),
    }


def _build_prediction_row(row: dict[str, Any], bbox: list[int], inference_ms: float) -> dict[str, Any]:
    updated_target = dict(get_group2_target(row))
    updated_target["bbox"] = bbox
    updated_target["center"] = _bbox_center(bbox)
    prediction = set_group2_target(row, updated_target)
    tile_bbox = prediction.get("tile_bbox")
    if isinstance(tile_bbox, list) and len(tile_bbox) == 4:
        prediction["offset_x"] = int(bbox[0]) - int(tile_bbox[0])
        prediction["offset_y"] = int(bbox[1]) - int(tile_bbox[1])
    prediction["label_source"] = "predicted"
    prediction["inference_ms"] = round(inference_ms, 4)
    return prediction


def _decode_bbox(response: torch.Tensor, meta: dict[str, Any]) -> list[int]:
    response_height = int(meta["response_height"])
    response_width = int(meta["response_width"])
    index = int(response.flatten().argmax().item())
    feature_y, feature_x = divmod(index, response_width)
    scale_x = float(meta["scale_x"])
    scale_y = float(meta["scale_y"])
    tile_width = int(meta["tile_width"])
    tile_height = int(meta["tile_height"])
    master_width = int(meta["master_width"])
    master_height = int(meta["master_height"])

    x1 = int(round((feature_x * FEATURE_STRIDE) / scale_x))
    y1 = int(round((feature_y * FEATURE_STRIDE) / scale_y))
    x1 = max(0, min(x1, max(0, master_width - tile_width)))
    y1 = max(0, min(y1, max(0, master_height - tile_height)))
    return [x1, y1, x1 + tile_width, y1 + tile_height]


def _load_checkpoint(path: Path, device: torch.device) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"未找到 group2 检查点：{path}")
    checkpoint = torch.load(path, map_location=device)
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise RuntimeError(f"group2 检查点格式非法：{path}")
    return checkpoint


def _save_checkpoint(
    path: Path,
    *,
    model: PairedGapLocator,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    imgsz: int,
    best_score: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "imgsz": imgsz,
            "best_score": best_score,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
        },
        path,
    )


def _image_to_tensor(image: Image.Image) -> torch.Tensor:
    array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


def _rgba_tile_to_tensor(image: Image.Image) -> torch.Tensor:
    rgba = np.asarray(image, dtype=np.float32)
    rgb = rgba[:, :, :3].mean(axis=2)
    alpha = rgba[:, :, 3] / 255.0
    return torch.from_numpy((rgb * alpha / 255.0).astype(np.float32)).unsqueeze(0)


def _response_extent(master_extent: int, tile_extent: int) -> int:
    return max(1, master_extent // FEATURE_STRIDE - tile_extent // FEATURE_STRIDE + 1)


def _resolve_device(raw_device: str) -> torch.device:
    if raw_device == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device(f"cuda:{raw_device}")
    return torch.device("cpu")


def _distance(left: list[int], right: list[int]) -> float:
    return math.hypot(int(left[0]) - int(right[0]), int(left[1]) - int(right[1]))


def _iou(left: list[int], right: list[int]) -> float:
    left_x1, left_y1, left_x2, left_y2 = [int(value) for value in left]
    right_x1, right_y1, right_x2, right_y2 = [int(value) for value in right]
    inter_x1 = max(left_x1, right_x1)
    inter_y1 = max(left_y1, right_y1)
    inter_x2 = min(left_x2, right_x2)
    inter_y2 = min(left_y2, right_y2)
    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    if inter_width == 0 or inter_height == 0:
        return 0.0

    intersection = inter_width * inter_height
    left_area = max(1, (left_x2 - left_x1) * (left_y2 - left_y1))
    right_area = max(1, (right_x2 - right_x1) * (right_y2 - right_y1))
    union = left_area + right_area - intersection
    return intersection / union


def _bbox_center(bbox: list[int]) -> list[int]:
    return [int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _fmt_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())

