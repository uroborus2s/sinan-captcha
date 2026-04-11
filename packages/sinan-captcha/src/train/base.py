"""Common training job helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import shutil
import subprocess

from common.paths import default_work_root


@dataclass(frozen=True)
class TrainingJob:
    task: str
    dataset_yaml: Path
    model: str
    epochs: int
    batch: int
    imgsz: int = 640
    device: str = "0"
    project_dir: Path | None = None
    run_name: str = "v1"
    resume: bool = False

    def command(self) -> list[str]:
        if self.resume:
            command = [
                "uv",
                "run",
                "yolo",
                "detect",
                "train",
                "resume",
                f"model={self.model}",
            ]
            if self.device:
                command.append(f"device={self.device}")
            return command

        command = [
            "uv",
            "run",
            "yolo",
            "detect",
            "train",
            f"data={self.dataset_yaml}",
            f"model={self.model}",
            f"imgsz={self.imgsz}",
            f"epochs={self.epochs}",
            f"batch={self.batch}",
            f"device={self.device}",
            f"name={self.run_name}",
        ]
        if self.project_dir is not None:
            command.append(f"project={self.project_dir}")
        return command

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


def default_dataset_yaml(train_root: Path, task: str, dataset_version: str) -> Path:
    return train_root / "datasets" / task / dataset_version / "yolo" / "dataset.yaml"


def default_train_root(start: Path | None = None) -> Path:
    return default_work_root(start)


def default_dataset_config(train_root: Path, task: str, dataset_version: str) -> Path:
    if task in {"group1", "group2"}:
        return train_root / "datasets" / task / dataset_version / "dataset.json"
    return default_dataset_yaml(train_root, task, dataset_version)


def default_project_dir(train_root: Path, task: str) -> Path:
    return train_root / "runs" / task


def default_report_dir(train_root: Path, task: str) -> Path:
    return train_root / "reports" / task


def default_run_dir(train_root: Path, task: str, run_name: str) -> Path:
    return default_project_dir(train_root, task) / run_name


def default_run_weights(train_root: Path, task: str, run_name: str, filename: str) -> Path:
    return default_run_dir(train_root, task, run_name) / "weights" / filename


def default_best_weights(train_root: Path, task: str, run_name: str) -> Path:
    return default_run_weights(train_root, task, run_name, "best.pt")


def default_last_weights(train_root: Path, task: str, run_name: str) -> Path:
    return default_run_weights(train_root, task, run_name, "last.pt")


def preferred_checkpoint_path(best_path: Path, last_path: Path) -> Path:
    if best_path.exists():
        return best_path
    if last_path.exists():
        return last_path
    return best_path


def preferred_run_checkpoint(train_root: Path, task: str, run_name: str) -> Path:
    return preferred_checkpoint_path(
        default_best_weights(train_root, task, run_name),
        default_last_weights(train_root, task, run_name),
    )


def default_predict_source(train_root: Path, task: str, dataset_version: str) -> Path:
    if task in {"group1", "group2"}:
        return train_root / "datasets" / task / dataset_version / "splits" / "val.jsonl"
    return train_root / "datasets" / task / dataset_version / "yolo" / "images" / "val"


def execute_training_job(job: TrainingJob) -> int:
    _ensure_training_dependencies()
    try:
        if job.resume:
            if Path(job.model).suffix == ".pt" and not Path(job.model).exists():
                raise RuntimeError(f"未找到可继续训练的检查点：{job.model}")
            command = job.command()
        else:
            dataset_yaml = prepare_dataset_yaml_for_ultralytics(job.dataset_yaml)
            command = TrainingJob(
                task=job.task,
                dataset_yaml=dataset_yaml,
                model=job.model,
                epochs=job.epochs,
                batch=job.batch,
                imgsz=job.imgsz,
                device=job.device,
                project_dir=job.project_dir,
                run_name=job.run_name,
                resume=job.resume,
            ).command()
        completed = subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到训练启动器 `uv run yolo`。请先安装 `uv`，并在当前训练环境中安装 "
            "`sinan-captcha[train]`。"
        ) from exc
    return completed.returncode


def prepare_dataset_yaml_for_ultralytics(dataset_yaml: Path) -> Path:
    if not dataset_yaml.exists():
        raise RuntimeError(f"未找到训练数据集配置文件：{dataset_yaml}")
    content = dataset_yaml.read_text(encoding="utf-8")
    rewritten = _rewrite_relative_dataset_root(content, dataset_yaml.parent.resolve())
    if rewritten == content:
        return dataset_yaml

    normalized_dir = dataset_yaml.parent / ".sinan"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = normalized_dir / "dataset.ultralytics.yaml"
    normalized_path.write_text(rewritten, encoding="utf-8")
    return normalized_path


def _rewrite_relative_dataset_root(content: str, dataset_root: Path) -> str:
    rewritten_lines: list[str] = []
    changed = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("path:"):
            rewritten_lines.append(line)
            continue

        raw_value = stripped.split(":", 1)[1].strip()
        if not raw_value:
            rewritten_lines.append(line)
            continue

        if _is_absolute_dataset_path(raw_value):
            rewritten_lines.append(line)
            continue

        resolved_root = (dataset_root / raw_value).resolve()
        rewritten_lines.append(f"path: {resolved_root.as_posix()}")
        changed = True

    if not changed:
        return content
    return "\n".join(rewritten_lines) + "\n"


def _is_absolute_dataset_path(value: str) -> bool:
    normalized = value.strip().strip("'\"")
    return PureWindowsPath(normalized).is_absolute() or PurePosixPath(normalized).is_absolute()


def _ensure_training_dependencies() -> None:
    if shutil.which("uv") is None:
        raise RuntimeError(
            "未检测到 `uv`。请先安装 uv，再进入训练目录执行 `uv sync` 完成环境安装。"
        )

    missing_packages: list[str] = []
    for package_name in ("torch", "ultralytics"):
        try:
            importlib.import_module(package_name)
        except Exception:
            missing_packages.append(package_name)

    if missing_packages:
        joined = "、".join(missing_packages)
        raise RuntimeError(
            "当前训练环境缺少依赖："
            f"{joined}。\n"
            "请先执行训练目录初始化或安装命令：\n"
            "1. uv run sinan env setup-train --train-root <训练目录>\n"
            "2. 进入训练目录后执行 uv sync\n"
            "3. 再运行 uv run sinan train group1|group2"
        )
