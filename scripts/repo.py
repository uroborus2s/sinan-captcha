#!/usr/bin/env python3
"""Root-level repository CLI for monorepo build and delivery commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

from release.service import (
    PackageWindowsRequest,
    StageSolverAssetsRequest,
    package_windows_bundle,
    stage_solver_assets,
)
from release.solver_export import ExportSolverAssetsRequest, export_solver_assets


@dataclass(frozen=True)
class RepoLayout:
    repo_root: Path
    packages_dir: Path
    sinan_dir: Path
    solver_dir: Path
    generator_dir: Path


@dataclass(frozen=True)
class PublishRequest:
    project_dir: Path
    token_env: str | None = None


def default_layout(repo_root: Path | None = None) -> RepoLayout:
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    packages_dir = root / "packages"
    return RepoLayout(
        repo_root=root,
        packages_dir=packages_dir,
        sinan_dir=packages_dir / "sinan-captcha",
        solver_dir=packages_dir / "solver",
        generator_dir=packages_dir / "generator",
    )


def build_target(
    target: str,
    *,
    layout: RepoLayout,
    goos: str | None = None,
    goarch: str | None = None,
) -> None:
    if target == "all":
        build_target("sinan-captcha", layout=layout)
        build_target("generator", layout=layout, goos=goos, goarch=goarch)
        build_target("solver", layout=layout)
        return
    if target == "sinan-captcha":
        _build_python_package(package_name="sinan-captcha", package_dir=layout.sinan_dir, layout=layout)
        return
    if target == "solver":
        _build_python_package(package_name="sinanz", package_dir=layout.solver_dir, layout=layout)
        return
    if target == "generator":
        _build_generator(layout=layout, goos=goos, goarch=goarch)
        return
    raise ValueError(f"unsupported target: {target}")


def publish_distribution(request: PublishRequest) -> None:
    layout = default_layout(request.project_dir)
    token, token_source = _resolve_publish_token(request)
    version = _read_project_version(layout.sinan_dir)
    distribution_files = _current_distribution_files(layout.sinan_dir, version=version)

    env = _tool_env(layout.repo_root)
    env["UV_PUBLISH_TOKEN"] = token
    subprocess.run(
        args=[
            "uv",
            "publish",
            "--publish-url",
            "https://upload.pypi.org/legacy/",
            "--check-url",
            "https://pypi.org/simple",
            *[path.as_posix() for path in distribution_files],
        ],
        check=True,
        cwd=layout.sinan_dir,
        env=env,
    )
    print(f"published sinan-captcha to PyPI using token from {token_source}")


def _build_python_package(*, package_name: str, package_dir: Path, layout: RepoLayout) -> None:
    if not (package_dir / "pyproject.toml").is_file():
        raise ValueError(f"package project not found: {package_dir}")
    output_dir = package_dir / "dist"
    _recreate_dir(output_dir)
    _build_setuptools_distribution(package_dir=package_dir, output_dir=output_dir)


def _build_generator(*, layout: RepoLayout, goos: str | None, goarch: str | None) -> None:
    generator_dir = layout.generator_dir
    if not (generator_dir / "go.mod").is_file():
        raise ValueError(f"generator module not found: {generator_dir}")

    env = _tool_env(layout.repo_root)
    if goos:
        env["GOOS"] = goos
    if goarch:
        env["GOARCH"] = goarch
    target_goos = _go_env("GOOS", layout=layout, env=env)
    target_goarch = _go_env("GOARCH", layout=layout, env=env)
    output_dir = generator_dir / "dist" / f"{target_goos}-{target_goarch}"
    _recreate_dir(output_dir)
    output_name = "sinan-generator.exe" if target_goos == "windows" else "sinan-generator"
    subprocess.run(
        ["go", "build", "-o", str((output_dir / output_name).resolve()), "./cmd/sinan-generator"],
        check=True,
        cwd=generator_dir,
        env=env,
    )


def _go_env(name: str, *, layout: RepoLayout, env: dict[str, str]) -> str:
    return subprocess.check_output(
        ["go", "env", name],
        cwd=layout.generator_dir,
        env=env,
        text=True,
    ).strip()


def _tool_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    cache_root = (repo_root / "work_home" / ".cache").resolve()
    uv_cache_dir = cache_root / "uv"
    go_cache_dir = cache_root / "go"
    uv_cache_dir.mkdir(parents=True, exist_ok=True)
    go_cache_dir.mkdir(parents=True, exist_ok=True)
    env.setdefault("UV_CACHE_DIR", str(uv_cache_dir))
    env.setdefault("GOCACHE", str(go_cache_dir))
    return env


def _resolve_publish_token(request: PublishRequest) -> tuple[str, str]:
    if request.token_env is not None:
        token = os.environ.get(request.token_env)
        if not token:
            raise ValueError(f"missing publish token env var: {request.token_env}")
        return token, request.token_env

    for env_name in ("PYPI_TOKEN", "UV_PUBLISH_TOKEN"):
        token = os.environ.get(env_name)
        if token:
            return token, env_name
    raise ValueError("missing publish token env var: PYPI_TOKEN or UV_PUBLISH_TOKEN")


def _read_project_version(project_dir: Path) -> str:
    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("python 3.11+ is required to read pyproject.toml") from exc

    pyproject_path = project_dir / "pyproject.toml"
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


def _current_distribution_files(project_dir: Path, *, version: str) -> list[Path]:
    dist_dir = project_dir / "dist"
    wheel = dist_dir / f"sinan_captcha-{version}-py3-none-any.whl"
    sdist = dist_dir / f"sinan_captcha-{version}.tar.gz"
    missing = [path for path in (wheel, sdist) if not path.exists()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise ValueError(f"missing release artifacts for current version: {missing_text}")
    return [wheel, sdist]


def _build_setuptools_distribution(*, package_dir: Path, output_dir: Path) -> None:
    build_meta = importlib.import_module("setuptools.build_meta")
    staged_opencode_assets = _stage_repo_opencode_assets(package_dir)
    _clean_python_build_artifacts(package_dir)
    current_dir = Path.cwd()
    try:
        os.chdir(package_dir)
        build_meta.build_wheel(str(output_dir.resolve()))
        build_meta.build_sdist(str(output_dir.resolve()))
    finally:
        os.chdir(current_dir)
        _clean_python_build_artifacts(package_dir)
        if staged_opencode_assets is not None:
            _clear_staged_opencode_assets(package_dir)


def _clean_python_build_artifacts(package_dir: Path) -> None:
    build_dir = package_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    src_dir = package_dir / "src"
    egg_info_dirs = list(package_dir.glob("*.egg-info"))
    if src_dir.is_dir():
        egg_info_dirs.extend(src_dir.glob("*.egg-info"))
    for egg_info in egg_info_dirs:
        if egg_info.is_dir():
            shutil.rmtree(egg_info)


def _stage_repo_opencode_assets(package_dir: Path) -> Path | None:
    source_root = package_dir.parents[1] / ".opencode"
    if not source_root.is_dir():
        return None
    destination = package_dir / "src" / "auto_train" / "resources" / "opencode"
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, destination)
    return destination


def _clear_staged_opencode_assets(package_dir: Path) -> None:
    destination = package_dir / "src" / "auto_train" / "resources" / "opencode"
    if destination.exists():
        shutil.rmtree(destination)

    resources_dir = destination.parent
    if resources_dir.exists():
        try:
            resources_dir.rmdir()
        except OSError:
            pass


def _recreate_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run root-level repository commands for sinan-captcha."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build one package or all packages.")
    build_parser.add_argument(
        "target",
        choices=["sinan-captcha", "generator", "solver", "all"],
        help="Workspace member or aggregate target to build.",
    )
    build_parser.add_argument("--goos", help="Optional GOOS override when building generator.")
    build_parser.add_argument("--goarch", help="Optional GOARCH override when building generator.")
    build_parser.set_defaults(handler=_handle_build)

    publish_parser = subparsers.add_parser("publish", help="Publish current sinan-captcha artifacts to PyPI.")
    publish_parser.add_argument(
        "--token-env",
        help="Optional token env var. Defaults to PYPI_TOKEN, then UV_PUBLISH_TOKEN.",
    )
    publish_parser.set_defaults(handler=_handle_publish)

    export_parser = subparsers.add_parser(
        "export-solver-assets",
        help="Export group1/group2 PT checkpoints into sinanz ONNX solver assets.",
    )
    export_parser.add_argument("--group1-proposal-checkpoint", type=Path, default=None)
    export_parser.add_argument("--group1-query-checkpoint", type=Path, default=None)
    export_parser.add_argument("--group1-embedder-checkpoint", type=Path, default=None)
    export_parser.add_argument("--group1-run", default="")
    export_parser.add_argument("--group2-checkpoint", type=Path, required=True)
    export_parser.add_argument("--group2-run", required=True)
    export_parser.add_argument("--output-dir", type=Path, required=True)
    export_parser.add_argument("--asset-version", required=True)
    export_parser.add_argument("--exported-at", default=None)
    export_parser.add_argument("--source-checkpoint", default=None)
    export_parser.add_argument("--opset", type=int, default=17)
    export_parser.set_defaults(handler=_handle_export_solver_assets)

    stage_parser = subparsers.add_parser(
        "stage-solver-assets",
        help="Copy exported solver assets into packages/solver/resources/ for packaging.",
    )
    stage_parser.add_argument("--asset-dir", type=Path, required=True)
    stage_parser.set_defaults(handler=_handle_stage_solver_assets)

    package_parser = subparsers.add_parser(
        "package-windows",
        help="Assemble a Windows delivery bundle with the wheel, generator, and optional assets.",
    )
    package_parser.add_argument("--generator-exe", type=Path, required=True)
    package_parser.add_argument("--output-dir", type=Path, required=True)
    package_parser.add_argument("--bundle-dir", type=Path, default=None)
    package_parser.add_argument("--datasets-dir", type=Path, default=None)
    package_parser.add_argument("--materials-dir", type=Path, default=None)
    package_parser.set_defaults(handler=_handle_package_windows)

    paths_parser = subparsers.add_parser("paths", help="Print current monorepo package paths.")
    paths_parser.set_defaults(handler=_handle_paths)
    return parser


def _handle_build(args: argparse.Namespace, *, layout: RepoLayout) -> int:
    build_target(args.target, layout=layout, goos=args.goos, goarch=args.goarch)
    return 0


def _handle_publish(args: argparse.Namespace, *, layout: RepoLayout) -> int:
    publish_distribution(PublishRequest(project_dir=layout.repo_root, token_env=args.token_env))
    return 0


def _handle_export_solver_assets(args: argparse.Namespace, *, layout: RepoLayout) -> int:
    export_solver_assets(
        ExportSolverAssetsRequest(
            project_dir=layout.repo_root,
            group1_proposal_checkpoint=args.group1_proposal_checkpoint,
            group1_query_checkpoint=args.group1_query_checkpoint,
            group1_embedder_checkpoint=args.group1_embedder_checkpoint,
            group1_run=args.group1_run,
            group2_checkpoint=args.group2_checkpoint,
            output_dir=args.output_dir,
            asset_version=args.asset_version,
            group2_run=args.group2_run,
            exported_at=args.exported_at,
            source_checkpoint=args.source_checkpoint,
            opset=args.opset,
        )
    )
    return 0


def _handle_stage_solver_assets(args: argparse.Namespace, *, layout: RepoLayout) -> int:
    stage_solver_assets(
        StageSolverAssetsRequest(
            project_dir=layout.repo_root,
            asset_dir=args.asset_dir,
        )
    )
    return 0


def _handle_package_windows(args: argparse.Namespace, *, layout: RepoLayout) -> int:
    package_windows_bundle(
        PackageWindowsRequest(
            project_dir=layout.repo_root,
            generator_exe=args.generator_exe,
            output_dir=args.output_dir,
            bundle_dir=args.bundle_dir,
            datasets_dir=args.datasets_dir,
            materials_dir=args.materials_dir,
        )
    )
    return 0


def _handle_paths(_: argparse.Namespace, *, layout: RepoLayout) -> int:
    print(f"repo_root={layout.repo_root}")
    print(f"sinan_captcha={layout.sinan_dir}")
    print(f"generator={layout.generator_dir}")
    print(f"solver={layout.solver_dir}")
    print(f"work_home={layout.repo_root / 'work_home'}")
    return 0


def main(argv: list[str] | None = None, *, layout: RepoLayout | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_layout = layout or default_layout()
    try:
        return int(args.handler(args, layout=repo_layout))
    except ValueError as err:
        parser.exit(1, f"{err}\n")


def usage_overview() -> str:
    return textwrap.dedent(
        """
        uv run repo <command>

        Commands:
          build <target>              Build one package or all packages.
          publish                     Publish current sinan-captcha artifacts to PyPI.
          export-solver-assets        Export group1/group2 PT checkpoints into sinanz ONNX assets.
          stage-solver-assets         Stage exported assets into packages/solver/resources/.
          package-windows             Assemble a Windows delivery bundle.
          paths                       Print current monorepo package paths.
        """
    ).strip()


if __name__ == "__main__":
    raise SystemExit(main())
