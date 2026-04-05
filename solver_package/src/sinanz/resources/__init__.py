"""Package resource helpers for embedded solver assets."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable


def resource_root() -> Traversable:
    return files(__name__)


def models_root() -> Traversable:
    return resource_root().joinpath("models")


def metadata_root() -> Traversable:
    return resource_root().joinpath("metadata")
