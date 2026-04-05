"""Helpers for locating and copying packaged OpenCode command/skill assets."""

from __future__ import annotations

from pathlib import Path
import shutil


def repo_opencode_root() -> Path:
    return Path(__file__).resolve().parents[2] / ".opencode"


def packaged_opencode_root() -> Path:
    return Path(__file__).resolve().parent / "resources" / "opencode"


def resolve_opencode_assets_root() -> Path:
    repo_root = repo_opencode_root()
    if repo_root.exists():
        return repo_root
    packaged_root = packaged_opencode_root()
    if packaged_root.exists():
        return packaged_root
    raise FileNotFoundError("opencode assets not found in repository or packaged resources")


def copy_opencode_assets(target_root: Path) -> Path:
    source_root = resolve_opencode_assets_root()
    destination = target_root / ".opencode"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source_root, destination)
    return destination
