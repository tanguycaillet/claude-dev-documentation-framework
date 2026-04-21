# Changelog

All notable changes to this framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-04-21

### Added
- **Code-Level Traceability section** in `docs/documentation-approach.md` — extends the chain all the way down to source code via two conventions:
  - Inline ADR markers at definition sites (e.g., `// ADR-0007: short reason`)
  - One-ADR-per-commit discipline with `[ADR-NNNN]` tags in commit messages
- **Behavioral Guidelines** in `templates/CLAUDE.md` — universal anti-patterns for AI-assisted coding (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution). Complements the framework's architectural discipline with code-level discipline.
- **Commit Convention section** in `templates/CLAUDE.md` showing expected message formats with worked examples.
- Inline marker + commit examples added to `ADR-0007` and `ADR-0012` in the worked examples.
- Two new entries in the Quick Reference table: "Inline marker in code" and "Implementation commit".
- Two new queries in the Traceability Invariant: "Why is this line of code written this way?" and "Which commits implemented this ADR?".

### Changed
- The "Putting It All Together" checklist now includes step 9 (add commit & marker conventions to CLAUDE.md) before the feedback memories.
- Closing summary updated from "six artifact types" to "six artifact types plus two code-level conventions".

## [0.1.0] — 2026-04-19

Initial public release.

### Added
- Core framework specification (`docs/documentation-approach.md`)
- Six artifact types with cross-reference discipline:
  - `CLAUDE.md` — project instructions
  - `TASKS.md` — progress tracker
  - `REQ-NNNN` — requirement record
  - `PLAN-NNNN` — architecture plan
  - `ADR-NNNN` — architectural decision record
  - `SCN-NNNN` — scenario / bug report / post-mortem
- Two complementary pipelines: Forward (proactive) and Reactive (bug-to-fix)
- Template scaffold in `templates/` for copy-paste adoption
- Two fully worked examples in `examples/`:
  - `forward-pipeline-bookshelf-stats/` — building a new feature end-to-end
  - `reactive-pipeline-timezone-bug/` — diagnosing and fixing a bug end-to-end
- Standing Claude memory files for enforcing pipeline discipline across sessions
- Traceability invariant — five queries that should always be answerable by
  following ID references

[Unreleased]: https://github.com/tanguycaillet/claude-dev-documentation-framework/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tanguycaillet/claude-dev-documentation-framework/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tanguycaillet/claude-dev-documentation-framework/releases/tag/v0.1.0
