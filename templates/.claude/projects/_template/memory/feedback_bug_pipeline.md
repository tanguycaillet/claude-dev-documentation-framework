---
name: Bug-to-Fix Pipeline is mandatory for issues
description: Bugs always go SCN → ADR (if non-trivial) → TASKS
type: feedback
---

Rule: When a bug or unexpected behavior is discovered, do not jump to a
code fix. Create SCN-NNNN first.

Why: Ad-hoc fixes erase the reasoning trail. Three months later nobody
remembers why the code looks the way it does, and the same class of bug
recurs.

How to apply:
1. Create SCN-NNNN scenario first (even 3 sentences is enough)
2. Surface root cause + fix options to the user
3. Capture chosen fix as ADR-NNNN with triggered_by: SCN-NNNN
4. Add TASKS.md entry referencing the ADR before writing code
5. Only then implement

Exception: one-line mechanical fixes may skip the ADR but still need SCN.
