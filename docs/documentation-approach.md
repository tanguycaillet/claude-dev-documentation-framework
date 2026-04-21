# Documentation & Decision Architecture for AI-Assisted Projects

A practical guide to keeping your project's knowledge organized so that an AI coding assistant (and future-you) can pick up where you left off — even weeks later, even in a fresh session.

---

## Why Bother?

Without structure, knowledge lives only in chat logs. Chat logs get compressed, sessions end, and you lose context. Four problems this solves:

1. **Continuity** — A new session can read your docs and understand the project in 30 seconds
2. **Decision memory** — You won't re-debate choices you already made (and won't accidentally undo them)
3. **Multi-agent safety** — If you fork sessions to work in parallel, they need a shared source of truth
4. **Traceability** — Every task can be traced back to the decision that caused it, every decision to the plan or scenario that triggered it, and every plan to the user requirement that motivated it

---

## The Artifact Catalog

Six artifact types, each with a sequential ID and strict cross-references. The IDs are what make the whole system navigable.

| Artifact | ID | Purpose | Location |
|---|---|---|---|
| Project instructions | — | Tell the assistant what this project is and how to work | `CLAUDE.md` |
| Progress tracker | — | Single source of truth for current work | `TASKS.md` |
| Requirement | `REQ-NNNN` | What the user needs + acceptance criteria | `docs/requirements/` |
| Plan | `PLAN-NNNN` | Proposed architecture/approach, user-accepted | `docs/plans/` |
| Decision | `ADR-NNNN` | Why we chose approach X over Y | `docs/decisions/` |
| Scenario | `SCN-NNNN` | Bug, incident, or debugging write-up | `docs/knowledge/scenarios/` |
| Knowledge article | — | Reference material, concepts, how-it-works | `docs/knowledge/` |

---

## The Three Pillars

### 1. `CLAUDE.md` — Project Instructions (checked into git)

This is the first file the AI assistant reads when it opens your project. Put in it:

- **What the project is** (1-2 paragraphs)
- **Tech stack** (language, framework, DB, key libraries)
- **Project structure** (directory tree with one-line descriptions)
- **How to run things** (build, test, start server, deploy)
- **Code conventions** (formatting, naming, testing rules)
- **Safety rules** (things that must never happen)
- **Environment variables** (list them with descriptions)
- **Pipeline reminders** — short paragraphs pointing to both the Forward Pipeline (new features) and Bug-to-Fix Pipeline (issues)

Keep it under 200 lines. If it grows beyond that, split details into `docs/`.

```markdown
# CLAUDE.md — Bookshelf

## What This Is
A personal reading tracker. Users log books they've read, are reading, or
want to read. Mobile-first web app.

## Running
\`\`\`bash
npm run dev
\`\`\`

## Code Style
- Use Prettier + ESLint (configs checked in)
- All functions must have type hints (TypeScript strict mode)
- Tests in tests/ using Vitest; each test file references the REQ-NNNN it verifies

## Safety Rules
1. Never commit .env files
2. Never log full user emails; hash or truncate
3. Migrations are forward-only — no DROP in prod

## Working Discipline
- New features: follow the Forward Pipeline (REQ → PLAN → ADR → TASKS → verify)
- Bugs / unexpected behavior: follow the Bug-to-Fix Pipeline (SCN → ADR → TASKS)
- Never implement without first creating the upstream artifacts
See docs/README.md for full pipeline protocols.
```

### 2. `TASKS.md` — Single Source of Truth for Progress

One file at the repo root. Every task references its upstream artifacts so you can always trace *why* a task exists.

```markdown
# TASKS.md

Legend: [x] done · [~] in progress · [ ] todo · [!] blocked

## In Progress
- [~] **Build monthly-pages SQL view** (ADR-0007 ← PLAN-0002 ← REQ-0003) — started 2026-04-10
  - [x] View definition for per-month aggregation
  - [x] Trigger to refresh on book edit
  - [ ] Integration test with seeded fixtures

## Done
- [x] **Store finished_at timezone correctly** (ADR-0012 ← SCN-0007) — 2026-04-13
- [x] **Initial project scaffold** (PLAN-0001 ← REQ-0001) — 2026-04-08

## Todo
- [ ] **Reading stats dashboard widget** (PLAN-0002 ← REQ-0003)
- [ ] **Chart.js integration** (ADR-0008 ← PLAN-0002 ← REQ-0003)
```

