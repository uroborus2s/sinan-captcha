---
name: training-judge
description: Use when a command or agent needs to judge one summarized trial and return decision.json using the allowed action set only.
---

# Training Judge

Use this skill to turn one `result_summary.json` into `decision.json`.

Inputs:

- `study.json`
- `result_summary.json`
- optional `leaderboard.json`
- optional `decisions.jsonl`

Rules:

1. Choose exactly one action from:
   - `RETUNE`
   - `REGENERATE_DATA`
   - `RESUME`
   - `PROMOTE_BRANCH`
   - `ABANDON_BRANCH`
2. Base the judgment only on attached structured artifacts.
3. Include short evidence grounded in metrics, trend, weak classes, failure patterns, or budget pressure.
4. Keep `next_action` machine-readable and concise.

Boundaries:

- Do not run shell commands.
- Do not ask for more context beyond attached files.
- Return JSON only.
- The final output must be a single `decision.json` object.
