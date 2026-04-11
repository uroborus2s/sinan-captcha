"""Study-level status summaries for autonomous-training orchestration."""

from __future__ import annotations

from auto_train import contracts


def build_study_status(
    *,
    study: contracts.StudyRecord,
    leaderboard: contracts.LeaderboardRecord,
    decision: contracts.DecisionRecord,
    business_eval: contracts.BusinessEvalRecord | None = None,
) -> contracts.StudyStatusRecord:
    best_entry = leaderboard.best_entry
    budget_pressure = _budget_pressure(study, completed_trials=len(leaderboard.entries))
    summary_cn = _summary_cn(
        study=study,
        best_entry=best_entry,
        decision=decision,
        budget_pressure=budget_pressure,
        business_eval=business_eval,
    )
    return contracts.StudyStatusRecord(
        study_name=study.study_name,
        task=study.task,
        status=study.status,
        current_trial_id=study.current_trial_id,
        best_trial_id=None if best_entry is None else best_entry.trial_id,
        latest_decision=decision.decision,
        best_primary_score=None if best_entry is None else best_entry.primary_score,
        budget_pressure=budget_pressure,
        summary_cn=summary_cn,
        next_actions_cn=_next_actions_cn(study=study, decision=decision.decision, business_eval=business_eval),
        evidence=_evidence(
            study=study,
            best_entry=best_entry,
            decision=decision,
            budget_pressure=budget_pressure,
            business_eval=business_eval,
        ),
        business_success_rate=None if business_eval is None else business_eval.success_rate,
        business_success_threshold=None if business_eval is None else business_eval.success_threshold,
        commercial_ready=None if business_eval is None else business_eval.commercial_ready,
        latest_gate_status=_gate_status(business_eval),
        final_reason=study.final_reason,
        final_detail=study.final_detail,
    )


def markdown_from_study_status(record: contracts.StudyStatusRecord) -> str:
    lines = [
        f"# {record.study_name}",
        "",
        f"- task: {record.task}",
        f"- status: {record.status}",
        f"- current_trial_id: {record.current_trial_id}",
        f"- latest_decision: {record.latest_decision}",
        f"- best_trial_id: {record.best_trial_id}",
        f"- best_primary_score: {record.best_primary_score}",
        f"- budget_pressure: {record.budget_pressure}",
    ]
    if record.final_reason is not None:
        lines.append(f"- final_reason: {record.final_reason}")
    if record.final_detail is not None:
        lines.append(f"- final_detail: {record.final_detail}")
    if record.business_success_rate is not None:
        lines.extend(
            [
                f"- business_success_rate: {record.business_success_rate}",
                f"- business_success_threshold: {record.business_success_threshold}",
                f"- commercial_ready: {record.commercial_ready}",
                f"- latest_gate_status: {record.latest_gate_status}",
            ]
        )
    lines.extend(
        [
            "",
            "## 中文摘要",
            "",
            record.summary_cn,
            "",
            "## 下一步",
            "",
        ]
    )
    for action in record.next_actions_cn:
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def _budget_pressure(study: contracts.StudyRecord, *, completed_trials: int) -> str:
    ratio = completed_trials / study.budget.max_trials
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.5:
        return "medium"
    return "low"


