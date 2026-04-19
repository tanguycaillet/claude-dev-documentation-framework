# Examples

Two fully worked examples showing the framework end-to-end. Every artifact
here is real — not a template. Use these to see what a complete cross-
referenced chain actually looks like.

Both examples are set in a fictional **Bookshelf** app — a personal reading
tracker where users log books they've read, are reading, or want to read.

## Forward Pipeline — [Reading Stats Dashboard](forward-pipeline-bookshelf-stats/)

A new-feature build from initial user request to verified delivery:

```
REQ-0003 (user wants monthly reading stats)
  └─ PLAN-0002 (SQL view → API → Chart.js component)
       ├─ ADR-0007 (monthly aggregation as a SQL view)
       └─ ADR-0008 (Chart.js over alternatives)
            └─ TASKS.md entries referencing the full chain
```

## Reactive Pipeline — [Timezone Bug](reactive-pipeline-timezone-bug/)

A bug discovered mid-implementation, diagnosed, decided, and fixed:

```
SCN-0007 (books appearing in wrong month near timezone boundary)
  └─ ADR-0012 (convert to user timezone before month-bucketing)
       └─ TASKS.md entry referencing the chain
```

## How to read these

Start with the README in each example directory — it gives you the story
in narrative form. Then open each artifact in order to see how the
cross-references work in practice.

Pay particular attention to:
- The `triggered_by` field in ADRs
- The `addresses` and `spawns_*` fields in PLANs
- The arrow notation in TASKS excerpts: `(ADR-NNNN ← PLAN-NNNN ← REQ-NNNN)`
- The `resolved_by` field in the scenario
