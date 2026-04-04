---
name: study-archivist
description: Use when a command or agent needs to summarize study state into study_status.json or archive advice from study and leaderboard artifacts.
---

# Study Archivist

Use this skill to summarize study-level state into `study_status.json`.

Inputs:

- `study.json`
- `leaderboard.json`
- optional `best_trial.json`
- optional `decisions.jsonl`

Workflow:

1. Summarize current status, current trial, best trial, budget pressure, and next human-readable actions.
2. Prefer concise machine-readable fields plus short Chinese summary text where needed.
3. Keep the output grounded in the attached study artifacts only.

Boundaries:

- Do not run shell commands.
- Do not invent missing study state.
- Return JSON only.
- The final output must be a single `study_status.json` object.
