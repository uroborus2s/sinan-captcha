"""Business-sample evaluation helpers for autonomous training."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import time
from typing import Iterable

from core.auto_train import contracts
from core.solve import group2_runtime
from core.train.base import default_best_weights

_EDGE_DIFF_THRESHOLD = 18.0
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
_MASTER_IMAGE_STEMS = ("master", "bg", "background")
_TILE_IMAGE_STEMS = ("tile", "gap", "piece", "puzzle_piece")


@dataclass(frozen=True)
class OcclusionScore:
    boundary_before: float
    boundary_after: float
    fill_score: float
    seam_score: float
    occlusion_score: float
    success: bool


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    master_path: Path
    tile_path: Path


def score_occlusion_overlay(
    *,
    master_luma: list[list[float]],
    tile_luma: list[list[float]],
    tile_alpha: list[list[float]],
    x: int,
    y: int,
    success_threshold: float = 0.78,
    edge_diff_threshold: float = _EDGE_DIFF_THRESHOLD,
) -> OcclusionScore:
    """Score whether overlaying the tile at ``(x, y)`` cleanly occludes the gap."""

    _validate_grids(master_luma=master_luma, tile_luma=tile_luma, tile_alpha=tile_alpha)
    composite = _composite_luma_grid(master_luma=master_luma, tile_luma=tile_luma, tile_alpha=tile_alpha, x=x, y=y)
    before_diffs = _boundary_diffs(image=master_luma, tile_alpha=tile_alpha, x=x, y=y)
    after_diffs = _boundary_diffs(image=composite, tile_alpha=tile_alpha, x=x, y=y)
    if not before_diffs or not after_diffs:
        return OcclusionScore(
            boundary_before=1.0,
            boundary_after=1.0,
            fill_score=0.0,
            seam_score=0.0,
            occlusion_score=0.0,
            success=False,
        )

    boundary_before = _clamp01(_mean(before_diffs) / 255.0)
    boundary_after = _clamp01(_mean(after_diffs) / 255.0)
    fill_score = _clamp01((boundary_before - boundary_after) / max(boundary_before, 1e-6))
    seam_score = 1.0 - _bad_edge_ratio(after_diffs, threshold=edge_diff_threshold)
    occlusion_score = _clamp01(fill_score * 0.6 + seam_score * 0.4)
    success = occlusion_score >= success_threshold and fill_score >= 0.2
    return OcclusionScore(
        boundary_before=boundary_before,
        boundary_after=boundary_after,
        fill_score=fill_score,
        seam_score=seam_score,
        occlusion_score=occlusion_score,
        success=success,
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
        f"- occlusion_threshold: {record.occlusion_threshold:.4f}",
        f"- verdict_cn: {verdict}",
        "",
        "## 字段说明",
        "",
        "- available_cases: business_eval 目录下发现的全部候选样本数。",
        "- sample_size: 本轮配置允许抽样的最大样本数。",
        "- total_cases: 本轮实际参与商业测试的样本数。",
        "- passed_cases: 单样本 occlusion / fill 同时达标的通过数。",
        "- success_rate: passed_cases / total_cases，表示本轮商业测试通过率。",
        "- success_threshold: 判定达到商用门所需的最小通过率。",
        "- occlusion_threshold: 单样本 occlusion_score 的最低通过阈值。",
        "- predicted_bbox: 求解模块输出的缺口框坐标，格式为 [x1, y1, x2, y2]。",
        "- predicted_center: 求解模块输出的缺口中心点，格式为 [cx, cy]。",
        "- inference_ms: 求解模块本次推理耗时，单位毫秒。",
        "- fill: 贴回缺口块后，原始缺口边界残差下降的幅度，越高越好。",
        "- seam: 缺口块边缘与背景拼缝的自然程度，越高越好。",
        "- occlusion: 商业测试主分数，按 0.6 * fill + 0.4 * seam 计算。",
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
            f"predicted_center={item.predicted_center}, inference_ms={item.inference_ms:.4f}, "
            f"occlusion={item.occlusion_score:.4f}, fill={item.fill_score:.4f}, "
            f"seam={item.seam_score:.4f}, reason_cn={item.reason_cn}"
        )
    return "\n".join(lines) + "\n"


def log_from_business_eval(record: contracts.BusinessEvalRecord) -> str:
    lines = [
        "# 字段说明",
        "# predicted_bbox: 模型输出的背景图坐标框 [x1, y1, x2, y2]。",
        "# predicted_center: 模型输出的缺口中心点 [cx, cy]。",
        "# inference_ms: 求解模块单次推理耗时，单位毫秒。",
        "# fill: 贴回后原始缺口边界残差下降幅度，越高越好。",
        "# seam: 拼缝边缘自然程度，越高越好。",
        "# occlusion: 商业测试主分数，按 0.6 * fill + 0.4 * seam 计算。",
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
        f"occlusion_threshold={record.occlusion_threshold:.4f}",
        f"commercial_ready={str(record.commercial_ready).lower()}",
        "",
    ]
    for item in record.case_results:
        status = "PASS" if item.success else "FAIL"
        lines.append(
            f"{status} case_id={item.case_id} predicted_bbox={item.predicted_bbox} "
            f"predicted_center={item.predicted_center} inference_ms={item.inference_ms:.4f} "
            f"occlusion={item.occlusion_score:.4f} fill={item.fill_score:.4f} "
            f"seam={item.seam_score:.4f} reason_cn={item.reason_cn}"
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
        f"- occlusion_threshold: {business_record.occlusion_threshold:.4f}",
        f"- commercial_ready: {business_record.commercial_ready}",
        "",
        "## 商业测试字段说明",
        "",
        "- predicted_bbox / predicted_center / inference_ms: 直接来自 group2 求解模块的推理输出。",
        "- fill_score: 缺口块贴回后，原始缺口边界残差被削减的幅度；0 表示几乎没补上，1 表示显著补平。",
        "- seam_score: 缺口块边缘与背景拼缝的自然程度；越高说明边缘越贴合。",
        "- occlusion_score: 该样本的主评分，按 0.6 * fill_score + 0.4 * seam_score 计算。",
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
            f"predicted_center={item.predicted_center}, occlusion={item.occlusion_score:.4f}, "
            f"fill={item.fill_score:.4f}, seam={item.seam_score:.4f}, reason_cn={item.reason_cn}"
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
        f"单样本还需满足 occlusion_score >= {record.occlusion_threshold:.2f}。"
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


def _reason_cn(score: OcclusionScore) -> str:
    if score.success:
        return "贴回后缺口边界明显收敛，遮挡质量达到阈值。"
    if score.fill_score < 0.2:
        return "贴回后没有显著降低原始缺口边界残差，疑似未覆盖到真实缺口。"
    if score.seam_score < 0.6:
        return "贴图边缘与周围背景衔接仍然明显，疑似定位存在偏移。"
    return "遮挡质量未达到商用阈值。"


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


def _bad_edge_ratio(diffs: list[float], *, threshold: float) -> float:
    if not diffs:
        return 1.0
    bad = sum(1 for item in diffs if item > threshold)
    return bad / float(len(diffs))


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
