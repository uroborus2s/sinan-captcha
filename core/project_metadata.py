"""Read package metadata from the repository source of truth."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import tomllib

PACKAGE_NAME = "sinan-captcha"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_project_version(project_dir: Path | None = None) -> str:
    root = (project_dir or repository_root()).resolve()
    pyproject_path = root / "pyproject.toml"
    try:
        raw = pyproject_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"pyproject.toml not found: {pyproject_path}") from exc

    try:
        version = tomllib.loads(raw)["project"]["version"]
    except KeyError as exc:
        raise ValueError(f"project.version is missing in pyproject.toml: {pyproject_path}") from exc

    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"project.version must be a non-empty string: {pyproject_path}")
    return version.strip()


def get_runtime_version() -> str:
    pyproject_path = repository_root() / "pyproject.toml"
    if pyproject_path.exists():
        return read_project_version(repository_root())
    return importlib.metadata.version(PACKAGE_NAME)
