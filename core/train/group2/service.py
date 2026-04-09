"""Paired-input group2 training and prediction job helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import shutil
import subprocess

from core.common.jsonl import read_jsonl, write_jsonl
from core.train.group2.dataset import load_group2_dataset_config, load_group2_rows, resolve_group2_path


@dataclass(frozen=True)
class Group2TrainingJob:
    dataset_config: Path
    project_dir: Path
    model: str
    epochs: int
    batch: int
    run_name: str
    imgsz: int = 192
    device: str = "0"
    resume: bool = False

    def command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "python",
            "-m",
            "core.train.group2.runner",
            "train",
            "--dataset-config",
            str(self.dataset_config),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--model",
            self.model,
            "--epochs",
            str(self.epochs),
            "--batch",
            str(self.batch),
            "--imgsz",
            str(self.imgsz),
            "--device",
            self.device,
        ]
        if self.resume:
            command.append("--resume")
        return command

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group2PredictionJob:
    dataset_config: Path
    model_path: Path
    source: Path
    project_dir: Path
    run_name: str
    imgsz: int = 192
    device: str = "0"

    def output_dir(self) -> Path:
        return self.project_dir / self.run_name

    def command(self) -> list[str]:
        return [
            "uv",
            "run",
            "python",
            "-m",
            "core.train.group2.runner",
            "predict",
            "--dataset-config",
            str(self.dataset_config),
            "--model",
            str(self.model_path),
            "--source",
            str(self.source),
            "--project",
            str(self.project_dir),
            "--name",
            self.run_name,
            "--imgsz",
            str(self.imgsz),
            "--device",
            self.device,
        ]

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class Group2PredictionResult:
    output_dir: Path
    labels_path: Path
    sample_count: int
    command: str


def build_group2_training_job(
    dataset_config: Path,
    project_dir: Path,
    model: str = "paired_cnn_v1",
    run_name: str = "v1",
    *,
    epochs: int | None = None,
    batch: int | None = None,
    imgsz: int = 192,
    device: str = "0",
    resume: bool = False,
) -> Group2TrainingJob:
    return Group2TrainingJob(
        dataset_config=dataset_config,
        project_dir=project_dir,
        model=model,
        epochs=100 if epochs is None else epochs,
        batch=16 if batch is None else batch,
        run_name=run_name,
        imgsz=imgsz,
        device=device,
        resume=resume,
    )


def build_group2_prediction_job(
    dataset_config: Path,
    model_path: Path,
    source: Path,
    project_dir: Path,
    run_name: str,
    *,
    imgsz: int = 192,
    device: str = "0",
) -> Group2PredictionJob:
    return Group2PredictionJob(
        dataset_config=dataset_config,
        model_path=model_path,
        source=source,
        project_dir=project_dir,
        run_name=run_name,
        imgsz=imgsz,
        device=device,
    )


def execute_group2_training_job(job: Group2TrainingJob) -> int:
    _ensure_group2_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group2 数据集配置文件：{job.dataset_config}")
    if job.resume and Path(job.model).suffix == ".pt" and not Path(job.model).exists():
        raise RuntimeError(f"未找到可继续训练的检查点：{job.model}")
    try:
        completed = subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group2 训练启动器 `uv run python -m core.train.group2.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc
    return completed.returncode


def run_group2_prediction_job(job: Group2PredictionJob) -> Group2PredictionResult:
    _ensure_group2_training_dependencies()
    if not job.dataset_config.exists():
        raise RuntimeError(f"未找到 group2 数据集配置文件：{job.dataset_config}")
    if not job.model_path.exists():
        raise RuntimeError(f"未找到 group2 预测权重文件：{job.model_path}")
    if not job.source.exists():
        raise RuntimeError(f"未找到 group2 预测输入：{job.source}")

    source_rows = _load_prediction_source_rows(job)
    if _requires_per_sample_prediction(job, source_rows):
        return _run_group2_prediction_job_per_sample(job, source_rows)

    return _run_group2_prediction_subprocess(job)


def _run_group2_prediction_subprocess(job: Group2PredictionJob) -> Group2PredictionResult:
    try:
        subprocess.run(job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到 group2 预测启动器 `uv run python -m core.train.group2.runner`。"
            "请先安装 `uv`，并在当前训练环境中安装所需依赖。"
        ) from exc

    labels_path = job.output_dir() / "labels.jsonl"
    if not labels_path.exists():
        raise RuntimeError(f"group2 预测输出缺少 labels.jsonl：{labels_path}")
    return Group2PredictionResult(
        output_dir=job.output_dir(),
        labels_path=labels_path,
        sample_count=len(read_jsonl(labels_path)),
        command=job.command_string(),
    )


def _load_prediction_source_rows(job: Group2PredictionJob) -> list[dict[str, object]]:
    dataset_config = load_group2_dataset_config(job.dataset_config)
    return load_group2_rows(dataset_config, job.source)


def _requires_per_sample_prediction(
    job: Group2PredictionJob,
    source_rows: list[dict[str, object]],
) -> bool:
    from PIL import Image

    if len(source_rows) <= 1:
        return False

    dataset_config = load_group2_dataset_config(job.dataset_config)
    shapes: set[tuple[int, int, int, int]] = set()
    for row in source_rows:
        master_path = resolve_group2_path(dataset_config.root, Path(str(row["master_image"])))
        tile_path = resolve_group2_path(dataset_config.root, Path(str(row["tile_image"])))
        with Image.open(master_path) as master_image:
            master_width, master_height = master_image.size
        with Image.open(tile_path) as tile_image:
            tile_width, tile_height = tile_image.size
        shapes.add((master_width, master_height, tile_width, tile_height))
        if len(shapes) > 1:
            return True
    return False


def _run_group2_prediction_job_per_sample(
    job: Group2PredictionJob,
    source_rows: list[dict[str, object]],
) -> Group2PredictionResult:
    output_dir = job.output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    per_sample_source_dir = output_dir / "_per_sample_source"
    per_sample_output_dir = output_dir / "_per_sample_predict"

    predictions: list[dict[str, object]] = []
    commands: list[str] = []
    for row in source_rows:
        sample_id = str(row["sample_id"])
        sample_source_path = per_sample_source_dir / f"{sample_id}.jsonl"
        write_jsonl(sample_source_path, [row])
        sample_job = Group2PredictionJob(
            dataset_config=job.dataset_config,
            model_path=job.model_path,
            source=sample_source_path,
            project_dir=per_sample_output_dir,
            run_name=sample_id,
            imgsz=job.imgsz,
            device=job.device,
        )
        sample_result = _run_group2_prediction_subprocess(sample_job)
        sample_predictions = read_jsonl(sample_result.labels_path)
        if len(sample_predictions) != 1:
            raise RuntimeError(
                "group2 单样本预测返回了非法结果数量："
                f"sample_id={sample_id} count={len(sample_predictions)}"
            )
        predictions.extend(sample_predictions)
        commands.append(sample_result.command)

    labels_path = output_dir / "labels.jsonl"
    write_jsonl(labels_path, predictions)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "mode": "per_sample_group2_predict",
                "dataset_config": str(job.dataset_config),
                "source": str(job.source),
                "model": str(job.model_path),
                "sample_count": len(predictions),
                "labels_path": str(labels_path),
                "per_sample_source_dir": str(per_sample_source_dir),
                "per_sample_output_dir": str(per_sample_output_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return Group2PredictionResult(
        output_dir=output_dir,
        labels_path=labels_path,
        sample_count=len(predictions),
        command=_render_group2_prediction_command(commands),
    )


def _render_group2_prediction_command(commands: list[str]) -> str:
    if not commands:
        return "per-sample group2 prediction skipped: no samples"
    if len(commands) == 1:
        return commands[0]
    return f"per-sample group2 prediction x{len(commands)}; first_command={commands[0]}"


def _ensure_group2_training_dependencies() -> None:
    if shutil.which("uv") is None:
        raise RuntimeError(
            "未检测到 `uv`。请先安装 uv，再进入训练目录执行 `uv sync` 完成环境安装。"
        )

    missing_packages: list[str] = []
    for package_name in ("torch", "numpy", "PIL"):
        try:
            importlib.import_module(package_name)
        except Exception:
            missing_packages.append(package_name)

    if missing_packages:
        joined = "、".join(missing_packages)
        raise RuntimeError(
            "当前 group2 双输入训练环境缺少依赖："
            f"{joined}。\n"
            "请先执行训练目录初始化或安装命令：\n"
            "1. uv run sinan env setup-train --train-root <训练目录>\n"
            "2. 进入训练目录后执行 uv sync\n"
            "3. 再运行 uv run sinan train group2"
        )
