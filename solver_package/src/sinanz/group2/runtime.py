"""Independent group2 runtime helpers for the standalone solver package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import SolverRuntimeError

FEATURE_STRIDE = 4
DEFAULT_IMGSZ = 192


def create_model() -> Any:
    torch, nn, functional = _load_torch_modules()

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

        def forward(self, inputs: Any) -> Any:
            return self.layers(inputs)

    class PairedGapLocator(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.master_encoder = CorrelationEncoder()
            self.tile_encoder = CorrelationEncoder()

        def forward(self, master: Any, tile: Any) -> Any:
            master_features = functional.normalize(self.master_encoder(master), dim=1)
            tile_features = self.tile_encoder(tile)

            responses: list[Any] = []
            for index in range(master_features.shape[0]):
                kernel = tile_features[index : index + 1]
                kernel = kernel / kernel.flatten(1).norm(dim=1, keepdim=True).clamp_min(1e-6).view(1, 1, 1, 1)
                responses.append(functional.conv2d(master_features[index : index + 1], kernel))
            return torch.cat(responses, dim=0)

    return PairedGapLocator()


def load_model(path: Path, raw_device: str) -> tuple[Any, int, Any]:
    torch_device = resolve_device(raw_device)
    checkpoint = load_checkpoint(path, torch_device)
    model = create_model().to(torch_device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    imgsz = int(checkpoint.get("imgsz", DEFAULT_IMGSZ))
    return model, imgsz, torch_device


def prepare_inputs(*, master_path: Path, tile_path: Path, imgsz: int) -> tuple[Any, Any, dict[str, Any]]:
    try:
        import numpy as np
        from PIL import Image
        import torch
    except Exception as exc:  # pragma: no cover - host env dependent
        raise SolverRuntimeError("当前环境缺少 `numpy` / `Pillow` / `torch`，无法准备滑块求解输入。") from exc

    master_image = Image.open(master_path).convert("L")
    tile_image = Image.open(tile_path).convert("RGBA")
    master_width, master_height = master_image.size
    tile_width, tile_height = tile_image.size
    scale_x = imgsz / float(master_width)
    scale_y = imgsz / float(master_height)
    resized_tile_width = max(1, int(round(tile_width * scale_x)))
    resized_tile_height = max(1, int(round(tile_height * scale_y)))

    master_tensor = _image_to_tensor(
        torch,
        np,
        master_image.resize((imgsz, imgsz)),
    ).unsqueeze(0)
    tile_tensor = _rgba_tile_to_tensor(
        torch,
        np,
        tile_image.resize((resized_tile_width, resized_tile_height)),
    ).unsqueeze(0)
    meta = {
        "master_width": master_width,
        "master_height": master_height,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "response_width": max(1, imgsz // FEATURE_STRIDE - resized_tile_width // FEATURE_STRIDE + 1),
        "response_height": max(1, imgsz // FEATURE_STRIDE - resized_tile_height // FEATURE_STRIDE + 1),
    }
    return master_tensor, tile_tensor, meta


def decode_bbox(response: Any, meta: dict[str, Any]) -> list[int]:
    response_width = int(meta["response_width"])
    index = int(response.flatten().argmax().item())
    _, feature_x = divmod(index, response_width)
    feature_y = index // response_width
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


def bbox_center(bbox: list[int]) -> list[int]:
    return [int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)]


def load_checkpoint(path: Path, device: Any) -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - host env dependent
        raise SolverRuntimeError("当前环境缺少 `torch`，无法加载滑块模型。") from exc
    if not path.exists():
        raise SolverRuntimeError(f"未找到滑块模型文件：{path}")
    checkpoint = torch.load(path, map_location=device)
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise SolverRuntimeError(f"滑块模型文件格式非法：{path}")
    return checkpoint


def resolve_device(raw_device: str) -> Any:
    torch, _, _ = _load_torch_modules()
    if raw_device == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device(f"cuda:{raw_device}")
    return torch.device("cpu")


def torch_no_grad() -> Any:
    torch, _, _ = _load_torch_modules()
    return torch.no_grad()


def _image_to_tensor(torch: Any, np: Any, image: Any) -> Any:
    array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


def _rgba_tile_to_tensor(torch: Any, np: Any, image: Any) -> Any:
    rgba = np.asarray(image, dtype=np.float32)
    rgb = rgba[:, :, :3].mean(axis=2)
    alpha = rgba[:, :, 3] / 255.0
    return torch.from_numpy((rgb * alpha / 255.0).astype(np.float32)).unsqueeze(0)


def _load_torch_modules() -> tuple[Any, Any, Any]:
    try:
        import torch
        from torch import nn
        from torch.nn import functional
    except Exception as exc:  # pragma: no cover - host env dependent
        raise SolverRuntimeError("当前环境缺少 `torch`，无法执行滑块求解运行时。") from exc
    return torch, nn, functional
