---
id: ADR-0007
title: "Monthly aggregation as a SQL view"
status: accepted
date: 2026-04-10
triggered_by: PLAN-0002
implementation_tasks:
  - TASK-0001
  - TASK-0002
supersedes: null
superseded_by: null
---

## Context

REQ-0003 requires a monthly bar chart of pages read. The `books` table has one row per book with a `finished_at` timestamp and a `page_count` integer. We need to aggregate those rows into per-user, per-month totals efficiently and correctly.

This is Decision D1 from PLAN-0002.

## Decision

Create a SQL view (`monthly_reading_stats`) that pre-aggregates page totals grouped by user and calendar month. Refresh the view row for the affected user whenever a book is written (via a `AFTER INSERT OR UPDATE OR DELETE` trigger on the `books` table).

## Consequences

**Positive:**
- Query for the dashboard is a simple `SELECT * FROM monthly_reading_stats WHERE user_id = ? AND year = ?` — fast and deterministic
- All aggregation logic lives in one place (the view definition); the API and component are pure consumers
- Trigger-based refresh means the view is always fresh within one write cycle

**Negative:**
- Trigger must cover all three mutation paths (INSERT / UPDATE / DELETE) — a missed path silently produces stale data. Mitigated by integration tests that exercise all three paths and assert view freshness.
- Adding new aggregation dimensions (e.g., genre breakdown) requires a view migration

## Alternatives Considered

- **Compute on read in the API:** `SELECT user_id, DATE_TRUNC('month', finished_at), SUM(page_count) FROM books WHERE user_id = ? GROUP BY 1, 2`. Correct, but runs a full table scan per request. Fine now with hundreds of books; problematic at thousands. Rejected on growth grounds.
- **Materialized view with a scheduled refresh job:** More robust for large datasets, but requires a background job scheduler (we don't have one), adds operational complexity, and introduces a refresh latency that makes the "update within 5 seconds" acceptance criterion in REQ-0003 harder to guarantee. Rejected as over-engineering for current scale.
- **In-memory cache in the API layer:** Would require cache invalidation logic duplicated from the trigger, and a cold-start rebuild on deploy. Rejected — more moving parts for no benefit over the view + trigger approach.

## Implementation

- Create migration `0042_add_monthly_reading_stats_view.sql` defining the view with `DATE_TRUNC('month', finished_at AT TIME ZONE user_timezone)` for correct bucketing (see SCN-0007 / ADR-0012 for why the timezone conversion is here)
- Create migration `0043_add_books_monthly_stats_trigger.sql` with `AFTER INSERT OR UPDATE OR DELETE` trigger
- Add `GET /stats/monthly?year=<YYYY>` endpoint returning `[{ month: "2026-01", pages: 312 }, ...]`
- Integration test: seed three books in different months, delete one, verify view reflects deletion within the same transaction

### Code-level traceability

Inline markers to add at definition sites:

```sql
-- migrations/0042_add_monthly_reading_stats_view.sql
-- ADR-0007: monthly aggregation lives in a SQL view, not the API layer.
CREATE VIEW monthly_reading_stats AS ...
```

```typescript
// src/api/stats.ts
// ADR-0007: view-backed; see docs/decisions/ADR-0007-sql-view-for-monthly-aggregation.md
export async function getMonthlyStats(userId: string, year: number) { ... }
```

Expected commits (one per ADR, chronologically):

```
feat(stats): add monthly_reading_stats SQL view + trigger [ADR-0007]
feat(stats): expose /stats/monthly endpoint [ADR-0007]
test(stats): verify view freshness across insert/update/delete [ADR-0007]
```

