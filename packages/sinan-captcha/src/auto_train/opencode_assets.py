"""Helpers for locating and copying packaged OpenCode command/skill assets."""

from __future__ import annotations

from pathlib import Path
import shutil

from common.paths import repository_root


def repo_opencode_root() -> Path | None:
    try:
        return repository_root(Path(__file__)) / ".opencode"
    except ValueError:
        return None


def packaged_opencode_root() -> Path:
    return Path(__file__).resolve().parent / "resources" / "opencode"


def packaged_opencode_root_for(package_dir: Path) -> Path:
    return package_dir / "src" / "auto_train" / "resources" / "opencode"


def resolve_opencode_assets_root() -> Path:
    repo_root = repo_opencode_root()
    if repo_root is not None and repo_root.exists():
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


def stage_repo_opencode_assets(package_dir: Path, *, source_root: Path | None = None) -> Path:
    resolved_package_dir = package_dir.resolve()
    resolved_source_root = (source_root or repo_opencode_root()).resolve()
    if not resolved_source_root.is_dir():
        raise FileNotFoundError(f"repo opencode assets not found: {resolved_source_root}")

    destination = packaged_opencode_root_for(resolved_package_dir)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(resolved_source_root, destination)
    return destination


def clear_staged_opencode_assets(package_dir: Path) -> None:
    destination = packaged_opencode_root_for(package_dir.resolve())
    if destination.exists():
        shutil.rmtree(destination)

    parent = destination.parent
    while parent.name == "resources":
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
