"""Full-text search over the indexed corpus.

SQLite FTS5 with BM25 ranking + snippet highlighting. Every result is tagged
with its corpus. Search spans all corpora by default; an optional `corpus`
filter narrows to one.

Public surface:
    SearchHit
    search(conn, query, *, kind=None, artifact_type=None, corpus=None, limit=10)
        -> list[SearchHit]
"""

import sqlite3
from typing import Literal

from pydantic import BaseModel

Kind = Literal["typed", "knowledge"]


class SearchHit(BaseModel):
    ref: str          # artifact id (typed) or path slug (knowledge)
    kind: str         # 'typed' or 'knowledge'
    corpus: str
    title: str | None = None
    snippet: str
    rank: float       # BM25, lower is better


def _escape_fts5_query(query: str) -> str:
    """Wrap each whitespace-separated token in double quotes so FTS5 treats
    special chars (-, :, $, *, OR, NEAR, column qualifiers, ...) as literal
    text instead of operators or syntax. Empty input yields a query that
    matches nothing rather than crashing the parser.

    Examples (input -> escaped FTS5 query):
        Hapag-Lloyd ZIM       -> "Hapag-Lloyd" "ZIM"
        $7B Amkor             -> "$7B" "Amkor"
        column:value          -> "column:value"
        a quoted-tok phrase   -> "a" "quoted-tok" "phrase"
        (empty)               -> ""              (matches nothing)
    """
    tokens = []
    for tok in query.split():
        escaped = tok.replace('"', '""')
        tokens.append(f'"{escaped}"')
    return " ".join(tokens) if tokens else '""'


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    kind: Kind | None = None,
    artifact_type: str | None = None,
    corpus: str | None = None,
    limit: int = 10,
) -> list[SearchHit]:
    """Full-text search via FTS5 with BM25 ranking and snippet highlighting.

    Filters:
        kind         , 'typed' | 'knowledge' (None: both)
        artifact_type, 'req' | 'plan' | 'adr' | 'scn' (None: any; only
                        affects typed rows since knowledge has no type)
        corpus       , limit to one corpus (None: span all)

    Returns up to `limit` hits ordered by BM25 rank (lower == better).
    Snippets wrap matched terms with `**...**` and use `…` for elision.
    """
    safe_query = _escape_fts5_query(query)
    where = ["fts_artifacts MATCH ?"]
    params: list = [safe_query]

    # Defensive: filter NULL-corpus orphan rows (FTS5 can't enforce NOT NULL
    # on UNINDEXED columns).
    where.append("corpus IS NOT NULL")

    if kind is not None:
        where.append("kind = ?")
        params.append(kind)

    if corpus is not None:
        where.append("corpus = ?")
        params.append(corpus)

    if artifact_type is not None:
        if corpus is not None:
            where.append(
                "ref IN (SELECT id FROM artifacts WHERE type = ? AND corpus = ?)"
            )
            params.extend([artifact_type.upper(), corpus])
        else:
            where.append("ref IN (SELECT id FROM artifacts WHERE type = ?)")
            params.append(artifact_type.upper())

    sql = f"""
        SELECT ref, kind, corpus, title,
               snippet(fts_artifacts, -1, '**', '**', '…', 32),
               bm25(fts_artifacts)
        FROM fts_artifacts
        WHERE {' AND '.join(where)}
        ORDER BY bm25(fts_artifacts)
        LIMIT ?
    """
    params.append(limit)

    return [
        SearchHit(
            ref=r[0],
            kind=r[1],
            corpus=r[2],
            title=r[3],
            snippet=r[4],
            rank=r[5],
        )
        for r in conn.execute(sql, params)
    ]
