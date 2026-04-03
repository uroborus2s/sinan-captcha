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

    python_dir = request.output_dir / "python"
    generator_dir = request.output_dir / "generator"
    python_dir.mkdir(parents=True, exist_ok=True)
    generator_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(wheel, python_dir / wheel.name)
    shutil.copy2(request.generator_exe, generator_dir / request.generator_exe.name)

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
            2. generator/ 目录包含 Go 生成器可执行文件
            3. 默认训练目录初始化方式：
               uvx --from sinan-captcha sinan env setup-train --train-root <训练目录>
            4. 如果已有 YOLO 数据集，可直接拷贝到训练目录 datasets/ 下开始训练
            5. 如果需要本地生成样本，请先进入 generator/ 目录，再用 .\sinan-generator.exe 执行命令
            6. 推荐先初始化工作区：
               .\sinan-generator.exe workspace init --workspace <生成器工作区>
            7. 准备素材的两种主路径：
               .\sinan-generator.exe materials import --workspace <生成器工作区> --from <materials-pack目录>
               .\sinan-generator.exe materials fetch --workspace <生成器工作区> --source <materials-pack.zip或URL>
            8. 生成训练数据：
               .\sinan-generator.exe make-dataset --workspace <生成器工作区> --task group1 --dataset-dir <训练数据目录>
            9. 默认 firstpass 预设一次生成 200 条，smoke 预设一次生成 20 条
            10. 如果对同一个 dataset-dir 重跑并加 --force，会覆盖原目录；要保留旧数据，请改用新的版本目录
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
