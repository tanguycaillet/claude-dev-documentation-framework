# docs/

This is the project's knowledge base and decision log. Everything here is
under version control and should be updated alongside code changes.

## Directory layout

```
docs/
├── README.md                     # You are here
├── architecture.md               # Module contracts (optional, create when useful)
├── requirements/                 # REQ-NNNN records
├── plans/                        # PLAN-NNNN records
├── decisions/                    # ADR-NNNN records
└── knowledge/
    ├── concepts/                 # Background / theory
    ├── data-sources/             # External data documentation
    ├── models/                   # Algorithm / model explanations
    └── scenarios/                # SCN-NNNN bug reports & post-mortems
```

## The Two Pipelines

### Forward Pipeline — for new features

```
User need → REQ-NNNN → PLAN-NNNN → ADR-NNNN (×N) → TASKS.md → code+tests → verify
```

**Before implementing any new feature:**

1. Write a `REQ-NNNN` in `requirements/` describing the user need and acceptance criteria. Get user acceptance.
2. Write a `PLAN-NNNN` in `plans/` describing the proposed architecture. Get user acceptance.
3. For each key decision in the plan, write an `ADR-NNNN` in `decisions/`.
4. Add entries to `TASKS.md` referencing the full chain.
5. Implement. Tests reference the `REQ` they verify.
6. Verify: walk through acceptance criteria with the user. Mark `REQ` as `verified`.

### Reactive Pipeline — for bugs and unexpected behavior

```
Observed issue → SCN-NNNN → ADR-NNNN (if non-trivial) → TASKS.md → fix
```

**When you hit a bug:**

1. Write an `SCN-NNNN` in `knowledge/scenarios/` before touching code.
2. Investigate. Update the scenario with root cause.
3. Decide the fix with the user. Capture the decision as an `ADR-NNNN` (unless the fix is purely mechanical).
4. Add task(s) to `TASKS.md` referencing the ADR.
5. Close the scenario with `resolved_by: ADR-NNNN`.
6. Implement.

## ID conventions

- Zero-padded to four digits: `REQ-0003`, `ADR-0012`, `SCN-0007`, `PLAN-0002`
- Sequential within each artifact type; never reused
- Filenames: `<ID>-<short-slug>.md`, e.g., `REQ-0003-monthly-stats-dashboard.md`

## The Traceability Invariant

Any task in `TASKS.md` should be traceable back to:
- Its `ADR` (via the arrow notation)
- Its `PLAN` or `SCN` (via the ADR's `triggered_by` field)
- Its `REQ` (via the PLAN's `addresses` field)

If any link is missing, the docs have drifted — fix the chain before continuing work.
