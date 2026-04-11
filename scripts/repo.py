#!/usr/bin/env python3
"""Thin monorepo wrapper for root-level build commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class RepoLayout:
    repo_root: Path
    packages_dir: Path
    sinan_dir: Path
    solver_dir: Path
    generator_dir: Path


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


def _build_python_package(*, package_name: str, package_dir: Path, layout: RepoLayout) -> None:
    if not (package_dir / "pyproject.toml").is_file():
        raise ValueError(f"package project not found: {package_dir}")
    output_dir = package_dir / "dist"
    _recreate_dir(output_dir)
    subprocess.run(
        [
            "uv",
            "build",
            "--package",
            package_name,
            "--out-dir",
            output_dir.relative_to(layout.repo_root).as_posix(),
        ],
        check=True,
        cwd=layout.repo_root,
    )


def _build_generator(*, layout: RepoLayout, goos: str | None, goarch: str | None) -> None:
    generator_dir = layout.generator_dir
    if not (generator_dir / "go.mod").is_file():
        raise ValueError(f"generator module not found: {generator_dir}")

    env = os.environ.copy()
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


def _recreate_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run root-level monorepo build commands for sinan-captcha members."
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

    paths_parser = subparsers.add_parser("paths", help="Print current monorepo package paths.")
    paths_parser.set_defaults(handler=_handle_paths)
    return parser


def _handle_build(args: argparse.Namespace, *, layout: RepoLayout) -> int:
    build_target(args.target, layout=layout, goos=args.goos, goarch=args.goarch)
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
    return int(args.handler(args, layout=repo_layout))


if __name__ == "__main__":
    raise SystemExit(main())
