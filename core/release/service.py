"""Build, publish, and package local delivery artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

from core.project_metadata import read_project_version
from core.release.solver_export import ExportGroup2SolverAssetsRequest, export_group2_solver_assets


@dataclass(frozen=True)
class BuildReleaseRequest:
    project_dir: Path


@dataclass(frozen=True)
class BuildGeneratorRequest:
    project_dir: Path
    goos: str | None = None
    goarch: str | None = None


@dataclass(frozen=True)
class BuildSolverRequest:
    project_dir: Path


@dataclass(frozen=True)
class StageSolverAssetsRequest:
    project_dir: Path
    asset_dir: Path


@dataclass(frozen=True)
class BuildAllReleaseRequest:
    project_dir: Path
    goos: str | None = None
    goarch: str | None = None


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
    bundle_dir: Path | None = None
    datasets_dir: Path | None = None
    materials_dir: Path | None = None


def build_distribution(request: BuildReleaseRequest) -> None:
    project_dir = request.project_dir.resolve()
    _clean_output_dir(project_dir / "dist")
    subprocess.run(["uv", "build", "--out-dir", "dist"], check=True, cwd=project_dir)


def build_generator_distribution(request: BuildGeneratorRequest) -> None:
    project_dir = request.project_dir.resolve()
    generator_dir = project_dir / "generator"
    if not (generator_dir / "go.mod").exists():
        raise ValueError(f"generator module not found: {generator_dir}")

    goos, goarch, env = _resolve_go_build_target(
        generator_dir=generator_dir,
        requested_goos=request.goos,
        requested_goarch=request.goarch,
    )
    output_dir = generator_dir / "dist" / f"{goos}-{goarch}"
    _clean_output_dir(output_dir)
    output_path = output_dir / _generator_binary_name(goos)
    subprocess.run(
        ["go", "build", "-o", str(output_path.resolve()), "./cmd/sinan-generator"],
        check=True,
        cwd=generator_dir,
        env=env,
    )
    if not output_path.exists():
        raise ValueError(f"expected generator binary was not created: {output_path}")


def build_solver_distribution(request: BuildSolverRequest) -> None:
    project_dir = request.project_dir.resolve()
    solver_dir = project_dir / "solver"
    if not (solver_dir / "pyproject.toml").exists():
        raise ValueError(f"solver project not found: {solver_dir}")
    _clean_output_dir(solver_dir / "dist")
    subprocess.run(["uv", "build", "--out-dir", "dist"], check=True, cwd=solver_dir)


def build_all_distributions(request: BuildAllReleaseRequest) -> None:
    project_dir = request.project_dir.resolve()
    build_distribution(BuildReleaseRequest(project_dir=project_dir))
    build_generator_distribution(
        BuildGeneratorRequest(
            project_dir=project_dir,
            goos=request.goos,
            goarch=request.goarch,
        )
    )
    build_solver_distribution(BuildSolverRequest(project_dir=project_dir))


def stage_solver_assets(request: StageSolverAssetsRequest) -> None:
    project_dir = request.project_dir.resolve()
    asset_dir = request.asset_dir.resolve()
    solver_resource_dir = project_dir / "solver" / "resources"
    models_dir = solver_resource_dir / "models"
    metadata_dir = solver_resource_dir / "metadata"
    manifest_path = asset_dir / "manifest.json"
    source_models_dir = asset_dir / "models"
    source_metadata_dir = asset_dir / "metadata"

    if not manifest_path.is_file():
        raise ValueError(f"solver asset manifest does not exist: {manifest_path}")
    if not source_models_dir.is_dir():
        raise ValueError(f"solver asset models dir does not exist: {source_models_dir}")
    if not source_metadata_dir.is_dir():
        raise ValueError(f"solver asset metadata dir does not exist: {source_metadata_dir}")
    if not solver_resource_dir.is_dir():
        raise ValueError(f"solver resource dir does not exist: {solver_resource_dir}")

    models_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    _clear_directory_files(models_dir)
    _clear_directory_files(metadata_dir)

    for model_path in sorted(source_models_dir.glob("*")):
        if model_path.is_file():
            shutil.copy2(model_path, models_dir / model_path.name)
    for metadata_path in sorted(source_metadata_dir.glob("*.json")):
        shutil.copy2(metadata_path, metadata_dir / metadata_path.name)
    shutil.copy2(manifest_path, solver_resource_dir / "manifest.json")


def publish_distribution(request: PublishReleaseRequest) -> None:
    token = os.environ.get(request.token_env)
    if not token:
        raise ValueError(f"missing publish token env var: {request.token_env}")

    publish_url, check_url = _resolve_repository_urls(request.repository)
    env = os.environ.copy()
    env["UV_PUBLISH_TOKEN"] = token
    distribution_files = _current_distribution_files(request.project_dir)
    subprocess.run(
        args=[
            "uv",
            "publish",
            "--publish-url",
            publish_url,
            "--check-url",
            check_url,
            *[path.as_posix() for path in distribution_files],
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
    if request.bundle_dir is not None:
        if not request.bundle_dir.exists():
            raise ValueError(f"solver bundle dir does not exist: {request.bundle_dir}")
        shutil.copytree(request.bundle_dir, request.output_dir / "bundle", dirs_exist_ok=True)

    if request.datasets_dir is not None and request.datasets_dir.exists():
        shutil.copytree(request.datasets_dir, request.output_dir / "datasets", dirs_exist_ok=True)
    if request.materials_dir is not None and request.materials_dir.exists():
        shutil.copytree(request.materials_dir, request.output_dir / "materials", dirs_exist_ok=True)

    (request.output_dir / "README-交付包说明.txt").write_text(
        textwrap.dedent(
            f"""
            交付包说明
            ============

            1. python/ 目录包含 Python wheel，可通过 pip/uv pip 安装本地求解库或训练 CLI
            2. generator/ 目录包含 Go 生成器可执行文件
            3. 如果本包同时带有 bundle/，则 bundle\\manifest.json 是统一求解入口的模型事实源
            4. 默认训练目录初始化方式：
               uvx --from sinan-captcha sinan env setup-train --train-root <训练目录>
            5. 如果已有 YOLO 数据集，可直接拷贝到训练目录 datasets/ 下开始训练
            6. 如果需要本地生成样本，请先进入 generator/ 目录，再用 .\\sinan-generator.exe 执行命令
            7. 推荐先初始化工作区：
               .\\sinan-generator.exe workspace init --workspace <生成器工作区>
            8. 准备素材的两种主路径：
               .\\sinan-generator.exe materials import --workspace <生成器工作区> --from <materials-pack目录>
               .\\sinan-generator.exe materials fetch --workspace <生成器工作区> --source <materials-pack.zip或URL>
            9. 生成训练数据：
               .\\sinan-generator.exe make-dataset --workspace <生成器工作区> --task group1 --dataset-dir <训练数据目录>
            10. 默认 firstpass 预设一次生成 200 条，smoke 预设一次生成 20 条
            11. 如果对同一个 dataset-dir 重跑并加 --force，会覆盖原目录；要保留旧数据，请改用新的版本目录
            12. 如果已有 solver bundle，可用 Python API 或 CLI 调用：
                uv run sinan solve run --bundle-dir <bundle目录> --request <请求JSON>
                Python API: from core.solve.service import UnifiedSolverService
            13. bundle 目录存在时，至少应包含：
                bundle\\manifest.json
                bundle\\models\\...
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


