# Architectural Decision Records (`ADR-NNNN`)

One file per decision. Filename format: `ADR-NNNN-short-slug.md`.

An ADR captures **why** you made a technical choice. Not the code — the reasoning.

## Status lifecycle

`proposed` → `accepted` → optionally `superseded`

## Key rules

- **ADRs are immutable once accepted.** If you change your mind, write a NEW
  ADR with `supersedes: ADR-NNNN` pointing to the old one. Never edit an
  accepted ADR.
- **`triggered_by` is mandatory** — even if the value is `null` (meaning a
  freestanding architectural choice, not driven by a specific REQ / PLAN / SCN).
- **An ADR cannot be `accepted` until its `implementation_tasks` exist in `TASKS.md`.**
- **Keep them short.** One page max. Value is in the decision + reasoning, not length.

## When to write one

- A decision called out inside an accepted PLAN (most common source)
- Resolving a SCN that required more than a mechanical fix
- Any standalone architectural choice not part of a larger plan
- Any decision you might question in 3 months

## Template

Copy `ADR-template.md`, rename to the next available `ADR-NNNN-slug.md`, and fill it in.
