"""Business-evaluation runner adapter for autonomous training."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.auto_train import business_eval, contracts
from core.auto_train.runners.common import RunnerExecutionError, classify_runtime_error, require_existing_path


@dataclass(frozen=True)
class BusinessEvalRunnerRequest:
    trial_id: str
    task: str
    train_root: Path
    train_name: str
    cases_root: Path
    report_dir: Path
    device: str = "0"
    success_threshold: float = 0.98
    min_cases: int = 100
    sample_size: int = 100
    occlusion_threshold: float = 0.78


@dataclass(frozen=True)
class BusinessEvalRunnerResult:
    record: contracts.BusinessEvalRecord
    command: str


def run_business_eval_request(request: BusinessEvalRunnerRequest) -> BusinessEvalRunnerResult:
    if request.task != "group2":
        raise RunnerExecutionError(
            stage="BUSINESS_EVAL",
            reason="invalid_request",
            message=f"business eval 目前仅支持 group2，收到：{request.task}",
            retryable=False,
        )

    require_existing_path(request.cases_root, stage="BUSINESS_EVAL", label="business eval 样本目录")
    try:
        record = business_eval.run_group2_business_eval(
            trial_id=request.trial_id,
            train_root=request.train_root,
            train_name=request.train_name,
            cases_root=request.cases_root,
            report_dir=request.report_dir,
            device=request.device,
            success_threshold=request.success_threshold,
            min_cases=request.min_cases,
            sample_size=request.sample_size,
            occlusion_threshold=request.occlusion_threshold,
        )
    except RuntimeError as exc:
        raise classify_runtime_error("BUSINESS_EVAL", str(exc)) from exc

    return BusinessEvalRunnerResult(
        record=record,
        command=(
            "uv run sinan business-eval "
            f"{request.task} --train-name {request.train_name} --cases-root {request.cases_root}"
        ),
    )
