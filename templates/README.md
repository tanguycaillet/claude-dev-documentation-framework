# Templates

These are copy-paste-ready scaffolds for adopting the framework in your own project.

## Quick start

From your project root:

```bash
# Clone this repo somewhere temporary
git clone https://github.com/YOUR-ORG/claude-dev-documentation-framework /tmp/cddf

# Copy the templates into your project
cp -r /tmp/cddf/templates/. .

# Clean up
rm -rf /tmp/cddf

# Commit
git add CLAUDE.md TASKS.md docs/ .claude/
git commit -m "chore: adopt claude-dev-documentation-framework"
```

## What's here

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project instructions — fill in your tech stack, conventions, safety rules |
| `TASKS.md` | Single source of truth for progress — starts empty |
| `docs/README.md` | Describes both pipelines so anyone (or any AI) reading the repo knows the protocol |
| `docs/requirements/REQ-template.md` | Copy this to `REQ-NNNN-slug.md` for each new requirement |
| `docs/plans/PLAN-template.md` | Copy this to `PLAN-NNNN-slug.md` for each new plan |
| `docs/decisions/ADR-template.md` | Copy this to `ADR-NNNN-slug.md` for each new decision |
| `docs/knowledge/scenarios/SCN-template.md` | Copy this to `SCN-NNNN-slug.md` for each new bug / incident |
| `.claude/projects/_template/memory/*` | Standing memory files for AI assistant continuity |

## Next steps after copying

1. Edit `CLAUDE.md` with your project's specifics
2. Write `REQ-0001` for the project's initial scope
3. Write `PLAN-0001` for the initial architecture; get user acceptance
4. Populate `TASKS.md` with initial tasks (with upstream references)
5. Rename `.claude/projects/_template/` to `.claude/projects/<your-project-name>/`

See the full framework spec at `docs/documentation-approach.md` in the main repo.
