"""Model-test runner adapter for the autonomous-training controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from auto_train import contracts
from auto_train.runners.common import RunnerExecutionError, classify_runtime_error, require_existing_path
from modeltest.service import ModelTestRequest, ModelTestResult, run_model_test
from train.base import (
    default_best_weights,
    default_dataset_config,
    default_predict_source,
    default_report_dir,
)
from train.group1.dataset import load_group1_dataset_config
from train.group1.service import (
    EMBEDDER_COMPONENT,
    PROPOSAL_COMPONENT,
    QUERY_COMPONENT,
    resolve_group1_component_best_weights,
)

ModelTestExecutor = Callable[[ModelTestRequest], ModelTestResult]


@dataclass(frozen=True)
class TestRunnerRequest:
    task: str
    train_root: Path
    dataset_version: str
    train_name: str
    dataset_config: Path | None = None
    model_path: Path | None = None
    query_model_path: Path | None = None
    embedder_model_path: Path | None = None
    source: Path | None = None
    project_dir: Path | None = None
    report_dir: Path | None = None
    predict_name: str | None = None
    val_name: str | None = None
    conf: float = 0.25
    device: str = "0"
    imgsz: int = 640


@dataclass(frozen=True)
class TestRunnerResult:
    record: contracts.TestRecord
    predict_command: str
    val_command: str


def run_test_request(
    request: TestRunnerRequest,
    *,
    runner: ModelTestExecutor | None = None,
) -> TestRunnerResult:
    """Execute the existing predict+val flow and normalize the artifacts."""

    model_request = _build_model_test_request(request)
    require_existing_path(model_request.dataset_config, stage="TEST", label="测试数据集配置文件")
    require_existing_path(model_request.model_path, stage="TEST", label="测试权重文件")
    if model_request.query_model_path is not None:
        require_existing_path(model_request.query_model_path, stage="TEST", label="group1 query parser 权重文件")
    if model_request.embedder_model_path is not None:
        require_existing_path(model_request.embedder_model_path, stage="TEST", label="group1 icon embedder 权重文件")
    require_existing_path(model_request.source, stage="TEST", label="测试图片来源")

    try:
        result = (runner or run_model_test)(model_request)
    except RuntimeError as exc:
        raise classify_runtime_error("TEST", str(exc)) from exc

    return TestRunnerResult(
        record=contracts.TestRecord(
            task=result.task,
            dataset_version=result.dataset_version,
            train_name=result.train_name,
            metrics=result.metrics,
            predict_output_dir=str(result.predict_output_dir),
            val_output_dir=str(result.val_output_dir),
            report_dir=str(result.report_dir),
        ),
        predict_command=result.predict_command,
        val_command=result.val_command,
    )


def _build_model_test_request(request: TestRunnerRequest) -> ModelTestRequest:
    task = request.task
    dataset_config = request.dataset_config or default_dataset_config(request.train_root, task, request.dataset_version)
    if task == "group1":
        group1_dataset_config = load_group1_dataset_config(dataset_config)
        model_path = request.model_path or resolve_group1_component_best_weights(request.train_root, request.train_name, PROPOSAL_COMPONENT)
        query_model_path = request.query_model_path or resolve_group1_component_best_weights(request.train_root, request.train_name, QUERY_COMPONENT)
        embedder_model_path = None
        if group1_dataset_config.is_instance_matching:
            embedder_model_path = (
                request.embedder_model_path
                or resolve_group1_component_best_weights(request.train_root, request.train_name, EMBEDDER_COMPONENT)
            )
    else:
        model_path = request.model_path or default_best_weights(request.train_root, task, request.train_name)
        query_model_path = None
        embedder_model_path = None
    source = request.source or default_predict_source(request.train_root, task, request.dataset_version)
    project_dir = request.project_dir or default_report_dir(request.train_root, task)
    report_dir = request.report_dir or (project_dir / f"test_{request.train_name}")
    predict_name = request.predict_name or f"predict_{request.train_name}"
    val_name = request.val_name or f"val_{request.train_name}"
    return ModelTestRequest(
        task=task,
        dataset_version=request.dataset_version,
        train_name=request.train_name,
        dataset_config=dataset_config,
        model_path=model_path,
        query_model_path=query_model_path,
        embedder_model_path=embedder_model_path,
        source=source,
        project_dir=project_dir,
        report_dir=report_dir,
        predict_name=predict_name,
        val_name=val_name,
        conf=request.conf,
        device=request.device,
        imgsz=request.imgsz,
    )
