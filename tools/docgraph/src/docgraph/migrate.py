"""docgraph-migrate-adr-tasks: rewrite ADR.implementation_tasks from string-titles to task IDs.

One-shot migration script per ADR-0004. Reads each ADR's frontmatter, matches
its `implementation_tasks` titles against the TASKS.md task titles via a
strict cascade (exact -> case-insensitive -> whitespace-normalized), and on
`--apply` rewrites the frontmatter to the typed-id list format.

Two-phase semantics:
- Plan phase always runs: collects ready / no-op / blocked per ADR.
- Dry-run (default) prints the plan and exits 0, regardless of blocked count.
- --apply only writes when every ADR is ready or no-op; if any ADR is
  blocked (unmatched titles), it aborts with zero writes and exit 1.

Idempotent: ADRs whose `implementation_tasks` are already a list of typed
IDs short-circuit to no-op. Mixed-format ADRs (some IDs, some titles) are
re-resolved entry-by-entry.

Public surface:
    main(argv)                                       -> int (exit code)
    is_already_migrated(implementation_tasks)        -> bool
    match_titles(titles, tasks)                      -> MatchResult
    plan_run(adr_paths, tasks)                       -> list[ADRPlan]
    apply_run(plans, *, write)                       -> bool (success)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

from docgraph.config import CorpusConfig
from docgraph.models import Task
from docgraph.parser import parse_directory, parse_tasks_file


# Same regex as ADR-0001's ID rule. Used here to detect already-migrated
# ADRs (every implementation_tasks entry is already a typed ID).
_TASK_ID_RE = re.compile(r"^[A-Z]+(?:-[A-Z0-9]+)+[a-z]?$")


@dataclass
class TitleMatch:
    """One ADR title and its resolution outcome."""

    title: str
    matched_task_id: str | None
    """The task ID this title resolved to, or None when unmatched."""

    cascade_level: str | None
    """Which stage of the matching cascade resolved this title:
    - "already_id"             pre-typed ID; bypasses the cascade
    - "exact"                  task.title == title
    - "case_insensitive"       case-folded equality
    - "whitespace_normalized"  whitespace-collapsed + case-folded equality
    - None                     no match at any stage
    """

    ambiguous: bool = False
    """True when multiple tasks matched at the same cascade level (the
    earliest-by-line-number wins; the warning surfaces in dry-run output)."""


@dataclass
class ADRPlan:
    """Per-ADR migration plan, collected during the plan phase."""

    path: Path
    adr_id: str
    status: str                  # "ready" | "no-op" | "blocked"
    title_matches: list[TitleMatch] = field(default_factory=list)
    new_implementation_tasks: list[str] = field(default_factory=list)
    note: str = ""               # for no-op rationale, etc.


def is_already_migrated(implementation_tasks: Any) -> bool:
    """True if every entry in the list is already a typed ID per ADR-0001's regex.

    A missing or empty list is treated as already-migrated (nothing to do).
    A non-list is treated as not-migrated (so the script surfaces it as a
    regular planning step rather than silently skipping).
    """
    if not isinstance(implementation_tasks, list):
        return False
    if len(implementation_tasks) == 0:
        return True
    return all(
        isinstance(t, str) and _TASK_ID_RE.match(t) is not None
        for t in implementation_tasks
    )


def _normalize_whitespace(s: str) -> str:
    """Collapse runs of whitespace to single space + strip + lowercase."""
    return re.sub(r"\s+", " ", s).strip().lower()


def match_titles(titles: list[str], tasks: list[Task]) -> list[TitleMatch]:
    """Resolve each title against the tasks list via the strict cascade.

    Cascade order:
      1. Exact match on `task.title`
      2. Case-insensitive exact match
      3. Whitespace-normalized (collapsed + trimmed + lowercased) match

    No fuzzy matching. False positives at any level are quieter than
    unmatched and harder to detect, so the cascade caps at level 3.

    Tie-breaking: at the FIRST level where any match is found, if multiple
    tasks tie, earliest-by-line-number wins; the result is marked
    `ambiguous=True` so the caller can warn.
    """
    out: list[TitleMatch] = []
    for title in titles:
        # Already a typed ID? Short-circuit through, treat as "matched at level 0".
        if isinstance(title, str) and _TASK_ID_RE.match(title):
            out.append(
                TitleMatch(
                    title=title,
                    matched_task_id=title,
                    cascade_level="already_id",
                )
            )
            continue

        # Level 1: exact match
        exact_hits = [t for t in tasks if t.title == title]
        if exact_hits:
            exact_hits.sort(key=lambda t: t.line_number)
            out.append(
                TitleMatch(
                    title=title,
                    matched_task_id=exact_hits[0].id,
                    cascade_level="exact",
                    ambiguous=len(exact_hits) > 1,
                )
            )
            continue

        # Level 2: case-insensitive
        ci_hits = [
            t for t in tasks
            if t.title is not None and t.title.lower() == title.lower()
        ]
        if ci_hits:
            ci_hits.sort(key=lambda t: t.line_number)
            out.append(
                TitleMatch(
                    title=title,
                    matched_task_id=ci_hits[0].id,
                    cascade_level="case_insensitive",
                    ambiguous=len(ci_hits) > 1,
                )
            )
            continue

        # Level 3: whitespace-normalized
        norm_target = _normalize_whitespace(title)
        norm_hits = [
            t for t in tasks
            if t.title is not None and _normalize_whitespace(t.title) == norm_target
        ]
        if norm_hits:
            norm_hits.sort(key=lambda t: t.line_number)
            out.append(
                TitleMatch(
                    title=title,
                    matched_task_id=norm_hits[0].id,
                    cascade_level="whitespace_normalized",
                    ambiguous=len(norm_hits) > 1,
                )
            )
            continue

        # No match at any level
        out.append(
            TitleMatch(
                title=title,
                matched_task_id=None,
                cascade_level=None,
            )
        )

    return out


def plan_run(adr_paths: list[Path], tasks: list[Task]) -> list[ADRPlan]:
    """Build the migration plan for each ADR. No writes. Always succeeds."""
    plans: list[ADRPlan] = []
    for path in adr_paths:
        post = frontmatter.load(path)
        adr_id = post.metadata.get("id", path.stem)
        impl = post.metadata.get("implementation_tasks", [])

        # Idempotent: already-migrated ADR is a no-op.
        if is_already_migrated(impl):
            plans.append(
                ADRPlan(
                    path=path,
                    adr_id=adr_id,
                    status="no-op",
                    note="already on task-id format",
                )
            )
            continue

        if not isinstance(impl, list):
            plans.append(
                ADRPlan(
                    path=path,
                    adr_id=adr_id,
                    status="blocked",
                    note=f"implementation_tasks is not a list ({type(impl).__name__})",
                )
            )
            continue

        # Normalize entries to strings (frontmatter may yield non-string YAML
        # values for malformed ADRs; we treat those as unmatched titles).
        titles = [t if isinstance(t, str) else str(t) for t in impl]
        title_matches = match_titles(titles, tasks)

        unmatched = [m for m in title_matches if m.matched_task_id is None]
        if unmatched:
            plans.append(
                ADRPlan(
                    path=path,
                    adr_id=adr_id,
                    status="blocked",
                    title_matches=title_matches,
                    note=f"{len(unmatched)} of {len(titles)} unmatched",
                )
            )
            continue

        new_tasks = [m.matched_task_id for m in title_matches if m.matched_task_id is not None]
        plans.append(
            ADRPlan(
                path=path,
                adr_id=adr_id,
                status="ready",
                title_matches=title_matches,
                new_implementation_tasks=new_tasks,
            )
        )

    return plans


def _write_adr(path: Path, new_implementation_tasks: list[str]) -> None:
    """Rewrite an ADR's `implementation_tasks` frontmatter to the typed-id list."""
    post = frontmatter.load(path)
    post.metadata["implementation_tasks"] = new_implementation_tasks
    path.write_bytes(frontmatter.dumps(post).encode("utf-8") + b"\n")


