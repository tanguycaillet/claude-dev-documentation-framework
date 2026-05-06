"""Shared path-resolution helpers used by both the indexer and the CLI.

Single source of truth for finding TASKS.md given a docs root, so the
indexer (which discovers tasks per corpus on reindex) and the CLI (which
parses tasks in-memory for ad-hoc inspection) cannot drift in their
discovery behaviour.
"""

from pathlib import Path


def resolve_tasks_path(docs_root: Path, override: Path | None = None) -> Path | None:
    """Return the TASKS.md path for `docs_root`, or None if there isn't one.

    Search order (inside-first):
      1. `<docs_root>/TASKS.md` — self-contained example dirs ship this way.
      2. `<docs_root>/../TASKS.md` — real projects keep TASKS.md sibling to docs/.

    An explicit `override` wins. Missing files return None silently —
    corpora without TASKS.md are valid (zero tasks indexed).
    """
    if override is not None:
        return override if override.exists() else None
    inside = docs_root / "TASKS.md"
    if inside.exists():
        return inside
    sibling = docs_root.parent / "TASKS.md"
    return sibling if sibling.exists() else None