**Rules:**
- Update at every meaningful milestone (not every line of code, but every "unit of work")
- Convert relative dates to absolute ("Thursday" → "2026-04-10")
- **Every task references its full provenance chain** using `←` arrows
  - Forward pipeline: `(ADR-NNNN ← PLAN-NNNN ← REQ-NNNN)`
  - Reactive pipeline: `(ADR-NNNN ← SCN-NNNN)`
  - Pure trivial task: `(no upstream)` — should be rare
- If you fork sessions, each fork updates TASKS.md independently; main session consolidates on merge

### 3. `docs/` — Knowledge Base + All Records

```
docs/
├── README.md                # Both pipeline protocols, top of mind
├── architecture.md          # Module contracts — how components talk to each other
├── requirements/
│   ├── README.md
│   ├── REQ-0001-initial-scope.md
│   ├── REQ-0002-...md
│   └── ...
├── plans/
│   ├── README.md
│   ├── PLAN-0001-initial-scaffold.md
│   ├── PLAN-0002-reading-stats-pipeline.md
│   └── ...
├── decisions/
│   ├── README.md
│   ├── ADR-0001-choice-of-database.md
│   └── ...
└── knowledge/
    ├── README.md            # Format rules for articles
    ├── concepts/
    ├── data-sources/
    ├── models/
    └── scenarios/
        ├── SCN-0001-....md
        └── ...
```

---

## Requirements (`REQ-NNNN`)

A requirement captures **what** the user needs and **how we'll know it's done**. Not the design, not the code — the goal and the acceptance criteria.

### When to Write One

- Any new feature or capability the user asks for
- Any non-trivial behavior change that affects users
- Any refactor with user-visible impact

### Format

```markdown
---
id: REQ-0003
title: "Monthly reading stats dashboard"
status: accepted        # proposed | accepted | in-progress | verified | superseded
source: "User conversation 2026-04-10"
owner: alex
date: 2026-04-10
implemented_by:
  plan: PLAN-0002       # populated once a plan is accepted
  adrs: [ADR-0007, ADR-0008]
  tasks_in: TASKS.md
verified_on: null       # date when user signed off
---

## User Need
What the user is trying to accomplish. Written in the user's language.
"I want to see how much I'm actually reading each month so I can track
whether I'm keeping up with my reading goal."

## Scope
What's in:
- Monthly bar chart of pages read for the selected year
- Year dropdown
- Empty state when no books finished yet

What's out (non-goals):
- Social features / public profiles
- Real-time updates (daily refresh is fine)
- Custom date ranges beyond "by year"

## Acceptance Criteria
Each criterion is testable. Implementation is complete only when all pass.
- [ ] Dashboard renders a bar chart of pages read per month for current year
- [ ] User can switch year via dropdown
- [ ] Chart updates within 5 seconds of marking a book as finished
- [ ] Empty state shown when no books finished yet
- [ ] Chart is legible on a 375px-wide mobile viewport

## Open Questions
Things that need resolution before/during PLAN.
- Should partially read books count proportionally, or only on completion?
```

### Key Rules

- **Requirements are user-facing.** They describe outcomes, not designs. If you find yourself writing tech stack choices, move that to the PLAN.
- **Acceptance criteria are the contract.** Tests verify them. User acceptance closes them.
- **Status lifecycle:** `proposed` → `accepted` → `in-progress` (once PLAN is accepted) → `verified` (once user signs off) → optionally `superseded`
- **A REQ can't be marked `verified` without all acceptance criteria checked.**

---

## Plans (`PLAN-NNNN`)

A plan is **the assistant's proposed approach** to satisfying one or more requirements. It's the point where architecture gets proposed, discussed, and accepted as a batch.

### When to Write One

- Before implementing any new REQ (even small ones get a short plan — one paragraph is fine)
- When restructuring significant portions of the codebase
- When adopting a new external dependency, service, or framework

Think of a PLAN as a design review in document form. The user reviews it, pushes back or accepts, and on acceptance it spawns the concrete artifacts that drive implementation.

### Format

