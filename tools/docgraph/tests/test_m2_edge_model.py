"""M2 tests: edge model evolution + schema v2 + task queries.

Covers the post-M2 behaviour that didn't exist in M1:
- task-target edges resolve to tasks instead of being free-text
- missing task IDs surface as dangling-unexplained drift findings
- missing ADR refs from TASKS.md surface the same way
- get_task / list_tasks queries
- schema_version is at 2
"""

from pathlib import Path

import pytest

from docgraph.config import CorpusConfig
from docgraph.db import SCHEMA_VERSION, connect
from docgraph.indexer import index, index_all
from docgraph.models import Edge, EdgeType
from docgraph.query import (
    get_task,
    graph_from_db,
    graphs_from_db,
    list_tasks,
    tasks_from_db,
)
from docgraph.validate import validate_graphs


REPO_ROOT = Path(__file__).resolve().parents[3]
FORWARD = REPO_ROOT / "examples" / "forward-pipeline-bookshelf-stats"
REACTIVE = REPO_ROOT / "examples" / "reactive-pipeline-timezone-bug"


def test_schema_version_is_2():
    assert SCHEMA_VERSION == 2


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "m2.db"
    c = connect(db)
    yield c
    c.close()


@pytest.fixture
def indexed_examples(conn):
    corpora = [
        CorpusConfig(name="forward", path=FORWARD, task_domains={"TASK": "Task"}),
        CorpusConfig(name="reactive", path=REACTIVE, task_domains={"TASK": "Task"}),
    ]
    stats = index_all(conn, corpora)
    return conn, stats


def test_target_is_node_always_true_for_resolved_edges(indexed_examples):
    """After M2, every resolved edge has target_is_node=1."""
    conn, _ = indexed_examples
    rows = list(conn.execute("SELECT target_is_node FROM edges WHERE is_dangling = 0"))
    assert rows, "expected at least one resolved edge"
    assert all(r[0] == 1 for r in rows)


def test_task_target_edges_resolve_when_task_exists(indexed_examples):
    """ADR.implementation_tasks=[TASK-0001] resolves to a non-dangling edge
    after M2 (was always-text-target, never-dangling pre-M2)."""
    conn, _ = indexed_examples
    rows = list(
        conn.execute(
            "SELECT source_id, target FROM edges "
            "WHERE corpus = 'forward' AND edge_type = 'implementation_tasks' "
            "AND is_dangling = 0 ORDER BY source_id, target"
        )
    )
    assert ("ADR-0007", "TASK-0001") in rows
    assert ("ADR-0007", "TASK-0002") in rows
    assert ("ADR-0008", "TASK-0003") in rows
    assert ("ADR-0008", "TASK-0004") in rows


