"""A7 contract: `h trace <suite>` on feel_min (spec 07_feel.md AC-07.9 .. 12, 15, 16, 17, 20, 21, 23). Owner: T7.

Black-box: subprocess only, fixture copies only (B3). Red until B7 lands (`h trace` does not exist yet).
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from a7util import (AGENT_LINE, ALL_METRICS, SUITE, TARGETED, edit_suite, edit_text, metrics_json, replay_kinds,
                    report_text, trace)
from helpers.h import REPO, apply_fault, assert_contract, copy_fixture, load_fault, run_h

pytestmark = pytest.mark.godot

STAT_ORDER = ["project", "import", "sync", "suite", "targets", "runs", "report"]


# ---- AC-07.9 ---------------------------------------------------------------------------------------------
def test_ac_07_9_clean_suite_passes_with_all_targets_met(clean_run):
    r, _ = clean_run
    assert r.rc == 0, str(r)
    assert r.verdict == "PASS" and r.verb == "trace"
    assert re.match(r"^PASS trace 11/11 targets met", r.lines[0]), r.lines[0]
    assert not r.findings


def test_ac_07_9_stat_lines_in_spec_order(clean_run):
    r, _ = clean_run
    keys = [k for k, _ in r.stat_items]
    assert keys[: len(STAT_ORDER)] == STAT_ORDER, keys


def test_ac_07_9_twelve_ok_check_lines_one_without_target(clean_run):
    r, _ = clean_run
    oks = [c for c in r.checks if c[0] == "OK"]
    assert len(oks) == 12, r.checks
    assert [c for c in r.checks if c[0] != "OK"] == []
    names = [c[1] for c in oks]
    for m in ALL_METRICS:
        assert m in names, f"{m} missing from check lines {names}"
    tap = r.check("jump.tap_apex_px")
    assert tap is not None and "(no target)" in tap[2]
    assert sum("(no target)" in c[2] for c in oks) == 1


def test_ac_07_9_runs_stat_and_report_file(clean_run):
    r, _ = clean_run
    m = re.match(r"^(\d+) ", r.stats["runs"])
    assert m and int(m.group(1)) >= 20, r.stats["runs"]
    report = r.artifact("feel_report.md")
    assert report.is_file()
    text = report.read_text()
    for name in ALL_METRICS:
        assert name in text, f"{name} not in feel_report.md"
    assert AGENT_LINE in text
    assert r.stats["report"].endswith("feel_report.md")


def test_ac_07_9_warm_wall_clock_budget(clean_run):
    r, _ = clean_run
    assert r.wall <= 20, f"{r.wall:.1f}s > 20s warm budget (spec 3.8)"


# ---- AC-07.10 ----------------------------------------------------------------------------------------------
def test_ac_07_10_metrics_json_has_a_passing_value_per_target(clean_run):
    r, _ = clean_run
    mj = metrics_json(r)
    assert mj["measurements"], mj
    assert mj.get("rates") == [60]
    for name in TARGETED:
        m = mj["measurements"][name]
        assert m["value"] is not None, name
        assert m["verdict"] == "pass", (name, m)
    tap = mj["measurements"]["jump.tap_apex_px"]
    assert tap["verdict"] == "none" and tap["value"] is not None
    for name, m in mj["measurements"].items():
        for key in ("metric", "probe", "value", "unit", "by_rate", "target", "verdict"):
            assert key in m, f"{name} lacks {key}"


def test_ac_07_10_run_trace_csv_rows_columns_and_meta(clean_run):
    r, _ = clean_run
    csv_path = r.artifact("traces/run.csv")
    meta_path = r.artifact("traces/run.meta.json")
    assert csv_path.is_file() and meta_path.is_file()
    meta = json.loads(meta_path.read_text())
    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    assert len(body) == meta["ticks"] + 1 == meta["rows"] == 121
    for col in ("tick", "player.position.x", "player.velocity.x", "player.is_on_floor",
                "camera.get_screen_center_position.x", "in.right"):
        assert col in header, f"{col} not in {header}"
    assert header[0] == "tick"
    assert [int(x[0]) for x in body] == list(range(121))
    assert meta["schema"] == "harness.trace/1" and meta["tick_rate"] == 60


def test_ac_07_10_mark_column_is_declared_in_the_trace(clean_run):
    r, _ = clean_run
    with open(r.artifact("traces/run.csv"), newline="") as f:
        header = next(csv.reader(f))
    assert "mark.state" in header


# ---- AC-07.11 ----------------------------------------------------------------------------------------------
def test_ac_07_11_window_values_match_the_fixture_timers(clean_run):
    r, _ = clean_run
    mj = metrics_json(r)["measurements"]
    c = mj["jump.coyote_window"]["value"]
    b = mj["jump.buffer_window"]["value"]
    assert 5 <= c <= 6, f"coyote window {c} not in [5, 6] (0.1 s timer at 60 Hz)"
    assert 4 <= b <= 6, f"buffer window {b} not in [4, 6]"


def test_ac_07_11_report_lists_sweep_offsets_with_yes_no(clean_run):
    r, _ = clean_run
    c = int(metrics_json(r)["measurements"]["jump.coyote_window"]["value"])
    text = report_text(r)
    for off in range(0, c + 2):
        assert re.search(rf"^\|?\s*{off}\s*\|.*\b(y|n|yes|no)\b", text, re.MULTILINE | re.IGNORECASE), \
            f"sweep offset {off} missing from the report tables"


# ---- AC-07.12 ----------------------------------------------------------------------------------------------
def test_ac_07_12_two_runs_are_byte_identical(feel):
    a = trace(feel, SUITE)
    b = trace(feel, SUITE)
    assert a.rc == b.rc == 0
    ta = sorted(p.name for p in a.artifact("traces").glob("*.csv"))
    tb = sorted(p.name for p in b.artifact("traces").glob("*.csv"))
    assert ta == tb and ta, ta
    for n in ta:
        assert a.artifact(f"traces/{n}").read_bytes() == b.artifact(f"traces/{n}").read_bytes(), n
    assert metrics_json(a)["measurements"] == metrics_json(b)["measurements"]


# ---- AC-07.15 suite errors: rc 2 before any replay ---------------------------------------------------------
def _suite_error(feel, rule, edit=None, *, text_edit=None, delete=None, extra_files=None):
    for rel, content in (extra_files or {}).items():
        p = Path(feel) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    if edit:
        edit_suite(feel, edit)
    if text_edit:
        edit_text(feel, *text_edit)
    if delete:
        (Path(feel) / delete).unlink()
    r = trace(feel, SUITE)
    assert r.rc == 2, str(r)
    assert r.verdict == "ERROR"
    assert r.has_finding(rule=rule), f"want [{rule}]\n{r}"
    assert replay_kinds(r) == [], "no scenario replay may run for an invalid suite"
    return r


def _probe(d, pid):
    return next(p for p in d["probes"] if p["id"] == pid)


def test_ac_07_15_unknown_metric(feel):
    _suite_error(feel, "feel.unknown-metric",
                 lambda d: _probe(d, "run")["metrics"].append({"metric": "run.no_such_metric"}))


def test_ac_07_15_duplicate_measurement_name(feel):
    _suite_error(feel, "feel.suite",
                 lambda d: _probe(d, "jump")["metrics"].append({"metric": "run.max_speed", "name": "run.max_speed"}))


def test_ac_07_15_window_metric_without_sweep(feel):
    _suite_error(feel, "feel.suite", lambda d: _probe(d, "coyote").pop("sweep"))


def test_ac_07_15_non_window_metric_with_sweep(feel):
    _suite_error(feel, "feel.suite", lambda d: _probe(d, "run").update({"sweep": {"anchor": "land"}}))


def test_ac_07_15_sweep_scenario_without_t0_var(feel):
    scen = {"schema": "harness.scenario/1", "scene": "res://scenes/ledge.tscn", "seed": 7, "ticks": 240,
            "vars": {"k": 0},
            "inputs": [{"tick": 1, "action": "right", "pressed": True},
                       {"tick": "200+$k", "action": "jump", "pressed": True, "hold": 3}]}
    _suite_error(feel, "feel.suite",
                 lambda d: _probe(d, "coyote").update({"scenario": "res://feel/coyote_not0.json"}),
                 extra_files={"feel/coyote_not0.json": json.dumps(scen)})


def test_ac_07_15_missing_targets_file(feel):
    _suite_error(feel, "feel.targets", delete="feel/targets.tres")


def test_ac_07_15_target_with_min_above_max(feel):
    _suite_error(feel, "feel.targets", text_edit=("feel/targets.tres", "min_value = 200.0", "min_value = 300.0"))


def test_ac_07_15_bad_suite_schema_version(feel):
    r = _suite_error(feel, "feel.suite", lambda d: d.update({"schema": "harness.feel/99"}))
    assert re.search(r"feel\.suite\] error:", r.stdout)


# ---- AC-07.16 unapproved targets -------------------------------------------------------------------------
def _blank_approvals(feel):
    edit_text(feel, "feel/targets.tres", 'approved_by = "fixture-human"', 'approved_by = ""', 11)


def test_ac_07_16_unapproved_targets_warn_not_pass(feel):
    _blank_approvals(feel)
    r = trace(feel, SUITE)
    assert r.rc == 5, str(r)
    assert r.verdict == "WARN"
    assert r.has_finding(rule="feel.unapproved", severity="warning", msg_re=r"11 of 11")
    assert not [f for f in r.findings_jsonl() if f["severity"] == "error"]


def test_ac_07_16_unapproved_and_out_of_range_is_still_only_a_warning(feel):
    apply_fault("FAULT-A7-01", feel)
    _blank_approvals(feel)
    r = trace(feel, SUITE)
    assert r.rc == 5, str(r)
    assert r.has_finding(rule="feel.out-of-range", severity="warning")
    assert r.has_finding(rule="feel.unapproved", severity="warning")


def test_ac_07_16_strict_turns_unapproved_into_fail(feel):
    _blank_approvals(feel)
    r = trace(feel, SUITE, "--strict")
    assert r.rc == 1 and r.verdict == "FAIL", str(r)


# ---- AC-07.17 --propose ------------------------------------------------------------------------------------
def test_ac_07_17_propose_writes_proposals_and_never_the_targets(feel):
    targets = Path(feel) / "feel" / "targets.tres"
    before = targets.read_bytes()
    r = trace(feel, SUITE, "--propose")
    assert r.rc in (0, 5), str(r)
    prop = r.artifact("proposed_targets.json")
    assert prop.is_file()
    data = json.loads(prop.read_text())
    entries = data.get("targets", data) if isinstance(data, dict) else data
    if isinstance(entries, dict):
        entries = [dict(v, metric=k) for k, v in entries.items()]
    assert len(entries) == 11, entries
    mj = metrics_json(r)["measurements"]
    for e in entries:
        assert e["approved_by"] == "", e
        m = mj[e["metric"]]
        v = m["seconds"] if e.get("unit") == "s" and m.get("seconds") is not None else m["value"]
        assert e["min_value"] <= v <= e["max_value"], (e, v)
    assert targets.read_bytes() == before, "--propose must not write the targets file"
    assert "Proposed" in report_text(r)


# ---- AC-07.18 (non-TTY half; the pty half lives in tests/e2e/a7) --------------------------------------------
def test_ac_07_18_approve_without_tty_is_rc_2_and_writes_nothing(feel):
    targets = Path(feel) / "feel" / "targets.tres"
    p = trace(feel, SUITE, "--propose")
    before = targets.read_bytes()
    run_dir = p.require_log_dir()
    r = trace(feel, SUITE, "--approve", "--from", str(run_dir))
    assert r.rc == 2, str(r)
    assert r.verdict == "ERROR"
    assert r.has_finding(rule="feel.approve-needs-tty")
    assert targets.read_bytes() == before


# ---- AC-07.20 ----------------------------------------------------------------------------------------------
def test_ac_07_20_misspelt_trace_node_is_a_bind_error(feel):
    edit_suite(feel, lambda d: d["trace"]["player"].update({"node": "Playr"}))
    r = trace(feel, SUITE)
    assert r.rc == 1, str(r)
    assert r.has_finding(rule="feel.bind", severity="error", msg_re="Playr")


def test_ac_07_20_missing_trace_autoload_is_not_synced(tmp_path):
    proj = copy_fixture("feel_noautoload", tmp_path / "proj")
    r = trace(proj, SUITE)
    assert r.rc == 2, str(r)
    assert r.has_finding(rule="feel.not-synced", msg_re=r"h sync")


# ---- AC-07.21 ----------------------------------------------------------------------------------------------
def test_ac_07_21_runtime_script_error_fails_the_trace(feel):
    edit_text(feel, "scripts/player.gd", "var buffer_t := 0.0\n",
              "var buffer_t := 0.0\nvar _frames := 0\n")
    edit_text(feel, "scripts/player.gd", "func _physics_process(delta: float) -> void:\n",
              "func _physics_process(delta: float) -> void:\n\t_frames += 1\n"
              "\tif _frames == 50:\n\t\tvar nothing = null\n\t\tnothing.no_such_method()\n")
    r = trace(feel, SUITE)
    assert r.rc == 1, str(r)
    assert r.has_finding(rule="godot.script-error", path="res://scripts/player.gd")


# ---- AC-07.23 each planted feel fault fails exactly its metric --------------------------------------------
FEEL_FAULTS = {
    "FAULT-A7-01": "run.accel_time",
    "FAULT-A7-02": "jump.fall_rise_ratio",
    "FAULT-A7-03": "jump.coyote_window",
    "FAULT-A7-04": "jump.buffer_window",
    "FAULT-A7-05": "jump.cut_ratio",
    "FAULT-A7-06": "camera.settle_time",
}


@pytest.mark.parametrize("fault_id", sorted(FEEL_FAULTS))
def test_ac_07_23_fault_fails_exactly_its_metric(feel, fault_id):
    metric = FEEL_FAULTS[fault_id]
    spec = apply_fault(fault_id, feel)
    r = trace(feel, *spec["run"]["args"])
    assert r.rc == 1, str(r)
    fails = [c for c in r.checks if c[0] == "FAIL"]
    assert [c[1] for c in fails] == [metric], f"want only {metric} to FAIL:\n{r}"
    others = [c for c in r.checks if c[1] != metric]
    assert others and all(c[0] == "OK" for c in others), others
    for rx in spec["expect"]["regex"]:
        assert re.search(rx, r.stdout, re.MULTILINE), rx
    for rx in spec["expect"]["not_regex"]:
        assert not re.search(rx, r.stdout, re.MULTILINE), rx


def test_ac_07_23_fault_files_cover_the_six_feel_faults():
    for fid, metric in FEEL_FAULTS.items():
        spec = load_fault(fid)
        assert spec["fixture"] == "feel_min" and spec["run"]["verb"] == "trace"
        assert metric.replace(".", r"\.") in "".join(spec["expect"]["regex"] + spec["expect"]["not_regex"])


# ---- fixture self-checks (no Godot): the repo fixture is what the spec says ---------------------------------
def test_fixture_targets_file_has_eleven_approved_targets():
    text = (REPO / "tests/fixtures/projects/feel_min/feel/targets.tres").read_text()
    assert text.count('approved_by = "fixture-human"') == 11
    assert text.count('approved_on = "2026-10-01"') == 11


def test_fixture_suite_has_twelve_measurements_and_eleven_targets():
    suite = json.loads((REPO / "tests/fixtures/projects/feel_min/feel/player.feel.json").read_text())
    names = []
    for p in suite["probes"]:
        names += [m.get("name", m["metric"]) for m in p["metrics"]]
    names += [d["name"] for d in suite["derived"]]
    assert sorted(names) == sorted(ALL_METRICS)
    text = (REPO / "tests/fixtures/projects/feel_min/feel/targets.tres").read_text()
    assert sorted(re.findall(r'^metric = "([^"]+)"', text, re.MULTILINE)) == sorted(TARGETED)


def test_fixture_fault_toml_files_parse():
    for fid in [f"FAULT-A7-{i:02d}" for i in range(1, 12)] + ["CLEAN-A7-01", "CLEAN-A7-02"]:
        spec = load_fault(fid)
        assert spec["id"] == fid and spec["area"] == "A7"