def _summary_cn(
    *,
    study: contracts.StudyRecord,
    best_entry: contracts.LeaderboardEntry | None,
    decision: contracts.DecisionRecord,
    budget_pressure: str,
    business_eval: contracts.BusinessEvalRecord | None,
) -> str:
    final_reason_cn = _final_reason_cn(study.final_reason, study.final_detail)
    if business_eval is not None:
        if business_eval.commercial_ready:
            return (
                f"当前 study 状态为 {study.status}，最新候选已通过真实业务样本 gate，"
                f"成功率达到 {business_eval.success_rate:.2%}，满足 {business_eval.success_threshold:.0%} 商用门槛。"
            )
        if study.status == "stopped":
            return (
                f"当前 study 状态为 {study.status}，训练指标已进入候选晋级区间，"
                f"但真实业务样本 gate 成功率仅 {business_eval.success_rate:.2%}，"
                f"尚未达到 {business_eval.success_threshold:.0%} 商用门槛，未达到商用门。"
                f"本次自动训练因 {final_reason_cn} 已停止。"
            )
        return (
            f"当前 study 状态为 {study.status}，训练指标已进入候选晋级区间，"
            f"但真实业务样本 gate 成功率仅 {business_eval.success_rate:.2%}，"
            f"尚未达到 {business_eval.success_threshold:.0%} 商用门槛，将继续训练。"
        )
    if study.status == "stopped":
        return f"当前 study 状态为 {study.status}，本次自动训练因 {final_reason_cn} 已停止。"
    if best_entry is None:
        return f"当前 study 还没有形成稳定最佳轮次，最近动作是 {decision.decision}，预算压力为 {budget_pressure}。"
    return (
        f"当前 study 状态为 {study.status}，最佳轮次是 {best_entry.trial_id}，"
        f"主指标达到 {best_entry.primary_score:.4f}，最近动作是 {decision.decision}，预算压力为 {budget_pressure}。"
    )


def _next_actions_cn(
    *,
    study: contracts.StudyRecord,
    decision: str,
    business_eval: contracts.BusinessEvalRecord | None,
) -> list[str]:
    if business_eval is not None:
        if business_eval.commercial_ready:
            return ["当前候选已达到商用门，停止自动训练并固化最终报告。"]
        if study.status == "stopped":
            return ["本次自动训练已停止；如需继续，请扩大预算、放宽停止策略或调整真实业务样本后重新启动。"]
        return ["继续下一轮训练，优先修复 business gate 未通过的样本。"]
    if study.status == "stopped":
        return ["本次自动训练已停止；如需继续，请根据停止原因调整预算或策略后重新启动。"]
    if decision == "PROMOTE_BRANCH":
        return ["冻结当前最佳分支并安排人工验收。"]
    if decision == "REGENERATE_DATA":
        return ["按失败模式生成新数据版本，再基于当前最佳分支继续训练。"]
    if decision == "ABANDON_BRANCH":
        return ["停止当前分支继续投入，保留结果供对比复盘。"]
    if decision == "RESUME":
        return ["继续当前训练轮次，优先观察是否仍有稳定提升。"]
    return ["继续下一轮调参，并对比主指标与失败模式是否改善。"]


def _evidence(
    *,
    study: contracts.StudyRecord,
    best_entry: contracts.LeaderboardEntry | None,
    decision: contracts.DecisionRecord,
    budget_pressure: str,
    business_eval: contracts.BusinessEvalRecord | None,
) -> list[str]:
    evidence = [
        f"status={study.status}",
        f"current_trial_id={study.current_trial_id}",
        f"latest_decision={decision.decision}",
        f"budget_pressure={budget_pressure}",
    ]
    if best_entry is not None:
        evidence.append(f"best_trial_id={best_entry.trial_id}")
        evidence.append(f"best_primary_score={best_entry.primary_score:.6f}")
    if business_eval is not None:
        evidence.append(f"business_success_rate={business_eval.success_rate:.6f}")
        evidence.append(f"business_success_threshold={business_eval.success_threshold:.6f}")
        evidence.append(f"commercial_ready={str(business_eval.commercial_ready).lower()}")
    if study.final_reason is not None:
        evidence.append(f"final_reason={study.final_reason}")
    if study.final_detail is not None:
        evidence.append(f"final_detail={study.final_detail}")
    return evidence


def _gate_status(record: contracts.BusinessEvalRecord | None) -> str | None:
    if record is None:
        return None
    for item in record.evidence:
        if item.startswith("runner_error="):
            return "error"
    return "passed" if record.commercial_ready else "failed"


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
    return "未记录停止原因"
