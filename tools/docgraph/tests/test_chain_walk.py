"""Tests for ADR-0005: walk_chain fans out task descendants of any
ADR/PLAN reached during traversal.

Covers REQ-0002 acceptance criteria:
- AC-1: walk_chain follows implementation_tasks / spawns_tasks edges
- AC-2: ChainStep.node_kind discriminates "artifact" vs "task"
- AC-4: synthetic-fixture coverage of both fan-out edge types
"""

from pathlib import Path

import pytest

from docgraph.graph import build_graph, walk_chain
from docgraph.models import Artifact, ArtifactType, Task, TaskStatus


def _mk_artifact(
    artifact_id: str,
    artifact_type: ArtifactType,
    frontmatter: dict | None = None,
    *,
    tmp_path: Path,
) -> Artifact:
    fm = dict(frontmatter or {})
    fm.setdefault("id", artifact_id)
    return Artifact(
        id=artifact_id,
        type=artifact_type,
        source_path=tmp_path / f"{artifact_id}.md",
        frontmatter=fm,
    )


def _mk_task(task_id: str, *, tmp_path: Path, title: str | None = None) -> Task:
    return Task(
        id=task_id,
        title=title or f"Task {task_id}",
        status=TaskStatus.TODO,
        source_path=tmp_path / "TASKS.md",
        line_number=1,
    )


def test_chain_walk_fans_out_adr_implementation_tasks(tmp_path):
    """ADR-0005 / AC-1, AC-2: an ADR's implementation_tasks become task
    ChainSteps at parent_depth + 1 with node_kind='task', emitted
    contiguously immediately after the parent ADR step."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001",
        ArtifactType.ADR,
        {
            "triggered_by": "PLAN-0001",
            "implementation_tasks": ["TASK-0001", "TASK-0002"],
        },
        tmp_path=tmp_path,
    )
    t1 = _mk_task("TASK-0001", tmp_path=tmp_path)
    t2 = _mk_task("TASK-0002", tmp_path=tmp_path)

    graph = build_graph([plan, adr], [t1, t2])
    chain = walk_chain(graph, "ADR-0001")

    # Shape + node_kind + via_edge presence
    by_id = [(s.artifact_id, s.node_kind, s.via_edge) for s in chain]
    assert ("ADR-0001", "artifact", None) in by_id
    assert ("PLAN-0001", "artifact", "triggered_by →") in by_id
    assert ("TASK-0001", "task", "implementation_tasks →") in by_id
    assert ("TASK-0002", "task", "implementation_tasks →") in by_id

    # Ordering / adjacency: task fan-out for ADR-0001 is contiguous and
    # immediately follows the ADR step in declared order; tasks do not
    # reappear later in the chain.
    ids = [s.artifact_id for s in chain]
    adr_index = ids.index("ADR-0001")
    expected_task_ids = ["TASK-0001", "TASK-0002"]
    assert ids[adr_index + 1 : adr_index + 1 + len(expected_task_ids)] == expected_task_ids
    remaining = ids[adr_index + 1 + len(expected_task_ids):]
    assert not any(t in remaining for t in expected_task_ids)

    # Depth: task steps at parent_depth + 1
    adr_step = next(s for s in chain if s.artifact_id == "ADR-0001")
    task_steps = [s for s in chain if s.node_kind == "task"]
    assert all(s.depth == adr_step.depth + 1 for s in task_steps)


def test_chain_walk_fans_out_plan_spawns_tasks(tmp_path):
    """ADR-0005 / AC-1: a PLAN reached during the walk fans out its
    spawns_tasks at parent_depth + 1 with via_edge='spawns_tasks ->'."""
    req = _mk_artifact(
        "REQ-0001",
        ArtifactType.REQ,
        {"implemented_by": {"plan": "PLAN-0001"}},
        tmp_path=tmp_path,
    )
    plan = _mk_artifact(
        "PLAN-0001",
        ArtifactType.PLAN,
        {"spawns_tasks": ["TASK-0001", "TASK-0002"]},
        tmp_path=tmp_path,
    )
    t1 = _mk_task("TASK-0001", tmp_path=tmp_path)
    t2 = _mk_task("TASK-0002", tmp_path=tmp_path)

    graph = build_graph([req, plan], [t1, t2])
    chain = walk_chain(graph, "PLAN-0001")

    plan_step = next(s for s in chain if s.artifact_id == "PLAN-0001")
    spawned = [s for s in chain if s.via_edge == "spawns_tasks →"]

    assert {s.artifact_id for s in spawned} == {"TASK-0001", "TASK-0002"}
    assert all(s.node_kind == "task" for s in spawned)
    assert all(s.depth == plan_step.depth + 1 for s in spawned)


def test_chain_walk_without_tasks_is_backwards_compatible(tmp_path):
    """ADR-0005: when no ADR/PLAN reached has task children, the chain
    shape matches pre-fan-out callers (only artifact steps, all
    node_kind='artifact')."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001",
        ArtifactType.ADR,
        {"triggered_by": "PLAN-0001"},
        tmp_path=tmp_path,
    )

    graph = build_graph([plan, adr])
    chain = walk_chain(graph, "ADR-0001")

    assert [s.artifact_id for s in chain] == ["ADR-0001", "PLAN-0001"]
    assert all(s.node_kind == "artifact" for s in chain)
    # depth is monotonic, no fan-out gaps
    assert [s.depth for s in chain] == [0, 1]


def test_chain_walk_skips_missing_task_targets(tmp_path):
    """ADR-0005: when an ADR's implementation_tasks references a task
    not present in the task index (e.g. mid-edit corpus state), the
    walk silently skips the missing entry, includes the resolvable
    sibling, and completes without error.

    Pins the `if task is None: continue` branch in walk_chain.
    """
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001",
        ArtifactType.ADR,
        {
            "triggered_by": "PLAN-0001",
            # TASK-0001 exists in the graph; TASK-9999 does not.
            "implementation_tasks": ["TASK-0001", "TASK-9999"],
        },
        tmp_path=tmp_path,
    )
    only_real = _mk_task("TASK-0001", tmp_path=tmp_path)

    graph = build_graph([plan, adr], [only_real])
    chain = walk_chain(graph, "ADR-0001")

    task_ids = {s.artifact_id for s in chain if s.node_kind == "task"}
    assert task_ids == {"TASK-0001"}

    # Walk still produces the artifact spine intact -- missing task does
    # not interrupt traversal.
    artifact_ids = [s.artifact_id for s in chain if s.node_kind == "artifact"]
    assert artifact_ids == ["ADR-0001", "PLAN-0001"]
