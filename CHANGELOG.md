# Changelog

All notable changes to this framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/YOUR-ORG/claude-dev-documentation-framework/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR-ORG/claude-dev-documentation-framework/releases/tag/v0.1.0
