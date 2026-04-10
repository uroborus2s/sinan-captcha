"""Two-model training and prediction job helpers for group1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from core.common.jsonl import read_jsonl
from core.train.base import _ensure_training_dependencies

ALL_COMPONENTS = "all"
SCENE_COMPONENT = "scene-detector"
QUERY_COMPONENT = "query-parser"


@dataclass(frozen=True)
class Group1TrainingJob:
    dataset_config: Path
    project_dir: Path
    scene_model: str | None
    query_model: str | None
    epochs: int
    batch: int
    run_name: str
    component: str = ALL_COMPONENTS
    imgsz: int = 640
    device: str = "0"
    resume: bool = False

    def command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "python",
            "-m",
            "core.train.group1.runner",
            "train",
            "--dataset-config",
            str(self.dataset_config),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--component",
            self.component,
            "--epochs",
            str(self.epochs),
            "--batch",
            str(self.batch),
            "--imgsz",
            str(self.imgsz),
            "--device",
            self.device,
        ]
        if self.scene_model is not None:
            command.extend(["--scene-model", self.scene_model])
        if self.query_model is not None:
            command.extend(["--query-model", self.query_model])
        if self.resume:
            command.append("--resume")
        return command

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group1PredictionJob:
    dataset_config: Path
    scene_model_path: Path
    query_model_path: Path
    source: Path
    project_dir: Path
    run_name: str
    conf: float = 0.25
    imgsz: int = 640
    device: str = "0"

    def output_dir(self) -> Path:
        return self.project_dir / self.run_name

    def command(self) -> list[str]:
        return [
            "uv",
            "run",
            "python",
            "-m",
            "core.train.group1.runner",
            "predict",
            "--dataset-config",
            str(self.dataset_config),
            "--scene-model",
            str(self.scene_model_path),
            "--query-model",
            str(self.query_model_path),
            "--source",
            str(self.source),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--conf",
            f"{self.conf:g}",
            "--imgsz",
            str(self.imgsz),
            "--device",
            self.device,
        ]

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group1PredictionResult:
    output_dir: Path
    labels_path: Path
    sample_count: int
    command: str


def build_group1_training_job(
    dataset_config: Path,
    project_dir: Path,
    model: str = "yolo26n.pt",
    run_name: str = "v1",
    *,
    scene_model: str | None = None,
    query_model: str | None = None,
    epochs: int | None = None,
    batch: int | None = None,
    component: str = ALL_COMPONENTS,
    imgsz: int = 640,
    device: str = "0",
    resume: bool = False,
) -> Group1TrainingJob:
    if component not in {ALL_COMPONENTS, SCENE_COMPONENT, QUERY_COMPONENT}:
        raise RuntimeError(f"不支持的 group1 训练组件：{component}")
    resolved_scene_model = scene_model or model
    resolved_query_model = query_model or model
    if component == SCENE_COMPONENT:
        resolved_query_model = None
    elif component == QUERY_COMPONENT:
        resolved_scene_model = None
    return Group1TrainingJob(
        dataset_config=dataset_config,
        project_dir=project_dir,
        scene_model=resolved_scene_model,
        query_model=resolved_query_model,
        epochs=120 if epochs is None else epochs,
        batch=16 if batch is None else batch,
        run_name=run_name,
        component=component,
        imgsz=imgsz,
        device=device,
        resume=resume,
    )


def build_group1_prediction_job(
    dataset_config: Path,
    scene_model_path: Path,
    query_model_path: Path,
    source: Path,
    project_dir: Path,
    run_name: str,
    *,
    conf: float = 0.25,
    imgsz: int = 640,
    device: str = "0",
) -> Group1PredictionJob:
    return Group1PredictionJob(
        dataset_config=dataset_config,
        scene_model_path=scene_model_path,
        query_model_path=query_model_path,
        source=source,
        project_dir=project_dir,
        run_name=run_name,
        conf=conf,
        imgsz=imgsz,
        device=device,
    )


def execute_group1_training_job(job: Group1TrainingJob) -> int:
    _ensure_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group1 数据集配置文件：{job.dataset_config}")
    for component_name, model in (
        (SCENE_COMPONENT, job.scene_model),
        (QUERY_COMPONENT, job.query_model),
    ):
        if model is None:
            continue
        if job.resume and Path(model).suffix == ".pt" and not Path(model).exists():
            raise RuntimeError(f"未找到 group1 {component_name} 可继续训练的检查点：{model}")
    try:
        completed = subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group1 双模型训练启动器 `uv run python -m core.train.group1.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc
    return completed.returncode


def run_group1_prediction_job(job: Group1PredictionJob) -> Group1PredictionResult:
    _ensure_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group1 数据集配置文件：{job.dataset_config}")
    if not job.scene_model_path.exists():
        raise RuntimeError(f"未找到 group1 scene detector 权重：{job.scene_model_path}")
    if not job.query_model_path.exists():
        raise RuntimeError(f"未找到 group1 query parser 权重：{job.query_model_path}")
    if not job.source.exists():
        raise RuntimeError(f"未找到 group1 预测输入：{job.source}")

    try:
        subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group1 预测启动器 `uv run python -m core.train.group1.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc

    labels_path = job.output_dir() / "labels.jsonl"
    if not labels_path.exists():
        raise RuntimeError(f"group1 预测输出缺少 labels.jsonl：{labels_path}")
    return Group1PredictionResult(
        output_dir=job.output_dir(),
        labels_path=labels_path,
        sample_count=len(read_jsonl(labels_path)),
        command=job.command_string(),
    )


def group1_component_best_weights(train_root: Path, run_name: str, component: str) -> Path:
    return train_root / "runs" / "group1" / run_name / component / "weights" / "best.pt"


def group1_component_last_weights(train_root: Path, run_name: str, component: str) -> Path:
    return train_root / "runs" / "group1" / run_name / component / "weights" / "last.pt"