```markdown
---
id: PLAN-0002
title: "Reading Stats Pipeline"
status: accepted        # proposed | accepted | superseded
date: 2026-04-10
addresses: [REQ-0003]
spawns_adrs: [ADR-0007, ADR-0008]
spawns_tasks:
  - "Build monthly-pages SQL view"
  - "Chart.js integration"
  - "Reading stats dashboard widget"
accepted_by: alex
accepted_on: 2026-04-10
superseded_by: null
---

## Summary
One paragraph: what are we building and how?
"Add a pre-aggregated SQL view over the books table to compute pages-read-
per-month-per-user. Expose it through a GET /stats/monthly endpoint. Render
as a Chart.js bar chart inside a new StatsDashboard React component."

## Architecture
Diagram or narrative of component interactions. Keep it high-level;
details live in individual ADRs.

┌────────────┐   ┌──────────────┐   ┌──────────┐   ┌───────────────┐
│  books     │──▶│ monthly_view │──▶│  /stats/ │──▶│ StatsDashboard│
│  (table)   │   │  (SQL view)  │   │ monthly  │   │ (Chart.js)    │
└────────────┘   └──────────────┘   └──────────┘   └───────────────┘

## Key Decisions (each becomes an ADR)
- D1: SQL view vs. compute-on-read → ADR-0007
- D2: Chart.js vs. Recharts vs. D3 → ADR-0008

## Alternatives Considered (high-level)
Detailed alternatives go in individual ADRs.
- Materialized view with refresh job. Deferred — dataset too small to justify.
- Client-side aggregation. Rejected — doesn't scale past a few hundred books.

## Risks & Mitigations
- View becomes stale if book edits miss the trigger → integration test ensures
  trigger fires on all three mutation paths (add/edit/delete)
- Chart.js bundle size on mobile → import only the bar-chart module

## User Acceptance
Reviewed: 2026-04-10 by alex
Decision: Accepted with note — "add a year-over-year comparison in v2" (logged
as future REQ, not in scope for this plan)
```

### Key Rules

- **A plan can't be `accepted` until the user explicitly signs off** (captured in frontmatter + "User Acceptance" section)
- **Once accepted, all spawned ADRs must be written before implementation starts.** The PLAN promises decisions; the ADRs deliver them.
- **Small features still get a plan.** A one-paragraph Summary + three-line Architecture + one Decision is enough for small work. The ritual matters more than the length.
- **Plans are immutable once accepted.** If the approach changes materially, write PLAN-NNNN+1 with `supersedes`.

---

## Architectural Decision Records (ADRs)

An ADR captures **why** you made a technical choice. Not the code — the reasoning.

### When to Write One

- A decision called out inside an accepted PLAN (most common source)
- Resolving a SCN that required more than a mechanical fix
- Any standalone architectural choice (library, pattern, safety rule) that wasn't part of a larger plan
- Any decision you might question in 3 months

### Format

```markdown
---
id: ADR-0007
title: "Monthly aggregation as a SQL view"
status: accepted
date: 2026-04-10
triggered_by: PLAN-0002         # REQ-NNNN | PLAN-NNNN | SCN-NNNN | null
implementation_tasks:
  - "Build monthly-pages SQL view"
supersedes: null
superseded_by: null
---

## Context
What problem are we solving? What constraints exist?
If triggered by a scenario, summarize the symptom. If by a plan, reference
the relevant Key Decision line.

## Decision
What did we choose and why?

## Consequences
What are the trade-offs? What does this enable or prevent?

## Alternatives Considered
What else did we look at and why did we reject it?

## Implementation
Bullet list of concrete changes. These MUST match entries in TASKS.md.
```

### Key Rules

- **ADRs are immutable once accepted.** If you change your mind, write a NEW ADR with `supersedes`.
- **Number sequentially.** `ADR-0001`, `ADR-0002`, ...
- **Keep them short.** One page max. The value is in the decision + reasoning, not length.
- **Status values:** `proposed` → `accepted` → optionally `superseded`
- **An ADR's `triggered_by` field is mandatory** — even if the value is `null` (meaning: freestanding architectural choice).
- **An ADR can't be marked `accepted` until its `implementation_tasks` exist in TASKS.md.**

### Example

```markdown
---
id: ADR-0005
title: "Cursor-based pagination for the books catalog"
status: accepted
date: 2026-04-05
triggered_by: REQ-0002
implementation_tasks:
  - "Replace offset pagination with cursor on /books endpoint"
  - "Update client to consume cursor tokens"
---

## Context
The /books endpoint returns a growing catalog. Offset-based pagination is
showing duplicate and missing rows when users add books while browsing
(see REQ-0002 acceptance criterion "pagination is stable across inserts").

## Decision
Switch to cursor-based pagination using (created_at, id) as the opaque
cursor, base64-encoded.

## Consequences
- Stable results under concurrent inserts
- Constant-time query regardless of how deep the user has paginated
- Client code is slightly more complex (no more page numbers)
- "Jump to page N" is no longer supported — we accept this trade-off

## Alternatives Considered
- Keep offset with server-side snapshotting: rejected — memory cost grows with
  active users, and still doesn't help users who paginate across sessions
- Page tokens managed server-side: rejected — stateful, hard to scale

## Implementation
- Endpoint signature: `GET /books?cursor=<token>&limit=<n>` (default limit 20)
- Response includes `next_cursor` when more results exist, else null
- Client library exposes an async iterator that fetches pages lazily
```

