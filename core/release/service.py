"""Build, publish, and package local delivery artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import textwrap


@dataclass(frozen=True)
class BuildReleaseRequest:
    project_dir: Path


@dataclass(frozen=True)
class PublishReleaseRequest:
    project_dir: Path
    repository: str
    token_env: str


@dataclass(frozen=True)
class PackageWindowsRequest:
    project_dir: Path
    generator_exe: Path
    output_dir: Path
    datasets_dir: Path | None = None
    materials_dir: Path | None = None


def build_distribution(request: BuildReleaseRequest) -> None:
    subprocess.run(["uv", "build"], check=True, cwd=request.project_dir)


def publish_distribution(request: PublishReleaseRequest) -> None:
    token = os.environ.get(request.token_env)
    if not token:
        raise ValueError(f"missing publish token env var: {request.token_env}")

    publish_url, check_url = _resolve_repository_urls(request.repository)
    env = os.environ.copy()
    env["UV_PUBLISH_TOKEN"] = token
    subprocess.run(
        args=[
            "uv",
            "publish",
            "--publish-url",
            publish_url,
            "--check-url",
            check_url,
        ],
        check=True,
        cwd=request.project_dir,
        env=env,
    )


def package_windows_bundle(request: PackageWindowsRequest) -> None:
    dist_dir = request.project_dir / "dist"
    wheel = _latest_wheel(dist_dir)
    generator_configs_dir = request.project_dir / "generator" / "configs"

    python_dir = request.output_dir / "python"
    generator_dir = request.output_dir / "generator"
    python_dir.mkdir(parents=True, exist_ok=True)
    generator_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(wheel, python_dir / wheel.name)
    shutil.copy2(request.generator_exe, generator_dir / request.generator_exe.name)
    if generator_configs_dir.exists():
        shutil.copytree(
            generator_configs_dir,
            generator_dir / "configs",
            dirs_exist_ok=True,
        )

    if request.datasets_dir is not None and request.datasets_dir.exists():
        shutil.copytree(request.datasets_dir, request.output_dir / "datasets", dirs_exist_ok=True)
    if request.materials_dir is not None and request.materials_dir.exists():
        shutil.copytree(request.materials_dir, request.output_dir / "materials", dirs_exist_ok=True)

    (request.output_dir / "README-交付包说明.txt").write_text(
        textwrap.dedent(
            f"""
            交付包说明
            ============

            1. python/ 目录包含训练机安装用的 wheel 备份包
            2. generator/ 目录包含 Go 生成器和配置
            3. 默认训练目录初始化方式：
               uvx --from sinan-captcha sinan env setup-train --train-root <训练目录>
            4. 如果已有 YOLO 数据集，可直接拷贝到训练目录 datasets/ 下开始训练
            5. 如果需要本地生成样本，请在独立生成器目录使用 generator/ 下的二进制、配置和显式工作区
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _latest_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise ValueError(f"no wheel found in dist dir: {dist_dir}")
    return wheels[-1]


def _resolve_repository_urls(repository: str) -> tuple[str, str]:
    if repository == "pypi":
        return ("https://upload.pypi.org/legacy/", "https://pypi.org/simple")
    if repository == "testpypi":
        return ("https://test.pypi.org/legacy/", "https://test.pypi.org/simple")
    raise ValueError(f"unsupported repository: {repository}")
