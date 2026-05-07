"""Tests for ADR-0011: parse_errors finding category in validate_graph.

Covers REQ-0006 acceptance criteria:
- AC-2: ValidationReport.parse_errors as a finding category
- AC-3: validate_graph optional parse_errors parameter
- AC-5: parse_errors don't count toward has_errors
"""

from pathlib import Path

from docgraph.graph import build_graph
from docgraph.models import Artifact, ArtifactType
from docgraph.validate import ParseErrorFinding, validate_graph, validate_graphs


def _mk_artifact(id: str, type_: ArtifactType, fm: dict, *, tmp_path: Path) -> Artifact:
    fm = dict(fm)
    fm.setdefault("id", id)
    return Artifact(id=id, type=type_, source_path=tmp_path / f"{id}.md", frontmatter=fm)


def test_parse_errors_become_findings(tmp_path):
    """ADR-0011 / AC-3: validate_graph with parse_errors=[...] emits one
    ParseErrorFinding per string."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    graph = build_graph([plan])
    errors = [
        "/x/KB-0001.md: KB has invalid `kind='widget'`",
        "/x/KB-0002.md: KB missing required `last_verified` field",
    ]
    report = validate_graph(graph, corpus="ef", parse_errors=errors)
    assert len(report.parse_errors) == 2
    assert all(isinstance(f, ParseErrorFinding) for f in report.parse_errors)
    assert all(f.corpus == "ef" for f in report.parse_errors)
    assert "kind='widget'" in report.parse_errors[0].message
    assert "last_verified" in report.parse_errors[1].message


def test_parse_errors_empty_list_no_findings(tmp_path):
    """Empty / None parse_errors -> empty parse_errors findings."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    graph = build_graph([plan])
    for errs in (None, []):
        report = validate_graph(graph, corpus="ef", parse_errors=errs)
        assert report.parse_errors == []


def test_parse_errors_do_not_flip_has_errors(tmp_path):
    """ADR-0011 / AC-5: parse_errors are informational; a graph whose
    only finding is parse_errors validates with has_errors=False."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    graph = build_graph([plan])
    report = validate_graph(graph, corpus="ef", parse_errors=["e1", "e2"])
    assert len(report.parse_errors) == 2
    assert report.has_errors is False, "parse_errors must NOT count toward has_errors"


def test_validate_graphs_merges_parse_errors(tmp_path):
    """validate_graphs accepts a per-corpus parse_errors mapping and
    merges findings across corpora."""
    plan_a = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    plan_b = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    graphs = {"corpus_a": build_graph([plan_a]), "corpus_b": build_graph([plan_b])}
    parse_errors = {
        "corpus_a": ["KB-0001 invalid kind"],
        "corpus_b": ["yaml.YAMLError: bad indent"],
    }
    report = validate_graphs(graphs, parse_errors=parse_errors)
    assert len(report.parse_errors) == 2
    corpora = {f.corpus for f in report.parse_errors}
    assert corpora == {"corpus_a", "corpus_b"}


def test_validate_graphs_missing_corpus_in_errors_is_ok(tmp_path):
    """If parse_errors dict omits a corpus, that corpus contributes 0
    parse_errors findings (no KeyError)."""
    plan = _mk_artifact("PLAN-0001", ArtifactType.PLAN, {}, tmp_path=tmp_path)
    graphs = {"corpus_a": build_graph([plan]), "corpus_b": build_graph([plan])}
    # only corpus_a in the parse_errors dict
    parse_errors = {"corpus_a": ["a problem"]}
    report = validate_graphs(graphs, parse_errors=parse_errors)
    assert len(report.parse_errors) == 1
    assert report.parse_errors[0].corpus == "corpus_a"
