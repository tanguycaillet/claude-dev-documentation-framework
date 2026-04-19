---
id: REQ-0003
title: "Monthly reading stats dashboard"
status: verified
source: "User conversation 2026-04-10"
owner: alex
date: 2026-04-10
implemented_by:
  plan: PLAN-0002
  adrs: [ADR-0007, ADR-0008]
  tasks_in: TASKS.md
verified_on: 2026-04-15
superseded_by: null
---

## User Need

"I want to see how much I'm actually reading each month so I can track whether I'm keeping up with my reading goal."

The user keeps a reading goal of 24 books / year and currently has no way to see at a glance whether they're on track. They check in maybe once a week and want the answer in under 5 seconds of opening the app.

## Scope

**What's in:**
- Monthly bar chart of pages read for the selected year
- Year dropdown (default: current year)
- Empty state when no books finished in the selected year
- Renders correctly on mobile (375px-wide viewport)

**What's out (non-goals):**
- Social features / public profiles
- Real-time updates (daily refresh is fine)
- Custom date ranges beyond "by year"
- Year-over-year comparison (deferred to future REQ per user request during plan review)
- Pages-per-day breakdown (deferred)

## Acceptance Criteria

Each criterion is testable. Implementation is complete only when all pass.

- [x] Dashboard renders a bar chart of pages read per month for the current year
- [x] User can switch year via dropdown; chart updates without full page reload
- [x] Chart updates within 5 seconds of marking a book as finished (verified via end-to-end test)
- [x] Empty state shown when no books finished yet in the selected year
- [x] Chart is legible on a 375px-wide mobile viewport (verified with real device)

## Open Questions

Resolved during PLAN-0002 review:

- ~~Should partially read books count proportionally, or only on completion?~~ → Only on completion. Partial counting is a future enhancement.
- ~~Should we bucket by the day the user finished, or the day the app learned they finished?~~ → By the day the user finished, in the user's timezone (this question later turned out to be the source of SCN-0007; see [reactive pipeline example](../reactive-pipeline-timezone-bug/)).
