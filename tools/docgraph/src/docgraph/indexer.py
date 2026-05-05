"""Indexer: walks docs root(s), parses, persists artifacts + edges into SQLite.

Per-corpus full-refresh: each corpus's rows are deleted and rewritten on
reindex; other corpora are untouched. Idempotent within a corpus, read-only
against the corpus files.

Public surface:
    IndexStats                                              counts + errors
    index(conn, docs_root, *, corpus="default")             -> IndexStats
    index_all(conn, corpora)                                -> dict[name, IndexStats]
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from docgraph.config import CorpusConfig
from docgraph.graph import build_graph
from docgraph.parser import parse_directory, walk_knowledge


class IndexStats(BaseModel):
    artifacts: int = 0
    edges: int = 0
    dangling: int = 0
    knowledge: int = 0
    parse_errors: list[str] = Field(default_factory=list)


def index(
    conn: sqlite3.Connection,
    docs_root: Path,
    *,
    corpus: str = "default",
) -> IndexStats:
    """Walk `docs_root`, parse, persist into SQLite scoped to `corpus`.

    Per-corpus full-refresh: deletes only `WHERE corpus = ?` rows (across
    artifacts, edges via FK cascade, and FTS rows for both kinds). Other
    corpora's rows are untouched.

    Idempotent within a corpus, running twice leaves the DB in the same
    state with no row duplication.
    """
    artifacts, parse_errors = parse_directory(docs_root)
    graph = build_graph(artifacts)
    now = int(time.time())

    conn.execute("DELETE FROM artifacts WHERE corpus = ?", (corpus,))

    conn.executemany(
        """INSERT INTO artifacts
           (id, corpus, type, title, status, source_path, frontmatter, content, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                a.id,
                corpus,
                a.type.value,
                a.title,
                a.status,
                str(a.source_path),
                json.dumps(a.frontmatter, default=str),
                a.content,
                now,
            )
            for a in graph.artifacts.values()
        ],
    )

    edge_rows = [
        (
            e.source_id,
            corpus,
            e.target,
            e.edge_type.value,
            1 if e.target_is_artifact else 0,
            0,
        )
        for e in graph.edges
    ] + [
        (e.source_id, corpus, e.target, e.edge_type.value, 1, 1)
        for e in graph.dangling_edges
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO edges
           (source_id, corpus, target, edge_type, target_is_artifact, is_dangling)
           VALUES (?, ?, ?, ?, ?, ?)""",
        edge_rows,
    )

    conn.execute(
        "DELETE FROM fts_artifacts WHERE kind = 'typed' AND corpus = ?",
        (corpus,),
    )
    conn.executemany(
        "INSERT INTO fts_artifacts(ref, kind, corpus, title, content) "
        "VALUES (?, 'typed', ?, ?, ?)",
        [(a.id, corpus, a.title, a.content) for a in graph.artifacts.values()],
    )

    knowledge, kn_errors = walk_knowledge(docs_root)
    conn.execute(
        "DELETE FROM fts_artifacts WHERE kind = 'knowledge' AND corpus = ?",
        (corpus,),
    )
    conn.executemany(
        "INSERT INTO fts_artifacts(ref, kind, corpus, title, content) "
        "VALUES (?, 'knowledge', ?, ?, ?)",
        [(k.slug, corpus, k.title, k.content) for k in knowledge],
    )

    conn.commit()

    return IndexStats(
        artifacts=len(graph.artifacts),
        edges=len(graph.edges),
        dangling=len(graph.dangling_edges),
        knowledge=len(knowledge),
        parse_errors=parse_errors + kn_errors,
    )


def index_all(
    conn: sqlite3.Connection,
    corpora: Iterable[CorpusConfig],
) -> dict[str, IndexStats]:
    """Run `index()` for every corpus, return per-corpus stats keyed by name."""
    return {
        c.name: index(conn, c.path, corpus=c.name)
        for c in corpora
    }
