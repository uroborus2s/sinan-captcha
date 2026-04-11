"""Repository and work-directory path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

_REPO_MARKERS = (".git", ".factory")


def _is_windows_absolute_path(path: Path) -> bool:
    return PureWindowsPath(str(path)).is_absolute()


def package_root(start: Path | None = None) -> Path:
    anchors: list[Path] = []
    for raw_anchor in (start, Path(__file__)):
        if raw_anchor is None:
            continue
        if _is_windows_absolute_path(raw_anchor):
            continue
        anchor = raw_anchor.resolve()
        if anchor.is_file():
            anchor = anchor.parent
        anchors.append(anchor)

    for anchor in anchors:
        for candidate in (anchor, *anchor.parents):
            if (candidate / "src" / "cli.py").exists() and (candidate / "pyproject.toml").exists():
                return candidate
    raise ValueError(f"unable to locate package root from {anchor}")


def find_repo_root(start: Path | None = None) -> Path | None:
    raw_anchor = start or package_root()
    if _is_windows_absolute_path(raw_anchor):
        return None
    anchor = raw_anchor.resolve()
    if anchor.is_file():
        anchor = anchor.parent
    for candidate in (anchor, *anchor.parents):
        if any((candidate / marker).exists() for marker in _REPO_MARKERS):
            return candidate
        if (candidate / "packages" / "sinan-captcha" / "pyproject.toml").exists():
            return candidate
    return None


def repository_root(start: Path | None = None) -> Path:
    return find_repo_root(start) or package_root(start)


def default_work_root(start: Path | None = None) -> Path:
    raw_anchor = start or Path.cwd()
    if _is_windows_absolute_path(raw_anchor):
        return Path(str(raw_anchor))
    anchor = raw_anchor.resolve()
    repo_root = find_repo_root(anchor)
    if repo_root is None:
        return anchor
    return repo_root / "work_home"


@dataclass(frozen=True)
class WorkspacePaths:
    """Well-known project paths used by scripts and CLIs."""

    repo_root: Path
    package_root: Path
    packages_dir: Path
    sinan_package_dir: Path
    solver_package_dir: Path
    generator_package_dir: Path
    work_root: Path
    datasets_dir: Path
    reports_dir: Path
    materials_dir: Path
    cache_dir: Path
    sinan_dist_dir: Path
    solver_dist_dir: Path
    generator_dist_dir: Path

    @classmethod
    def from_roots(cls, repo_root: Path, work_root: Path | None = None) -> "WorkspacePaths":
        resolved_repo_root = repo_root.resolve()
        resolved_package_root = package_root()
        resolved_work_root = (work_root or (resolved_repo_root / "work_home")).resolve()
        packages_dir = resolved_repo_root / "packages"
        sinan_package_dir = packages_dir / "sinan-captcha"
        solver_package_dir = packages_dir / "solver"
        generator_package_dir = packages_dir / "generator"
        return cls(
            repo_root=resolved_repo_root,
            package_root=resolved_package_root,
            packages_dir=packages_dir,
            sinan_package_dir=sinan_package_dir,
            solver_package_dir=solver_package_dir,
            generator_package_dir=generator_package_dir,
            work_root=resolved_work_root,
            datasets_dir=resolved_work_root / "datasets",
            reports_dir=resolved_work_root / "reports",
            materials_dir=resolved_work_root / "materials",
            cache_dir=resolved_work_root / ".cache",
            sinan_dist_dir=sinan_package_dir / "dist",
            solver_dist_dir=solver_package_dir / "dist",
            generator_dist_dir=generator_package_dir / "dist",
        )


def workspace_paths(start: Path | None = None) -> WorkspacePaths:
    repo_root = repository_root(start)
    return WorkspacePaths.from_roots(repo_root=repo_root, work_root=default_work_root(start))
