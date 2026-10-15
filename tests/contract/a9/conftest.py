"""A9 contract fixtures. The sample is the fixture (D-1): `copy_fixture("@sample", ...)` excludes .godot/.harness/
addons/harness/addons/gdUnit4 and runs `h sync --no-gdunit` on the copy (R-51, N28).
`sample_fresh` = fresh copy per test (nothing imported yet); `sample_warm` = session copy after one `h check`
(imported); `sp` = per-test copy of the warm one without .harness/ (B3)."""
import shutil
from pathlib import Path

import pytest

from helpers.h import copy_fixture, run_h


@pytest.fixture
def sample_fresh(tmp_path) -> Path:
    return copy_fixture("@sample", tmp_path / "proj")


@pytest.fixture(scope="session")
def sample_warm(tmp_path_factory):
    d = tmp_path_factory.mktemp("a9_warm") / "proj"
    copy_fixture("@sample", d)
    r = run_h("check", "--project", d, env={"HARNESS_OUT": d.parent / "out"}, timeout=300)
    assert r.rc == 0, f"warm @sample copy: first `h check` rc={r.rc}\n{r}"
    return d


@pytest.fixture
def sp(tmp_path, sample_warm) -> Path:
    dest = tmp_path / "proj"
    shutil.copytree(sample_warm, dest, ignore=shutil.ignore_patterns(".harness"), symlinks=True)
    return dest
