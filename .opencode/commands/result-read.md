---
description: Read trial artifacts and return result_summary.json
agent: build
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`
- `trial_id`: `$3`
- `dataset_version`: `$4`
- `train_name`: `$5`
- `primary_metric`: `$6`

Required attached files:

- `test.json`

Optional attached files:

- `evaluate.json`
- `best_trial.json`
- `recent result_summary.json`

Task:

0. Load the local `result-reader` skill using the `skill` tool with exact name `result-reader`.
1. Read only the attached files.
2. Compress the current trial into the final contents of `result_summary.json`.
3. Echo `study_name`, `task`, `trial_id`, `dataset_version`, `train_name`, and `primary_metric` exactly from the arguments above.
4. Keep only decision-critical fields: primary metric, key test/evaluation metrics, weak classes, failure patterns, recent trials, best trial, and evidence.
5. If an attached file is missing, use `null`, `{}`, or `[]` rather than inventing data.
6. Do not ask for shell access or attempt to run training commands.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.

Example JSON output string:

{"study_name":"study_group1_llm","task":"group1","trial_id":"trial_0002","dataset_version":"firstpass_r0002","train_name":"trial_0002","primary_metric":"map50_95","primary_score":0.0,"test_metrics":{"single_target_hit_rate":0.82,"full_sequence_hit_rate":0.79,"mean_center_error_px":0.70,"order_error_rate":0.41},"evaluation_available":true,"evaluation_metrics":{"single_target_hit_rate":0.82,"full_sequence_hit_rate":0.79,"mean_center_error_px":0.70,"order_error_rate":0.41},"failure_count":7,"trend":"baseline","delta_vs_previous":null,"delta_vs_best":null,"weak_classes":[],"failure_patterns":["order_errors","sequence_consistency"],"recent_trials":[],"best_trial":null,"evidence":["recent_window=1","failure_patterns=order_errors, sequence_consistency"]}
