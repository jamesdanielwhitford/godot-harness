"""A5 contract tests for `h run` (spec 05_scenario.md section 4, AC-05.1 .. AC-05.24, AC-05.27).

Black-box: every run is on a temp copy of tests/fixtures/projects/scenario_min (or scenario_noautoload) (B3) and every
result goes through the strict assert_contract (check-line names are project-relative paths, R-57).
`scp` is a warm copy (imported + synced); `sc_fresh` has neither .godot nor addons/.
"""
import hashlib
import json
import re
import statistics
import time

import pytest

from a5util import (JUMP, MOVER, hr, load_json, mover_golden, multi_check_lines,
                    wrong_variant, write_variant)
from helpers.h import apply_fault, copy_fixture, live_processes_mentioning

pytestmark = pytest.mark.godot

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def state_of(r, sub=""):
    p = r.artifact(f"{sub}/state.json" if sub else "state.json")
    assert p.exists(), f"{p} missing\n{r}"
    return json.loads(p.read_text())


def jsonl(path):
    assert path.exists(), f"{path} missing"
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def events_of(r, sub=""):
    return jsonl(r.artifact(f"{sub}/events.jsonl" if sub else "events.jsonl"))


def finding_lines(r):
    return [ln for ln, k in zip(r.lines[1:], r.kinds) if k == "finding"]


# ---------------------------------------------------------------- AC-05.1
def test_ac_05_1_1_jump_passes_with_ordered_stats(scp):
    r = hr(scp, JUMP)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "run"
    assert re.match(r"^6/6 asserts, 120 ticks \(", r.reason), r.reason
    keys = [k for k, _ in r.stat_items]
    want = ["project", "import", "sync", "scenario", "hash", "golden", "asserts", "events"]
    idx = [keys.index(k) for k in want]
    assert idx == sorted(idx), f"stat order {keys}"
    assert r.stats["project"] == str(scp)
    assert "twice" not in r.stats
    assert re.match(r"^res://scenarios/jump\.json \(seed 7, 120 ticks @ 60 Hz\)$", r.stats["scenario"]), r.stats["scenario"]
    assert re.match(r"^[0-9a-f]{16} chain [0-9a-f]{16}$", r.stats["hash"]), r.stats["hash"]
    assert r.stats["golden"] == "none"
    assert r.stats["asserts"] == "6 total, 6 pass, 0 fail"
    ev = r.stats["events"]
    assert ev.startswith("4 (") and "jump_pressed x1" in ev and "teleported x1" in ev and "landed x1" in ev, ev
    assert not r.findings


def test_ac_05_1_2_fresh_copy_syncs_and_imports_then_passes(sc_fresh):
    r = hr(sc_fresh, MOVER)
    assert r.rc == 0 and r.verdict == "PASS"
    assert r.stats["sync"].startswith("ran")
    assert r.stats["import"].startswith("ran")


# ---------------------------------------------------------------- AC-05.2
def test_ac_05_2_1_artifacts_exist_and_parse(scp):
    r = hr(scp, JUMP)
    assert r.rc == 0
    st = state_of(r)
    assert st["schema"] == "harness.state/1"
    assert HEX64.match(st["hash"]) and HEX64.match(st["chain"])
    assert st["hash"].startswith(r.stats["hash"].split()[0])
    assert r.stats["hash"].split()[2] == st["chain"][:16]
    assert "player" in st["entities"]
    assert st["meta"]["tick_rate"] == 60
    assert r.artifact("states.jsonl").exists()
    ticks = jsonl(r.artifact("ticks.jsonl"))
    assert len(ticks) == 121 and ticks[0]["tick"] == 0 and ticks[-1]["tick"] == 120
    assert HEX64.match(ticks[-1]["hash"]) and "player" in ticks[-1]["entities"]
    assert ticks[-1]["hash"] == st["hash"]
    ev = events_of(r)
    pressed = [e for e in ev if e["type"] == "jump_pressed"]
    assert len(pressed) == 1 and pressed[0]["tick"] == 40
    m = load_json(r.artifact("metrics.json"))
    assert m["schema"] == "harness.metrics/1"
    assert m["metrics"]["ticks"] == 120
    assert m["metrics"]["events.jump_pressed"] == 1
    assert m["metrics"]["tick_signals"] == 121, "R-18: tick_completed is emitted ticks + 1 times"
    a = load_json(r.artifact("asserts.json"))
    assert len(a) == 6 and all(x["pass"] is True for x in a)
    res = load_json(r.artifact("scenario.resolved.json"))
    assert res["ticks"] == 120 and res["seed"] == 7 and res["tick_rate"] == 60