---

## Knowledge Articles

For anything that isn't a decision but is important to understand. Each article has YAML frontmatter:

```markdown
---
title: How Our Book Import Pipeline Works
category: ingestion
tags: [import, isbn, open-library]
audience: developer
status: accepted
last_updated: 2026-04-12
---

# How Our Book Import Pipeline Works

[Content — explain the concept, show examples, link to code]
```

### Scenarios (`SCN-NNNN`) — Bug Reports, Post-Mortems, Incident Write-ups

The most valuable knowledge articles. When something interesting happens — a bug, a wrong result, a successful debug session — write it up. **Scenarios are the entry point of the Bug-to-Fix Pipeline.**

```markdown
---
id: SCN-0007
title: finished_at Timezone — Books Appearing in Wrong Month
category: scenarios
status: resolved            # open | investigating | decision-pending | resolved | wont-fix
discovered: 2026-04-12
resolved_by: ADR-0012       # null until decided; required to set status=resolved
related_req: REQ-0003       # optional — the REQ this bug occurred under
tags: [bug, timezone, stats]
last_updated: 2026-04-13
---

# finished_at Timezone — Books Appearing in Wrong Month

## What Happened
User in Japan (UTC+9) marked "Dune" as finished at 11:00 PM local time
on March 31. The book appeared in the April bucket on their stats dashboard
because our aggregation was bucketing by UTC date — and 11:00 PM JST is
14:00 UTC, but 00:30 JST on April 1 is 15:30 UTC on March 31, which meant
a book the user clearly finished "in March" showed up "in April".

## Root Cause
`finished_at` is stored correctly as a UTC timestamp. The monthly SQL view
(ADR-0007) groups by `DATE_TRUNC('month', finished_at)` without converting
to the user's timezone first. So users near a date boundary see books in
the wrong bucket.

## Fix
See ADR-0012. Implementation tracked in TASKS.md.

## Lesson
Any aggregation that buckets timestamps into calendar units (day, month,
year) must happen AFTER converting to the user's timezone. UTC is correct
for storage; it is almost never correct for display or bucketing.
```

### Scenario Lifecycle

| Status | Meaning |
|---|---|
| `open` | Just discovered. Symptom documented. Cause unknown. |
| `investigating` | Root cause analysis in progress. |
| `decision-pending` | Cause understood. Waiting for a fix decision (ADR). |
| `resolved` | ADR written, implementation queued or done. `resolved_by` populated. |
| `wont-fix` | Closed without action; reason in the article. |

A scenario cannot move to `resolved` without a `resolved_by: ADR-NNNN` field populated.

---

## The Full Development Lifecycle

Everything above connects through two complementary pipelines. Both end in TASKS.md, both use ADRs, both obey the same ID cross-referencing discipline.

```
 FORWARD PIPELINE (proactive, requirement-driven)
 ═══════════════════════════════════════════════════════════════════════════

  User need ─→ REQ-NNNN ─→ PLAN-NNNN ─→ ADR-NNNN (×N) ─→ TASKS.md ─→ code
                  ▲           │                             │          +
                  │           │                             │        tests
                  │           └── user accepts plan         │          │
                  │                                         │          ▼
                  └─── verify against ─── acceptance ───────┘    acceptance
                       criteria                                   criteria
                                                                       │
                                                                       ▼
                                                              REQ: verified


 REACTIVE PIPELINE (bug-driven)
 ═══════════════════════════════════════════════════════════════════════════

  Observed issue ─→ SCN-NNNN ─→ ADR-NNNN ─→ TASKS.md ─→ fix ─→ SCN: resolved
                                (if non-
                                 trivial)
```

The Forward Pipeline is how features get built. The Reactive Pipeline is how problems get solved. They share infrastructure (ADRs, TASKS.md) and together cover every kind of change the project undergoes.

### Forward Pipeline — The Protocol

**Stage 1 — Capture the requirement.**

1. User expresses a need (could be casual: "it'd be nice if...")
2. The assistant drafts `REQ-NNNN` with the User Need, Scope, Acceptance Criteria
3. User reviews and accepts (status: `proposed` → `accepted`)
4. Commit. No implementation discussion yet.

**Stage 2 — Propose the plan.**

5. The assistant drafts `PLAN-NNNN` with Summary, Architecture, Key Decisions, Alternatives, Risks
6. Set `addresses: [REQ-NNNN]`
7. User reviews. Push back, iterate, or accept.
8. On acceptance: set `status: accepted`, fill in `accepted_by` and `accepted_on`
9. Commit.

