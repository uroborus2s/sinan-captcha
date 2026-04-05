---
name: training-judge
description: Judge one summarized trial under budget constraints and return decision.json using the fixed autonomous-training action set.
---

# Training Judge

Use this skill to turn one summarized trial into `decision.json`.

Inputs:

- `study.json`
- `result_summary.json`
- optional `leaderboard.json`
- optional `decisions.jsonl`

Workflow:

1. Read the trial summary and current study budget context.
2. Decide one action from the fixed action set:
   - `RETUNE`
   - `REGENERATE_DATA`
   - `RESUME`
   - `PROMOTE_BRANCH`
   - `ABANDON_BRANCH`
3. Include concise evidence grounded in the attached files.
4. Keep the action aligned with budget pressure and trend.

Boundaries:

- Do not ask for shell access.
- Do not propose free-form plans.
- Return JSON only.
