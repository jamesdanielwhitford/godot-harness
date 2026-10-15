"""A3 contract: regex pass over the r1_5 corpus, clean fixtures, hints, comments. AC-03.2 .. 03.5, 03.8 .. 03.10."""
from __future__ import annotations

import json
import re

from a3_common import (CASES, RULES_DIR, TSCN, STRICT_TOML, expected_godot3, finding_set, fresh, lint, write)
from helpers.h import assert_contract


def _godot3(tmp_path):
    return fresh(tmp_path, "godot3_scripts")


def test_ac_03_2_godot3_scripts_exact_finding_table(tmp_path):
    p = _godot3(tmp_path)
    r = assert_contract(lint(p))
    assert r.rc == 1 and r.verdict == "FAIL" and r.verb == "lint", str(r)
    got, exp = finding_set(r), expected_godot3()
    assert got == exp, f"missing {sorted(exp - got)}; unexpected {sorted(got - exp)}"
    # every file listed as "none" has no finding
    none_files = [f"res://cases/{n}.gd" for n, (_t, rows) in CASES.items() if not rows]
    none_files += [f"res://scenes/{n}.tscn" for n, (_t, rows) in TSCN.items() if not rows] + ["res://scenes/ok.gd"]
    assert not [f for f in finding_set(r) if f[0] in none_files]


def test_ac_03_2_stat_lines_and_no_godot(tmp_path):
    r = assert_contract(lint(_godot3(tmp_path)))
    assert r.stats["files"].startswith("36 .gd, 4 .tscn, 0 .tres"), r.stats
    assert re.match(r"^\d+$", r.stats["rules"]) and int(r.stats["rules"]) >= 1213
    assert list(r.stats)[:3] == ["project", "files", "rules"]
    assert r.invocations() == []
    c = r.run_json()["counts"]
    assert (c["error"], c["warning"]) == (37, 5)


def test_ac_03_2_first_line_counts(tmp_path):
    r = assert_contract(lint(_godot3(tmp_path)))
    assert re.match(r"^37 errors, 5 warnings in 41 files", r.reason), r.reason


def test_ac_03_3_dedup_generated_rule_wins_over_hand_rule(tmp_path):
    r = assert_contract(lint(_godot3(tmp_path)))
    rows = r.findings_jsonl()
    at = lambda path, line: {f["rule"] for f in rows if f["path"] == path and f["line"] == line}  # noqa: E731
    assert "fn-rand_range" in at("res://cases/c10_randrange.gd", 3)
    assert "syn-rand-seed" not in at("res://cases/c10_randrange.gd", 3)
    assert "tscnclass-Spatial" in at("res://scenes/g3.tscn", 5)
    assert "tscn-g3-types" not in at("res://scenes/g3.tscn", 5)
    # one finding per (file, line, rule)
    keys = [(f["path"], f["line"], f["rule"]) for f in rows if f["severity"] != "info"]
    assert len(keys) == len(set(keys))
    # untyped receivers: d01 only syn-connect-3arg, d02 only prop-rect_position (dedup of syn-rect-props-gd)
    assert at("res://cases/d01_untyped_connect.gd", 4) == {"syn-connect-3arg"}
    assert at("res://cases/d02_untyped_move.gd", 4) == {"prop-rect_position"}


def test_ac_03_4_lint_base_is_clean_and_godot_free(tmp_path):
    p = fresh(tmp_path, "lint_base")
    r = assert_contract(lint(p))
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    assert r.findings == [] and r.run_json()["findings_total"] == 0
    assert r.invocations() == []
    assert "skipped" not in r.stats and "suppressed" not in r.stats


def test_ac_03_4_lint_base_clean_under_strict_replay_dirs(tmp_path):
    p = fresh(tmp_path, "lint_base")
    write(p, "harness.toml", STRICT_TOML)
    r = assert_contract(lint(p))
    assert r.rc == 0 and r.verdict == "PASS" and r.run_json()["findings_total"] == 0, str(r)


def test_ac_03_5_lint_clean_demo_nine_warnings(tmp_path):
    p = fresh(tmp_path, "lint_clean_demo")
    r = assert_contract(lint(p))
    assert r.rc == 5 and r.verdict == "WARN", str(r)
    want = {("res://hud.gd", 16, "lint.det-idle-timer", "warning"), ("res://hud.tscn", 57, "lint.det-idle-timer", "warning"),
            ("res://main.tscn", 30, "lint.det-idle-timer", "warning"), ("res://main.tscn", 33, "lint.det-idle-timer", "warning"),
            ("res://main.tscn", 35, "lint.det-idle-timer", "warning"),
            ("res://main.gd", 30, "lint.det-global-rng", "warning"), ("res://main.gd", 39, "lint.det-global-rng", "warning"),
            ("res://main.gd", 43, "lint.det-global-rng", "warning"), ("res://mob.gd", 5, "lint.det-global-rng", "warning")}
    assert finding_set(r) == want, f"missing {sorted(want - finding_set(r))}; extra {sorted(finding_set(r) - want)}"
    assert r.run_json()["counts"]["error"] == 0


