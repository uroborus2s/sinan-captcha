"""Dataset planning fallbacks for autonomous training."""

from __future__ import annotations

import re

from auto_train import contracts


_RETUNE_SUFFIX_PATTERN = re.compile(r"_r\d+$")


def build_dataset_plan(
    *,
    summary: contracts.ResultSummaryRecord,
    decision: contracts.DecisionRecord,
) -> contracts.DatasetPlanRecord:
    dataset_action = "new_version" if decision.decision == "REGENERATE_DATA" else "reuse"
    generator_preset = _generator_preset(summary=summary, dataset_action=dataset_action)
    generator_overrides = _generator_overrides(
        task=summary.task,
        preset=generator_preset,
        summary=summary,
        dataset_action=dataset_action,
    )
    rationale_cn = _rationale_cn(summary=summary, decision=decision, dataset_action=dataset_action)
    evidence = [
        f"decision={decision.decision}",
        f"dataset_action={dataset_action}",
        f"trend={summary.trend}",
    ]
    evidence.extend(summary.evidence)
    return contracts.DatasetPlanRecord(
        study_name=summary.study_name,
        task=summary.task,
        trial_id=summary.trial_id,
        dataset_action=dataset_action,
        generator_preset=generator_preset,
        generator_overrides=generator_overrides,
        boost_classes=summary.weak_classes,
        focus_failure_patterns=summary.failure_patterns,
        rationale_cn=rationale_cn,
        evidence=evidence,
    )


def _rationale_cn(
    *,
    summary: contracts.ResultSummaryRecord,
    decision: contracts.DecisionRecord,
    dataset_action: str,
) -> str:
    if dataset_action == "new_version":
        classes = "、".join(summary.weak_classes) if summary.weak_classes else "当前弱类"
        patterns = "、".join(summary.failure_patterns) if summary.failure_patterns else "当前失败模式"
        return f"本轮建议新建数据版本，重点补强 {classes}，并围绕 {patterns} 扩充样本。"
    return f"本轮仍以复用现有数据版本为主，继续观察 {decision.decision} 后的训练变化。"


def _generator_preset(*, summary: contracts.ResultSummaryRecord, dataset_action: str) -> str:
    base_preset = _infer_base_preset(summary.dataset_version)
    if dataset_action != "new_version":
        return base_preset
    if base_preset == "smoke":
        return "v1"
    if base_preset == "firstpass":
        if summary.trend in {"plateau", "declining"} or summary.failure_patterns:
            return "hard"
        return "v1"
    if summary.trend in {"plateau", "declining"} or summary.failure_patterns:
        return "hard"
    return base_preset


def _infer_base_preset(dataset_version: str) -> str:
    base = _RETUNE_SUFFIX_PATTERN.sub("", dataset_version.strip())
    if base in {"smoke", "firstpass", "v1", "hard"}:
        return base
    return "firstpass"


def _generator_overrides(
    *,
    task: str,
    preset: str,
    summary: contracts.ResultSummaryRecord,
    dataset_action: str,
) -> dict[str, contracts.JsonValue] | None:
    if dataset_action != "new_version":
        return None
    sample_count = _sample_count(task=task, preset=preset, summary=summary)
    if task == "group1":
        return {
            "project": {"sample_count": sample_count},
            "sampling": _group1_sampling(preset),
            "effects": {
                "common": _common_effects(preset),
                "click": _click_effects(preset),
            },
        }
    return {
        "project": {"sample_count": sample_count},
        "effects": {
            "common": _common_effects(preset),
            "slide": _slide_effects(preset),
        },
    }


def _sample_count(*, task: str, preset: str, summary: contracts.ResultSummaryRecord) -> int:
    base_counts = {
        ("group1", "smoke"): 200,
        ("group1", "firstpass"): 240,
        ("group1", "v1"): 10000,
        ("group1", "hard"): 12000,
        ("group2", "smoke"): 200,
        ("group2", "firstpass"): 220,
        ("group2", "v1"): 10000,
        ("group2", "hard"): 12000,
    }
    base = base_counts.get((task, preset), 240)
    signal_weight = len(summary.weak_classes) + len(summary.failure_patterns)
    return base + min(signal_weight, 3) * 20


def _group1_sampling(preset: str) -> dict[str, contracts.JsonValue]:
    if preset == "hard":
        return {
            "target_count_min": 3,
            "target_count_max": 3,
            "distractor_count_min": 5,
            "distractor_count_max": 8,
        }
    return {
        "target_count_min": 3,
        "target_count_max": 3,
        "distractor_count_min": 3,
        "distractor_count_max": 6,
    }


def _common_effects(preset: str) -> dict[str, contracts.JsonValue]:
    if preset == "hard":
        return {
            "scene_veil_strength": 1.45,
            "background_blur_radius_min": 1,
            "background_blur_radius_max": 2,
        }
    return {
        "scene_veil_strength": 1.15,
        "background_blur_radius_min": 0,
        "background_blur_radius_max": 1,
    }


def _click_effects(preset: str) -> dict[str, contracts.JsonValue]:
    if preset == "hard":
        return {
            "icon_shadow_alpha_min": 0.28,
            "icon_shadow_alpha_max": 0.36,
            "icon_shadow_offset_x_min": 2,
            "icon_shadow_offset_x_max": 3,
            "icon_shadow_offset_y_min": 3,
            "icon_shadow_offset_y_max": 4,
            "icon_edge_blur_radius_min": 1,
            "icon_edge_blur_radius_max": 2,
        }
    return {
        "icon_shadow_alpha_min": 0.24,
        "icon_shadow_alpha_max": 0.3,
        "icon_shadow_offset_x_min": 2,
        "icon_shadow_offset_x_max": 2,
        "icon_shadow_offset_y_min": 3,
        "icon_shadow_offset_y_max": 3,
        "icon_edge_blur_radius_min": 0,
        "icon_edge_blur_radius_max": 1,
    }


def _slide_effects(preset: str) -> dict[str, contracts.JsonValue]:
    if preset == "hard":
        return {
            "gap_shadow_alpha_min": 0.16,
            "gap_shadow_alpha_max": 0.24,
            "gap_shadow_offset_x_min": 1,
            "gap_shadow_offset_x_max": 3,
            "gap_shadow_offset_y_min": 1,
            "gap_shadow_offset_y_max": 3,
            "tile_edge_blur_radius_min": 1,
            "tile_edge_blur_radius_max": 2,
        }
    return {
        "gap_shadow_alpha_min": 0.08,
        "gap_shadow_alpha_max": 0.16,
        "gap_shadow_offset_x_min": 0,
        "gap_shadow_offset_x_max": 1,
        "gap_shadow_offset_y_min": 0,
        "gap_shadow_offset_y_max": 1,
        "tile_edge_blur_radius_min": 0,
        "tile_edge_blur_radius_max": 1,
    }
