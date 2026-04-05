"""Shared image input helpers for future runtime migration."""

from __future__ import annotations

from pathlib import Path

from .errors import SolverInputError
from .types import ImageInput


def require_pathlike_image(image: ImageInput, *, field: str) -> Path:
    """Resolve a path-like image input for local runtime use."""
    if isinstance(image, Path):
        return image
    if isinstance(image, str):
        return Path(image)
    raise SolverInputError(f"`{field}` 当前只支持本地文件路径输入。")
