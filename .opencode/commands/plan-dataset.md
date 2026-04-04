---
description: Plan the next dataset action and return dataset_plan.json
agent: plan
subtask: true
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`
- `trial_id`: `$3`

Required attached files:

- `result_summary.json`

Optional attached files:

- `leaderboard.json`
- `best_trial.json`

Task:

1. Load and follow the local `dataset-planner` skill.
2. Read the summarized weak classes, failure patterns, and trend.
3. Produce the final contents of `dataset_plan.json` for the next dataset action.
4. Keep the plan constrained to data strategy only: class boosts, failure-pattern focus, reuse vs new version, and a short rationale.
5. Do not return training parameters here.
6. Do not ask for shell access or propose free-form text outside the JSON object.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.
