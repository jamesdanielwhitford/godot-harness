"""A1 contract: `h check` (AC-01.1-16, 01.31). Layer: contract. Every result also passes assert_contract.
Copies are made per test (B3); imported copies come from the session-cached `warm` fixtures."""
import collections
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from helpers.h import (FIXTURES, REPO, apply_fault, assert_contract, live_processes_mentioning, run_h,
                       scene_for_script, write)

GD = FIXTURES / "gd_cases"
CASES = FIXTURES / "r1_4_cases"
RUNNER = REPO / "addons" / "harness" / "runners" / "load_check.gd"
ORIG_UID = "uid://dvpey5akgbony"

# case -> expected parse-error line (spec 01 section 6; verified against Godot 4.7 [Run])
P_CLASS = {
    "c01_kinematic": 1, "c02_onready": 2, "c03_export": 2, "c04_yield": 3, "c05_connect3": 3, "c07_tool": 1,
    "c08_setget": 2, "c09_rect": 3, "c10_randrange": 3, "c11_variant_infer": 4, "c12_poolarr": 2, "c13_os_ticks": 3,
    "c14_file": 3, "c15_move_and_slide": 3, "c17_stepify": 3, "c19_get_node_in_var": 2, "c23_shadow_dot_super": 3,
    "c24_typedarray": 2, "c25_deg2rad": 3, "c27_hallucinated": 3, "c28_tabspace": 4, "c30_preload_dyn": 4,
    "c31_assign_ret_void": 5, "d01_untyped_connect": 4,
}


def env_out(tmp_path):
    return {"HARNESS_OUT": str(tmp_path / "out")}


def put_gd(p, name):
    shutil.copy(GD / f"{name}.gd", p / "scripts" / f"{name}.gd")


def put_case(p, name, uid=None):
    text = (CASES / f"{name}.tscn").read_text()
    if uid:
        text = text.replace(ORIG_UID, uid)
    write(p, f"cases/{name}.tscn", text)


def real_hero_uid(p):
    f = p / "scripts" / "hero.gd.uid"
    assert f.exists(), "import must have written scripts/hero.gd.uid"
    return f.read_text().strip()


def check(p, tmp_path, *args, cwd=None, timeout=120):
    return run_h("check", "--project", p, *args, cwd=cwd, env=env_out(tmp_path), timeout=timeout)


# ---- AC-01.1 --------------------------------------------------------------------------------------------
@pytest.mark.godot
def test_ac_01_1_clean_min_fresh_then_warm(mkproj, tmp_path):
    p = mkproj()
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "check", r
    assert re.match(r"^ran \(no \.godot/\)", r.stats["import"]), r.stats
    assert r.stats["files"] == "1 .gd, 1 .tscn"
    assert r.wall <= 25, f"{r.wall:.1f}s"
    r2 = check(p, tmp_path)
    assert_contract(r2)
    assert r2.rc == 0 and r2.stats["import"] == "fresh"
    assert r2.wall <= 5, f"{r2.wall:.1f}s"


# ---- AC-01.2 / 01.3 ---------------------------------------------------------------------------------------
@pytest.mark.godot
@pytest.mark.parametrize("name,line", sorted(P_CLASS.items()))
def test_ac_01_2_python_class_snippet_is_a_parse_error(name, line, mkwarm, tmp_path):
    p = mkwarm()
    put_gd(p, name)
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 1, r
    assert re.search(rf"^res://scripts/{name}\.gd:{line}: \[godot\.parse-error\] error:", r.stdout, re.M), r.stdout


@pytest.mark.godot
def test_ac_01_3_all_24_at_once(mkwarm, tmp_path):
    assert len(P_CLASS) == 24
    p = mkwarm()
    for n in P_CLASS:
        put_gd(p, n)
    put_gd(p, "c20_ok_baseline")
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 1
    rows = r.findings_jsonl()
    err_paths = {x["path"] for x in rows if x["severity"] == "error" and x["rule"] == "godot.parse-error"}
    assert err_paths == {f"res://scripts/{n}.gd" for n in P_CLASS}
    assert not any(x["path"] == "res://scripts/c20_ok_baseline.gd" for x in rows)
    assert r.wall <= 10, f"{r.wall:.1f}s"
    assert len(r.lines) <= 40 and r.trunc is not None, "24+ errors cannot fit: a truncation line is required"


