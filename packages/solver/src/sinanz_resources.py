"""Filesystem helpers for embedded solver assets."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import sysconfig


def resource_root() -> Path:
    module_dir = Path(__file__).resolve().parent
    candidates = (
        module_dir.parent / "resources",
        module_dir / "resources",
        Path(sysconfig.get_path("data")) / "resources",
    )
    try:
        dist = distribution("sinanz")
    except PackageNotFoundError:
        dist = None
    if dist is not None:
        located_root = Path(dist.locate_file(Path("resources")))
        if located_root.is_dir():
            return located_root
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def models_root() -> Path:
    return resource_root() / "models"


def metadata_root() -> Path:
    return resource_root() / "metadata"
