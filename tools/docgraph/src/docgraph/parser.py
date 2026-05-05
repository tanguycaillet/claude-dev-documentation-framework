"""Frontmatter parser for typed artifacts and knowledge articles.

Public surface:
    parse_file(path)            -> Artifact | None
    parse_directory(root)       -> tuple[list[Artifact], list[str]]
    walk_knowledge(root)        -> tuple[list[KnowledgeFile], list[str]]
    KnowledgeFile               (Pydantic model)
"""

import re
from pathlib import Path
from typing import Any

import frontmatter
from pydantic import BaseModel, Field

from docgraph.models import Artifact, ArtifactType

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
