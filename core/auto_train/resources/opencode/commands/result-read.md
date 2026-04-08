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

1. Use the inlined local `result-reader` guidance included below.
2. Read the test and evaluation artifacts.
3. Echo `study_name`, `task`, `trial_id`, `dataset_version`, `train_name`, and `primary_metric` exactly from the arguments above.
4. Produce the final contents of `result_summary.json`.
5. Keep the output concise, structured, and grounded in the attached files.
6. Do not ask for shell access or return prose outside the JSON object.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.

Example JSON output string:

{"study_name":"study_group1_llm","task":"group1","trial_id":"trial_0002","dataset_version":"study_group1_llm_trial_0002","train_name":"trial_0002","primary_metric":"map50_95","primary_score":0.0,"test_metrics":{"single_target_hit_rate":0.82,"full_sequence_hit_rate":0.79,"mean_center_error_px":0.70,"order_error_rate":0.41},"evaluation_available":true,"evaluation_metrics":{"single_target_hit_rate":0.82,"full_sequence_hit_rate":0.79,"mean_center_error_px":0.70,"order_error_rate":0.41},"failure_count":7,"trend":"baseline","delta_vs_previous":null,"delta_vs_best":null,"weak_classes":[],"failure_patterns":["order_errors","sequence_consistency"],"recent_trials":[],"best_trial":null,"evidence":["recent_window=1","failure_patterns=order_errors, sequence_consistency"]}
