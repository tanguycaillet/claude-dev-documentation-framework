"""Tests for ADR-0007: legacy_text_titles dangling-edge category.

Covers REQ-0004 acceptance criteria:
- AC-1: free-text in implementation_tasks / spawns_tasks classifies as legacy
- AC-2: legacy_text_titles does NOT count toward has_errors
- AC-3: ID-shape-but-missing target keeps classifying as unexplained
- AC-4: validate_graphs preserves the new field across multi-corpus merge
"""

from pathlib import Path

import pytest

from docgraph.graph import build_graph
from docgraph.models import Artifact, ArtifactType, Task, TaskStatus
from docgraph.validate import validate_graph, validate_graphs


def _mk_artifact(id: str, type: ArtifactType, frontmatter: dict, *, tmp_path: Path) -> Artifact:
    fm = dict(frontmatter)
    fm.setdefault("id", id)
    return Artifact(
        id=id,
        type=type,
        source_path=tmp_path / f"{id}.md",
        frontmatter=fm,
    )


def _mk_task(id: str, *, tmp_path: Path) -> Task:
    return Task(
        id=id,
        title=f"Task {id}",
        status=TaskStatus.TODO,
        source_path=tmp_path / "TASKS.md",
        line_number=1,
    )


def test_free_text_implementation_tasks_classifies_as_legacy(tmp_path):
    """ADR-0007 / AC-1: ADR.implementation_tasks holding a free-text string
    (no leading task-ID) classifies as legacy_text_titles, NOT
    dangling_unexplained."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001", ArtifactType.ADR,
        {
            "triggered_by": "PLAN-0001",
            "implementation_tasks": [
                "Audit all thermal-value passing for unit consistency",
                "Document rule in CLAUDE.md",
            ],
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([plan, adr])
    report = validate_graph(graph, corpus="ef")

    legacy_targets = {f.target for f in report.legacy_text_titles}
    assert "Audit all thermal-value passing for unit consistency" in legacy_targets
    assert "Document rule in CLAUDE.md" in legacy_targets
    # And these should NOT be in dangling_unexplained
    unexplained_targets = {f.target for f in report.dangling_unexplained}
    assert not (legacy_targets & unexplained_targets)


def test_free_text_spawns_tasks_classifies_as_legacy(tmp_path):
    """ADR-0007 / AC-1: PLAN.spawns_tasks holding a free-text string
    classifies as legacy_text_titles via the SPAWNS_TASKS edge type."""
    req = _mk_artifact(
        "REQ-0001", ArtifactType.REQ,
        {"implemented_by": {"plan": "PLAN-0001"}},
        tmp_path=tmp_path,
    )
    plan = _mk_artifact(
        "PLAN-0001", ArtifactType.PLAN,
        {"spawns_tasks": ["Implement parser", "Build the SQL view"]},
        tmp_path=tmp_path,
    )
    graph = build_graph([req, plan])
    report = validate_graph(graph, corpus="ef")

    legacy_targets = {f.target for f in report.legacy_text_titles}
    assert "Implement parser" in legacy_targets
    assert "Build the SQL view" in legacy_targets
    edge_types = {f.edge_type for f in report.legacy_text_titles}
    assert "spawns_tasks" in edge_types


def test_id_shape_missing_task_stays_unexplained(tmp_path):
    """ADR-0007 / AC-3: a target that DOES match the task-ID regex but
    doesn't resolve (typed-shaped reference to a non-existent task)
    keeps classifying as dangling_unexplained — that's a real broken ref."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001", ArtifactType.ADR,
        {
            "triggered_by": "PLAN-0001",
            "implementation_tasks": ["TASK-9999"],
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([plan, adr])
    report = validate_graph(graph, corpus="ef")

    unexplained = {f.target for f in report.dangling_unexplained}
    assert "TASK-9999" in unexplained
    legacy = {f.target for f in report.legacy_text_titles}
    assert "TASK-9999" not in legacy
    # Real broken ref still flips has_errors
    assert report.has_errors is True


def test_legacy_text_titles_do_not_flip_has_errors(tmp_path):
    """ADR-0007 / AC-2: a corpus whose ONLY drift is legacy free-text
    titles validates with has_errors=False. Drift visibility, not
    gatekeeping."""
    plan = _mk_artifact(
        "PLAN-0001", ArtifactType.PLAN,
        {"spawns_tasks": ["legacy free-text outline"]},
        tmp_path=tmp_path,
    )
    plan.status = "accepted"
    graph = build_graph([plan])
    report = validate_graph(graph, corpus="ef")

    assert len(report.legacy_text_titles) >= 1
    assert report.has_errors is False, "legacy_text_titles must NOT count toward has_errors"


def test_validate_graphs_merges_legacy_text_titles(tmp_path):
    """ADR-0007 / AC-4: multi-corpus validate_graphs merges the new field."""
    plan_a = _mk_artifact(
        "PLAN-0001", ArtifactType.PLAN,
        {"spawns_tasks": ["legacy a"]}, tmp_path=tmp_path,
    )
    plan_b = _mk_artifact(
        "PLAN-0001", ArtifactType.PLAN,
        {"spawns_tasks": ["legacy b"]}, tmp_path=tmp_path,
    )
    graphs = {
        "corpus_a": build_graph([plan_a]),
        "corpus_b": build_graph([plan_b]),
    }
    report = validate_graphs(graphs)

    targets = {f.target for f in report.legacy_text_titles}
    assert {"legacy a", "legacy b"} <= targets
    corpora = {f.corpus for f in report.legacy_text_titles}
    assert corpora == {"corpus_a", "corpus_b"}


def test_other_edge_types_with_non_id_target_stay_unexplained(tmp_path):
    """ADR-0007: legacy_text_titles is scoped to IMPLEMENTATION_TASKS /
    SPAWNS_TASKS only. A non-ID target on a triggered_by, supersedes,
    resolved_by, or implemented_by_plan edge is a real authoring bug
    and stays in dangling_unexplained."""
    # An ADR with a totally bogus triggered_by that doesn't shape like an ID
    # AND isn't a hex hash AND isn't a "this SCN..." narrative.
    adr = _mk_artifact(
        "ADR-0001", ArtifactType.ADR,
        {"triggered_by": "some bogus authoring drift here"},
        tmp_path=tmp_path,
    )
    graph = build_graph([adr])
    report = validate_graph(graph, corpus="ef")

    unexplained = {f.target for f in report.dangling_unexplained}
    legacy = {f.target for f in report.legacy_text_titles}
    assert "some bogus authoring drift here" in unexplained
    assert "some bogus authoring drift here" not in legacy
