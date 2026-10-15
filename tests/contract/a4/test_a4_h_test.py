"""A4 contract tests for `h test` (spec 04_test_runner.md section 4, AC-04.1 .. AC-04.21).

Black-box: every run is on a temp copy of tests/fixtures/projects/gd_tests (B3), every result goes through
assert_contract. Fixture counts (FIXTURE.md): 3 suites, 55 cases = test_counter 4 + test_jumper 1 + test_many 50.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from helpers.h import (REPO, apply_fault, assert_contract, copy_fixture, live_processes_mentioning, run_h,
                       tree_hash, validate_schema, write)

pytestmark = pytest.mark.godot

N_ALL = 55
N_COUNTER = 4
COUNTER = "res://tests/sim/test_counter.gd"


def h_test(p, *args, env=None, cwd=None, timeout=300):
    r = run_h("test", *([] if cwd else ["--project", p]), *args, env=env, cwd=cwd, timeout=timeout)
    return assert_contract(r)


def finding_lines(r):
    return [ln for ln, k in zip(r.lines[1:], r.kinds) if k == "finding"]


def stat_lines(r):
    return [ln for ln, k in zip(r.lines[1:], r.kinds) if k == "stat"]


# ---------------------------------------------------------------- AC-04.1
def test_ac_04_1_1_fresh_copy_installs_imports_and_passes(gd_fresh):
    assert not (gd_fresh / ".godot").exists() and not (gd_fresh / "addons" / "gdUnit4").exists()
    r = h_test(gd_fresh)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "test"
    assert r.stats["import"].startswith("ran")
    assert r.stats["gdunit4"] == "v6.2.2 installed (was missing)"
    assert r.stats["tests"] == f"{N_ALL} total, {N_ALL} passed, 0 failed, 0 errors, 0 skipped, 0 orphans"
    assert "selected" not in r.stats
    assert r.stats["project"] == str(gd_fresh)
    assert not r.findings
    assert len(r.lines) <= 15


def test_ac_04_1_2_second_run_is_fresh_and_present(gd_fresh):
    assert h_test(gd_fresh).rc == 0
    r = h_test(gd_fresh)
    assert r.rc == 0
    assert r.stats["import"] == "fresh"
    assert r.stats["gdunit4"] == "v6.2.2 present"
    assert r.stats["tests"].startswith(f"{N_ALL} total, {N_ALL} passed")


# ---------------------------------------------------------------- AC-04.2
def test_ac_04_2_1_failing_assert_one_line_with_location(gdp):
    apply_fault("FAULT-A4-01", gdp)
    r = h_test(gdp, "test_math")
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.search(r"^res://tests/test_math\.gd:6: \[test\.failed\] error: test_math::test_bad: "
                     r"Expecting: 3 but was 2$", r.stdout, re.M)
    assert re.search(r"^res://tests/test_math\.gd:8: \[test\.failed\] error: test_math::test_bad_str: "
                     r"Expecting: 'hello world' but was 'hello <LF>world'$", r.stdout, re.M)
    bad = [ln for ln in finding_lines(r) if "test_math::test_bad:" in ln]
    assert len(bad) == 1, "the whole failure is on one line"
    assert r.reason.startswith("2 failed") and "1 passed of 3 tests" in r.reason
    assert r.stats["tests"] == "3 total, 1 passed, 2 failed, 0 errors, 0 skipped, 0 orphans"
    assert re.match(r"^v6\.2\.2 present, rc 100$", r.stats["gdunit4"])


def test_ac_04_2_2_failing_suite_among_others_runs_all_of_them(gdp):
    """No fail-fast: tests after the failing suite still run (always -c)."""
    apply_fault("FAULT-A4-01", gdp)
    r = h_test(gdp)
    assert r.rc == 1
    assert r.stats["tests"].startswith(f"{N_ALL + 3} total, {N_ALL + 1} passed, 2 failed")


# ---------------------------------------------------------------- AC-04.3
def test_ac_04_3_1_runtime_error_in_game_code(gdp):
    apply_fault("FAULT-A4-05", gdp)
    r = h_test(gdp, "test_buggy")
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.search(r"^res://scripts/buggy\.gd:6: \[test\.error\] error: ", r.stdout, re.M)
    at_game = [f for f in r.findings if f["path"] == "res://scripts/buggy.gd" and f["line"] == 6]
    assert len(at_game) == 1, f"dedup: exactly one finding at the game-code location, got {at_game}"
    assert not re.search(r"^res://tests/test_buggy\.gd:6:", r.stdout, re.M)
    assert "test_buggy::test_runs" in r.stdout


# ---------------------------------------------------------------- AC-04.4
def test_ac_04_4_1_parse_error_in_test_file(gdp):
    apply_fault("FAULT-A4-02", gdp)
    r = h_test(gdp)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.match(r"^v6\.2\.2 present, rc 105$", r.stats["gdunit4"])
    assert r.stats["tests"] == "not run"
    assert re.search(r"^res://tests/test_broken\.gd:3: \[godot\.parse-error\]", r.stdout, re.M)
    assert r.reason.startswith("tests not run")


# ---------------------------------------------------------------- AC-04.5
def test_ac_04_5_1_orphans_warn_rc5(gdp):
    apply_fault("FAULT-A4-03", gdp)
    r = h_test(gdp, "test_leak")
    assert r.rc == 5 and r.verdict == "WARN"
    assert re.search(r"^res://tests/test_leak\.gd:\d+: \[test\.orphans\] warning: test_leak::test_leaks_node: "
                     r"1 possible orphan", r.stdout, re.M)
    assert r.stats["tests"].endswith("1 orphans")
    assert "orphan warning" in r.reason


def test_ac_04_5_2_orphans_strict_is_fail(gdp):
    apply_fault("FAULT-A4-03", gdp)
    r = h_test(gdp, "test_leak", "--strict")
    assert r.rc == 1 and r.verdict == "FAIL"


def test_ac_04_5_3_orphans_policy_fail(gdp):
    apply_fault("FAULT-A4-03", gdp)
    write(gdp, "harness.toml", '[test]\norphans = "fail"\n')
    r = h_test(gdp, "test_leak")
    assert r.rc == 1
    assert r.has_finding(rule="test.orphans", severity="error")


def test_ac_04_5_4_orphans_policy_ignore(gdp):
    apply_fault("FAULT-A4-03", gdp)
    write(gdp, "harness.toml", '[test]\norphans = "ignore"\n')
    r = h_test(gdp, "test_leak")
    assert r.rc == 0 and r.verdict == "PASS"
    assert not r.has_finding(rule="test.orphans", severity="warning")
    assert not r.has_finding(rule="test.orphans", severity="error")


# ---------------------------------------------------------------- AC-04.6
def test_ac_04_6_1_hang_hits_timeout_and_names_test(gdp):
    apply_fault("FAULT-A4-04", gdp)
    r = h_test(gdp, "test_hang", timeout=60)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.search(r"^res://tests/test_hang\.gd:2: \[harness\.hang\] error: .*test_hang::test_forever", r.stdout, re.M)
    inv = r.invocations()
    assert len(inv) == 1
    assert inv[0]["timed_out"] is True and inv[0]["rc"] == 124
    assert inv[0]["timeout_s"] == 10
    assert r.wall <= 20, f"wall {r.wall:.1f}s"
    assert live_processes_mentioning(str(gdp)) == []


# ---------------------------------------------------------------- AC-04.7
def test_ac_04_7_1_push_error_is_warning(gdp):
    apply_fault("FAULT-A4-06", gdp)
    r = h_test(gdp, "test_noisy")
    assert r.rc == 5 and r.verdict == "WARN"
    assert re.search(r"^res://scripts/noisy\.gd:\d+: \[godot\.error\] warning: ", r.stdout, re.M)


def test_ac_04_7_2_push_error_policy_fail(gdp):
    apply_fault("FAULT-A4-06", gdp)
    write(gdp, "harness.toml", '[test]\npush_error = "fail"\n')
    r = h_test(gdp, "test_noisy")
    assert r.rc == 1
    assert re.search(r"^res://scripts/noisy\.gd:\d+: \[godot\.error\] error: ", r.stdout, re.M)


# ---------------------------------------------------------------- AC-04.8
@pytest.mark.parametrize("target,cwd_rel", [
    (COUNTER, False), ("tests/sim/test_counter.gd", True), ("test_counter", False)])
def test_ac_04_8_1_three_target_forms_same_suite(gdp, target, cwd_rel):
    r = h_test(gdp, target, cwd=gdp if cwd_rel else None)
    assert r.rc == 0
    assert r.stats["tests"].startswith(f"{N_COUNTER} total, {N_COUNTER} passed")
    assert r.stats["selected"].startswith("1 suites")


def test_ac_04_8_2_single_test(gdp):
    r = h_test(gdp, "test_counter::test_add")
    assert r.rc == 0 and r.stats["tests"].startswith("1 total, 1 passed")
    assert r.stats["selected"].startswith("1 suites, 1 tests")


def test_ac_04_8_3_parameterised_test_runs_all_rows(gdp):
    r = h_test(gdp, "test_counter::test_table")
    assert r.rc == 0 and r.stats["tests"].startswith("2 total, 2 passed")


def test_ac_04_8_4_filter_substring(gdp):
    r = h_test(gdp, "--filter", "add")
    assert r.rc == 0
    assert r.stats["tests"].startswith("2 total, 2 passed")  # test_add, test_add_twice
    assert r.stats["selected"].startswith("1 suites, 2 tests")


def test_ac_04_8_5_two_targets_are_summed_and_deduplicated(gdp):
    r = h_test(gdp, "test_counter::test_add", "test_jumper")
    assert r.rc == 0 and r.stats["tests"].startswith("2 total, 2 passed")
    r2 = h_test(gdp, "test_counter::test_add", COUNTER)
    assert r2.rc == 0 and r2.stats["tests"].startswith(f"{N_COUNTER} total")


def test_ac_04_8_6_scene_suite_runs_headless(gdp):
    r = h_test(gdp, "test_jumper")
    assert r.rc == 0 and r.stats["tests"].startswith("1 total, 1 passed")


# ---------------------------------------------------------------- AC-04.9
BAD_TARGETS = [
    (["res://tests/nope.gd"], r"no such test path"),
    (["test_countr"], r"unknown suite 'test_countr' \(did you mean 'test_counter'\?\)"),
    (["test_counter::test_ad"], r"no test 'test_ad'"),
    (["/tmp"], r"."),
    (["res://tests/sim::test_add"], r"."),
    (["--changed", "test_counter"], r"."),
    (["project.godot"], r"."),
]


@pytest.mark.parametrize("args,rx", BAD_TARGETS, ids=["nofile", "typo", "notest", "outside", "dir-colons",
                                                      "changed-and-target", "not-gd"])
def test_ac_04_9_1_bad_target_is_usage_error_without_godot(gdp, args, rx):
    r = h_test(gdp, *args)
    assert r.rc == 2 and r.verdict == "ERROR"
    assert r.lines[0].startswith("ERROR test ")
    assert re.search(rx, r.lines[0])
    assert r.invocations() == []


def test_ac_04_9_2_ambiguous_suite_stem(gdp):
    write(gdp, "tests/scenes/test_counter.gd", "extends GdUnitTestSuite\n\nfunc test_x() -> void:\n\tassert_bool(true).is_true()\n")
    r = h_test(gdp, "test_counter")
    assert r.rc == 2
    assert re.search(r"suite 'test_counter' is ambiguous: ", r.lines[0])
    assert r.invocations() == []


# ---------------------------------------------------------------- AC-04.10
def test_ac_04_10_1_filter_matches_nothing(gdp):
    r = h_test(gdp, "--filter", "zzz")
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.search(r"\[test\.no-tests\]", r.stdout)
    assert r.invocations() == []


def test_ac_04_10_2_suite_without_test_functions(gdp):
    apply_fault("FAULT-A4-09", gdp)
    r = h_test(gdp, "test_empty")
    assert r.rc == 1 and re.search(r"\[test\.no-tests\]", r.stdout)
    assert r.invocations() == []


def test_ac_04_10_3_only_empty_suite_in_test_dir(gdp):
    shutil.rmtree(gdp / "tests")
    apply_fault("FAULT-A4-09", gdp)
    r = h_test(gdp)
    assert r.rc == 1 and re.search(r"\[test\.no-tests\]", r.stdout)


def test_ac_04_10_4_no_tests_dir(gdp):
    shutil.rmtree(gdp / "tests")
    r = h_test(gdp)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.search(r"\[test\.no-tests\]", r.stdout)


# ---------------------------------------------------------------- AC-04.11
def test_ac_04_11_1_user_gdunit4_other_version_not_overwritten(gd_fresh):
    cfg_rel = "addons/gdUnit4/plugin.cfg"
    apply_fault("FAULT-A4-10", gd_fresh)
    before = (gd_fresh / cfg_rel).read_bytes()
    r = h_test(gd_fresh)
    assert r.rc == 4 and r.verdict == "ERROR"
    assert re.search(r"^ERROR test gdUnit4 6\.1\.0", r.lines[0])
    assert (gd_fresh / cfg_rel).read_bytes() == before
    assert not (gd_fresh / "addons" / "gdUnit4" / "plugin.gd").exists()


def test_ac_04_11_2_cache_missing(gd_fresh, tmp_path):
    empty = tmp_path / "empty_cache"
    empty.mkdir()
    r = h_test(gd_fresh, env={"HARNESS_CACHE": empty})
    assert r.rc == 4 and r.verdict == "ERROR"
    assert "gdUnit4 not found" in r.lines[0]


# ---------------------------------------------------------------- AC-04.12
@pytest.mark.slow
def test_ac_04_12_1_fifty_tests_within_five_seconds(gdp):
    r = h_test(gdp, "res://tests/perf/test_many.gd")
    assert r.rc == 0 and r.stats["tests"].startswith("50 total, 50 passed")
    assert r.stats["import"] == "fresh"
    assert r.wall <= 5, f"wall {r.wall:.1f}s"


def test_ac_04_12_2_one_suite_within_three_seconds(gdp):
    r = h_test(gdp, "test_counter")
    assert r.rc == 0 and r.wall <= 3, f"wall {r.wall:.1f}s"


# ---------------------------------------------------------------- AC-04.13
def test_ac_04_13_1_output_cap_with_target(gdp):
    apply_fault("FAULT-A4-08", gdp)
    r = h_test(gdp, "test_many_fail")
    assert r.rc == 1
    assert len(r.lines) <= 15
    assert len(stat_lines(r)) == 5
    assert len(finding_lines(r)) == 7
    assert "... 23 more findings (23 errors, 0 warnings) in findings.jsonl" in r.lines
    rows = [f for f in r.findings_jsonl() if f["rule"] == "test.failed"]
    assert len(rows) == 30


def test_ac_04_13_2_output_cap_without_target(gdp):
    apply_fault("FAULT-A4-08", gdp)
    r = h_test(gdp)
    assert r.rc == 1
    assert len(r.lines) <= 15
    assert len(stat_lines(r)) == 4
    assert len(finding_lines(r)) == 8
    assert "... 22 more findings (22 errors, 0 warnings) in findings.jsonl" in r.lines
    assert len([f for f in r.findings_jsonl() if f["rule"] == "test.failed"]) == 30


# ---------------------------------------------------------------- AC-04.14
TESTS_JSON_SCHEMA = {
    "type": "object", "required": ["schema", "gdunit_rc", "selected", "tests"],
    "properties": {
        "schema": {"const": "harness.tests/1"}, "gdunit_rc": {"type": ["integer", "null"]},
        "selected": {"type": "object", "required": ["suites", "targets", "filter", "changed"],
                     "properties": {"suites": {"type": "array", "items": {"type": "string"}},
                                    "targets": {"type": "array", "items": {"type": "string"}},
                                    "filter": {"type": ["string", "null"]}, "changed": {"type": "boolean"}}},
        "tests": {"type": "array", "items": {
            "type": "object", "required": ["suite", "name", "status", "duration_s", "path", "line", "message"],
            "properties": {"suite": {"type": "string"},
                           "name": {"type": "string"},
                           "status": {"enum": ["passed", "failed", "error", "skipped", "orphans", "hung"]},
                           "duration_s": {"type": "number"}, "path": {"type": ["string", "null"]},
                           "line": {"type": ["integer", "null"]}, "message": {"type": ["string", "null"]}}}}}}


def test_ac_04_14_1_artifacts_and_clean_project_tree(gdp):
    apply_fault("FAULT-A4-01", gdp)
    before = (gdp / "project.godot").read_bytes()
    r = h_test(gdp, "test_math")
    assert r.rc == 1
    assert r.artifact("gdunit/results.xml").is_file()
    assert r.artifact("gdunit/index.html").is_file()
    tj = json.loads(r.artifact("tests.json").read_text())
    assert validate_schema(tj, TESTS_JSON_SCHEMA) == []
    assert re.match(r"^res://.*\.gd$", tj["tests"][0]["suite"])
    st = {t["name"]: t["status"] for t in tj["tests"]}
    assert st == {"test_ok": "passed", "test_bad": "failed", "test_bad_str": "failed"}
    assert tj["gdunit_rc"] == 100
    assert tj["selected"]["suites"] == ["res://tests/test_math.gd"]
    assert tj["selected"]["targets"] == ["test_math"] and tj["selected"]["changed"] is False
    assert not (gdp / ".harness" / "gdunit").exists()
    assert not (gdp / "reports").exists()
    assert (gdp / "project.godot").read_bytes() == before


def test_ac_04_14_2_tests_json_lists_every_test(gdp):
    r = h_test(gdp)
    tj = json.loads(r.artifact("tests.json").read_text())
    assert len(tj["tests"]) == N_ALL
    assert {t["status"] for t in tj["tests"]} == {"passed"}
    assert tj["gdunit_rc"] == 0
    assert validate_schema(tj, TESTS_JSON_SCHEMA) == []


# ---------------------------------------------------------------- AC-04.15
def test_ac_04_15_1_run_json_invocation_and_extra(gdp):
    apply_fault("FAULT-A4-01", gdp)
    r = h_test(gdp, "test_math")
    run = r.run_json()
    inv = run["invocations"]
    assert len(inv) == 1
    i = inv[0]
    assert i["kind"] == "test" and i["timeout_s"] == 300
    for tok in ("--ignoreHeadlessMode", "-c", "-rd", "res://addons/gdUnit4/bin/GdUnitCmdTool.gd", "--headless"):
        assert tok in i["argv"], (tok, i["argv"])
    rd = i["argv"][i["argv"].index("-rd") + 1]
    assert rd.startswith("res://.harness/gdunit/")
    assert i["argv"][i["argv"].index("-s") + 1] == "res://addons/gdUnit4/bin/GdUnitCmdTool.gd"
    ex = run["extra"]
    for k in ("gdunit_rc", "total", "passed", "failed", "errors", "skipped", "orphans", "suites"):
        assert k in ex, k
    assert ex["gdunit_rc"] == 100
    assert r.stats["tests"] == (f"{ex['total']} total, {ex['passed']} passed, {ex['failed']} failed, "
                                f"{ex['errors']} errors, {ex['skipped']} skipped, {ex['orphans']} orphans")
    assert ex["suites"] == 1


# ---------------------------------------------------------------- AC-04.16
def _git(p, *a):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=p, check=True,
                   capture_output=True)


def _commit_all(p):
    (p / ".gitignore").write_text(".godot/\n.harness/\n")
    _git(p, "init", "-q")
    _git(p, "add", "-A")
    _git(p, "commit", "-q", "-m", "base")


def test_ac_04_16_1_changed_nothing_is_pass_without_godot(gdp):
    _commit_all(gdp)
    r = h_test(gdp, "--changed")
    assert r.rc == 0 and r.verdict == "PASS"
    assert r.stats["selected"].startswith("0 suites")
    assert r.invocations() == []
    assert r.wall <= 1.0, f"wall {r.wall:.2f}s"
    assert not r.has_finding(rule="test.no-tests")


def test_ac_04_16_2_changed_source_runs_its_suite(gdp):
    _commit_all(gdp)
    with open(gdp / "sim" / "counter.gd", "a") as f:
        f.write("\n# touched\n")
    r = h_test(gdp, "--changed")
    assert r.rc == 0
    tj = json.loads(r.artifact("tests.json").read_text())
    assert tj["selected"]["suites"] == [COUNTER] and tj["selected"]["changed"] is True
    assert r.stats["tests"].startswith(f"{N_COUNTER} total")


def test_ac_04_16_3_changed_untracked_suite(gdp):
    _commit_all(gdp)
    write(gdp, "tests/test_new.gd", "extends GdUnitTestSuite\n\nfunc test_new() -> void:\n\tassert_bool(true).is_true()\n")
    r = h_test(gdp, "--changed")
    assert r.rc == 0
    tj = json.loads(r.artifact("tests.json").read_text())
    assert tj["selected"]["suites"] == ["res://tests/test_new.gd"]
    assert r.stats["tests"].startswith("1 total, 1 passed")


def test_ac_04_16_4_changed_outside_git_work_tree(gdp):
    assert not (gdp / ".git").exists()
    r = h_test(gdp, "--changed")
    assert r.rc == 2 and r.verdict == "ERROR"
    assert r.lines[0].startswith("ERROR test ")


# ---------------------------------------------------------------- AC-04.17 / 04.21
def test_ac_04_17_1_dotnet_disabled(gdp):
    r = h_test(gdp, "--dotnet")
    assert r.rc == 2
    assert re.match(r"^ERROR test --dotnet is disabled in v0 \(D1", r.lines[0])
    assert r.invocations() == []


def test_ac_04_21_1_help():
    r = run_h("test", "--help")
    assert_contract(r, nodir=True, help_output=True)
    assert r.rc == 0 and len(r.lines) <= 40
    assert "--filter" in r.stdout and "--changed" in r.stdout


def test_ac_04_21_2_bogus_flag(gdp):
    r = h_test(gdp, "--bogus")
    assert r.rc == 2
    assert re.match(r"^ERROR test usage: ", r.lines[0])
    assert r.lines[-1].startswith("log: ")


# ---------------------------------------------------------------- AC-04.18
def test_ac_04_18_1_stale_class_cache_triggers_import(gdp):
    write(gdp, "sim/dice.gd", "class_name Dice\nextends RefCounted\n\n\nfunc roll() -> int:\n\treturn 4\n")
    write(gdp, "tests/sim/test_dice.gd",
          "extends GdUnitTestSuite\n\n\nfunc test_roll() -> void:\n\tassert_int(Dice.new().roll()).is_equal(4)\n")
    r = h_test(gdp, "test_dice")
    assert r.rc == 0, r
    assert r.stats["import"].startswith("ran (stale class cache (")
    assert r.stats["tests"].startswith("1 total, 1 passed")


# ---------------------------------------------------------------- extra negatives and hygiene
def test_ac_04_x_1_fixture_source_untouched_and_no_false_positive(gd_fresh):
    """A clean copy has no findings of any kind and the repo fixture is never modified (B3)."""
    src = REPO / "tests" / "fixtures" / "projects" / "gd_tests"
    before = tree_hash(src)
    r = h_test(gd_fresh)
    assert r.rc == 0 and r.findings == [] and r.all_findings() == []
    assert tree_hash(src) == before
    assert not (src / ".godot").exists() and not (src / "addons").exists()


def test_ac_04_x_2_runs_on_copy_dir_is_isolated_from_other_copy(gd_fresh, tmp_path):
    other = copy_fixture("gd_tests", tmp_path / "other")
    r = h_test(gd_fresh, "test_counter")
    assert r.rc == 0
    assert not (other / ".godot").exists() and not (other / "addons").exists()


# ---------------------------------------------------------------- AC-04.20
@pytest.mark.slow
def test_ac_04_20_1_selftest_area_a4():
    r = run_h("selftest", "--area", "A4", timeout=400)
    assert_contract(r)
    assert r.rc == 0, r
    assert re.search(r"^faults: 11 total, 11 caught, 0 missed", r.stdout, re.M)
    assert re.search(r"^clean: 2 total, 2 pass, 0 false-positive", r.stdout, re.M)
    assert r.wall <= 180, f"wall {r.wall:.0f}s"
