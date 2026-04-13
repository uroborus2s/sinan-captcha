"""Training runner adapter for the autonomous-training controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from auto_train import contracts
from auto_train.runners.common import RunnerExecutionError, classify_runtime_error, require_existing_path
from train.base import (
    default_best_weights,
    default_dataset_config,
    default_last_weights,
    default_project_dir,
    default_run_dir,
    execute_training_job,
    preferred_checkpoint_path,
    preferred_run_checkpoint,
)
from train.group1.dataset import load_group1_dataset_config
from train.group1.service import Group1TrainingJob, build_group1_training_job, execute_group1_training_job
from train.group1.service import (
    ALL_COMPONENTS,
    EMBEDDER_COMPONENT,
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    normalize_group1_component,
    resolve_group1_component_best_weights,
    resolve_group1_component_last_weights,
)
from train.group2.service import Group2TrainingJob, build_group2_training_job, execute_group2_training_job

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
    component: str | None = None


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
    group1_component = _resolve_group1_component(request) if request.task == "group1" else None
    model = _resolve_model(request, component=group1_component)
    command_text = ""

    if request.train_mode != "resume":
        require_existing_path(dataset_config, stage="TRAIN", label="训练数据集配置文件")

    group1_dataset = load_group1_dataset_config(dataset_config) if request.task == "group1" else None
    if request.train_mode in {"resume", "from_run"}:
        if request.task == "group1":
            component_resolver = (
                resolve_group1_component_last_weights
                if request.train_mode == "resume"
                else resolve_group1_component_best_weights
            )
            for component_name, label in _required_group1_components(
                dataset=group1_dataset,
                component=group1_component,
            ):
                require_existing_path(
                    component_resolver(
                        request.train_root,
                        request.train_name if request.train_mode == "resume" else request.base_run or "",
                        component_name,
                    ),
                    stage="TRAIN",
                    label=label,
                )
        else:
            require_existing_path(Path(model), stage="TRAIN", label="训练检查点")

    job = _build_training_job(
        request,
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=model,
        component=group1_component,
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
    if group1_component is not None:
        params["component"] = group1_component
    best_weights = default_best_weights(request.train_root, request.task, request.train_name)
    last_weights = default_last_weights(request.train_root, request.task, request.train_name)
    if request.task == "group1":
        output_component = _group1_output_component(group1_component)
        best_weights = resolve_group1_component_best_weights(request.train_root, request.train_name, output_component)
        last_weights = resolve_group1_component_last_weights(request.train_root, request.train_name, output_component)
        if group1_dataset is not None and group1_dataset.query_component is not None:
            params["query_model_best"] = str(
                resolve_group1_component_best_weights(request.train_root, request.train_name, QUERY_COMPONENT)
            )
            params["query_model_last"] = str(
                resolve_group1_component_last_weights(request.train_root, request.train_name, QUERY_COMPONENT)
            )
        if group1_dataset is not None and group1_dataset.is_instance_matching:
            params["embedder_model_best"] = str(
                resolve_group1_component_best_weights(request.train_root, request.train_name, EMBEDDER_COMPONENT)
            )
            params["embedder_model_last"] = str(
                resolve_group1_component_last_weights(request.train_root, request.train_name, EMBEDDER_COMPONENT)
            )
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


def _resolve_model(request: TrainRunnerRequest, *, component: str | None = None) -> str | None:
    if request.train_mode not in contracts.ALLOWED_TRAIN_MODES:
        raise RunnerExecutionError(
            stage="TRAIN",
            reason="invalid_request",
            message=f"不支持的 train_mode：{request.train_mode}",
            retryable=False,
        )

    if request.train_mode == "resume":
        if request.task == "group1":
            return str(
                resolve_group1_component_last_weights(
                    request.train_root,
                    request.train_name,
                    _group1_output_component(component),
                )
            )
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
            return str(
                _preferred_group1_component_weights(
                    request.train_root,
                    request.base_run,
                    _group1_output_component(component),
                )
            )
        return str(preferred_run_checkpoint(request.train_root, request.task, request.base_run))

    if request.model is not None:
        return request.model
    if request.task == "group1" and component == EMBEDDER_COMPONENT:
        return None
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
    model: str | None,
    component: str | None = None,
) -> object:
    if request.task == "group1":
        group1_dataset = load_group1_dataset_config(dataset_config)
        normalized_component = component or ALL_COMPONENTS
        query_model = None
        proposal_model = None
        embedder_model = None
        if request.train_mode == "resume":
            if group1_dataset.query_component is not None:
                query_model = str(resolve_group1_component_last_weights(request.train_root, request.train_name, QUERY_COMPONENT))
            proposal_model = str(resolve_group1_component_last_weights(request.train_root, request.train_name, PROPOSAL_COMPONENT))
            if group1_dataset.is_instance_matching:
                embedder_model = str(resolve_group1_component_last_weights(request.train_root, request.train_name, EMBEDDER_COMPONENT))
        elif request.train_mode == "from_run" and request.base_run is not None:
            if group1_dataset.query_component is not None:
                query_model = str(_preferred_group1_component_weights(request.train_root, request.base_run, QUERY_COMPONENT))
            proposal_model = str(_preferred_group1_component_weights(request.train_root, request.base_run, PROPOSAL_COMPONENT))
            if group1_dataset.is_instance_matching:
                embedder_model = str(_preferred_group1_component_weights(request.train_root, request.base_run, EMBEDDER_COMPONENT))
        return build_group1_training_job(
            dataset_config=dataset_config,
            project_dir=project_dir,
            model=model or _FRESH_DEFAULT_MODELS["group1"],
            query_model=query_model,
            proposal_model=proposal_model,
            embedder_model=embedder_model,
            run_name=request.train_name,
            component=normalized_component,
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


def _resolve_group1_component(request: TrainRunnerRequest) -> str:
    if request.component is None:
        return ALL_COMPONENTS
    return normalize_group1_component(request.component)


def _group1_output_component(component: str | None) -> str:
    if component in {None, ALL_COMPONENTS, PROPOSAL_COMPONENT}:
        return PROPOSAL_COMPONENT
    return component


def _required_group1_components(*, dataset: object, component: str | None) -> list[tuple[str, str]]:
    normalized = component or ALL_COMPONENTS
    results: list[tuple[str, str]] = []
    if normalized in {ALL_COMPONENTS, QUERY_COMPONENT} and getattr(dataset, "query_component", None) is not None:
        results.append((QUERY_COMPONENT, "group1 query detector 检查点"))
    if normalized in {ALL_COMPONENTS, PROPOSAL_COMPONENT}:
        results.append((PROPOSAL_COMPONENT, "group1 proposal detector 检查点"))
    if normalized in {ALL_COMPONENTS, EMBEDDER_COMPONENT} and getattr(dataset, "is_instance_matching", False):
        results.append((EMBEDDER_COMPONENT, "group1 icon embedder 检查点"))
    return results
