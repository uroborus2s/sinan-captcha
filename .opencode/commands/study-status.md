---
description: Summarize the current study and return study_status.json
agent: plan
subtask: true
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

1. Load and follow the local `study-archivist` skill.
2. Read the attached study state and leaderboard.
3. Produce the final contents of `study_status.json`.
4. Summarize current status, best trial, current trial, budget pressure, and the next human-readable actions in Chinese.
5. Keep the output machine-readable and self-contained.
6. Do not attempt to run commands or request additional context beyond the attached files.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.
