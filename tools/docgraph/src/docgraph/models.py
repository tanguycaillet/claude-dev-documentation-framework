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


class TaskStatus(str, Enum):
    """The five task statuses parsed from TASKS.md row checkboxes (ADR-0001).

    Mapping from row format:
        [ ] -> todo
        [~] -> in-progress
        [x] -> done
        [!] -> blocked
        [/] -> parked
    """

    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    BLOCKED = "blocked"
    PARKED = "parked"


class EdgeType(str, Enum):
    """The seven typed edges resolved from artifact frontmatter.

    All seven point at addressable graph nodes: five at artifact IDs
    (TRIGGERED_BY, SUPERSEDES, RESOLVED_BY, IMPLEMENTED_BY_PLAN,
    SPAWNS_ADRS) and two at task IDs (IMPLEMENTATION_TASKS,
    SPAWNS_TASKS). The task-target edges previously held free-text
    titles; M2 of the TASKS.md-as-graph-node work flipped them to
    resolve against task records.
    """

    TRIGGERED_BY = "triggered_by"
    SUPERSEDES = "supersedes"
    RESOLVED_BY = "resolved_by"
    IMPLEMENTED_BY_PLAN = "implemented_by.plan"
    SPAWNS_ADRS = "spawns_adrs"
    IMPLEMENTATION_TASKS = "implementation_tasks"
    SPAWNS_TASKS = "spawns_tasks"


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
    """A typed relationship from an artifact to another node (artifact or task).

    After M2 every edge target is meant to resolve to a graph node; the
    DB still stores a `target_is_node` column as a forward-compat slot
    for any future non-node target type, but the in-memory Edge model
    doesn't carry it. Callers that care about resolution status read
    Graph.dangling_edges vs Graph.edges instead.
    """

    source_id: str
    target: str
    edge_type: EdgeType


class Task(BaseModel):
    """A parseable row from TASKS.md (ADR-0001).

    `domain_id` is always set when the ID matches the regex (the substring
    of `id` before the first `-`, per ADR-0003). `domain_label` is the
    looked-up human-readable label from CorpusConfig.task_domains, or None
    for an unrecognized prefix.

    `refs` is the flattened list of upstream typed-IDs from the row's
    backticked annotation. `refs_by_level` carries the same data partitioned
    by artifact kind so callers that care about the chain shape (e.g. "all
    ADRs this task implements") don't have to re-classify.

    `body` aggregates the task's freeform Markdown sub-bullets into one
    string for FTS searchability; the file on disk keeps its original
    nested structure (REQ-0001 confirmed: parser is read-only).
    """

    id: str
    title: str | None = None
    status: TaskStatus = TaskStatus.TODO
    refs: list[str] = Field(default_factory=list)
    refs_by_level: dict[str, list[str]] = Field(default_factory=dict)
    domain_id: str | None = None
    domain_label: str | None = None
    phase: str | None = None
    body: str = ""
    source_path: Path
    corpus: str = "default"
    line_number: int


class Graph(BaseModel):
    """In-memory typed graph of artifacts, tasks, and their resolved edges.

    After M2 of the TASKS.md-as-graph-node work, tasks are addressable
    nodes. `get()` looks up artifacts; use `get_task()` for tasks.
    """

    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    tasks: dict[str, Task] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)
    dangling_edges: list[Edge] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)

    def get(self, artifact_id: str) -> Artifact | None:
        return self.artifacts.get(artifact_id)

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def list_by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        return [a for a in self.artifacts.values() if a.type == artifact_type]
