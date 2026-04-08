"""Business-sample evaluation helpers for autonomous training."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import random
import time
from typing import Iterable

from core.auto_train import contracts
from core.solve import group2_runtime
from core.train.base import default_best_weights

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
_MASTER_IMAGE_STEMS = ("master", "bg", "background")
_TILE_IMAGE_STEMS = ("tile", "gap", "piece", "puzzle_piece")
_BBOX_EDGE_TOLERANCE_PX = 5.0
_LOCAL_SEARCH_RADIUS_PX = 8


@dataclass(frozen=True)
class OcclusionScore:
    boundary_before: float
    boundary_after: float
    fill_score: float
    seam_score: float
    occlusion_score: float
    success: bool
    best_local_bbox: list[int]
    best_local_offset_px: float
    best_local_clean_score: float
    tile_residue_ratio: float
    double_edge_score: float
    overflow_edge_score: float


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    master_path: Path
    tile_path: Path


@dataclass(frozen=True)
class OverlayArtifactMetrics:
    tile_residue_ratio: float
    double_edge_score: float
    overflow_edge_score: float
    artifact_score: float
    clean_score: float


def score_occlusion_overlay(
    *,
    master_luma: list[list[float]],
    tile_luma: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
    success_threshold: float = 0.78,
) -> OcclusionScore:
    """Score whether overlaying the tile at ``(x, y)`` looks locally well-fitted."""

    _validate_grids(master_luma=master_luma, tile_luma=tile_luma, tile_alpha=tile_alpha)
    predicted_metrics = _overlay_artifact_metrics(
        master_luma=master_luma,
        tile_luma=tile_luma,
        tile_alpha=tile_alpha,
        x=x,
        y=y,
    )
    best_local_bbox, best_local_metrics = _best_local_bbox(
        master_luma=master_luma,
        tile_luma=tile_luma,
        tile_alpha=tile_alpha,
        x=x,
        y=y,
    )
    best_local_offset_px = _bbox_edge_error([x, y, x + len(tile_alpha[0]), y + len(tile_alpha)], best_local_bbox)
    success = (
        best_local_offset_px <= _BBOX_EDGE_TOLERANCE_PX
        and best_local_metrics.clean_score >= success_threshold
    )
    edge_clean_score = _clamp01(1.0 - max(predicted_metrics.double_edge_score, predicted_metrics.overflow_edge_score))
    return OcclusionScore(
        boundary_before=predicted_metrics.double_edge_score,
        boundary_after=predicted_metrics.overflow_edge_score,
        fill_score=_clamp01(1.0 - predicted_metrics.tile_residue_ratio),
        seam_score=edge_clean_score,
        occlusion_score=predicted_metrics.clean_score,
        success=success,
        best_local_bbox=best_local_bbox,
        best_local_offset_px=best_local_offset_px,
        best_local_clean_score=best_local_metrics.clean_score,
        tile_residue_ratio=predicted_metrics.tile_residue_ratio,
        double_edge_score=predicted_metrics.double_edge_score,
        overflow_edge_score=predicted_metrics.overflow_edge_score,
    )


def discover_group2_cases(cases_root: Path) -> list[CaseSpec]:
    master = _find_first_image(cases_root, stems=_MASTER_IMAGE_STEMS)
    tile = _find_first_image(cases_root, stems=_TILE_IMAGE_STEMS)
    if master is not None and tile is not None:
        return [CaseSpec(case_id=cases_root.name or "case_0001", master_path=master, tile_path=tile)]

    cases: list[CaseSpec] = []
    for candidate in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        master = _find_first_image(candidate, stems=_MASTER_IMAGE_STEMS)
        tile = _find_first_image(candidate, stems=_TILE_IMAGE_STEMS)
        if master is None or tile is None:
            continue
        cases.append(CaseSpec(case_id=candidate.name, master_path=master, tile_path=tile))
    return cases


def run_group2_business_eval(
    *,
    trial_id: str,
    train_root: Path,
    train_name: str,
    cases_root: Path,
    report_dir: Path,
    device: str,
    success_threshold: float,
    min_cases: int,
    sample_size: int,
    occlusion_threshold: float,
) -> contracts.BusinessEvalRecord:
    try:
        from PIL import Image, ImageChops
    except Exception as exc:  # pragma: no cover - host env dependent
        raise RuntimeError("当前环境缺少 `Pillow`，无法执行真实样本 business eval。") from exc

    discovered_cases = discover_group2_cases(cases_root)
    if not discovered_cases:
        raise RuntimeError(
            "未在 business_eval 样本目录中找到背景图/缺口块图片。"
            f"当前支持 `master.* + tile.*` 或 `bg.* + gap.*`：{cases_root}"
        )
    cases = select_case_sample(
        discovered_cases,
        sample_size=sample_size,
        sample_key=f"{trial_id}:{train_name}:{cases_root}",
    )

    weights_path = default_best_weights(train_root, "group2", train_name)
    model, imgsz, torch_device = group2_runtime.load_model(weights_path, device)
    case_results: list[contracts.BusinessEvalCaseRecord] = []

    for case in cases:
        master_tensor, tile_tensor, meta = group2_runtime.prepare_inputs(
            master_path=case.master_path,
            tile_path=case.tile_path,
            imgsz=imgsz,
        )
        started = time.perf_counter()
        with group2_runtime.torch_no_grad():
            response = model(master_tensor.to(torch_device), tile_tensor.to(torch_device))[0]
        inference_ms = (time.perf_counter() - started) * 1000.0
        bbox = group2_runtime.decode_bbox(response, meta)
        center = group2_runtime.bbox_center(bbox)

        master_rgba = Image.open(case.master_path).convert("RGBA")
        tile_rgba = group2_runtime.normalize_tile_rgba_image(Image.open(case.tile_path))
        score = score_occlusion_overlay(
            master_luma=_image_to_luma_grid(master_rgba.convert("L")),
            tile_luma=_image_to_luma_grid(tile_rgba.convert("L")),
            tile_alpha=_image_to_alpha_grid(tile_rgba),
            x=bbox[0],
            y=bbox[1],
            success_threshold=occlusion_threshold,
        )

        case_dir = report_dir / case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = case_dir / "overlay.png"
        diff_path = case_dir / "diff.png"
        overlay = master_rgba.copy()
        overlay.paste(tile_rgba, (bbox[0], bbox[1]), tile_rgba)
        overlay.save(overlay_path)
        ImageChops.difference(master_rgba, overlay).save(diff_path)

        case_results.append(
            contracts.BusinessEvalCaseRecord(
                case_id=case.case_id,
                master_image=str(case.master_path),
                tile_image=str(case.tile_path),
                predicted_bbox=bbox,
                predicted_center=center,
                inference_ms=round(inference_ms, 4),
                boundary_before=round(score.boundary_before, 6),
                boundary_after=round(score.boundary_after, 6),
                fill_score=round(score.fill_score, 6),
                seam_score=round(score.seam_score, 6),
                occlusion_score=round(score.occlusion_score, 6),
                success=score.success,
                reason_cn=_reason_cn(score),
                overlay_path=str(overlay_path),
                diff_path=str(diff_path),
                best_local_bbox=score.best_local_bbox,
                best_local_offset_px=round(score.best_local_offset_px, 4),
                best_local_clean_score=round(score.best_local_clean_score, 6),
                tile_residue_ratio=round(score.tile_residue_ratio, 6),
                double_edge_score=round(score.double_edge_score, 6),
                overflow_edge_score=round(score.overflow_edge_score, 6),
            )
        )

    passed_cases = sum(1 for item in case_results if item.success)
    total_cases = len(case_results)
    success_rate = 0.0 if total_cases == 0 else passed_cases / float(total_cases)
    commercial_ready = total_cases >= min_cases and success_rate >= success_threshold
    evidence = [
        f"available_cases={len(discovered_cases)}",
        f"sample_size={sample_size}",
        f"total_cases={total_cases}",
        f"passed_cases={passed_cases}",
        f"success_rate={success_rate:.4f}",
        f"success_threshold={success_threshold:.4f}",
        f"occlusion_threshold={occlusion_threshold:.4f}",
        f"commercial_ready={str(commercial_ready).lower()}",
    ]
    return contracts.BusinessEvalRecord(
        trial_id=trial_id,
        task="group2",
        train_name=train_name,
        cases_root=str(cases_root),
        available_cases=len(discovered_cases),
        total_cases=total_cases,
        passed_cases=passed_cases,
        success_rate=success_rate,
        success_threshold=success_threshold,
        min_cases=min_cases,
        sample_size=sample_size,
        commercial_ready=commercial_ready,
        occlusion_threshold=occlusion_threshold,
        report_dir=str(report_dir),
        case_results=case_results,
        evidence=evidence,
    )


def select_case_sample(
    cases: list[CaseSpec],
    *,
    sample_size: int,
    sample_key: str,
) -> list[CaseSpec]:
    if sample_size <= 0:
        raise ValueError("sample_size must be greater than 0")
    if len(cases) <= sample_size:
        return sorted(cases, key=lambda item: item.case_id)
    shuffled = list(cases)
    random.Random(sample_key).shuffle(shuffled)
    return sorted(shuffled[:sample_size], key=lambda item: item.case_id)


def markdown_from_business_eval(record: contracts.BusinessEvalRecord) -> str:
    verdict = "通过" if record.commercial_ready else "未通过"
    lines = [
        f"# {record.trial_id} Business Eval",
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
        f"- main_score_threshold: {record.occlusion_threshold:.4f}",
        f"- verdict_cn: {verdict}",
        "",
        "## 字段说明",
        "",
        "- available_cases: business_eval 目录下发现的全部候选样本数。",
        "- sample_size: 本轮配置允许抽样的最大样本数。",
        "- total_cases: 本轮实际参与商业测试的样本数。",
        "- passed_cases: 单样本 overlay 痕迹检测与局部 5px 容差同时达标的通过数。",
        "- success_rate: passed_cases / total_cases，表示本轮商业测试通过率。",
        "- success_threshold: 判定达到商用门所需的最小通过率。",
        "- main_score_threshold: 单样本最佳局部 clean_score 的最低通过阈值。",
        "- predicted_bbox: 求解模块输出的缺口框坐标，格式为 [x1, y1, x2, y2]。",
        "- predicted_center: 求解模块输出的缺口中心点，格式为 [cx, cy]。",
        "- best_local_bbox: 在模型输出位置附近小范围搜索后，痕迹最干净的候选框。",
        "- best_local_offset_px: predicted_bbox 与 best_local_bbox 四条边偏差的最大值；<= 5px 视为定位正常。",
        "- best_local_clean_score: 邻域内最优贴合位置的 clean_score，越高越好。",
        "- inference_ms: 求解模块本次推理耗时，单位毫秒。",
        "- tile_residue_ratio: overlay 中仍然保留大面积图块痕迹的程度，越低越好。",
        "- double_edge_score: overlay 中出现明显双边缘/重影的程度，越低越好。",
        "- overflow_edge_score: overlay 中出现越界边缘的程度，越低越好。",
        "- clean_score(occlusion): 兼容旧字段 occlusion_score，表示当前模型输出位置的整体干净程度，越高越好。",
        "",
        "## 样本结果",
        "",
    ]
    if not record.case_results:
        lines.append("- 当前 trial 没有写入样本明细。")
    for item in record.case_results:
        status = "PASS" if item.success else "FAIL"
        lines.append(
            f"- {item.case_id}: {status}, predicted_bbox={item.predicted_bbox}, "
            f"predicted_center={item.predicted_center}, best_local_bbox={item.best_local_bbox}, "
            f"best_local_offset_px={_format_optional_float(item.best_local_offset_px)}, "
            f"best_local_clean_score={_format_optional_float(item.best_local_clean_score)}, "
            f"inference_ms={item.inference_ms:.4f}, clean_score={item.occlusion_score:.4f}, "
            f"tile_residue_ratio={_format_optional_float(item.tile_residue_ratio)}, "
            f"double_edge_score={_format_optional_float(item.double_edge_score)}, "
            f"overflow_edge_score={_format_optional_float(item.overflow_edge_score)}, "
            f"reason_cn={item.reason_cn}"
        )
    return "\n".join(lines) + "\n"


def log_from_business_eval(record: contracts.BusinessEvalRecord) -> str:
    lines = [
        "# 字段说明",
        "# predicted_bbox: 模型输出的背景图坐标框 [x1, y1, x2, y2]。",
        "# predicted_center: 模型输出的缺口中心点 [cx, cy]。",
        "# best_local_bbox: 在模型输出位置附近做局部搜索后，痕迹最干净的候选框。",
        "# best_local_offset_px: predicted_bbox 与 best_local_bbox 四条边偏差的最大值，<= 5px 视为定位正常。",
        "# best_local_clean_score: 邻域内最优贴合位置的 clean_score，越高越好。",
        "# inference_ms: 求解模块单次推理耗时，单位毫秒。",
        "# tile_residue_ratio: overlay 中仍保留明显图块痕迹的程度，越低越好。",
        "# double_edge_score: overlay 中出现双边缘/重影的程度，越低越好。",
        "# overflow_edge_score: overlay 中出现越界边缘的程度，越低越好。",
        "# clean_score(occlusion): 当前模型输出位置的整体干净程度，越高越好。",
        "# success_rate: 当前批次通过率，即 passed_cases / total_cases。",
        "# commercial_ready: 当前批次是否达到最终商用门。",
        "",
        f"trial_id={record.trial_id}",
        f"train_name={record.train_name}",
        f"cases_root={record.cases_root}",
        f"available_cases={record.available_cases}",
        f"sample_size={record.sample_size}",
        f"total_cases={record.total_cases}",
        f"passed_cases={record.passed_cases}",
        f"success_rate={record.success_rate:.4f}",
        f"success_threshold={record.success_threshold:.4f}",
        f"main_score_threshold={record.occlusion_threshold:.4f}",
        f"commercial_ready={str(record.commercial_ready).lower()}",
        "",
    ]
    for item in record.case_results:
        status = "PASS" if item.success else "FAIL"
        lines.append(
            f"{status} case_id={item.case_id} predicted_bbox={item.predicted_bbox} "
            f"predicted_center={item.predicted_center} best_local_bbox={item.best_local_bbox} "
            f"best_local_offset_px={_format_optional_float(item.best_local_offset_px)} "
            f"best_local_clean_score={_format_optional_float(item.best_local_clean_score)} "
            f"inference_ms={item.inference_ms:.4f} clean_score={item.occlusion_score:.4f} "
            f"tile_residue_ratio={_format_optional_float(item.tile_residue_ratio)} "
            f"double_edge_score={_format_optional_float(item.double_edge_score)} "
            f"overflow_edge_score={_format_optional_float(item.overflow_edge_score)} "
            f"reason_cn={item.reason_cn}"
        )
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
    process_conclusion = _process_conclusion_cn(study=study, business_record=business_record)
    final_conclusion = _final_conclusion_cn(study=study, business_record=business_record)
    offline_promotion = _offline_promotion_conclusion_cn(raw_decision=raw_decision, business_record=business_record)
    business_test_conclusion = _business_test_conclusion_cn(business_record)
    lines = [
        f"# {study.study_name} 商业可用性结论",
        "",
        "## 最终结论",
        "",
        final_conclusion,
        "",
        "## 流程状态",
        "",
        f"- study_status: {study.status}",
        f"- final_reason: {study.final_reason}",
        f"- final_detail: {study.final_detail}",
        f"- 流程结论: {process_conclusion}",
        "",
        "## 训练过程结论",
        "",
        f"- 当前触发结论的 trial: {summary_record.trial_id}",
        f"- 已完成 trial 数: {len(leaderboard.entries)}",
        f"- best_trial_id: {None if best_entry is None else best_entry.trial_id}",
        f"- best_primary_score: {None if best_entry is None else best_entry.primary_score}",
        f"- best_dataset_version: {None if best_entry is None else best_entry.dataset_version}",
        f"- point_hit_rate: {_metric_value(best_entry, 'point_hit_rate')}",
        f"- mean_iou: {_metric_value(best_entry, 'mean_iou')}",
        f"- mean_center_error_px: {_metric_value(best_entry, 'mean_center_error_px')}",
        f"- mean_inference_ms: {_metric_value(best_entry, 'mean_inference_ms')}",
        "- point_hit_rate: 预测中心点落入容差范围的比例，越高越好。",
        "- mean_iou: 预测框与目标框重叠程度的均值，越高越好。",
        "- mean_center_error_px: 预测中心与真实中心的平均像素误差，越低越好。",
        "- mean_inference_ms: 单次推理平均耗时，越低越好。",
        "",
        "## 晋级结论",
        "",
        f"- 离线晋级判定: {raw_decision.decision}",
        f"- 离线晋级说明: {offline_promotion}",
        f"- 最终动作判定: {effective_decision.decision}",
        f"- 最终动作原因: {effective_decision.reason}",
        "- group2 离线晋级门: point_hit_rate >= 0.93、mean_iou >= 0.85、mean_center_error_px <= 8.0。",
        "",
        "## 商业测试结论",
        "",
        business_test_conclusion,
        "",
        "## 真实业务样本 Gate",
        "",
        f"- cases_root: {business_record.cases_root}",
        f"- available_cases: {business_record.available_cases}",
        f"- sample_size: {business_record.sample_size}",
        f"- total_cases: {business_record.total_cases}",
        f"- passed_cases: {business_record.passed_cases}",
        f"- success_rate: {business_record.success_rate:.4f}",
        f"- success_threshold: {business_record.success_threshold:.4f}",
        f"- main_score_threshold: {business_record.occlusion_threshold:.4f}",
        f"- commercial_ready: {business_record.commercial_ready}",
        "",
        "## 商业测试字段说明",
        "",
        "- predicted_bbox / predicted_center / inference_ms: 直接来自 group2 求解模块的推理输出。",
        "- best_local_bbox: 在模型输出位置附近做局部搜索后，痕迹最干净的候选框。",
        "- best_local_offset_px: predicted_bbox 与 best_local_bbox 四条边偏差的最大值；当前 <= 5px 视为定位正常。",
        "- best_local_clean_score: 邻域内最优贴合位置的 clean_score，越高越好。",
        "- tile_residue_ratio: overlay 中仍然保留大面积图块痕迹的程度，越低越好。",
        "- double_edge_score: overlay 中出现双边缘/重影的程度，越低越好。",
        "- overflow_edge_score: overlay 中出现越界边缘的程度，越低越好。",
        "- fill_score: 兼容旧字段名；现表示 tile_clean_score，即 1 - tile_residue_ratio。",
        "- seam_score: 兼容旧字段名；现表示 edge_clean_score，即 1 - max(double_edge_score, overflow_edge_score)。",
        "- occlusion_score: 兼容旧字段名；现表示当前模型输出位置的 clean_score，越高越好。",
        "- boundary_before / boundary_after: 兼容旧辅诊断字段；现分别记录 double_edge_score 与 overflow_edge_score。",
        "- success_rate: 本轮商业测试通过率，即 passed_cases / total_cases。",
        "- commercial_ready: success_rate 是否达到 success_threshold，且样本数满足 min_cases。",
        "",
        "## 失败样本",
        "",
    ]
    failed_cases = [item for item in business_record.case_results if not item.success]
    if not failed_cases:
        lines.append("- 无")
    for item in failed_cases[:20]:
        lines.append(
            f"- {item.case_id}: predicted_bbox={item.predicted_bbox}, "
            f"predicted_center={item.predicted_center}, best_local_bbox={item.best_local_bbox}, "
            f"best_local_offset_px={_format_optional_float(item.best_local_offset_px)}, "
            f"best_local_clean_score={_format_optional_float(item.best_local_clean_score)}, "
            f"clean_score={item.occlusion_score:.4f}, tile_residue_ratio={_format_optional_float(item.tile_residue_ratio)}, "
            f"double_edge_score={_format_optional_float(item.double_edge_score)}, "
            f"overflow_edge_score={_format_optional_float(item.overflow_edge_score)}, reason_cn={item.reason_cn}"
        )
    return "\n".join(lines) + "\n"


def _metric_value(entry: contracts.LeaderboardEntry | None, key: str) -> str:
    if entry is None:
        return "None"
    value = entry.metrics.get(key)
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _process_conclusion_cn(*, study: contracts.StudyRecord, business_record: contracts.BusinessEvalRecord) -> str:
    if study.status == "completed" and business_record.commercial_ready:
        return "自动训练流程正常完成，且最终商业测试达标。"
    if study.status == "stopped":
        return f"自动训练流程正常结束，但属于预算/停止规则触发的停止；原因是 {_final_reason_cn(study.final_reason, study.final_detail)}。"
    return "自动训练流程仍处于运行中。"


def _final_conclusion_cn(*, study: contracts.StudyRecord, business_record: contracts.BusinessEvalRecord) -> str:
    if business_record.commercial_ready:
        return "达到商用门。本次最佳候选已经通过真实业务样本 gate，可以结束自动训练并进入交付/复核阶段。"
    if study.status == "stopped":
        return (
            "未达到商用门。本次自动训练虽然正常执行完毕，但最终因为停止规则触发而结束，"
            "不是因为商业测试通过。"
        )
    return "未达到商用门。当前应继续迭代训练并优先修复商业测试失败样本。"


def _offline_promotion_conclusion_cn(
    *,
    raw_decision: contracts.DecisionRecord,
    business_record: contracts.BusinessEvalRecord,
) -> str:
    if raw_decision.decision == "PROMOTE_BRANCH":
        if business_record.commercial_ready:
            return "离线指标已达到候选晋级区间，且商业测试通过。"
        return "离线指标已达到候选晋级区间，但商业测试未通过，因此不能认定为最终商用成功。"
    return f"离线指标未进入候选晋级区间，judge 返回 {raw_decision.decision}。"


def _business_test_conclusion_cn(record: contracts.BusinessEvalRecord) -> str:
    return (
        f"- 本轮从 {record.available_cases} 组真实样本中抽取 {record.total_cases} 组进行商业测试。\n"
        f"- 其中通过 {record.passed_cases} 组，通过率为 {record.success_rate:.2%}。\n"
        f"- 当前商用门要求 success_rate >= {record.success_threshold:.0%}，"
        f"单样本还需满足局部最优 clean_score >= {record.occlusion_threshold:.2f}，"
        f"且模型输出位置与附近最干净贴合位置的边框偏差 <= 5px。"
    )


def _final_reason_cn(reason: str | None, detail: str | None) -> str:
    if reason == "commercial_gate_passed":
        return "真实业务样本 gate 已通过"
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


def _validate_grids(
    *,
    master_luma: list[list[float]],
    tile_luma: list[list[float]],
    tile_alpha: list[list[float]],
) -> None:
    if not master_luma or not master_luma[0]:
        raise ValueError("master_luma must not be empty")
    if not tile_luma or not tile_luma[0]:
        raise ValueError("tile_luma must not be empty")
    if len(tile_luma) != len(tile_alpha) or len(tile_luma[0]) != len(tile_alpha[0]):
        raise ValueError("tile_luma and tile_alpha shapes must match")


def _boundary_diffs(
    *,
    image: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
) -> list[float]:
    diffs: list[float] = []
    height = len(image)
    width = len(image[0])
    tile_height = len(tile_alpha)
    tile_width = len(tile_alpha[0])
    for tile_y in range(tile_height):
        for tile_x in range(tile_width):
            if tile_alpha[tile_y][tile_x] <= 0.0:
                continue
            inside_x = x + tile_x
            inside_y = y + tile_y
            if inside_x < 0 or inside_x >= width or inside_y < 0 or inside_y >= height:
                continue
            for delta_x, delta_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor_tile_x = tile_x + delta_x
                neighbor_tile_y = tile_y + delta_y
                neighbor_is_mask = (
                    0 <= neighbor_tile_x < tile_width
                    and 0 <= neighbor_tile_y < tile_height
                    and tile_alpha[neighbor_tile_y][neighbor_tile_x] > 0.0
                )
                if neighbor_is_mask:
                    continue
                outside_x = inside_x + delta_x
                outside_y = inside_y + delta_y
                if outside_x < 0 or outside_x >= width or outside_y < 0 or outside_y >= height:
                    continue
                diffs.append(abs(image[inside_y][inside_x] - image[outside_y][outside_x]))
    return diffs


def _composite_luma_grid(
    *,
    master_luma: list[list[float]],
    tile_luma: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
) -> list[list[float]]:
    composite = [list(row) for row in master_luma]
    height = len(master_luma)
    width = len(master_luma[0])
    for tile_y, (tile_row, alpha_row) in enumerate(zip(tile_luma, tile_alpha, strict=False)):
        for tile_x, (tile_pixel, alpha) in enumerate(zip(tile_row, alpha_row, strict=False)):
            target_x = x + tile_x
            target_y = y + tile_y
            if target_x < 0 or target_x >= width or target_y < 0 or target_y >= height:
                continue
            master_pixel = composite[target_y][target_x]
            composite[target_y][target_x] = master_pixel * (1.0 - alpha) + tile_pixel * alpha
    return composite


def _image_to_luma_grid(image: object) -> list[list[float]]:
    width, height = image.size
    pixels = list(image.getdata())
    return [
        [float(pixels[row * width + column]) for column in range(width)]
        for row in range(height)
    ]


def _image_to_alpha_grid(image: object) -> list[list[float]]:
    alpha_image = image.getchannel("A")
    width, height = alpha_image.size
    pixels = list(alpha_image.getdata())
    return [
        [float(pixels[row * width + column]) / 255.0 for column in range(width)]
        for row in range(height)
    ]


def _overlay_artifact_metrics(
    *,
    master_luma: list[list[float]],
    tile_luma: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
) -> OverlayArtifactMetrics:
    composite = _composite_luma_grid(master_luma=master_luma, tile_luma=tile_luma, tile_alpha=tile_alpha, x=x, y=y)
    mask_coords, boundary_coords, outer_ring_coords = _mask_regions(tile_alpha)
    tile_residue_ratio = _normalized_region_diff(
        original=master_luma,
        overlay=composite,
        coords=mask_coords,
        x=x,
        y=y,
    )
    double_edge_score = _normalized_region_diff(
        original=master_luma,
        overlay=composite,
        coords=boundary_coords,
        x=x,
        y=y,
    )
    overflow_edge_score = _normalized_region_diff(
        original=master_luma,
        overlay=composite,
        coords=outer_ring_coords,
        x=x,
        y=y,
    )
    artifact_score = _clamp01(
        tile_residue_ratio * 0.50
        + double_edge_score * 0.30
        + overflow_edge_score * 0.20
    )
    return OverlayArtifactMetrics(
        tile_residue_ratio=tile_residue_ratio,
        double_edge_score=double_edge_score,
        overflow_edge_score=overflow_edge_score,
        artifact_score=artifact_score,
        clean_score=_clamp01(1.0 - artifact_score),
    )


def _best_local_bbox(
    *,
    master_luma: list[list[float]],
    tile_luma: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
) -> tuple[list[int], OverlayArtifactMetrics]:
    height = len(master_luma)
    width = len(master_luma[0])
    tile_height = len(tile_alpha)
    tile_width = len(tile_alpha[0])
    max_x = max(0, width - tile_width)
    max_y = max(0, height - tile_height)

    best_x = min(max(x, 0), max_x)
    best_y = min(max(y, 0), max_y)
    best_metrics = _overlay_artifact_metrics(
        master_luma=master_luma,
        tile_luma=tile_luma,
        tile_alpha=tile_alpha,
        x=best_x,
        y=best_y,
    )
    for candidate_y in range(max(0, y - _LOCAL_SEARCH_RADIUS_PX), min(max_y, y + _LOCAL_SEARCH_RADIUS_PX) + 1, 2):
        for candidate_x in range(max(0, x - _LOCAL_SEARCH_RADIUS_PX), min(max_x, x + _LOCAL_SEARCH_RADIUS_PX) + 1, 2):
            metrics = _overlay_artifact_metrics(
                master_luma=master_luma,
                tile_luma=tile_luma,
                tile_alpha=tile_alpha,
                x=candidate_x,
                y=candidate_y,
            )
            if metrics.artifact_score < best_metrics.artifact_score:
                best_x = candidate_x
                best_y = candidate_y
                best_metrics = metrics

    refine_radius = 2
    for candidate_y in range(max(0, best_y - refine_radius), min(max_y, best_y + refine_radius) + 1):
        for candidate_x in range(max(0, best_x - refine_radius), min(max_x, best_x + refine_radius) + 1):
            metrics = _overlay_artifact_metrics(
                master_luma=master_luma,
                tile_luma=tile_luma,
                tile_alpha=tile_alpha,
                x=candidate_x,
                y=candidate_y,
            )
            if metrics.artifact_score < best_metrics.artifact_score:
                best_x = candidate_x
                best_y = candidate_y
                best_metrics = metrics

    return [best_x, best_y, best_x + tile_width, best_y + tile_height], best_metrics


def _mask_regions(
    tile_alpha: list[list[float]],
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
    tile_height = len(tile_alpha)
    tile_width = len(tile_alpha[0])
    mask_coords: list[tuple[int, int]] = []
    boundary_coords: list[tuple[int, int]] = []
    outer_ring: set[tuple[int, int]] = set()

    for tile_y in range(tile_height):
        for tile_x in range(tile_width):
            if tile_alpha[tile_y][tile_x] <= 0.0:
                continue
            mask_coords.append((tile_x, tile_y))
            is_boundary = False
            for delta_x, delta_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor_x = tile_x + delta_x
                neighbor_y = tile_y + delta_y
                neighbor_is_mask = (
                    0 <= neighbor_x < tile_width
                    and 0 <= neighbor_y < tile_height
                    and tile_alpha[neighbor_y][neighbor_x] > 0.0
                )
                if neighbor_is_mask:
                    continue
                is_boundary = True
                outer_ring.add((neighbor_x, neighbor_y))
            if is_boundary:
                boundary_coords.append((tile_x, tile_y))

    outer_ring_coords = [
        (tile_x, tile_y)
        for tile_x, tile_y in sorted(outer_ring)
        if 0 <= tile_x < tile_width and 0 <= tile_y < tile_height and tile_alpha[tile_y][tile_x] <= 0.0
    ]
    return mask_coords, boundary_coords, outer_ring_coords


def _normalized_region_diff(
    *,
    original: list[list[float]],
    overlay: list[list[float]],
    coords: list[tuple[int, int]],
    x: int,
    y: int,
) -> float:
    if not coords:
        return 0.0
    height = len(original)
    width = len(original[0])
    values: list[float] = []
    for offset_x, offset_y in coords:
        target_x = x + offset_x
        target_y = y + offset_y
        if target_x < 0 or target_x >= width or target_y < 0 or target_y >= height:
            continue
        values.append(abs(overlay[target_y][target_x] - original[target_y][target_x]))
    if not values:
        return 1.0
    return _clamp01(_mean(values) / 255.0)


def _reason_cn(score: OcclusionScore) -> str:
    if score.success:
        return "模型输出位置与附近最干净贴合位置的边框偏差在 5px 以内，且局部 overlay 痕迹检测达标，判定通过。"
    if score.best_local_offset_px > _BBOX_EDGE_TOLERANCE_PX:
        return "把图块在模型输出位置附近挪动后，存在明显更干净的位置，且偏差超过 5px，判定为定位偏移。"
    if score.tile_residue_ratio > 0.35:
        return "overlay 中仍保留明显图块痕迹，疑似缺口块没有贴到合适位置。"
    if score.double_edge_score > 0.35:
        return "overlay 中出现明显双边缘或重影，疑似图块轮廓与缺口轮廓没有对齐。"
    if score.overflow_edge_score > 0.35:
        return "overlay 中出现明显越界边缘，疑似图块压到了缺口外的背景区域。"
    return "当前位置附近虽有可接受贴合候选，但最佳局部贴合的 clean score 仍未达标，建议结合 overlay/diff 继续人工复核。"


def _find_image(root: Path, *, stem: str) -> Path | None:
    for suffix in _IMAGE_EXTENSIONS:
        candidate = root / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _find_first_image(root: Path, *, stems: tuple[str, ...]) -> Path | None:
    for stem in stems:
        candidate = _find_image(root, stem=stem)
        if candidate is not None:
            return candidate
    return None


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / float(len(items))


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _estimate_reference_bbox(
    *,
    master_luma: list[list[float]],
    tile_alpha: list[list[float]],
) -> tuple[list[int], list[int], float]:
    height = len(master_luma)
    width = len(master_luma[0])
    tile_height = len(tile_alpha)
    tile_width = len(tile_alpha[0])
    max_x = max(0, width - tile_width)
    max_y = max(0, height - tile_height)
    search_space = (max_x + 1) * (max_y + 1)
    coarse_step = 2 if search_space > 4096 else 1

    best_x = 0
    best_y = 0
    best_score = -1.0
    for candidate_y in range(0, max_y + 1, coarse_step):
        for candidate_x in range(0, max_x + 1, coarse_step):
            score = _slot_signal_score(master_luma=master_luma, tile_alpha=tile_alpha, x=candidate_x, y=candidate_y)
            if score > best_score:
                best_x = candidate_x
                best_y = candidate_y
                best_score = score

    refine_radius = max(1, coarse_step)
    for candidate_y in range(max(0, best_y - refine_radius), min(max_y, best_y + refine_radius) + 1):
        for candidate_x in range(max(0, best_x - refine_radius), min(max_x, best_x + refine_radius) + 1):
            score = _slot_signal_score(master_luma=master_luma, tile_alpha=tile_alpha, x=candidate_x, y=candidate_y)
            if score > best_score:
                best_x = candidate_x
                best_y = candidate_y
                best_score = score

    bbox = [best_x, best_y, best_x + tile_width, best_y + tile_height]
    return bbox, _bbox_center(bbox), best_score


def _slot_signal_score(
    *,
    master_luma: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
) -> float:
    inside_values, boundary_diffs = _mask_patch_values(image=master_luma, tile_alpha=tile_alpha, x=x, y=y)
    if not inside_values:
        return 0.0
    inside_mean = _mean(inside_values) / 255.0
    inside_std = _stddev(inside_values) / 255.0
    bright_ratio = sum(1 for value in inside_values if value >= 180.0) / float(len(inside_values))
    boundary_score = _clamp01(_mean(boundary_diffs) / 96.0)
    brightness_score = _clamp01((inside_mean - 0.55) / 0.30)
    uniformity_score = 1.0 - _clamp01(inside_std / 0.12)
    bright_ratio_score = _clamp01(bright_ratio / 0.75)
    return _clamp01(
        boundary_score * 0.35
        + brightness_score * 0.25
        + uniformity_score * 0.20
        + bright_ratio_score * 0.20
    )


def _mask_patch_values(
    *,
    image: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
) -> tuple[list[float], list[float]]:
    inside_values: list[float] = []
    boundary_diffs: list[float] = []
    height = len(image)
    width = len(image[0])
    tile_height = len(tile_alpha)
    tile_width = len(tile_alpha[0])
    for tile_y in range(tile_height):
        for tile_x in range(tile_width):
            if tile_alpha[tile_y][tile_x] <= 0.0:
                continue
            target_x = x + tile_x
            target_y = y + tile_y
            if target_x < 0 or target_x >= width or target_y < 0 or target_y >= height:
                continue
            inside_values.append(image[target_y][target_x])
            for delta_x, delta_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor_tile_x = tile_x + delta_x
                neighbor_tile_y = tile_y + delta_y
                neighbor_is_mask = (
                    0 <= neighbor_tile_x < tile_width
                    and 0 <= neighbor_tile_y < tile_height
                    and tile_alpha[neighbor_tile_y][neighbor_tile_x] > 0.0
                )
                if neighbor_is_mask:
                    continue
                outside_x = target_x + delta_x
                outside_y = target_y + delta_y
                if outside_x < 0 or outside_x >= width or outside_y < 0 or outside_y >= height:
                    continue
                boundary_diffs.append(abs(image[target_y][target_x] - image[outside_y][outside_x]))
    return inside_values, boundary_diffs


def _stddev(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    avg = _mean(items)
    return math.sqrt(sum((value - avg) ** 2 for value in items) / float(len(items)))


def _bbox_center(bbox: list[int]) -> list[int]:
    return [int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)]


def _position_tolerance_px(tile_alpha: list[list[float]]) -> float:
    tile_height = len(tile_alpha)
    tile_width = len(tile_alpha[0])
    return max(10.0, min(tile_width, tile_height) * 0.5)


def _point_distance(lhs: list[int], rhs: list[int]) -> float:
    return math.sqrt(float((lhs[0] - rhs[0]) ** 2 + (lhs[1] - rhs[1]) ** 2))


def _bbox_edge_error(lhs: list[int], rhs: list[int]) -> float:
    return float(max(abs(lhs[index] - rhs[index]) for index in range(4)))


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:.4f}"
