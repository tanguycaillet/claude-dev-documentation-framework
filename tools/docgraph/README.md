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

You should see counts for the four artifacts that ship in that example
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

## TASKS.md row format

docgraph parses `TASKS.md` as a structured surface alongside the typed
artifacts in `docs/`. Every row that matches the format below produces
one Task record with a stable ID, a status, the upstream chain (refs),
and an optional phase tag. Sub-bullets stay freeform Markdown and are
aggregated into the task's body for full-text search.

The file on disk is the source of truth. The parser is read-only: it
never rewrites `TASKS.md`. You and any coding agent edit the file
through normal text edits; the parser re-reads on each parse.

### The row grammar

```
- [<STATUS>] **<ID>: <TITLE>** [`<REFS>`] [{phase: <PHASE>}] [<COMMENTARY>]
```

Component by component:

- `<STATUS>` is one character inside `[]`:

  | Marker | Status |
  |---|---|
  | `[ ]` | todo |
  | `[~]` | in-progress |
  | `[x]` (or `[X]`) | done |
  | `[!]` | blocked |
  | `[/]` | parked |
  | `[]` | todo (parser warning, accepted as forgiving fallback) |

- `<ID>` matches the regex `^[A-Z]+(?:-[A-Z0-9]+)+[a-z]?$`. Examples that
  match: `BE-014`, `BE-014a`, `FE-DEV-1`, `EP-008`, `EP-008-P0`,
  `TASK-0001`. Examples that do not match (skipped with a warning):
  whitespace-bearing IDs like `EP-008 Phase 0`, lowercase prefixes,
  digit-led tokens, bare-prefix-no-segment tokens like `BE`.

- `<TITLE>` is everything after the first `: ` separator inside the bold
  span. Titles are optional: a row whose bold span is just `**TASK-0001**`
  parses as untitled with a warning.

- `<REFS>` is the first backtick-quoted parens span on the line:

  ```
  `(<LEVEL_1> [<- <LEVEL_2> [<- <LEVEL_3>]])`
  ```

  Each level is a comma-separated list of typed-ids. ASCII (`<-`) and
  Unicode (`←`) arrow forms both parse. Numeric shorthand is supported
  inside a level: `ADR-0001,0005,0008` expands to
  `[ADR-0001, ADR-0005, ADR-0008]` (the prefix from the first id
  applies to bare numeric tails until the next arrow resets it).

  Three concrete examples:

  ```
  `(ADR-0071 <- PLAN-0016 <- REQ-0018)`
  `(ADR-0067, ADR-0068, ADR-0074, ADR-0075 <- PLAN-0015 <- REQ-0016)`
  `(no upstream)`
  ```

  Anything outside the backtick span on the same line (commentary, dates,
  status notes) is preserved as text but ignored by the parser.

- `{phase: <PHASE>}` is optional; the value is a freeform slug. May appear
  before or after the refs span. Tasks under an H3 section header that
  declares its own phase inherit it; per-task phase tags override.

### H3 section context

```
### [<LABEL>: <PLAN-ID>] [{phase: <PHASE>}]
```

Tasks under this header inherit `<PLAN-ID>` as a fallback PLAN ref (only
applied when the task's own refs don't list a PLAN), and inherit the
section's phase (only applied when the task has no explicit `{phase: ...}`).
Sections can omit `<PLAN-ID>` (e.g. `### [Foundation]`) for label-only
grouping; in that case nothing is inherited.

### Sub-bullets

Lines indented two or more spaces and starting with `- ` are sub-bullets
of the most-recent task. They aggregate into the parent's `body` field
(preserving leading dash, status, indentation), which feeds FTS. The
parser does not parse sub-bullets as individual tasks; their checkboxes
are visible to humans and to FTS but not to the typed graph.

### Authoring rule for multi-segment IDs

The ID regex permits multi-segment IDs like `FE-DEV-1` and `EP-008-P0`.
The parser always extracts the first segment as the domain, regardless
of `task_domains` content: `FE-DEV-1` resolves to domain `FE`, never to
`FE-DEV`.

