"""SQLite read-side: hydrates in-memory models from persisted state.

Backs the FastMCP tool handlers. Every read carries a corpus; addresses can
be expressed either as bare ids + `corpus` arg or via `corpus:id` prefix
strings. Collision-aware: get_artifact returns a list (singleton on unique
match across corpora, multi-element on collision).

Public surface:
    parse_artifact_address(addr) -> (corpus|None, bare_id)
    get_artifact(conn, id, corpus=None)            -> list[Artifact]
    list_artifacts(conn, *, type, status, corpus)  -> list[Artifact]
    graph_from_db(conn, corpus)                    -> Graph
    graphs_from_db(conn)                           -> dict[corpus_name, Graph]
"""

import json
import sqlite3
from pathlib import Path

from docgraph.models import Artifact, ArtifactType, Edge, EdgeType, Graph

_ARTIFACT_COLS = (
    "id, type, title, status, source_path, frontmatter, content, corpus, updated_at"
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


def graph_from_db(conn: sqlite3.Connection, corpus: str) -> Graph:
    """Reconstruct an in-memory Graph for one corpus."""
    artifacts: dict[str, Artifact] = {}
    for row in conn.execute(
        f"SELECT {_ARTIFACT_COLS} FROM artifacts WHERE corpus = ? ORDER BY id",
        (corpus,),
    ):
        a = _row_to_artifact(row)
        artifacts[a.id] = a

    edges: list[Edge] = []
    dangling: list[Edge] = []
    for source_id, target, edge_type, target_is_artifact, is_dangling in conn.execute(
        "SELECT source_id, target, edge_type, target_is_artifact, is_dangling "
        "FROM edges WHERE corpus = ?",
        (corpus,),
    ):
        edge = Edge(source_id=source_id, target=target, edge_type=EdgeType(edge_type))
        if is_dangling:
            dangling.append(edge)
        else:
            edges.append(edge)

    return Graph(artifacts=artifacts, edges=edges, dangling_edges=dangling)


def graphs_from_db(conn: sqlite3.Connection) -> dict[str, Graph]:
    """Reconstruct one Graph per corpus present in the DB."""
    corpora = [
        row[0] for row in conn.execute("SELECT DISTINCT corpus FROM artifacts ORDER BY corpus")
    ]
    return {corpus: graph_from_db(conn, corpus) for corpus in corpora}
