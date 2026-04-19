# TASKS.md — excerpt for SCN-0007 / ADR-0012

> This excerpt shows how a bug-driven task appears in TASKS.md alongside
> the forward-pipeline tasks from the same feature sprint. Not the full file.

---

## In Progress

- [~] **Build monthly-pages SQL view** (ADR-0007 ← PLAN-0002 ← REQ-0003) — started 2026-04-10
  - [x] View definition (initial version — see Done below for timezone fix)
  - [x] Trigger on books table
  - [ ] Migration review

## Done

- [x] **Store finished_at timezone correctly** (ADR-0012 ← SCN-0007) — 2026-04-13
  - [x] Migration 0041: add `timezone TEXT NOT NULL DEFAULT 'UTC'` to `users`
  - [x] Migration 0042: rewrite view with `AT TIME ZONE u.timezone`
  - [x] Backfill: `UPDATE users SET timezone = 'UTC' WHERE timezone IS NULL`
  - [x] Settings form: timezone selector with IANA validation
  - [x] test_req_0003_timezone.ts: UTC+9 user, book at 23:15 on Mar 31 → appears in March ✓

---

## Reading the two chain types side by side

Both tasks are in the same `TASKS.md`. The notation tells you which pipeline
produced each task:

| Task | Chain | Pipeline |
|---|---|---|
| Build monthly-pages SQL view | `ADR-0007 ← PLAN-0002 ← REQ-0003` | Forward (new feature) |
| Store finished_at timezone correctly | `ADR-0012 ← SCN-0007` | Reactive (bug fix) |

The reactive task is shorter — two artifacts instead of three — because bugs
skip the PLAN stage. They go straight from symptom (SCN) to decision (ADR)
to implementation.

Both tasks are equally traceable. The only difference is the origin: one
started with a user need, the other started with an observed failure.
