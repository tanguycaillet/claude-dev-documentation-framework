"""docgraph MCP server: typed-graph + FTS query layer for AI assistants.

Single-process daemon. `main()` loads corpora, runs an initial reindex,
spawns one FileWatcher per corpus, then starts a FastMCP server. Default
transport is stdio (one server per Claude Code / Claude Desktop subprocess);
`--http` opens an HTTP transport on `127.0.0.1:<port>` for shared use.

Seven MCP tools:
    get_artifact, get_chain, list_artifacts, search_artifacts, validate_graph,
    get_task, list_tasks

Usage:
    docgraph-mcp --docs ./docs                  # single-corpus, stdio
    docgraph-mcp --config corpora.toml          # multi-corpus, stdio
    docgraph-mcp --http --port 8200 ...         # HTTP transport on loopback
"""

import argparse
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from docgraph.config import CorpusConfig, load_corpora
from docgraph.db import connect
from docgraph.graph import ChainStep, walk_chain
from docgraph.indexer import index_all
from docgraph.models import Artifact, Task
from docgraph.parser import parse_directory  # ADR-0011: re-parse for validate_graph
from docgraph.query import (
    get_artifact as _get_artifact,
    get_task as _get_task,
    graph_from_db,
    graphs_from_db,
    list_artifacts as _list_artifacts,
    list_tasks as _list_tasks,
    parse_artifact_address,
)
from docgraph.search import SearchHit, search as _search
from docgraph.validate import (
    ValidationReport,
    validate_graph as _validate_graph,
    validate_graphs as _validate_graphs,
)
from docgraph.watcher import FileWatcher

mcp: FastMCP = FastMCP("docgraph")

# Per-process state, set by main() before mcp.run().
_DB_PATH: Path | None = None
_CORPORA: list[CorpusConfig] = []


def _conn():
    if _DB_PATH is None:
        raise RuntimeError("docgraph MCP server not initialized; call main() first")
    return connect(_DB_PATH)


# --- chain return wrapper ----------------------------------------------


class Chain(BaseModel):
    """A chain walked from a single artifact, tagged with its corpus.

    `get_chain` returns list[Chain], singleton on unique bare-id match,
    multi-element on collision across corpora.
    """

    corpus: str
    start_id: str
    steps: list[ChainStep] = Field(default_factory=list)


# --- five tools --------------------------------------------------------


@mcp.tool()
def get_artifact(id: str, corpus: str | None = None) -> list[Artifact]:
    """Fetch artifacts (REQ/PLAN/ADR/SCN) by id with frontmatter + content.

    `id` may be either bare (`REQ-0001`) or prefixed (`myproject:REQ-0001`).
    With no `corpus` arg, bare ids span every configured corpus, the
    return is a list (singleton on unique match, multi on collision).
    """
    conn = _conn()
    try:
        return _get_artifact(conn, id, corpus=corpus)
    finally:
        conn.close()


@mcp.tool()
def get_chain(id: str, corpus: str | None = None) -> list[Chain]:
    """Walk the typed-graph chain from any artifact id.

    Returns one Chain per corpus that contains the id. Each Chain is
    self-contained (cross-corpus traversal is intentionally out of scope).
    """
    conn = _conn()
    try:
        addr_corpus, bare_id = parse_artifact_address(id)
        if addr_corpus is not None and corpus is not None and addr_corpus != corpus:
            raise ValueError(
                f"corpus mismatch: id-prefix {addr_corpus!r} vs corpus arg {corpus!r}"
            )
        effective_corpus = addr_corpus or corpus
        graphs = graphs_from_db(conn)
        results: list[Chain] = []
        if effective_corpus is not None:
            graph = graphs.get(effective_corpus)
            if graph is not None and graph.get(bare_id) is not None:
                results.append(
                    Chain(corpus=effective_corpus, start_id=bare_id,
                          steps=walk_chain(graph, bare_id))
                )
        else:
            for corpus_name, graph in graphs.items():
                if graph.get(bare_id) is not None:
                    results.append(
                        Chain(corpus=corpus_name, start_id=bare_id,
                              steps=walk_chain(graph, bare_id))
                    )
        return results
    finally:
        conn.close()


@mcp.tool()
def list_artifacts(
    type: str | None = None,
    status: str | None = None,
    corpus: str | None = None,
) -> list[Artifact]:
    """List artifacts. Filters: type, status, corpus (all optional)."""
    conn = _conn()
    try:
        return _list_artifacts(conn, artifact_type=type, status=status, corpus=corpus)
    finally:
        conn.close()


