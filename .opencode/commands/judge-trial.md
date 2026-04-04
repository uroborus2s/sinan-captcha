---
description: Judge one summarized trial and return decision.json
agent: plan
subtask: true
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`
- `trial_id`: `$3`

Required attached files:

- `study.json`
- `result_summary.json`

Optional attached files:

- `leaderboard.json`
- `decisions.jsonl`

Task:

1. Load and follow the local `training-judge` skill.
2. Read the current trial summary and study budget context.
3. Decide the next action using only the allowed action set:
   - `RETUNE`
   - `REGENERATE_DATA`
   - `RESUME`
   - `PROMOTE_BRANCH`
   - `ABANDON_BRANCH`
4. Output the final contents of `decision.json`.
5. Include concise evidence from the attached summary files.
6. Do not propose shell commands, code edits, or free-form plans outside the JSON.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.
