"""docgraph CLI, parse / get / chain / list.

In-memory Pydantic graph rebuilt per invocation; suitable for the few-hundred
artifact corpora a single project produces. The MCP server (`docgraph-mcp`)
uses the persistent SQLite + FTS5 store for cross-session queries.

Entry point: `docgraph` (set in pyproject.toml). Run `uv run docgraph -h`.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from docgraph.config import CorpusConfig
from docgraph.graph import build_graph, walk_chain
from docgraph.models import ArtifactType, Graph, TaskStatus
from docgraph.parser import parse_directory, parse_tasks_file


def _resolve_tasks_path(docs_root: Path) -> Path | None:
    """Same inside-then-outside search the indexer uses."""
    inside = docs_root / "TASKS.md"
    if inside.exists():
        return inside
    sibling = docs_root.parent / "TASKS.md"
    return sibling if sibling.exists() else None


def _load_graph(docs_root: Path) -> tuple[Graph, list[str]]:
    artifacts, errors = parse_directory(docs_root)
    tasks = []
    tasks_path = _resolve_tasks_path(docs_root)
    if tasks_path is not None:
        cfg = CorpusConfig(name="default", path=docs_root)
        tasks, task_errors = parse_tasks_file(tasks_path, cfg)
        errors = errors + task_errors
    return build_graph(artifacts, tasks), errors


def cmd_parse(graph: Graph, errors: list[str]) -> int:
    print(f"Artifacts: {len(graph.artifacts)}")
    type_counts = Counter(a.type.value for a in graph.artifacts.values())
    for t in ("REQ", "PLAN", "ADR", "SCN"):
        print(f"  {t}: {type_counts.get(t, 0)}")
    print(f"Edges: {len(graph.edges)}")
    edge_counts = Counter(e.edge_type.value for e in graph.edges)
    for t in sorted(edge_counts):
        print(f"  {t}: {edge_counts[t]}")
    print(f"Dangling edges: {len(graph.dangling_edges)}")
    print(f"Parse errors: {len(errors)}")
    for err in errors:
        print(f"  {err}", file=sys.stderr)
    return 0


def cmd_get(graph: Graph, artifact_id: str) -> int:
    artifact = graph.get(artifact_id)
    if artifact is None:
        print(f"Not found: {artifact_id}", file=sys.stderr)
        return 1
    print(f"{artifact.id} [{artifact.status or 'no status'}]: {artifact.title or ''}")
    print(f"source: {artifact.source_path}")
    print()
    for k, v in artifact.frontmatter.items():
        if k == "id":
            continue
        print(f"  {k}: {v}")
    if artifact.content:
        print()
        print(artifact.content.rstrip())
    return 0


def cmd_chain(graph: Graph, artifact_id: str) -> int:
    if graph.get(artifact_id) is None:
        print(f"Not found: {artifact_id}", file=sys.stderr)
        return 1
    for step in walk_chain(graph, artifact_id):
        prefix = "  " * step.depth
        suffix = f" [{step.status or 'no status'}]: {step.title or ''}"
        if step.via_edge:
            print(f"{prefix}{step.via_edge} {step.artifact_id}{suffix}")
        else:
            print(f"{step.artifact_id}{suffix}")
        # When this step is an ADR, surface its child tasks (tasks whose
        # refs_by_level.adr includes this ADR id).
        if step.artifact_id.startswith("ADR-"):
            child_prefix = "  " * (step.depth + 1)
            for task in graph.tasks.values():
                if step.artifact_id in task.refs_by_level.get("adr", []):
                    print(
                        f"{child_prefix}implementation_tasks -> {task.id} "
                        f"[{task.status.value}]: {task.title or ''}"
                    )
    return 0


def cmd_list(graph: Graph, type_str: str, status_filter: str | None) -> int:
    artifacts = sorted(
        graph.list_by_type(ArtifactType(type_str.upper())),
        key=lambda a: a.id,
    )
    if status_filter is not None:
        artifacts = [a for a in artifacts if a.status == status_filter]
    for a in artifacts:
        print(f"{a.id} [{a.status or 'no status'}]: {a.title or ''}")
    return 0


def cmd_tasks(
    graph: Graph,
    status_filter: str | None,
    domain_filter: str | None,
    phase_filter: str | None,
) -> int:
    """List tasks in the graph, filtered by status / domain / phase."""
    tasks = list(graph.tasks.values())
    tasks.sort(key=lambda t: (str(t.source_path), t.line_number))
    if status_filter is not None:
        tasks = [t for t in tasks if t.status.value == status_filter]
    if domain_filter is not None:
        tasks = [t for t in tasks if t.domain_id == domain_filter]
    if phase_filter is not None:
        tasks = [t for t in tasks if t.phase == phase_filter]
    for t in tasks:
        domain_note = f" ({t.domain_id})" if t.domain_id else ""
        phase_note = f" {{phase: {t.phase}}}" if t.phase else ""
        print(
            f"{t.id} [{t.status.value}]{domain_note}{phase_note}: {t.title or ''}"
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docgraph",
        description="Typed-graph query layer for the claude-dev-documentation-framework.",
    )
    p.add_argument(
        "--docs",
        default="docs",
        help="Path to docs root (default: ./docs)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("parse", help="parse docs root and print stats")

    p_get = sub.add_parser("get", help="fetch an artifact by ID")
    p_get.add_argument("id")

    p_chain = sub.add_parser("chain", help="walk the typed-graph chain from an artifact")
    p_chain.add_argument("id")

    p_list = sub.add_parser("list", help="list artifacts by type")
    p_list.add_argument("type", choices=["req", "plan", "adr", "scn"])
    p_list.add_argument("--status", help="filter by status")

    p_tasks = sub.add_parser("tasks", help="list tasks (parsed from TASKS.md), filtered")
    p_tasks.add_argument(
        "--status",
        choices=[s.value for s in TaskStatus],
        help="filter by task status (todo / in-progress / done / blocked / parked)",
    )
    p_tasks.add_argument("--domain", help="filter by domain prefix (e.g. BE)")
    p_tasks.add_argument("--phase", help="filter by phase tag")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    graph, errors = _load_graph(Path(args.docs))

    if args.cmd == "parse":
        return cmd_parse(graph, errors)
    if args.cmd == "get":
        return cmd_get(graph, args.id)
    if args.cmd == "chain":
        return cmd_chain(graph, args.id)
    if args.cmd == "list":
        return cmd_list(graph, args.type, args.status)
    if args.cmd == "tasks":
        return cmd_tasks(graph, args.status, args.domain, args.phase)
    return 1


if __name__ == "__main__":
    sys.exit(main())