@mcp.tool()
def search_artifacts(
    query: str,
    kind: str | None = None,
    type: str | None = None,
    corpus: str | None = None,
    limit: int = 10,
) -> list[SearchHit]:
    """Full-text search via FTS5 (BM25 ranked, with snippets).

    Filters: kind in {'typed','knowledge','task'}; type in {'req','plan','adr','scn'};
    corpus (any configured corpus name). Task rows index against the
    aggregated sub-bullet body.
    """
    conn = _conn()
    try:
        return _search(
            conn, query, kind=kind, artifact_type=type,
            corpus=corpus, limit=limit,
        )
    finally:
        conn.close()


@mcp.tool()
def validate_graph(corpus: str | None = None) -> ValidationReport:
    """Run integrity checks. Without `corpus`, validates every configured corpus.

    ADR-0011: re-parses each corpus's docs root to feed fresh parse_errors
    into the validator. Cost is small (parser is fast); the validator is
    rarely-called so the per-call re-parse stays cheap operationally.
    """
    conn = _conn()
    try:
        if corpus is not None:
            graph = graph_from_db(conn, corpus)
            parse_errors: list[str] = []
            cfg = next((c for c in _CORPORA if c.name == corpus), None)
            if cfg is not None:
                _, parse_errors = parse_directory(cfg.path)
            return _validate_graph(
                graph, corpus=corpus, parse_errors=parse_errors,
            )
        # Multi-corpus path: collect per-corpus parse_errors from each
        # corpus's docs root.
        graphs = graphs_from_db(conn)
        per_corpus_errors: dict[str, list[str]] = {}
        for c in _CORPORA:
            _, errs = parse_directory(c.path)
            if errs:
                per_corpus_errors[c.name] = errs
        return _validate_graphs(graphs, parse_errors=per_corpus_errors)
    finally:
        conn.close()


@mcp.tool()
def get_task(id: str, corpus: str | None = None) -> list[Task]:
    """Fetch tasks (parsed from TASKS.md) by id.

    `id` may be either bare (`TASK-0001`, `BE-014`) or prefixed
    (`myproject:TASK-0001`). With no `corpus` arg, bare ids span every
    configured corpus and the return is a list (singleton on unique
    match, multi on collision).
    """
    conn = _conn()
    try:
        return _get_task(conn, id, corpus=corpus)
    finally:
        conn.close()


@mcp.tool()
def list_tasks(
    status: str | None = None,
    domain: str | None = None,
    phase: str | None = None,
    corpus: str | None = None,
) -> list[Task]:
    """List tasks. Filters: status, domain (prefix), phase, corpus.

    All filters optional. Status values: todo / in-progress / done /
    blocked / parked. Domain is the bare uppercase prefix (e.g. 'BE'),
    not the human-readable label.
    """
    conn = _conn()
    try:
        return _list_tasks(
            conn, status=status, domain=domain, phase=phase, corpus=corpus,
        )
    finally:
        conn.close()


# --- lifecycle ----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Boot the MCP server: load corpora, initial reindex, watcher, mcp.run().

    Configuration sources:
      --config PATH      explicit path to corpora.toml
                         (default: ./corpora.toml if present)
      --docs name=path   repeatable; CLI overrides TOML on collision
      --docs PATH        bare path; single-corpus mode (corpus name from basename)
      --db PATH          SQLite location (default: <cwd>/.docgraph.db)
      --http             use HTTP transport instead of stdio
      --host HOST        HTTP bind host (default: 127.0.0.1, loopback only)
      --port PORT        HTTP bind port (default: 8200)
    """
    parser = argparse.ArgumentParser(prog="docgraph-mcp")
    parser.add_argument("--config", default=None, help="Path to corpora.toml")
    parser.add_argument(
        "--docs",
        action="append",
        default=[],
        help="Corpus declaration: 'name=path' or bare path (single-corpus mode)",
    )
    parser.add_argument("--db", default=None, help="SQLite DB path")
    parser.add_argument("--http", action="store_true", help="Use HTTP transport")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host")
    parser.add_argument("--port", type=int, default=8200, help="HTTP bind port")
    args = parser.parse_args(argv)

    toml_path: Path | None = None
    if args.config:
        toml_path = Path(args.config)
    else:
        candidate = Path.cwd() / "corpora.toml"
        if candidate.exists():
            toml_path = candidate

    corpora = load_corpora(toml_path=toml_path, cli_overrides=args.docs)

    global _DB_PATH, _CORPORA
    _DB_PATH = (
        Path(args.db).resolve()
        if args.db
        else (Path.cwd() / ".docgraph.db").resolve()
    )
    _CORPORA = corpora

    boot_conn = connect(_DB_PATH)
    try:
        index_all(boot_conn, corpora)
    finally:
        boot_conn.close()

    watchers = [
        FileWatcher(_DB_PATH, c.path, corpus=c.name, task_domains=c.task_domains)
        for c in corpora
    ]
    for w in watchers:
        w.start()
    try:
        if args.http:
            mcp.run(transport="http", host=args.host, port=args.port)
        else:
            mcp.run()
    finally:
        for w in watchers:
            w.stop()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