# ---------------------------------------------------------------- AC-05.3
def test_ac_05_3_1_two_runs_give_identical_hash_and_chain(scp):
    r1 = hr(scp, JUMP)
    r2 = hr(scp, JUMP)
    assert r1.rc == 0 and r2.rc == 0
    s1, s2 = state_of(r1), state_of(r2)
    assert s1["hash"] == s2["hash"] and s1["chain"] == s2["chain"]
    assert r1.stats["hash"] == r2.stats["hash"]
    assert jsonl(r1.artifact("ticks.jsonl")) == jsonl(r2.artifact("ticks.jsonl"))


# ---------------------------------------------------------------- AC-05.4
@pytest.mark.parametrize("scen", ["jump", "mover"])
def test_ac_05_4_1_twice_identical(scp, scen):
    r = hr(scp, f"res://scenarios/{scen}.json", "--twice")
    assert r.rc == 0 and r.verdict == "PASS"
    assert r.stats["twice"] == "identical (A 60 fps vs B 120 fps, global seed changed)"
    assert r.artifact("A").is_dir() and r.artifact("B").is_dir()
    assert state_of(r, "A")["hash"] == state_of(r, "B")["hash"]
    assert state_of(r, "A")["chain"] == state_of(r, "B")["chain"]
    keys = [k for k, _ in r.stat_items]
    assert keys.index("hash") < keys.index("twice") < keys.index("golden")


def _twice_fault(scp, fault_id):
    apply_fault(fault_id, scp)
    return hr(scp, JUMP, "--twice")


def test_ac_05_4_2_twice_catches_global_rng(scp):
    r = _twice_fault(scp, "FAULT-A5-01")
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.stats["twice"].startswith("DIFFERENT")
    assert "cause: global-rng" in r.stats["twice"]
    assert r.has_finding(rule="run.nondeterministic", severity="error")
    assert re.search(r"diverged at tick \d+", r.reason), r.reason


def test_ac_05_4_3_twice_catches_idle_tween_and_process_delta(scp, tmp_path):
    r = _twice_fault(scp, "FAULT-A5-02")
    assert r.rc == 1 and "cause: frame-rate" in r.stats["twice"]
    assert r.has_finding(rule="run.nondeterministic", severity="error")
    p2 = copy_fixture("scenario_min", tmp_path / "second")
    apply_fault("FAULT-A5-08", p2)
    r2 = hr(p2, JUMP, "--twice")
    assert r2.rc == 1 and "cause: frame-rate" in r2.stats["twice"]


def test_ac_05_4_4_nondeterministic_finding_points_at_entity_script(scp):
    r = _twice_fault(scp, "FAULT-A5-01")
    f = [x for x in r.findings_jsonl() if x["rule"] == "run.nondeterministic"]
    assert f and f[0]["path"] == "res://scripts/player.gd", f
    assert "player" in f[0]["message"]


def test_ac_05_4_5_twice_names_identical_runs_cause(scp):
    r = _twice_fault(scp, "FAULT-A5-11")
    assert r.rc == 1 and "cause: identical-runs" in r.stats["twice"]


# ---------------------------------------------------------------- AC-05.5
def test_ac_05_5_1_input_timing_hold(scp):
    r = hr(scp, JUMP)
    assert r.rc == 0
    ev = events_of(r)
    pressed = [e for e in ev if e["type"] == "jump_pressed"]
    released = [e for e in ev if e["type"] == "jump_released"]
    assert len(pressed) == 1 and pressed[0]["tick"] == 40
    assert pressed[0]["data"] == {"just": True, "pressed": True}
    assert pressed[0]["src"] == "harness"
    assert len(released) == 1 and released[0]["tick"] == 43
    assert state_of(r)["entities"]["player"]["input_events"] == 1


