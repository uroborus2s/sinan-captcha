---
name: result-reader
description: Summarize one trial's test and evaluation artifacts into result_summary.json for downstream judge and dataset planning.
---

# Result Reader

Use this skill to compress one trial's test and evaluation artifacts into `result_summary.json`.

Inputs:

- `test.json`
- optional `evaluate.json`
- optional `best_trial.json`
- optional previous `result_summary.json`

Workflow:

1. Read the primary test metrics and any available evaluation metrics.
2. Identify the primary score, weak classes, and failure patterns.
3. Compare against recent/best context when files are attached.
4. Produce a single structured `result_summary.json`.

Boundaries:

- Do not ask for shell access.
- Do not propose free-form plans.
- Return JSON only.
