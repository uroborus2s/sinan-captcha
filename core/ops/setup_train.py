"""Bootstrap a dedicated training root as an independent uv project."""

from __future__ import annotations

import argparse
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
import platform
import re
import shutil
import subprocess
import textwrap

from core._version import VERSION as PACKAGE_VERSION
from core.auto_train import opencode_assets


@dataclass(frozen=True)
class TorchBackend:
    name: str
    index_name: str
    index_url: str


@dataclass(frozen=True)
class TrainingSetupPlan:
    train_root: Path
    package_spec: str
    torch_backend: TorchBackend
    cuda_version: str | None
    python_version: str
    generator_root: Path | None = None


TORCH_BACKENDS: dict[str, TorchBackend] = {
    "cpu": TorchBackend("cpu", "pytorch-cpu", "https://download.pytorch.org/whl/cpu"),
    "cu118": TorchBackend("cu118", "pytorch-cu118", "https://download.pytorch.org/whl/cu118"),
    "cu126": TorchBackend("cu126", "pytorch-cu126", "https://download.pytorch.org/whl/cu126"),
    "cu128": TorchBackend("cu128", "pytorch-cu128", "https://download.pytorch.org/whl/cu128"),
    "cu130": TorchBackend("cu130", "pytorch-cu130", "https://download.pytorch.org/whl/cu130"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a dedicated training root and install its runtime environment.")
    parser.add_argument("--train-root", type=Path, default=Path.cwd() / "sinan-captcha-work")
    parser.add_argument("--generator-root", type=Path, default=None)
    parser.add_argument("--package-spec", default=_default_package_spec())
    parser.add_argument(
        "--torch-backend",
        choices=("auto", "cpu", "cu118", "cu126", "cu128", "cu130"),
        default="auto",
    )
    parser.add_argument("--yes", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if shutil.which("uv") is None:
        parser.exit(1, "未检测到 `uv`，请先安装 uv 后再执行该命令。\n")

    cuda_version = detect_cuda_version()
    try:
        torch_backend = resolve_torch_backend(cuda_version, override=args.torch_backend)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")

    plan = TrainingSetupPlan(
        train_root=args.train_root.resolve(),
        package_spec=args.package_spec,
        torch_backend=torch_backend,
        cuda_version=cuda_version,
        python_version="3.12",
        generator_root=args.generator_root.resolve() if args.generator_root is not None else None,
    )

    print(render_setup_summary(plan))
    if not args.yes and not _confirm():
        print("已取消创建训练目录。")
        return 1

    prepare_training_root(plan)
    sync_training_root(plan.train_root)
    print(
        "\n训练目录已创建完成。\n"
        f"- 训练目录：{plan.train_root}\n"
        "- 现在你可以把 group1 pipeline dataset 和 group2 paired dataset 拷贝到 datasets/ 下，"
        "或者让生成器直接输出到这个训练目录的 datasets/ 下。"
    )
    return 0


def resolve_torch_backend(cuda_version: str | None, *, override: str) -> TorchBackend:
    if override != "auto":
        return TORCH_BACKENDS[override]
    if cuda_version is None:
        return TORCH_BACKENDS["cpu"]

    normalized = _parse_version_tuple(cuda_version)
    if normalized is None:
        raise ValueError(f"无法识别 CUDA 版本：{cuda_version}")

    if normalized == (11, 8):
        return TORCH_BACKENDS["cu118"]
    if normalized >= (13, 0):
        return TORCH_BACKENDS["cu130"]
    if normalized >= (12, 8):
        return TORCH_BACKENDS["cu128"]
    if normalized >= (12, 6):
        return TORCH_BACKENDS["cu126"]
    raise ValueError(
        "当前自动安装矩阵仅支持 CUDA 11.8、12.6+、13.0+ 或 CPU。"
        f"检测到 {cuda_version}，请升级驱动后重试，或使用 --torch-backend 手动指定。"
    )


def detect_cuda_version() -> str | None:
    nvidia_smi_path = shutil.which("nvidia-smi")
    if nvidia_smi_path is None:
        return None
    try:
        result = subprocess.run(
            [nvidia_smi_path],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    match = re.search(r"CUDA Version:\s*([0-9.]+)", result.stdout)
    if match is None:
        return None
    return match.group(1)


def prepare_training_root(plan: TrainingSetupPlan) -> None:
    plan.train_root.mkdir(parents=True, exist_ok=True)
    for relative in (
        "datasets/group1",
        "datasets/group2",
        "runs/group1",
        "runs/group2",
        "reports/group1",
        "reports/group2",
    ):
        (plan.train_root / relative).mkdir(parents=True, exist_ok=True)
    opencode_assets.copy_opencode_assets(plan.train_root)

    (plan.train_root / ".python-version").write_text(f"{plan.python_version}\n", encoding="utf-8")
    (plan.train_root / "pyproject.toml").write_text(render_train_pyproject(plan), encoding="utf-8")
    (plan.train_root / "README-训练机使用说明.txt").write_text(
        render_train_readme(plan),
        encoding="utf-8",
    )


def sync_training_root(train_root: Path) -> None:
    subprocess.run(["uv", "python", "install", "3.12"], check=True)
    subprocess.run(["uv", "sync"], check=True, cwd=train_root)


def render_setup_summary(plan: TrainingSetupPlan) -> str:
    generator_root = plan.generator_root or (plan.train_root.parent / "sinan-captcha-generator")
    generator_workspace = generator_root / "workspace"
    cuda_value = plan.cuda_version or "未检测到，可按 CPU 环境创建"
    return textwrap.dedent(
        f"""
        即将创建独立训练目录，并自动安装训练环境：

        - 操作系统：{platform.system()}
        - 训练目录：{plan.train_root}
        - 推荐生成器安装目录：{generator_root}
        - 推荐生成器工作区：{generator_workspace}
        - Python 版本：{plan.python_version}
        - 检测到的 CUDA 版本：{cuda_value}
        - 选定的 PyTorch 后端：{plan.torch_backend.name}
        - 将安装的训练包：{plan.package_spec}

        训练目录创建完成后：
        1. 你可以把现成数据集拷贝到：
           - {plan.train_root / "datasets" / "group1"}
           - {plan.train_root / "datasets" / "group2"}
        2. 也可以让生成器直接输出到训练目录，例如：
           - group1 raw -> {plan.train_root / "datasets" / "group1" / "v1" / "raw"}
           - group1 pipeline -> {plan.train_root / "datasets" / "group1" / "v1"}
           - group2 raw -> {plan.train_root / "datasets" / "group2" / "v1" / ".sinan" / "raw"}
           - group2 paired -> {plan.train_root / "datasets" / "group2" / "v1"}
        3. 如果希望把生成器工作区固定在安装目录下，后续生成器命令统一带上：
           - --workspace {generator_workspace}
        4. 训练目录会自动包含：
           - {plan.train_root / ".opencode" / "commands"}
           - {plan.train_root / ".opencode" / "skills"}
        5. `opencode` 路线下建议直接在训练目录启动：
           - opencode serve --port 4096
        6. 训练命令在训练目录内执行：
           - uv run sinan train group1 --dataset-version v1 --name firstpass
           - uv run sinan train group2 --dataset-version v1 --name firstpass
        """
    ).strip()


def render_train_pyproject(plan: TrainingSetupPlan) -> str:
    return textwrap.dedent(
        f"""
        [project]
        name = "sinan-captcha-train"
        version = "{PACKAGE_VERSION}"
        requires-python = ">={plan.python_version},<{int(plan.python_version.split('.')[0])}.{int(plan.python_version.split('.')[1]) + 1}"
        dependencies = [
          "{plan.package_spec}",
          "torch",
          "torchvision",
          "torchaudio",
        ]

        [[tool.uv.index]]
        name = "{plan.torch_backend.index_name}"
        url = "{plan.torch_backend.index_url}"
        explicit = true

        [tool.uv.sources]
        torch = [{{ index = "{plan.torch_backend.index_name}" }}]
        torchvision = [{{ index = "{plan.torch_backend.index_name}" }}]
        torchaudio = [{{ index = "{plan.torch_backend.index_name}" }}]
        """
    ).strip() + "\n"


def render_train_readme(plan: TrainingSetupPlan) -> str:
    generator_root = plan.generator_root or (plan.train_root.parent / "sinan-captcha-generator")
    generator_workspace = generator_root / "workspace"
    return textwrap.dedent(
        f"""
        训练目录说明
        ==============

        1. 当前目录是训练目录，不存放生成器素材。
        2. 生成器建议放到独立安装目录：{generator_root}
        3. 如果希望生成器工作区跟安装目录放在一起，建议固定为：{generator_workspace}
        4. 当前目录会自动包含：
           - .opencode/commands
           - .opencode/skills
        5. 如果要启用 `auto-train --judge-provider opencode`，建议直接在当前目录执行：
           - opencode serve --port 4096
        6. 训练数据放置方式：
           - 直接拷贝 group1 pipeline dataset 到 datasets/group1/<版本>
           - 直接拷贝 group2 paired dataset 到 datasets/group2/<版本>
           - 或让生成器直接输出到训练目录下的 datasets/
        7. 生成器命令示例：
           - sinan-generator workspace init --workspace {generator_workspace}
           - sinan-generator materials import --workspace {generator_workspace} --from <materials-pack>
           - sinan-generator make-dataset --workspace {generator_workspace} --task group1 --dataset-dir {plan.train_root / "datasets" / "group1" / "v1"}
           - sinan-generator make-dataset --workspace {generator_workspace} --task group2 --dataset-dir {plan.train_root / "datasets" / "group2" / "v1"}
        8. 训练命令示例：
           - uv run sinan train group1 --dataset-version v1 --name firstpass
           - uv run sinan train group2 --dataset-version v1 --name firstpass
        9. 评估命令示例：
           - uv run sinan evaluate --task group1 --gold-dir <gold-dir> --prediction-dir <pred-dir> --report-dir reports/group1/eval
        """
    ).strip() + "\n"


def _confirm() -> bool:
    response = input("确认创建训练目录并自动安装依赖吗？[y/N]: ").strip().lower()
    return response in {"y", "yes"}


def _default_package_spec() -> str:
    try:
        version = importlib.metadata.version("sinan-captcha")
    except importlib.metadata.PackageNotFoundError:
        version = PACKAGE_VERSION
    return f"sinan-captcha[train]=={version}"


def _parse_version_tuple(raw: str) -> tuple[int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)", raw)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


if __name__ == "__main__":
    raise SystemExit(main())