# ---- AC-01.4 / 01.5 -----------------------------------------------------------------------------------------
# (case, rc, rule or None, line required, message regex or None)
SCENE_CASES = [
    ("c03_missing_ext_path", 1, None, False, r"missing\.png"),
    ("c04_wrong_uid_right_path", 5, None, False, r"(?i)invalid uid"),
    ("c08_sub_forward_ref", 1, "check.load-failed", True, None),
    ("c09_undeclared_ext_ref", 1, "check.load-failed", True, None),
    ("c10_bad_parent", 1, "godot.parent-vanished", False, None),
    ("c11_parent_includes_root", 1, "godot.parent-vanished", False, None),
    ("c12_child_before_parent", 1, "godot.parent-vanished", False, None),
    ("c13_two_roots", 1, "check.instantiate-failed", False, None),
    ("c14_unknown_type", 1, None, False, None),
    ("c16_syntax_error", 1, "check.load-failed", True, None),
    ("c17_conn_bad_target", 1, None, False, None),
    ("c18_missing_script_path", 1, None, False, r"ghost\.gd"),
    ("c19_future_format", 1, "check.load-failed", True, None),
    ("c23_instance_missing", 1, None, False, r"gone\.tscn"),
]


@pytest.mark.godot
@pytest.mark.parametrize("name,rc,rule,need_line,msg", SCENE_CASES, ids=[c[0] for c in SCENE_CASES])
def test_ac_01_4_detectable_scene_cases(name, rc, rule, need_line, msg, mkwarm, tmp_path):
    p = mkwarm("scene_cases")
    put_case(p, name)
    r = check(p, tmp_path, "--no-lint")
    assert_contract(r)
    assert r.rc == rc, r
    sev = "warning" if rc == 5 else "error"
    here = [f for f in r.findings_jsonl() if f["path"] == f"res://cases/{name}.tscn" and f["severity"] == sev]
    assert here, f"no {sev} finding located at res://cases/{name}.tscn\n{r.stdout}"
    if rule:
        here = [f for f in here if f["rule"] == rule]
        assert here, f"no [{rule}] at the scene\n{r.stdout}"
    if need_line:
        assert any(f["line"] is not None for f in here), here
    if msg:
        assert any(re.search(msg, f["message"] + " " + (f["hint"] or "")) for f in r.findings_jsonl()), r.stdout
    if name == "c18_missing_script_path":
        assert any(f["rule"] in ("godot.load-failed", "godot.error") for f in r.findings_jsonl())


SILENT = ["c00_valid", "c01_unknown_node_prop", "c02_unknown_subres_prop", "c05_right_uid_wrong_path",
          "c06_dup_ext_id", "c07_dup_sub_id", "c15_wrong_value_type", "c20_no_header_format",
          "c21_stale_load_steps", "c22_godot3_format", "c24_typed_arrays", "c25_bad_nodepath_export",
          "c26_export_node_no_node_paths", "c27_sub_unused_and_ext_unused"]


@pytest.mark.godot
@pytest.mark.parametrize("name", SILENT)
def test_ac_01_5_silent_scene_cases_pass_the_load_check(name, mkwarm, tmp_path):
    p = mkwarm("scene_cases")
    put_case(p, name, uid=real_hero_uid(p))
    r = check(p, tmp_path, "--no-lint")
    assert_contract(r)
    assert r.rc == 0, r


# ---- AC-01.6 .. 01.11 ------------------------------------------------------------------------------------
@pytest.mark.godot
def test_ac_01_6_broken_script_on_a_scene_reports_script_not_scene(mkwarm, tmp_path):
    p = mkwarm()
    apply_fault("FAULT-P0-03", p)
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 1
    assert re.search(r"^res://scripts/broken\.gd:4: \[godot\.parse-error\]", r.stdout, re.M), r.stdout
    assert not r.has_finding(rule="check.load-failed", path="res://scenes/uses_broken.tscn")


@pytest.mark.godot
def test_ac_01_7_smoke_runs_ready_code(mkwarm, tmp_path):
    p = mkwarm("scene_cases")
    apply_fault("FAULT-A1-13", p)
    r = check(p, tmp_path, "--smoke")
    assert_contract(r)
    assert r.rc == 1
    assert re.search(r"^res://scripts/null_ready\.gd:4: \[godot\.script-error\]", r.stdout, re.M), r.stdout
    assert re.search(r"smoke on", r.stats["phases"]), r.stats
    off = check(p, tmp_path, "--no-lint")
    assert_contract(off)
    assert off.rc == 0, off
    assert re.search(r"smoke off", off.stats["phases"]), off.stats


