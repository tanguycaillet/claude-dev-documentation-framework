"""docgraph: typed-document graph layer for the claude-dev-documentation-framework.

Indexes REQ/PLAN/ADR/SCN markdown frontmatter from one or more docs/ corpora
into SQLite + FTS5. Exposes chain navigation, lexical search, and integrity
validation through a CLI and an MCP server.

Public surface:
    parser.parse_directory(root) -> (artifacts, errors)
    graph.build_graph(artifacts) -> Graph
    graph.walk_chain(graph, start_id) -> list[ChainStep]
    indexer.index(conn, root, *, corpus="default") -> IndexStats
    indexer.index_all(conn, corpora) -> dict[str, IndexStats]
    search.search(conn, query, ...) -> list[SearchHit]
    query.get_artifact / list_artifacts / graph_from_db / graphs_from_db
    validate.validate_graph(graph) / validate_graphs(graphs) -> ValidationReport
    watcher.FileWatcher(...)
"""
