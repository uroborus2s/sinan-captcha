"""Group1 training job construction."""

from __future__ import annotations

from pathlib import Path

from core.train.base import TrainingJob


def build_group1_training_job(
    dataset_yaml: Path,
    project_dir: Path,
    model: str = "yolo26n.pt",
    run_name: str = "v1",
    *,
    epochs: int | None = None,
    batch: int | None = None,
    imgsz: int = 640,
    device: str = "0",
) -> TrainingJob:
    return TrainingJob(
        task="group1",
        dataset_yaml=dataset_yaml,
        model=model,
        epochs=120 if epochs is None else epochs,
        batch=16 if batch is None else batch,
        imgsz=imgsz,
        device=device,
        project_dir=project_dir,
        run_name=run_name,
    )