**Stage 3 — Decompose into ADRs and tasks.**

10. For each Key Decision in the plan, write an ADR with `triggered_by: PLAN-NNNN`
11. In each ADR, list `implementation_tasks`
12. Add matching entries to TASKS.md with full chain: `(ADR-NNNN ← PLAN-NNNN ← REQ-NNNN)`
13. Mark ADRs `accepted`, update PLAN frontmatter with `spawns_adrs: [...]` and `spawns_tasks: [...]`
14. Flip REQ status to `in-progress`

**Stage 4 — Implement with tests tied to the REQ.**

15. Work through TASKS.md, checking off sub-tasks
16. Each test file or test case references the REQ it verifies (in docstring or test marker)
17. If a mid-implementation decision is needed, write a new ADR (`triggered_by: PLAN-NNNN` or the task)
18. If a bug or unexpected behavior appears, flip to the Reactive Pipeline with a SCN

**Stage 5 — Verify against acceptance criteria.**

19. Run through REQ-NNNN's Acceptance Criteria checklist with the user
20. Each criterion: test passing + user confirmation
21. When all checked: REQ status → `verified`, populate `verified_on: <date>`
22. Move final TASKS.md entries to `## Done`

### Reactive Pipeline — The Protocol (Bug-to-Fix)

**Stage 1 — Discover (before touching code):**

