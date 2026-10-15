"""A1 contract: `h import` (AC-01.17). Layer: contract."""
import re
import shutil

import pytest

from helpers.h import FIXTURES, assert_contract, run_h, write


def env_out(tmp_path):
    return {"HARNESS_OUT": str(tmp_path / "out")}


@pytest.mark.godot
def test_ac_01_17_import_runs_and_says_why(mkproj, tmp_path):
    p = mkproj()
    r = run_h("import", "--project", p, env=env_out(tmp_path), timeout=180)
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "import", r
    assert r.stats["import"] == "ran (requested)"
    assert re.match(r"^\d+(\.\d+)?s$", r.stats["duration"]), r.stats
    assert (p / ".godot" / "global_script_class_cache.cfg").exists()
    assert [i["kind"] for i in r.invocations()] == ["import"]


@pytest.mark.godot
def test_ac_01_17_import_runs_even_when_fresh(mkwarm, tmp_path):
    p = mkwarm()
    r = run_h("import", "--project", p, env=env_out(tmp_path), timeout=180)
    assert_contract(r)
    assert r.rc == 0 and r.stats["import"] == "ran (requested)"


@pytest.mark.godot
def test_ac_01_17_force_removes_godot_first(mkwarm, tmp_path):
    p = mkwarm()
    marker = p / ".godot" / "marker_from_test.txt"
    marker.write_text("x")
    r = run_h("import", "--force", "--project", p, env=env_out(tmp_path), timeout=180)
    assert_contract(r)
    assert r.rc == 0 and r.stats["import"] == "ran (forced)", r.stats
    assert not marker.exists(), ".godot/ must be deleted before the forced import"
    assert (p / ".godot" / "global_script_class_cache.cfg").exists()


@pytest.mark.godot
def test_ac_01_17_import_findings_count(mkproj, tmp_path):
    p = mkproj("scene_cases")
    shutil.copy(FIXTURES / "r1_4_cases" / "c19_future_format.tscn", p / "cases" / "c19_future_format.tscn")
    r = run_h("import", "--project", p, env=env_out(tmp_path), timeout=180)
    assert_contract(r)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert re.search(r"^res://cases/c19_future_format\.tscn:1: ", r.stdout, re.M), r.stdout
