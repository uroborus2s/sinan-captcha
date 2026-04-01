"""Common training job helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingJob:
    task: str
    dataset_yaml: Path
    model: str
    epochs: int
    batch: int
    imgsz: int = 640
    device: str = "0"
    project_dir: Path | None = None
    run_name: str = "v1"

    def command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "yolo",
            "detect",
            "train",
            f"data={self.dataset_yaml}",
            f"model={self.model}",
            f"imgsz={self.imgsz}",
            f"epochs={self.epochs}",
            f"batch={self.batch}",
            f"device={self.device}",
            f"name={self.run_name}",
        ]
        if self.project_dir is not None:
            command.append(f"project={self.project_dir}")
        return command