1. Create `docs/knowledge/scenarios/SCN-NNNN-short-slug.md`
2. Frontmatter: `status: open`, `discovered: <today>`, `resolved_by: null`
3. Populate `related_req: REQ-NNNN` if the bug occurred under a known requirement
4. Write **What Happened** (symptom only — don't speculate yet)
5. Commit. Non-negotiable: if it's not worth 3 minutes to document, it's not worth fixing.

**Stage 2 — Investigate:**

6. Update status to `investigating`
7. Fill in **Root Cause** as you learn it
8. When cause is known but fix isn't decided, update status to `decision-pending`

**Stage 3 — Decide (with the user, or with yourself in writing):**

9. Create `docs/decisions/ADR-NNNN-short-slug.md` with `triggered_by: SCN-NNNN`
10. Fill in Context, Decision, Consequences, Alternatives, Implementation
11. Before marking ADR `accepted`, add matching entries to TASKS.md

**Stage 4 — Queue (update TASKS.md):**

12. Add task(s) with full chain: `(ADR-NNNN ← SCN-NNNN)`
13. Break into sub-tasks if the work is more than ~1 hour

**Stage 5 — Close the scenario:**

14. Set `status: resolved` and `resolved_by: ADR-NNNN`
15. Fill in **Fix** (points to ADR) and **Lesson** (what to generalize)

**Stage 6 — Implement:**

16. Work the task, check off sub-tasks, move to `## Done` when complete

### Shortcut Rule (Reactive Pipeline)

For **mechanical fixes with no design decision** (typo, obvious off-by-one, missing null check), skip the ADR. But still write the scenario — next time the class of bug recurs, you want to see the pattern. In that case the scenario's `resolved_by` points to the commit hash, not an ADR, with a note "Trivial fix, no ADR".

Rule of thumb: **if the user and assistant had to discuss more than one option, it's an ADR.**

### Worked Example — Forward Pipeline (Reading Stats Dashboard)

| Stage | Artifact | Key Contents |
|---|---|---|
| 1 | `REQ-0003` | "Monthly reading stats dashboard" + 5 acceptance criteria; user accepts |
| 2 | `PLAN-0002` | SQL view → API endpoint → Chart.js component; two Key Decisions; user accepts with note "year-over-year comparison as future REQ", logged separately |
| 3 | `ADR-0007` (SQL view) and `ADR-0008` (Chart.js), both `triggered_by: PLAN-0002` | Written and accepted |
| 3 | `TASKS.md` gains | `- [ ] Build monthly-pages SQL view (ADR-0007 ← PLAN-0002 ← REQ-0003)` + two more |
| 4 | Implementation | Tests named `test_req_0003_*.ts`; sub-tasks checked off |
| 4 | Mid-implementation bug: books appear in wrong month near timezone boundary | `SCN-0007` opened with `related_req: REQ-0003`, resolved by `ADR-0012` (timezone-aware bucketing) |
| 5 | User verifies REQ-0003 acceptance criteria together | All green; REQ-0003 → `verified`, `verified_on: 2026-04-15` |

Six months later, someone asks "why do we use a SQL view instead of computing stats on read?" → open ADR-0007 → trace `triggered_by` to PLAN-0002 → see that PLAN-0002 addresses REQ-0003 → understand the full context including alternatives evaluated. The chain never breaks.

### Worked Example — Reactive Pipeline (Timezone Bug)

| Step | Artifact | Contents |
|---|---|---|
| 1 | `SCN-0007-finished-date-timezone.md` | Symptom logged, `status: open`, `related_req: REQ-0003` |
| 2 | Same file updated | Root cause: bucketing by UTC date ignores user timezone, `status: decision-pending` |
| 3 | `ADR-0012-timezone-aware-month-buckets.md` | Decision: convert to user timezone before month-truncation; `triggered_by: SCN-0007` |
| 4 | `TASKS.md` | `- [ ] **Store finished_at timezone correctly** (ADR-0012 ← SCN-0007)` |
| 5 | SCN-0007 updated | `status: resolved`, `resolved_by: ADR-0012`, Lesson filled in |
| 6 | Task moves to `## Done` with completion date | |

---

## Code-Level Traceability

The pipelines above get you from a user need to a task, but the chain breaks once a developer (or AI assistant) starts writing code. A reader staring at a specific line has no direct way back to the decision that shaped it. Two lightweight conventions fix that: **inline ADR markers** in source code, and **one-ADR-per-commit** discipline in git history.

Together these make the chain navigable from any direction: from TASKS.md up to the REQ, from a git commit to the ADR, from a line of code to the reasoning that justifies it.

### Inline ADR markers in source code

When code embodies a non-obvious trade-off captured in an ADR, mark it with a comment referencing the ADR ID. The test is simple: **if a future reader might look at this code and think "why don't we just do X?", add the marker.** The marker tells them exactly where to find the answer.

```python
# Python
# ADR-0007: monthly aggregation lives in a SQL view, not the API layer.
# See docs/decisions/ADR-0007-sql-view-for-monthly-aggregation.md for alternatives.
def get_monthly_stats(user_id: str, year: int) -> list[MonthlyStat]:
    ...
```

```typescript
// TypeScript
// ADR-0008: Chart.js with tree-shaken imports over Recharts/D3.
// See docs/decisions/ADR-0008-chart-library-choice.md for bundle-size rationale.
import { Bar } from 'react-chartjs-2';
import { Chart, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
Chart.register(BarElement, CategoryScale, LinearScale, Tooltip);
```

```sql
-- SQL
-- ADR-0012: buckets month AFTER converting to user timezone.
-- See docs/decisions/ADR-0012-timezone-aware-month-buckets.md and SCN-0007.
CREATE VIEW monthly_reading_stats AS
SELECT
  u.id AS user_id,
  DATE_TRUNC('month', b.finished_at AT TIME ZONE u.timezone) AS month,
  SUM(b.page_count) AS pages
FROM books b JOIN users u ON u.id = b.user_id
GROUP BY 1, 2;
```

**When to add markers:**

- At the definition of any function, class, module, or config value whose *design* is driven by an ADR
- At any block of code that implements a safety rule, a non-obvious optimisation, or a deliberate limitation
- At config files where a value choice comes from an ADR (e.g., `KELLY_FRACTION = 0.25  # ADR-0005`)
- At test files — a single top-of-file comment is enough: `// Tests for REQ-0003. See ADR-0007, ADR-0008.`

**When NOT to add markers:**

- Trivial code (getters, string formatting, obvious helpers) — markers would be noise
- Code that's one of many identical instances of a pattern (mark the pattern's canonical location, not every use)
- Internal implementation details that aren't themselves decisions

**Format:**

- Always use the full ID: `ADR-0007`, not `ADR 7` or `adr-7`. This makes grep/ripgrep searches reliable.
- Prefer one-line markers. If you need more than two lines to explain, the ADR itself isn't doing its job — fix that instead.
- For code that implements multiple ADRs, list them: `// ADR-0007, ADR-0012`.
- It's fine to also mark REQ or SCN when relevant: `// ADR-0012 ← SCN-0007: fix for timezone-bucketing bug`.

**Grep-ability is the payoff.** Any ADR can be traced to every line that implements it:

```bash
# Find every file mentioning a specific ADR
rg "ADR-0007"

# Find every ADR marker in the codebase
rg "ADR-\d{4}"

# Find tests for a specific REQ
rg "REQ-0003" tests/
```

### One commit per ADR

When implementing, commit changes in units that map one-to-one to ADRs. The commit message carries the ADR ID so `git log` itself becomes a traceability surface.

**Commit message format:**

