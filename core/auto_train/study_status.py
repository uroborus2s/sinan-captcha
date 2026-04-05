"""Study-level status summaries for autonomous-training orchestration."""

from __future__ import annotations

from core.auto_train import contracts


def build_study_status(
    *,
    study: contracts.StudyRecord,
    leaderboard: contracts.LeaderboardRecord,
    decision: contracts.DecisionRecord,
) -> contracts.StudyStatusRecord:
    best_entry = leaderboard.best_entry
    budget_pressure = _budget_pressure(study, completed_trials=len(leaderboard.entries))
    summary_cn = _summary_cn(study=study, best_entry=best_entry, decision=decision, budget_pressure=budget_pressure)
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
        next_actions_cn=_next_actions_cn(decision.decision),
        evidence=_evidence(study=study, best_entry=best_entry, decision=decision, budget_pressure=budget_pressure),
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
        "",
        "## 中文摘要",
        "",
        record.summary_cn,
        "",
        "## 下一步",
        "",
    ]
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
) -> str:
    if best_entry is None:
        return f"当前 study 还没有形成稳定最佳轮次，最近动作是 {decision.decision}，预算压力为 {budget_pressure}。"
    return (
        f"当前 study 状态为 {study.status}，最佳轮次是 {best_entry.trial_id}，"
        f"主指标达到 {best_entry.primary_score:.4f}，最近动作是 {decision.decision}，预算压力为 {budget_pressure}。"
    )


def _next_actions_cn(decision: str) -> list[str]:
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
    return evidence
