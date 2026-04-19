# Claude Dev Documentation Framework

> A traceable documentation architecture for AI-assisted software projects.
> Every task links to a decision. Every decision links to a requirement or a bug.
> Nothing gets orphaned, and nothing gets forgotten.

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Status: v0.1.0](https://img.shields.io/badge/status-v0.1.0-blue.svg)](CHANGELOG.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Why this exists

When you work with an AI coding assistant across many sessions, the assistant loses context between sessions, and you lose it across weeks. Chat logs compress, decisions get re-debated, bugs get patched without anyone remembering why the original code looked that way.

This framework fixes that by giving every project six well-defined artifact types, each with a sequential ID, each linking to the others. The result is a **bi-directional traceability chain**: from any task, you can walk backwards to the decision that caused it, the plan that contained that decision, and the requirement (or bug) that motivated the plan. And from any requirement, you can walk forward to every decision, task, and test that implements it.

## The two pipelines

New work flows forward. Problems flow reactively. Both end in `TASKS.md`, both use the same ID discipline.

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

## The artifact catalog

| Artifact | ID | Purpose |
|---|---|---|
| Project instructions | — | `CLAUDE.md` — how the assistant should work in this repo |
| Progress tracker | — | `TASKS.md` — single source of truth for current work |
| Requirement | `REQ-NNNN` | What the user needs + acceptance criteria |
| Plan | `PLAN-NNNN` | Proposed architecture, reviewed and accepted by the user |
| Decision | `ADR-NNNN` | Why we chose approach X over Y |
| Scenario | `SCN-NNNN` | Bug, incident, or debugging write-up |
| Knowledge article | — | Reference material, concepts, how-it-works |

## Who this is for

- **Developers using Claude Code, Cursor, or similar AI coding assistants** who have felt the pain of context loss between sessions
- **Solo devs and small teams** building real software who want lightweight but durable documentation
- **Tech leads** who want junior devs (human or AI) to understand *why* the architecture looks the way it does
- **Anyone** who has ever said "wait, why did we do it this way?" three months after the fact

It is **not** a heavyweight enterprise process. Every artifact is a short Markdown file with YAML frontmatter. The ritual is what matters, not the length.

## Quick start

### Option A — Use as a GitHub template (recommended)

1. Click **Use this template** at the top of the repo page
2. Name your new project repo
3. Clone it locally
4. Delete the `examples/` directory (or keep it for reference)
5. Fill in `CLAUDE.md`, write your first `REQ-0001` in `docs/requirements/`, and go

### Option B — Copy the scaffold into an existing project

```bash
# From your existing project root:
git clone https://github.com/YOUR-ORG/claude-dev-documentation-framework /tmp/cddf
cp -r /tmp/cddf/templates/. .
rm -rf /tmp/cddf

# Customize the templates with your project's specifics, then commit
git add CLAUDE.md TASKS.md docs/ .claude/
git commit -m "chore: adopt claude-dev-documentation-framework"
```

### Option C — Read first, adopt later

Start by reading [`docs/documentation-approach.md`](docs/documentation-approach.md) end-to-end. Then look at the worked [`examples/`](examples/) to see real cross-referenced artifacts. Adopt what fits your project.

## What's in this repo

```
claude-dev-documentation-framework/
├── README.md                         # You are here
├── LICENSE                           # CC BY 4.0
├── CONTRIBUTING.md                   # How to contribute
├── CHANGELOG.md                      # Version history
├── docs/
│   └── documentation-approach.md     # The full framework specification
├── templates/                        # Copy these into your project
│   ├── CLAUDE.md
│   ├── TASKS.md
│   ├── docs/
│   │   ├── README.md
│   │   ├── requirements/
│   │   ├── plans/
│   │   ├── decisions/
│   │   └── knowledge/scenarios/
│   └── .claude/projects/_template/memory/
└── examples/                         # Fully worked examples
    ├── forward-pipeline-bookshelf-stats/   # New feature, end-to-end
    └── reactive-pipeline-timezone-bug/     # Bug fix, end-to-end
```

## A peek at what "traceable" means

Here's a single line from a `TASKS.md` in a project that uses this framework:

```markdown
- [~] **Build monthly-pages SQL view** (ADR-0007 ← PLAN-0002 ← REQ-0003) — started 2026-04-10
```

From that one line you can trace:
- **REQ-0003** tells you what the user actually asked for and how they'll know it's done
- **PLAN-0002** tells you the broader architectural approach, which the user reviewed and accepted
- **ADR-0007** tells you *specifically* why a SQL view was chosen over computing on-read, with alternatives considered

Three months from now, if someone asks "why do we have this view?", the answer is a 30-second walk through four Markdown files — not an archaeological dig through Git history and Slack threads.

See [`examples/forward-pipeline-bookshelf-stats/`](examples/forward-pipeline-bookshelf-stats/) for the full chain.

## The traceability invariant

At any moment, any person (or any AI assistant session) should be able to answer:

- **"Why is this task in TASKS.md?"** → follow the chain: ADR → PLAN → REQ (forward) or ADR → SCN (reactive)
- **"Why was this ADR written?"** → check `triggered_by`: a REQ, a PLAN, or a SCN
- **"What did we do about this requirement?"** → open the REQ → follow `implemented_by` → see spawned plans, ADRs, and tasks
- **"What did we do about this bug?"** → open the SCN → follow `resolved_by` → read the ADR
- **"Is this requirement done?"** → open the REQ → check `status: verified` and each acceptance criterion

If any of those chains break, the documentation has drifted. Fix it.

## Contributing

Issues, PRs, and forks are all welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. This framework is itself a work in progress — if you find something that doesn't work in practice, I want to hear about it.

## License

This work is licensed under a [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/). You are free to share, adapt, and build on it commercially; please attribute.

## Acknowledgements

The ADR pattern used here was popularized by [Michael Nygard's 2011 post](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). The broader framework emerged from practical experience working on multi-week AI-assisted coding projects where context loss was the dominant pain point.
