"""Run novice-friendly model test flows and export Chinese reports."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess

from core.predict.service import PredictionJob, count_images
from core.train.base import _ensure_training_dependencies, prepare_dataset_yaml_for_ultralytics


@dataclass(frozen=True)
class ValidationJob:
    task: str
    dataset_yaml: Path
    model_path: Path
    project_dir: Path
    run_name: str
    device: str = "0"
    imgsz: int = 640

    def output_dir(self) -> Path:
        return self.project_dir / self.run_name

    def command(self) -> list[str]:
        return [
            "uv",
            "run",
            "yolo",
            "detect",
            "val",
            f"data={self.dataset_yaml}",
            f"model={self.model_path}",
            f"device={self.device}",
            f"imgsz={self.imgsz}",
            f"project={self.project_dir}",
            f"name={self.run_name}",
            "exist_ok=True",
        ]

    def command_string(self) -> str:
        return " ".join(str(part) for part in self.command())


@dataclass(frozen=True)
class ModelTestRequest:
    task: str
    dataset_version: str
    train_name: str
    dataset_yaml: Path
    model_path: Path
    source: Path
    project_dir: Path
    report_dir: Path
    predict_name: str
    val_name: str
    conf: float = 0.25
    device: str = "0"
    imgsz: int = 640


@dataclass(frozen=True)
class ModelTestResult:
    task: str
    dataset_version: str
    train_name: str
    model_path: Path
    dataset_yaml: Path
    source: Path
    project_dir: Path
    report_dir: Path
    predict_output_dir: Path
    val_output_dir: Path
    source_image_count: int
    predicted_image_count: int
    metrics: dict[str, float | None]
    verdict_title: str
    verdict_detail: str
    next_actions: list[str]
    predict_command: str
    val_command: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in (
            "model_path",
            "dataset_yaml",
            "source",
            "project_dir",
            "report_dir",
            "predict_output_dir",
            "val_output_dir",
        ):
            payload[key] = str(payload[key])
        return payload

    def render_console_report(self) -> str:
        metric_lines = [
            f"- Precision（框出来的里有多少是真的）：{_format_metric(self.metrics['precision'])}",
            f"- Recall（该找出来的里找到了多少）：{_format_metric(self.metrics['recall'])}",
            f"- mAP50（综合看框和分类是否到位）：{_format_metric(self.metrics['map50'])}",
            f"- mAP50-95（更严格的综合指标）：{_format_metric(self.metrics['map50_95'])}",
        ]
        next_actions = "\n".join(f"- {item}" for item in self.next_actions)
        return "\n".join(
            [
                "模型测试完成",
                f"- 专项：{self.task}",
                f"- 数据版本：{self.dataset_version}",
                f"- 训练版本：{self.train_name}",
                f"- 权重文件：{self.model_path}",
                f"- 本次预测图片数：{self.source_image_count}",
                f"- 预测输出目录：{self.predict_output_dir}",
                f"- 验证输出目录：{self.val_output_dir}",
                f"- 中文报告目录：{self.report_dir}",
                f"- 初学者结论：{self.verdict_title}。{self.verdict_detail}",
                "",
                "关键指标：",
                *metric_lines,
                "",
                "下一步建议：",
                next_actions,
            ]
        )


def build_validation_job(
    task: str,
    dataset_yaml: Path,
    model_path: Path,
    project_dir: Path,
    run_name: str,
    *,
    device: str = "0",
    imgsz: int = 640,
) -> ValidationJob:
    return ValidationJob(
        task=task,
        dataset_yaml=dataset_yaml,
        model_path=model_path,
        project_dir=project_dir,
        run_name=run_name,
        device=device,
        imgsz=imgsz,
    )


def build_model_test_jobs(request: ModelTestRequest) -> tuple[PredictionJob, ValidationJob]:
    normalized_dataset = prepare_dataset_yaml_for_ultralytics(request.dataset_yaml)
    predict_job = PredictionJob(
        task=request.task,
        model_path=request.model_path,
        source=request.source,
        project_dir=request.project_dir,
        run_name=request.predict_name,
        conf=request.conf,
        device=request.device,
        imgsz=request.imgsz,
    )
    val_job = build_validation_job(
        task=request.task,
        dataset_yaml=normalized_dataset,
        model_path=request.model_path,
        project_dir=request.project_dir,
        run_name=request.val_name,
        device=request.device,
        imgsz=request.imgsz,
    )
    return predict_job, val_job


def run_model_test(request: ModelTestRequest) -> ModelTestResult:
    _ensure_training_dependencies()
    if not request.model_path.exists():
        raise RuntimeError(f"未找到测试权重文件：{request.model_path}")
    if not request.source.exists():
        raise RuntimeError(f"未找到测试图片来源：{request.source}")

    predict_job, val_job = build_model_test_jobs(request)
    source_image_count = count_images(request.source)

    try:
        subprocess.run(predict_job.command(), check=True)
        subprocess.run(val_job.command(), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到测试启动器 `uv run yolo`。请先安装 `uv`，并在当前训练环境中安装 "
            "`sinan-captcha[train]`。"
        ) from exc

    predicted_image_count = count_images(predict_job.output_dir())
    metrics = _read_validation_metrics(val_job.output_dir() / "results.csv")
    verdict_title, verdict_detail = _summarize_verdict(metrics)
    next_actions = _build_next_actions(metrics)
    result = ModelTestResult(
        task=request.task,
        dataset_version=request.dataset_version,
        train_name=request.train_name,
        model_path=request.model_path,
        dataset_yaml=request.dataset_yaml,
        source=request.source,
        project_dir=request.project_dir,
        report_dir=request.report_dir,
        predict_output_dir=predict_job.output_dir(),
        val_output_dir=val_job.output_dir(),
        source_image_count=source_image_count,
        predicted_image_count=predicted_image_count,
        metrics=metrics,
        verdict_title=verdict_title,
        verdict_detail=verdict_detail,
        next_actions=next_actions,
        predict_command=predict_job.command_string(),
        val_command=val_job.command_string(),
    )
    _write_reports(result)
    return result


def _read_validation_metrics(results_csv: Path) -> dict[str, float | None]:
    if not results_csv.exists():
        raise RuntimeError(f"验证完成后未找到 results.csv：{results_csv}")

    with results_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"验证结果为空：{results_csv}")

    latest = rows[-1]
    return {
        "precision": _read_float(latest, "metrics/precision(B)"),
        "recall": _read_float(latest, "metrics/recall(B)"),
        "map50": _read_float(latest, "metrics/mAP50(B)"),
        "map50_95": _read_float(latest, "metrics/mAP50-95(B)"),
        "fitness": _read_float(latest, "fitness"),
    }


def _read_float(row: dict[str, str], key: str) -> float | None:
    raw_value = row.get(key)
    if raw_value in {None, ""}:
        return None
    return float(raw_value)


def _summarize_verdict(metrics: dict[str, float | None]) -> tuple[str, str]:
    map50 = metrics["map50"]
    if map50 is None:
        return "验证结果不完整", "YOLO 已经跑完，但没有从 results.csv 读到 mAP50，请先检查验证输出目录。"
    if map50 >= 0.85:
        return "这轮模型已经比较稳", "可以先进入人工抽查和业务联调，再决定要不要继续压指标。"
    if map50 >= 0.7:
        return "这轮模型已经有明显效果", "已经不算白训，可以继续补难样本或微调参数，把结果再往上推。"
    if map50 >= 0.55:
        return "这轮模型已经学到东西", "但稳定性还不够，优先补数据质量和难样本，再继续训练。"
    return "这轮模型还在起步阶段", "先回头检查数据、标签和素材分布，不建议只靠硬拉 epoch。"


def _build_next_actions(metrics: dict[str, float | None]) -> list[str]:
    next_actions: list[str] = []
    precision = metrics["precision"]
    recall = metrics["recall"]
    map50 = metrics["map50"]

    if map50 is None:
        return [
            "先打开验证输出目录，确认 `results.csv`、`args.yaml` 和预测图片是否都已经生成。",
            "确认当前命令使用的是 `weights/best.pt`，不是旧版本权重。",
        ]

    if precision is not None and recall is not None and recall + 0.15 < precision:
        next_actions.append("当前更像是漏检偏多，优先补更多目标样本、复杂背景样本和边缘位置样本。")
    if precision is not None and recall is not None and precision + 0.15 < recall:
        next_actions.append("当前更像是误检偏多，优先清理错标、补干扰项和负样本。")
    if map50 < 0.7:
        next_actions.append("先固定一版验证集，不要边训练边改测试集，然后新增一个更干净的数据版本继续训练。")
    else:
        next_actions.append("保留当前数据版本不动，再开一个新训练名做对照实验，避免把好结果覆盖掉。")
    next_actions.append("每次只改一类因素，例如只换数据版本、只加 epoch、或只换模型大小，这样你才能看懂变化原因。")
    next_actions.append("如果只是训练被打断，用 `--resume` 继续；如果是拿上一轮最佳权重做新一轮微调，用 `--from-run` 新开一个训练名。")
    return next_actions


def _write_reports(result: ModelTestResult) -> None:
    result.report_dir.mkdir(parents=True, exist_ok=True)
    (result.report_dir / "summary.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (result.report_dir / "summary.md").write_text(_render_markdown(result), encoding="utf-8")


def _render_markdown(result: ModelTestResult) -> str:
    lines = [
        f"# {result.task} 模型测试报告",
        "",
        "## 初学者结论",
        "",
        f"- {result.verdict_title}",
        f"- {result.verdict_detail}",
        "- 这是一份入门级阅读口径，方便你先判断“这轮值不值得继续”。",
        "",
        "## 本次测试做了什么",
        "",
        f"- 已加载权重：`{result.model_path}`",
        f"- 已在验证集来源上执行 `predict`：`{result.source}`",
        f"- 已执行 `val` 验证：`{result.dataset_yaml}`",
        f"- 本次预测图片数：{result.source_image_count}",
        f"- 成功写出的预测图片数：{result.predicted_image_count}",
        "",
        "## 关键指标怎么读",
        "",
        f"- Precision（精确率）：{_format_metric(result.metrics['precision'])}",
        "  表示“模型框出来的结果里，有多少是真的”。",
        f"- Recall（召回率）：{_format_metric(result.metrics['recall'])}",
        "  表示“该找出来的目标里，模型实际找出来了多少”。",
        f"- mAP50：{_format_metric(result.metrics['map50'])}",
        "  可以把它先粗略理解成“这轮模型整体准不准”。",
        f"- mAP50-95：{_format_metric(result.metrics['map50_95'])}",
        "  这是更严格的综合指标，通常会比 mAP50 更低。",
        "",
        "## 输出目录",
        "",
        f"- 预测输出目录：`{result.predict_output_dir}`",
        f"- 验证输出目录：`{result.val_output_dir}`",
        f"- 中文报告目录：`{result.report_dir}`",
        "",
        "## 本次实际执行的底层命令",
        "",
        "```text",
        result.predict_command,
        result.val_command,
        "```",
        "",
        "## 下一步建议",
        "",
    ]
    lines.extend(f"- {item}" for item in result.next_actions)
    return "\n".join(lines) + "\n"


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"
