# TASKS.md — excerpt for REQ-0003 / PLAN-0002

> This is a representative excerpt showing how the Reading Stats feature
> appears in TASKS.md at various stages. Not the full file.

---

## In Progress

- [~] **Build monthly-pages SQL view** (ADR-0007 ← PLAN-0002 ← REQ-0003) — started 2026-04-10
  - [x] View definition with timezone-aware `DATE_TRUNC`
  - [x] `AFTER INSERT OR UPDATE OR DELETE` trigger on `books`
  - [x] Integration test: add / edit / delete books, assert view freshness
  - [ ] Migration review — confirm forward-only, no DROP statements

## Done

- [x] **Wire /stats/monthly API endpoint** (ADR-0007 ← PLAN-0002 ← REQ-0003) — 2026-04-12
  - [x] `GET /stats/monthly?year=YYYY` endpoint
  - [x] Auth guard — returns only the requesting user's data
  - [x] Returns `[]` (not 404) when no books finished in the year
  - [x] test_req_0003_api.ts: four cases (normal, empty year, different user isolation, invalid year param)

- [x] **Store finished_at timezone correctly** (ADR-0012 ← SCN-0007) — 2026-04-13
  - [x] Add `timezone` column to `users` table (migration 0041)
  - [x] Update SQL view to use `AT TIME ZONE user_timezone` before `DATE_TRUNC`
  - [x] Backfill: set `timezone = 'UTC'` for existing users
  - [x] test_req_0003_timezone.ts: user in UTC+9, book finished at 23:00 local → appears in correct local month

## Todo

- [ ] **Reading stats dashboard component** (ADR-0008 ← PLAN-0002 ← REQ-0003)
  - [ ] `MonthlyBarChart.tsx` component (Chart.js bar, tree-shaken import)
  - [ ] `StatsDashboard.tsx` wrapper with year dropdown
  - [ ] Empty state: "No books finished in {year} yet"
  - [ ] test_req_0003_ui.ts: renders chart, renders empty state, year switch updates chart

- [ ] **Chart.js integration** (ADR-0008 ← PLAN-0002 ← REQ-0003)
  - [ ] `npm install chart.js react-chartjs-2` — pin to Chart.js ^4.x
  - [ ] Register only: BarElement, CategoryScale, LinearScale, Tooltip
  - [ ] Verify bundle delta ≤ 40kB gzipped

---

## Reading the arrow notation

`(ADR-0007 ← PLAN-0002 ← REQ-0003)` means:

- This task exists because of **ADR-0007** (which made the specific technical decision)
- That ADR was prompted by **PLAN-0002** (which proposed the overall approach)
- That plan addresses **REQ-0003** (which captured the user's original need)

Follow those IDs to their files and the full reasoning is there.

Note also: **`(ADR-0012 ← SCN-0007)`** — that task came from a bug discovered
mid-implementation. It used the Reactive Pipeline, not the Forward Pipeline,
but it still lands in the same TASKS.md and still carries a traceable chain.
See the [reactive pipeline example](../reactive-pipeline-timezone-bug/) for
the full story on that one.
