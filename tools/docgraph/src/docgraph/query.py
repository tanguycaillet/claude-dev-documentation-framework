"""SQLite read-side: hydrates in-memory models from persisted state.

Backs the FastMCP tool handlers. Every read carries a corpus; addresses can
be expressed either as bare ids + `corpus` arg or via `corpus:id` prefix
strings. Collision-aware: get_artifact and get_task return lists (singleton
on unique match across corpora, multi-element on collision).

Public surface:
    parse_artifact_address(addr)                                      -> (corpus|None, bare_id)
    get_artifact(conn, id, corpus=None)                               -> list[Artifact]
    list_artifacts(conn, *, type, status, corpus)                     -> list[Artifact]
    get_task(conn, id, corpus=None)                                   -> list[Task]
    list_tasks(conn, *, status, domain, phase, corpus)                -> list[Task]
    graph_from_db(conn, corpus)                                       -> Graph
    graphs_from_db(conn)                                              -> dict[corpus_name, Graph]
    tasks_from_db(conn, corpus=None)                                  -> list[Task]
"""

import json
import sqlite3
from pathlib import Path

from docgraph.models import Artifact, ArtifactType, Edge, EdgeType, Graph, Task, TaskStatus

_ARTIFACT_COLS = (
    "id, type, title, status, source_path, frontmatter, content, corpus, updated_at"
)
_TASK_COLS = (
    "id, corpus, title, status, refs, refs_by_level, domain_id, domain_label, "
    "phase, body, source_path, line_number"
)


def parse_artifact_address(addr: str) -> tuple[str | None, str]:
    """Split a `corpus:id` address into `(corpus, bare_id)`.

    Bare ids (no `:`) return `(None, addr)`. The `:` separator never appears
    in valid REQ/PLAN/ADR/SCN ids, so this split is unambiguous.
    """
    if ":" in addr:
        corpus, _, bare = addr.partition(":")
        return corpus, bare
    return None, addr


def _row_to_artifact(row: tuple) -> Artifact:
    (
        artifact_id,
        type_str,
        title,
        status,
        source_path,
        frontmatter_json,
        content,
        corpus,
        _updated_at,
    ) = row
    return Artifact(
        id=artifact_id,
        type=ArtifactType(type_str),
        title=title,
        status=status,
        source_path=Path(source_path),
        corpus=corpus,
        frontmatter=json.loads(frontmatter_json),
        content=content or "",
    )


def get_artifact(
    conn: sqlite3.Connection,
    id: str,
    corpus: str | None = None,
) -> list[Artifact]:
    """Fetch artifacts matching an id, optionally scoped to a corpus.

    Accepts either:
      get_artifact(conn, "myproject:REQ-0001")
      get_artifact(conn, "REQ-0001", corpus="myproject")
      get_artifact(conn, "REQ-0001")  # spans all corpora, list

    Returns:
      []              , id not found anywhere
      [a]             , singleton, unique match
      [a1, a2, ...]   , collisions across corpora (each tagged with .corpus)
    """
    addr_corpus, bare_id = parse_artifact_address(id)
    if addr_corpus is not None and corpus is not None and addr_corpus != corpus:
        raise ValueError(
            f"corpus mismatch: id-prefix {addr_corpus!r} vs corpus arg {corpus!r}"
        )
    effective_corpus = addr_corpus or corpus

    sql = f"SELECT {_ARTIFACT_COLS} FROM artifacts WHERE id = ?"
    params: list = [bare_id]
    if effective_corpus is not None:
        sql += " AND corpus = ?"
        params.append(effective_corpus)
    sql += " ORDER BY corpus"
    return [_row_to_artifact(row) for row in conn.execute(sql, params)]


def list_artifacts(
    conn: sqlite3.Connection,
    *,
    artifact_type: str | None = None,
    status: str | None = None,
    corpus: str | None = None,
) -> list[Artifact]:
    """List artifacts ordered by (corpus, id), optionally filtered."""
    where: list[str] = []
    params: list = []
    if artifact_type is not None:
        where.append("type = ?")
        params.append(artifact_type.upper())
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if corpus is not None:
        where.append("corpus = ?")
        params.append(corpus)
    sql = f"SELECT {_ARTIFACT_COLS} FROM artifacts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY corpus, id"
    return [_row_to_artifact(row) for row in conn.execute(sql, params)]


