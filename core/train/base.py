"""Common training job helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class TrainingJob:
    task: str
    dataset_yaml: Path
    model: str
    epochs: int
    batch: int
    imgsz: int = 640
    device: str = "0"
    project_dir: Path | None = None
    run_name: str = "v1"

    def command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "yolo",
            "detect",
            "train",
            f"data={self.dataset_yaml}",
            f"model={self.model}",
            f"imgsz={self.imgsz}",
            f"epochs={self.epochs}",
            f"batch={self.batch}",
            f"device={self.device}",
            f"name={self.run_name}",
        ]
        if self.project_dir is not None:
            command.append(f"project={self.project_dir}")
        return command

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


def execute_training_job(job: TrainingJob) -> int:
    _ensure_training_dependencies()
    try:
        completed = subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到训练启动器 `uv run yolo`。请先安装 `uv`，并在当前训练环境中安装 "
            "`sinan-captcha[train]`。"
        ) from exc
    return completed.returncode


def _ensure_training_dependencies() -> None:
    if shutil.which("uv") is None:
        raise RuntimeError(
            "未检测到 `uv`。请先安装 uv，再进入训练目录执行 `uv sync` 完成环境安装。"
        )

    missing_packages: list[str] = []
    for package_name in ("torch", "ultralytics"):
        try:
            importlib.import_module(package_name)
        except Exception:
            missing_packages.append(package_name)

    if missing_packages:
        joined = "、".join(missing_packages)
        raise RuntimeError(
            "当前训练环境缺少依赖："
            f"{joined}。\n"
            "请先执行训练目录初始化或安装命令：\n"
            "1. uv run sinan env setup-train --train-root <训练目录>\n"
            "2. 进入训练目录后执行 uv sync\n"
            "3. 再运行 uv run sinan train group1|group2"
        )
