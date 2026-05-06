---
id: ADR-0012
title: "Convert to user timezone before month-bucketing in SQL view"
status: accepted
date: 2026-04-13
triggered_by: SCN-0007
implementation_tasks:
  - TASK-0001
supersedes: null
superseded_by: null
---

## Context

SCN-0007 identified that the `monthly_reading_stats` view buckets timestamps
using raw UTC, causing books finished near midnight to appear in the wrong
calendar month for users in non-UTC timezones.

The view currently contains:
```sql
DATE_TRUNC('month', finished_at) AS month
```

We need to decide how to fix the bucketing without changing the storage
format of `finished_at` (which is correctly UTC).

## Decision

Keep `finished_at` stored in UTC. Fix the bucketing in the SQL view by
converting to the user's stored timezone before truncating:

```sql
DATE_TRUNC('month', b.finished_at AT TIME ZONE u.timezone) AS month
```

This requires:
1. A `timezone` column on the `users` table (TEXT, IANA timezone name, e.g. `'Asia/Tokyo'`)
2. A default / backfill of `'UTC'` for existing users
3. The view to JOIN `users` to get the timezone for each book

## Consequences

**Positive:**
- Books always appear in the calendar month the user experienced them in, regardless of timezone
- UTC storage is preserved — ordering, cross-user comparisons, and audit logs remain correct
- The fix is entirely in the view definition; no data migration needed, no changes to write paths

**Negative:**
- The view now joins `users` — slightly more complex and marginally slower (negligible at current scale)
- Users who travel or change timezones will see historical books bucketed using their *current* timezone setting, not the timezone they were in when they finished the book. This is an accepted limitation — tracking per-book timezone at read time is over-engineering for this use case.
- `timezone` must be a valid IANA timezone name. We add a validation step on the settings form to prevent invalid values reaching the DB.

## Alternatives Considered

- **Store `finished_at` in user-local time instead of UTC:** Solves the bucketing problem but creates new problems — ordering across users becomes timezone-dependent, and if a user changes their timezone setting, historical `finished_at` values become ambiguous (did they mean that local time in the old timezone or the new one?). UTC storage is a well-established best practice. Rejected.

- **Store both UTC and local timestamps:** Redundant, and the "local" timestamp has the same ambiguity problem if the user changes timezones. Rejected.

- **Compute month bucket in the application layer (not SQL):** The API would fetch raw rows and group them in TypeScript. Moves the logic away from the DB, increases data transfer for large reading histories, and makes it harder to use SQL aggregates for future analytics. Rejected.

- **Store the user's timezone at the time of finishing each book (on the `books` row):** Correct in theory — captures the exact timezone context. But it adds a column that must be populated on every book-finish event, and it's unclear what to do for existing books that already have `finished_at` values without a stored timezone. Over-engineering for a personal reading tracker. Deferred as a possible v2 enhancement if the current approach proves insufficient.

## Implementation

- Migration `0041_add_users_timezone.sql`: add `timezone TEXT NOT NULL DEFAULT 'UTC'` to `users`
- Migration `0042_update_monthly_stats_view.sql`: rewrite view to JOIN `users` and use `AT TIME ZONE u.timezone`
- Settings form: add timezone selector (dropdown of IANA names); validate on server before writing to DB
- Backfill script (one-time): `UPDATE users SET timezone = 'UTC' WHERE timezone IS NULL` — runs as part of migration
- Test `test_req_0003_timezone.ts`: seed user with `timezone = 'Asia/Tokyo'`, finish book at 23:15 local on March 31, assert chart shows book in March, not April

### Code-level traceability

Inline markers to add at definition sites:

```sql
-- migrations/0042_update_monthly_stats_view.sql
-- ADR-0012 ← SCN-0007: bucket by user's local timezone, not UTC.
-- Storing finished_at as UTC remains correct — only the aggregation needs conversion.
CREATE OR REPLACE VIEW monthly_reading_stats AS
SELECT
  u.id AS user_id,
  DATE_TRUNC('month', b.finished_at AT TIME ZONE u.timezone) AS month,
  SUM(b.page_count) AS pages
FROM books b JOIN users u ON u.id = b.user_id
GROUP BY 1, 2;
```

```typescript
// src/components/Settings/TimezoneSelect.tsx
// ADR-0012: timezone is load-bearing for the stats view — validate IANA names server-side.
export function TimezoneSelect() { ... }
```

Expected commits (one per ADR):

```
fix(stats): bucket monthly stats in user timezone [ADR-0012 ← SCN-0007]

Resolves SCN-0007 where users near date boundaries saw books in the
wrong month. Adds users.timezone column, rewrites monthly_reading_stats
view to convert before DATE_TRUNC, and adds a timezone selector to
settings.
```

