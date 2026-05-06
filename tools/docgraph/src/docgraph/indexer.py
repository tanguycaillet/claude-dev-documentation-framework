"""Indexer: walks docs root(s), parses, persists artifacts + tasks + edges into SQLite.

Per-corpus full-refresh: each corpus's rows are deleted and rewritten on
reindex; other corpora are untouched. Idempotent within a corpus, read-only
against the corpus files.

After M2: also walks `<docs_root>/../TASKS.md` (sibling to the docs/
directory) when present, parses it via parse_tasks_file, and persists
tasks alongside artifacts. Tasks become resolvable graph nodes for the
edge-resolution pass.

Public surface:
    IndexStats                                                                counts + errors
    index(conn, docs_root, *, corpus, task_domains, tasks_path)               -> IndexStats
    index_all(conn, corpora)                                                  -> dict[name, IndexStats]
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from docgraph.config import CorpusConfig
from docgraph.graph import build_graph
from docgraph.models import Task
from docgraph.parser import parse_directory, parse_tasks_file, walk_knowledge
from docgraph.paths import resolve_tasks_path


class IndexStats(BaseModel):
    artifacts: int = 0
    tasks: int = 0
    edges: int = 0
    dangling: int = 0
    knowledge: int = 0
    parse_errors: list[str] = Field(default_factory=list)


def index(
    conn: sqlite3.Connection,
    docs_root: Path,
    *,
    corpus: str = "default",
    task_domains: dict[str, str] | None = None,
    tasks_path: Path | None = None,
) -> IndexStats:
    """Walk `docs_root`, parse, persist into SQLite scoped to `corpus`.

    Per-corpus full-refresh: deletes only `WHERE corpus = ?` rows (across
    artifacts, tasks, edges via FK cascade, and FTS rows for all three
    kinds). Other corpora's rows are untouched.

    Idempotent within a corpus, running twice leaves the DB in the same
    state with no row duplication.

    `task_domains` and `tasks_path` are optional. If `tasks_path` is None,
    the indexer searches for `<docs_root>/../TASKS.md`; missing TASKS.md
    is fine (zero tasks indexed).
    """
    artifacts, parse_errors = parse_directory(docs_root)

    # Resolve and parse TASKS.md (optional).
    tasks: list[Task] = []
    task_errors: list[str] = []
    resolved_tasks_path = resolve_tasks_path(docs_root, tasks_path)
    if resolved_tasks_path is not None:
        task_corpus_config = CorpusConfig(
            name=corpus,
            path=docs_root,
            task_domains=task_domains or {},
        )
        tasks, task_errors = parse_tasks_file(resolved_tasks_path, task_corpus_config)

    graph = build_graph(artifacts, tasks)
    now = int(time.time())

    conn.execute("DELETE FROM artifacts WHERE corpus = ?", (corpus,))
    conn.execute("DELETE FROM tasks WHERE corpus = ?", (corpus,))

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

    conn.executemany(
        """INSERT INTO tasks
           (id, corpus, title, status, refs, refs_by_level, domain_id, domain_label,
            phase, body, source_path, line_number, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                t.id,
                corpus,
                t.title,
                t.status.value,
                json.dumps(t.refs),
                json.dumps(t.refs_by_level),
                t.domain_id,
                t.domain_label,
                t.phase,
                t.body,
                str(t.source_path),
                t.line_number,
                now,
            )
            for t in graph.tasks.values()
        ],
    )

    # After M2: every edge target is meant to resolve to a graph node.
    # The target_is_node column means "did the target actually resolve to a
    # node?" — 1 for resolved edges, 0 for dangling. is_dangling carries the
    # same information from the opposite direction; the column stays as a
    # forward-compat slot for future edge types whose targets aren't nodes
    # at all (e.g. external URLs, commit hashes promoted from narrative).
    edge_rows = [
        (e.source_id, corpus, e.target, e.edge_type.value, 1, 0)
        for e in graph.edges
    ] + [
        (e.source_id, corpus, e.target, e.edge_type.value, 0, 1)
        for e in graph.dangling_edges
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO edges
           (source_id, corpus, target, edge_type, target_is_node, is_dangling)
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

    # FTS rows for tasks (kind='task'). Body feeds searchability of
    # sub-bullet text aggregated by parse_tasks_file.
    conn.execute(
        "DELETE FROM fts_artifacts WHERE kind = 'task' AND corpus = ?",
        (corpus,),
    )
    conn.executemany(
        "INSERT INTO fts_artifacts(ref, kind, corpus, title, content) "
        "VALUES (?, 'task', ?, ?, ?)",
        [(t.id, corpus, t.title, t.body) for t in graph.tasks.values()],
    )

    conn.commit()

    return IndexStats(
        artifacts=len(graph.artifacts),
        tasks=len(graph.tasks),
        edges=len(graph.edges),
        dangling=len(graph.dangling_edges),
        knowledge=len(knowledge),
        parse_errors=parse_errors + kn_errors + task_errors,
    )


def index_all(
    conn: sqlite3.Connection,
    corpora: Iterable[CorpusConfig],
) -> dict[str, IndexStats]:
    """Run `index()` for every corpus, return per-corpus stats keyed by name."""
    return {
        c.name: index(
            conn,
            c.path,
            corpus=c.name,
            task_domains=c.task_domains,
        )
        for c in corpora
    }
