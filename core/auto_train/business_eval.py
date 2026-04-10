"""Reviewed business-exam helpers for autonomous training."""

from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import random
from typing import Any, Callable

from core.auto_train import contracts
from core.common.jsonl import read_jsonl, write_jsonl
from core.dataset.validation import (
    get_group1_scene_targets,
    get_group2_target,
    validate_group1_row,
    validate_group2_row,
)
from core.evaluate.service import EvaluationRequest, evaluate_model
from core.modeltest.service import ModelTestRequest, ModelTestResult, run_model_test
from core.train.base import default_dataset_config, preferred_checkpoint_path, preferred_run_checkpoint
from core.train.group1.service import (
    QUERY_COMPONENT,
    SCENE_COMPONENT,
    group1_component_best_weights,
    group1_component_last_weights,
)

ModelTestExecutor = Callable[[ModelTestRequest], ModelTestResult]


def load_reviewed_exam_rows(task: str, cases_root: Path) -> list[dict[str, Any]]:
    labels_path = cases_root / "labels.jsonl"
    if not labels_path.exists():
        raise RuntimeError(f"未找到 reviewed 试卷 labels.jsonl：{labels_path}")
    rows = read_jsonl(labels_path)
    if task == "group1":
        return [validate_group1_row(row) for row in rows]
    if task == "group2":
        return [validate_group2_row(row) for row in rows]
    raise ValueError(f"unsupported business eval task: {task}")


def select_exam_sample(
    rows: list[dict[str, Any]],
    *,
    sample_size: int,
    sample_key: str,
) -> list[dict[str, Any]]:
    if sample_size <= 0:
        raise ValueError("sample_size must be greater than 0")
    if len(rows) <= sample_size:
        return sorted(rows, key=lambda item: str(item["sample_id"]))
    shuffled = list(rows)
    random.Random(sample_key).shuffle(shuffled)
    return sorted(shuffled[:sample_size], key=lambda item: str(item["sample_id"]))


