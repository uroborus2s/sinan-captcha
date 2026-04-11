---
name: dataset-planner
description: Use when a command or agent needs to turn weak classes and failure patterns into dataset_plan.json, including generator preset and generator override hints, without choosing training hyperparameters.
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
3. When a new dataset version is needed, choose a generator preset and only the minimal generator controls needed for data difficulty:
   - `project.sample_count`
   - `sampling.target_count_*`
   - `sampling.distractor_count_*`
   - `effects.common.*`
   - `effects.click.*`
   - `effects.slide.*`
4. Focus only on data strategy: class boosts, failure-pattern focus, generator controls, edge cases, and rationale.
5. Do not choose training hyperparameters here.

Boundaries:

- Do not run shell commands.
- Do not suggest model execution steps.
- Return JSON only.
- The final output must be a single `dataset_plan.json` object.
