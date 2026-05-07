"""Graph integrity checks.

Reports status inconsistencies, categorises dangling edges, and surfaces
KB freshness drift (ADR-0009). Knowledge articles without typed
frontmatter are ignored here, they have no graph edges and no
last_verified field to check.

In multi-corpus mode the validator runs per-corpus and tags every finding
with its corpus. `validate_graph(graph)` keeps the single-corpus contract.

Public surface:
    ValidationFinding         corpus-tagged structured issue
    DanglingFinding           corpus-tagged dangling edge
    StaleKnowledgeFinding     corpus-tagged KB-freshness drift (ADR-0009)
    ValidationReport          partitioned findings + has_errors property
    validate_graph(graph, corpus="default", knowledge_freshness_days=None)
                              -> ValidationReport
    validate_graphs(graphs, configs=None)
                              -> ValidationReport (merged across corpora)
"""

import re
from datetime import date

from pydantic import BaseModel, Field, computed_field

from docgraph.config import CorpusConfig
from docgraph.models import ArtifactType, Graph

_HEX_HASH = re.compile(r"^[0-9a-f]{6,40}$")
_NARRATIVE = re.compile(r"^this\s+scn", re.IGNORECASE)
# ADR-0009: default freshness threshold when corpora.toml doesn't override.
_DEFAULT_KNOWLEDGE_FRESHNESS_DAYS = 90


class ValidationFinding(BaseModel):
    corpus: str = "default"
    artifact_id: str | None = None
    message: str


class DanglingFinding(BaseModel):
    corpus: str = "default"
    source_id: str
    target: str
    edge_type: str


class StaleKnowledgeFinding(BaseModel):
    """ADR-0009: KB article whose `last_verified` is past the corpus
    freshness threshold. Informational; not counted toward has_errors.

    `kind` echoes the KB's frontmatter `kind` so callers can filter
    drift by operational-knowledge taxonomy (e.g. "all stale RUNBOOKs").
    """

    corpus: str = "default"
    kb_id: str
    last_verified: str            # ISO YYYY-MM-DD
    days_stale: int               # today - last_verified
    kind: str | None = None       # KBKind value, or None if missing/malformed


class ValidationReport(BaseModel):
    status_inconsistencies: list[ValidationFinding] = Field(default_factory=list)
    dangling_commit_hashes: list[DanglingFinding] = Field(default_factory=list)
    dangling_narrative: list[DanglingFinding] = Field(default_factory=list)
    dangling_unexplained: list[DanglingFinding] = Field(default_factory=list)
    # ADR-0009: KB articles past their freshness threshold. Informational;
    # excluded from has_errors.
    stale_knowledge: list[StaleKnowledgeFinding] = Field(default_factory=list)

    @computed_field
    @property
    def has_errors(self) -> bool:
        """True iff there are findings beyond framework-compliant shortcut-rule
        danglings or informational drift (legacy_text_titles, stale_knowledge).

        Declared as `computed_field` so it round-trips through Pydantic's
        model_dump (and therefore the MCP serialization boundary).
        """
        return bool(self.status_inconsistencies or self.dangling_unexplained)


def validate_graph(
    graph: Graph,
    corpus: str = "default",
    knowledge_freshness_days: int | None = None,
) -> ValidationReport:
    """Run integrity checks on one corpus's graph; return a partitioned report.

    Findings are tagged with `corpus`. For multi-corpus environments, prefer
    `validate_graphs()` which iterates and merges.

    `knowledge_freshness_days` (ADR-0009): None uses the default of 90
    days; 0 disables the stale_knowledge check entirely (archival corpora);
    positive values override the default.
    """
    report = ValidationReport()
    _check_status_inconsistencies(graph, corpus, report)
    _classify_dangling_edges(graph, corpus, report)
    _check_stale_knowledge(graph, corpus, report, knowledge_freshness_days)
    return report


def validate_graphs(
    graphs: dict[str, Graph],
    configs: dict[str, CorpusConfig] | None = None,
) -> ValidationReport:
    """Run `validate_graph` per corpus and merge findings into one report.

    Each finding carries its corpus tag, so callers can group/filter by
    corpus without re-running the validator.

    `configs` (ADR-0009): per-corpus configs keyed by name; the validator
    reads `knowledge_freshness_days` from each config to compute the
    stale_knowledge finding. Missing config or absent
    `knowledge_freshness_days` falls back to the default.
    """
    merged = ValidationReport()
    for corpus_name, graph in graphs.items():
        kfd = None
        if configs is not None and corpus_name in configs:
            kfd = configs[corpus_name].knowledge_freshness_days
        sub = validate_graph(graph, corpus=corpus_name, knowledge_freshness_days=kfd)
        merged.status_inconsistencies.extend(sub.status_inconsistencies)
        merged.dangling_commit_hashes.extend(sub.dangling_commit_hashes)
        merged.dangling_narrative.extend(sub.dangling_narrative)
        merged.dangling_unexplained.extend(sub.dangling_unexplained)
        merged.stale_knowledge.extend(sub.stale_knowledge)
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
    """Partition dangling edges into commit-hash / narrative / unexplained.

    The framework's shortcut rule allows trivial fixes to set
    `resolved_by: <commit-hash>` instead of an ADR id. Those edges are
    dangling-by-design; we surface them but they don't count as errors.
    Targets starting with "this SCN ..." are narrative explanations; same
    treatment.
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
        else:
            report.dangling_unexplained.append(finding)


def _check_stale_knowledge(
    graph: Graph,
    corpus: str,
    report: ValidationReport,
    knowledge_freshness_days: int | None,
) -> None:
    """ADR-0009: flag KB articles whose `last_verified` is past the
    freshness threshold.

    `knowledge_freshness_days = 0` disables the check (archival corpora).
    `knowledge_freshness_days = None` falls back to the 90-day default.
    KBs with `status` in {superseded, deprecated} are skipped — they're
    explicitly retired, not silently stale.
    """
    threshold = (
        knowledge_freshness_days
        if knowledge_freshness_days is not None
        else _DEFAULT_KNOWLEDGE_FRESHNESS_DAYS
    )
    if threshold == 0:
        return
    today = date.today()
    for kb in graph.list_by_type(ArtifactType.KB):
        kb_status = kb.frontmatter.get("status")
        if kb_status in ("superseded", "deprecated"):
            continue
        last_verified = kb.frontmatter.get("last_verified")
        # Coerce to a date object regardless of YAML's auto-parsing.
        if isinstance(last_verified, date):
            lv_date = last_verified
            lv_str = last_verified.isoformat()
        elif isinstance(last_verified, str):
            try:
                lv_date = date.fromisoformat(last_verified)
                lv_str = last_verified
            except ValueError:
                # Malformed dates surface elsewhere as parse errors; skip
                # silently here rather than synthesising a finding for
                # data we can't measure.
                continue
        else:
            continue
        days_stale = (today - lv_date).days
        if days_stale > threshold:
            report.stale_knowledge.append(
                StaleKnowledgeFinding(
                    corpus=corpus,
                    kb_id=kb.id,
                    last_verified=lv_str,
                    days_stale=days_stale,
                    kind=kb.frontmatter.get("kind"),
                )
            )
