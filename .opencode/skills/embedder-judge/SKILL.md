---
name: embedder-judge
description: Use when a command or agent needs to review group1 icon-embedder progress and return embedder_review.json using the stage-scoped action set only.
---

# Embedder Judge

Use this skill to turn one `embedder_review_context.json` into `embedder_review.json`.

Inputs:

- `embedder_review_context.json`
- optional `embedder_review_history.jsonl`

Rules:

1. Choose exactly one action from the allowed set for the current stage.
2. Base the judgment only on attached structured artifacts.
3. Prefer early strategy changes when exact retrieval has plateaued but identity retrieval is already much higher.
4. For `TRAIN_EMBEDDER_BASE`, if `epoch >= 20` and:
   - `embedding_recall_at_1 <= 0.10`
   - `embedding_positive_rank_mean >= 20`
   - `embedding_identity_recall_at_1 >= embedding_recall_at_1 + 0.25`
   then prefer `STOP_AND_ADVANCE` even if the latest review window still shows small exact-recall gains.
5. For `TRAIN_EMBEDDER_HARD`, prefer:
   - `REBUILD_HARDSET` when same-template confusion dominates and rebuild budget remains.
   - `ESCALATE_DETECTOR` when scene-target / false-positive errors dominate.
   - `STOP_AND_ADVANCE` when hard-stage gains have flattened without a clearer corrective action.
6. Keep `next_action` machine-readable and concise.

Boundaries:

- Do not run shell commands.
- Do not ask for more context beyond attached files.
- Return JSON only.
- The final output must be a single `embedder_review.json` object.
