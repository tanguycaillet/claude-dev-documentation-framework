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
