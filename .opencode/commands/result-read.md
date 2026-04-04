---
description: Read trial artifacts and return result_summary.json
agent: plan
subtask: true
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`
- `trial_id`: `$3`
- `primary_metric`: `$4`

Required attached files:

- `test.json`

Optional attached files:

- `evaluate.json`
- `best_trial.json`
- `recent result_summary.json`

Task:

0. Load and follow the local `result-reader` skill.
1. Read only the attached files.
2. Compress the current trial into the final contents of `result_summary.json`.
3. Keep only decision-critical fields: primary metric, key test/evaluation metrics, weak classes, failure patterns, recent trials, best trial, and evidence.
4. If an attached file is missing, use `null`, `{}`, or `[]` rather than inventing data.
5. Do not ask for shell access or attempt to run training commands.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.
