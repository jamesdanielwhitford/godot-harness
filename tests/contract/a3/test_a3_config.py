"""A3 contract: suppression, severity overrides, exclude. AC-03.11 .. 03.13."""
from __future__ import annotations

from a3_common import CASES, finding_set, fresh, lint, write
from helpers.h import assert_contract

YIELD = CASES["c04_yield"][0]
SUPPRESS = (
    "extends Node\n"
    "func _ready():\n"
    '\tyield(get_tree().create_timer(1.0), "timeout")  # lint-ignore: syn-yield\n'
    "\tvar f = File.new()  # lint-ignore: syn-yield\n"
    "\t# lint-ignore-next-line: syn-file-dir-class\n"
    "\tvar g = File.new()\n"
    "\tvar h = File.new()  # lint-ignore: no-such-rule-xyz\n"
)


def _rules_at(r, path, line):
    return {f["rule"] for f in r.findings_jsonl() if f["path"] == path and f["line"] == line and f["severity"] != "info"}


# ---- AC-03.11 suppression ------------------------------------------------------------------------------------
def test_ac_03_11_same_line_and_next_line_suppression(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/s.gd", SUPPRESS)
    r = assert_contract(lint(p))
    s = "res://scripts/s.gd"
    assert "syn-yield" not in _rules_at(r, s, 3)                       # same-line form works
    assert "syn-file-dir-class" in _rules_at(r, s, 4)                  # names only syn-yield: other id still fires
    assert "syn-file-dir-class" not in _rules_at(r, s, 6)              # next-line form works
    assert "syn-file-dir-class" in _rules_at(r, s, 7)                  # unknown id suppresses nothing
    assert r.stats.get("suppressed") == "2", r.stats
    sup = [f for f in r.findings_jsonl() if f["severity"] == "info" and f["message"].startswith("suppressed:")]
    assert {(f["line"], f["rule"]) for f in sup} == {(3, "syn-yield"), (6, "syn-file-dir-class")}, sup


def test_ac_03_11_unknown_id_gives_bad_suppress_warning(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/s.gd", SUPPRESS)
    r = assert_contract(lint(p))
    assert r.has_finding("lint.bad-suppress", "res://scripts/s.gd", 7, "warning")


def test_ac_03_11_only_bad_suppress_is_warn(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/s.gd", "extends Node\nvar a: int = 1  # lint-ignore: not-a-rule\n")
    r = assert_contract(lint(p))
    assert r.rc == 5 and r.verdict == "WARN" and finding_set(r) == {("res://scripts/s.gd", 2, "lint.bad-suppress", "warning")}


def test_ac_03_11_comma_list_suppresses_all_named_ids(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/s.gd", "extends Node\nfunc _ready():\n\tyield(File.new(), \"x\")  # lint-ignore: syn-file-dir-class, syn-yield\n")
    r = assert_contract(lint(p))
    assert r.rc == 0 and r.stats.get("suppressed") == "2", str(r)


# ---- AC-03.12 severity overrides -----------------------------------------------------------------------------
def _yield_project(tmp_path, toml: str):
    p = fresh(tmp_path)
    write(p, "scripts/y.gd", YIELD)
    write(p, "harness.toml", toml)
    return p


def test_ac_03_12_severity_warning_gives_rc5(tmp_path):
    r = assert_contract(lint(_yield_project(tmp_path, '[lint]\nseverity = {"syn-yield" = "warning"}\n')))
    assert r.rc == 5 and r.verdict == "WARN" and r.has_finding("syn-yield", severity="warning"), str(r)


def test_ac_03_12_severity_off_gives_rc0(tmp_path):
    r = assert_contract(lint(_yield_project(tmp_path, '[lint]\nseverity = {"syn-yield" = "off"}\n')))
    assert r.rc == 0 and r.run_json()["findings_total"] == 0, str(r)


def test_ac_03_12_family_glob_off_removes_fn_rand_range(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/r.gd", CASES["c10_randrange"][0])
    r0 = assert_contract(lint(p))
    assert r0.rc == 1 and r0.has_finding("fn-rand_range")
    write(p, "harness.toml", '[lint]\nseverity = {"fn-*" = "off"}\n')
    r = assert_contract(lint(p))
    assert r.rc == 0 and not r.has_finding("fn-rand_range"), str(r)


def test_ac_03_12_precedence_exact_id_beats_family_glob(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/r.gd", CASES["c10_randrange"][0])
    write(p, "harness.toml", '[lint]\nseverity = {"fn-*" = "off", "fn-rand_range" = "warning"}\n')
    r = assert_contract(lint(p))
    assert r.rc == 5 and r.has_finding("fn-rand_range", severity="warning"), str(r)


def test_ac_03_12_lint_star_glob_and_exact_override(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/i.gd", 'extends Node\nfunc _ready() -> void:\n\tInput.is_action_pressed("nope")\n')
    write(p, "harness.toml", '[lint]\nseverity = {"lint.*" = "warning"}\n')
    r = assert_contract(lint(p))
    assert r.rc == 5 and r.has_finding("lint.input-action", severity="warning"), str(r)
    write(p, "harness.toml", '[lint]\nseverity = {"lint.*" = "off", "lint.input-action" = "error"}\n')
    r2 = assert_contract(lint(p))
    assert r2.rc == 1 and r2.has_finding("lint.input-action", severity="error"), str(r2)


def test_ac_03_12_unknown_rule_key_is_config_error(tmp_path):
    r = assert_contract(lint(_yield_project(tmp_path, '[lint]\nseverity = {"syn-yeld" = "off"}\n')))
    assert r.rc == 2 and r.verdict == "ERROR", str(r)
    assert "[harness.config]" in r.stdout and "syn-yeld" in r.stdout


def test_ac_03_12_bad_value_is_config_error(tmp_path):
    r = assert_contract(lint(_yield_project(tmp_path, '[lint]\nseverity = {"syn-yield" = "fatal"}\n')))
    assert r.rc == 2 and r.verdict == "ERROR" and "[harness.config]" in r.stdout, str(r)


def test_ac_03_12_unknown_lint_key_is_config_error(tmp_path):
    r = assert_contract(lint(_yield_project(tmp_path, "[lint]\nreplay_dir = []\n")))
    assert r.rc == 2 and "[harness.config]" in r.stdout and "replay_dir" in r.stdout


def test_ac_03_12_strict_turns_warnings_into_failure(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/w.gd", CASES["c09_rect"][0])            # syn-rect-props-gd is a warning
    r = assert_contract(lint(p))
    assert r.rc == 5 and r.verdict == "WARN", str(r)
    r2 = assert_contract(lint(p, "--strict"))
    assert r2.rc == 1 and r2.verdict == "FAIL", str(r2)


# ---- AC-03.13 exclude ----------------------------------------------------------------------------------------
def test_ac_03_13_addons_excluded_by_default(tmp_path):
    p = fresh(tmp_path)
    write(p, "addons/x/y.gd", YIELD)
    r = assert_contract(lint(p))
    assert r.rc == 0 and not r.has_finding("syn-yield"), str(r)
    r2 = assert_contract(lint(p, "--hook", "addons/x/y.gd", cwd=p))
    assert r2.rc == 0 and r2.stats.get("skipped", "").startswith("1"), str(r2)
    assert "(excluded)" in r2.stats["skipped"]


def test_ac_03_13_exclude_empty_lints_addons(tmp_path):
    p = fresh(tmp_path)
    write(p, "addons/x/y.gd", YIELD)
    write(p, "harness.toml", "[lint]\nexclude = []\n")
    r = assert_contract(lint(p))
    assert r.rc == 1 and r.has_finding("syn-yield", "res://addons/x/y.gd", 3), str(r)
    assert "skipped" not in r.stats
