---
description: Plan the next retune action and return retune_plan.json
agent: build
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`
- `trial_id`: `$3`

Required attached files:

- `result_summary.json`
- `trial_analysis.json`

Optional attached files:

- `leaderboard.json`
- `best_trial.json`

Task:

1. Use the inlined local `retune-planner` guidance included below.
2. Read the current metrics, current parameters, component diagnostics, and sampled error evidence.
3. Produce the final contents of `retune_plan.json`.
4. Only choose from these training hyperparameters:
   - `model`
   - `epochs`
   - `batch`
   - `imgsz`
5. For `group1`, you may also decide per-component `train|reuse` actions for:
   - `query-detector`
   - `proposal-detector`
   - `icon-embedder`
6. Do not propose shell commands, code edits, or free-form text outside the JSON object.

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.

Example JSON output string:

{"study_name":"study_group1_llm","task":"group1","trial_id":"trial_0004","parameter_updates":{},"component_actions":{"query-detector":"reuse","proposal-detector":"train","icon-embedder":"train"},"component_parameter_updates":{"proposal-detector":{"model":"yolo26s.pt","epochs":160,"batch":8,"imgsz":640},"icon-embedder":{"epochs":180,"batch":48,"imgsz":96}},"rationale_cn":"proposal 和 embedder 当前错误信号更强，继续定向调参。","evidence":["trend=plateau","proposal_detector_errors=precision_fp:3","embedder_alert=embedding_top1_error_scene_target_rate=0.180000"]}
