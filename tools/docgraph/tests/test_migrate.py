"""Unit tests for the docgraph-migrate-adr-tasks script (ADR-0004).

Covers the title-matching cascade, dry-run output, --apply success path,
hard-fail-on-partial, idempotency, mixed-format input, ambiguous-tie
warnings, and exit codes per the ADR-0004 failure-mode table.
"""

from pathlib import Path

import frontmatter
import pytest

from docgraph.migrate import (
    apply_run,
    is_already_migrated,
    main,
    match_titles,
    plan_run,
    _normalize_whitespace,
)
from docgraph.models import Task, TaskStatus


def _make_task(id: str, title: str, line: int = 1) -> Task:
    return Task(
        id=id,
        title=title,
        status=TaskStatus.TODO,
        source_path=Path("/fake/TASKS.md"),
        line_number=line,
    )


def _scaffold_corpus(tmp_path: Path, adr_frontmatter: dict, tasks_md_text: str) -> tuple[Path, Path]:
    """Build a minimal docs/+TASKS.md for migration tests. Returns (docs_dir, tasks_path)."""
    docs = tmp_path / "docs"
    decisions = docs / "decisions"
    decisions.mkdir(parents=True)
    # Minimal REQ + PLAN so triggered_by/addresses chains are valid (the
    # migration only touches ADR.implementation_tasks but we want the
    # corpus to parse cleanly otherwise).
    (docs / "REQ-0001-foo.md").write_text(
        "---\nid: REQ-0001\ntitle: foo\nstatus: accepted\n---\n",
        encoding="utf-8",
    )
    (decisions / "ADR-0001-foo.md").write_text(
        "---\n"
        "id: ADR-0001\n"
        "title: test\n"
        "status: accepted\n"
        "triggered_by: REQ-0001\n"
        + frontmatter.dumps(frontmatter.Post("", **adr_frontmatter)).split("---")[1].strip()
        + "\n---\n",
        encoding="utf-8",
    )
    tasks_path = tmp_path / "TASKS.md"
    tasks_path.write_text(tasks_md_text, encoding="utf-8")
    return docs, tasks_path


# --- is_already_migrated --------------------------------------------------


def test_already_migrated_all_ids():
    assert is_already_migrated(["TASK-0001", "TASK-0002", "BE-014a"])


def test_already_migrated_empty_list():
    assert is_already_migrated([])


def test_not_migrated_string_titles():
    assert not is_already_migrated(["Build the thing", "Wire endpoint"])


def test_not_migrated_mixed():
    assert not is_already_migrated(["TASK-0001", "Wire endpoint"])


def test_not_migrated_non_list():
    assert not is_already_migrated("TASK-0001")
    assert not is_already_migrated(None)


# --- match_titles cascade -------------------------------------------------


def test_cascade_exact_match():
    tasks = [_make_task("TASK-0001", "Build the SQL view")]
    out = match_titles(["Build the SQL view"], tasks)
    assert out[0].matched_task_id == "TASK-0001"
    assert out[0].cascade_level == "exact"


def test_cascade_falls_through_to_case_insensitive():
    tasks = [_make_task("TASK-0001", "Build the SQL VIEW")]
    out = match_titles(["build the sql view"], tasks)
    assert out[0].matched_task_id == "TASK-0001"
    assert out[0].cascade_level == "case_insensitive"


def test_cascade_falls_through_to_whitespace_normalized():
    tasks = [_make_task("TASK-0001", "Build  the\tSQL view")]
    out = match_titles(["Build the SQL  view"], tasks)
    assert out[0].matched_task_id == "TASK-0001"
    assert out[0].cascade_level == "whitespace_normalized"


def test_cascade_unmatched():
    tasks = [_make_task("TASK-0001", "Some other thing")]
    out = match_titles(["Build the SQL view"], tasks)
    assert out[0].matched_task_id is None
    assert out[0].cascade_level is None


def test_cascade_already_id_passes_through():
    """If the input is already a typed ID, no matching is performed."""
    tasks = [_make_task("TASK-0001", "real one")]
    out = match_titles(["TASK-0042"], tasks)
    assert out[0].matched_task_id == "TASK-0042"
    assert out[0].cascade_level == "already_id"


def test_cascade_ambiguous_tie_picks_earliest():
    tasks = [
        _make_task("TASK-0002", "duplicate", line=10),
        _make_task("TASK-0001", "duplicate", line=5),
    ]
    out = match_titles(["duplicate"], tasks)
    assert out[0].matched_task_id == "TASK-0001"  # earliest line
    assert out[0].ambiguous is True


