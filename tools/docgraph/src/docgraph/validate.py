"""Graph integrity checks.

Reports status inconsistencies and categorises dangling edges. Knowledge
articles aren't validated here, they have no graph edges.

In multi-corpus mode the validator runs per-corpus and tags every finding
with its corpus. `validate_graph(graph)` keeps the single-corpus contract.

Public surface:
    ValidationFinding         corpus-tagged structured issue
    DanglingFinding           corpus-tagged dangling edge
    ValidationReport          partitioned findings + has_errors property
    validate_graph(graph, corpus="default") -> ValidationReport
    validate_graphs(graphs)                -> ValidationReport (merged across corpora)
"""

import re

from pydantic import BaseModel, Field, computed_field

from docgraph.models import ArtifactType, EdgeType, Graph

_HEX_HASH = re.compile(r"^[0-9a-f]{6,40}$")
_NARRATIVE = re.compile(r"^this\s+scn", re.IGNORECASE)
# ADR-0007: shape of a valid task-ID. Same regex as ADR-0001 / migrate.py.
_TASK_ID_RE = re.compile(r"^[A-Z]+(?:-[A-Z0-9]+)+[a-z]?$")
# ADR-0007: edges authored as free-text in legacy corpora; classifier
# scopes legacy_text_titles to these.
_TASK_TARGET_EDGES = {EdgeType.IMPLEMENTATION_TASKS, EdgeType.SPAWNS_TASKS}


class ValidationFinding(BaseModel):
    corpus: str = "default"
    artifact_id: str | None = None
    message: str


class DanglingFinding(BaseModel):
    corpus: str = "default"
    source_id: str
    target: str
    edge_type: str


class ValidationReport(BaseModel):
    status_inconsistencies: list[ValidationFinding] = Field(default_factory=list)
    dangling_commit_hashes: list[DanglingFinding] = Field(default_factory=list)
    dangling_narrative: list[DanglingFinding] = Field(default_factory=list)
    # ADR-0007: legacy free-text in implementation_tasks / spawns_tasks
    # from corpora authored before the TASKS.md row-format spec stabilised.
    # Informational; doesn't count toward has_errors.
    legacy_text_titles: list[DanglingFinding] = Field(default_factory=list)
    dangling_unexplained: list[DanglingFinding] = Field(default_factory=list)

    @computed_field
    @property
    def has_errors(self) -> bool:
        """True iff there are findings beyond framework-compliant shortcut-rule
        danglings or legacy free-text drift.

        Declared as `computed_field` so it round-trips through Pydantic's
        model_dump (and therefore the MCP serialization boundary).

        ADR-0007: legacy_text_titles deliberately excluded — drift visibility
        without gatekeeping. Forcing has_errors=True on every pre-spec corpus
        would defeat the field's actionable signal.
        """
        return bool(self.status_inconsistencies or self.dangling_unexplained)


def validate_graph(graph: Graph, corpus: str = "default") -> ValidationReport:
    """Run integrity checks on one corpus's graph; return a partitioned report.

    Findings are tagged with `corpus`. For multi-corpus environments, prefer
    `validate_graphs()` which iterates and merges.
    """
    report = ValidationReport()
    _check_status_inconsistencies(graph, corpus, report)
    _classify_dangling_edges(graph, corpus, report)
    return report


def validate_graphs(graphs: dict[str, Graph]) -> ValidationReport:
    """Run `validate_graph` per corpus and merge findings into one report.

    Each finding carries its corpus tag, so callers can group/filter by
    corpus without re-running the validator.
    """
    merged = ValidationReport()
    for corpus_name, graph in graphs.items():
        sub = validate_graph(graph, corpus=corpus_name)
        merged.status_inconsistencies.extend(sub.status_inconsistencies)
        merged.dangling_commit_hashes.extend(sub.dangling_commit_hashes)
        merged.dangling_narrative.extend(sub.dangling_narrative)
        merged.legacy_text_titles.extend(sub.legacy_text_titles)
        merged.dangling_unexplained.extend(sub.dangling_unexplained)
    return merged


