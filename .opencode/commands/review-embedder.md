---
description: Review group1 icon-embedder progress and return embedder_review.json
agent: build
---

Read the attached files for:

- `study_name`: `$1`
- `task`: `$2`
- `trial_id`: `$3`
- `stage`: `$4`
- `epoch`: `$5`

Required attached files:

- `embedder_review_context.json`

Optional attached files:

- `embedder_review_history.jsonl`

Task:

1. Use the inlined local `embedder-judge` guidance included below.
2. Read the current embedder review context and any prior review history.
3. Decide the next action using only the allowed action set for the current stage:
   - `TRAIN_EMBEDDER_BASE`
     - `CONTINUE`
     - `STOP_AND_ADVANCE`
   - `TRAIN_EMBEDDER_HARD`
     - `CONTINUE`
     - `STOP_AND_ADVANCE`
     - `REBUILD_HARDSET`
     - `ESCALATE_DETECTOR`
4. Keep `next_action` machine-readable and concise.
5. Ground the evidence in attached structured metrics only.
6. Do not propose shell commands, code edits, or free-form plans outside the JSON.
7. For `TRAIN_EMBEDDER_BASE`, if `epoch >= 20` and exact retrieval is still weak while rank remains poor, prefer `STOP_AND_ADVANCE` even when the latest window shows small gains:
   - weak exact retrieval: `embedding_recall_at_1 <= 0.10`
   - rank remains poor: `embedding_positive_rank_mean >= 20`
   - identity gap is still large: `embedding_identity_recall_at_1 >= embedding_recall_at_1 + 0.25`

Return only one JSON object.
No markdown fences.
No prose before or after the JSON.

Example JSON output string:

{"decision":"STOP_AND_ADVANCE","reason":"base_plateau_identity_gap","confidence":0.82,"next_action":{"train_action":"stop_and_advance","target_stage":"EMBEDDER_GATE"},"evidence":["embedding_recall_at_1=0.047000","embedding_identity_recall_at_1=0.934000","embedding_positive_rank_mean=35.800000","recent_window=plateau"]}