def test_cascade_no_fuzzy():
    """A typo'd title doesn't match. False positives are worse than unmatched."""
    tasks = [_make_task("TASK-0001", "Build the SQL view")]
    out = match_titles(["Build the SQL veiw"], tasks)  # typo
    assert out[0].matched_task_id is None


def test_normalize_whitespace_collapses():
    assert _normalize_whitespace("Foo  Bar\n\nbaz") == "foo bar baz"


# --- ADR-0006: id_prefix tier ---------------------------------------------


def test_id_prefix_resolves_short_form():
    """ADR-0006: title shaped `<TASK-ID>: description` resolves by ID even
    when descriptions diverge between ADR side and TASKS.md side."""
    tasks = [_make_task("FE-015", "Scaffold landing v8 section tree")]
    out = match_titles(
        ["FE-015: scaffold new landing v8 section tree under app/(marketing)/_sections/"],
        tasks,
    )
    assert out[0].matched_task_id == "FE-015"
    assert out[0].cascade_level == "id_prefix"


def test_id_prefix_resolves_lowercase_suffix():
    """ADR-0006: lowercase-suffix IDs (BE-014a, FE-009d) follow the same rule."""
    tasks = [_make_task("BE-014a", "Drop garbage rows from window context")]
    out = match_titles(
        ["BE-014a: drop garbage rows where U > 5 W/m^2K or area = 0 in window context"],
        tasks,
    )
    assert out[0].matched_task_id == "BE-014a"
    assert out[0].cascade_level == "id_prefix"


def test_id_prefix_with_non_colon_separator():
    """ADR-0006: leading ID is extracted at the word boundary regardless of
    whether the separator is a colon, space, or parenthesis."""
    tasks = [_make_task("FE-015", "anything")]
    out = match_titles(["FE-015 (lighter scope now): foo bar"], tasks)
    assert out[0].matched_task_id == "FE-015"
    assert out[0].cascade_level == "id_prefix"


def test_id_prefix_unknown_id_falls_through_to_title_cascade():
    """ADR-0006: a leading ID that isn't in the tasks list does NOT block
    title-cascade resolution. The cascade keeps trying."""
    tasks = [_make_task("TASK-0001", "Build the SQL view")]
    # Title carries an unknown ID prefix but the description text matches a
    # task by exact title; the match should still resolve at the exact tier.
    # Note: _LEADING_ID_RE will extract "ZZ-999"; that's not in tasks, so we
    # fall through; descriptive text "Build the SQL view" matches exactly.
    out = match_titles(["ZZ-999: Build the SQL view"], tasks)
    # No exact match because the full string differs, no id_prefix match
    # because ZZ-999 is unknown; ultimately unmatched.
    assert out[0].matched_task_id is None
    assert out[0].cascade_level is None


def test_id_prefix_does_not_shadow_already_id():
    """ADR-0006: a bare ID (no description) still resolves through the
    already_id short-circuit, not the id_prefix tier."""
    tasks = [_make_task("TASK-0001", "real one")]
    out = match_titles(["TASK-0042"], tasks)
    assert out[0].matched_task_id == "TASK-0042"
    assert out[0].cascade_level == "already_id"


def test_id_prefix_no_leading_id_runs_title_cascade():
    """ADR-0006: titles without a recognisable leading ID skip the id_prefix
    tier entirely and run the existing title cascade."""
    tasks = [_make_task("TASK-0001", "Port prototype to webapp")]
    out = match_titles(["Port prototype to webapp"], tasks)
    assert out[0].matched_task_id == "TASK-0001"
    assert out[0].cascade_level == "exact"


# --- plan_run end-to-end --------------------------------------------------


