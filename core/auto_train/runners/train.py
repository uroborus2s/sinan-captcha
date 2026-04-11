"""Training runner adapter for the autonomous-training controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from core.auto_train import contracts
from core.auto_train.runners.common import RunnerExecutionError, classify_runtime_error, require_existing_path
from core.train.base import (
    default_best_weights,
    default_dataset_config,
    default_last_weights,
    default_project_dir,
    default_run_dir,
    execute_training_job,
    preferred_checkpoint_path,
    preferred_run_checkpoint,
)
from core.train.group1.service import Group1TrainingJob, build_group1_training_job, execute_group1_training_job
from core.train.group1.service import (
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    resolve_group1_component_best_weights,
    resolve_group1_component_last_weights,
)
from core.train.group2.service import Group2TrainingJob, build_group2_training_job, execute_group2_training_job

TrainingExecutor = Callable[[object], int]

_FRESH_DEFAULT_MODELS = {
    "group1": "yolo26n.pt",
    "group2": "paired_cnn_v1",
}


@dataclass(frozen=True)
class TrainRunnerRequest:
    task: str
    train_root: Path
    dataset_version: str
    train_name: str
    train_mode: str = "fresh"
    base_run: str | None = None
    model: str | None = None
    epochs: int | None = None
    batch: int | None = None
    imgsz: int = 640
    device: str = "0"


@dataclass(frozen=True)
class TrainRunnerResult:
    record: contracts.TrainRecord
    command: str


def run_training_request(
    request: TrainRunnerRequest,
    *,
    executor: TrainingExecutor | None = None,
) -> TrainRunnerResult:
    """Build and execute one training job without leaking CLI details into the controller."""

    dataset_config = default_dataset_config(request.train_root, request.task, request.dataset_version)
    project_dir = default_project_dir(request.train_root, request.task)
    model = _resolve_model(request)
    command_text = ""

    if request.train_mode != "resume":
        require_existing_path(dataset_config, stage="TRAIN", label="训练数据集配置文件")

    if request.train_mode in {"resume", "from_run"}:
        if request.task == "group1":
            component_resolver = (
                resolve_group1_component_last_weights
                if request.train_mode == "resume"
                else resolve_group1_component_best_weights
            )
            require_existing_path(
                component_resolver(request.train_root, request.train_name if request.train_mode == "resume" else request.base_run or "", PROPOSAL_COMPONENT),
                stage="TRAIN",
                label="group1 proposal detector 检查点",
            )
            require_existing_path(
                component_resolver(request.train_root, request.train_name if request.train_mode == "resume" else request.base_run or "", QUERY_COMPONENT),
                stage="TRAIN",
                label="group1 query parser 检查点",
            )
        else:
            require_existing_path(Path(model), stage="TRAIN", label="训练检查点")

    job = _build_training_job(
        request,
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=model,
    )
    command_text = job.command_string()

    try:
        if executor is not None:
            return_code = executor(job)
        elif request.task == "group2":
            assert isinstance(job, Group2TrainingJob)
            return_code = execute_group2_training_job(job)
        elif request.task == "group1":
            assert isinstance(job, Group1TrainingJob)
            return_code = execute_group1_training_job(job)
        else:
            return_code = execute_training_job(job)
    except subprocess.CalledProcessError as exc:
        raise RunnerExecutionError(
            stage="TRAIN",
            reason="command_failed",
            message=f"训练命令执行失败，退出码：{exc.returncode}",
            retryable=True,
            command=command_text,
        ) from exc
    except RuntimeError as exc:
        raise classify_runtime_error("TRAIN", str(exc), command=command_text) from exc

    if return_code != 0:
        raise RunnerExecutionError(
            stage="TRAIN",
            reason="command_failed",
            message=f"训练命令返回非零状态：{return_code}",
            retryable=True,
            command=command_text,
        )

    dataset_key = "dataset_config" if request.task in {"group1", "group2"} else "dataset_yaml"
    params = {
        "dataset_version": request.dataset_version,
        dataset_key: str(dataset_config),
        "train_mode": request.train_mode,
        "model": model,
        "epochs": job.epochs,
        "batch": job.batch,
        "imgsz": job.imgsz,
        "device": job.device,
    }
    best_weights = default_best_weights(request.train_root, request.task, request.train_name)
    last_weights = default_last_weights(request.train_root, request.task, request.train_name)
    if request.task == "group1":
        best_weights = resolve_group1_component_best_weights(request.train_root, request.train_name, PROPOSAL_COMPONENT)
        last_weights = resolve_group1_component_last_weights(request.train_root, request.train_name, PROPOSAL_COMPONENT)
        params["query_model_best"] = str(resolve_group1_component_best_weights(request.train_root, request.train_name, QUERY_COMPONENT))
        params["query_model_last"] = str(resolve_group1_component_last_weights(request.train_root, request.train_name, QUERY_COMPONENT))
    return TrainRunnerResult(
        record=contracts.TrainRecord(
            task=request.task,
            train_name=request.train_name,
            run_dir=str(default_run_dir(request.train_root, request.task, request.train_name)),
            params=params,
            best_weights=str(best_weights),
            last_weights=str(last_weights),
            resumed_from=request.base_run if request.train_mode == "from_run" else request.train_name if request.train_mode == "resume" else None,
        ),
        command=command_text,
    )


def _resolve_model(request: TrainRunnerRequest) -> str:
    if request.train_mode not in contracts.ALLOWED_TRAIN_MODES:
        raise RunnerExecutionError(
            stage="TRAIN",
            reason="invalid_request",
            message=f"不支持的 train_mode：{request.train_mode}",
            retryable=False,
        )

    if request.train_mode == "resume":
        if request.task == "group1":
            return str(resolve_group1_component_last_weights(request.train_root, request.train_name, PROPOSAL_COMPONENT))
        return request.model or str(default_last_weights(request.train_root, request.task, request.train_name))

    if request.train_mode == "from_run":
        if request.base_run is None:
            raise RunnerExecutionError(
                stage="TRAIN",
                reason="invalid_request",
                message="train_mode=from_run 时必须提供 base_run。",
                retryable=False,
            )
        if request.model is not None:
            raise RunnerExecutionError(
                stage="TRAIN",
                reason="invalid_request",
                message="train_mode=from_run 时不要再显式传入 model。",
                retryable=False,
            )
        if request.task == "group1":
            return str(_preferred_group1_component_weights(request.train_root, request.base_run, PROPOSAL_COMPONENT))
        return str(preferred_run_checkpoint(request.train_root, request.task, request.base_run))

    if request.model is not None:
        return request.model
    try:
        return _FRESH_DEFAULT_MODELS[request.task]
    except KeyError as exc:
        raise RunnerExecutionError(
            stage="TRAIN",
            reason="invalid_request",
            message=f"不支持的训练任务：{request.task}",
            retryable=False,
        ) from exc


def _build_training_job(
    request: TrainRunnerRequest,
    *,
    dataset_config: Path,
    project_dir: Path,
    model: str,
) -> object:
    if request.task == "group1":
        proposal_model = None
        query_model = None
        if request.train_mode == "resume":
            proposal_model = str(resolve_group1_component_last_weights(request.train_root, request.train_name, PROPOSAL_COMPONENT))
            query_model = str(resolve_group1_component_last_weights(request.train_root, request.train_name, QUERY_COMPONENT))
        elif request.train_mode == "from_run" and request.base_run is not None:
            proposal_model = str(_preferred_group1_component_weights(request.train_root, request.base_run, PROPOSAL_COMPONENT))
            query_model = str(_preferred_group1_component_weights(request.train_root, request.base_run, QUERY_COMPONENT))
        return build_group1_training_job(
            dataset_config=dataset_config,
            project_dir=project_dir,
            model=model,
            proposal_model=proposal_model,
            query_model=query_model,
            run_name=request.train_name,
            epochs=request.epochs,
            batch=request.batch,
            imgsz=request.imgsz,
            device=request.device,
            resume=request.train_mode == "resume",
        )
    if request.task == "group2":
        return build_group2_training_job(
            dataset_config=dataset_config,
            project_dir=project_dir,
            model=model,
            run_name=request.train_name,
            epochs=request.epochs,
            batch=request.batch,
            imgsz=request.imgsz,
            device=request.device,
            resume=request.train_mode == "resume",
        )
    raise RunnerExecutionError(
        stage="TRAIN",
        reason="invalid_request",
        message=f"不支持的训练任务：{request.task}",
        retryable=False,
    )


def _preferred_group1_component_weights(train_root: Path, run_name: str, component: str) -> Path:
    best = resolve_group1_component_best_weights(train_root, run_name, component)
    last = resolve_group1_component_last_weights(train_root, run_name, component)
    return preferred_checkpoint_path(best, last)
