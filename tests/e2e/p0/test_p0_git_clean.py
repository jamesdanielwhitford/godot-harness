"""AC-00.24 (B3): running the suite must not leave changes under tests/ or selftest/. Layer: e2e.
Compares `git status --porcelain tests selftest` with the snapshot taken at session start (tests/conftest.py), so it
holds on an uncommitted working tree too. To avoid passing vacuously it first runs a real verb on a temp copy."""
from helpers.h import assert_contract, run_h


def test_ac_00_24_suite_leaves_tests_and_selftest_clean(mkproj, tmp_path, git_porcelain_baseline, current_porcelain):
    p = mkproj()
    r = run_h("check", "--project", p, env={"HARNESS_OUT": str(tmp_path / "out")}, timeout=120)
    assert_contract(r)
    assert r.rc == 0, r
    now = current_porcelain()
    assert now == git_porcelain_baseline, (
        "files under tests/ or selftest/ changed during the run (B3: copy fixtures first):\n"
        f"before:\n{git_porcelain_baseline}\nafter:\n{now}")
