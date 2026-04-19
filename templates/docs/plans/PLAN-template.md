---
id: PLAN-NNNN
title: "<Short title in quotes>"
status: proposed          # proposed | accepted | superseded
date: YYYY-MM-DD
addresses: [REQ-NNNN]     # which requirements this plan implements
spawns_adrs: []           # [ADR-NNNN, ...] populated once ADRs are written
spawns_tasks: []          # task titles matching entries in TASKS.md
accepted_by: null         # <user handle> when accepted
accepted_on: null         # YYYY-MM-DD when accepted
superseded_by: null       # PLAN-NNNN if this is later replaced
---

## Summary

<One paragraph: what are we building and how? Keep it high-level.>

## Architecture

<Narrative or ASCII diagram of component interactions. Details live in
individual ADRs — this section is the 30-second overview.>

```
┌──────────┐   ┌──────────┐   ┌──────────┐
│   ...    │──▶│   ...    │──▶│   ...    │
└──────────┘   └──────────┘   └──────────┘
```

## Key Decisions (each becomes an ADR)

- D1: <decision title> → ADR-NNNN
- D2: <decision title> → ADR-NNNN

## Alternatives Considered (high-level)

<Brief notes. Detailed alternatives go in individual ADRs.>

- <alternative 1>: deferred/rejected because ...
- <alternative 2>: deferred/rejected because ...

## Risks & Mitigations

- <risk> → <mitigation>
- <risk> → <mitigation>

## User Acceptance

Reviewed: YYYY-MM-DD by <user>
Decision: <accepted | accepted with notes | revise>
Notes: <any changes agreed during review — incorporated into the plan above>