@pytest.mark.godot
@pytest.mark.parametrize("name,line", [("c18_emit_str", 4), ("c32_get_tree_input", 3)])
def test_ac_01_8_smoke_backtrace_locations(name, line, mkwarm, tmp_path):
    p = mkwarm("scene_cases")
    put_gd(p, name)
    scene_for_script(p, f"scenes/{name}.tscn", f"res://scripts/{name}.gd")
    r = check(p, tmp_path, "--smoke", "--no-lint")
    assert_contract(r)
    assert r.rc == 1
    assert r.has_finding(path=f"res://scripts/{name}.gd", line=line, severity="error"), r.stdout


@pytest.mark.godot
def test_ac_01_9_hang_is_attributed_and_the_rest_is_resumed(mkwarm, tmp_path):
    p = mkwarm()
    apply_fault("FAULT-A1-14", p)
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 1
    assert re.search(r"^res://scripts/a_hang\.gd: \[harness\.hang\]", r.stdout, re.M), r.stdout
    assert re.search(r"^res://scripts/z_broken\.gd:3: \[godot\.parse-error\]", r.stdout, re.M), r.stdout
    assert r.wall <= 20, f"{r.wall:.1f}s"
    assert live_processes_mentioning(str(p)) == []


@pytest.mark.godot
def test_ac_01_10_autoload_runtime_error_is_a_finding(mkwarm, tmp_path):
    p = mkwarm("scene_cases")
    apply_fault("FAULT-A1-16", p)
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 1
    assert r.has_finding(path="res://scripts/bad_auto.gd", line=3, severity="error"), r.stdout


@pytest.mark.godot
def test_ac_01_10_autoload_quit_zero_gives_rc_warning_and_still_fails(mkwarm, tmp_path):
    p = mkwarm()
    apply_fault("FAULT-A1-17", p)
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 1
    assert r.has_finding(rule="harness.rc", severity="warning"), r.stdout
    assert r.has_finding(path="res://scripts/bad_parse.gd", line=3, severity="error")


@pytest.mark.godot
def test_ac_01_11_no_duplicate_findings(mkwarm, tmp_path):
    p = mkwarm("scene_cases")
    put_case(p, "c08_sub_forward_ref")
    r = check(p, tmp_path, "--no-lint")
    assert_contract(r)
    errs = [(f["path"], f["line"], f["message"]) for f in r.findings_jsonl() if f["severity"] == "error"]
    assert errs, r.stdout
    dup = [k for k, n in collections.Counter(errs).items() if n > 1]
    assert not dup, f"duplicate error findings: {dup}"


# ---- AC-01.12 ---------------------------------------------------------------------------------------------
@pytest.mark.godot
def test_ac_01_12_stale_class_cache_reimports(mkproj, tmp_path):
    p = mkproj()
    apply_fault("CLEAN-A1-02", p)
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 0, r
    assert r.stats["import"].startswith("ran (stale class cache"), r.stats


# ---- AC-01.13 / 01.14 -------------------------------------------------------------------------------------
@pytest.mark.godot
def test_ac_01_13_path_argument_pulls_in_dependents(mkwarm, tmp_path):
    p = mkwarm()
    r = check(p, tmp_path, "scripts/hello.gd", cwd=p)
    assert_contract(r)
    assert r.rc == 0 and r.stats["files"] == "1 .gd, 1 .tscn", r.stats
    r = check(p, tmp_path, "res://scripts/hello.gd")
    assert_contract(r)
    assert r.stats["files"] == "1 .gd, 1 .tscn", r.stats
    r = check(p, tmp_path, "scripts/hello.gd", "--no-deps", cwd=p)
    assert_contract(r)
    assert r.stats["files"] == "1 .gd", r.stats


@pytest.mark.godot
def test_ac_01_13_path_errors_are_usage_errors(mkwarm, tmp_path):
    p = mkwarm()
    (tmp_path / "x.gd").write_text("extends Node\n")
    r = check(p, tmp_path, "../x.gd", cwd=p)
    assert r.rc == 2 and re.match(r"^ERROR check usage: path outside project: ", r.lines[0]), r.lines[0]
    assert_contract(r)
    r = check(p, tmp_path, "scripts/nope.gd", cwd=p)
    assert r.rc == 2 and re.match(r"^ERROR check usage: no such file: ", r.lines[0]), r.lines[0]
    assert_contract(r)


def _git(p, *args):
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", *args], cwd=p, env=e, capture_output=True, text=True, check=True)


