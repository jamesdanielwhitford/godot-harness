"""P0 contract: `h selftest` and the fault format (AC-00.21-23). Layer: contract (+ slow)."""
import json
import re
from pathlib import Path

import pytest

from helpers.h import FIXTURES, REPO, assert_contract, run_h, tree_hash

TREES = FIXTURES / "selftest_trees"


def env(tmp_path, **kw):
    return {"HARNESS_OUT": str(tmp_path / "out"), "HARNESS_TMP": str(tmp_path / "ht"), **kw}


def matrix(r):
    return json.loads(r.artifact("matrix.json").read_text())


def entries_of(m):
    return m["entries"] if isinstance(m, dict) and "entries" in m else m


@pytest.mark.slow
@pytest.mark.godot
def test_ac_00_21_selftest_p0_catches_everything(tmp_path):
    r = run_h("selftest", "--area", "P0", env=env(tmp_path), timeout=400)
    assert_contract(r)
    assert r.rc == 0, r
    assert re.match(r"^8 total, 8 caught, 0 missed \(must 0, nice 0\), 0 slow, 0 overflow, 0 broken$", r.stats["faults"]), r.stats
    assert re.match(r"^2 total, 2 pass, 0 false-positive$", r.stats["clean"]), r.stats
    ents = entries_of(matrix(r))
    assert len(ents) == 10
    assert {e["id"] for e in ents} >= {f"FAULT-P0-0{i}" for i in range(1, 9)} | {"CLEAN-P0-01", "CLEAN-P0-02"}
    assert all(e["result"] in ("CAUGHT", "PASS") for e in ents)
    assert r.wall <= 120, f"{r.wall:.0f}s"


def test_ac_00_22_unmeetable_must_fault_is_missed_rc_1(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "miss_must", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.search(r"^FAIL +FAULT-P0-91: MISSED", r.stdout, re.M), r.stdout
    assert re.match(r"^1 total, 0 caught, 1 missed \(must 1, nice 0\)", r.stats["faults"]), r.stats


def test_ac_00_22_nice_miss_only_is_rc_5(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "miss_nice", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 5 and r.verdict == "WARN", r
    assert "FAULT-P0-92" in r.stdout and "MISSED" in r.stdout
    assert re.match(r"^1 total, 0 caught, 1 missed \(must 0, nice 1\)", r.stats["faults"]), r.stats


def test_ac_00_22_replace_matching_zero_times_is_broken(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "broken_op", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 1
    assert "FAULT-P0-93" in r.stdout and "BROKEN" in r.stdout
    assert r.stats["faults"].endswith("1 broken"), r.stats


def test_ac_00_22_failing_clean_entry_is_false_positive(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "falsepos", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 1
    assert "CLEAN-P0-94" in r.stdout and "FALSEPOS" in r.stdout
    assert re.match(r"^1 total, 0 pass, 1 false-positive$", r.stats["clean"]), r.stats


def test_ac_00_22_missing_expect_rc_is_a_schema_error(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "bad_schema", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 2 and r.verdict == "ERROR", r
    assert r.has_finding(rule="selftest.bad-fault", severity="error"), r.findings_jsonl()


def test_ac_00_22_exceeding_max_seconds_is_slow(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "slow", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 1
    assert "FAULT-P0-96" in r.stdout and "SLOW" in r.stdout
    assert re.search(r", 1 slow,", r.stats["faults"]), r.stats


def test_ac_00_22_all_caught_tree_is_rc_0(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "all_caught", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", r
    assert re.match(r"^1 total, 1 caught, 0 missed", r.stats["faults"]), r.stats
    assert re.match(r"^1 total, 1 pass, 0 false-positive$", r.stats["clean"]), r.stats


def test_ac_00_22_id_glob_filters_entries(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "mixed", "--id", "FAULT-P0-82", env=env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0
    assert re.match(r"^1 total, 1 caught", r.stats["faults"]), r.stats


def results_by_id(r):
    return {e["id"]: e["result"] for e in entries_of(matrix(r))}


def test_ac_00_23_jobs_do_not_change_results(tmp_path):
    a = run_h("selftest", "--faults-dir", TREES / "mixed", "--jobs", "1", env=env(tmp_path / "a"), timeout=180)
    b = run_h("selftest", "--faults-dir", TREES / "mixed", "--jobs", "4", env=env(tmp_path / "b"), timeout=180)
    assert_contract(a)
    assert_contract(b)
    assert a.rc == b.rc == 5
    assert results_by_id(a) == results_by_id(b)
    assert results_by_id(a) == {"FAULT-P0-81": "CAUGHT", "FAULT-P0-82": "CAUGHT", "FAULT-P0-83": "MISSED",
                                "CLEAN-P0-85": "PASS"}


def test_ac_00_23_fixture_trees_untouched_and_temp_dirs_removed(tmp_path):
    before = tree_hash(FIXTURES / "projects" / "clean_min")
    env_ = env(tmp_path)
    r = run_h("selftest", "--faults-dir", TREES / "mixed", env=env_, timeout=180)
    assert_contract(r)
    assert tree_hash(FIXTURES / "projects" / "clean_min") == before
    ht = tmp_path / "ht"
    assert not list(ht.rglob("proj")) if ht.exists() else True, "temp copies must be deleted without --keep"


def test_ac_00_23_keep_preserves_temp_copies(tmp_path):
    r = run_h("selftest", "--faults-dir", TREES / "mixed", "--keep", env=env(tmp_path), timeout=180)
    assert_contract(r)
    kept = list((tmp_path / "ht").rglob("proj"))
    assert kept, "--keep must leave the temp project copies"
    assert any((k / "extra.txt").exists() for k in kept), "the applied ops are visible in the kept copy"
