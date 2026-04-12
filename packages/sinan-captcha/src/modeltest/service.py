"""Run novice-friendly model test flows and export Chinese reports."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess

from common.jsonl import write_jsonl
from evaluate.service import EvaluationRequest, evaluate_model
from group2_semantics import (
    GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX,
    GROUP2_MODELTEST_BOOTSTRAP_POINT_HIT_THRESHOLD,
    GROUP2_MODELTEST_DATASET_GAP_IOU_THRESHOLD,
    GROUP2_MODELTEST_EFFECTIVE_IOU_THRESHOLD,
    GROUP2_MODELTEST_EFFECTIVE_POINT_HIT_THRESHOLD,
    GROUP2_MODELTEST_STRONG_IOU_THRESHOLD,
    GROUP2_MODELTEST_STRONG_POINT_HIT_THRESHOLD,
)
from predict.service import PredictionJob, count_images
from train.base import (
    _ensure_training_dependencies as _ensure_group1_training_dependencies,
    prepare_dataset_yaml_for_ultralytics,
)
from train.group1.dataset import load_group1_dataset_config, load_group1_rows
from train.group1.service import (
    Group1PredictionJob,
    build_group1_prediction_job,
    run_group1_prediction_job,
)
from train.group2.dataset import load_group2_dataset_config, load_group2_rows
from train.group2.service import (
    _ensure_group2_training_dependencies,
    Group2PredictionJob,
    build_group2_prediction_job,
    run_group2_prediction_job,
)


@dataclass(frozen=True)
class CommandPreview:
    command: str

    def command_string(self) -> str:
        return self.command


@dataclass(frozen=True)
class ValidationJob:
    task: str
    dataset_config: Path
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
            f"data={self.dataset_config}",
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
    dataset_config: Path
    model_path: Path
    query_model_path: Path | None
    source: Path
    project_dir: Path
    report_dir: Path
    predict_name: str
    val_name: str
    conf: float = 0.25
    device: str = "0"
    imgsz: int = 640
    embedder_model_path: Path | None = None


@dataclass(frozen=True)
class ModelTestResult:
    task: str
    dataset_version: str
    train_name: str
    model_path: Path
    query_model_path: Path | None
    dataset_config: Path
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
    embedder_model_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in (
            "model_path",
            "query_model_path",
            "embedder_model_path",
            "dataset_config",
            "source",
            "project_dir",
            "report_dir",
            "predict_output_dir",
            "val_output_dir",
        ):
            if payload[key] is not None:
                payload[key] = str(payload[key])
        return payload

    def render_console_report(self) -> str:
        metric_lines = _render_metric_lines(self.task, self.metrics)
        next_actions = "\n".join(f"- {item}" for item in self.next_actions)
        workflow_line = ""
        if self.task == "group1":
            workflow_line = "- 本次重点验证最终位置挑选：query splitter + proposal detector + icon embedder + matcher。"
        elif self.task == "group2":
            workflow_line = "- 本次重点验证最终定位结果，而不是单纯看中间特征。"
        return "\n".join(
            [
                "模型测试完成",
                f"- 专项：{self.task}",
                *([workflow_line] if workflow_line else []),
                f"- 数据版本：{self.dataset_version}",
                f"- 训练版本：{self.train_name}",
                f"- 主权重文件：{self.model_path}",
                *([f"- Query Parser 权重：{self.query_model_path}"] if self.query_model_path is not None else []),
                *([f"- Icon Embedder 权重：{self.embedder_model_path}"] if self.embedder_model_path is not None else []),
                f"- 本次预测样本数：{self.source_image_count}",
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
    dataset_config: Path,
    model_path: Path,
    project_dir: Path,
    run_name: str,
    *,
    device: str = "0",
    imgsz: int = 640,
) -> ValidationJob:
    return ValidationJob(
        task=task,
        dataset_config=dataset_config,
        model_path=model_path,
        project_dir=project_dir,
        run_name=run_name,
        device=device,
        imgsz=imgsz,
    )


def build_model_test_jobs(
    request: ModelTestRequest,
) -> tuple[PredictionJob | Group1PredictionJob | Group2PredictionJob, ValidationJob | CommandPreview]:
    if request.task == "group1":
        prediction_job = build_group1_prediction_job(
            dataset_config=request.dataset_config,
            proposal_model_path=request.model_path,
            embedder_model_path=request.embedder_model_path,
            source=request.source,
            project_dir=request.project_dir,
            run_name=request.predict_name,
            query_model_path=request.query_model_path,
            conf=request.conf,
            imgsz=request.imgsz,
            device=request.device,
        )
        gold_dir = request.report_dir / "_gold"
        evaluate_command = _build_group1_evaluate_command(
            gold_dir=gold_dir,
            prediction_dir=prediction_job.output_dir(),
            report_dir=request.project_dir / request.val_name,
        )
        return prediction_job, CommandPreview(evaluate_command)

    if request.task == "group2":
        prediction_job = build_group2_prediction_job(
            dataset_config=request.dataset_config,
            model_path=request.model_path,
            source=request.source,
            project_dir=request.project_dir,
            run_name=request.predict_name,
            imgsz=request.imgsz,
            device=request.device,
        )
        gold_dir = request.report_dir / "_gold"
        evaluate_command = _build_group2_evaluate_command(
            gold_dir=gold_dir,
            prediction_dir=prediction_job.output_dir(),
            report_dir=request.project_dir / request.val_name,
        )
        return prediction_job, CommandPreview(evaluate_command)

    normalized_dataset = prepare_dataset_yaml_for_ultralytics(request.dataset_config)
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
        dataset_config=normalized_dataset,
        model_path=request.model_path,
        project_dir=request.project_dir,
        run_name=request.val_name,
        device=request.device,
        imgsz=request.imgsz,
    )
    return predict_job, val_job


def run_model_test(request: ModelTestRequest) -> ModelTestResult:
    if request.task == "group1":
        return _run_group1_model_test(request)
    if request.task == "group2":
        return _run_group2_model_test(request)

    _ensure_training_dependencies("group1")
    if not request.model_path.exists():
        raise RuntimeError(f"未找到测试权重文件：{request.model_path}")
    if not request.source.exists():
        raise RuntimeError(f"未找到测试图片来源：{request.source}")

    predict_job, val_job = build_model_test_jobs(request)
    assert isinstance(predict_job, PredictionJob)
    assert isinstance(val_job, ValidationJob)
    source_image_count = count_images(request.source)

    _execute_and_capture_output(predict_job.command())
    val_output = _execute_and_capture_output(val_job.command())

    predicted_image_count = count_images(predict_job.output_dir())
    metrics = _read_validation_metrics(
        results_csv=val_job.output_dir() / "results.csv",
        command_output=val_output,
    )
    verdict_title, verdict_detail = _summarize_verdict("group1", metrics)
    next_actions = _build_next_actions("group1", metrics)
    result = ModelTestResult(
        task=request.task,
        dataset_version=request.dataset_version,
        train_name=request.train_name,
        model_path=request.model_path,
        query_model_path=None,
        embedder_model_path=None,
        dataset_config=request.dataset_config,
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


def _run_group1_model_test(request: ModelTestRequest) -> ModelTestResult:
    _ensure_training_dependencies("group1")
    if not request.model_path.exists():
        raise RuntimeError(f"未找到 group1 proposal detector 权重：{request.model_path}")
    if request.query_model_path is not None and not request.query_model_path.exists():
        raise RuntimeError(f"未找到 group1 query parser 权重：{request.query_model_path}")
    dataset_config = load_group1_dataset_config(request.dataset_config)
    if (
        dataset_config.is_instance_matching
        and request.embedder_model_path is not None
        and not request.embedder_model_path.exists()
    ):
        raise RuntimeError(f"未找到 group1 icon embedder 权重：{request.embedder_model_path}")
    if not request.source.exists():
        raise RuntimeError(f"未找到 group1 测试样本来源：{request.source}")

    gold_rows = load_group1_rows(dataset_config, request.source)
    prediction_job = build_group1_prediction_job(
        dataset_config=request.dataset_config,
        proposal_model_path=request.model_path,
        embedder_model_path=request.embedder_model_path,
        source=request.source,
        project_dir=request.project_dir,
        run_name=request.predict_name,
        query_model_path=request.query_model_path,
        conf=request.conf,
        imgsz=request.imgsz,
        device=request.device,
    )
    prediction_result = run_group1_prediction_job(prediction_job)

    gold_dir = request.report_dir / "_gold"
    write_jsonl(gold_dir / "labels.jsonl", gold_rows)
    evaluate_report_dir = request.project_dir / request.val_name
    evaluation = evaluate_model(
        EvaluationRequest(
            task="group1",
            gold_dir=gold_dir,
            prediction_dir=prediction_result.output_dir,
            report_dir=evaluate_report_dir,
        )
    )
    metrics = {
        "single_target_hit_rate": _metric_value(evaluation.metrics, "single_target_hit_rate"),
        "full_sequence_hit_rate": _metric_value(evaluation.metrics, "full_sequence_hit_rate"),
        "mean_center_error_px": _metric_value(evaluation.metrics, "mean_center_error_px"),
        "order_error_rate": _metric_value(evaluation.metrics, "order_error_rate"),
    }
    verdict_title, verdict_detail = _summarize_verdict("group1", metrics)
    next_actions = _build_next_actions("group1", metrics)
    result = ModelTestResult(
        task=request.task,
        dataset_version=request.dataset_version,
        train_name=request.train_name,
        model_path=request.model_path,
        query_model_path=request.query_model_path,
        embedder_model_path=request.embedder_model_path,
        dataset_config=request.dataset_config,
        source=request.source,
        project_dir=request.project_dir,
        report_dir=request.report_dir,
        predict_output_dir=prediction_result.output_dir,
        val_output_dir=evaluation.report_dir,
        source_image_count=len(gold_rows),
        predicted_image_count=prediction_result.sample_count,
        metrics=metrics,
        verdict_title=verdict_title,
        verdict_detail=verdict_detail,
        next_actions=next_actions,
        predict_command=prediction_result.command,
        val_command=_build_group1_evaluate_command(
            gold_dir=gold_dir,
            prediction_dir=prediction_result.output_dir,
            report_dir=evaluation.report_dir,
        ),
    )
    _write_reports(result)
    return result


def _run_group2_model_test(request: ModelTestRequest) -> ModelTestResult:
    _ensure_training_dependencies("group2")
    if not request.model_path.exists():
        raise RuntimeError(f"未找到测试权重文件：{request.model_path}")
    if not request.source.exists():
        raise RuntimeError(f"未找到测试样本来源：{request.source}")

    dataset_config = load_group2_dataset_config(request.dataset_config)
    gold_rows = load_group2_rows(dataset_config, request.source)
    prediction_job = build_group2_prediction_job(
        dataset_config=request.dataset_config,
        model_path=request.model_path,
        source=request.source,
        project_dir=request.project_dir,
        run_name=request.predict_name,
        imgsz=request.imgsz,
        device=request.device,
    )
    prediction_result = run_group2_prediction_job(prediction_job)

    gold_dir = request.report_dir / "_gold"
    write_jsonl(gold_dir / "labels.jsonl", gold_rows)
    evaluate_report_dir = request.project_dir / request.val_name
    evaluation = evaluate_model(
        EvaluationRequest(
            task="group2",
            gold_dir=gold_dir,
            prediction_dir=prediction_result.output_dir,
            report_dir=evaluate_report_dir,
        )
    )
    metrics = {
        "point_hit_rate": _metric_value(evaluation.metrics, "point_hit_rate"),
        "mean_center_error_px": _metric_value(evaluation.metrics, "mean_center_error_px"),
        "mean_iou": _metric_value(evaluation.metrics, "mean_iou"),
        "mean_inference_ms": _metric_value(evaluation.metrics, "mean_inference_ms"),
    }
    verdict_title, verdict_detail = _summarize_verdict("group2", metrics)
    next_actions = _build_next_actions("group2", metrics)
    result = ModelTestResult(
        task=request.task,
        dataset_version=request.dataset_version,
        train_name=request.train_name,
        model_path=request.model_path,
        query_model_path=None,
        embedder_model_path=None,
        dataset_config=request.dataset_config,
        source=request.source,
        project_dir=request.project_dir,
        report_dir=request.report_dir,
        predict_output_dir=prediction_result.output_dir,
        val_output_dir=evaluation.report_dir,
        source_image_count=len(gold_rows),
        predicted_image_count=prediction_result.sample_count,
        metrics=metrics,
        verdict_title=verdict_title,
        verdict_detail=verdict_detail,
        next_actions=next_actions,
        predict_command=prediction_result.command,
        val_command=_build_group2_evaluate_command(
            gold_dir=gold_dir,
            prediction_dir=prediction_result.output_dir,
            report_dir=evaluation.report_dir,
        ),
    )
    _write_reports(result)
    return result


def _ensure_training_dependencies(task: str) -> None:
    if task == "group2":
        _ensure_group2_training_dependencies()
        return
    _ensure_group1_training_dependencies()


def _execute_and_capture_output(command: list[str]) -> str:
    output_lines: list[str] = []
    try:
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="")
                output_lines.append(line)
            return_code = process.wait()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "未找到测试启动器 `uv run yolo`。请先安装 `uv`，并在当前训练环境中安装 "
            "`sinan-captcha[train]`。"
        ) from exc

    if return_code != 0:
        raise RuntimeError("模型测试失败，请先查看上面的 YOLO 原始输出。")
    return "".join(output_lines)


def _read_validation_metrics(results_csv: Path, command_output: str) -> dict[str, float | None]:
    if results_csv.exists():
        return _read_validation_metrics_from_csv(results_csv)

    parsed = _parse_validation_metrics_from_output(command_output)
    if parsed is not None:
        return parsed

    raise RuntimeError(
        "验证完成后未找到 `results.csv`，并且无法从终端输出中解析验证指标。"
        f"请检查验证输出目录：{results_csv.parent}"
    )


def _read_validation_metrics_from_csv(results_csv: Path) -> dict[str, float | None]:
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


def _parse_validation_metrics_from_output(command_output: str) -> dict[str, float | None] | None:
    pattern = re.compile(
        r"^\s*all\s+\d+\s+\d+\s+"
        r"(?P<precision>\d+(?:\.\d+)?)\s+"
        r"(?P<recall>\d+(?:\.\d+)?)\s+"
        r"(?P<map50>\d+(?:\.\d+)?)\s+"
        r"(?P<map50_95>\d+(?:\.\d+)?)\s*$",
        re.MULTILINE,
    )
    match = pattern.search(command_output)
    if match is None:
        return None

    return {
        "precision": float(match.group("precision")),
        "recall": float(match.group("recall")),
        "map50": float(match.group("map50")),
        "map50_95": float(match.group("map50_95")),
        "fitness": None,
    }


def _read_float(row: dict[str, str], key: str) -> float | None:
    raw_value = row.get(key)
    if raw_value in {None, ""}:
        return None
    return float(raw_value)


def _summarize_verdict(task: str, metrics: dict[str, float | None]) -> tuple[str, str]:
    if task == "group1":
        full_sequence_hit_rate = metrics.get("full_sequence_hit_rate")
        order_error_rate = metrics.get("order_error_rate")
        if full_sequence_hit_rate is None or order_error_rate is None:
            return "验证结果不完整", "group1 预测和评估已经跑完，但关键业务指标没有完整落盘，请先检查预测输出和评估目录。"
        if full_sequence_hit_rate >= 0.85 and order_error_rate <= 0.1:
            return "这轮双模型点击流水线已经比较稳", "可以开始做业务联调和难样本抽查，再决定是否继续追更高指标。"
        if full_sequence_hit_rate >= 0.7 and order_error_rate <= 0.2:
            return "这轮双模型点击流水线已经有明显效果", "可以继续补复杂背景和相似图标样本，把整组命中率再往上推。"
        if full_sequence_hit_rate >= 0.5:
            return "这轮模型已经学到部分顺序关系", "但整组成功率还不够，优先补 query/scene 成对困难样本。"
        return "这轮模型还在起步阶段", "先回头检查 query_items/scene_targets 契约、实例身份字段和三段模型训练是否一致。"

    if task == "group2":
        point_hit_rate = metrics.get("point_hit_rate")
        mean_iou = metrics.get("mean_iou")
        if point_hit_rate is None or mean_iou is None:
            return "验证结果不完整", "group2 预测和评估已经跑完，但关键指标没有完整落盘，请先检查预测输出和评估目录。"
        if (
            point_hit_rate >= GROUP2_MODELTEST_STRONG_POINT_HIT_THRESHOLD
            and mean_iou >= GROUP2_MODELTEST_STRONG_IOU_THRESHOLD
        ):
            return "这轮双输入定位已经比较稳", "可以开始做业务联调和难样本抽查，再决定是否继续追更高指标。"
        if (
            point_hit_rate >= GROUP2_MODELTEST_EFFECTIVE_POINT_HIT_THRESHOLD
            and mean_iou >= GROUP2_MODELTEST_EFFECTIVE_IOU_THRESHOLD
        ):
            return "这轮双输入定位已经有明显效果", "可以继续补复杂背景和弱对比样本，把定位误差再往下压。"
        if point_hit_rate >= GROUP2_MODELTEST_BOOTSTRAP_POINT_HIT_THRESHOLD:
            return "这轮模型已经学到配对关系", "但定位稳定性还不够，优先补更多图案形状和难背景。"
        return "这轮模型还在起步阶段", "先回头检查双输入样本契约、缺口图案一致性和训练集规模。"

    map50 = metrics.get("map50")
    if map50 is None:
        return "验证结果不完整", "YOLO 已经跑完，但没有从 results.csv 读到 mAP50，请先检查验证输出目录。"
    if map50 >= 0.85:
        return "这轮模型已经比较稳", "可以先进入人工抽查和业务联调，再决定要不要继续压指标。"
    if map50 >= 0.7:
        return "这轮模型已经有明显效果", "已经不算白训，可以继续补难样本或微调参数，把结果再往上推。"
    if map50 >= 0.55:
        return "这轮模型已经学到东西", "但稳定性还不够，优先补数据质量和难样本，再继续训练。"
    return "这轮模型还在起步阶段", "先回头检查数据、标签和素材分布，不建议只靠硬拉 epoch。"


def _build_next_actions(task: str, metrics: dict[str, float | None]) -> list[str]:
    if task == "group1":
        next_actions: list[str] = []
        full_sequence_hit_rate = metrics.get("full_sequence_hit_rate")
        order_error_rate = metrics.get("order_error_rate")
        center_error = metrics.get("mean_center_error_px")
        if full_sequence_hit_rate is not None and full_sequence_hit_rate < 0.7:
            next_actions.append("优先补更多 query/scene 成对难样本，特别是相似图标、边缘位置和复杂背景样本。")
        if order_error_rate is not None and order_error_rate > 0.2:
            next_actions.append("重点检查 query splitter 的切分排序和 matcher 规则，确认 query_items 的 order 恢复是否稳定。")
        if center_error is not None and center_error > 12:
            next_actions.append("当前更像是 proposal detector 定位偏差偏大，建议固定数据集后单独调 imgsz、batch 或继续训练轮数。")
        if not next_actions:
            next_actions.append("保留当前 pipeline dataset 不动，再开一个新训练名做对照实验，避免把好结果覆盖掉。")
        next_actions.append("如果只是训练被打断，用 `--resume` 继续；如果是沿用上一轮最佳权重开新实验，用 `--from-run`。")
        next_actions.append("每次只改一类因素，例如只换数据版本、只加 epoch、或只换子模型初始化权重，这样你才能看懂变化原因。")
        return next_actions

    if task == "group2":
        next_actions: list[str] = []
        point_hit_rate = metrics.get("point_hit_rate")
        mean_iou = metrics.get("mean_iou")
        center_error = metrics.get("mean_center_error_px")
        if point_hit_rate is not None and point_hit_rate < GROUP2_MODELTEST_EFFECTIVE_POINT_HIT_THRESHOLD:
            next_actions.append("优先补更多真实图案缺口样本，特别是弱对比背景和边缘位置样本。")
        if mean_iou is not None and mean_iou < GROUP2_MODELTEST_DATASET_GAP_IOU_THRESHOLD:
            next_actions.append("重点检查 tile 图案和主图缺口是否严格同源，先清理任何形状不一致样本。")
        if center_error is not None and center_error > GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX:
            next_actions.append("当前更像是定位偏移偏大，建议先固定一版数据集，再单独调 imgsz、batch 或继续训练轮数。")
        if not next_actions:
            next_actions.append("保留当前 paired dataset 不动，再开一个新训练名做对照实验，避免把好结果覆盖掉。")
        next_actions.append("如果只是训练被打断，用 `--resume` 继续；如果是沿用上一轮最佳权重开新实验，用 `--from-run`。")
        next_actions.append("每次只改一类因素，例如只换数据版本、只加 epoch、或只调 imgsz，这样你才能看懂变化原因。")
        return next_actions

    next_actions = []
    precision = metrics.get("precision")
    recall = metrics.get("recall")
    map50 = metrics.get("map50")

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
    metric_lines = _render_markdown_metric_lines(result.task, result.metrics)
    lines = [
        f"# {result.task} 模型测试报告",
        "",
        "## 初学者结论",
        "",
        f"- {result.verdict_title}",
        f"- {result.verdict_detail}",
        "- 这是一份入门级阅读口径，方便你先判断“这轮值不值得继续”。",
        *(
            ["- 这次重点验证最终位置挑选链路：query splitter + proposal detector + icon embedder + matcher。"]
            if result.task == "group1"
            else []
        ),
        "",
        "## 本次测试做了什么",
        "",
        f"- 已加载主权重：`{result.model_path}`",
        *([f"- 已加载 Query Parser 权重：`{result.query_model_path}`"] if result.query_model_path is not None else []),
        *([f"- 已加载 Icon Embedder 权重：`{result.embedder_model_path}`"] if result.embedder_model_path is not None else []),
        f"- 已在验证集来源上执行预测：`{result.source}`",
        f"- 已执行验证/评估：`{result.dataset_config}`",
        f"- 本次预测样本数：{result.source_image_count}",
        f"- 成功写出的预测样本数：{result.predicted_image_count}",
        "",
        "## 关键指标怎么读",
        "",
        *metric_lines,
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


def _render_metric_lines(task: str, metrics: dict[str, float | None]) -> list[str]:
    if task == "group1":
        return [
            f"- 单目标命中率（single_target_hit_rate）：{_format_metric(metrics.get('single_target_hit_rate'))}",
            f"- 整组命中率（full_sequence_hit_rate）：{_format_metric(metrics.get('full_sequence_hit_rate'))}",
            f"- 平均中心误差（mean_center_error_px）：{_format_metric(metrics.get('mean_center_error_px'))}",
            f"- 顺序错误率（order_error_rate）：{_format_metric(metrics.get('order_error_rate'))}",
        ]
    if task == "group2":
        return [
            f"- 点位命中率（point_hit_rate）：{_format_metric(metrics.get('point_hit_rate'))}",
            f"- 平均中心误差（mean_center_error_px）：{_format_metric(metrics.get('mean_center_error_px'))}",
            f"- 平均 IoU（mean_iou）：{_format_metric(metrics.get('mean_iou'))}",
            f"- 平均推理耗时（mean_inference_ms）：{_format_metric(metrics.get('mean_inference_ms'))}",
        ]
    return [
        f"- Precision（框出来的里有多少是真的）：{_format_metric(metrics.get('precision'))}",
        f"- Recall（该找出来的里找到了多少）：{_format_metric(metrics.get('recall'))}",
        f"- mAP50（综合看框和分类是否到位）：{_format_metric(metrics.get('map50'))}",
        f"- mAP50-95（更严格的综合指标）：{_format_metric(metrics.get('map50_95'))}",
    ]


def _render_markdown_metric_lines(task: str, metrics: dict[str, float | None]) -> list[str]:
    if task == "group1":
        return [
            f"- 单目标命中率（single_target_hit_rate）：{_format_metric(metrics.get('single_target_hit_rate'))}",
            "  表示 query 里每个目标图标是否都能在 scene 中找到正确点位。",
            f"- 整组命中率（full_sequence_hit_rate）：{_format_metric(metrics.get('full_sequence_hit_rate'))}",
            "  表示一整张验证码是否能按顺序一次性全部点对。",
            f"- 平均中心误差（mean_center_error_px）：{_format_metric(metrics.get('mean_center_error_px'))}",
            "  表示预测点击点离真实目标中心平均差了多少像素。",
            f"- 顺序错误率（order_error_rate）：{_format_metric(metrics.get('order_error_rate'))}",
            "  表示 query 顺序恢复或匹配阶段出错的比例。",
        ]
    if task == "group2":
        return [
            f"- 点位命中率（point_hit_rate）：{_format_metric(metrics.get('point_hit_rate'))}",
            "  表示“滑块 tile 放回去后，目标中心点是否落在可接受误差范围内”。",
            f"- 平均中心误差（mean_center_error_px）：{_format_metric(metrics.get('mean_center_error_px'))}",
            "  表示预测缺口中心点离真实中心点平均差了多少像素。",
            f"- mean_iou：{_format_metric(metrics.get('mean_iou'))}",
            "  表示预测缺口框和真实缺口框的平均重叠程度。",
            f"- mean_inference_ms：{_format_metric(metrics.get('mean_inference_ms'))}",
            "  表示单条 paired 样本平均推理耗时。",
        ]
    return [
        f"- Precision（精确率）：{_format_metric(metrics.get('precision'))}",
        "  表示“模型框出来的结果里，有多少是真的”。",
        f"- Recall（召回率）：{_format_metric(metrics.get('recall'))}",
        "  表示“该找出来的目标里，模型实际找出来了多少”。",
        f"- mAP50：{_format_metric(metrics.get('map50'))}",
        "  可以把它先粗略理解成“这轮模型整体准不准”。",
        f"- mAP50-95：{_format_metric(metrics.get('map50_95'))}",
        "  这是更严格的综合指标，通常会比 mAP50 更低。",
    ]


def _build_group1_evaluate_command(gold_dir: Path, prediction_dir: Path, report_dir: Path) -> str:
    return (
        "uv run sinan evaluate"
        f" --task group1 --gold-dir {gold_dir}"
        f" --prediction-dir {prediction_dir}"
        f" --report-dir {report_dir}"
    )


def _build_group2_evaluate_command(gold_dir: Path, prediction_dir: Path, report_dir: Path) -> str:
    return (
        "uv run sinan evaluate"
        f" --task group2 --gold-dir {gold_dir}"
        f" --prediction-dir {prediction_dir}"
        f" --report-dir {report_dir}"
    )


def _metric_value(metrics: dict[str, float | None], key: str) -> float | None:
    value = metrics.get(key)
    if value is None:
        return None
    return float(value)
def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"
