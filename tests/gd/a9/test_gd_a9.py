"""A9 [gd] wrapper (REVIEW R-39, A9 D-2): runs tests/gd/a9/*.gd inside a copy of `@sample` at res://tests/a9/ via
`run_gd_suites("a9", "@sample")`, then maps the results to ACs by test-name prefix (`test_ac_09_<n>_`).
Red until B9a/B9b land (no sample/ -> HelperError)."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from helpers.gd import cleanup, run_gd_suites
from helpers.h import REPO, assert_contract

pytestmark = [pytest.mark.godot, pytest.mark.slow]

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("a9_snapshot_check", REPO / "tests" / "fixtures" / "a9" / "snapshot_check.py")
snapshot_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snapshot_check)

SUITES = ["test_a9_sim_core", "test_a9_view", "test_a9_motor", "test_a9_scene_manager", "test_a9_player_scene"]
AC_TO_SUITE = {8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 1, 15: 1, 16: 2, 17: 3, 18: 4}


@pytest.fixture(scope="module")
def gd():
    r = run_gd_suites("a9", "@sample")
    snap = r.extra["copy"] / "a9_snapshot_out.json"
    r.extra["snapshot_text"] = snap.read_text() if snap.exists() else None
    try:
        r.extra["tests_json"] = json.loads(r.artifact("tests.json").read_text())
    except (AssertionError, OSError, ValueError):
        r.extra["tests_json"] = None
    yield r
    cleanup(r)


def n_test_funcs() -> int:
    return sum(len(re.findall(r"^func (test_\w+)", p.read_text(), re.M)) for p in HERE.glob("test_a9_*.gd"))


def ac_rows(gd, prefix: str) -> list:
    tj = gd.extra["tests_json"]
    assert tj is not None, f"no artifacts/tests.json\n{gd}"
    return [t for t in tj["tests"] if t["name"].startswith(prefix)]


def test_gd_a9_all_suites_pass(gd):
    assert_contract(gd)
    assert gd.rc == 0 and gd.verdict == "PASS", str(gd)
    m = re.match(r"(\d+) total, (\d+) passed, (\d+) failed, (\d+) errors, (\d+) skipped, (\d+) orphans", gd.stats["tests"])
    assert m, gd.stats.get("tests")
    total, passed, failed, errors, skipped, orphans = map(int, m.groups())
    assert total >= n_test_funcs()
    assert (failed, errors, skipped, orphans) == (0, 0, 0, 0), gd.stats["tests"]
    assert not [f for f in gd.findings if f["severity"] == "error"]


def test_gd_a9_every_suite_ran(gd):
    tj = gd.extra["tests_json"]
    assert tj is not None, str(gd)
    ran = {t["suite"] for t in tj["tests"]}
    for s in SUITES:
        assert f"res://tests/a9/{s}.gd" in ran, f"{s} did not run; ran {sorted(ran)}"


@pytest.mark.parametrize("ac", sorted(AC_TO_SUITE))
def test_gd_a9_each_ac_has_passing_tests(gd, ac):
    ts = ac_rows(gd, f"test_ac_09_{ac}_")
    assert ts, f"no test named test_ac_09_{ac}_* ran"
    bad = [(t["name"], t["status"], t["message"]) for t in ts if t["status"] != "passed"]
    assert not bad, bad
    assert all(t["suite"].endswith(f"/{SUITES[AC_TO_SUITE[ac]]}.gd") for t in ts)


def test_ac_09_10_snapshot_matches_schema(gd):
    text = gd.extra["snapshot_text"]
    assert text is not None, "test_ac_09_10_export_snapshot_for_schema_check did not write res://a9_snapshot_out.json"
    snap = json.loads(text)
    assert snapshot_check.validate(snap) == []
    assert snap["schema"] == "sample.tactics" and snap["version"] == 1
    assert snap["tick"] == 300
    assert isinstance(snap["tick"], int) and isinstance(snap["next_id"], int)
    assert set(snap["data"]) >= {"width", "height", "team_to_move", "wave", "blocked", "stats"}
    assert "debug_note" not in snap["data"]  # HOOK-SIM-FIELD: view/debug fields never serialised
    assert text.endswith("}\n") and "\t" in text  # JSON.stringify(.., "\t", true, true) + "\n"
    keys = list(snap.keys())
    assert keys == sorted(keys), "keys must be sorted (sort_keys=true)"
    for v in snap["data"]["stats"].values():
        assert isinstance(v, int) and not isinstance(v, bool)
