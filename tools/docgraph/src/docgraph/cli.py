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

from docgraph.graph import build_graph
from docgraph.models import Artifact, ArtifactType, Graph
from docgraph.parser import parse_directory


def _load_graph(docs_root: Path) -> tuple[Graph, list[str]]:
    artifacts, errors = parse_directory(docs_root)
    return build_graph(artifacts), errors


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
    start = graph.get(artifact_id)
    if start is None:
        print(f"Not found: {artifact_id}", file=sys.stderr)
        return 1
    for depth, art, label in _walk_chain(graph, start):
        prefix = "  " * depth
        suffix = f" [{art.status or 'no status'}]: {art.title or ''}"
        if label:
            print(f"{prefix}{label} {art.id}{suffix}")
        else:
            print(f"{art.id}{suffix}")
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


def _walk_chain(
    graph: Graph, start: Artifact
) -> list[tuple[int, Artifact, str | None]]:
    """Walk the typed-graph chain from `start`.

    Returns a list of (depth, artifact, label) tuples; label is the edge
    name + arrow indicating direction (`→` forward through frontmatter,
    `←` inverse lookup). Cycles are broken by visited-set tracking.
    """
    chain: list[tuple[int, Artifact, str | None]] = [(0, start, None)]
    visited = {start.id}

    def step(current: Artifact, depth: int) -> None:
        next_id, label = _next_in_chain(graph, current)
        if next_id is None or next_id not in graph.artifacts or next_id in visited:
            return
        next_art = graph.artifacts[next_id]
        chain.append((depth, next_art, label))
        visited.add(next_id)
        step(next_art, depth + 1)

    step(start, 1)
    return chain


def _next_in_chain(
    graph: Graph, current: Artifact
) -> tuple[str | None, str | None]:
    """One step of chain traversal, returns (next_artifact_id, edge_label)."""
    fm = current.frontmatter
    if current.type == ArtifactType.ADR:
        tb = fm.get("triggered_by")
        if isinstance(tb, str):
            return tb, "triggered_by →"
    elif current.type == ArtifactType.PLAN:
        for req in graph.list_by_type(ArtifactType.REQ):
            impl = req.frontmatter.get("implemented_by")
            if isinstance(impl, dict) and impl.get("plan") == current.id:
                return req.id, "implemented_by.plan ←"
    elif current.type == ArtifactType.SCN:
        rb = fm.get("resolved_by")
        if isinstance(rb, str):
            return rb, "resolved_by →"
    elif current.type == ArtifactType.REQ:
        impl = fm.get("implemented_by")
        if isinstance(impl, dict):
            p = impl.get("plan")
            if isinstance(p, str):
                return p, "implemented_by.plan →"
    return None, None


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
    return 1


if __name__ == "__main__":
    sys.exit(main())
