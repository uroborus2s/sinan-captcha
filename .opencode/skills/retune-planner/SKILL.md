---
name: retune-planner
description: Use when a command or agent needs to turn current parameters, component errors, and failure evidence into retune_plan.json.
---

# Retune Planner

Use this skill to create `retune_plan.json` from structured trial diagnostics.

Inputs:

- `result_summary.json`
- `trial_analysis.json`
- optional `leaderboard.json`
- optional `best_trial.json`

Workflow:

1. Read the current metrics, current training parameters, and sampled error evidence.
2. Decide whether the next retune should stay global or target specific `group1` components.
3. Only choose training hyperparameters from:
   - `model`
   - `epochs`
   - `batch`
   - `imgsz`
4. For `group1`, you may set per-component `train|reuse` actions and per-component parameter updates.
5. Keep the plan machine-readable and directly applicable by the controller.

Boundaries:

- Do not run shell commands.
- Do not request more files beyond the attached structured artifacts.
- Return JSON only.
- The final output must be a single `retune_plan.json` object.
