---
description: Summarize the current study and return study_status.json
agent: build
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`

Required attached files:

- `study.json`
- `leaderboard.json`

Optional attached files:

- `best_trial.json`
- `decisions.jsonl`

Task:

1. Load the local `study-archivist` skill using the `skill` tool with exact name `study-archivist`.
2. Read the attached study state and leaderboard.
3. Produce the final contents of `study_status.json`.
4. Summarize current status, best trial, current trial, budget pressure, and the next human-readable actions in Chinese.
5. Keep the output machine-readable and self-contained.
6. Do not attempt to run commands or request additional context beyond the attached files.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.

Example JSON output string:

{"study_name":"study_group1_llm","task":"group1","status":"stopped","current_trial_id":"trial_0002","best_trial_id":"trial_0001","latest_decision":"REGENERATE_DATA","best_primary_score":0.0,"budget_pressure":"medium","summary_cn":"当前 study 状态为 stopped，最佳轮次是 trial_0001，最近动作是 REGENERATE_DATA，预算压力为 medium。","next_actions_cn":["按失败模式生成新数据版本，再基于当前最佳分支继续训练。"],"evidence":["status=stopped","current_trial_id=trial_0002","latest_decision=REGENERATE_DATA","budget_pressure=medium","best_trial_id=trial_0001","best_primary_score=0.000000"]}
