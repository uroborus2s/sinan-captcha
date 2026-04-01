"""Evaluation service placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationRequest:
    task: str
    weights_path: Path
    dataset_dir: Path
    report_dir: Path


def evaluate_model(request: EvaluationRequest) -> None:
    message = (
        f"Evaluation is not implemented yet: task={request.task}, "
        f"weights={request.weights_path}, dataset={request.dataset_dir}, report={request.report_dir}"
    )
    raise NotImplementedError(message)