def test_ac_05_5_2_strength_input_moves_player(scp):
    r = hr(scp, JUMP)
    states = jsonl(r.artifact("states.jsonl"))
    by_tick = {s["tick"]: s["entities"] for s in states}
    x60 = by_tick[60]["player"]["position"]["x"]
    assert 99 <= x60 <= 101


# ---------------------------------------------------------------- AC-05.6
def test_ac_05_6_1_failing_assert_reports_measured_value(scp):
    rel = write_variant(scp, "wrong.json", wrong_variant)
    r = hr(scp, rel)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert re.match(r"^1 of 6 asserts failed", r.reason), r.reason
    pat = (r"^res://scenarios/\S+\.json: \[run\.assert\] error: asserts\[\d+\] player\.position\.x ge 400 "
           r"@tick 100: got -?[0-9.]+")
    assert any(re.search(pat, ln) for ln in r.lines), r.stdout
    rows = load_json(r.artifact("asserts.json"))
    bad = [x for x in rows if not x["pass"]]
    assert len(bad) == 1 and isinstance(bad[0]["got"], (int, float)) and bad[0]["got"] < 400
    assert r.stats["asserts"] == "6 total, 5 pass, 1 fail"


# ---------------------------------------------------------------- AC-05.8
def _scenario_error_cases():
    base = {"schema": "harness.scenario/1", "scene": "res://scenes/level.tscn", "seed": 7, "ticks": 600,
            "asserts": [{"at_end": True, "path": "mover.n", "op": "eq", "value": 600}]}

    def mk(**kw):
        d = dict(base)
        d.update(kw)
        return d

    no_scene = {k: v for k, v in base.items() if k != "scene"}
    return {
        "missing_scene": (no_scene, r"scene"),
        "unknown_key": (mk(bogus=1), r"bogus"),
        "tick_gt_ticks": (mk(asserts=[{"tick": 700, "path": "mover.n", "op": "eq", "value": 1}]), r"/asserts/0/tick"),
        "pressed_and_strength": (mk(inputs=[{"tick": 5, "action": "jump", "pressed": True, "strength": 1}]),
                                 r"/inputs/0"),
        "metric_with_tick": (mk(asserts=[{"tick": 5, "metric": "ticks", "op": "eq", "value": 1}]), r"/asserts/0"),
        "op_not_in_enum": (mk(asserts=[{"at_end": True, "path": "mover.n", "op": "approx", "value": 1}]),
                           r"/asserts/0/op"),
        "between_not_pair": (mk(asserts=[{"at_end": True, "path": "mover.n", "op": "between", "value": [1]}]),
                             r"/asserts/0"),
        "unknown_var": (mk(inputs=[{"tick": "$nope", "action": "jump", "pressed": True}]), r"nope"),
        "scene_absent": (mk(scene="res://scenes/absent.tscn"), r"scene"),
    }


@pytest.mark.parametrize("case", sorted(_scenario_error_cases()))
def test_ac_05_8_1_scenario_errors_rc2_with_json_pointer(scp, case):
    body, needle = _scenario_error_cases()[case]
    (scp / "scenarios" / "bad.json").write_text(json.dumps(body))
    r = hr(scp, "res://scenarios/bad.json")
    assert r.rc == 2 and r.verdict == "ERROR" and r.verb == "run", str(r)
    assert any(f["rule"] == "run.scenario" and f["severity"] == "error" for f in r.findings), str(r)
    f = [x for x in r.findings if x["rule"] == "run.scenario"][0]
    assert f["path"] == "res://scenarios/bad.json" and f["line"] is None
    assert re.search(needle, f["message"]), f["message"]
    assert r.invocations() == [], "no Godot invocation for a scenario that fails validation"


def test_ac_05_8_2_unknown_path_and_empty_dir_rc2(scp):
    r = hr(scp, "res://scenarios/nosuch.json")
    assert r.rc == 2 and r.verdict == "ERROR"
    (scp / "scenarios" / "empty").mkdir()
    r = hr(scp, "res://scenarios/empty/")
    assert r.rc == 2 and r.verdict == "ERROR"