_VALID_UPSTREAM_STATUSES = {"accepted", "superseded"}


def _check_status_inconsistencies(graph: Graph, corpus: str, report: ValidationReport) -> None:
    """Flag artifacts whose status implies an upstream that isn't there yet.

    A PLAN with status `superseded` is a valid upstream, it was accepted at
    the time the ADR or REQ pointed at it; only `proposed` (or stranger
    statuses) indicate genuine drift.
    """
    for adr in graph.list_by_type(ArtifactType.ADR):
        if adr.status != "accepted":
            continue
        triggered_by = adr.frontmatter.get("triggered_by")
        if not isinstance(triggered_by, str):
            continue
        target = graph.get(triggered_by)
        if target is None or target.type != ArtifactType.PLAN:
            continue
        if target.status not in _VALID_UPSTREAM_STATUSES:
            report.status_inconsistencies.append(
                ValidationFinding(
                    corpus=corpus,
                    artifact_id=adr.id,
                    message=(
                        f"ADR {adr.id} (accepted) triggered by "
                        f"{target.id} (status: {target.status})"
                    ),
                )
            )

    for req in graph.list_by_type(ArtifactType.REQ):
        if req.status != "verified":
            continue
        impl = req.frontmatter.get("implemented_by")
        if not isinstance(impl, dict):
            continue
        plan_id = impl.get("plan")
        if not isinstance(plan_id, str):
            continue
        plan = graph.get(plan_id)
        if plan is not None and plan.status not in _VALID_UPSTREAM_STATUSES:
            report.status_inconsistencies.append(
                ValidationFinding(
                    corpus=corpus,
                    artifact_id=req.id,
                    message=(
                        f"REQ {req.id} (verified) implemented_by "
                        f"{plan.id} (status: {plan.status})"
                    ),
                )
            )

    for scn in graph.list_by_type(ArtifactType.SCN):
        resolved_by = scn.frontmatter.get("resolved_by")
        if not isinstance(resolved_by, str):
            continue
        if scn.status != "resolved":
            report.status_inconsistencies.append(
                ValidationFinding(
                    corpus=corpus,
                    artifact_id=scn.id,
                    message=(
                        f"SCN {scn.id} has resolved_by={resolved_by!r} "
                        f"but status is {scn.status!r} (expected 'resolved')"
                    ),
                )
            )


def _classify_dangling_edges(graph: Graph, corpus: str, report: ValidationReport) -> None:
    """Partition dangling edges into four categories.

    The framework's shortcut rule allows trivial fixes to set
    `resolved_by: <commit-hash>` instead of an ADR id. Those edges are
    dangling-by-design; we surface them but they don't count as errors.
    Targets starting with "this SCN ..." are narrative explanations; same
    treatment.

    ADR-0007: task-target edges (`implementation_tasks`, `spawns_tasks`)
    whose target isn't a valid task-ID shape are treated as legacy
    free-text drift — informational, not error-counting. Real broken
    artifact-ID refs (`triggered_by: ADR-9999`) keep landing in
    `dangling_unexplained` because their target *does* match the
    artifact-ID shape, just doesn't resolve to a node.
    """
    for edge in graph.dangling_edges:
        finding = DanglingFinding(
            corpus=corpus,
            source_id=edge.source_id,
            target=edge.target,
            edge_type=edge.edge_type.value,
        )
        if _HEX_HASH.match(edge.target):
            report.dangling_commit_hashes.append(finding)
        elif _NARRATIVE.match(edge.target):
            report.dangling_narrative.append(finding)
        elif (
            edge.edge_type in _TASK_TARGET_EDGES
            and not _TASK_ID_RE.match(edge.target)
        ):
            report.legacy_text_titles.append(finding)
        else:
            report.dangling_unexplained.append(finding)