def test_ac_03_5_lint_clean_demo_quiet_without_replay_dirs(tmp_path):
    p = fresh(tmp_path, "lint_clean_demo")
    write(p, "harness.toml", "[lint]\nreplay_dirs = []\n")
    r = assert_contract(lint(p))
    assert r.rc == 0 and r.verdict == "PASS" and r.run_json()["findings_total"] == 0, str(r)


def test_ac_03_8_no_godot_needed_full_and_hook(tmp_path):
    p = _godot3(tmp_path)
    env = {"HARNESS_GODOT": "/nonexistent/godot"}
    r = assert_contract(lint(p, env=env))
    assert r.rc == 1 and r.verdict == "FAIL", str(r)
    r2 = assert_contract(lint(p, "--hook", "cases/c04_yield.gd", env=env, cwd=p))
    assert r2.rc == 1 and r2.verdict == "FAIL" and r2.has_finding("syn-yield"), str(r2)
    assert r2.invocations() == []


def test_ac_03_9_every_finding_line_has_single_line_hint_le_100(tmp_path):
    r = assert_contract(lint(_godot3(tmp_path)))
    assert r.findings, "no findings shown"
    for f in r.findings:
        if f["rule"] == "lint.lsp":
            continue
        assert f["hint"], f"no hint: {f}"
        assert len(f["hint"]) <= 100, f"hint longer than 100 chars: {f}"
        assert "\n" not in f["hint"]
    for ln in r.lines:
        if re.search(r"\] (error|warning): ", ln) and "lint.lsp]" not in ln:
            assert ln.endswith(")") and "(hint: " in ln, ln


def test_ac_03_9_jsonl_hints_complete_and_equal_to_rule_data(tmp_path):
    r = assert_contract(lint(_godot3(tmp_path)))
    rules = {x["id"]: x for x in json.loads((RULES_DIR / "lint_rules.json").read_text())["rules"]}
    rows = [f for f in r.findings_jsonl() if f["severity"] != "info"]
    for f in rows:
        assert f["hint"], f"findings.jsonl row without hint: {f}"
        if f["rule"] in rules and not f["rule"].startswith("lint."):
            assert f["hint"] == rules[f["rule"]]["hint"], f
    shown = {(x["path"], x["line"], x["rule"]): x["hint"] for x in r.findings}
    multi = [f for f in rows if "\n" in f["hint"] or len(f["hint"]) > 100]
    assert multi, "corpus should contain at least one multi-line/long hint (syn-setget)"
    norm = lambda s: s.replace("\n", " / ")  # noqa: E731
    for f in multi:
        h = shown.get((f["path"], f["line"], f["rule"]))
        if h is None:
            continue  # cut by the 40-line cap: stdout carries only the first lines
        assert "\n" not in h and len(h) <= 100
        assert norm(f["hint"]).startswith(h[:-3] if h.endswith("...") else h), (h, f["hint"])


def test_ac_03_10_comment_only_lines_give_no_finding(tmp_path):
    p = fresh(tmp_path, "lint_base")
    write(p, "scripts/cm.gd", 'extends Node\n# yield(x, "y")\n\t# var f = File.new()\nfunc _ready() -> void:\n\tpass\n')
    write(p, "scenes/cm.tscn", '[gd_scene format=3]\n\n[node name="Root" type="Node2D"]\n; rect_position = Vector2( 1, 1 )\n')
    r = assert_contract(lint(p))
    assert r.rc == 0 and r.run_json()["findings_total"] == 0, str(r)


def test_ac_03_10_positive_controls_same_text_uncommented_and_trailing_comment(tmp_path):
    p = fresh(tmp_path, "lint_base")
    write(p, "scripts/cm.gd", 'extends Node\nfunc _ready() -> void:\n\tyield(x, "y")\n\tyield(x, "y")  # trailing note\n')
    write(p, "scenes/cm.tscn", '[gd_scene format=3]\n\n[node name="Root" type="Control"]\nrect_position = Vector2( 1, 1 )\n')
    r = assert_contract(lint(p))
    assert r.rc == 1
    assert r.has_finding("syn-yield", "res://scripts/cm.gd", 3) and r.has_finding("syn-yield", "res://scripts/cm.gd", 4)
    assert r.has_finding("tscn-rect-props", "res://scenes/cm.tscn", 4)
