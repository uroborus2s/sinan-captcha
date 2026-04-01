"""Conversion contracts from JSONL source-of-truth files to YOLO datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConversionRequest:
    task: str
    version: str
    source_dir: Path
    output_dir: Path


def build_yolo_dataset(request: ConversionRequest) -> None:
    """Placeholder for the future conversion implementation."""

    message = (
        f"YOLO dataset conversion is not implemented yet: task={request.task}, "
        f"version={request.version}, source={request.source_dir}, output={request.output_dir}"
    )
    raise NotImplementedError(message)
