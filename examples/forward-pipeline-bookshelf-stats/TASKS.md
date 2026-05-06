# TASKS.md, forward-pipeline-bookshelf-stats example

Example TASKS.md for the framework's forward-pipeline worked example.
Demonstrates post-M2 task IDs (TASK-NNNN) referenced by ADR
`implementation_tasks` and PLAN `spawns_tasks` lists.

Legend: `[x]` done, `[~]` in progress, `[ ]` todo, `[!]` blocked, `[/]` parked.

## Done

### [Reading Stats Pipeline: PLAN-0002]

- [x] **TASK-0001: Build monthly-pages SQL view** `(ADR-0007 <- PLAN-0002 <- REQ-0003)`
- [x] **TASK-0002: Wire /stats/monthly API endpoint** `(ADR-0007 <- PLAN-0002 <- REQ-0003)`
- [x] **TASK-0003: Chart.js integration** `(ADR-0008 <- PLAN-0002 <- REQ-0003)`
- [x] **TASK-0004: Reading stats dashboard component** `(ADR-0008 <- PLAN-0002 <- REQ-0003)`
