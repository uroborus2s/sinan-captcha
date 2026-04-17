"""Query/proposal detector + icon-embedder job helpers for group1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from common.jsonl import read_jsonl
from train.base import _ensure_training_dependencies
from train.group1.dataset import load_group1_dataset_config

ALL_COMPONENTS = "all"
QUERY_COMPONENT = "query-detector"
PROPOSAL_COMPONENT = "proposal-detector"
EMBEDDER_COMPONENT = "icon-embedder"
DEFAULT_ICON_EMBEDDER_IMGSZ = 96
DEFAULT_ICON_EMBEDDER_BATCH = 32


@dataclass(frozen=True)
class EmbedderReviewConfig:
    provider: str | None = None
    model: str | None = None
    project_root: Path | None = None
    study_name: str | None = None
    task: str | None = None
    trial_id: str | None = None
    stage: str | None = None
    attach_url: str | None = None
    binary: str | None = None
    timeout_seconds: float | None = None
    min_epochs: int | None = None
    window: int | None = None
    rebuild_count: int = 0

    @property
    def enabled(self) -> bool:
        return bool(
            self.provider
            and self.model
            and self.project_root is not None
            and self.study_name
            and self.task
            and self.trial_id
            and self.stage
        )


@dataclass(frozen=True)
class Group1TrainingJob:
    dataset_config: Path
    project_dir: Path
    query_model: str | None
    proposal_model: str | None
    embedder_model: str | None
    epochs: int
    batch: int
    run_name: str
    component: str = ALL_COMPONENTS
    imgsz: int = 640
    device: str = "0"
    resume: bool = False
    embedder_review: EmbedderReviewConfig | None = None
    interim_trial_dir: Path | None = None
    interim_primary_metric: str | None = None

    def command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "python",
            "-m",
            "train.group1.runner",
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
        if self.query_model is not None:
            command.extend(["--query-model", self.query_model])
        if self.proposal_model is not None:
            command.extend(["--proposal-model", self.proposal_model])
        if self.embedder_model is not None:
            command.extend(["--embedder-model", self.embedder_model])
        if self.resume:
            command.append("--resume")
        if self.embedder_review is not None and self.embedder_review.enabled:
            command.extend(["--review-provider", str(self.embedder_review.provider)])
            command.extend(["--review-model", str(self.embedder_review.model)])
            command.extend(["--review-project-root", str(self.embedder_review.project_root)])
            command.extend(["--review-study-name", str(self.embedder_review.study_name)])
            command.extend(["--review-task", str(self.embedder_review.task)])
            command.extend(["--review-trial-id", str(self.embedder_review.trial_id)])
            command.extend(["--review-stage", str(self.embedder_review.stage)])
            command.extend(["--review-rebuild-count", str(self.embedder_review.rebuild_count)])
            if self.embedder_review.attach_url is not None:
                command.extend(["--review-attach-url", self.embedder_review.attach_url])
            if self.embedder_review.binary is not None:
                command.extend(["--review-binary", self.embedder_review.binary])
            if self.embedder_review.timeout_seconds is not None:
                command.extend(["--review-timeout-seconds", str(self.embedder_review.timeout_seconds)])
            if self.embedder_review.min_epochs is not None:
                command.extend(["--review-min-epochs", str(self.embedder_review.min_epochs)])
            if self.embedder_review.window is not None:
                command.extend(["--review-window", str(self.embedder_review.window)])
        if self.interim_trial_dir is not None:
            command.extend(["--interim-trial-dir", str(self.interim_trial_dir)])
        if self.interim_primary_metric is not None:
            command.extend(["--interim-primary-metric", self.interim_primary_metric])
        return command

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group1PredictionJob:
    dataset_config: Path
    query_detector_model_path: Path | None
    proposal_model_path: Path
    embedder_model_path: Path | None
    source: Path
    project_dir: Path
    run_name: str
    conf: float = 0.25
    imgsz: int = 640
    device: str = "0"
    similarity_threshold: float | None = None
    ambiguity_margin: float | None = None

    def output_dir(self) -> Path:
        return self.project_dir / self.run_name

    def command(self) -> list[str]:
        return [
            "uv",
            "run",
            "python",
            "-m",
            "train.group1.runner",
            "predict",
            "--dataset-config",
            str(self.dataset_config),
            *(["--query-model", str(self.query_detector_model_path)] if self.query_detector_model_path is not None else []),
            "--proposal-model",
            str(self.proposal_model_path),
            *(["--embedder-model", str(self.embedder_model_path)] if self.embedder_model_path is not None else []),
            "--source",
            str(self.source),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--conf",
            f"{self.conf:g}",
            *(["--similarity-threshold", f"{self.similarity_threshold:g}"] if self.similarity_threshold is not None else []),
            *(["--ambiguity-margin", f"{self.ambiguity_margin:g}"] if self.ambiguity_margin is not None else []),
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
    query_model: str | None = None,
    proposal_model: str | None = None,
    embedder_model: str | None = None,
    epochs: int | None = None,
    batch: int | None = None,
    component: str = ALL_COMPONENTS,
    imgsz: int = 640,
    device: str = "0",
    resume: bool = False,
    embedder_review: EmbedderReviewConfig | None = None,
    interim_trial_dir: Path | None = None,
    interim_primary_metric: str | None = None,
) -> Group1TrainingJob:
    normalized_component = normalize_group1_component(component)
    resolved_query_model = query_model or model
    resolved_proposal_model = proposal_model or model
    resolved_embedder_model = embedder_model
    resolved_imgsz = imgsz
    resolved_batch = 16 if batch is None else batch
    if normalized_component == QUERY_COMPONENT:
        resolved_proposal_model = None
        resolved_embedder_model = None
    elif normalized_component == PROPOSAL_COMPONENT:
        resolved_query_model = None
        resolved_embedder_model = None
    elif normalized_component == EMBEDDER_COMPONENT:
        resolved_query_model = None
        resolved_proposal_model = None
        if imgsz == 640:
            resolved_imgsz = DEFAULT_ICON_EMBEDDER_IMGSZ
        if batch is None:
            resolved_batch = DEFAULT_ICON_EMBEDDER_BATCH
    return Group1TrainingJob(
        dataset_config=dataset_config,
        project_dir=project_dir,
        query_model=resolved_query_model,
        proposal_model=resolved_proposal_model,
        embedder_model=resolved_embedder_model,
        epochs=120 if epochs is None else epochs,
        batch=resolved_batch,
        run_name=run_name,
        component=normalized_component,
        imgsz=resolved_imgsz,
        device=device,
        resume=resume,
        embedder_review=embedder_review if normalized_component == EMBEDDER_COMPONENT else None,
        interim_trial_dir=interim_trial_dir if normalized_component == EMBEDDER_COMPONENT else None,
        interim_primary_metric=interim_primary_metric if normalized_component == EMBEDDER_COMPONENT else None,
    )


def build_group1_prediction_job(
    dataset_config: Path,
    proposal_model_path: Path,
    source: Path,
    project_dir: Path,
    run_name: str,
    *,
    query_detector_model_path: Path | None = None,
    embedder_model_path: Path | None = None,
    conf: float = 0.25,
    imgsz: int = 640,
    device: str = "0",
    similarity_threshold: float | None = None,
    ambiguity_margin: float | None = None,
) -> Group1PredictionJob:
    return Group1PredictionJob(
        dataset_config=dataset_config,
        query_detector_model_path=query_detector_model_path,
        proposal_model_path=proposal_model_path,
        embedder_model_path=embedder_model_path,
        source=source,
        project_dir=project_dir,
        run_name=run_name,
        conf=conf,
        imgsz=imgsz,
        device=device,
        similarity_threshold=similarity_threshold,
        ambiguity_margin=ambiguity_margin,
    )


def execute_group1_training_job(job: Group1TrainingJob) -> int:
    _ensure_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group1 数据集配置文件：{job.dataset_config}")
    for component_name, model in (
        (QUERY_COMPONENT, job.query_model),
        (PROPOSAL_COMPONENT, job.proposal_model),
        (EMBEDDER_COMPONENT, job.embedder_model),
    ):
        if model is None:
            continue
        if job.resume and Path(model).suffix == ".pt" and not Path(model).exists():
            raise RuntimeError(f"未找到 group1 {component_name} 可继续训练的检查点：{model}")
    try:
        completed = subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group1 双模型训练启动器 `uv run python -m train.group1.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc
    return completed.returncode


def run_group1_prediction_job(job: Group1PredictionJob) -> Group1PredictionResult:
    _ensure_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group1 数据集配置文件：{job.dataset_config}")
    dataset_config = load_group1_dataset_config(job.dataset_config)
    if job.query_detector_model_path is not None and not job.query_detector_model_path.exists():
        raise RuntimeError(f"未找到 group1 query detector 权重：{job.query_detector_model_path}")
    if not job.proposal_model_path.exists():
        raise RuntimeError(f"未找到 group1 proposal detector 权重：{job.proposal_model_path}")
    if dataset_config.is_instance_matching and job.embedder_model_path is None:
        raise RuntimeError("group1 instance-matching 预测缺少 icon embedder 权重。")
    if dataset_config.is_instance_matching and not job.embedder_model_path.exists():
        raise RuntimeError(f"未找到 group1 icon embedder 权重：{job.embedder_model_path}")
    if not job.source.exists():
        raise RuntimeError(f"未找到 group1 预测输入：{job.source}")

    try:
        subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group1 预测启动器 `uv run python -m train.group1.runner`。"
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
    return train_root / "runs" / "group1" / run_name / normalize_group1_component(component) / "weights" / "best.pt"


def group1_component_last_weights(train_root: Path, run_name: str, component: str) -> Path:
    return train_root / "runs" / "group1" / run_name / normalize_group1_component(component) / "weights" / "last.pt"


def resolve_group1_component_best_weights(train_root: Path, run_name: str, component: str) -> Path:
    return group1_component_best_weights(train_root, run_name, component)


def resolve_group1_component_last_weights(train_root: Path, run_name: str, component: str) -> Path:
    return group1_component_last_weights(train_root, run_name, component)


def normalize_group1_component(component: str) -> str:
    normalized = component.strip()
    if normalized in {ALL_COMPONENTS, QUERY_COMPONENT, PROPOSAL_COMPONENT, EMBEDDER_COMPONENT}:
        return normalized
    raise RuntimeError(f"不支持的 group1 训练组件：{component}")
