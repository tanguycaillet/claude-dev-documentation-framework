---
id: PLAN-0002
title: "Reading Stats Pipeline"
status: accepted
date: 2026-04-10
addresses: [REQ-0003]
spawns_adrs: [ADR-0007, ADR-0008]
spawns_tasks:
  - "Build monthly-pages SQL view"
  - "Wire /stats/monthly API endpoint"
  - "Reading stats dashboard component"
  - "Chart.js integration"
accepted_by: alex
accepted_on: 2026-04-10
superseded_by: null
---

## Summary

Add a pre-aggregated SQL view over the `books` table that computes pages-read-per-month-per-user. Expose it through a `GET /stats/monthly` endpoint. Render it as a Chart.js bar chart inside a new `StatsDashboard` React component that's added to the app's main nav.

## Architecture

```
┌────────────┐   ┌──────────────┐   ┌───────────┐   ┌───────────────┐
│  books     │──▶│ monthly_view │──▶│  /stats/  │──▶│ StatsDashboard│
│  (table)   │   │  (SQL view)  │   │  monthly  │   │ (Chart.js)    │
└────────────┘   └──────────────┘   └───────────┘   └───────────────┘
     ▲                  ▲                 ▲
     │                  │                 │
   writes           triggers          auth'd GET
 on book edit     on books write       returns JSON
```

The flow is: user marks a book as finished → `books` row written → trigger invalidates the view row for the affected month → next API call returns fresh data → dashboard re-renders.

## Key Decisions (each becomes an ADR)

- **D1: SQL view vs. compute-on-read** → [ADR-0007](ADR-0007-sql-view-for-monthly-aggregation.md)
- **D2: Chart.js vs. Recharts vs. D3** → [ADR-0008](ADR-0008-chart-library-choice.md)

## Alternatives Considered (high-level)

Detailed alternatives live in the individual ADRs. At the plan level, we considered and rejected:

- **Materialized view with periodic refresh job.** The dataset is small enough (hundreds of books per user, not millions) that the complexity of a refresh job isn't justified. A regular view with triggers is enough.
- **Client-side aggregation from the full book list.** Doesn't scale past ~500 books, and pushes date-bucketing logic to the client where timezone handling is fragile. Rejected.

## Risks & Mitigations

- **View becomes stale if a book edit path misses the trigger** → integration test hits all three mutation paths (add / edit / delete) and verifies view is updated
- **Chart.js bundle size on mobile** → import only the bar-chart module, not the full Chart.js bundle (saves ~80kB)
- **Empty state looks broken** → design review before shipping; copy is "No books finished in 2026 yet — pick one up!"

## User Acceptance

Reviewed: 2026-04-10 by alex
Decision: **Accepted with note.**

Notes from review: Alex asked for a year-over-year comparison view showing 2025 vs 2026 side-by-side. Decided to defer that to a future REQ (logged as REQ-0004, status `proposed`) rather than expand this plan's scope. Core monthly-stats implementation proceeds unchanged.
