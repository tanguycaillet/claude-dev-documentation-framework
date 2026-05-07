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

from docgraph.models import Artifact, ArtifactType, Edge, EdgeType, Graph, Task


# Anchored at start so genuine narrative ("First draft of REQ-0018 ...") is
# not consumed; only verbose-but-unambiguous values yield a bare-id extraction.
# After M2, this normalization runs on every edge target. Task IDs (BE-014,
# TASK-0001, etc.) don't match this artifact-prefix regex and pass through
# unchanged, which is correct: task-id strings are already canonical when
# they come from `ADR.implementation_tasks` lists.
_TYPED_ID_PREFIX = re.compile(r"^(?:REQ|PLAN|ADR|SCN)-\d+")


def _normalize_artifact_target(target: str) -> str:
    """Extract the leading typed-id prefix from an artifact-target string.

    Tolerates verbose annotations like 'ADR-0054 - description' by extracting
    just 'ADR-0054'. Strings without a leading typed-id (including all task
    IDs) are returned as-is.
    """
    match = _TYPED_ID_PREFIX.match(target.strip())
    return match.group(0) if match else target


def _emit(
    source_id: str,
    target: Any,
    edge_type: EdgeType,
    nodes: dict[str, Any],
    edges: list[Edge],
    dangling: list[Edge],
) -> None:
    if not isinstance(target, str) or not target.strip():
        return
    target = _normalize_artifact_target(target)
    edge = Edge(source_id=source_id, target=target, edge_type=edge_type)
    if edge.target not in nodes:
        dangling.append(edge)
    else:
        edges.append(edge)


def _emit_list(
    source_id: str,
    targets: Any,
    edge_type: EdgeType,
    nodes: dict[str, Any],
    edges: list[Edge],
    dangling: list[Edge],
) -> None:
    if not isinstance(targets, list):
        return
    for target in targets:
        _emit(source_id, target, edge_type, nodes, edges, dangling)


def build_graph(
    artifacts: list[Artifact],
    tasks: list[Task] | None = None,
) -> Graph:
    """Build an in-memory typed graph from artifacts plus optional tasks.

    Resolves the seven typed edges from each artifact's frontmatter against
    the merged (artifacts + tasks) node space. Edges whose targets aren't
    in either dict are routed to `dangling_edges`. Task-target edges
    (implementation_tasks, spawns_tasks) resolve to task IDs after M2;
    missing task IDs become dangling-unexplained findings via the
    validator's existing classifier.

    The default-empty `tasks` argument preserves backward compatibility for
    callers that pre-date M1; in that mode every task-target edge is
    dangling, which is the pre-M2 behaviour expressed as drift.
    """
    by_id: dict[str, Artifact] = {a.id: a for a in artifacts}
    tasks_by_id: dict[str, Task] = {t.id: t for t in (tasks or [])}
    # Artifact and task ID spaces are disjoint by construction (artifact IDs
    # match REQ/PLAN/ADR/SCN-N+; task IDs use other prefixes). If they
    # collide, something authored is wrong; fail fast rather than silently
    # letting one shadow the other.
    overlap = by_id.keys() & tasks_by_id.keys()
    if overlap:
        raise ValueError(
            f"artifact-task ID collision: {sorted(overlap)} appear in both spaces. "
            "Artifact IDs (REQ/PLAN/ADR/SCN-N+) and task IDs (TASK/BE/FE/...-N+) "
            "must be disjoint. Rename one side."
        )
    nodes: dict[str, Any] = {**by_id, **tasks_by_id}
    edges: list[Edge] = []
    dangling: list[Edge] = []

    for artifact in artifacts:
        fm = artifact.frontmatter
        sid = artifact.id

        _emit(sid, fm.get("triggered_by"), EdgeType.TRIGGERED_BY, nodes, edges, dangling)
        _emit(sid, fm.get("supersedes"), EdgeType.SUPERSEDES, nodes, edges, dangling)
        _emit(sid, fm.get("resolved_by"), EdgeType.RESOLVED_BY, nodes, edges, dangling)

        implemented_by = fm.get("implemented_by")
        if isinstance(implemented_by, dict):
            _emit(
                sid,
                implemented_by.get("plan"),
                EdgeType.IMPLEMENTED_BY_PLAN,
                nodes,
                edges,
                dangling,
            )

        _emit_list(sid, fm.get("spawns_adrs"), EdgeType.SPAWNS_ADRS, nodes, edges, dangling)
        _emit_list(
            sid, fm.get("implementation_tasks"), EdgeType.IMPLEMENTATION_TASKS,
            nodes, edges, dangling,
        )
        _emit_list(
            sid, fm.get("spawns_tasks"), EdgeType.SPAWNS_TASKS,
            nodes, edges, dangling,
        )

    return Graph(
        artifacts=by_id,
        tasks=tasks_by_id,
        edges=edges,
        dangling_edges=dangling,
    )


