"""P0 contract: failure modes that must be findings, not exit codes (AC-00.13-15, AC-00.27). Layer: contract.
Setups are replayed from selftest/faults/FAULT-P0-* with helpers.h.apply_fault so tests and faults cannot drift."""
import re

import pytest

from helpers.h import apply_fault, assert_contract, live_processes_mentioning, run_h, write


def env_out(tmp_path):
    return {"HARNESS_OUT": str(tmp_path / "out")}


@pytest.mark.godot
def test_ac_00_13_hang_is_a_finding_and_leaves_no_process(mkproj, tmp_path):
    p = mkproj()
    apply_fault("FAULT-P0-02", p)
    r = run_h("check", "--project", p, env=env_out(tmp_path), timeout=150)
    assert_contract(r)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.matches(r"\[harness\.hang\]"), r.stdout
    hung = [i for i in r.invocations() if i["timed_out"]]
    assert hung, "no invocation has timed_out: true"
    assert hung[0]["rc"] == 124 and hung[0]["duration_s"] <= 10, hung[0]
    assert live_processes_mentioning(str(p)) == []


@pytest.mark.godot
def test_ac_00_14_parse_error_behind_a_scene_is_found(mkproj, tmp_path):
    p = mkproj()
    apply_fault("FAULT-P0-03", p)
    r = run_h("check", "--project", p, env=env_out(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 1
    assert re.search(r"^res://scripts/broken\.gd:4: \[", r.stdout, re.M), r.stdout
    assert r.has_finding(path="res://scripts/broken.gd", line=4, severity="error")


@pytest.mark.godot
def test_ac_00_15_crash_is_a_finding_with_rc_134(mkproj, tmp_path):
    p = mkproj()
    apply_fault("FAULT-P0-07", p)
    r = run_h("check", "--project", p, env=env_out(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 1 and r.matches(r"\[harness\.crash\]"), r.stdout
    assert any(i["rc"] == 134 for i in r.invocations()), [i["rc"] for i in r.invocations()]


@pytest.mark.godot
def test_ac_00_27a_edit_keeping_class_name_stays_fresh(mkwarm, tmp_path):
    p = mkwarm()
    with open(p / "scripts" / "hello.gd", "a") as f:
        f.write("\n\nfunc extra() -> int:\n\treturn 1\n")
    r = run_h("check", "--project", p, env=env_out(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0 and r.stats["import"] == "fresh", r


@pytest.mark.godot
def test_ac_00_27b_new_class_name_triggers_import(mkwarm, tmp_path):
    p = mkwarm()
    write(p, "scripts/extra.gd", "class_name Extra\nextends Node\n")
    r = run_h("check", "--project", p, env=env_out(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0
    assert re.match(r"^ran \(stale class cache \(.*extra\.gd\)\)$", r.stats["import"]), r.stats.get("import")


@pytest.mark.godot
def test_ac_00_27c_missing_class_cache_triggers_import(mkwarm, tmp_path):
    p = mkwarm()
    (p / ".godot" / "global_script_class_cache.cfg").unlink()
    r = run_h("check", "--project", p, env=env_out(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0 and r.stats["import"].startswith("ran "), r
