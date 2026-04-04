---
name: dataset-planner
description: Use when a command or agent needs to turn weak classes and failure patterns into dataset_plan.json without choosing training parameters.
---

# Dataset Planner

Use this skill to create `dataset_plan.json` from summarized trial weaknesses.

Inputs:

- `result_summary.json`
- optional `leaderboard.json`
- optional `best_trial.json`

Workflow:

1. Read weak classes, failure patterns, trend, and recent context.
2. Decide whether the next dataset action should reuse the current version or create a new version.
3. Focus only on data strategy: class boosts, failure-pattern focus, edge cases, and rationale.
4. Do not choose training hyperparameters here.

Boundaries:

- Do not run shell commands.
- Do not suggest model execution steps.
- Return JSON only.
- The final output must be a single `dataset_plan.json` object.