# --- chain walker -------------------------------------------------------


class ChainStep(BaseModel):
    """One step in a chain walk: artifact OR task reached, depth, edge label.

    `node_kind="artifact"` (default) for REQ/PLAN/ADR/SCN; `node_kind="task"`
    for TASKS.md rows reached via implementation_tasks / spawns_tasks edges
    (ADR-0005). The id field is `artifact_id` for both, kept as the field
    name for backwards compatibility with pre-task-fanout callers; the
    discriminator is `node_kind`. Task IDs and artifact IDs are guaranteed
    disjoint by build_graph's collision check, so the ID itself is
    unambiguous.
    """

    depth: int
    artifact_id: str
    title: str | None = None
    status: str | None = None
    via_edge: str | None = None
    node_kind: str = "artifact"  # ADR-0005: "artifact" | "task"


def walk_chain(graph: Graph, start_id: str) -> list[ChainStep]:
    """Walk the typed-graph chain starting from `start_id`.

    Direction follows the framework's pipelines:
      ADR  → triggered_by         (forward: PLAN/REQ/SCN)
      PLAN ← implemented_by.plan  (inverse, find the REQ that points here)
      SCN  → resolved_by          (forward: ADR)
      REQ  → implemented_by.plan  (forward: PLAN)

    ADR-0005: every ADR or PLAN reached during the walk also fans out its
    `implementation_tasks` / `spawns_tasks` children as task steps at
    `parent_depth + 1`. Tasks are leaves (no further outgoing edges); the
    fan-out terminates immediately.

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
            node_kind="artifact",
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
                node_kind="artifact",
            )
        )
        visited.add(next_id)
        current = next_artifact
        depth += 1

    # ADR-0005: fan-out task descendants for every ADR/PLAN step. Walk in
    # original order, append tasks immediately after their parent. Implemented
    # as a rebuild rather than in-place mutation so depth stays monotonic.
    rebuilt: list[ChainStep] = []
    for step in chain:
        rebuilt.append(step)
        if step.node_kind != "artifact":
            continue
        parent = graph.get(step.artifact_id)
        if parent is None or parent.type not in (ArtifactType.ADR, ArtifactType.PLAN):
            continue
        edge_type, label = (
            (EdgeType.IMPLEMENTATION_TASKS, "implementation_tasks →")
            if parent.type == ArtifactType.ADR
            else (EdgeType.SPAWNS_TASKS, "spawns_tasks →")
        )
        for edge in graph.edges:
            if edge.source_id != parent.id or edge.edge_type != edge_type:
                continue
            task = graph.get_task(edge.target)
            if task is None:
                continue
            rebuilt.append(
                ChainStep(
                    depth=step.depth + 1,
                    artifact_id=task.id,
                    title=task.title,
                    status=task.status.value,
                    via_edge=label,
                    node_kind="task",
                )
            )
    return rebuilt


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