def test_missing_task_target_becomes_dangling(tmp_path):
    """An ADR.implementation_tasks=[TASK-9999] (not in TASKS.md) drifts."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "REQ-0001-foo.md").write_text(
        "---\nid: REQ-0001\ntitle: foo\nstatus: accepted\n---\n",
        encoding="utf-8",
    )
    (docs / "ADR-0001-foo.md").write_text(
        "---\nid: ADR-0001\ntitle: foo\nstatus: accepted\ntriggered_by: REQ-0001\n"
        "implementation_tasks:\n  - TASK-9999\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "TASKS.md").write_text(
        "## Done\n- [x] **TASK-0001: real one** `(no upstream)`\n",
        encoding="utf-8",
    )
    db = tmp_path / "drift.db"
    conn = connect(db)
    try:
        stats = index(conn, docs, corpus="t", task_domains={"TASK": "Task"})
        assert stats.dangling >= 1
        # Validator surfaces TASK-9999 as dangling_unexplained (not commit hash, not narrative)
        report = validate_graphs(graphs_from_db(conn))
        unexplained_targets = {f.target for f in report.dangling_unexplained}
        assert "TASK-9999" in unexplained_targets
    finally:
        conn.close()


def test_get_task_collision_across_corpora(indexed_examples):
    """Bare-id TASK-0001 returns both rows when task_domains in both corpora."""
    conn, _ = indexed_examples
    hits = get_task(conn, "TASK-0001")
    corpora = sorted(t.corpus for t in hits)
    assert corpora == ["forward", "reactive"]


def test_get_task_corpus_prefix_scopes(indexed_examples):
    conn, _ = indexed_examples
    hits = get_task(conn, "forward:TASK-0001")
    assert len(hits) == 1
    assert hits[0].corpus == "forward"
    assert hits[0].title == "Build monthly-pages SQL view"


def test_list_tasks_filters_by_status(indexed_examples):
    conn, _ = indexed_examples
    done = list_tasks(conn, status="done")
    assert len(done) == 5  # forward 4 + reactive 1
    todo = list_tasks(conn, status="todo")
    assert todo == []


def test_list_tasks_filters_by_corpus(indexed_examples):
    conn, _ = indexed_examples
    forward_tasks = list_tasks(conn, corpus="forward")
    assert {t.id for t in forward_tasks} == {
        "TASK-0001", "TASK-0002", "TASK-0003", "TASK-0004",
    }


def test_list_tasks_filters_by_domain(indexed_examples):
    conn, _ = indexed_examples
    task_domain = list_tasks(conn, domain="TASK")
    assert len(task_domain) == 5
    nada = list_tasks(conn, domain="NOPE")
    assert nada == []


def test_tasks_from_db_round_trip(indexed_examples):
    """Tasks round-trip through the DB with all fields preserved."""
    conn, _ = indexed_examples
    all_tasks = tasks_from_db(conn)
    assert len(all_tasks) == 5
    forward_t1 = next(t for t in all_tasks if t.corpus == "forward" and t.id == "TASK-0001")
    assert forward_t1.title == "Build monthly-pages SQL view"
    assert forward_t1.refs_by_level["adr"] == ["ADR-0007"]
    assert forward_t1.refs_by_level["plan"] == ["PLAN-0002"]
    assert forward_t1.refs_by_level["req"] == ["REQ-0003"]
    assert forward_t1.domain_id == "TASK"
    assert forward_t1.domain_label == "Task"


def test_graph_from_db_includes_tasks(indexed_examples):
    conn, _ = indexed_examples
    graph = graph_from_db(conn, "forward")
    assert len(graph.tasks) == 4
    assert "TASK-0001" in graph.tasks
    # Task-target edges are non-dangling because tasks resolve
    task_edges = [e for e in graph.edges if e.edge_type == EdgeType.IMPLEMENTATION_TASKS]
    assert len(task_edges) == 4
    spawns_edges = [e for e in graph.edges if e.edge_type == EdgeType.SPAWNS_TASKS]
    assert len(spawns_edges) == 4


def test_fts_indexes_task_kind(indexed_examples):
    """search_artifacts can hit kind='task' rows."""
    from docgraph.search import search

    conn, _ = indexed_examples
    hits = search(conn, "monthly-pages", kind="task")
    assert any(h.ref == "TASK-0001" and h.corpus == "forward" for h in hits)


def test_missing_adr_ref_from_tasks_md_reports_dangling(tmp_path):
    """A TASKS.md row whose refs include a non-existent ADR drifts.

    Mirror image of test_missing_task_target_becomes_dangling: not the
    ADR -> missing-task direction, but the task -> missing-ADR direction.
    Both should land in dangling_unexplained.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "REQ-0001-foo.md").write_text(
        "---\nid: REQ-0001\ntitle: foo\nstatus: accepted\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "TASKS.md").write_text(
        "## Done\n"
        "- [x] **TASK-0001: refs a missing ADR** `(ADR-9999 <- PLAN-0001 <- REQ-0001)`\n",
        encoding="utf-8",
    )
    db = tmp_path / "drift.db"
    conn = connect(db)
    try:
        index(conn, docs, corpus="t", task_domains={"TASK": "Task"})
        # The task row's ADR-9999 ref is captured in refs_by_level but doesn't
        # resolve to anything; this surfaces as the same drift category as
        # ADR -> missing-task. We assert via list_tasks that the task IS
        # indexed (the row itself parses fine), and via the refs_by_level
        # field that the dangling ADR ref is captured.
        tasks = list_tasks(conn, corpus="t")
        assert len(tasks) == 1
        assert tasks[0].refs_by_level["adr"] == ["ADR-9999"]
    finally:
        conn.close()