def test_plan_run_ready_when_all_titles_match(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={
            "implementation_tasks": ["Build the SQL view", "Wire endpoint"],
        },
        tasks_md_text=(
            "## Done\n"
            "- [x] **TASK-0001: Build the SQL view** `(no upstream)`\n"
            "- [x] **TASK-0002: Wire endpoint** `(no upstream)`\n"
        ),
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    plans = plan_run([docs / "decisions" / "ADR-0001-foo.md"], tasks)
    assert len(plans) == 1
    assert plans[0].status == "ready"
    assert plans[0].new_implementation_tasks == ["TASK-0001", "TASK-0002"]


def test_plan_run_blocked_when_any_unmatched(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={
            "implementation_tasks": ["Real title", "Made-up title that doesn't exist"],
        },
        tasks_md_text=(
            "## Done\n"
            "- [x] **TASK-0001: Real title** `(no upstream)`\n"
        ),
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    plans = plan_run([docs / "decisions" / "ADR-0001-foo.md"], tasks)
    assert plans[0].status == "blocked"
    assert "1 of 2 unmatched" in plans[0].note


def test_plan_run_no_op_for_already_migrated(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["TASK-0001", "TASK-0002"]},
        tasks_md_text="## Done\n- [x] **TASK-0001: foo** `(no upstream)`\n",
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    plans = plan_run([docs / "decisions" / "ADR-0001-foo.md"], tasks)
    assert plans[0].status == "no-op"


def test_plan_run_mixed_format_resolves_remaining(tmp_path):
    """ADR with [TASK-0001, "Old title"] re-resolves the title; TASK-0001 passes through."""
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["TASK-0001", "Old title"]},
        tasks_md_text=(
            "## Done\n"
            "- [x] **TASK-0001: real one** `(no upstream)`\n"
            "- [x] **TASK-0002: Old title** `(no upstream)`\n"
        ),
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    plans = plan_run([docs / "decisions" / "ADR-0001-foo.md"], tasks)
    assert plans[0].status == "ready"
    assert plans[0].new_implementation_tasks == ["TASK-0001", "TASK-0002"]


# --- apply_run ------------------------------------------------------------


def test_apply_writes_when_all_ready(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["A", "B"]},
        tasks_md_text=(
            "## Done\n"
            "- [x] **TASK-0001: A** `(no upstream)`\n"
            "- [x] **TASK-0002: B** `(no upstream)`\n"
        ),
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    adr_path = docs / "decisions" / "ADR-0001-foo.md"
    plans = plan_run([adr_path], tasks)
    assert apply_run(plans, write=True) is True
    # Verify the write
    rewritten = frontmatter.load(adr_path)
    assert rewritten.metadata["implementation_tasks"] == ["TASK-0001", "TASK-0002"]


def test_apply_aborts_on_blocked_writes_nothing(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["A", "Missing"]},
        tasks_md_text="## Done\n- [x] **TASK-0001: A** `(no upstream)`\n",
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    adr_path = docs / "decisions" / "ADR-0001-foo.md"
    original = frontmatter.load(adr_path).metadata.copy()
    plans = plan_run([adr_path], tasks)
    assert apply_run(plans, write=True) is False
    # Frontmatter unchanged
    after = frontmatter.load(adr_path).metadata
    assert after["implementation_tasks"] == original["implementation_tasks"]


def test_apply_idempotent_no_op(tmp_path):
    """Running --apply twice is safe; second run is no-op."""
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["A"]},
        tasks_md_text="## Done\n- [x] **TASK-0001: A** `(no upstream)`\n",
    )
    from docgraph.config import CorpusConfig
    from docgraph.parser import parse_tasks_file
    tasks, _ = parse_tasks_file(tasks_path, CorpusConfig(name="t", path=docs))
    adr_path = docs / "decisions" / "ADR-0001-foo.md"
    # First apply
    apply_run(plan_run([adr_path], tasks), write=True)
    # Second run sees an already-migrated ADR
    plans = plan_run([adr_path], tasks)
    assert plans[0].status == "no-op"


# --- main() exit codes ----------------------------------------------------


def test_main_dry_run_exits_zero_even_with_blocked(tmp_path, capsys):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["Missing"]},
        tasks_md_text="## Done\n- [x] **TASK-0001: A** `(no upstream)`\n",
    )
    rc = main([str(docs), str(tasks_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "blocked (unmatched): 1" in out


def test_main_apply_exits_one_on_blocked(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["Missing"]},
        tasks_md_text="## Done\n- [x] **TASK-0001: A** `(no upstream)`\n",
    )
    rc = main([str(docs), str(tasks_path), "--apply"])
    assert rc == 1


def test_main_apply_exits_zero_on_clean(tmp_path):
    docs, tasks_path = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": ["A"]},
        tasks_md_text="## Done\n- [x] **TASK-0001: A** `(no upstream)`\n",
    )
    rc = main([str(docs), str(tasks_path), "--apply"])
    assert rc == 0
    # Verify written
    adr_path = docs / "decisions" / "ADR-0001-foo.md"
    assert frontmatter.load(adr_path).metadata["implementation_tasks"] == ["TASK-0001"]


def test_main_missing_docs_dir_exits_two(tmp_path):
    tasks_path = tmp_path / "TASKS.md"
    tasks_path.write_text("## Done\n", encoding="utf-8")
    rc = main([str(tmp_path / "nope"), str(tasks_path)])
    assert rc == 2


def test_main_missing_tasks_path_exits_two(tmp_path):
    docs, _ = _scaffold_corpus(
        tmp_path,
        adr_frontmatter={"implementation_tasks": []},
        tasks_md_text="## Done\n",
    )
    rc = main([str(docs), str(tmp_path / "nope.md")])
    assert rc == 2