When you create a new task ID, decide which case you are in:

- **To group with an existing domain**, use a multi-segment ID under
  that prefix. Example: a frontend task related to dev tooling becomes
  `FE-DEV-1`, which resolves to domain `FE` ("Frontend").
- **To get a separate domain** (its own label, queryable independently
  via `--domain`), use a distinct flat prefix. Example: a dedicated
  domain for FE dev tooling becomes `FEDEV-1`, configured as
  `FEDEV = "Frontend dev tools"` under `[corpora.<name>.task_domains]`.

Worked examples:

| Author intent | Correct ID | Domain |
|---|---|---|
| New backend task | `BE-014` | `BE` |
| Backend task variant (a/b/c suffix) | `BE-014a` | `BE` |
| Phase N of EP-008 in the existing EP domain | `EP-008-P0` | `EP` |
| Frontend task with dev-tools sub-context, **same FE domain** | `FE-DEV-1` | `FE` |
| Separate FE-dev domain (own label + filterable) | `FEDEV-1` | `FEDEV` |

### Configuring task_domains per corpus

Each corpus may declare a prefix-to-label mapping in `corpora.toml`:

```toml
[corpora.myproject.task_domains]
BE   = "Backend"
FE   = "Frontend"
AI   = "AI Ingestion"
SEC  = "Security"
```

Keys must be uppercase letters only (no digits, dashes, or lowercase).
Tasks whose prefix is in the map carry both `domain_id` (the bare
prefix) and `domain_label` (the human-readable string). Tasks whose
prefix isn't in the map carry `domain_id` (always set when the ID
parses) and `domain_label = null`, plus a once-per-prefix parser
warning. The map is optional: a corpus without it gets `domain_label =
null` for every task.

### What ships now vs later

After M2: tasks are first-class graph nodes. The indexer reads
`TASKS.md` (alongside docs/), persists tasks into the `tasks` SQLite
table, and the edge model resolves `IMPLEMENTATION_TASKS` and
`SPAWNS_TASKS` against task IDs. Queries: `docgraph tasks
[--status --domain --phase --corpus]` from the CLI, plus `get_task` /
`list_tasks` MCP tools. Chains starting from an ADR surface its child
tasks; `validate_graph` reports bidirectional drift (missing task IDs
or missing artifact refs from `TASKS.md`) under `dangling_unexplained`.

Still queued for **M3**: a `docgraph-migrate-adr-tasks` script that
rewrites legacy string-title `ADR.implementation_tasks` to task-id
format. ADRs in old format produce dangling-unexplained drift findings
today, signalling the migration is needed.

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
  BM25-ranked FTS5 over titles + bodies. `kind` accepts `'typed'`,
  `'knowledge'`, or `'task'`. Snippet-highlighted.
- **`validate_graph(corpus=None)`**: integrity report. Status
  inconsistencies, plus dangling edges partitioned into commit-hash
  shortcuts (framework-compliant), narrative explanations, and unexplained
  references. After M2: missing task IDs and unmigrated string-title
  `implementation_tasks` lists surface as unexplained drift.
- **`get_task(id, corpus=None)`**: full body + metadata for one task
  parsed from TASKS.md. Same shape as `get_artifact`.
- **`list_tasks(status=None, domain=None, phase=None, corpus=None)`**:
  filterable task listing across configured corpora.

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
- **Indexed task queries**. M1 ships the parser and the row format spec;
  the indexer that persists tasks into SQLite, the `docgraph tasks`
  CLI command, and the MCP `get_task` / `list_tasks` tools land in M2.
  Until M2 ships, parse `TASKS.md` programmatically via
  `docgraph.parser.parse_tasks_file(path, corpus_config)`.
- **Cross-corpus traversal.** Each `get_chain` result is corpus-scoped.
  Two corpora that happen to share an ID don't get linked.

## License

Inherits the [CC BY 4.0](../../LICENSE) license of the parent repository.