# ---------------------------------------------------------------- AC-05.9
def test_ac_05_9_1_var_moves_the_jump(scp):
    r0 = hr(scp, "res://scenarios/sweep.json")
    assert r0.rc == 0
    assert [e["tick"] for e in events_of(r0) if e["type"] == "jump_pressed"] == [40]
    r5 = hr(scp, "res://scenarios/sweep.json", "--var", "k=5")
    assert r5.rc == 0
    assert [e["tick"] for e in events_of(r5) if e["type"] == "jump_pressed"] == [45]
    res = load_json(r5.artifact("scenario.resolved.json"))
    assert res["inputs"][0]["tick"] == 45


def test_ac_05_9_2_unknown_var_rc2(scp):
    r = hr(scp, "res://scenarios/sweep.json", "--var", "nope=1")
    assert r.rc == 2 and r.verdict == "ERROR"
    assert r.invocations() == []


# ---------------------------------------------------------------- AC-05.10
def test_ac_05_10_1_command_applied_before_its_tick(scp):
    r = hr(scp, JUMP)
    assert r.rc == 0
    by_tick = {s["tick"]: s["entities"] for s in jsonl(r.artifact("states.jsonl"))}
    assert by_tick[89]["player"]["position"]["x"] < 500
    assert 500 <= by_tick[90]["player"]["position"]["x"] <= 502
    tele = [e for e in events_of(r) if e["type"] == "teleported"]
    assert len(tele) == 1 and tele[0]["src"] == "command" and tele[0]["cmd"] == 1
    assert load_json(r.artifact("metrics.json"))["metrics"]["commands_total"] == 1


# ---------------------------------------------------------------- AC-05.11
def test_ac_05_11_1_unknown_target(scp):
    rel = write_variant(scp, "ghost.json", lambda d: d.update(
        commands=[{"tick": 10, "type": "teleport", "target": "ghost", "value": {"x": 1, "y": 1}}]))
    r = hr(scp, rel)
    assert r.rc == 1 and r.verdict == "FAIL"
    f = [x for x in r.findings if x["rule"] == "run.unknown-target"]
    assert f and f[0]["severity"] == "error" and f[0]["path"] == "res://scenarios/ghost.json"
    assert "commands[0]" in f[0]["message"] and "ghost" in f[0]["message"]


def test_ac_05_11_2_unknown_command_type(scp):
    rel = write_variant(scp, "warp.json", lambda d: d.update(commands=[{"tick": 10, "type": "warp"}]))
    r = hr(scp, rel)
    assert r.rc == 1 and r.verdict == "FAIL"
    f = [x for x in r.findings if x["rule"] == "run.unknown-command"]
    assert f and f[0]["severity"] == "error" and "warp" in f[0]["message"]


# ---------------------------------------------------------------- AC-05.12
def test_ac_05_12_1_unknown_action_with_did_you_mean(scp):
    def typo(d):
        d["inputs"][1]["action"] = "jmup"

    rel = write_variant(scp, "typo.json", typo)
    r = hr(scp, rel)
    assert r.rc == 1 and r.verdict == "FAIL"
    f = [x for x in r.findings if x["rule"] == "run.unknown-action"]
    assert f and f[0]["severity"] == "error" and f[0]["path"] == "res://scenarios/typo.json"
    assert "jmup" in f[0]["message"]
    assert re.search(r"did you mean 'jump'", r.stdout)
    assert not [i for i in r.invocations() if i["kind"] == "scenario"], "checked before Godot starts"


# ---------------------------------------------------------------- AC-05.13
def test_ac_05_13_1_autoload_not_declared_is_rc2_not_synced(tmp_path):
    p = copy_fixture("scenario_noautoload", tmp_path / "proj")
    r = hr(p, JUMP)
    assert r.rc == 2 and r.verdict == "ERROR" and r.verb == "run"
    f = [x for x in r.findings if x["rule"] == "run.not-synced"]
    assert f and f[0]["severity"] == "error" and "h sync" in f[0]["message"]
    assert not [i for i in r.invocations() if i["kind"] == "scenario"]


