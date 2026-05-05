"""End-to-end smoke test: parse the framework's own example corpora,
index into a temp SQLite DB, exercise every read tool.

Catches regressions in the parser/indexer/query/search/validate pipeline
without needing a long fixture corpus.
"""

from pathlib import Path

import pytest

from docgraph.config import CorpusConfig
from docgraph.db import connect
from docgraph.indexer import index_all
from docgraph.query import get_artifact, graphs_from_db, list_artifacts
from docgraph.search import search
from docgraph.validate import validate_graphs


REPO_ROOT = Path(__file__).resolve().parents[3]
FORWARD = REPO_ROOT / "examples" / "forward-pipeline-bookshelf-stats"
REACTIVE = REPO_ROOT / "examples" / "reactive-pipeline-timezone-bug"


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "smoke.db"
    c = connect(db)
    yield c
    c.close()


@pytest.fixture
def indexed(conn):
    corpora = [
        CorpusConfig(name="forward", path=FORWARD),
        CorpusConfig(name="reactive", path=REACTIVE),
    ]
    stats = index_all(conn, corpora)
    return conn, stats


def test_index_counts(indexed):
    _, stats = indexed

    forward = stats["forward"]
    assert forward.artifacts == 4
    assert forward.dangling == 0
    assert forward.knowledge == 0
    assert forward.parse_errors == []

    reactive = stats["reactive"]
    assert reactive.artifacts == 2
    assert reactive.dangling == 0
    assert reactive.knowledge == 0
    assert reactive.parse_errors == []


def test_get_artifact_bare_id_finds_corpus(indexed):
    conn, _ = indexed
    rows = get_artifact(conn, "REQ-0003")
    assert len(rows) == 1
    assert rows[0].corpus == "forward"
    assert rows[0].title == "Monthly reading stats dashboard"


def test_get_artifact_corpus_prefix(indexed):
    conn, _ = indexed
    rows = get_artifact(conn, "reactive:ADR-0012")
    assert len(rows) == 1
    assert rows[0].corpus == "reactive"


def test_list_spans_corpora(indexed):
    conn, _ = indexed
    adrs = list_artifacts(conn, artifact_type="adr")
    assert {a.corpus for a in adrs} == {"forward", "reactive"}
    assert {a.id for a in adrs} == {"ADR-0007", "ADR-0008", "ADR-0012"}


def test_search_returns_corpus_tagged_hits(indexed):
    conn, _ = indexed
    hits = search(conn, "timezone", limit=5)
    assert hits, "expected at least one hit for 'timezone'"
    refs = {(h.corpus, h.ref) for h in hits}
    assert ("reactive", "ADR-0012") in refs
    assert ("reactive", "SCN-0007") in refs


def test_validate_graphs_clean(indexed):
    conn, _ = indexed
    report = validate_graphs(graphs_from_db(conn))
    assert not report.has_errors, report.model_dump()
