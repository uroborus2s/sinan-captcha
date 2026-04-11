from __future__ import annotations

from pathlib import Path
import shutil


REPO_ROOT = Path(__file__).resolve().parents[2]


def _remove_tree(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def cleanup_generated_test_artifacts() -> None:
    for pycache_dir in REPO_ROOT.rglob("__pycache__"):
        _remove_tree(pycache_dir)

    for build_dir in REPO_ROOT.glob("packages/*/build"):
        _remove_tree(build_dir)

    for egg_info_dir in REPO_ROOT.glob("packages/*/*.egg-info"):
        _remove_tree(egg_info_dir)
    for egg_info_dir in REPO_ROOT.glob("packages/*/src/*.egg-info"):
        _remove_tree(egg_info_dir)

    _remove_tree(REPO_ROOT / ".pytest_cache")
    _remove_tree(REPO_ROOT / ".ruff_cache")
    _remove_tree(REPO_ROOT / ".mypy_cache")
    _remove_tree(REPO_ROOT / "htmlcov")

    for coverage_file in REPO_ROOT.glob(".coverage*"):
        if coverage_file.is_file():
            coverage_file.unlink(missing_ok=True)


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    cleanup_generated_test_artifacts()