def test_ac_05_13_2_declared_but_addons_absent_syncs_and_runs(sc_fresh):
    assert not (sc_fresh / "addons").exists()
    r = hr(sc_fresh, JUMP)
    assert r.rc == 0 and r.verdict == "PASS"
    assert r.stats["sync"].startswith("ran")
    assert (sc_fresh / "addons" / "harness").is_dir()


# ---------------------------------------------------------------- AC-05.14
def dice_sum(r):
    return state_of(r)["entities"]["dice"]["sum"]


def test_ac_05_14_1_same_seed_same_sum_other_seed_other_sum(scp):
    a1 = hr(scp, "res://scenarios/dice.json", "--seed", "1")
    a2 = hr(scp, "res://scenarios/dice.json", "--seed", "1")
    b = hr(scp, "res://scenarios/dice.json", "--seed", "2")
    assert a1.rc == a2.rc == b.rc == 0
    assert dice_sum(a1) == dice_sum(a2)
    assert dice_sum(a1) != dice_sum(b)
    assert re.search(r"\(seed 1, 100 ticks", a1.stats["scenario"]), a1.stats["scenario"]
    assert load_json(a1.artifact("scenario.resolved.json"))["seed"] == 1


def test_ac_05_14_2_scenario_seed_used_without_flag(scp):
    d0 = hr(scp, "res://scenarios/dice.json")
    d5 = hr(scp, "res://scenarios/dice.json", "--seed", "5")
    assert re.search(r"\(seed 5, 100 ticks", d0.stats["scenario"]), d0.stats["scenario"]
    assert dice_sum(d0) == dice_sum(d5)


def test_ac_05_14_3_overrides_skip_golden(scp):
    mover_golden(scp)
    r = hr(scp, MOVER, "--seed", "4")
    assert r.stats["golden"] == "skipped (overrides)"
    assert not r.has_finding(rule="run.golden-mismatch") and not r.has_finding(rule="run.golden-drift")
    r = hr(scp, MOVER, "--ticks", "300")
    assert r.stats["golden"] == "skipped (overrides)"


def test_ac_05_14_4_ticks_override(scp):
    r = hr(scp, MOVER, "--ticks", "60")
    st = state_of(r)
    assert st["tick"] == 60 and st["entities"]["mover"]["n"] == 60
    assert re.search(r"60 ticks", r.stats["scenario"])
    assert len(jsonl(r.artifact("ticks.jsonl"))) == 61


# ---------------------------------------------------------------- AC-05.15
def test_ac_05_15_1_bind_exposes_plain_nodes(scp):
    r = hr(scp, "res://scenarios/bind.json")
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    ents = state_of(r)["entities"]
    assert ents["box"]["position"]["x"] == 50
    assert isinstance(ents["box"]["visible"], bool)
    assert isinstance(ents["player2"]["is_on_floor()"], bool)


def test_ac_05_15_2_wrong_node_path_is_run_bind_error(scp):
    def bad(d):
        d["bind"]["box"]["node"] = "NoSuchNode"

    rel = write_variant(scp, "bind_bad.json", bad, base="bind.json")
    r = hr(scp, rel)
    assert r.rc == 1 and r.verdict == "FAIL"
    f = [x for x in r.findings if x["rule"] == "run.bind"]
    assert f and f[0]["severity"] == "error" and f[0]["path"] == "res://scenarios/bind_bad.json"
    assert "NoSuchNode" in f[0]["message"] or "box" in f[0]["message"]


