"""Evaluation runner adapter for the autonomous-training controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.auto_train import contracts
from core.auto_train.runners.common import RunnerExecutionError, classify_runtime_error, require_existing_path
from core.evaluate.service import EvaluationRequest, EvaluationResult, evaluate_model

EvaluationExecutor = Callable[[EvaluationRequest], EvaluationResult]


@dataclass(frozen=True)
class EvaluateRunnerRequest:
    task: str
    gold_dir: Path
    prediction_dir: Path
    report_dir: Path
    point_tolerance_px: int = 5
    iou_threshold: float = 0.5

    def command(self) -> str:
        return " ".join(
            [
                "uv",
                "run",
                "sinan",
                "evaluate",
                f"--task {self.task}",
                f"--gold-dir {self.gold_dir}",
                f"--prediction-dir {self.prediction_dir}",
                f"--report-dir {self.report_dir}",
                f"--point-tolerance-px {self.point_tolerance_px}",
                f"--iou-threshold {self.iou_threshold:g}",
            ]
        )


@dataclass(frozen=True)
class EvaluateRunnerResult:
    record: contracts.EvaluateRecord
    command: str


def run_evaluation_request(
    request: EvaluateRunnerRequest,
    *,
    evaluator: EvaluationExecutor | None = None,
) -> EvaluateRunnerResult:
    """Execute JSONL evaluation and normalize the result into trial artifacts."""

    command = request.command()
    require_existing_path(request.gold_dir / "labels.jsonl", stage="EVALUATE", label="gold labels.jsonl", command=command)
    require_existing_path(
        request.prediction_dir / "labels.jsonl",
        stage="EVALUATE",
        label="prediction labels.jsonl",
        command=command,
    )

    evaluation_request = EvaluationRequest(
        task=request.task,
        gold_dir=request.gold_dir,
        prediction_dir=request.prediction_dir,
        report_dir=request.report_dir,
        point_tolerance_px=request.point_tolerance_px,
        iou_threshold=request.iou_threshold,
    )
    try:
        result = (evaluator or evaluate_model)(evaluation_request)
    except RuntimeError as exc:
        raise classify_runtime_error("EVALUATE", str(exc), command=command) from exc

    return EvaluateRunnerResult(
        record=contracts.EvaluateRecord(
            available=True,
            task=result.task,
            metrics=result.metrics,
            failure_count=result.failure_count,
            report_dir=str(result.report_dir),
        ),
        command=command,
    )
