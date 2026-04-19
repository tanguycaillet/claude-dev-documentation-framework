---
id: SCN-0007
title: "finished_at Timezone — Books Appearing in Wrong Month"
category: scenarios
status: resolved
discovered: 2026-04-12
resolved_by: ADR-0012
related_req: REQ-0003
tags: [bug, timezone, stats, sql-view]
last_updated: 2026-04-13
---

# finished_at Timezone — Books Appearing in Wrong Month

## What Happened

During testing of the reading stats dashboard (REQ-0003), a book marked as
finished at **11:15 PM on March 31** appeared in the **April** bar on the chart
instead of March.

Steps to reproduce:
1. Set system timezone to Asia/Tokyo (UTC+9)
2. Mark any book as finished at 23:15 local time on the last day of any month
3. Open the stats dashboard
4. Observe: the book counts in the following month, not the current one

**Impact:** Any user in a timezone ahead of UTC will see books near month
boundaries bucketed into the wrong month. UTC users are unaffected. Users
behind UTC (e.g. UTC-5) see the inverse issue: a book finished in the early
hours of the 1st may appear in the previous month.

First noticed during local testing. Not yet in production (caught during
REQ-0003 implementation).

## Root Cause

The `monthly_reading_stats` SQL view (introduced by ADR-0007) aggregates
with:

```sql
DATE_TRUNC('month', finished_at)
```

`finished_at` is stored as UTC (correct). But `DATE_TRUNC` operates on the
raw UTC value — it does not know about the user's timezone. So a book
finished at `2026-03-31 23:15:00 JST` is stored as `2026-03-31 14:15:00 UTC`
and correctly assigned to March.

However, a book finished at `2026-04-01 00:30:00 JST` is stored as
`2026-03-31 15:30:00 UTC` — still March in UTC, but April in the user's
local time. The view buckets it into March, which is wrong from the user's
perspective.

The root cause is bucketing calendar months from UTC rather than from the
user's local timezone. This was flagged as an Open Question in REQ-0003
("should we bucket by the day the user finished, or the day the app learned
they finished?") but the timezone dimension wasn't handled in the initial
view definition.

## Fix

See [ADR-0012](../../forward-pipeline-bookshelf-stats/ADR-0007-sql-view-for-monthly-aggregation.md).

Concretely: the SQL view is updated to convert `finished_at` to the user's
stored timezone before truncating to month:

```sql
DATE_TRUNC('month', finished_at AT TIME ZONE u.timezone)
```

This requires a `timezone` column on the `users` table, backfilled to `'UTC'`
for existing users.

## Lesson

**Any aggregation that buckets timestamps into calendar units (day, week,
month, year) must happen AFTER converting to the user's local timezone.**

UTC is the correct format for *storing* timestamps — it handles ordering,
comparisons, and future timezone changes cleanly. It is almost never correct
for *displaying or bucketing* timestamps into human calendar units.

The pattern to remember:

```sql
-- Wrong: buckets in UTC
DATE_TRUNC('month', event_at)

-- Right: buckets in user's timezone
DATE_TRUNC('month', event_at AT TIME ZONE user_timezone)
```

This applies to any time-based grouping: daily active users, weekly
summaries, "how many X this month" — all of it.
