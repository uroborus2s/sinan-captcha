"""Prediction helpers with training-root defaults."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from train.base import _ensure_training_dependencies

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class PredictionJob:
    task: str
    model_path: Path
    source: Path
    project_dir: Path
    run_name: str
    conf: float = 0.25
    device: str = "0"
    imgsz: int = 640

    def output_dir(self) -> Path:
        return self.project_dir / self.run_name

    def command(self) -> list[str]:
        return [
            "uv",
            "run",
            "yolo",
            "detect",
            "predict",
            f"model={self.model_path}",
            f"source={self.source}",
            f"conf={self.conf:g}",
            f"device={self.device}",
            f"imgsz={self.imgsz}",
            f"project={self.project_dir}",
            f"name={self.run_name}",
            "save=True",
            "exist_ok=True",
        ]

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


def execute_prediction_job(job: PredictionJob) -> int:
    _ensure_training_dependencies()
    if not job.model_path.exists():
        raise RuntimeError(f"未找到预测权重文件：{job.model_path}")
    if not job.source.exists():
        raise RuntimeError(f"未找到预测输入路径：{job.source}")

    try:
        completed = subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到预测启动器 `uv run yolo`。请先安装 `uv`，并在当前训练环境中安装 "
            "`sinan-captcha[train]`。"
        ) from exc
    return completed.returncode


def count_images(path: Path) -> int:
    if path.is_file():
        return 1 if path.suffix.lower() in IMAGE_SUFFIXES else 0
    if not path.exists():
        return 0
    return sum(1 for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES)