def materialize_sampled_source(
    *,
    task: str,
    cases_root: Path,
    sampled_rows: list[dict[str, Any]],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_path = output_dir / "labels.jsonl"
    rewritten_rows = [_rewrite_row_image_paths(task=task, cases_root=cases_root, row=row) for row in sampled_rows]
    write_jsonl(labels_path, rewritten_rows)
    return labels_path


def run_reviewed_business_eval(
    *,
    trial_id: str,
    task: str,
    train_root: Path,
    dataset_version: str,
    train_name: str,
    cases_root: Path,
    report_dir: Path,
    device: str,
    imgsz: int,
    success_threshold: float,
    min_cases: int,
    sample_size: int,
    point_tolerance_px: int,
    iou_threshold: float,
    modeltest_runner: ModelTestExecutor | None = None,
) -> contracts.BusinessEvalRecord:
    all_rows = load_reviewed_exam_rows(task, cases_root)
    available_cases = len(all_rows)
    if available_cases < min_cases:
        raise RuntimeError(
            "reviewed 试卷池样本不足，无法执行商业测试。"
            f"要求至少 {min_cases} 组，实际只有 {available_cases} 组：{cases_root}"
        )

    sampled_rows = select_exam_sample(
        all_rows,
        sample_size=sample_size,
        sample_key=f"{trial_id}:{train_name}:{cases_root.resolve()}",
    )
    sampled_source = materialize_sampled_source(
        task=task,
        cases_root=cases_root,
        sampled_rows=sampled_rows,
        output_dir=report_dir / "_sampled_source",
    )
    model_request = _build_business_model_test_request(
        task=task,
        train_root=train_root,
        dataset_version=dataset_version,
        train_name=train_name,
        source=sampled_source,
        report_dir=report_dir,
        device=device,
        imgsz=imgsz,
    )
    model_result = (modeltest_runner or run_model_test)(model_request)

    evaluation = evaluate_model(
        EvaluationRequest(
            task=task,
            gold_dir=sampled_source.parent,
            prediction_dir=model_result.predict_output_dir,
            report_dir=report_dir / "evaluation",
            point_tolerance_px=point_tolerance_px,
            iou_threshold=iou_threshold,
        )
    )
    gold_rows = load_reviewed_exam_rows(task, sampled_source.parent)
    prediction_rows = _load_prediction_rows(task, model_result.predict_output_dir / "labels.jsonl")
    case_results = build_case_results(
        task=task,
        gold_rows=gold_rows,
        prediction_rows=prediction_rows,
        point_tolerance_px=point_tolerance_px,
        iou_threshold=iou_threshold,
    )
    if task == "group2":
        case_results = _attach_group2_failure_artifacts(case_results=case_results, report_dir=report_dir)
    passed_cases = sum(1 for item in case_results if item.success)
    total_cases = len(case_results)
    success_rate = 0.0 if total_cases == 0 else passed_cases / float(total_cases)
    commercial_ready = success_rate >= success_threshold
    evidence = [
        f"available_cases={available_cases}",
        f"sample_size={sample_size}",
        f"total_cases={total_cases}",
        f"passed_cases={passed_cases}",
        f"success_rate={success_rate:.4f}",
        f"success_threshold={success_threshold:.4f}",
        f"point_tolerance_px={point_tolerance_px}",
        f"iou_threshold={iou_threshold:.4f}",
        f"evaluation_failure_count={evaluation.failure_count}",
        f"commercial_ready={str(commercial_ready).lower()}",
    ]
    return contracts.BusinessEvalRecord(
        trial_id=trial_id,
        task=task,
        train_name=train_name,
        cases_root=str(cases_root),
        available_cases=available_cases,
        total_cases=total_cases,
        passed_cases=passed_cases,
        success_rate=success_rate,
        success_threshold=success_threshold,
        min_cases=min_cases,
        sample_size=sample_size,
        commercial_ready=commercial_ready,
        point_tolerance_px=point_tolerance_px,
        iou_threshold=iou_threshold,
        sampled_source=str(sampled_source),
        report_dir=str(report_dir),
        prediction_dir=str(model_result.predict_output_dir),
        evaluation_report_dir=str(evaluation.report_dir),
        case_results=case_results,
        evidence=evidence,
    )


def build_case_results(
    *,
    task: str,
    gold_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    point_tolerance_px: int,
    iou_threshold: float,
) -> list[contracts.BusinessEvalCaseRecord]:
    prediction_by_id = {str(row["sample_id"]): row for row in prediction_rows}
    if task == "group1":
        return _build_group1_case_results(
            gold_rows=gold_rows,
            prediction_by_id=prediction_by_id,
            point_tolerance_px=point_tolerance_px,
        )
    if task == "group2":
        return _build_group2_case_results(
            gold_rows=gold_rows,
            prediction_by_id=prediction_by_id,
            point_tolerance_px=point_tolerance_px,
            iou_threshold=iou_threshold,
        )
    raise ValueError(f"unsupported business eval task: {task}")


def markdown_from_business_eval(record: contracts.BusinessEvalRecord) -> str:
    verdict = "通过" if record.commercial_ready else "未通过"
    lines = [
        f"# {record.trial_id} Business Exam",
        "",
        f"- task: {record.task}",
        f"- train_name: {record.train_name}",
        f"- cases_root: {record.cases_root}",
        f"- available_cases: {record.available_cases}",
        f"- sample_size: {record.sample_size}",
        f"- total_cases: {record.total_cases}",
        f"- passed_cases: {record.passed_cases}",
        f"- success_rate: {record.success_rate:.4f}",
        f"- success_threshold: {record.success_threshold:.4f}",
        f"- point_tolerance_px: {record.point_tolerance_px}",
        f"- iou_threshold: {record.iou_threshold:.4f}",
        f"- sampled_source: {record.sampled_source}",
        f"- prediction_dir: {record.prediction_dir}",
        f"- evaluation_report_dir: {record.evaluation_report_dir}",
        f"- verdict_cn: {verdict}",
        "",
        "## 商业测试结论",
        "",
        _business_test_conclusion_cn(record),
        "",
        "## 判卷规则",
        "",
        _business_rule_cn(record),
        "",
        "## 样本结果",
        "",
    ]
    if not record.case_results:
        lines.append("- 当前 trial 没有写入样本明细。")
    for item in record.case_results:
        lines.extend(_render_case_markdown(item))
    return "\n".join(lines) + "\n"


def log_from_business_eval(record: contracts.BusinessEvalRecord) -> str:
    lines = [
        "# reviewed exam business eval",
        f"trial_id={record.trial_id}",
        f"task={record.task}",
        f"train_name={record.train_name}",
        f"cases_root={record.cases_root}",
        f"available_cases={record.available_cases}",
        f"sample_size={record.sample_size}",
        f"total_cases={record.total_cases}",
        f"passed_cases={record.passed_cases}",
        f"success_rate={record.success_rate:.4f}",
        f"success_threshold={record.success_threshold:.4f}",
        f"point_tolerance_px={record.point_tolerance_px}",
        f"iou_threshold={record.iou_threshold:.4f}",
        f"sampled_source={record.sampled_source}",
        f"prediction_dir={record.prediction_dir}",
        f"evaluation_report_dir={record.evaluation_report_dir}",
        f"commercial_ready={str(record.commercial_ready).lower()}",
        "",
    ]
    for item in record.case_results:
        lines.append(_render_case_line(item, prefix="CASE"))
    return "\n".join(lines) + "\n"


def commercial_report_markdown(
    *,
    study: contracts.StudyRecord,
    leaderboard: contracts.LeaderboardRecord,
    summary_record: contracts.ResultSummaryRecord,
    raw_decision: contracts.DecisionRecord,
    effective_decision: contracts.DecisionRecord,
    business_record: contracts.BusinessEvalRecord,
) -> str:
    best_entry = leaderboard.best_entry
    lines = [
        f"# {study.study_name} 商业可用性结论",
        "",
        "## 最终结论",
        "",
        _final_conclusion_cn(study=study, business_record=business_record),
        "",
        "## 流程状态",
        "",
        f"- study_status: {study.status}",
        f"- final_reason: {study.final_reason}",
        f"- final_detail: {study.final_detail}",
        f"- 流程结论: {_process_conclusion_cn(study=study, business_record=business_record)}",
        "",
        "## 训练过程结论",
        "",
        f"- 当前触发结论的 trial: {summary_record.trial_id}",
        f"- 已完成 trial 数: {len(leaderboard.entries)}",
        f"- best_trial_id: {None if best_entry is None else best_entry.trial_id}",
        f"- best_primary_score: {None if best_entry is None else best_entry.primary_score}",
    ]
    lines.extend(_task_metric_lines(task=business_record.task, best_entry=best_entry))
    lines.extend(
        [
            "",
            "## 晋级结论",
            "",
            f"- 离线晋级判定: {raw_decision.decision}",
            f"- 最终动作判定: {effective_decision.decision}",
            f"- 最终动作原因: {effective_decision.reason}",
            f"- 离线晋级说明: {_offline_promotion_conclusion_cn(raw_decision=raw_decision, business_record=business_record)}",
            "",
            "## 商业测试结论",
            "",
            _business_test_conclusion_cn(business_record),
            "",
            "## 真实业务试卷 Gate",
            "",
            f"- cases_root: {business_record.cases_root}",
            f"- available_cases: {business_record.available_cases}",
            f"- sample_size: {business_record.sample_size}",
            f"- total_cases: {business_record.total_cases}",
            f"- passed_cases: {business_record.passed_cases}",
            f"- success_rate: {business_record.success_rate:.4f}",
            f"- success_threshold: {business_record.success_threshold:.4f}",
            f"- point_tolerance_px: {business_record.point_tolerance_px}",
            f"- iou_threshold: {business_record.iou_threshold:.4f}",
            f"- commercial_ready: {business_record.commercial_ready}",
            "",
            "## 失败样本",
            "",
        ]
    )
    failed_cases = [item for item in business_record.case_results if not item.success]
    if not failed_cases:
        lines.append("- 无")
    for item in failed_cases[:20]:
        lines.append(f"- {_render_case_line(item)}")
    return "\n".join(lines) + "\n"


def _build_business_model_test_request(
    *,
    task: str,
    train_root: Path,
    dataset_version: str,
    train_name: str,
    source: Path,
    report_dir: Path,
    device: str,
    imgsz: int,
) -> ModelTestRequest:
    dataset_config = default_dataset_config(train_root, task, dataset_version)
    if task == "group1":
        return ModelTestRequest(
            task=task,
            dataset_version=dataset_version,
            train_name=train_name,
            dataset_config=dataset_config,
            model_path=_preferred_group1_component_weights(train_root, train_name, SCENE_COMPONENT),
            query_model_path=_preferred_group1_component_weights(train_root, train_name, QUERY_COMPONENT),
            source=source,
            project_dir=report_dir / "modeltest",
            report_dir=report_dir / "modeltest-report",
            predict_name=f"predict_{train_name}_business_exam",
            val_name=f"val_{train_name}_business_exam",
            device=device,
            imgsz=imgsz,
        )
    return ModelTestRequest(
        task=task,
        dataset_version=dataset_version,
        train_name=train_name,
        dataset_config=dataset_config,
        model_path=preferred_run_checkpoint(train_root, "group2", train_name),
        query_model_path=None,
        source=source,
        project_dir=report_dir / "modeltest",
        report_dir=report_dir / "modeltest-report",
        predict_name=f"predict_{train_name}_business_exam",
        val_name=f"val_{train_name}_business_exam",
        device=device,
        imgsz=imgsz,
    )


def _load_prediction_rows(task: str, labels_path: Path) -> list[dict[str, Any]]:
    if not labels_path.exists():
        raise RuntimeError(f"商业测试预测输出缺少 labels.jsonl：{labels_path}")
    rows = read_jsonl(labels_path)
    if task == "group1":
        return [validate_group1_row(row) for row in rows]
    if task == "group2":
        return [validate_group2_row(row) for row in rows]
    raise ValueError(f"unsupported business eval task: {task}")


def _rewrite_row_image_paths(*, task: str, cases_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    rewritten = json.loads(json.dumps(row, ensure_ascii=False))
    if task == "group1":
        rewritten["query_image"] = str(_resolve_case_image(cases_root, Path(str(row["query_image"]))))
        rewritten["scene_image"] = str(_resolve_case_image(cases_root, Path(str(row["scene_image"]))))
        return rewritten
    if task == "group2":
        rewritten["master_image"] = str(_resolve_case_image(cases_root, Path(str(row["master_image"]))))
        rewritten["tile_image"] = str(_resolve_case_image(cases_root, Path(str(row["tile_image"]))))
        return rewritten
    raise ValueError(f"unsupported business eval task: {task}")


def _resolve_case_image(cases_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate
    return (cases_root / candidate).resolve()


def _build_group1_case_results(
    *,
    gold_rows: list[dict[str, Any]],
    prediction_by_id: dict[str, dict[str, Any]],
    point_tolerance_px: int,
) -> list[contracts.BusinessEvalCaseRecord]:
    results: list[contracts.BusinessEvalCaseRecord] = []
    for gold in sorted(gold_rows, key=lambda item: str(item["sample_id"])):
        sample_id = str(gold["sample_id"])
        gold_targets = get_group1_scene_targets(gold)
        prediction = prediction_by_id.get(sample_id)
        if prediction is None:
            results.append(
                contracts.BusinessEvalCaseRecord(
                    case_id=sample_id,
                    sample_id=sample_id,
                    success=False,
                    reason_code="missing_prediction",
                    reason_cn="模型未输出该题结果。",
                    input_images=_group1_input_images(gold),
                    metrics={
                        "target_count": len(gold_targets),
                        "predicted_target_count": 0,
                        "matched_target_count": 0,
                        "point_tolerance_px": point_tolerance_px,
                    },
                    prediction=None,
                    reference={"scene_targets": gold_targets},
                    evidence=["missing_prediction"],
                )
            )
            continue

        predicted_targets = get_group1_scene_targets(prediction)
        matched_target_count = 0
        order_ok = len(gold_targets) == len(predicted_targets)
        sequence_ok = order_ok
        center_errors: list[float] = []
        for index, gold_target in enumerate(gold_targets):
            if index >= len(predicted_targets):
                sequence_ok = False
                continue
            predicted_target = predicted_targets[index]
            if predicted_target.get("order") != gold_target.get("order"):
                order_ok = False
            if predicted_target.get("class_id") != gold_target.get("class_id"):
                sequence_ok = False
                order_ok = False
                continue
            center_error = _distance(gold_target["center"], predicted_target["center"])
            center_errors.append(center_error)
            if center_error <= point_tolerance_px:
                matched_target_count += 1
            else:
                sequence_ok = False
        success = sequence_ok and matched_target_count == len(gold_targets)
        reason_code = "pass" if success else ("order_mismatch" if not order_ok else "sequence_mismatch")
        reason_cn = (
            "点击序列、类别和中心点误差均达标。"
            if success
            else (
                "输出目标顺序或类别与标准答案不一致。"
                if reason_code == "order_mismatch"
                else "输出目标数量、类别或点击中心未全部达标。"
            )
        )
        results.append(
            contracts.BusinessEvalCaseRecord(
                case_id=sample_id,
                sample_id=sample_id,
                success=success,
                reason_code=reason_code,
                reason_cn=reason_cn,
                input_images=_group1_input_images(gold),
                metrics={
                    "target_count": len(gold_targets),
                    "predicted_target_count": len(predicted_targets),
                    "matched_target_count": matched_target_count,
                    "point_tolerance_px": point_tolerance_px,
                    "mean_center_error_px": _rounded_or_none(_mean(center_errors), 4),
                    "order_ok": order_ok,
                },
                prediction={
                    "scene_targets": predicted_targets,
                    "inference_ms": prediction.get("inference_ms"),
                },
                reference={"scene_targets": gold_targets},
                evidence=[f"status={prediction.get('status', 'unknown')}"],
            )
        )
    return results


def _build_group2_case_results(
    *,
    gold_rows: list[dict[str, Any]],
    prediction_by_id: dict[str, dict[str, Any]],
    point_tolerance_px: int,
    iou_threshold: float,
) -> list[contracts.BusinessEvalCaseRecord]:
    results: list[contracts.BusinessEvalCaseRecord] = []
    for gold in sorted(gold_rows, key=lambda item: str(item["sample_id"])):
        sample_id = str(gold["sample_id"])
        gold_target = get_group2_target(gold)
        prediction = prediction_by_id.get(sample_id)
        if prediction is None:
            results.append(
                contracts.BusinessEvalCaseRecord(
                    case_id=sample_id,
                    sample_id=sample_id,
                    success=False,
                    reason_code="missing_prediction",
                    reason_cn="模型未输出该题结果。",
                    input_images=_group2_input_images(gold),
                    metrics={
                        "point_tolerance_px": point_tolerance_px,
                        "iou_threshold": iou_threshold,
                    },
                    prediction=None,
                    reference={"target_gap": gold_target},
                    evidence=["missing_prediction"],
                )
            )
            continue
        predicted_target = get_group2_target(prediction)
        center_error = _distance(gold_target["center"], predicted_target["center"])
        delta_x = float(predicted_target["center"][0]) - float(gold_target["center"][0])
        delta_y = float(predicted_target["center"][1]) - float(gold_target["center"][1])
        iou = _iou(gold_target["bbox"], predicted_target["bbox"])
        x_hit = abs(delta_x) <= point_tolerance_px
        y_hit = abs(delta_y) <= point_tolerance_px
        axis_hit = x_hit and y_hit
        iou_hit = iou >= iou_threshold
        failed_checks: list[str] = []
        if not x_hit:
            failed_checks.append("delta_x")
        if not y_hit:
            failed_checks.append("delta_y")
        if not iou_hit:
            failed_checks.append("iou")
        success = axis_hit and iou_hit
        if success:
            reason_code = "pass"
            reason_cn = "X/Y 方向偏差和 IoU 均达标。"
        elif not axis_hit and not iou_hit:
            reason_code = "axis_miss_and_low_iou"
            reason_cn = "预测中心点在 X/Y 方向上的偏差超出允许像素容差，且预测框与标准答案重合度不足。"
        elif not axis_hit:
            reason_code = "axis_miss"
            reason_cn = "预测中心点在 X/Y 方向上的偏差超出允许像素容差。"
        else:
            reason_code = "low_iou"
            reason_cn = "预测框与标准答案重合度不足。"
        results.append(
            contracts.BusinessEvalCaseRecord(
                case_id=sample_id,
                sample_id=sample_id,
                success=success,
                reason_code=reason_code,
                reason_cn=reason_cn,
                input_images=_group2_input_images(gold),
                metrics={
                    "point_tolerance_px": point_tolerance_px,
                    "iou_threshold": iou_threshold,
                    "center_error_px": round(center_error, 4),
                    "delta_x_px": round(delta_x, 4),
                    "delta_y_px": round(delta_y, 4),
                    "iou": round(iou, 6),
                    "x_hit": x_hit,
                    "y_hit": y_hit,
                    "axis_hit": axis_hit,
                    "iou_hit": iou_hit,
                    "failed_checks": failed_checks,
                    "inference_ms": prediction.get("inference_ms"),
                },
                prediction={"target_gap": predicted_target},
                reference={"target_gap": gold_target},
                evidence=[],
            )
        )
    return results


def _group1_input_images(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_image": str(row["query_image"]),
        "scene_image": str(row["scene_image"]),
    }


def _group2_input_images(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "master_image": str(row["master_image"]),
        "tile_image": str(row["tile_image"]),
    }


def _business_rule_cn(record: contracts.BusinessEvalRecord) -> str:
    if record.task == "group1":
        return (
            f"group1 单题必须整题序列正确，且所有点击目标中心点误差不超过 {record.point_tolerance_px}px。"
        )
    return (
        f"group2 单题必须同时满足 X 方向偏差不超过 {record.point_tolerance_px}px、"
        f"Y 方向偏差不超过 {record.point_tolerance_px}px，"
        f"且 IoU 不低于 {record.iou_threshold:.2f}。"
    )


def _task_metric_lines(*, task: str, best_entry: contracts.LeaderboardEntry | None) -> list[str]:
    metric_keys = (
        ("full_sequence_hit_rate", "full_sequence_hit_rate"),
        ("single_target_hit_rate", "single_target_hit_rate"),
        ("mean_center_error_px", "mean_center_error_px"),
        ("order_error_rate", "order_error_rate"),
    )
    if task == "group2":
        metric_keys = (
            ("point_hit_rate", "point_hit_rate"),
            ("mean_iou", "mean_iou"),
            ("mean_center_error_px", "mean_center_error_px"),
            ("mean_inference_ms", "mean_inference_ms"),
        )
    lines: list[str] = []
    for key, label in metric_keys:
        lines.append(f"- {label}: {_leaderboard_metric(best_entry, key)}")
    return lines


def _leaderboard_metric(entry: contracts.LeaderboardEntry | None, key: str) -> str:
    if entry is None:
        return "None"
    value = entry.metrics.get(key)
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render_case_line(item: contracts.BusinessEvalCaseRecord, prefix: str | None = None) -> str:
    line = (
        f"case_id={item.case_id} sample_id={item.sample_id} "
        f"status={'PASS' if item.success else 'FAIL'} reason_code={item.reason_code} "
        f"metrics={_render_mapping(item.metrics)} "
        f"input_images={_render_mapping(item.input_images)}"
    )
    if item.artifacts is not None:
        line += f" artifacts={_render_mapping(item.artifacts)}"
    if item.prediction is not None:
        line += f" prediction={_render_mapping(item.prediction)}"
    if item.reference is not None:
        line += f" reference={_render_mapping(item.reference)}"
    if item.evidence:
        line += f" evidence={json.dumps(item.evidence, ensure_ascii=False)}"
    line += f" reason_cn={item.reason_cn}"
    summary_cn = _case_summary_cn(item)
    if summary_cn:
        line += f" summary_cn={json.dumps(summary_cn, ensure_ascii=False)}"
    if prefix is None:
        return line
    return f"{prefix} {line}"


def _render_case_markdown(item: contracts.BusinessEvalCaseRecord) -> list[str]:
    lines = [
        f"### {item.case_id}",
        "",
        f"- 样本编号：{item.sample_id}",
        f"- 判定结果：{'通过' if item.success else '未通过'}",
        f"- 失败代码：{item.reason_code}",
        f"- 结论说明：{item.reason_cn}",
    ]
    lines.extend(_case_input_lines(item))
    lines.extend(_case_reference_lines(item))
    lines.extend(_case_prediction_lines(item))
    lines.extend(_case_metric_lines(item))
    lines.extend(_case_artifact_lines(item))
    if item.evidence:
        lines.append(f"- 辅助证据：{json.dumps(item.evidence, ensure_ascii=False)}")
    lines.append("")
    return lines


def _render_mapping(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _preferred_group1_component_weights(train_root: Path, train_name: str, component: str) -> Path:
    best = group1_component_best_weights(train_root, train_name, component)
    last = group1_component_last_weights(train_root, train_name, component)
    return preferred_checkpoint_path(best, last)


def _process_conclusion_cn(*, study: contracts.StudyRecord, business_record: contracts.BusinessEvalRecord) -> str:
    if study.status == "completed" and business_record.commercial_ready:
        return "自动训练流程正常完成，且最终商业测试达标。"
    if study.status == "stopped":
        return f"自动训练流程正常结束，但属于预算/停止规则触发的停止；原因是 {_final_reason_cn(study.final_reason, study.final_detail)}。"
    return "自动训练流程仍处于运行中。"


def _final_conclusion_cn(*, study: contracts.StudyRecord, business_record: contracts.BusinessEvalRecord) -> str:
    if business_record.commercial_ready:
        return "达到商用门。本次最佳候选已经通过 reviewed 试卷集商业测试，可以结束自动训练并进入交付/复核阶段。"
    if study.status == "stopped":
        return "未达到商用门。本次自动训练因为停止规则触发而结束，不是因为商业测试通过。"
    return "未达到商用门。当前应继续迭代训练并优先修复商业测试失败样本。"


def _offline_promotion_conclusion_cn(
    *,
    raw_decision: contracts.DecisionRecord,
    business_record: contracts.BusinessEvalRecord,
) -> str:
    if raw_decision.decision == "PROMOTE_BRANCH":
        if business_record.commercial_ready:
            return "离线指标已达到候选晋级区间，且 reviewed 试卷集商业测试通过。"
        return "离线指标已达到候选晋级区间，但 reviewed 试卷集商业测试未通过，因此不能认定为最终商用成功。"
    return f"离线指标未进入候选晋级区间，judge 返回 {raw_decision.decision}。"


def _business_test_conclusion_cn(record: contracts.BusinessEvalRecord) -> str:
    return (
        f"- 本轮试卷池共有 {record.available_cases} 组 reviewed 试题。\n"
        f"- 本轮计划抽取 {record.sample_size} 组进行商业测试，实际完成判卷 {record.total_cases} 组。\n"
        f"- 其中通过 {record.passed_cases} 组，通过率为 {record.success_rate:.2%}。\n"
        f"- 当前商用门要求 success_rate >= {record.success_threshold:.0%}。\n"
        f"- {_business_rule_cn(record)}"
    )


def _attach_group2_failure_artifacts(
    *,
    case_results: list[contracts.BusinessEvalCaseRecord],
    report_dir: Path,
) -> list[contracts.BusinessEvalCaseRecord]:
    artifact_dir = report_dir / "failure_overlays"
    rewritten: list[contracts.BusinessEvalCaseRecord] = []
    for item in case_results:
        if item.success or item.prediction is None:
            rewritten.append(item)
            continue
        try:
            overlay_path = _write_group2_failure_overlay(item=item, output_dir=artifact_dir)
        except Exception as exc:
            evidence = list(item.evidence or [])
            evidence.append(f"failure_overlay_error={exc}")
            rewritten.append(replace(item, evidence=evidence))
            continue
        artifacts = dict(item.artifacts or {})
        artifacts["predicted_overlay_image"] = str(overlay_path)
        rewritten.append(replace(item, artifacts=artifacts))
    return rewritten


def _case_input_lines(item: contracts.BusinessEvalCaseRecord) -> list[str]:
    if not item.input_images:
        return []
    if "master_image" in item.input_images:
        return [
            f"- 输入背景图：{item.input_images.get('master_image')}",
            f"- 输入缺口图：{item.input_images.get('tile_image')}",
        ]
    if "query_image" in item.input_images:
        return [
            f"- 输入查询图：{item.input_images.get('query_image')}",
            f"- 输入场景图：{item.input_images.get('scene_image')}",
        ]
    return [f"- 输入图片：{_render_mapping(item.input_images)}"]


def _case_reference_lines(item: contracts.BusinessEvalCaseRecord) -> list[str]:
    if item.reference is None:
        return []
    target_gap = item.reference.get("target_gap")
    if isinstance(target_gap, dict):
        return [
            f"- 标准答案框：{target_gap.get('bbox')}",
            f"- 标准答案中心点：{target_gap.get('center')}",
        ]
    scene_targets = item.reference.get("scene_targets")
    if isinstance(scene_targets, list):
        return [f"- 标准答案目标序列：{json.dumps(scene_targets, ensure_ascii=False)}"]
    return [f"- 标准答案：{_render_mapping(item.reference)}"]


def _case_prediction_lines(item: contracts.BusinessEvalCaseRecord) -> list[str]:
    if item.prediction is None:
        return ["- 模型输出：未输出该题结果"]
    target_gap = item.prediction.get("target_gap")
    if isinstance(target_gap, dict):
        return [
            f"- 模型预测框：{target_gap.get('bbox')}",
            f"- 模型预测中心点：{target_gap.get('center')}",
        ]
    scene_targets = item.prediction.get("scene_targets")
    if isinstance(scene_targets, list):
        return [f"- 模型预测目标序列：{json.dumps(scene_targets, ensure_ascii=False)}"]
    return [f"- 模型输出：{_render_mapping(item.prediction)}"]


def _case_artifact_lines(item: contracts.BusinessEvalCaseRecord) -> list[str]:
    if not item.artifacts:
        return []
    lines: list[str] = []
    for key, value in sorted(item.artifacts.items()):
        label = "失败证据图" if key == "predicted_overlay_image" else key
        lines.append(f"- {label}：{value}")
    return lines


def _case_metric_lines(item: contracts.BusinessEvalCaseRecord) -> list[str]:
    if item.reference is None or item.prediction is None:
        return [f"- 指标明细：{_render_mapping(item.metrics)}"]
    if "target_gap" in item.reference and "target_gap" in item.prediction:
        metrics = item.metrics
        failed_checks = metrics.get("failed_checks")
        failed_checks_cn = _failed_checks_cn(failed_checks if isinstance(failed_checks, list) else [])
        return [
            f"- 中心点总误差：{metrics.get('center_error_px')}px，仅作参考展示",
            f"- X 方向偏差：{_delta_axis_cn(metrics.get('delta_x_px'), 'x')}",
            f"- Y 方向偏差：{_delta_axis_cn(metrics.get('delta_y_px'), 'y')}",
            f"- X 方向是否达标：{'是' if metrics.get('x_hit') else '否'}，阈值 {metrics.get('point_tolerance_px')}px",
            f"- Y 方向是否达标：{'是' if metrics.get('y_hit') else '否'}，阈值 {metrics.get('point_tolerance_px')}px",
            f"- IoU 重合度：{metrics.get('iou')}，要求不低于 {metrics.get('iou_threshold')}",
            f"- 未通过项：{failed_checks_cn}",
        ]
    return [f"- 指标明细：{_render_mapping(item.metrics)}"]


def _case_summary_cn(item: contracts.BusinessEvalCaseRecord) -> str | None:
    if item.reference is None or item.prediction is None:
        return None
    if "target_gap" in item.reference and "target_gap" in item.prediction:
        metrics = item.metrics
        return (
            f"该题标准答案中心点为 {item.reference['target_gap'].get('center')}，"
            f"模型预测中心点为 {item.prediction['target_gap'].get('center')}；"
            f"中心点总误差 {metrics.get('center_error_px')}px（仅作参考），"
            f"X 方向偏差 {metrics.get('delta_x_px')}px，"
            f"Y 方向偏差 {metrics.get('delta_y_px')}px，"
            f"IoU 为 {metrics.get('iou')}，"
            f"最终判定为{'通过' if item.success else '未通过'}。"
        )
    return None


def _write_group2_failure_overlay(
    *,
    item: contracts.BusinessEvalCaseRecord,
    output_dir: Path,
) -> Path:
    from PIL import Image

    master_image = item.input_images.get("master_image")
    tile_image = item.input_images.get("tile_image")
    if not isinstance(master_image, str) or not master_image.strip():
        raise ValueError("missing master_image")
    if not isinstance(tile_image, str) or not tile_image.strip():
        raise ValueError("missing tile_image")
    if item.prediction is None:
        raise ValueError("missing prediction")
    target_gap = item.prediction.get("target_gap")
    bbox = _target_gap_bbox(target_gap)
    x1, y1, x2, y2 = bbox
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{item.case_id}.png"

    with Image.open(master_image) as master_src, Image.open(tile_image) as tile_src:
        master = master_src.convert("RGBA")
        tile = tile_src.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", master.size, (0, 0, 0, 0))
        canvas.paste(tile, (x1, y1), tile)
        blended = Image.alpha_composite(master, canvas)
        blended.save(output_path, format="PNG")
    return output_path


def _target_gap_bbox(target_gap: Any) -> tuple[int, int, int, int]:
    if not isinstance(target_gap, dict):
        raise ValueError("prediction target_gap must be an object")
    bbox = target_gap.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("prediction target_gap bbox must contain four numbers")
    try:
        x1, y1, x2, y2 = [int(round(float(value))) for value in bbox]
    except (TypeError, ValueError) as exc:
        raise ValueError("prediction target_gap bbox must contain numeric values") from exc
    return x1, y1, x2, y2


def _delta_axis_cn(value: Any, axis: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if axis == "x":
        if number > 0:
            return f"向右偏 {abs(number):.4f}px"
        if number < 0:
            return f"向左偏 {abs(number):.4f}px"
        return "无偏移"
    if number > 0:
        return f"向下偏 {abs(number):.4f}px"
    if number < 0:
        return f"向上偏 {abs(number):.4f}px"
    return "无偏移"


def _failed_checks_cn(items: list[Any]) -> str:
    if not items:
        return "无，全部达标"
    labels: list[str] = []
    for item in items:
        if item == "delta_x":
            labels.append("X 方向偏差")
        elif item == "delta_y":
            labels.append("Y 方向偏差")
        elif item == "iou":
            labels.append("IoU")
        else:
            labels.append(str(item))
    return "、".join(labels)


def _final_reason_cn(reason: str | None, detail: str | None) -> str:
    if reason == "commercial_gate_passed":
        return "真实业务试卷 gate 已通过"
    if reason == "offline_promotion_ready":
        return "离线晋级门已通过"
    if reason == "abandon_branch":
        return "当前分支被判定为应停止投入"
    if reason == "max_trials_reached":
        return f"达到最大训练轮次上限（{detail}）" if detail else "达到最大训练轮次上限"
    if reason == "max_hours_reached":
        return f"达到最大训练时长上限（{detail}）" if detail else "达到最大训练时长上限"
    if reason == "max_new_datasets_reached":
        return f"达到最大新数据版本上限（{detail}）" if detail else "达到最大新数据版本上限"
    if reason == "no_improve_limit_reached":
        return f"达到连续无提升轮次上限（{detail}）" if detail else "达到连续无提升轮次上限"
    if reason == "plateau_detected":
        return "近期指标进入平台期"
    if reason == "fatal_failure":
        return detail or "发生致命错误"
    if reason == "stop_file_detected":
        return "检测到人工 STOP 文件"
    if reason and detail:
        return f"{reason}（{detail}）"
    if reason:
        return reason
    return "未记录最终原因"


def _distance(a: list[int], b: list[int]) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def _iou(box_a: list[int], box_b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = [float(value) for value in box_a]
    bx1, by1, bx2, by2 = [float(value) for value in box_b]
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0.0:
        return 0.0
    return inter_area / union


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / float(len(values))


def _rounded_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)
