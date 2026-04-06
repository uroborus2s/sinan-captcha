---
description: Plan the next dataset action and return dataset_plan.json
agent: build
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

1. Use the inlined local `dataset-planner` guidance included below.
2. Read the summarized weak classes, failure patterns, and trend.
3. Produce the final contents of `dataset_plan.json` for the next dataset action.
4. Keep the plan constrained to data strategy only: class boosts, failure-pattern focus, reuse vs new version, generator preset selection, and generator override fields for `sample_count`, `sampling`, and `effects`.
5. Do not return training hyperparameters here.
6. Do not ask for shell access or propose free-form text outside the JSON object.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.

Example JSON output string:

{"study_name":"study_group1_llm","task":"group1","trial_id":"trial_0002","dataset_action":"new_version","generator_preset":"hard","generator_overrides":{"project":{"sample_count":340},"sampling":{"target_count_min":2,"target_count_max":4,"distractor_count_min":5,"distractor_count_max":8},"effects":{"common":{"scene_veil_strength":1.45,"background_blur_radius_min":1,"background_blur_radius_max":2},"click":{"icon_shadow_alpha_min":0.28,"icon_shadow_alpha_max":0.36,"icon_shadow_offset_x_min":2,"icon_shadow_offset_x_max":3,"icon_shadow_offset_y_min":3,"icon_shadow_offset_y_max":4,"icon_edge_blur_radius_min":1,"icon_edge_blur_radius_max":2}}},"boost_classes":[],"focus_failure_patterns":["order_errors","sequence_consistency"],"rationale_cn":"本轮建议新建数据版本，重点围绕顺序错误和序列一致性扩充样本。","evidence":["decision=REGENERATE_DATA","dataset_action=new_version","trend=baseline"]}
