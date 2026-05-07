"""Tests for ADR-0008 + ADR-0009: KB artifacts as typed graph nodes.

Covers REQ-0005 acceptance criteria:
- AC-1, AC-2: parser recognises KB-NNNN ids; required frontmatter validated
- AC-3: KB.explains list resolves into EXPLAINS edges (resolved or dangling)
- AC-4: walk_chain fans out KB descendants of any artifact step at depth+1
- AC-5: stale_knowledge finding category for KB past freshness threshold
- AC-6: backwards compat — files without `id: KB-NNNN` stay FTS-only
"""

from datetime import date, timedelta
from pathlib import Path

from docgraph.graph import build_graph, walk_chain
from docgraph.models import Artifact, ArtifactType, EdgeType
from docgraph.parser import parse_file
from docgraph.validate import validate_graph


def _write(path: Path, frontmatter: dict, body: str = "") -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body
    path.write_text(text, encoding="utf-8")


# --- AC-1, AC-2: parser + KB type ----------------------------------------


def test_parser_recognises_kb_id(tmp_path):
    p = tmp_path / "KB-0007-howto.md"
    _write(p, {
        "id": "KB-0007", "title": "How to use the harness",
        "kind": "howto", "status": "active",
        "last_verified": "2026-05-07",
    })
    a = parse_file(p)
    assert a is not None
    assert a.type == ArtifactType.KB
    assert a.id == "KB-0007"


def test_parser_kb_with_lowercase_suffix(tmp_path):
    """KB-NNNNa shape (sub-article) is valid per the framework ID regex."""
    p = tmp_path / "KB-0007a.md"
    _write(p, {
        "id": "KB-0007a", "title": "Harness howto, batch mode",
        "kind": "howto", "status": "active",
        "last_verified": "2026-05-07",
    })
    a = parse_file(p)
    assert a is not None
    assert a.id == "KB-0007a"
    assert a.type == ArtifactType.KB


def test_parser_skips_untyped_knowledge_file(tmp_path):
    """AC-6 backwards compat: a markdown file with frontmatter but no
    KB-NNNN id stays out of the typed graph."""
    p = tmp_path / "old-knowledge.md"
    _write(p, {"title": "Some legacy notes"})
    a = parse_file(p)
    assert a is None


# --- AC-3: EXPLAINS edges -------------------------------------------------


def _mk_artifact(id: str, type_: ArtifactType, fm: dict, *, tmp_path: Path) -> Artifact:
    fm = dict(fm)
    fm.setdefault("id", id)
    return Artifact(id=id, type=type_, source_path=tmp_path / f"{id}.md", frontmatter=fm)


def test_explains_resolves_to_edge(tmp_path):
    """KB.explains: [ADR-0001] yields a resolved EXPLAINS edge."""
    adr = _mk_artifact("ADR-0001", ArtifactType.ADR, {}, tmp_path=tmp_path)
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "howto", "status": "active",
            "last_verified": "2026-05-07",
            "explains": ["ADR-0001"],
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([adr, kb])
    explains_edges = [e for e in graph.edges if e.edge_type == EdgeType.EXPLAINS]
    assert len(explains_edges) == 1
    assert explains_edges[0].source_id == "KB-0001"
    assert explains_edges[0].target == "ADR-0001"


def test_explains_unresolved_target_is_dangling(tmp_path):
    """KB.explains: [ADR-9999] (missing) lands in dangling_edges."""
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "howto", "status": "active",
            "last_verified": "2026-05-07",
            "explains": ["ADR-9999"],
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([kb])
    dangling = [e for e in graph.dangling_edges if e.edge_type == EdgeType.EXPLAINS]
    assert len(dangling) == 1
    assert dangling[0].target == "ADR-9999"


# --- AC-4: walk_chain knowledge fan-out -----------------------------------