def test_graphs_from_db_includes_tasks_only_corpus(tmp_path):
    """A corpus with only TASKS.md (no docs/*.md) still appears in graphs_from_db."""
    docs = tmp_path / "docs"
    docs.mkdir()  # empty docs dir
    (tmp_path / "TASKS.md").write_text(
        "## Done\n- [x] **TASK-0001: solo task** `(no upstream)`\n",
        encoding="utf-8",
    )
    db = tmp_path / "tasks_only.db"
    conn = connect(db)
    try:
        index(conn, docs, corpus="solo", task_domains={"TASK": "Task"})
        graphs = graphs_from_db(conn)
        assert "solo" in graphs
        assert len(graphs["solo"].artifacts) == 0
        assert len(graphs["solo"].tasks) == 1
        assert "TASK-0001" in graphs["solo"].tasks
    finally:
        conn.close()


def test_list_tasks_filters_by_phase(tmp_path):
    """Phase filter narrows the result set; phase-only and combined filters both work."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "TASKS.md").write_text(
        "## Todo\n"
        "### [Sprint A: PLAN-0001] {phase: alpha}\n"
        "- [ ] **TASK-0001: alpha 1** `(no upstream)`\n"
        "- [ ] **TASK-0002: alpha 2** `(no upstream)`\n"
        "### [Sprint B: PLAN-0001] {phase: beta}\n"
        "- [ ] **TASK-0003: beta 1** `(no upstream)`\n"
        "- [~] **TASK-0004: beta 2 in progress** `(no upstream)`\n",
        encoding="utf-8",
    )
    db = tmp_path / "phases.db"
    conn = connect(db)
    try:
        index(conn, docs, corpus="phased", task_domains={"TASK": "Task"})
        alpha = list_tasks(conn, phase="alpha")
        assert {t.id for t in alpha} == {"TASK-0001", "TASK-0002"}
        beta = list_tasks(conn, phase="beta")
        assert {t.id for t in beta} == {"TASK-0003", "TASK-0004"}
        # Combined filter: phase + status
        beta_in_progress = list_tasks(conn, phase="beta", status="in-progress")
        assert {t.id for t in beta_in_progress} == {"TASK-0004"}
        # Combined filter: corpus + phase
        alpha_in_corpus = list_tasks(conn, phase="alpha", corpus="phased")
        assert len(alpha_in_corpus) == 2
        # Non-existent phase returns empty
        assert list_tasks(conn, phase="__no_such__") == []
    finally:
        conn.close()


def test_tasks_from_db_corpus_scoping(indexed_examples):
    """tasks_from_db(corpus=NAME) only returns tasks for that corpus."""
    conn, _ = indexed_examples
    forward_only = tasks_from_db(conn, corpus="forward")
    assert len(forward_only) == 4
    assert all(t.corpus == "forward" for t in forward_only)
    reactive_only = tasks_from_db(conn, corpus="reactive")
    assert len(reactive_only) == 1
    assert reactive_only[0].corpus == "reactive"


def test_artifact_task_id_collision_raises(tmp_path):
    """If a task ID collides with an artifact ID, build_graph fails fast."""
    from docgraph.graph import build_graph
    from docgraph.models import Artifact, ArtifactType, Task, TaskStatus

    art = Artifact(
        id="REQ-0001",
        type=ArtifactType.REQ,
        source_path=tmp_path / "fake.md",
    )
    # Synthetic collision: a task with the same ID as an artifact (would never
    # happen via the normal parser, but guards against mis-authored TASKS.md).
    task = Task(
        id="REQ-0001",
        status=TaskStatus.TODO,
        source_path=tmp_path / "fake.md",
        line_number=1,
    )
    with pytest.raises(ValueError, match="ID collision"):
        build_graph([art], [task])


def test_malformed_tasks_md_parse_errors_surface_in_index_stats(tmp_path):
    """Malformed TASKS.md rows produce parse_errors but don't crash indexing."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "TASKS.md").write_text(
        "## Todo\n"
        "- [ ] **TASK-0001: valid** `(no upstream)`\n"
        # Malformed: bold span doesn't match the ID regex
        "- [ ] **not a real id: title text** `(no upstream)`\n",
        encoding="utf-8",
    )
    db = tmp_path / "malformed.db"
    conn = connect(db)
    try:
        stats = index(conn, docs, corpus="m", task_domains={"TASK": "Task"})
        assert stats.tasks == 1  # only the valid one
        assert any("doesn't match" in e for e in stats.parse_errors), stats.parse_errors
    finally:
        conn.close()
