---
name: result-reader
description: Use when a command or agent needs to compress test and evaluate artifacts into result_summary.json for one trial.
---

# Result Reader

Use this skill to turn structured trial artifacts into `result_summary.json`.

Inputs:

- `test.json`
- optional `evaluate.json`
- optional recent `result_summary.json`
- optional `best_trial.json`

Workflow:

1. Read only the attached files for the current trial.
2. Keep only decision-critical facts: primary metric, key test metrics, key evaluation metrics, weak classes, failure patterns, recent-trial context, best-trial context, and short evidence.
3. Prefer compact structured fields over narrative text.
4. If a file is missing, use `null`, `{}`, or `[]` instead of inventing values.

Boundaries:

- Do not run shell commands.
- Do not request training execution.
- Return JSON only.
- The final output must be a single `result_summary.json` object.
