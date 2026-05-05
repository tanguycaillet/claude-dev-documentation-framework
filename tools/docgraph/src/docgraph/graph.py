"""Graph builder + chain walker.

Builds an in-memory typed graph from a list of artifacts; resolves the seven
typed edges from each artifact's frontmatter.

Artifact-target edge values are tolerantly normalised: verbose annotations
like `"ADR-0054 - description"` extract to bare `"ADR-0054"`; genuine narrative
targets (no leading typed-id) are left untouched so the validator's narrative
classifier still owns them.

Public surface:
    build_graph(artifacts)            -> Graph
    walk_chain(graph, start_id)       -> list[ChainStep]
    ChainStep                          (Pydantic)
"""

import re
from typing import Any

from pydantic import BaseModel

from docgraph.models import Artifact, ArtifactType, Edge, EdgeType, Graph


# Anchored at start so genuine narrative ("First draft of REQ-0018 ...") is
# not consumed; only verbose-but-unambiguous values yield a bare-id extraction.
_TYPED_ID_PREFIX = re.compile(r"^(?:REQ|PLAN|ADR|SCN)-\d+")

_ARTIFACT_TARGET_EDGES = {
    EdgeType.TRIGGERED_BY,
    EdgeType.SUPERSEDES,
    EdgeType.RESOLVED_BY,
    EdgeType.IMPLEMENTED_BY_PLAN,
    EdgeType.SPAWNS_ADRS,
}


def _normalize_artifact_target(target: str) -> str:
    """Extract the leading typed-id prefix from a target string.

    Tolerates verbose annotations like 'ADR-0054 - description' by extracting
    just 'ADR-0054'. Strings without a leading typed-id are returned as-is.
    """
    match = _TYPED_ID_PREFIX.match(target.strip())
    return match.group(0) if match else target


def _emit(
    source_id: str,
    target: Any,
    edge_type: EdgeType,
    artifacts: dict[str, Artifact],
    edges: list[Edge],
    dangling: list[Edge],
) -> None:
    if not isinstance(target, str) or not target.strip():
        return
    if edge_type in _ARTIFACT_TARGET_EDGES:
        target = _normalize_artifact_target(target)
    edge = Edge(source_id=source_id, target=target, edge_type=edge_type)
    if edge.target_is_artifact and edge.target not in artifacts:
        dangling.append(edge)
    else:
        edges.append(edge)


def _emit_list(
    source_id: str,
    targets: Any,
    edge_type: EdgeType,
    artifacts: dict[str, Artifact],
    edges: list[Edge],
    dangling: list[Edge],
) -> None:
    if not isinstance(targets, list):
        return
    for target in targets:
        _emit(source_id, target, edge_type, artifacts, edges, dangling)


def build_graph(artifacts: list[Artifact]) -> Graph:
    """Build an in-memory typed graph from a list of artifacts.

    Resolves the seven typed edges from each artifact's frontmatter. Edges to
    artifact ids not present in the artifacts list are routed to
    `dangling_edges`. Task-text edges (implementation_tasks, spawns_tasks)
    are never dangling, their targets are free-text.
    """
    by_id: dict[str, Artifact] = {a.id: a for a in artifacts}
    edges: list[Edge] = []
    dangling: list[Edge] = []

    for artifact in artifacts:
        fm = artifact.frontmatter
        sid = artifact.id

        _emit(sid, fm.get("triggered_by"), EdgeType.TRIGGERED_BY, by_id, edges, dangling)
        _emit(sid, fm.get("supersedes"), EdgeType.SUPERSEDES, by_id, edges, dangling)
        _emit(sid, fm.get("resolved_by"), EdgeType.RESOLVED_BY, by_id, edges, dangling)

        implemented_by = fm.get("implemented_by")
        if isinstance(implemented_by, dict):
            _emit(
                sid,
                implemented_by.get("plan"),
                EdgeType.IMPLEMENTED_BY_PLAN,
                by_id,
                edges,
                dangling,
            )

        _emit_list(sid, fm.get("spawns_adrs"), EdgeType.SPAWNS_ADRS, by_id, edges, dangling)
        _emit_list(
            sid, fm.get("implementation_tasks"), EdgeType.IMPLEMENTATION_TASKS,
            by_id, edges, dangling,
        )
        _emit_list(
            sid, fm.get("spawns_tasks"), EdgeType.SPAWNS_TASKS,
            by_id, edges, dangling,
        )

    return Graph(artifacts=by_id, edges=edges, dangling_edges=dangling)


# --- chain walker -------------------------------------------------------


class ChainStep(BaseModel):
    """One step in a chain walk: artifact reached, depth, edge label."""

    depth: int
    artifact_id: str
    title: str | None = None
    status: str | None = None
    via_edge: str | None = None


def walk_chain(graph: Graph, start_id: str) -> list[ChainStep]:
    """Walk the typed-graph chain starting from `start_id`.

    Direction follows the framework's pipelines:
      ADR  → triggered_by         (forward: PLAN/REQ/SCN)
      PLAN ← implemented_by.plan  (inverse, find the REQ that points here)
      SCN  → resolved_by          (forward: ADR)
      REQ  → implemented_by.plan  (forward: PLAN)

    Cycles are broken via a visited set. Returns an empty list when
    `start_id` isn't in the graph.
    """
    start = graph.get(start_id)
    if start is None:
        return []

    chain: list[ChainStep] = [
        ChainStep(
            depth=0,
            artifact_id=start.id,
            title=start.title,
            status=start.status,
            via_edge=None,
        )
    ]
    visited = {start.id}
    current = start
    depth = 1

    while True:
        next_id, label = _next_in_chain(graph, current)
        if next_id is None or next_id in visited:
            break
        next_artifact = graph.get(next_id)
        if next_artifact is None:
            break
        chain.append(
            ChainStep(
                depth=depth,
                artifact_id=next_artifact.id,
                title=next_artifact.title,
                status=next_artifact.status,
                via_edge=label,
            )
        )
        visited.add(next_id)
        current = next_artifact
        depth += 1

    return chain


def _next_in_chain(graph: Graph, current: Artifact) -> tuple[str | None, str | None]:
    """Artifact-target reads pass through `_normalize_artifact_target` so verbose
    authoring conventions still allow chain traversal."""
    fm = current.frontmatter
    if current.type == ArtifactType.ADR:
        tb = fm.get("triggered_by")
        if isinstance(tb, str):
            return _normalize_artifact_target(tb), "triggered_by →"
    elif current.type == ArtifactType.PLAN:
        for req in graph.list_by_type(ArtifactType.REQ):
            impl = req.frontmatter.get("implemented_by")
            if isinstance(impl, dict):
                plan_target = impl.get("plan")
                if isinstance(plan_target, str) and _normalize_artifact_target(plan_target) == current.id:
                    return req.id, "implemented_by.plan ←"
    elif current.type == ArtifactType.SCN:
        rb = fm.get("resolved_by")
        if isinstance(rb, str):
            return _normalize_artifact_target(rb), "resolved_by →"
    elif current.type == ArtifactType.REQ:
        impl = fm.get("implemented_by")
        if isinstance(impl, dict):
            p = impl.get("plan")
            if isinstance(p, str):
                return _normalize_artifact_target(p), "implemented_by.plan →"
    return None, None
