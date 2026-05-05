"""Pydantic data models for the typed-graph layer."""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    REQ = "REQ"
    PLAN = "PLAN"
    ADR = "ADR"
    SCN = "SCN"


class EdgeType(str, Enum):
    """The seven typed edges resolved from artifact frontmatter.

    Five point at artifact IDs (TRIGGERED_BY, SUPERSEDES, RESOLVED_BY,
    IMPLEMENTED_BY_PLAN, SPAWNS_ADRS); two point at free-text task names
    (IMPLEMENTATION_TASKS, SPAWNS_TASKS) since TASKS.md is not yet a
    parsed graph node.
    """

    TRIGGERED_BY = "triggered_by"
    SUPERSEDES = "supersedes"
    RESOLVED_BY = "resolved_by"
    IMPLEMENTED_BY_PLAN = "implemented_by.plan"
    SPAWNS_ADRS = "spawns_adrs"
    IMPLEMENTATION_TASKS = "implementation_tasks"
    SPAWNS_TASKS = "spawns_tasks"


_TASK_TARGET_EDGES: frozenset[EdgeType] = frozenset(
    {EdgeType.IMPLEMENTATION_TASKS, EdgeType.SPAWNS_TASKS}
)


class Artifact(BaseModel):
    """A typed documentation artifact (REQ/PLAN/ADR/SCN).

    `corpus` tags the originating corpus. Default `"default"` preserves
    single-corpus behaviour for parser callers that don't yet know which
    corpus they're building for; the indexer + query layer set it
    explicitly when persisting / reading back.
    """

    id: str
    type: ArtifactType
    title: str | None = None
    status: str | None = None
    source_path: Path
    corpus: str = "default"
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    content: str = ""


class Edge(BaseModel):
    """A typed relationship from an artifact to another artifact or task-text."""

    source_id: str
    target: str
    edge_type: EdgeType

    @property
    def target_is_artifact(self) -> bool:
        return self.edge_type not in _TASK_TARGET_EDGES


class Graph(BaseModel):
    """In-memory typed graph of artifacts and their resolved edges."""

    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)
    dangling_edges: list[Edge] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)

    def get(self, artifact_id: str) -> Artifact | None:
        return self.artifacts.get(artifact_id)

    def list_by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        return [a for a in self.artifacts.values() if a.type == artifact_type]
