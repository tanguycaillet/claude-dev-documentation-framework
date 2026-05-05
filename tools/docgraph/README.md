# docgraph

> A typed-graph + full-text query layer for the
> [claude-dev-documentation-framework](../../README.md).
> Indexes REQ / PLAN / ADR / SCN markdown frontmatter into SQLite + FTS5 and
> exposes it through a CLI and an MCP server, so Claude Code (or any
> MCP-aware assistant) can navigate the chain instead of re-reading the
> whole `docs/` tree.

## What it does

The framework gives you four typed artifacts (REQ, PLAN, ADR, SCN) plus
`TASKS.md`, all cross-referenced through frontmatter. As a project grows, an
AI assistant that re-reads every artifact each session burns context
quickly. `docgraph` solves that with one parser walk and a persistent index:

- **CLI** (`docgraph`): interactive parse / get / chain / list against a
  single docs/ tree. In-memory only; rebuilds per invocation.
- **MCP server** (`docgraph-mcp`): long-lived process. Indexes one or many
  corpora into SQLite + FTS5, watches for file changes, and serves five
  tools to any MCP client: `get_artifact`, `get_chain`, `list_artifacts`,
  `search_artifacts`, `validate_graph`.

The MCP tools answer questions like *"show me REQ-0003 and the full chain it
spawned"*, *"any ADRs about FTS5?"*, or *"is the graph internally
consistent?"*, without the assistant re-reading every file.

## Install

Requires Python 3.12+. We use [uv](https://docs.astral.sh/uv/) for env and
dependency management.

```bash
cd tools/docgraph
uv sync                 # creates .venv, installs deps + this package
```

Verify the CLI:

```bash
uv run docgraph --docs ../../examples/forward-pipeline-bookshelf-stats parse
```

You should see counts for the three artifacts that ship in that example
(REQ-0003, PLAN-0002, ADR-0007, ADR-0008) plus their resolved edges.

## CLI quickstart

The CLI walks a single docs root in memory each invocation. Useful for ad
hoc inspection; for repeated queries, prefer the MCP server.

```bash
# Parse and report stats
uv run docgraph --docs ./docs parse

# Fetch one artifact (frontmatter + body)
uv run docgraph --docs ./docs get REQ-0001

# Walk the chain from any artifact
uv run docgraph --docs ./docs chain REQ-0001

# List artifacts by type, optionally filter by status
uv run docgraph --docs ./docs list adr --status accepted
```

## MCP server: single corpus

The simplest setup: one project, one docs/ tree.

```bash
# stdio transport (default, for Claude Code / Claude Desktop subprocesses)
uv run docgraph-mcp --docs ./docs

# HTTP transport (for shared / multi-client use; loopback only)
uv run docgraph-mcp --docs ./docs --http --port 8200
```

By default the SQLite index lives at `./.docgraph.db` (gitignore it). Pass
`--db /some/path/docgraph.db` to put it elsewhere.

## MCP server: multi-corpus

Want one MCP server to query several projects at once? Declare each in a
`corpora.toml`:

```toml
# corpora.toml
[corpora.myproject]
path = "/home/me/myproject/docs"

[corpora.another-project]
path = "/home/me/another/docs"
```

Then point the server at it:

```bash
uv run docgraph-mcp --config /path/to/corpora.toml
```

When `corpora.toml` is in the working directory you launch from, the server
picks it up automatically. CLI `--docs name=path` flags can override or
extend the TOML at launch time.

Once multiple corpora are indexed, addresses can be either:

- **Bare**: `REQ-0001` spans every corpus. Returns a list (singleton on
  unique match, multi-element on collision across corpora).
- **Prefixed**: `myproject:REQ-0001` is scoped to one corpus. Always
  returns a singleton (or empty).

The same convention works on the CLI's MCP-tool output and through the
`get_artifact` / `get_chain` tools. See `corpora.toml.example` for a
copyable starter.

## Registering with Claude Code

Add a stdio MCP server in your Claude Code settings. From a project root
that contains a `corpora.toml` (or with explicit `--docs` flags):

```json
{
  "mcpServers": {
    "docgraph": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/tools/docgraph",
        "run", "docgraph-mcp",
        "--config", "/absolute/path/to/your/corpora.toml"
      ]
    }
  }
}
```

Use absolute paths. Claude Code launches the server from its own working
directory, not your project root.

## The five tools

Once the server is up, an assistant can call:

- **`get_artifact(id, corpus=None)`**: full body + frontmatter for one
  artifact.
- **`get_chain(id, corpus=None)`**: walks the typed chain forward and
  inverse (REQ → PLAN ← ADR; SCN → ADR; ADR → triggered_by).
- **`list_artifacts(type=None, status=None, corpus=None)`**: directory
  listing, filterable.
- **`search_artifacts(query, kind=None, type=None, corpus=None, limit=10)`**:
  BM25-ranked FTS5 over titles + bodies. Snippet-highlighted.
- **`validate_graph(corpus=None)`**: integrity report. Status
  inconsistencies, plus dangling edges partitioned into commit-hash
  shortcuts (framework-compliant), narrative explanations, and unexplained
  references.

All five return Pydantic models, so the JSON the assistant sees is
self-describing.

## Architecture in one paragraph

`parser.py` walks `*.md` and pulls frontmatter via `python-frontmatter`;
files without a typed `id` (REQ/PLAN/ADR/SCN-N+) are skipped (knowledge
articles + READMEs land in a separate FTS-only path). `graph.py` resolves
the seven typed edges into an in-memory `Graph`. `db.py` + `indexer.py`
persist that graph into SQLite (composite `(corpus, id)` PK; FK cascade on
edges; FTS5 virtual table for search). `query.py` rehydrates `Graph`
instances per corpus. `watcher.py` runs one debounced watchdog per corpus (inotify on Linux,
polling fallback on WSL), with a periodic full rescan safety net.
`mcp_server.py` glues it all to FastMCP.

## What's intentionally not here

- **Semantic search / embeddings.** docgraph is exact-match (BM25) only.
  Vector search over arbitrary prose is a separate concern and will land as
  a separate tool when it does.
- **TASKS.md as a graph node.** Today, `implementation_tasks` and
  `spawns_tasks` edge values are free-text strings. Making `TASKS.md` a
  parseable, addressable artifact (with proper IDs) is on the roadmap; the
  underlying edge model already distinguishes task-target from
  artifact-target edges.
- **Cross-corpus traversal.** Each `get_chain` result is corpus-scoped.
  Two corpora that happen to share an ID don't get linked.

## License

Inherits the [CC BY 4.0](../../LICENSE) license of the parent repository.