@pytest.mark.godot
def test_ac_01_13_changed_lists_edits_untracked_and_dependents(mkwarm, tmp_path):
    p = mkwarm()
    (p / ".gitignore").write_text(".godot/\n.harness/\n")
    _git(p, "init", "-q", "-b", "main")
    _git(p, "add", "-A")
    _git(p, "commit", "-qm", "init")
    clean = check(p, tmp_path, "--changed")
    assert_contract(clean)
    assert clean.rc == 0, "no changes -> empty set -> PASS"
    with open(p / "scripts" / "hello.gd", "a") as f:
        f.write("\n# edited\n")
    r = check(p, tmp_path, "--changed")
    assert_contract(r)
    assert r.rc == 0 and r.stats["files"] == "1 .gd, 1 .tscn", r.stats
    write(p, "scripts/fresh.gd", "extends Node\n")
    r = check(p, tmp_path, "--changed")
    assert_contract(r)
    assert r.stats["files"] == "2 .gd, 1 .tscn", r.stats


@pytest.mark.godot
def test_ac_01_13_changed_outside_git_is_usage_error(mkwarm, tmp_path):
    p = mkwarm()
    r = check(p, tmp_path, "--changed")
    assert r.rc == 2 and "--changed needs a git work tree" in r.lines[0], r.lines[0]
    assert_contract(r)


@pytest.mark.godot
def test_ac_01_14_addons_excluded_unless_asked(mkwarm, tmp_path):
    p = mkwarm()
    write(p, "addons/x/bad.gd", "extends Node\nvar a = 1 +\n")
    r = check(p, tmp_path)
    assert_contract(r)
    assert r.rc == 0, r
    r2 = check(p, tmp_path, "--include-addons")
    assert_contract(r2)
    assert r2.rc == 1 and r2.has_finding(path="res://addons/x/bad.gd", severity="error"), r2.stdout


# ---- AC-01.15 / 01.16 ------------------------------------------------------------------------------------
@pytest.mark.godot
def test_ac_01_15_invocations_in_run_json(mkproj, tmp_path):
    p = mkproj()
    r = check(p, tmp_path)
    assert_contract(r)
    invs = r.invocations()
    kinds = [i["kind"] for i in invs]
    assert kinds[0] == "import" and kinds[1:] == ["runner", "runner"], kinds
    for inv in invs[1:]:
        argv = inv["argv"]
        assert Path(argv[argv.index("--path") + 1]).resolve() == p.resolve()
        s = Path(argv[argv.index("-s") + 1])
        assert s.is_absolute() and s.resolve() == RUNNER.resolve(), s
    listing = r.artifact("scripts.txt").read_text()
    assert "res://scripts/hello.gd" in listing.splitlines()
    smoke = check(p, tmp_path, "--smoke")
    assert_contract(smoke)
    assert [i["kind"] for i in smoke.invocations()] == ["runner", "smoke"], [i["kind"] for i in smoke.invocations()]


@pytest.mark.godot
def test_ac_01_16_phases_line_and_no_lint(mkwarm, tmp_path):
    p = mkwarm()
    r = check(p, tmp_path)
    assert_contract(r)
    assert re.search(r"lint (\d+\.\d+s|skipped \(.+\))", r.stats["phases"]), r.stats["phases"]
    assert re.search(r"scripts \d+\.\d+s", r.stats["phases"]) and re.search(r"scenes \d+\.\d+s", r.stats["phases"])
    r2 = check(p, tmp_path, "--no-lint")
    assert_contract(r2)
    assert "lint skipped (--no-lint)" in r2.stats["phases"], r2.stats["phases"]


# ---- AC-01.31 -----------------------------------------------------------------------------------------------
@pytest.mark.godot
def test_ac_01_31_runner_incomplete_is_attributed_and_the_rest_resumed(mkwarm, tmp_path):
    p = mkwarm()
    apply_fault("FAULT-P0-06", p)
    shutil.copy(REPO / "selftest/faults/FAULT-A1-13/files/null_ready.gd", p / "scripts" / "null_ready.gd")
    scene_for_script(p, "scenes/zz_null.tscn", "res://scripts/null_ready.gd")
    r = check(p, tmp_path, "--smoke", "--no-lint")
    assert_contract(r)
    assert r.rc == 1
    assert re.search(r"^res://scenes/quit_early\.tscn: \[harness\.runner-incomplete\]", r.stdout, re.M), r.stdout
    assert re.search(r"null_ready\.gd:4: \[godot\.script-error\]", r.stdout), r.stdout
    assert r.wall <= 40, f"{r.wall:.1f}s"


# ---- negative control ----------------------------------------------------------------------------------------
@pytest.mark.godot
def test_scene_cases_fixture_itself_passes_check(mkproj, tmp_path):
    """No false positives: the scene_cases host project (hero script + valid c00) must PASS (FIXTURE.md)."""
    p = mkproj("scene_cases")
    r = check(p, tmp_path, "--no-lint")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", r
