# Example: Forward Pipeline — Reading Stats Dashboard

A complete worked example of the Forward Pipeline, from user request to
verified delivery. All artifacts are fictional but internally consistent.

## The story

Alex is building Bookshelf, a personal reading tracker. During a conversation
with their AI assistant, Alex says:

> "I want to see how much I'm actually reading each month so I can track
> whether I'm keeping up with my reading goal."

The assistant follows the Forward Pipeline.

## Stage-by-stage

1. **Capture the requirement** — The assistant drafts [`REQ-0003`](REQ-0003-monthly-stats-dashboard.md) with the user need, scope, and five testable acceptance criteria. Alex reviews and accepts.

2. **Propose the plan** — The assistant drafts [`PLAN-0002`](PLAN-0002-reading-stats-pipeline.md): a SQL view pre-aggregates pages per month, an API endpoint serves the data, a Chart.js component renders the dashboard. Two key decisions are called out for ADRs. Alex accepts with one note ("add year-over-year comparison later"), which gets logged as a future REQ rather than expanded into this plan.

3. **Decompose into ADRs and tasks** — The assistant writes two ADRs, both triggered by PLAN-0002:
   - [`ADR-0007`](ADR-0007-sql-view-for-monthly-aggregation.md) — why a SQL view over computing on read
   - [`ADR-0008`](ADR-0008-chart-library-choice.md) — why Chart.js over Recharts or D3

   Matching entries go into [`TASKS-excerpt.md`](TASKS-excerpt.md) with the full chain notation `(ADR ← PLAN ← REQ)`.

4. **Implement with tests tied to the REQ** — Not shown in the example files (that would be code), but every test file is named `test_req_0003_*.ts` and sub-tasks get checked off in TASKS.md as work progresses.

5. **Verify** — Alex and the assistant walk through REQ-0003's five acceptance criteria together. All green. REQ-0003 status flips to `verified`.

## What to look for

- **Bi-directional navigation.** From REQ-0003 you can walk forward to see everything built for it. From any ADR you can walk backward via `triggered_by` to understand why it exists.
- **No decision is lost.** The Chart.js vs D3 question is permanently documented in ADR-0008, with alternatives. Six months from now, if someone asks "should we switch to Recharts?", the answer starts by reading ADR-0008.
- **The PLAN is a user-accepted artifact.** Notice the "User Acceptance" section in PLAN-0002 — this is the formal record of "we discussed this approach and agreed."

## Files in this example

| File | What it is |
|---|---|
| `REQ-0003-monthly-stats-dashboard.md` | The requirement |
| `PLAN-0002-reading-stats-pipeline.md` | The accepted plan |
| `ADR-0007-sql-view-for-monthly-aggregation.md` | Decision 1 from the plan |
| `ADR-0008-chart-library-choice.md` | Decision 2 from the plan |
| `TASKS-excerpt.md` | How these artifacts appear in TASKS.md |
