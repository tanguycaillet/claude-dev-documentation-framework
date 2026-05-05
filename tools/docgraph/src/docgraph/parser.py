"""Frontmatter parser for typed artifacts, knowledge articles, and TASKS.md rows.

Public surface:
    parse_file(path)                          -> Artifact | None
    parse_directory(root)                     -> tuple[list[Artifact], list[str]]
    walk_knowledge(root)                      -> tuple[list[KnowledgeFile], list[str]]
    parse_tasks_file(path, corpus_config)     -> tuple[list[Task], list[str]]
    KnowledgeFile                             (Pydantic model)
"""

import re
from pathlib import Path
from typing import Any

import frontmatter
from pydantic import BaseModel, Field

from docgraph.config import CorpusConfig
from docgraph.models import Artifact, ArtifactType, Task, TaskStatus

_TYPED_ID_PATTERN = re.compile(r"^(REQ|PLAN|ADR|SCN)-\d+$")


def _classify_id(artifact_id: str) -> ArtifactType | None:
    match = _TYPED_ID_PATTERN.match(artifact_id)
    return ArtifactType(match.group(1)) if match else None


def parse_file(path: Path) -> Artifact | None:
    """Parse a markdown file with YAML frontmatter into an Artifact.

    Returns None when the file has no `id` frontmatter or its id doesn't match
    the typed pattern (REQ|PLAN|ADR|SCN-N+). Knowledge articles, READMEs, and
    TASKS.md are silently skipped this way.

    Raises FileNotFoundError if `path` doesn't exist, or yaml.YAMLError on
    malformed frontmatter.
    """
    post = frontmatter.load(path)
    artifact_id = post.metadata.get("id")
    if not isinstance(artifact_id, str):
        return None
    artifact_type = _classify_id(artifact_id)
    if artifact_type is None:
        return None
    return Artifact(
        id=artifact_id,
        type=artifact_type,
        title=post.metadata.get("title"),
        status=post.metadata.get("status"),
        source_path=path,
        frontmatter=dict(post.metadata),
        content=post.content,
    )


