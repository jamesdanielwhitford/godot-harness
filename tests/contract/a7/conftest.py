"""Fixtures local to the A7 contract tests (owner: T7)."""
from __future__ import annotations

import shutil

import pytest

from a7util import SUITE, trace
from helpers.h import copy_fixture, run_h


@pytest.fixture(scope="session")
def feel_base(tmp_path_factory):
    """One synced + imported copy of feel_min (the 'warm' state of the spec's wall-clock budgets)."""
    d = tmp_path_factory.mktemp("feel_base") / "proj"
    copy_fixture("feel_min", d)
    out = d.parent / "out"
    r = run_h("sync", "--no-gdunit", "--project", d, env={"HARNESS_OUT": out}, timeout=120)
    r = run_h("import", "--project", d, env={"HARNESS_OUT": out}, timeout=240)
    return d


@pytest.fixture
def feel(tmp_path, feel_base):
    """Fresh per-test copy of the warm feel_min (B3: tests never touch the repo fixture)."""
    dest = tmp_path / "proj"
    shutil.copytree(feel_base, dest, ignore=shutil.ignore_patterns(".harness"))
    return dest


@pytest.fixture(scope="session")
def clean_run(feel_base, tmp_path_factory):
    """(Result, project dir) of one `h trace` on the clean fixture, shared by the read-only AC-07.9..11 tests."""
    d = tmp_path_factory.mktemp("feel_clean") / "proj"
    shutil.copytree(feel_base, d, ignore=shutil.ignore_patterns(".harness"))
    r = trace(d, SUITE)
    return r, d