```
<type>(<scope>): <short description> [ADR-NNNN]

<optional body explaining what changed and why, referencing
the ADR for fuller reasoning>
```

Examples:

```
feat(stats): add monthly-pages SQL view [ADR-0007]

Implements the pre-aggregated view that powers the /stats/monthly
endpoint. See ADR-0007 for why this is a view and not an on-read
computation. Integration test covers insert/update/delete paths.
```

```
fix(stats): bucket monthly stats in user timezone [ADR-0012 ← SCN-0007]

Resolves the bug in SCN-0007 where users near date boundaries saw
books in the wrong month. See ADR-0012 for the UTC-storage,
timezone-on-bucket decision.
```

```
chore(bookshelf): enforce DRY_RUN default in dev env [ADR-0003]
```

**Rules:**

- **One ADR per commit when implementing that ADR.** A single commit may touch many files (migrations, code, tests, config) — that's fine, as long as every change traces to the same ADR.
- **Mixed-ADR commits are only acceptable for tiny cross-cutting changes** (e.g., adding an import used by three features). Prefer splitting.
- **Non-ADR commits use conventional-commit prefixes without the ADR tag**: `docs:`, `chore:`, `style:`, `test:`. A commit that only updates TASKS.md or fixes a typo doesn't need an ADR reference.
- **Bug fixes that used the shortcut rule** (no ADR, trivial fix) reference the scenario directly: `fix(parser): handle null payload [SCN-0014]`.

**`git log` becomes a queryable surface:**

```bash
# Every commit implementing a specific ADR
git log --grep "ADR-0012"

# Every commit related to a scenario (whether via ADR or shortcut)
git log --grep "SCN-0007"

# Recent ADR-tagged commits
git log --grep "ADR-\d\{4\}" -E --oneline -20
```

### Closing the chain

With both conventions in place, the traceability chain reaches all the way down:

```
REQ ← PLAN ← ADR ← TASKS.md ← git commit ← inline marker ← line of code
```

From any point you can walk in either direction:

- **"Why is this line written this way?"** → read the inline marker → open the ADR → see `triggered_by` → trace up to REQ or SCN
- **"What did we ship for ADR-0012?"** → `git log --grep "ADR-0012"` → see every commit → `git show <hash>` for the diffs
- **"What code implements REQ-0003?"** → look at REQ-0003's `implemented_by.adrs` → grep each ADR ID → see every file that references them

The chain has no gaps. Six months from now, a new contributor (or a fresh AI session) can land on any artifact and reconstruct the full story in minutes.

### Adoption checklist

To adopt these conventions on an existing project:

1. Add a **Commit convention** section to `CLAUDE.md` showing the `[ADR-NNNN]` format
2. Add an **Inline markers** line to the code conventions in `CLAUDE.md`
3. When creating new ADRs, mention in the `## Implementation` section where markers should go
4. No retrofit required — start with new code; existing code picks up markers as it's touched

---

## AI-Assistant Memory (`.claude/` directory)

Separate from project docs. This is the AI assistant's persistent memory across sessions (applies to Claude Code specifically; other tools have similar mechanisms).

```
.claude/
├── CLAUDE.md                    # Your personal global instructions
└── projects/
    └── my-project/
        └── memory/
            ├── MEMORY.md        # Index file (links to memories)
            ├── user_role.md     # Who you are, your expertise
            ├── feedback_*.md    # Corrections ("don't do X because Y")
            ├── project_*.md     # Project state, decisions, context
            └── reference_*.md   # External system pointers
```

Each memory file has frontmatter:

```markdown
---
name: Short descriptive name
description: One line — used to decide relevance in future sessions
type: user | feedback | project | reference
---

[Content — for feedback type, structure as: rule, then Why:, then How to apply:]
```

Two recommended standing feedback memories for any project using this architecture:

```markdown
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
```

```markdown
---
name: Bug-to-Fix Pipeline is mandatory for issues
description: Bugs always go SCN → ADR (if non-trivial) → TASKS
type: feedback
---

Rule: When a bug or unexpected behavior is discovered, do not jump to a
code fix. Create SCN-NNNN first.

Why: Ad-hoc fixes erase the reasoning trail. Three months later nobody
remembers why the code looks the way it does, and the same class of bug
recurs.

How to apply:
1. Create SCN-NNNN scenario first (even 3 sentences is enough)
2. Surface root cause + fix options to the user
3. Capture chosen fix as ADR-NNNN with triggered_by: SCN-NNNN
4. Add TASKS.md entry referencing the ADR before writing code
5. Only then implement
Exception: one-line mechanical fixes may skip the ADR but still need SCN.
```

