"""Corpus configuration loader.

Corpora can be declared via `corpora.toml` (durable, multi-corpus) and/or
repeated `--docs` CLI flags (ad-hoc). CLI overrides TOML on name collision.

`--docs PATH` (bare, no `=`) is the single-corpus shorthand; the corpus name
comes from the path basename, with the literal `docs` basename collapsing to
its parent directory name.

Public surface:
    CorpusConfig                 , Pydantic (name, path)
    corpus_name_from_path(path)   -> str
    load_corpora(toml_path, cli_overrides) -> list[CorpusConfig]
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel


class CorpusConfig(BaseModel):
    name: str
    path: Path


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
        out[name] = CorpusConfig(name=name, path=Path(path))
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
