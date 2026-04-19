# Plans (`PLAN-NNNN`)

One file per plan. Filename format: `PLAN-NNNN-short-slug.md`.

A plan is the AI assistant's proposed approach to satisfying one or more
requirements. It's the point where architecture gets proposed, discussed,
and accepted as a batch. Think of a PLAN as a design review in document form.

## Status lifecycle

`proposed` → `accepted` → optionally `superseded`

A plan cannot be marked `accepted` until the user explicitly signs off
(recorded in the frontmatter AND the "User Acceptance" section).

Once accepted, all spawned ADRs must be written before implementation
starts. The PLAN promises decisions; the ADRs deliver them.

## Template

Copy `PLAN-template.md`, rename to the next available `PLAN-NNNN-slug.md`, and fill it in.
