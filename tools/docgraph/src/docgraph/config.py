"""Corpus configuration loader.

Corpora can be declared via `corpora.toml` (durable, multi-corpus) and/or
repeated `--docs` CLI flags (ad-hoc). CLI overrides TOML on name collision.

`--docs PATH` (bare, no `=`) is the single-corpus shorthand; the corpus name
comes from the path basename, with the literal `docs` basename collapsing to
its parent directory name.

Each corpus may declare an optional `[corpora.<name>.task_domains]` table
mapping task ID prefixes to human-readable domain labels. Used by the
TASKS.md parser (parse_tasks_file) to set Task.domain_label. Keys must
match the uppercase-letters-only pattern; lowercase/digit/dash keys raise
at load time.

Public surface:
    CorpusConfig                 , Pydantic (name, path, task_domains)
    corpus_name_from_path(path)   -> str
    load_corpora(toml_path, cli_overrides) -> list[CorpusConfig]
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


# ADR-0003: keys in [corpora.<name>.task_domains] must be uppercase letters
# only, matching the first segment of the task ID regex (ADR-0001). Lowercase
# or composite keys (e.g. "BE-DEV") are rejected at load time so config drift
# can't silently desync from the parser's domain extraction rule.
_TASK_DOMAIN_KEY = re.compile(r"^[A-Z]+$")


class CorpusConfig(BaseModel):
    name: str
    path: Path
    task_domains: dict[str, str] = Field(default_factory=dict)
    # ADR-0009: per-corpus override for the KB freshness threshold. None
    # means "use the default" (90 days). 0 disables the stale_knowledge
    # check entirely (useful for archival corpora where KBs intentionally
    # don't refresh).
    knowledge_freshness_days: int | None = None


def corpus_name_from_path(path: Path) -> str:
    """Derive a corpus name from a docs root path.

    Returns `path.name`; collapses literal `"docs"` basename to `path.parent.name`
    so `~/myproject/docs` becomes corpus `myproject`.
    """
    name = path.name
    if name == "docs":
        return path.parent.name
    return name


def _validate_corpus_name(name: str) -> None:
    if ":" in name:
        # `:` is reserved as the corpus/id separator in corpus:id addressing.
        raise ValueError(
            f"corpus name {name!r} contains a colon, reserved for corpus:id addressing"
        )
    if not name or not name.strip():
        raise ValueError("corpus name must be non-empty")


def _validate_task_domains(corpus_name: str, raw: dict) -> dict[str, str]:
    """Normalize and validate a [corpora.<name>.task_domains] block.

    Keys must match `^[A-Z]+$` (ADR-0003). Values must be strings. The
    block is optional; absence is equivalent to an empty dict.
    """
    if not isinstance(raw, dict):
        raise ValueError(
            f"corpus {corpus_name!r}: task_domains must be a TOML table, got {type(raw).__name__}"
        )
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not _TASK_DOMAIN_KEY.match(key):
            raise ValueError(
                f"corpus {corpus_name!r}: task_domains key {key!r} must be uppercase letters only "
                f"(no digits, dashes, or lowercase). To group multiple ID styles under one domain, "
                f"use the first ID segment as the prefix."
            )
        if not isinstance(value, str):
            raise ValueError(
                f"corpus {corpus_name!r}: task_domains[{key!r}] must be a string, got {type(value).__name__}"
            )
        out[key] = value
    return out


def _from_toml(toml_path: Path) -> dict[str, CorpusConfig]:
    if not toml_path.exists():
        raise FileNotFoundError(f"corpora.toml not found: {toml_path}")
    with toml_path.open("rb") as fh:
        data = tomllib.load(fh)
    corpora = data.get("corpora", {})
    out: dict[str, CorpusConfig] = {}
    for name, body in corpora.items():
        _validate_corpus_name(name)
        path = body["path"]
        task_domains = _validate_task_domains(name, body.get("task_domains", {}))
        # ADR-0009: optional per-corpus knowledge freshness threshold.
        kfd = body.get("knowledge_freshness_days")
        if kfd is not None and not isinstance(kfd, int):
            raise ValueError(
                f"corpus {name!r}: knowledge_freshness_days must be an int (or absent), "
                f"got {type(kfd).__name__}"
            )
        if isinstance(kfd, int) and kfd < 0:
            raise ValueError(
                f"corpus {name!r}: knowledge_freshness_days must be >= 0 (got {kfd})"
            )
        out[name] = CorpusConfig(
            name=name,
            path=Path(path),
            task_domains=task_domains,
            knowledge_freshness_days=kfd,
        )
    return out


def _from_cli(cli_overrides: list[str]) -> dict[str, CorpusConfig]:
    """Parse `name=path` and bare `path` items into a name-keyed dict."""
    out: dict[str, CorpusConfig] = {}
    for raw in cli_overrides:
        if "=" in raw:
            name, _, path_str = raw.partition("=")
            if not name or not path_str:
                raise ValueError(
                    f"--docs {raw!r}: expected `name=path` or bare `path`"
                )
            _validate_corpus_name(name)
            out[name] = CorpusConfig(name=name, path=Path(path_str))
        else:
            path = Path(raw)
            name = corpus_name_from_path(path)
            _validate_corpus_name(name)
            out[name] = CorpusConfig(name=name, path=path)
    return out


def load_corpora(
    toml_path: Path | None,
    cli_overrides: list[str],
) -> list[CorpusConfig]:
    """Merge TOML + CLI corpus declarations. CLI overrides TOML on name collision.

    Returns the combined list, name-deduplicated, in insertion order
    (TOML names first, then CLI-only names).
    """
    merged: dict[str, CorpusConfig] = {}
    if toml_path is not None:
        merged.update(_from_toml(toml_path))
    merged.update(_from_cli(cli_overrides))
    if not merged:
        raise ValueError(
            "no corpora configured, provide corpora.toml or one or more --docs flags"
        )
    return list(merged.values())
