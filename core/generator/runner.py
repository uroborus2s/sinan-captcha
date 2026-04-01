"""Helpers for invoking the Go generator binary from Python scripts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class GeneratorCommand:
    binary: Path
    command: str
    config: Path
    materials_root: Path
    output_root: Path | None = None
    batch_dir: Path | None = None

    def as_args(self) -> list[str]:
        args = [
            str(self.binary),
            self.command,
            "--config",
            str(self.config),
            "--materials-root",
            str(self.materials_root),
        ]
        if self.output_root is not None:
            args.extend(["--output-root", str(self.output_root)])
        if self.batch_dir is not None:
            args.extend(["--batch-dir", str(self.batch_dir)])
        return args


def run_generator(command: GeneratorCommand) -> subprocess.CompletedProcess[str]:
    if not command.binary.exists():
        raise FileNotFoundError(f"generator binary does not exist: {command.binary}")
    return subprocess.run(command.as_args(), check=True, text=True, capture_output=True)
