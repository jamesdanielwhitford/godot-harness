"""AC-00.25: pathguard accepts T1's areas, rejects another area; check_lock ignores fixture .harness dirs.
Layer: unit; runs the tools/dev scripts inside a throw-away git repo (never touches this repo)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

DEV = Path(__file__).resolve().parents[3] / "tools" / "dev"


def sh(args, cwd):
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    e.pop("HARNESS_ROOT", None)
    return subprocess.run(args, cwd=cwd, env=e, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tools").mkdir()
    shutil.copytree(DEV, tmp_path / "tools" / "dev", ignore=shutil.ignore_patterns("__pycache__"))
    sh(["git", "init", "-q", "-b", "main"], tmp_path)
    (tmp_path / "README.md").write_text("x")
    sh(["git", "add", "-A"], tmp_path)
    sh(["git", "commit", "-qm", "init"], tmp_path)
    return tmp_path


def put(repo, rel, text="x"):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def guard(repo, role, area):
    return sh([str(repo / "tools/dev/pathguard.sh"), role, area, "working-tree"], repo)


def test_ac_00_25_a1_p0_accepts_fault_and_helper_paths(repo):
    put(repo, "selftest/faults/FAULT-P0-01/fault.toml")
    put(repo, "tests/helpers/h.py")
    put(repo, "tests/conftest.py")
    r = guard(repo, "test-writer", "a1,p0")
    assert r.returncode == 0, r.stdout + r.stderr


def test_ac_00_25_a2_rejects_both(repo):
    put(repo, "selftest/faults/FAULT-P0-01/fault.toml")
    put(repo, "tests/helpers/h.py")
    r = guard(repo, "test-writer", "a2")
    assert r.returncode == 1
    assert "selftest/faults/FAULT-P0-01/fault.toml" in r.stdout and "tests/helpers/h.py" in r.stdout


def test_ac_00_25_bootstrap_and_clean_dirs(repo):
    put(repo, "tests/unit/bootstrap/test_doctor.py")
    put(repo, "selftest/clean/CLEAN-A1-01/fault.toml")
    assert guard(repo, "test-writer", "a1,p0,bootstrap").returncode == 0
    assert guard(repo, "test-writer", "a1,p0").returncode == 1


def test_ac_00_25_check_lock_ignores_new_fixture_harness_dir(repo):
    put(repo, "tests/unit/t.py", "a")
    assert sh([str(repo / "tools/dev/lock_tests.sh")], repo).returncode == 0
    put(repo, "tests/fixtures/x/.harness/out/run.json", "{}")
    r = sh([str(repo / "tools/dev/check_lock.sh")], repo)
    assert r.returncode == 0, r.stdout
