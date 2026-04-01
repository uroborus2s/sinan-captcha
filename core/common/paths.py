"""Repository and work-directory path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    """Well-known project paths used by scripts and CLIs."""

    repo_root: Path
    work_root: Path
    datasets_dir: Path
    reports_dir: Path
    dist_dir: Path

    @classmethod
    def from_roots(cls, repo_root: Path, work_root: Path | None = None) -> "WorkspacePaths":
        resolved_repo_root = repo_root.resolve()
        resolved_work_root = (work_root or resolved_repo_root).resolve()
        return cls(
            repo_root=resolved_repo_root,
            work_root=resolved_work_root,
            datasets_dir=resolved_work_root / "datasets",
            reports_dir=resolved_work_root / "reports",
            dist_dir=resolved_repo_root / "dist",
        )
