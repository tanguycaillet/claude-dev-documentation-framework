---
name: Forward Pipeline is mandatory for new work
description: New features always go REQ → PLAN → ADR → TASKS → verify
type: feedback
---

Rule: When the user describes a new feature, capability, or behavior change,
do not begin implementation. Draft a REQ-NNNN first, then (after user
acceptance) a PLAN-NNNN, then ADRs, then TASKS.md entries.

Why: Jumping to code skips user validation of the outcome and skips
architectural review. Both cost far more to correct after the fact.

How to apply:
1. On any "can you build X" request, draft REQ-NNNN first
2. Get user acceptance before proposing a plan
3. Get user acceptance on the plan before writing ADRs
4. Only after ADRs + TASKS are in place, begin implementation

Exception: one-line edits or pure refactors may skip REQ/PLAN but still
need a TASKS.md entry.