def test_walk_chain_fans_out_kb_descendants(tmp_path):
    """ADR-0008: walk_chain from any artifact appends KB articles whose
    `explains` list contains that artifact's id, at parent_depth + 1."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001", ArtifactType.ADR,
        {"triggered_by": "PLAN-0001"}, tmp_path=tmp_path,
    )
    kb_howto = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "howto", "status": "active",
            "last_verified": "2026-05-07",
            "explains": ["ADR-0001", "PLAN-0001"],
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([plan, adr, kb_howto])
    chain = walk_chain(graph, "ADR-0001")

    knowledge_steps = [s for s in chain if s.node_kind == "knowledge"]
    # KB-0001 explains both ADR-0001 and PLAN-0001 → two ChainSteps,
    # one per parent the walker reaches.
    assert len(knowledge_steps) == 2
    assert all(s.artifact_id == "KB-0001" for s in knowledge_steps)
    assert all(s.via_edge == "explained_by ←" for s in knowledge_steps)
    # Each KB step sits at parent_depth + 1
    adr_step = next(s for s in chain if s.artifact_id == "ADR-0001")
    plan_step = next(s for s in chain if s.artifact_id == "PLAN-0001")
    kb_depths = sorted(s.depth for s in knowledge_steps)
    assert kb_depths == sorted([adr_step.depth + 1, plan_step.depth + 1])


def test_walk_chain_no_kb_means_no_knowledge_steps(tmp_path):
    """ADR-0008: when no KB articles reference the chain, the chain shape
    matches pre-ADR-0008 callers."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    adr = _mk_artifact(
        "ADR-0001", ArtifactType.ADR,
        {"triggered_by": "PLAN-0001"}, tmp_path=tmp_path,
    )
    graph = build_graph([plan, adr])
    chain = walk_chain(graph, "ADR-0001")
    assert all(s.node_kind == "artifact" for s in chain)


# --- AC-5: stale_knowledge validator finding ------------------------------


def test_stale_knowledge_finding_for_old_kb(tmp_path):
    """ADR-0009: a KB whose last_verified is past the threshold lands in
    stale_knowledge."""
    old_date = (date.today() - timedelta(days=120)).isoformat()
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "howto", "status": "active",
            "last_verified": old_date,
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([kb])
    report = validate_graph(graph, corpus="x", knowledge_freshness_days=90)
    assert len(report.stale_knowledge) == 1
    f = report.stale_knowledge[0]
    assert f.kb_id == "KB-0001"
    assert f.days_stale > 90
    assert f.kind == "howto"


def test_stale_knowledge_skips_fresh_kb(tmp_path):
    """A KB updated within the threshold doesn't trigger the finding."""
    fresh_date = (date.today() - timedelta(days=10)).isoformat()
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "runbook", "status": "active",
            "last_verified": fresh_date,
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([kb])
    report = validate_graph(graph, corpus="x", knowledge_freshness_days=90)
    assert report.stale_knowledge == []


def test_stale_knowledge_skips_superseded_kb(tmp_path):
    """ADR-0009: superseded / deprecated KBs are explicitly retired and
    never flagged as stale, regardless of last_verified age."""
    old_date = (date.today() - timedelta(days=500)).isoformat()
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "playbook", "status": "superseded",
            "last_verified": old_date,
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([kb])
    report = validate_graph(graph, corpus="x", knowledge_freshness_days=90)
    assert report.stale_knowledge == []


def test_stale_knowledge_disabled_when_threshold_zero(tmp_path):
    """ADR-0009: knowledge_freshness_days=0 disables the check (archival)."""
    old_date = (date.today() - timedelta(days=1000)).isoformat()
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "lineage", "status": "active",
            "last_verified": old_date,
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([kb])
    report = validate_graph(graph, corpus="x", knowledge_freshness_days=0)
    assert report.stale_knowledge == []


def test_stale_knowledge_does_not_flip_has_errors(tmp_path):
    """ADR-0009: stale_knowledge is informational; has_errors stays False
    when stale_knowledge is the only finding."""
    old_date = (date.today() - timedelta(days=200)).isoformat()
    kb = _mk_artifact(
        "KB-0001", ArtifactType.KB,
        {
            "kind": "howto", "status": "active",
            "last_verified": old_date,
        },
        tmp_path=tmp_path,
    )
    graph = build_graph([kb])
    report = validate_graph(graph, corpus="x", knowledge_freshness_days=90)
    assert len(report.stale_knowledge) == 1
    assert report.has_errors is False