# ---------------------------------------------------------------- AC-05.16
def test_ac_05_16_1_record_then_match_then_exists_then_force(scp):
    gpath = scp / "scenarios" / "mover.golden.json"
    assert not gpath.exists()
    r = hr(scp, MOVER, "--record")
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    assert gpath.exists()
    assert "twice" in r.stats and r.stats["twice"].startswith("identical")
    assert r.stats["golden"].startswith("recorded") and "mover.golden.json" in r.stats["golden"]
    g = json.loads(gpath.read_text())
    assert g["schema"] == "harness.golden/1"
    assert [c["tick"] for c in g["checkpoints"]] == list(range(0, 601, 60))
    st = state_of(r, "A") if r.artifact("A").is_dir() else state_of(r)
    assert g["final_hash"] == st["hash"] and g["chain_hash"] == st["chain"]
    assert HEX64.match(g["scenario_sha256"])
    assert g["scenario_sha256"] == hashlib.sha256((scp / "scenarios" / "mover.json").read_bytes()).hexdigest()
    last = g["checkpoints"][-1]["entities"]["mover"]
    assert last["n"] == 600 and last["x"] == 900

    r2 = hr(scp, MOVER)
    assert r2.rc == 0 and r2.verdict == "PASS" and r2.stats["golden"].startswith("match"), str(r2)

    r3 = hr(scp, MOVER, "--record")
    assert r3.rc == 2 and r3.verdict == "ERROR"
    assert "golden exists" in r3.stdout

    r4 = hr(scp, MOVER, "--record", "--force")
    assert r4.rc == 0 and r4.verdict == "PASS"


# ---------------------------------------------------------------- AC-05.17
def test_ac_05_17_1_nondeterministic_run_never_writes_golden(scp):
    apply_fault("FAULT-A5-01", scp)
    r = hr(scp, JUMP, "--record")
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.has_finding(rule="run.nondeterministic", severity="error")
    assert not (scp / "scenarios" / "jump.golden.json").exists()
    assert not list((scp / "scenarios").glob("*.golden.json"))


# ---------------------------------------------------------------- AC-05.18
def test_ac_05_18_1_off_by_one_value_is_golden_mismatch(scp):
    mover_golden(scp, n600=599)
    r = hr(scp, MOVER)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.stats["golden"].upper().startswith("MISMATCH")
    f = [x for x in r.findings if x["rule"] == "run.golden-mismatch"]
    assert f and f[0]["severity"] == "error" and f[0]["path"] == "res://scenarios/mover.json"
    msg = f[0]["message"]
    assert "mover.n" in msg and "599" in msg and "600" in msg


def test_ac_05_18_2_exact_values_bogus_hashes_is_drift_warning(scp):
    mover_golden(scp)
    r = hr(scp, MOVER)
    assert r.rc == 5 and r.verdict == "WARN", str(r)
    assert r.stats["golden"].startswith("drift")
    f = [x for x in r.findings if x["rule"] == "run.golden-drift"]
    assert f and f[0]["severity"] == "warning"
    rs = hr(scp, MOVER, "--strict")
    assert rs.rc == 1 and rs.verdict == "FAIL"
    assert rs.has_finding(rule="run.golden-drift")


def test_ac_05_18_3_stale_golden(scp):
    mover_golden(scp, stale=True)
    r = hr(scp, MOVER)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.stats["golden"] == "stale"
    f = [x for x in r.findings if x["rule"] == "run.golden-stale"]
    assert f and f[0]["severity"] == "error"
    assert "--record --force" in r.stdout


# ---------------------------------------------------------------- AC-05.19
def test_ac_05_19_1_no_asserts_no_golden_warns(scp):
    r = hr(scp, "res://scenarios/noasserts.json")
    assert r.rc == 5 and r.verdict == "WARN"
    f = [x for x in r.findings if x["rule"] == "run.no-asserts"]
    assert f and f[0]["severity"] == "warning"
    assert hr(scp, "res://scenarios/noasserts.json", "--strict").rc == 1


# ---------------------------------------------------------------- AC-05.20
def test_ac_05_20_1_runtime_script_error_fails_even_if_asserts_pass(scp):
    apply_fault("FAULT-A5-07", scp)
    r = hr(scp, JUMP)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.stats["asserts"].startswith("6 total, 6 pass"), r.stats["asserts"]
    assert any(re.search(r"^res://scripts/player\.gd:\d+: \[godot\.script-error\]", ln) for ln in r.lines), r.stdout


