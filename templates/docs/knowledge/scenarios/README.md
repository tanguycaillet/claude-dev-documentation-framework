# Scenarios (`SCN-NNNN`)

One file per scenario. Filename format: `SCN-NNNN-short-slug.md`.

Scenarios are the entry point of the Reactive Pipeline (Bug-to-Fix). They
document bugs, incidents, unexpected behaviors, and debugging sessions —
anything worth remembering that wasn't a planned change.

## Status lifecycle

| Status | Meaning |
|---|---|
| `open` | Just discovered. Symptom documented. Cause unknown. |
| `investigating` | Root cause analysis in progress. |
| `decision-pending` | Cause understood. Waiting for a fix decision (ADR). |
| `resolved` | ADR written, implementation queued or done. `resolved_by` populated. |
| `wont-fix` | Closed without action; reason in the article. |

A scenario cannot move to `resolved` without a `resolved_by: ADR-NNNN`
field populated (or a commit hash if the fix was purely mechanical).

## Template

Copy `SCN-template.md`, rename to the next available `SCN-NNNN-slug.md`, and fill it in.
