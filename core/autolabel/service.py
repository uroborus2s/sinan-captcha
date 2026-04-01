"""Autolabel service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AutolabelRequest:
    task: str
    mode: str
    input_dir: Path
    output_dir: Path


def run_autolabel(request: AutolabelRequest) -> None:
    """Placeholder for the future autolabel implementation."""

    message = (
        f"Autolabel is not implemented yet: task={request.task}, "
        f"mode={request.mode}, input={request.input_dir}, output={request.output_dir}"
    )
    raise NotImplementedError(message)
