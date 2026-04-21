# CLAUDE.md — <Project Name>

## What This Is
<One or two paragraphs. What does this project do? What problem does it solve?
Write it as if explaining to a new hire on day one.>

## Tech Stack
- Language: <e.g., Python 3.12+, TypeScript, Go>
- Framework: <e.g., FastAPI, Next.js, Express>
- Database: <e.g., PostgreSQL, SQLite, MongoDB>
- Key libraries: <list the handful that shape how code is written>
- Testing: <e.g., pytest, vitest, go test>
- Linting / formatting: <e.g., ruff + black, prettier + eslint, gofmt>

## Project Structure
```
<project-root>/
├── src/            # <one-line description>
├── tests/          # <one-line description>
├── docs/           # requirements, plans, decisions, scenarios
├── TASKS.md        # progress tracker
└── CLAUDE.md       # this file
```

## How to Run
```bash
# Install
<install command>

# Develop
<dev command>

# Test
<test command>

# Build / deploy
<build command>
```

## Code Conventions
- <convention 1>
- <convention 2>
- <convention 3>
- Tests in `tests/` follow naming `test_req_NNNN_*` so you can see which REQ each verifies
- **Inline ADR markers** on non-obvious code: `// ADR-NNNN: short reason` at the definition site. Use full IDs (`ADR-0007`, not `ADR 7`) so grep works. Skip markers on trivial code.
- **No "improvements" to adjacent code** when making a change — touch only what the task requires.

## Safety Rules
1. Never commit `.env` or any secrets file
2. <rule specific to your domain — e.g., "never run migrations against prod without dry-run">
3. <rule specific to your domain>

## Environment Variables
| Variable | Purpose | Required? |
|---|---|---|
| `DATABASE_URL` | Connection string | Yes |
| `LOG_LEVEL` | `debug` \| `info` \| `warn` \| `error` | No (default `info`) |

## Working Discipline
- **New features** follow the Forward Pipeline: REQ → PLAN → ADR → TASKS → verify
- **Bugs / unexpected behavior** follow the Bug-to-Fix Pipeline: SCN → ADR → TASKS
- **Never implement without first creating the upstream artifacts**

See `docs/README.md` for full pipeline protocols and `docs/documentation-approach.md`
(linked from the framework repo) for the complete specification.

## Commit Convention

One ADR per commit when implementing that ADR. The commit message carries the ADR ID so `git log` itself is a traceability surface.

Format:

```
<type>(<scope>): <short description> [ADR-NNNN]

<optional body>
```

Examples:

```
feat(stats): add monthly-pages SQL view [ADR-0007]
fix(stats): bucket monthly stats in user timezone [ADR-0012 ← SCN-0007]
chore(config): enforce DRY_RUN default in dev env [ADR-0003]
```

Non-implementation commits (docs, formatting, typos, TASKS.md updates) use plain conventional-commit prefixes without an ADR tag: `docs:`, `chore:`, `style:`, `test:`.

Shortcut-rule bug fixes (trivial, no ADR) reference the scenario directly: `fix(parser): handle null payload [SCN-0014]`.

---

## Behavioral Guidelines

Universal anti-patterns for AI-assisted coding. These apply on top of the project-specific rules above. The framework prevents architectural drift; these prevent code-level drift.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them. Don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it. Don't delete it.

When your changes create orphans:
- Remove imports, variables, and functions that your changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request (or to the current ADR being implemented).

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
