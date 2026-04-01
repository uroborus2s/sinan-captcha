"""Group2 training job construction."""

from __future__ import annotations

from pathlib import Path

from core.train.base import TrainingJob


def build_group2_training_job(
    dataset_yaml: Path,
    project_dir: Path,
    model: str = "yolo26n.pt",
    run_name: str = "v1",
) -> TrainingJob:
    return TrainingJob(
        task="group2",
        dataset_yaml=dataset_yaml,
        model=model,
        epochs=100,
        batch=16,
        project_dir=project_dir,
        run_name=run_name,
    )
