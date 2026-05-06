# TASKS.md, synthetic test fixture

This fixture exercises every grammar rule from ADR-0001 + ADR-0003 in a
small, hand-tuned file. Tests in `test_tasks_parser.py` parse this and
assert exact field values per row.

Legend: `[x]` done, `[~]` in progress, `[ ]` todo, `[!]` blocked, `[/]` parked.

## In Progress

- [~] **BE-001: implement the thing** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [x] **BE-002: completed task with multi-ADR refs** `(ADR-0001, ADR-0002 <- PLAN-0001 <- REQ-0001)`
- [ ] **BE-003: numeric shorthand** `(ADR-0001,0002 <- PLAN-0001 <- REQ-0001,0002)`
- [!] **BE-004: blocked task** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [/] **BE-005: parked task** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [X] **BE-006: capital-X done marker also parses** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [] **BE-007: empty status accepted as todo with warning** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`

## Done

### [Backend Foundation: PLAN-0001]

- [x] **BE-100: section PLAN inheritance, no explicit PLAN ref** `(ADR-0001)`
- [x] **BE-101: explicit PLAN ref overrides section** `(ADR-0001 <- PLAN-0002 <- REQ-0001)`

### [Standalone section, no PLAN]

- [x] **BE-200: section without PLAN context** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`

### [Phase Demo: PLAN-0001] {phase: alpha}

- [x] **BE-300: inherits section phase alpha** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [x] **BE-301: explicit phase overrides section** `(ADR-0001 <- PLAN-0001 <- REQ-0001)` {phase: beta}
- [x] **BE-302: phase before refs also parses** {phase: gamma} `(ADR-0001 <- PLAN-0001 <- REQ-0001)`

### [Sub-bullets: PLAN-0001]

- [x] **BE-400: task with three sub-bullets** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
  - [x] sub-bullet one: searchable text alpha
  - [x] sub-bullet two: searchable text beta
  - [ ] sub-bullet three: searchable text gamma

### [Multi-segment IDs: PLAN-0001]

- [x] **FE-DEV-1: multi-segment ID resolves to domain FE** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [x] **EP-008-P0: phase N of EP-008** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`
- [x] **BE-014a: alphabetic suffix** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`

### [Unicode arrow: PLAN-0001]

- [x] **BE-500: Unicode arrow in refs** `(ADR-0001 ← PLAN-0001 ← REQ-0001)`

### [Unrecognized prefix: PLAN-0001]

- [ ] **XYZ-001: prefix not in task_domains, warning expected** `(ADR-0001 <- PLAN-0001 <- REQ-0001)`

### [No upstream: PLAN-0001]

- [ ] **BE-600: no upstream literal** `(no upstream)`

## Todo

### [Malformed rows: PLAN-0001]

- [ ] **lowercase-prefix**: ID does not match regex, row is skipped
- [ ] **EP-008 Phase 0: whitespace in ID** `(ADR-0001)`
- [ ] **BE: prefix only, no segment** `(ADR-0001)`
