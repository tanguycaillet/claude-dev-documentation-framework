"""SQLite schema + connection management for the persistent graph.

SQLite + FTS5 backend. WAL mode for concurrent read/write. Composite
`(corpus, id)` primary key on artifacts; `corpus` column on edges and
fts_artifacts so multi-corpus rows coexist in one DB.

The `schema_version` table tracks the current schema; on version mismatch,
docgraph-owned tables are dropped and recreated. The DB is a derived
artifact, the indexer rebuilds rows from corpus files on next reindex.

Public surface:
    SCHEMA_VERSION      , current expected schema version (int)
    connect(db_path)     -> sqlite3.Connection (with pragmas + schema applied)
    init_schema(conn)    -> None  (drop-and-rebuild on version mismatch)
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

_DOCGRAPH_TABLES: tuple[str, ...] = (
    "schema_version",
    "fts_artifacts",
    "edges",
    "tasks",
    "artifacts",
)

SCHEMA: tuple[str, ...] = (
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)",
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        id          TEXT NOT NULL,
        corpus      TEXT NOT NULL DEFAULT 'default',
        type        TEXT NOT NULL CHECK(type IN ('REQ', 'PLAN', 'ADR', 'SCN')),
        title       TEXT,
        status      TEXT,
        source_path TEXT NOT NULL,
        frontmatter TEXT NOT NULL,
        content     TEXT NOT NULL DEFAULT '',
        updated_at  INTEGER NOT NULL,
        PRIMARY KEY (corpus, id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_artifacts_type   ON artifacts(type)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_corpus ON artifacts(corpus)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_id_only ON artifacts(id)",
    """
    CREATE TABLE IF NOT EXISTS edges (
        source_id      TEXT NOT NULL,
        corpus         TEXT NOT NULL DEFAULT 'default',
        target         TEXT NOT NULL,
        edge_type      TEXT NOT NULL,
        target_is_node INTEGER NOT NULL CHECK(target_is_node IN (0, 1)),
        is_dangling    INTEGER NOT NULL CHECK(is_dangling IN (0, 1)) DEFAULT 0,
        PRIMARY KEY (corpus, source_id, target, edge_type),
        FOREIGN KEY (corpus, source_id) REFERENCES artifacts(corpus, id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_edges_target   ON edges(target)",
    "CREATE INDEX IF NOT EXISTS idx_edges_type     ON edges(edge_type)",
    "CREATE INDEX IF NOT EXISTS idx_edges_corpus   ON edges(corpus)",
    "CREATE INDEX IF NOT EXISTS idx_edges_dangling ON edges(is_dangling) WHERE is_dangling = 1",
    # Schema v2: tasks become a queryable graph node alongside artifacts.
    # Mirrors the artifacts table shape with additional task-specific
    # columns (refs, refs_by_level, domain_id/_label, phase, line_number).
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id            TEXT NOT NULL,
        corpus        TEXT NOT NULL DEFAULT 'default',
        title         TEXT,
        status        TEXT NOT NULL,
        refs          TEXT NOT NULL,         -- JSON list of typed-id strings
        refs_by_level TEXT NOT NULL,         -- JSON object: {adr: [...], plan: [...], req: [...], scn: [...]}
        domain_id     TEXT,
        domain_label  TEXT,
        phase         TEXT,
        body          TEXT NOT NULL DEFAULT '',
        source_path   TEXT NOT NULL,
        line_number   INTEGER NOT NULL,
        updated_at    INTEGER NOT NULL,
        PRIMARY KEY (corpus, id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks(domain_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_phase  ON tasks(phase)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_corpus ON tasks(corpus)",
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_artifacts USING fts5(
        ref,
        kind UNINDEXED,
        corpus UNINDEXED,
        title,
        content,
        tokenize = 'unicode61'
    )
    """,
)

PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA synchronous = NORMAL",
)


def _read_version(conn: sqlite3.Connection) -> int:
    """Return the schema version stored in the DB, or 0 if untagged/missing."""
    try:
        row = conn.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row is not None else 0


def _drop_all(conn: sqlite3.Connection) -> None:
    """Drop every docgraph-owned table. Rebuild path on version mismatch."""
    for table in _DOCGRAPH_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply the schema. Drop-and-rebuild on version mismatch.

    - If `schema_version` is missing or stale, drop docgraph tables, recreate.
    - If it's current, fast path: re-run CREATE IF NOT EXISTS (cheap no-ops).
    - Idempotent, safe to call on every connection.
    """
    current = _read_version(conn)
    if current != SCHEMA_VERSION:
        _drop_all(conn)
    for stmt in SCHEMA:
        conn.execute(stmt)
    if _read_version(conn) != SCHEMA_VERSION:
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    conn.commit()


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection with pragmas applied and schema initialized."""
    conn = sqlite3.connect(str(db_path))
    for pragma in PRAGMAS:
        conn.execute(pragma)
    init_schema(conn)
    return conn