def parse_directory(root: Path) -> tuple[list[Artifact], list[str]]:
    """Walk `root` recursively for *.md files, return (artifacts, errors).

    Read-only: never mutates corpus files. Per-file parse failures are
    captured as human-readable strings and don't abort the walk.
    """
    artifacts: list[Artifact] = []
    errors: list[str] = []
    for md_path in sorted(root.rglob("*.md")):
        if not md_path.is_file():
            continue
        try:
            artifact = parse_file(md_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{md_path}: {type(exc).__name__}: {exc}")
            continue
        if artifact is not None:
            artifacts.append(artifact)
    return artifacts, errors


# --- knowledge articles ---------------------------------------------------


class KnowledgeFile(BaseModel):
    """An untyped reference document, has frontmatter, no typed `id`.

    Surfaced into FTS only; never enters the artifact graph. Addressed by
    relative path slug (e.g. `knowledge/equipment/heat-pump-curves`).
    """

    slug: str
    title: str | None = None
    content: str = ""
    source_path: Path
    frontmatter: dict[str, Any] = Field(default_factory=dict)


def _path_slug(docs_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(docs_root)
    return str(rel.with_suffix("")).replace("\\", "/")


def parse_knowledge_file(path: Path, docs_root: Path) -> KnowledgeFile | None:
    """Return a KnowledgeFile if `path` has frontmatter but no typed `id`.

    Returns None for files with no frontmatter at all (README.md, TASKS.md)
    and for typed artifacts (REQ/PLAN/ADR/SCN).
    """
    post = frontmatter.load(path)
    if not post.metadata:
        return None
    artifact_id = post.metadata.get("id")
    if isinstance(artifact_id, str) and _classify_id(artifact_id) is not None:
        return None
    return KnowledgeFile(
        slug=_path_slug(docs_root, path),
        title=post.metadata.get("title"),
        content=post.content,
        source_path=path,
        frontmatter=dict(post.metadata),
    )


def walk_knowledge(root: Path) -> tuple[list[KnowledgeFile], list[str]]:
    """Walk `root` recursively for knowledge articles. Read-only.

    A knowledge article is a markdown file with non-empty YAML frontmatter
    that does NOT carry a typed `id`. Files without any frontmatter are
    silently skipped.
    """
    articles: list[KnowledgeFile] = []
    errors: list[str] = []
    for md_path in sorted(root.rglob("*.md")):
        if not md_path.is_file():
            continue
        try:
            article = parse_knowledge_file(md_path, root)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{md_path}: {type(exc).__name__}: {exc}")
            continue
        if article is not None:
            articles.append(article)
    return articles, errors


# --- TASKS.md row parsing (ADR-0001 + ADR-0003) ---------------------------

# Status row: leading "- [STATUS] **<bold>**" with optional rest-of-line.
# Status char captures one of {space, ~, x/X, !, /} or empty (`[]` -> warning).
_STATUS_ROW = re.compile(
    r"^- \[(?P<status>[ ~xX!/]?)\]\s+\*\*(?P<bold>[^*]+)\*\*(?P<rest>.*)$"
)

# Bold span content: <ID>[: <TITLE>]. ID per ADR-0001 regex.
_BOLD_ID = re.compile(
    r"^(?P<id>[A-Z]+(?:-[A-Z0-9]+)+[a-z]?)(?:: (?P<title>.+))?$"
)

# H3 section header: ### [<LABEL>] [{phase: <PHASE>}]
# Label may end with ": PLAN-NNNN" for PLAN inheritance.
_SECTION_HEADER = re.compile(r"^### \[(?P<label>[^\]]+)\](?P<rest>.*)$")
_SECTION_PLAN_SUFFIX = re.compile(r":\s*(?P<plan>PLAN-\d+)\s*$")

# Phase annotation, anywhere on the line: {phase: <slug>}
_PHASE_ANNOTATION = re.compile(r"\{phase:\s*([^}]+)\}")

# Backticked refs span: `(...)`. First match in rest-of-line wins.
_REFS_SPAN = re.compile(r"`\((?P<refs>[^`]+)\)`")

# Sub-bullet: two-or-more space indent followed by `- `.
_SUBBULLET = re.compile(r"^  +- ")

# Status mapping (ADR-0001).
_STATUS_MAP: dict[str, TaskStatus] = {
    " ": TaskStatus.TODO,
    "":  TaskStatus.TODO,  # empty `[]` accepted as todo with a warning
    "~": TaskStatus.IN_PROGRESS,
    "x": TaskStatus.DONE,
    "X": TaskStatus.DONE,
    "!": TaskStatus.BLOCKED,
    "/": TaskStatus.PARKED,
}

# Typed-id pattern inside refs. Same as the artifact-target normalization
# regex in graph.py.
_TYPED_ID_IN_REFS = re.compile(
    r"^(?P<prefix>REQ|PLAN|ADR|SCN)-(?P<num>\d+[a-z]?)$"
)
_BARE_NUM_TAIL = re.compile(r"^\d+[a-z]?$")
_ARROW = re.compile(r"\s*(?:<-|←)\s*")


def _parse_section_header(line: str) -> tuple[str | None, str | None]:
    """Parse '### [<LABEL>: PLAN-NNNN] [{phase: <PHASE>}]'. Returns (plan, phase)."""
    m = _SECTION_HEADER.match(line)
    if not m:
        return None, None
    label = m.group("label")
    rest = m.group("rest") or ""
    plan_match = _SECTION_PLAN_SUFFIX.search(label)
    plan = plan_match.group("plan") if plan_match else None
    phase_match = _PHASE_ANNOTATION.search(rest)
    phase = phase_match.group(1).strip() if phase_match else None
    return plan, phase


def _parse_refs(
    text: str,
    line_no: int,
    file_path: Path,
    errors: list[str],
) -> tuple[list[str], dict[str, list[str]]]:
    """Parse the inside of a `(...)` refs span into (flat, by_level).

    Levels are separated by `<-` or `←`. Within a level, comma-separated
    typed-ids; bare numeric tails inherit the prefix from the previous
    full id at the same level (ADR-0001 shorthand).
    """
    inner = text.strip()
    if inner.lower() == "no upstream":
        return [], {}

    flat: list[str] = []
    by_level: dict[str, list[str]] = {}
    for level in _ARROW.split(inner):
        level_prefix: str | None = None
        for raw in level.split(","):
            token = raw.strip()
            if not token:
                continue
            full_id: str | None = None
            m_full = _TYPED_ID_IN_REFS.match(token)
            if m_full:
                level_prefix = m_full.group("prefix")
                full_id = token
            elif level_prefix and _BARE_NUM_TAIL.match(token):
                full_id = f"{level_prefix}-{token}"
            else:
                errors.append(
                    f"{file_path}:{line_no}: refs: cannot parse token {token!r}"
                )
                continue
            flat.append(full_id)
            kind = full_id.split("-", 1)[0].lower()
            by_level.setdefault(kind, []).append(full_id)
    return flat, by_level


def _resolve_status(raw: str, file_path: Path, line_no: int, errors: list[str]) -> TaskStatus | None:
    """Map a status marker char (or empty) to a TaskStatus. Emit warnings."""
    if raw not in _STATUS_MAP:
        errors.append(
            f"{file_path}:{line_no}: unrecognized status marker [{raw!r}], skipping row"
        )
        return None
    if raw == "":
        errors.append(
            f"{file_path}:{line_no}: empty status `[]` accepted as todo (use `[ ]` for explicit todo)"
        )
    return _STATUS_MAP[raw]


def _parse_status_row(
    m: re.Match,
    line_no: int,
    file_path: Path,
    corpus_config: CorpusConfig,
    section_plan: str | None,
    section_phase: str | None,
    errors: list[str],
    unrecognized_prefixes: set[str],
) -> Task | None:
    """Parse a status row (ADR-0001) into a Task. Returns None on malformed input."""
    status = _resolve_status(m.group("status"), file_path, line_no, errors)
    if status is None:
        return None

    bold = m.group("bold").strip()
    rest = m.group("rest") or ""

    m_bold = _BOLD_ID.match(bold)
    if not m_bold:
        errors.append(
            f"{file_path}:{line_no}: bold span {bold!r} doesn't match `<ID>[: <title>]`; "
            f"row skipped (ID regex: {_BOLD_ID.pattern})"
        )
        return None
    task_id = m_bold.group("id")
    title = m_bold.group("title")

    # Domain extraction (ADR-0003): always first segment.
    domain_id = task_id.split("-", 1)[0]
    domain_label = corpus_config.task_domains.get(domain_id)
    if domain_label is None and corpus_config.task_domains:
        unrecognized_prefixes.add(domain_id)

    # Refs (first backticked-parens span). A literal `(no upstream)` is an
    # explicit disclaim and short-circuits section PLAN inheritance below.
    refs: list[str] = []
    refs_by_level: dict[str, list[str]] = {}
    explicit_no_upstream = False
    refs_match = _REFS_SPAN.search(rest)
    if refs_match:
        inner = refs_match.group("refs").strip()
        if inner.lower() == "no upstream":
            explicit_no_upstream = True
        else:
            refs, refs_by_level = _parse_refs(inner, line_no, file_path, errors)

    # Phase: explicit overrides section default.
    phase: str | None = section_phase
    phase_match = _PHASE_ANNOTATION.search(rest)
    if phase_match:
        phase = phase_match.group(1).strip()

    # Section PLAN inheritance: skip when the task explicitly disclaimed via
    # `(no upstream)`, or when the task's refs already include a PLAN.
    if (
        section_plan is not None
        and not explicit_no_upstream
        and not refs_by_level.get("plan")
    ):
        refs_by_level.setdefault("plan", []).append(section_plan)
        refs.append(section_plan)

    return Task(
        id=task_id,
        title=title,
        status=status,
        refs=refs,
        refs_by_level=refs_by_level,
        domain_id=domain_id,
        domain_label=domain_label,
        phase=phase,
        body="",
        source_path=file_path,
        corpus=corpus_config.name,
        line_number=line_no,
    )


def _finalize_task(task: Task | None, body_lines: list[str], tasks: list[Task]) -> None:
    if task is None:
        return
    task.body = "\n".join(body_lines)
    tasks.append(task)


def parse_tasks_file(
    path: Path,
    corpus_config: CorpusConfig | None = None,
) -> tuple[list[Task], list[str]]:
    """Parse a TASKS.md file into Task records per ADR-0001 + ADR-0003.

    Read-only: never writes the file. The body field aggregates sub-bullet
    text for FTS searchability; the file on disk keeps its original
    nested Markdown structure.

    Raises FileNotFoundError if `path` doesn't exist.
    """
    if corpus_config is None:
        corpus_config = CorpusConfig(name="default", path=path.parent or Path("."))

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    tasks: list[Task] = []
    errors: list[str] = []
    unrecognized_prefixes: set[str] = set()

    section_plan: str | None = None
    section_phase: str | None = None
    current_task: Task | None = None
    body_lines: list[str] = []

    for i, line in enumerate(lines, start=1):
        # H1 / H2 boundary: reset section context.
        if line.startswith("# ") or line.startswith("## "):
            _finalize_task(current_task, body_lines, tasks)
            current_task = None
            body_lines = []
            section_plan = None
            section_phase = None
            continue

        # H3 section header: update section context.
        if line.startswith("### "):
            _finalize_task(current_task, body_lines, tasks)
            current_task = None
            body_lines = []
            section_plan, section_phase = _parse_section_header(line)
            continue

        # Status row.
        m_row = _STATUS_ROW.match(line)
        if m_row:
            _finalize_task(current_task, body_lines, tasks)
            body_lines = []
            current_task = _parse_status_row(
                m_row, i, path, corpus_config,
                section_plan, section_phase,
                errors, unrecognized_prefixes,
            )
            continue

        # Sub-bullet under a current task: aggregate into body.
        if _SUBBULLET.match(line) and current_task is not None:
            body_lines.append(line)
            continue

        # Anything else: ignore.

    # Finalize trailing task (no following H2/H3 or new row).
    _finalize_task(current_task, body_lines, tasks)

    # Once-per-prefix warning for unrecognized prefixes (ADR-0003).
    for prefix in sorted(unrecognized_prefixes):
        errors.append(
            f"{path}: unrecognized task ID prefix {prefix!r}; "
            f"add to [corpora.{corpus_config.name}.task_domains] in corpora.toml "
            f"to set domain_label"
        )

    return tasks, errors
