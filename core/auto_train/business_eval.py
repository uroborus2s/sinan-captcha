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
        tile_rgba = Image.open(case.tile_path).convert("RGBA")
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
        "## 样本结果",
        "",
    ]
    if not record.case_results:
        lines.append("- 当前 trial 没有写入样本明细。")
    for item in record.case_results:
        status = "PASS" if item.success else "FAIL"
        lines.append(
            f"- {item.case_id}: {status}, occlusion={item.occlusion_score:.4f}, "
            f"fill={item.fill_score:.4f}, seam={item.seam_score:.4f}, reason_cn={item.reason_cn}"
        )
    return "\n".join(lines) + "\n"


def commercial_report_markdown(
    *,
    study: contracts.StudyRecord,
    leaderboard: contracts.LeaderboardRecord,
    decision: contracts.DecisionRecord,
    business_record: contracts.BusinessEvalRecord,
) -> str:
    best_entry = leaderboard.best_entry
    conclusion = "达到商用门，可停止自动训练。" if business_record.commercial_ready else "未达到商用门，应继续训练。"
    lines = [
        f"# {study.study_name} 商业可用性结论",
        "",
        "## 结论",
        "",
        conclusion,
        "",
        "## 当前最佳候选",
        "",
        f"- latest_decision: {decision.decision}",
        f"- best_trial_id: {None if best_entry is None else best_entry.trial_id}",
        f"- best_primary_score: {None if best_entry is None else best_entry.primary_score}",
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
        "## 失败样本",
        "",
    ]
    failed_cases = [item for item in business_record.case_results if not item.success]
    if not failed_cases:
        lines.append("- 无")
    for item in failed_cases[:20]:
        lines.append(
            f"- {item.case_id}: occlusion={item.occlusion_score:.4f}, "
            f"fill={item.fill_score:.4f}, seam={item.seam_score:.4f}, reason_cn={item.reason_cn}"
        )
    return "\n".join(lines) + "\n"


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
