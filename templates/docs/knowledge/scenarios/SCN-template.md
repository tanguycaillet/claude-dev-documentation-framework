---
id: SCN-NNNN
title: <Short descriptive title — symptom-focused>
category: scenarios
status: open              # open | investigating | decision-pending | resolved | wont-fix
discovered: YYYY-MM-DD
resolved_by: null         # ADR-NNNN or <commit-hash>; required when status=resolved
related_req: null         # REQ-NNNN if the bug occurred under a known requirement
tags: [<tag>, <tag>]
last_updated: YYYY-MM-DD
---

# <Title>

## What Happened

<Symptom, observed behavior. Don't speculate about cause yet. Include:
when, who/what triggered it, what was expected vs. what occurred, and
any impact (users affected, data lost, etc.).>

## Root Cause

<Fill in as you investigate. What was the actual cause? Be specific — point
to the offending code path, configuration, or external trigger.>

## Fix

<Once decided, reference the ADR that captures the decision:
"See ADR-NNNN. Implementation tracked in TASKS.md."
For trivial fixes, reference the commit hash and note "Trivial fix, no ADR".>

## Lesson

<The generalizable takeaway. What class of bug is this? What pattern should
we watch for? What automated check could have caught it? This is the most
valuable section — it's what prevents the same bug recurring in a different form.>
