# Example: Reactive Pipeline — Timezone Bug

A complete worked example of the Reactive Pipeline, from bug discovery to
resolution. All artifacts are fictional but internally consistent, and link
back to the Forward Pipeline example (the timezone bug was discovered during
the REQ-0003 implementation).

## The story

Alex is mid-way through implementing the Reading Stats Dashboard (REQ-0003).
While testing, they mark a book as finished at 11:15 PM on March 31st. The
next morning, the stats chart shows that book counted in **April**, not March.

The AI assistant follows the Reactive Pipeline — no code touched until the
scenario is documented.

## Stage-by-stage

1. **Discover** — The assistant opens [`SCN-0007`](SCN-0007-finished-date-timezone.md) immediately: symptom described, `status: open`, `resolved_by: null`, `related_req: REQ-0003`. Three sentences. Committed.

2. **Investigate** — The assistant digs into the SQL view from ADR-0007. The `DATE_TRUNC('month', finished_at)` call operates on the raw UTC value. A book finished at 23:15 UTC+9 is stored as `14:15 UTC` — which is March 31 UTC, but the *user's* March 31 is fine. The bug surfaces for users whose local time crosses midnight at a different UTC time than the bucket boundary. SCN-0007 updated with root cause, `status: decision-pending`.

3. **Decide** — Alex and the assistant discuss two options:
   - A) Store `finished_at` in user-local time instead of UTC
   - B) Keep UTC storage, fix the bucketing to convert before truncating

   Option B wins because UTC storage is correct for ordering, sorting, and future timezone changes. The fix is in the view, not the data model. [`ADR-0012`](ADR-0012-timezone-aware-month-buckets.md) is written with `triggered_by: SCN-0007`.

4. **Queue** — A task is added to TASKS.md: `- [ ] Store finished_at timezone correctly (ADR-0012 ← SCN-0007)`. Sub-tasks: add `timezone` column to `users`, update the SQL view, backfill existing users to UTC.

5. **Close the scenario** — SCN-0007 updated: `status: resolved`, `resolved_by: ADR-0012`, Lesson filled in.

6. **Implement** — Task checked off. REQ-0003 implementation continues, now with correct timezone bucketing in the view from day one.

## What to look for

- **The scenario is written before any code.** Three sentences at first — enough to capture the symptom. It grows as investigation proceeds.
- **The fix decision involves a real trade-off** (UTC vs. local storage), and that trade-off is permanently recorded in ADR-0012. Nobody has to re-litigate this question.
- **The reactive chain links into the forward chain.** `ADR-0012 ← SCN-0007` sits in TASKS.md alongside `ADR-0007 ← PLAN-0002 ← REQ-0003`. Both chains are visible from a single file.
- **The scenario's `related_req: REQ-0003`** means someone reading REQ-0003 can trace to this bug and understand that the timezone question (which was in the Open Questions section of REQ-0003) became a real issue that required its own ADR.

## Files in this example

| File | What it is |
|---|---|
| `SCN-0007-finished-date-timezone.md` | The scenario (bug report + post-mortem) |
| `ADR-0012-timezone-aware-month-buckets.md` | The decision that resolved it |
| `TASKS-excerpt.md` | How the fix task appears in TASKS.md |
