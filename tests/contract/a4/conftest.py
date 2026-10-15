"""A4 contract fixtures. `gd_warm` = session-cached copy of gd_tests after one successful `h test` (imported,
gdUnit4 installed); `gdp` = fresh per-test copy of it without .harness/ (B3)."""
import shutil
from pathlib import Path

import pytest

from helpers.h import copy_fixture, run_h


@pytest.fixture(scope="session")
def gd_warm(tmp_path_factory):
    d = tmp_path_factory.mktemp("a4_warm") / "proj"
    copy_fixture("gd_tests", d)
    r = run_h("test", "--project", d, env={"HARNESS_OUT": d.parent / "out"}, timeout=300)
    assert r.rc == 0, f"warm copy of gd_tests: first `h test` rc={r.rc}\n{r}"
    return d


@pytest.fixture
def gdp(tmp_path, gd_warm) -> Path:
    dest = tmp_path / "proj"
    shutil.copytree(gd_warm, dest, ignore=shutil.ignore_patterns(".harness"), symlinks=True)
    return dest


@pytest.fixture
def gd_fresh(tmp_path) -> Path:
    return copy_fixture("gd_tests", tmp_path / "proj")
