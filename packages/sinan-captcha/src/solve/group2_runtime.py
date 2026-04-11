"""Independent group2 runtime helpers for the training-repo solver path."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

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
        raise RuntimeError("当前环境缺少 `numpy` / `Pillow` / `torch`，无法准备 group2 solver 输入。") from exc

    master_image = Image.open(master_path).convert("L")
    tile_image = normalize_tile_rgba_image(Image.open(tile_path))
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


def normalize_tile_rgba_image(image: Any) -> Any:
    rgba = image.convert("RGBA")
    alpha_grid = _image_to_alpha_grid(rgba)
    if _alpha_grid_has_shape(alpha_grid):
        return rgba
    derived_alpha = derive_alpha_grid_from_rgb_grid(_image_to_rgb_grid(rgba.convert("RGB")))
    alpha_image = rgba.getchannel("A").copy()
    alpha_image.putdata([int(round(value * 255.0)) for row in derived_alpha for value in row])
    normalized = rgba.copy()
    normalized.putalpha(alpha_image)
    return normalized


def derive_alpha_grid_from_rgb_grid(
    rgb_grid: list[list[tuple[int, int, int]]],
) -> list[list[float]]:
    if not rgb_grid or not rgb_grid[0]:
        raise ValueError("rgb_grid must not be empty")
    width = len(rgb_grid[0])
    if any(len(row) != width for row in rgb_grid):
        raise ValueError("rgb_grid rows must have equal width")

    background_rgb = _estimate_border_background(rgb_grid)
    diff_grid = [
        [_rgb_distance(pixel, background_rgb) for pixel in row]
        for row in rgb_grid
    ]
    border_diffs = _border_values(diff_grid)
    threshold = max(12.0, _percentile(border_diffs, 0.95) + 8.0)
    if max(max(row) for row in diff_grid) <= threshold:
        return [[1.0 for _ in row] for row in rgb_grid]

    background = _background_region(diff_grid, threshold=threshold)
    alpha_grid = [
        [0.0 if background[row_index][column_index] else 1.0 for column_index in range(width)]
        for row_index in range(len(rgb_grid))
    ]
    if all(value <= 0.0 for row in alpha_grid for value in row):
        return [
            [1.0 if diff_grid[row_index][column_index] > threshold else 0.0 for column_index in range(width)]
            for row_index in range(len(rgb_grid))
        ]
    return alpha_grid


def load_checkpoint(path: Path, device: Any) -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - host env dependent
        raise RuntimeError("当前环境缺少 `torch`，无法加载 group2 solver 模型。") from exc
    if not path.exists():
        raise RuntimeError(f"未找到 group2 检查点：{path}")
    checkpoint = torch.load(path, map_location=device)
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise RuntimeError(f"group2 检查点格式非法：{path}")
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


def _image_to_alpha_grid(image: Any) -> list[list[float]]:
    alpha_image = image.getchannel("A")
    width, height = alpha_image.size
    pixels = list(alpha_image.getdata())
    return [
        [float(pixels[row * width + column]) / 255.0 for column in range(width)]
        for row in range(height)
    ]


def _image_to_rgb_grid(image: Any) -> list[list[tuple[int, int, int]]]:
    width, height = image.size
    pixels = list(image.getdata())
    return [
        [tuple(int(channel) for channel in pixels[row * width + column]) for column in range(width)]
        for row in range(height)
    ]


def _alpha_grid_has_shape(alpha_grid: list[list[float]]) -> bool:
    min_alpha = min(min(row) for row in alpha_grid)
    max_alpha = max(max(row) for row in alpha_grid)
    return max_alpha > 0.0 and min_alpha < 0.999


def _estimate_border_background(
    rgb_grid: list[list[tuple[int, int, int]]],
) -> tuple[float, float, float]:
    border_pixels = _border_values(rgb_grid)
    return tuple(_median([float(pixel[index]) for pixel in border_pixels]) for index in range(3))


def _background_region(diff_grid: list[list[float]], *, threshold: float) -> list[list[bool]]:
    height = len(diff_grid)
    width = len(diff_grid[0])
    visited = [[False for _ in range(width)] for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    def push_if_background(x: int, y: int) -> None:
        if visited[y][x] or diff_grid[y][x] > threshold:
            return
        visited[y][x] = True
        queue.append((x, y))

    for column in range(width):
        push_if_background(column, 0)
        push_if_background(column, height - 1)
    for row in range(height):
        push_if_background(0, row)
        push_if_background(width - 1, row)

    while queue:
        x, y = queue.popleft()
        for delta_x, delta_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_x = x + delta_x
            next_y = y + delta_y
            if next_x < 0 or next_x >= width or next_y < 0 or next_y >= height:
                continue
            push_if_background(next_x, next_y)
    return visited


def _border_values(grid: list[list[Any]]) -> list[Any]:
    height = len(grid)
    width = len(grid[0])
    values: list[Any] = []
    for column in range(width):
        values.append(grid[0][column])
        values.append(grid[height - 1][column])
    for row in range(height):
        values.append(grid[row][0])
        values.append(grid[row][width - 1])
    return values


def _median(values: list[float]) -> float:
    items = sorted(values)
    middle = len(items) // 2
    if len(items) % 2 == 1:
        return items[middle]
    return (items[middle - 1] + items[middle]) / 2.0


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    index = min(len(items) - 1, max(0, int(round((len(items) - 1) * ratio))))
    return items[index]


def _rgb_distance(pixel: tuple[int, int, int], background_rgb: tuple[float, float, float]) -> float:
    red, green, blue = pixel
    bg_red, bg_green, bg_blue = background_rgb
    return ((red - bg_red) ** 2 + (green - bg_green) ** 2 + (blue - bg_blue) ** 2) ** 0.5


def _load_torch_modules() -> tuple[Any, Any, Any]:
    try:
        import torch
        from torch import nn
        from torch.nn import functional
    except Exception as exc:  # pragma: no cover - host env dependent
        raise RuntimeError("当前环境缺少 `torch`，无法执行 group2 solver 运行时。") from exc
    return torch, nn, functional