---

## Putting It All Together

When you start a new project with an AI coding assistant:

1. **Create `CLAUDE.md`** with project overview, tech stack, safety rules, and pointers to both pipelines
2. **Create `TASKS.md`** with an empty legend
3. **Create `docs/README.md`** that describes both pipelines prominently
4. **Create the folder scaffold**: `docs/requirements/`, `docs/plans/`, `docs/decisions/`, `docs/knowledge/scenarios/`, each with a README
5. **Write `REQ-0001`** for the project's initial scope
6. **Write `PLAN-0001`** for the initial architecture; get user acceptance
7. **Write ADR-0001 through ADR-000N** for the plan's key decisions
8. **Populate TASKS.md** with the initial implementation breakdown
9. **Add commit & inline-marker conventions to `CLAUDE.md`** (see the Code-Level Traceability section above)
10. **Add the two feedback memories** to `.claude/projects/*/memory/`
11. **Tell the assistant**: "Read CLAUDE.md, TASKS.md, and docs/README.md before starting. Follow the Forward Pipeline for new work and the Bug-to-Fix Pipeline for issues. Mark code with ADR references and commit per-ADR."

From then on:

- Every new feature → REQ → PLAN → ADRs → TASKS.md → verified REQ
- Every bug → SCN → ADR (if non-trivial) → TASKS.md → resolved SCN
- Every architectural choice → ADR (with appropriate `triggered_by`)
- Every debugging session → SCN (even if trivial)
- Every correction to the assistant → feedback memory
- Every milestone → TASKS.md update
- **Every non-obvious line of code → inline ADR marker**
- **Every implementation commit → `[ADR-NNNN]` in the message**

---

## Quick Reference

| What | Where | When to Create | Cross-references |
|------|-------|----------------|------------------|
| Project setup & rules | `CLAUDE.md` | Project start; update when conventions change | Points to docs/README.md |
| Progress tracking | `TASKS.md` | Every meaningful milestone | Each task: `(ADR ← PLAN ← REQ)` or `(ADR ← SCN)` |
| User need + acceptance | `docs/requirements/REQ-NNNN-*.md` | Any new feature or behavior change | `implemented_by.plan`, `.adrs`; `verified_on` |
| Proposed architecture | `docs/plans/PLAN-NNNN-*.md` | Before implementing any REQ | `addresses: [REQ]`, `spawns_adrs`, `spawns_tasks` |
| Architectural decision | `docs/decisions/ADR-NNNN-*.md` | Any non-trivial choice | `triggered_by: REQ\|PLAN\|SCN\|null`, `implementation_tasks` |
| Bug / incident | `docs/knowledge/scenarios/SCN-NNNN-*.md` | Upon discovery, before fixing | `related_req`, `resolved_by: ADR` |
| How things work | `docs/knowledge/` | When you learn something non-obvious | Link to relevant ADRs/REQs |
| Inline marker in code | Comment at definition site | Any non-obvious code backed by an ADR | `// ADR-NNNN` or `// ADR-NNNN ← SCN-NNNN` |
| Implementation commit | git commit message | Each commit that implements an ADR | `[ADR-NNNN]` or `[ADR-NNNN ← SCN-NNNN]` suffix |
| Assistant memory | `.claude/projects/*/memory/` | When the assistant should remember something | MEMORY.md indexes all |

---

## The Traceability Invariant

At any moment, any person (or any AI session) should be able to answer:

- **"Why is this task in TASKS.md?"** → follow the chain: ADR → PLAN → REQ (forward) or ADR → SCN (reactive)
- **"Why was this ADR written?"** → check `triggered_by`: a REQ (freestanding), a PLAN (architectural decision within a feature), or a SCN (bug fix)
- **"What did we do about this requirement?"** → open the REQ → follow `implemented_by.plan` → read the PLAN → see `spawns_adrs` and `spawns_tasks`
- **"What did we do about this bug?"** → open the SCN → follow `resolved_by` → read the ADR → see `implementation_tasks` in TASKS.md
- **"Is this requirement done?"** → open the REQ → check `status: verified` and each acceptance criterion
- **"Why is this line of code written this way?"** → read the inline ADR marker → open the ADR → follow `triggered_by` up to the REQ or SCN
- **"Which commits implemented this ADR?"** → `git log --grep "ADR-NNNN"` → see the full implementation history

If any of those chains break, the documentation has drifted. Fix it.

The ID system is what makes this work. Six artifact types plus two code-level conventions, each uniquely addressable, each linking to the others. No orphans, no lost reasoning, no "wait, why did we do it this way?" moments three months from now.
