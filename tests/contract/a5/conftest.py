"""A5 contract fixtures. `sc_warm` = session-cached scenario_min copy after one successful `h run` (imported, synced);
`scp` = fresh per-test copy of it without .harness/ (B3); `sc_fresh` = fresh copy of the repo fixture (no .godot, no addons)."""
import shutil
from pathlib import Path

import pytest

from helpers.h import copy_fixture, run_h


@pytest.fixture(scope="session")
def sc_warm(tmp_path_factory):
    d = tmp_path_factory.mktemp("a5_warm") / "proj"
    copy_fixture("scenario_min", d)
    r = run_h("run", "res://scenarios/mover.json", "--project", d, env={"HARNESS_OUT": d.parent / "out"}, timeout=300)
    assert r.rc == 0, f"warm copy of scenario_min: first `h run` rc={r.rc}\n{r}"
    return d


@pytest.fixture
def scp(tmp_path, sc_warm) -> Path:
    dest = tmp_path / "proj"
    shutil.copytree(sc_warm, dest, ignore=shutil.ignore_patterns(".harness"), symlinks=True)
    return dest


@pytest.fixture
def sc_fresh(tmp_path) -> Path:
    return copy_fixture("scenario_min", tmp_path / "proj")
