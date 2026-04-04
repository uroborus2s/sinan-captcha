"""Paired-input group2 training and prediction job helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import shutil
import subprocess

from core.common.jsonl import read_jsonl


@dataclass(frozen=True)
class Group2TrainingJob:
    dataset_config: Path
    project_dir: Path
    model: str
    epochs: int
    batch: int
    run_name: str
    imgsz: int = 192
    device: str = "0"
    resume: bool = False

    def command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "python",
            "-m",
            "core.train.group2.runner",
            "train",
            "--dataset-config",
            str(self.dataset_config),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--model",
            self.model,
            "--epochs",
            str(self.epochs),
            "--batch",
            str(self.batch),
            "--imgsz",
            str(self.imgsz),
            "--device",
            self.device,
        ]
        if self.resume:
            command.append("--resume")
        return command

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group2PredictionJob:
    dataset_config: Path
    model_path: Path
    source: Path
    project_dir: Path
    run_name: str
    imgsz: int = 192
    device: str = "0"

    def output_dir(self) -> Path:
        return self.project_dir / self.run_name

    def command(self) -> list[str]:
        return [
            "uv",
            "run",
            "python",
            "-m",
            "core.train.group2.runner",
            "predict",
            "--dataset-config",
            str(self.dataset_config),
            "--model",
            str(self.model_path),
            "--source",
            str(self.source),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--imgsz",
            str(self.imgsz),
            "--device",
            self.device,
        ]

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group2PredictionResult:
    output_dir: Path
    labels_path: Path
    sample_count: int
    command: str


def build_group2_training_job(
    dataset_config: Path,
    project_dir: Path,
    model: str = "paired_cnn_v1",
    run_name: str = "v1",
    *,
    epochs: int | None = None,
    batch: int | None = None,
    imgsz: int = 192,
    device: str = "0",
    resume: bool = False,
) -> Group2TrainingJob:
    return Group2TrainingJob(
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=model,
        epochs=100 if epochs is None else epochs,
        batch=16 if batch is None else batch,
        run_name=run_name,
        imgsz=imgsz,
        device=device,
        resume=resume,
    )


def build_group2_prediction_job(
    dataset_config: Path,
    model_path: Path,
    source: Path,
    project_dir: Path,
    run_name: str,
    *,
    imgsz: int = 192,
    device: str = "0",
) -> Group2PredictionJob:
    return Group2PredictionJob(
        dataset_config=dataset_config,
        model_path=model_path,
        source=source,
        project_dir=project_dir,
        run_name=run_name,
        imgsz=imgsz,
        device=device,
    )


def execute_group2_training_job(job: Group2TrainingJob) -> int:
    _ensure_group2_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group2 数据集配置文件：{job.dataset_config}")
    if job.resume and Path(job.model).suffix == ".pt" and not Path(job.model).exists():
        raise RuntimeError(f"未找到可继续训练的检查点：{job.model}")
    try:
        completed = subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group2 训练启动器 `uv run python -m core.train.group2.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc
    return completed.returncode


def run_group2_prediction_job(job: Group2PredictionJob) -> Group2PredictionResult:
    _ensure_group2_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group2 数据集配置文件：{job.dataset_config}")
    if not job.model_path.exists():
        raise RuntimeError(f"未找到 group2 预测权重文件：{job.model_path}")
    if not job.source.exists():
        raise RuntimeError(f"未找到 group2 预测输入：{job.source}")

    try:
        subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group2 预测启动器 `uv run python -m core.train.group2.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc

    labels_path = job.output_dir() / "labels.jsonl"
    if not labels_path.exists():
        raise RuntimeError(f"group2 预测输出缺少 labels.jsonl：{labels_path}")
    return Group2PredictionResult(
        output_dir=job.output_dir(),
        labels_path=labels_path,
        sample_count=len(read_jsonl(labels_path)),
        command=job.command_string(),
    )


def _ensure_group2_training_dependencies() -> None:
    if shutil.which("uv") is None:
        raise RuntimeError(
            "未检测到 `uv`。请先安装 uv，再进入训练目录执行 `uv sync` 完成环境安装。"
        )

    missing_packages: list[str] = []
    for package_name in ("torch", "numpy", "PIL"):
        try:
            importlib.import_module(package_name)
        except Exception:
            missing_packages.append(package_name)

    if missing_packages:
        joined = "、".join(missing_packages)
        raise RuntimeError(
            "当前 group2 双输入训练环境缺少依赖："
            f"{joined}。\n"
            "请先执行训练目录初始化或安装命令：\n"
            "1. uv run sinan env setup-train --train-root <训练目录>\n"
            "2. 进入训练目录后执行 uv sync\n"
            "3. 再运行 uv run sinan train group2"
        )