def apply_run(plans: list[ADRPlan], *, write: bool) -> bool:
    """Execute --apply: write every `ready` ADR's frontmatter.

    Hard-fails (returns False, writes nothing) when any plan is `blocked`.
    `no-op` plans are skipped silently. Returns True on full success.
    """
    if any(p.status == "blocked" for p in plans):
        return False
    if not write:
        return True
    for plan in plans:
        if plan.status == "ready":
            _write_adr(plan.path, plan.new_implementation_tasks)
    return True


# --- CLI output -------------------------------------------------------------


def _print_plan(plans: list[ADRPlan], verbose: bool, mode: str) -> None:
    print(f"{mode}: docgraph-migrate-adr-tasks")
    print(f"  ADRs found:  {len(plans)}")
    print()

    counts = {"ready": 0, "no-op": 0, "blocked": 0}
    for plan in plans:
        counts[plan.status] += 1
        if plan.status == "no-op" and not verbose:
            continue

        print(f"{plan.adr_id}  STATUS: {plan.status}")
        if plan.status == "no-op":
            print(f"  {plan.note}")
        else:
            for m in plan.title_matches:
                if m.matched_task_id is None:
                    print(f"  {m.title!r}  ->  ???  UNMATCHED")
                else:
                    arrow_note = f"  ({m.cascade_level})" if m.cascade_level not in (None, "exact", "already_id") else ""
                    ambig = "  AMBIGUOUS-TIE" if m.ambiguous else ""
                    print(f"  {m.title!r}  ->  {m.matched_task_id}{arrow_note}{ambig}")
        print()

    print("SUMMARY")
    print(f"  ready to migrate:    {counts['ready']}")
    print(f"  already migrated:    {counts['no-op']} (no-op)")
    print(f"  blocked (unmatched): {counts['blocked']}")
    print()