# ---------------------------------------------------------------- AC-05.21
def test_ac_05_21_1_infinite_loop_is_hang_within_scenario_timeout(scp):
    apply_fault("FAULT-A5-05", scp)
    t0 = time.monotonic()
    r = hr(scp, JUMP)
    wall = time.monotonic() - t0
    assert r.rc == 1 and r.verdict == "FAIL"
    assert r.has_finding(rule="harness.hang", severity="error")
    assert wall <= 12, f"wall {wall:.1f}s"
    inv = [i for i in r.invocations() if i["kind"] == "scenario"]
    assert inv and inv[0]["timed_out"] is True and inv[0]["rc"] == 124 and inv[0]["timeout_s"] == 5
    assert not live_processes_mentioning(str(scp))


# ---------------------------------------------------------------- AC-05.22
def test_ac_05_22_1_nodepath_state_is_nonserializable_finding(scp):
    apply_fault("FAULT-A5-06", scp)
    r = hr(scp, JUMP)
    assert r.rc == 1 and r.verdict == "FAIL"
    f = [x for x in r.findings if x["rule"] == "run.state-nonserializable"]
    assert f and f[0]["severity"] == "error"
    assert f[0]["path"] == "res://scripts/player.gd"
    assert "player" in f[0]["message"] and "target" in f[0]["message"] and "NodePath" in f[0]["message"]
    assert r.artifact("state.json").exists(), "the run still completes"
    assert state_of(r)["tick"] == 120


# ---------------------------------------------------------------- AC-05.23
@pytest.mark.slow
def test_ac_05_23_1_perf_600_ticks(scp):
    single, twice = [], []
    for _ in range(3):
        r = hr(scp, MOVER)
        assert r.rc == 0
        single.append(r.wall)
    for _ in range(3):
        r = hr(scp, MOVER, "--twice")
        assert r.rc == 0
        twice.append(r.wall)
    assert statistics.median(single) <= 3.0, single
    assert statistics.median(twice) <= 5.0, twice


# ---------------------------------------------------------------- AC-05.24
def _golden_decoy(scp):
    """A *.golden.json inside the scenario dir that belongs to no scenario: must not be run as a scenario."""
    mover_golden(scp, scenario_rel="scenarios/clean/mover.json")
    (scp / "scenarios" / "clean" / "mover.golden.json").rename(scp / "scenarios" / "clean" / "zzz.golden.json")


def test_ac_05_24_1_dir_runs_all_scenarios_ignoring_goldens(scp):
    _golden_decoy(scp)
    r = hr(scp, "res://scenarios/clean/", check=True)
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    assert r.reason.startswith("2/2 scenarios passed"), r.reason
    checks = multi_check_lines(r)
    assert [c[0] for c in checks] == ["OK", "OK"], r.stdout
    names = [c[1] for c in checks]
    assert names == ["scenarios/clean/jump.json", "scenarios/clean/mover.json"]
    assert "zzz" not in r.stdout


def test_ac_05_24_2_adding_a_failing_scenario_fails_the_dir(scp):
    write_variant(scp, "clean/wrong.json", wrong_variant)
    r = hr(scp, "res://scenarios/clean/", check=True)
    assert r.rc == 1 and r.verdict == "FAIL", str(r)
    assert r.reason.startswith("2/3 scenarios passed"), r.reason
    checks = multi_check_lines(r)
    assert sorted(c[0] for c in checks) == ["FAIL", "OK", "OK"]
    assert r.has_finding(rule="run.assert", severity="error")


def test_ac_05_24_3_several_positional_paths(scp):
    r = hr(scp, "res://scenarios/mover.json", "res://scenarios/dice.json", check=True)
    assert r.rc == 0 and r.reason.startswith("2/2 scenarios passed"), str(r)
    assert len(multi_check_lines(r)) == 2


# ---------------------------------------------------------------- AC-05.27
def test_ac_05_27_1_time_scale_warns_once(scp):
    apply_fault("FAULT-A5-12", scp)
    r = hr(scp, MOVER)
    assert r.rc == 5 and r.verdict == "WARN", str(r)
    rows = [x for x in r.findings_jsonl() if x["rule"] == "run.time-scale"]
    assert len(rows) == 1 and rows[0]["severity"] == "warning"