def _current_distribution_files(project_dir: Path) -> list[Path]:
    version = read_project_version(project_dir)
    dist_dir = project_dir / "dist"
    wheel = dist_dir / f"sinan_captcha-{version}-py3-none-any.whl"
    sdist = dist_dir / f"sinan_captcha-{version}.tar.gz"
    missing = [path for path in (wheel, sdist) if not path.exists()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise ValueError(f"missing release artifacts for current version: {missing_text}")
    return [wheel, sdist]


def _resolve_repository_urls(repository: str) -> tuple[str, str]:
    if repository == "pypi":
        return ("https://upload.pypi.org/legacy/", "https://pypi.org/simple")
    if repository == "testpypi":
        return ("https://test.pypi.org/legacy/", "https://test.pypi.org/simple")
    raise ValueError(f"unsupported repository: {repository}")


def _clean_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for entry in output_dir.iterdir():
        if entry.name == ".gitignore":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _clear_directory_files(directory: Path) -> None:
    for entry in directory.iterdir():
        if entry.name.lower().startswith("readme"):
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _resolve_go_build_target(
    generator_dir: Path,
    requested_goos: str | None,
    requested_goarch: str | None,
) -> tuple[str, str, dict[str, str]]:
    env = os.environ.copy()
    if requested_goos:
        env["GOOS"] = requested_goos
    if requested_goarch:
        env["GOARCH"] = requested_goarch

    resolved = subprocess.run(
        ["go", "env", "GOOS", "GOARCH"],
        check=True,
        cwd=generator_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    values = [line.strip() for line in resolved.stdout.splitlines() if line.strip()]
    if len(values) != 2:
        raise ValueError(f"unable to resolve Go target from go env output: {resolved.stdout!r}")
    goos, goarch = values
    env["GOOS"] = goos
    env["GOARCH"] = goarch
    return goos, goarch, env


def _generator_binary_name(goos: str) -> str:
    if goos == "windows":
        return "sinan-generator.exe"
    return "sinan-generator"