def _print_dry_run_footer(blocked: int) -> None:
    if blocked:
        print(
            f"DRY-RUN: {blocked} ADR(s) BLOCKED. "
            f"Resolve unmatched titles and re-run with --apply."
        )
    else:
        print("DRY-RUN: clean. Re-run with --apply to write.")


def _print_apply_footer(plans: list[ADRPlan], success: bool) -> None:
    if not success:
        blocked = sum(1 for p in plans if p.status == "blocked")
        print(
            f"ABORTING: {blocked} ADR(s) have unmatched titles. NO FILES WRITTEN.\n"
            "Resolve unmatched titles in TASKS.md or ADR frontmatter, re-run with --apply."
        )
        return
    written = sum(1 for p in plans if p.status == "ready")
    print(f"{written} ADR(s) migrated.")


# --- entry point ------------------------------------------------------------


def _load_adr_paths(docs_dir: Path) -> list[Path]:
    """Walk docs_dir, return paths to all ADRs that parse with id=ADR-NNNN."""
    artifacts, _ = parse_directory(docs_dir)
    return sorted(a.source_path for a in artifacts if a.id.startswith("ADR-"))


def main(argv: list[str] | None = None) -> int:
    """Entry point for the `docgraph-migrate-adr-tasks` console script."""
    parser = argparse.ArgumentParser(
        prog="docgraph-migrate-adr-tasks",
        description=(
            "Migrate ADR implementation_tasks from string-titles to task-id format. "
            "Dry-run by default; pass --apply to write. Hard-fails on partial."
        ),
    )
    parser.add_argument("docs_dir", type=Path, help="Path to docs root (containing decisions/)")
    parser.add_argument("tasks_path", type=Path, help="Path to TASKS.md")
    parser.add_argument(
        "--apply", action="store_true",
        help="Write the migration. Default is dry-run.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print every ADR's status, including no-ops.",
    )
    args = parser.parse_args(argv)

    if not args.docs_dir.exists():
        print(f"docs_dir not found: {args.docs_dir}", file=sys.stderr)
        return 2
    if not args.tasks_path.exists():
        print(f"tasks_path not found: {args.tasks_path}", file=sys.stderr)
        return 2

    # Tasks are loaded with a default CorpusConfig; we only need title +
    # line_number for matching, not domain labels.
    cfg = CorpusConfig(name="migration", path=args.docs_dir)
    tasks, task_errors = parse_tasks_file(args.tasks_path, cfg)
    if task_errors:
        # Surface task parse errors but continue; the migration only needs
        # successfully parsed tasks.
        for err in task_errors:
            print(f"warning: {err}", file=sys.stderr)

    adr_paths = _load_adr_paths(args.docs_dir)
    if not adr_paths:
        print(f"no ADRs found under {args.docs_dir}/decisions/", file=sys.stderr)
        return 1

    plans = plan_run(adr_paths, tasks)

    if args.apply:
        _print_plan(plans, args.verbose, mode="APPLY")
        success = apply_run(plans, write=True)
        _print_apply_footer(plans, success)
        return 0 if success else 1
    else:
        _print_plan(plans, args.verbose, mode="DRY-RUN")
        blocked = sum(1 for p in plans if p.status == "blocked")
        _print_dry_run_footer(blocked)
        return 0  # dry-run always exits 0


if __name__ == "__main__":
    sys.exit(main())
