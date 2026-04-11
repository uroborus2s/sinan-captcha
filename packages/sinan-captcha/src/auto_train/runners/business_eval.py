"""Business-evaluation runner adapter for autonomous training."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from auto_train import business_eval, contracts
from auto_train.runners.common import RunnerExecutionError, classify_runtime_error, require_existing_path


@dataclass(frozen=True)
class BusinessEvalRunnerRequest:
    trial_id: str
    task: str
    train_root: Path
    dataset_version: str
    train_name: str
    cases_root: Path
    report_dir: Path
    device: str = "0"
    imgsz: int = 640
    success_threshold: float = 0.90
    min_cases: int = 50
    sample_size: int = 50
    point_tolerance_px: int = 5
    iou_threshold: float = 0.5


@dataclass(frozen=True)
class BusinessEvalRunnerResult:
    record: contracts.BusinessEvalRecord
    command: str


def run_business_eval_request(request: BusinessEvalRunnerRequest) -> BusinessEvalRunnerResult:
    require_existing_path(request.cases_root, stage="BUSINESS_EVAL", label="business eval 样本目录")
    try:
        record = business_eval.run_reviewed_business_eval(
            trial_id=request.trial_id,
            task=request.task,
            train_root=request.train_root,
            dataset_version=request.dataset_version,
            train_name=request.train_name,
            cases_root=request.cases_root,
            report_dir=request.report_dir,
            device=request.device,
            imgsz=request.imgsz,
            success_threshold=request.success_threshold,
            min_cases=request.min_cases,
            sample_size=request.sample_size,
            point_tolerance_px=request.point_tolerance_px,
            iou_threshold=request.iou_threshold,
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
