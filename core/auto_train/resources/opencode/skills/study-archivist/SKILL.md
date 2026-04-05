---
name: study-archivist
description: Summarize study.json and leaderboard context into study_status.json for human review.
---

# Study Archivist

Use this skill to summarize the current study state into `study_status.json`.

Inputs:

- `study.json`
- `leaderboard.json`
- optional `best_trial.json`
- optional `decisions.jsonl`

Workflow:

1. Read current study metadata and budget.
2. Read leaderboard trend and best-trial context.
3. Produce a concise Chinese summary, next-action hints, and supporting evidence.

Boundaries:

- Do not ask for shell access.
- Do not return prose outside the JSON object.
- Return JSON only.
