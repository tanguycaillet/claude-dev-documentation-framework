"""Gated integration test: docgraph-migrate-adr-tasks against the
real energyflow corpus.

The fixture lives outside the public repo at
~/claude-dev-documentation-framework-internal/test-fixtures/. When the
fixture isn't present the test skips, so CI passes. When it IS present,
the test exercises the real-world scale (75+ ADRs, 200+ tasks) to catch
performance, edge-case parsing, and large-output bugs that the synthetic
fixture won't surface.
"""

import os
import time
from pathlib import Path

import pytest

from docgraph.config import CorpusConfig
from docgraph.migrate import _load_adr_paths, plan_run, main
from docgraph.parser import parse_tasks_file


def _fixture_dir() -> Path:
    """Resolve the energyflow fixture path; honors DOCGRAPH_ENERGYFLOW_FIXTURE env override."""
    override = os.environ.get("DOCGRAPH_ENERGYFLOW_FIXTURE")
    if override:
        return Path(override)
    return Path.home() / "claude-dev-documentation-framework-internal" / "test-fixtures"


@pytest.fixture
def energyflow_paths():
    base = _fixture_dir()
    docs = base / "energyflow-docs"
    tasks = base / "energyflow-TASKS.md"
    if not docs.exists() or not tasks.exists():
        pytest.skip(f"energyflow fixture not found at {base}")
    return docs, tasks


def test_dry_run_does_not_crash_on_real_corpus(energyflow_paths, capsys):
    """75 ADRs + 1053-line TASKS.md, dry-run mode must complete cleanly."""
    docs, tasks = energyflow_paths
    rc = main([str(docs), str(tasks)])
    assert rc == 0  # dry-run always exits 0
    out = capsys.readouterr().out
    assert "DRY-RUN: docgraph-migrate-adr-tasks" in out
    assert "SUMMARY" in out
    assert "ready to migrate:" in out
    assert "already migrated:" in out
    assert "blocked (unmatched):" in out


def test_plan_run_categorizes_every_adr(energyflow_paths):
    """Every ADR must appear in exactly one of ready / no-op / blocked."""
    docs, tasks_path = energyflow_paths
    cfg = CorpusConfig(name="energyflow", path=docs)
    tasks, _ = parse_tasks_file(tasks_path, cfg)
    adr_paths = _load_adr_paths(docs)
    assert len(adr_paths) >= 50, f"expected at least 50 ADRs in fixture, got {len(adr_paths)}"

    plans = plan_run(adr_paths, tasks)
    assert len(plans) == len(adr_paths)
    for p in plans:
        assert p.status in {"ready", "no-op", "blocked"}, p


def test_dry_run_finishes_quickly_on_real_corpus(energyflow_paths):
    """Performance gate: 75 ADRs + 200+ tasks should plan in well under the budget.

    Default budget is 10s, which is generous for the typical case
    (energyflow plans in ~50ms locally) but lenient enough to ride out
    slow CI runners. Override via `DOCGRAPH_PERF_BUDGET` env var (in
    seconds, float) when the machine is unusually slow or when you want
    a tighter local guardrail.
    """
    docs, tasks_path = energyflow_paths
    cfg = CorpusConfig(name="energyflow", path=docs)
    tasks, _ = parse_tasks_file(tasks_path, cfg)
    adr_paths = _load_adr_paths(docs)

    start = time.perf_counter()
    plan_run(adr_paths, tasks)
    elapsed = time.perf_counter() - start
    budget = float(os.getenv("DOCGRAPH_PERF_BUDGET", "10.0"))
    assert elapsed < budget, f"plan_run took {elapsed:.2f}s (budget <{budget:.2f}s)"


def test_dry_run_does_not_modify_any_file(energyflow_paths, tmp_path):
    """Defensive: dry-run mode must NEVER write to ADR or TASKS files.

    Snapshots a few ADRs before and after; verifies bytes-identical.
    """
    docs, tasks = energyflow_paths
    sample_adrs = sorted(docs.glob("decisions/*.md"))[:5]
    snapshots = {p: p.read_bytes() for p in sample_adrs}
    main([str(docs), str(tasks)])  # dry-run
    for p, before in snapshots.items():
        assert p.read_bytes() == before, f"dry-run wrote to {p}"
