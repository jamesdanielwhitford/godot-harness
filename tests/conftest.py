"""Shared pytest configuration (T1, areas a1/p0/bootstrap). Read-only for other areas.

- registers the markers `godot`, `xvfb`, `slow` (> 30 s)
- puts `tests/` on sys.path so `from helpers.h import ...` works
- puts `tools/harness` on sys.path ONLY while collecting files under tests/unit
  (REVIEW R-01: unit tests may import the closed list of pure harness modules)
- records `git status --porcelain tests selftest` at session start (AC-00.24)
- fixtures: `mkproj` (fresh fixture copy), `warm_copy` (copy of an imported fixture, cached per session)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent

if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


def pytest_configure(config):
    config.addinivalue_line("markers", "godot: needs the Godot binary")
    config.addinivalue_line("markers", "xvfb: needs xvfb-run")
    config.addinivalue_line("markers", "slow: takes more than 30 s")


def pytest_collect_file(file_path, parent):
    # Only unit tests may import harness.* (R-01). The insert is idempotent.
    try:
        rel = Path(file_path).resolve().relative_to(TESTS)
    except ValueError:
        return None
    if rel.parts and rel.parts[0] == "unit":
        p = str(REPO / "tools" / "harness")
        if p not in sys.path:
            sys.path.insert(0, p)
    return None


def _porcelain() -> str:
    r = subprocess.run(
        ["git", "status", "--porcelain", "--", "tests", "selftest"],
        cwd=REPO, capture_output=True, text=True,
    )
    return r.stdout


def pytest_sessionstart(session):
    session.config._git_porcelain_baseline = _porcelain()


@pytest.fixture(scope="session")
def git_porcelain_baseline(request):
    return request.config._git_porcelain_baseline


@pytest.fixture(scope="session")
def current_porcelain():
    return _porcelain


@pytest.fixture
def mkproj(tmp_path):
    """mkproj("clean_min") -> Path of a fresh copy (B3) under tmp_path/proj."""
    from helpers.h import copy_fixture

    def _mk(name: str = "clean_min", sub: str = "proj") -> Path:
        return copy_fixture(name, tmp_path / sub)

    return _mk


@pytest.fixture(scope="session")
def warm(tmp_path_factory):
    """warm("clean_min") -> Path of a session-cached copy after `h import` (contract 2.11)."""
    from helpers.h import copy_fixture, run_h

    cache: dict[str, Path] = {}

    def _get(name: str) -> Path:
        if name not in cache:
            d = tmp_path_factory.mktemp("warm_" + name) / "proj"
            copy_fixture(name, d)
            r = run_h("import", "--project", str(d), env={"HARNESS_OUT": str(d.parent / "out")})
            assert r.rc == 0, f"warm copy of {name}: `h import` rc={r.rc}\n{r.stdout}"
            cache[name] = d
        return cache[name]

    return _get


@pytest.fixture
def mkwarm(tmp_path, warm):
    """mkwarm("clean_min") -> fresh per-test copy of the imported copy (keeps .godot/)."""

    def _mk(name: str = "clean_min", sub: str = "proj") -> Path:
        src = warm(name)
        dest = tmp_path / sub
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".harness"))
        return dest

    return _mk