def _row_to_task(row: tuple) -> Task:
    (
        task_id,
        corpus,
        title,
        status,
        refs_json,
        refs_by_level_json,
        domain_id,
        domain_label,
        phase,
        body,
        source_path,
        line_number,
    ) = row
    return Task(
        id=task_id,
        corpus=corpus,
        title=title,
        status=TaskStatus(status),
        refs=json.loads(refs_json),
        refs_by_level=json.loads(refs_by_level_json),
        domain_id=domain_id,
        domain_label=domain_label,
        phase=phase,
        body=body or "",
        source_path=Path(source_path),
        line_number=line_number,
    )


def get_task(
    conn: sqlite3.Connection,
    id: str,
    corpus: str | None = None,
) -> list[Task]:
    """Fetch tasks matching an id, optionally scoped to a corpus.

    Same accepts/returns shape as get_artifact: bare ids span every corpus
    and may return multiple rows; corpus-prefixed ids scope to one.
    """
    addr_corpus, bare_id = parse_artifact_address(id)
    if addr_corpus is not None and corpus is not None and addr_corpus != corpus:
        raise ValueError(
            f"corpus mismatch: id-prefix {addr_corpus!r} vs corpus arg {corpus!r}"
        )
    effective_corpus = addr_corpus or corpus

    sql = f"SELECT {_TASK_COLS} FROM tasks WHERE id = ?"
    params: list = [bare_id]
    if effective_corpus is not None:
        sql += " AND corpus = ?"
        params.append(effective_corpus)
    sql += " ORDER BY corpus"
    return [_row_to_task(row) for row in conn.execute(sql, params)]


def list_tasks(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    domain: str | None = None,
    phase: str | None = None,
    corpus: str | None = None,
) -> list[Task]:
    """List tasks ordered by (corpus, source_path, line_number), filtered.

    Filters: status (one of the TaskStatus values), domain (the bare prefix
    like 'BE'), phase (exact match), corpus (corpus name).
    """
    where: list[str] = []
    params: list = []
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if domain is not None:
        where.append("domain_id = ?")
        params.append(domain)
    if phase is not None:
        where.append("phase = ?")
        params.append(phase)
    if corpus is not None:
        where.append("corpus = ?")
        params.append(corpus)
    sql = f"SELECT {_TASK_COLS} FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY corpus, source_path, line_number"
    return [_row_to_task(row) for row in conn.execute(sql, params)]


def tasks_from_db(conn: sqlite3.Connection, corpus: str | None = None) -> list[Task]:
    """Return all tasks for a corpus (or all corpora if corpus=None)."""
    sql = f"SELECT {_TASK_COLS} FROM tasks"
    params: list = []
    if corpus is not None:
        sql += " WHERE corpus = ?"
        params.append(corpus)
    sql += " ORDER BY corpus, source_path, line_number"
    return [_row_to_task(row) for row in conn.execute(sql, params)]


def graph_from_db(conn: sqlite3.Connection, corpus: str) -> Graph:
    """Reconstruct an in-memory Graph for one corpus, including tasks."""
    artifacts: dict[str, Artifact] = {}
    for row in conn.execute(
        f"SELECT {_ARTIFACT_COLS} FROM artifacts WHERE corpus = ? ORDER BY id",
        (corpus,),
    ):
        a = _row_to_artifact(row)
        artifacts[a.id] = a

    tasks: dict[str, Task] = {}
    for row in conn.execute(
        f"SELECT {_TASK_COLS} FROM tasks WHERE corpus = ? ORDER BY source_path, line_number",
        (corpus,),
    ):
        t = _row_to_task(row)
        tasks[t.id] = t

    edges: list[Edge] = []
    dangling: list[Edge] = []
    for source_id, target, edge_type, target_is_node, is_dangling in conn.execute(
        "SELECT source_id, target, edge_type, target_is_node, is_dangling "
        "FROM edges WHERE corpus = ?",
        (corpus,),
    ):
        edge = Edge(source_id=source_id, target=target, edge_type=EdgeType(edge_type))
        if is_dangling:
            dangling.append(edge)
        else:
            edges.append(edge)

    return Graph(artifacts=artifacts, tasks=tasks, edges=edges, dangling_edges=dangling)


def graphs_from_db(conn: sqlite3.Connection) -> dict[str, Graph]:
    """Reconstruct one Graph per corpus present in the DB.

    Lists corpora by union of artifacts and tasks tables (a corpus may have
    only tasks if its docs/ is empty but TASKS.md is present).
    """
    corpora_set: set[str] = set()
    for row in conn.execute("SELECT DISTINCT corpus FROM artifacts"):
        corpora_set.add(row[0])
    for row in conn.execute("SELECT DISTINCT corpus FROM tasks"):
        corpora_set.add(row[0])
    return {corpus: graph_from_db(conn, corpus) for corpus in sorted(corpora_set)}
