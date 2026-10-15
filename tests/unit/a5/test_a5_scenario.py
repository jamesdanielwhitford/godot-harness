"""A5 unit layer: harness.scenario (REVIEW R-01 allowlist; spec 05_scenario.md 2.7, 3.4).

Covers AC-05.7 (assert semantics on synthetic states), the pure part of AC-05.8/05.9 (load: schema, semantics,
$var substitution) and the pure part of AC-05.18 (compare_golden).

Shapes taken from the spec (everything else is [U], see .claude/handoff/A5/test_notes.md):
- states      = list of {"tick": k, "entities": {id: state}} (states.jsonl lines)
- metrics     = {name: number} (metrics.json "metrics")
- resolve()   = (value, reason|None); its `state` argument is the entities mapping {id: state}
- eval_asserts returns asserts.json entries {index, path|metric, op, value, ..., pass, got, at_tick}
- compare_golden returns {status, findings, n}; findings are findings.jsonl-style dicts with `rule`, `severity`, `message`
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from helpers.h import copy_fixture


class _Lazy:
    """Import harness.scenario at call time so a missing module fails each test, not collection."""

    def __getattr__(self, name):
        import importlib

        return getattr(importlib.import_module("harness.scenario"), name)


scenario = _Lazy()


def _err_text(exc) -> str:
    parts = [str(exc), repr(exc.args)]
    for a in ("pointer", "what", "message"):
        if hasattr(exc, a):
            parts.append(str(getattr(exc, a)))
    return " ".join(parts)


# ------------------------------------------------------------------------------------------ helpers (AC-05.7)
def resolved(asserts, ticks=100):
    return {"schema": "harness.scenario/1", "scene": "res://scenes/level.tscn", "seed": 1, "ticks": ticks,
            "tick_rate": 60, "hash_every": 1, "golden_every": 60, "golden_tol": 0.001,
            "inputs": [], "commands": [], "dumps": [], "asserts": asserts}


def st(tick, **entities):
    return {"tick": tick, "entities": entities}


def one(assert_entry, states, metrics=None, ticks=100):
    out = scenario.eval_asserts(resolved([assert_entry], ticks), states, metrics or {})
    assert len(out) == 1
    return out[0]


PLAYER10 = [st(10, player={"hp": 5, "name": "a", "alive": True, "none": None, "arr": [1, 2, 3], "obj": {"k": 1},
                           "position": {"x": 12.5, "y": 3.0}, "items": [{"id": "a"}, {"id": "b"}]})]


def A(op, path="player.hp", value=None, **kw):
    e = {"tick": 10, "path": path, "op": op}
    if value is not None or op != "exists":
        e["value"] = value
    e.update(kw)
    return e


# ------------------------------------------------------------------------------------------------ AC-05.7
def test_ac_05_7_1_eq_ne_numbers_with_and_without_tol():
    states = [st(10, player={"hp": 5.0004})]
    assert one(A("eq", value=5), states)["pass"] is False
    assert one(A("eq", value=5, tol=0.001), states)["pass"] is True
    assert one(A("eq", value=5, tol=0.0001), states)["pass"] is False
    assert one(A("ne", value=5), states)["pass"] is True
    assert one(A("ne", value=5, tol=0.001), states)["pass"] is False
    exact = [st(10, player={"hp": 5})]
    assert one(A("eq", value=5), exact)["pass"] is True
    assert one(A("ne", value=5), exact)["pass"] is False


@pytest.mark.parametrize("path,value,expect", [
    ("player.name", "a", True), ("player.name", "b", False),
    ("player.alive", True, True), ("player.alive", False, False),
    ("player.arr", [1, 2, 3], True), ("player.arr", [1, 2], False),
    ("player.obj", {"k": 1}, True), ("player.obj", {"k": 2}, False),
])
def test_ac_05_7_2_eq_exact_for_non_numbers(path, value, expect):
    assert one(A("eq", path=path, value=value), PLAYER10)["pass"] is expect


def test_ac_05_7_2b_eq_null_value():
    e = {"tick": 10, "path": "player.none", "op": "eq", "value": None}
    assert one(e, PLAYER10)["pass"] is True


@pytest.mark.parametrize("op,value,expect", [
    ("lt", 5, False), ("lt", 6, True), ("le", 5, True), ("le", 4, False),
    ("gt", 5, False), ("gt", 4, True), ("ge", 5, True), ("ge", 6, False),
])
def test_ac_05_7_3_ordering_ops(op, value, expect):
    assert one(A(op, value=value), PLAYER10)["pass"] is expect


@pytest.mark.parametrize("val,tol,expect", [
    (1.0, None, True), (3.0, None, True), (2.0, None, True), (3.2, None, False), (0.8, None, False),
    (3.2, 0.25, True), (0.8, 0.25, True), (3.3, 0.25, False),
])
def test_ac_05_7_4_between_inclusive_and_tol_widens(val, tol, expect):
    e = {"tick": 10, "path": "player.hp", "op": "between", "value": [1, 3]}
    if tol is not None:
        e["tol"] = tol
    assert one(e, [st(10, player={"hp": val})])["pass"] is expect


def test_ac_05_7_5_exists():
    e = {"tick": 10, "path": "player.position.x", "op": "exists"}
    assert one(e, PLAYER10)["pass"] is True
    assert one({**e, "path": "player.nokey"}, PLAYER10)["pass"] is False
    assert one({**e, "path": "ghost.position"}, PLAYER10)["pass"] is False


def test_ac_05_7_6_vector_and_array_paths():
    assert one(A("eq", path="player.position.x", value=12.5), PLAYER10)["pass"] is True
    assert one(A("lt", path="player.position.y", value=4), PLAYER10)["pass"] is True
    assert one(A("eq", path="player.arr[1]", value=2), PLAYER10)["pass"] is True
    assert one(A("eq", path="player.arr[7]", value=2), PLAYER10)["pass"] is False
    assert one(A("eq", path="player.items[1].id", value="b"), PLAYER10)["pass"] is True


def test_ac_05_7_7_resolve_values_and_reasons():
    ents = PLAYER10[0]["entities"]
    val, why = scenario.resolve(ents, "player.position.x")
    assert val == 12.5 and why is None
    val, why = scenario.resolve(ents, "player.arr[2]")
    assert val == 3 and why is None
    val, why = scenario.resolve(ents, "ghost.hp")
    assert val is None and why and re.search(r"entity 'ghost' not present", why)
    val, why = scenario.resolve(ents, "player.vel")
    assert val is None and why and re.search(r"key 'vel' not in player", why)


def test_ac_05_7_8_missing_entity_or_key_fails_with_null_got():
    r = one(A("ge", path="ghost.hp", value=0), PLAYER10)
    assert r["pass"] is False and r["got"] is None
    r = one(A("exists", path="player.vel"), PLAYER10)
    assert r["pass"] is False and r["got"] is None
    # a tick whose dump lacks the entity entirely
    r = one(A("ge", value=0), [st(10, other={"hp": 1})])
    assert r["pass"] is False and r["got"] is None


def test_ac_05_7_9_entry_fields():
    r = one(A("ge", value=3), PLAYER10)
    assert r["index"] == 0 and r["op"] == "ge" and r["path"] == "player.hp" and r["value"] == 3
    assert r["pass"] is True and r["got"] == 5 and r["at_tick"] == 10


def test_ac_05_7_10_failed_got_is_measured_value():
    r = one(A("ge", value=400, path="player.position.x"), PLAYER10)
    assert r["pass"] is False and r["got"] == 12.5 and r["at_tick"] == 10


def _during(values, op="lt", value=5, quant=None, start=10):
    states = [st(start + i, v={"x": x}) for i, x in enumerate(values)]
    e = {"during": [start, start + len(values) - 1], "path": "v.x", "op": op, "value": value}
    if quant:
        e["quant"] = quant
    return one(e, states)


def test_ac_05_7_11_during_all_reports_first_failing_tick():
    r = _during([1, 2, 9, 2, 3], quant="all")
    assert r["pass"] is False and r["got"] == 9 and r["at_tick"] == 12
    assert _during([1, 2, 3], quant="all")["pass"] is True
    # `all` is the default quantifier
    r = _during([1, 2, 9, 8])
    assert r["pass"] is False and r["got"] == 9 and r["at_tick"] == 12


def test_ac_05_7_12_during_any_reports_closest_value():
    r = _during([9, 8, 7, 9], quant="any")
    assert r["pass"] is False and r["got"] == 7 and r["at_tick"] == 12
    assert _during([9, 3, 7], quant="any")["pass"] is True
    r = _during([1, 4, 2], op="ge", value=10, quant="any")
    assert r["pass"] is False and r["got"] == 4 and r["at_tick"] == 11


def test_ac_05_7_13_metric_at_end():
    m = {"ticks": 120, "events.jump_pressed": 1}
    e = {"at_end": True, "metric": "events.jump_pressed", "op": "eq", "value": 1}
    r = one(e, [], m, ticks=120)
    assert r["pass"] is True and r["got"] == 1 and r["metric"] == "events.jump_pressed"
    assert one({**e, "value": 2}, [], m, ticks=120)["pass"] is False
    r = one({**e, "metric": "nosuch"}, [], m, ticks=120)
    assert r["pass"] is False and r["got"] is None
    assert one({"at_end": True, "metric": "ticks", "op": "between", "value": [100, 120]}, [], m, ticks=120)["pass"]


def test_ac_05_7_14_at_end_reads_last_tick_dump():
    states = [st(5, p={"x": 1}), st(100, p={"x": 7})]
    r = one({"at_end": True, "path": "p.x", "op": "eq", "value": 7}, states, ticks=100)
    assert r["pass"] is True and r["got"] == 7


def test_ac_05_7_15_indices_follow_file_order():
    asserts = [A("ge", value=1), A("ge", value=100), A("exists", path="player.position")]
    out = scenario.eval_asserts(resolved(asserts), PLAYER10, {})
    assert [o["index"] for o in out] == [0, 1, 2]
    assert [o["pass"] for o in out] == [True, False, True]


# ------------------------------------------------------------------------------------- load (AC-05.8, 05.9)
@pytest.fixture
def proj(tmp_path):
    return copy_fixture("scenario_min", tmp_path / "proj")


def _write(proj, name, body):
    p = proj / "scenarios" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body))
    return p


def base(**kw):
    d = {"schema": "harness.scenario/1", "scene": "res://scenes/level.tscn", "seed": 7, "ticks": 600,
         "asserts": [{"at_end": True, "path": "mover.n", "op": "eq", "value": 600}]}
    d.update(kw)
    return d


def test_ac_05_8_0_valid_scenario_loads_with_defaults(proj):
    d = scenario.load(proj / "scenarios" / "jump.json")
    assert d["ticks"] == 120 and d["seed"] == 7
    assert d["tick_rate"] == 60 and d["hash_every"] == 1 and d["golden_every"] == 60
    assert d["golden_tol"] == 0.001


def _bad_cases():
    return {
        "missing_scene": ({k: v for k, v in base().items() if k != "scene"}, r"scene"),
        "unknown_key": (base(bogus=1), r"bogus"),
        "tick_gt_ticks": (base(asserts=[{"tick": 700, "path": "mover.n", "op": "eq", "value": 1}]),
                          r"/asserts/0/tick"),
        "pressed_and_strength": (base(inputs=[{"tick": 5, "action": "jump", "pressed": True, "strength": 1}]),
                                 r"/inputs/0"),
        "metric_with_tick": (base(asserts=[{"tick": 5, "metric": "ticks", "op": "eq", "value": 1}]),
                             r"/asserts/0"),
        "op_not_in_enum": (base(asserts=[{"at_end": True, "path": "mover.n", "op": "approx", "value": 1}]),
                           r"/asserts/0/op"),
        "between_not_pair": (base(asserts=[{"at_end": True, "path": "mover.n", "op": "between", "value": [1]}]),
                             r"/asserts/0"),
        "unknown_var": (base(inputs=[{"tick": "$nope", "action": "jump", "pressed": True}]), r"nope"),
        "scene_absent": (base(scene="res://scenes/absent.tscn"), r"scene"),
        "negative_var_result": (base(vars={"k": 5}, inputs=[{"tick": "3-$k", "action": "jump", "pressed": True}]),
                                r"/inputs/0/tick"),
        "ticks_over_limit": (base(ticks=36001), r"ticks"),
        "input_tick_zero": (base(inputs=[{"tick": 0, "action": "jump", "pressed": True}]), r"/inputs/0/tick"),
        "during_reversed": (base(asserts=[{"during": [50, 10], "path": "mover.n", "op": "ge", "value": 0}]),
                            r"/asserts/0"),
    }


@pytest.mark.parametrize("case", sorted(_bad_cases()))
def test_ac_05_8_1_load_rejects_with_json_pointer(proj, case):
    body, needle = _bad_cases()[case]
    p = _write(proj, f"bad_{case}.json", body)
    with pytest.raises(Exception) as ei:
        scenario.load(p)
    assert type(ei.value).__name__ == "ScenarioError", f"{type(ei.value).__name__}: {ei.value}"
    assert re.search(needle, _err_text(ei.value)), _err_text(ei.value)


def test_ac_05_9_1_vars_substitution_and_override(proj):
    d = scenario.load(proj / "scenarios" / "sweep.json")
    assert d["inputs"][0]["tick"] == 40
    d = scenario.load(proj / "scenarios" / "sweep.json", vars={"k": 5})
    assert d["inputs"][0]["tick"] == 45


def test_ac_05_9_2_expression_in_ticks_and_overrides(proj):
    p = _write(proj, "expr.json", base(vars={"n": 10}, ticks="$n+20"))
    assert scenario.load(p)["ticks"] == 30
    assert scenario.load(p, ticks=77)["ticks"] == 77
    assert scenario.load(p, seed=99)["seed"] == 99


def test_ac_05_9_3_unknown_override_var_is_error(proj):
    with pytest.raises(Exception) as ei:
        scenario.load(proj / "scenarios" / "sweep.json", vars={"nope": 1})
    assert type(ei.value).__name__ == "ScenarioError"


def test_ac_05_9_4_hold_expands_or_stays_valid(proj):
    d = scenario.load(proj / "scenarios" / "jump.json")
    # `hold` is kept or expanded into an explicit release; either way a press at 40 exists
    assert any(i["tick"] == 40 and i["action"] == "jump" for i in d["inputs"])


def test_ac_05_8_2_write_resolved_roundtrip(proj, tmp_path):
    d = scenario.load(proj / "scenarios" / "jump.json")
    out = tmp_path / "scenario.resolved.json"
    scenario.write_resolved(d, out)
    assert json.loads(out.read_text()) == json.loads(json.dumps(d))
    txt = out.read_text()
    keys = list(json.loads(txt).keys())
    assert keys == sorted(keys), "write_resolved sorts keys"


# ------------------------------------------------------------------------------------------ golden (AC-05.18)
def _golden(n600=600, x600=900.0, final="f" * 64, chain="c" * 64, sha="s" * 64, extra=None):
    cps = []
    for k in range(0, 601, 60):
        n = n600 if k == 600 else k
        x = x600 if k == 600 else 1.5 * k
        ent = {"mover": {"n": n, "x": x}}
        if extra and k == 600:
            ent["mover"].update(extra)
        cps.append({"tick": k, "hash": "0" * 64, "entities": ent})
    return {"schema": "harness.golden/1", "scenario_sha256": sha, "recorded_at": "2026-10-15T00:00:00Z",
            "meta": {}, "final_hash": final, "chain_hash": chain, "tol": 0.001, "checkpoints": cps}


def _run(n600=600, x600=900.0, h="f" * 64, chain="c" * 64, extra=None):
    states = []
    for k in range(0, 601, 60):
        ent = {"n": n600 if k == 600 else k, "x": x600 if k == 600 else 1.5 * k}
        if extra and k == 600:
            ent.update(extra)
        states.append({"tick": k, "entities": {"mover": ent}})
    state = {"schema": "harness.state/1", "tick": 600, "hash": h, "chain": chain, "meta": {},
             "entities": states[-1]["entities"]}
    return state, states


def _cg(golden, run, sha="s" * 64):
    state, states = run
    res = scenario.compare_golden(golden, sha, state, states)
    return res, str(res["status"]).lower()


def _rules(res):
    return {f["rule"]: f for f in res["findings"]}


def test_ac_05_18_1_match_on_equal_hashes():
    res, status = _cg(_golden(), _run())
    assert status.startswith("match") and not [f for f in res["findings"] if f["severity"] == "error"]


def test_ac_05_18_2_stale_when_scenario_sha_differs():
    res, status = _cg(_golden(sha="a" * 64), _run(), sha="b" * 64)
    assert status == "stale"
    f = _rules(res)["run.golden-stale"]
    assert f["severity"] == "error"


def test_ac_05_18_3_drift_when_hash_differs_but_values_equal():
    res, status = _cg(_golden(final="1" * 64), _run())
    assert status.startswith("drift")
    f = _rules(res)["run.golden-drift"]
    assert f["severity"] == "warning"


def test_ac_05_18_4_drift_when_floats_within_tol():
    res, status = _cg(_golden(final="1" * 64, x600=900.0004), _run(x600=900.0))
    assert status.startswith("drift")
    assert _rules(res)["run.golden-drift"]["severity"] == "warning"


def test_ac_05_18_5_mismatch_on_int_off_by_one_names_tick_path_and_values():
    res, status = _cg(_golden(final="1" * 64, n600=599), _run())
    assert status == "mismatch"
    f = _rules(res)["run.golden-mismatch"]
    assert f["severity"] == "error"
    assert "mover.n" in f["message"] and "599" in f["message"] and "600" in f["message"]


def test_ac_05_18_6_mismatch_when_float_exceeds_tol():
    res, status = _cg(_golden(final="1" * 64, x600=901.0), _run(x600=900.0))
    assert status == "mismatch"
    assert "mover.x" in _rules(res)["run.golden-mismatch"]["message"]


def test_ac_05_18_7_ints_are_exact_even_with_large_tol():
    g = _golden(final="1" * 64, n600=601)
    g["tol"] = 100.0
    res, status = _cg(g, _run())
    assert status == "mismatch"


def test_ac_05_18_8_array_length_must_match():
    g = _golden(final="1" * 64, extra={"q": [1, 2, 3]})
    res, status = _cg(g, _run(extra={"q": [1, 2]}))
    assert status == "mismatch"


def test_ac_05_18_9_earliest_mismatching_checkpoint_is_named():
    g = _golden(final="1" * 64, n600=599)
    g["checkpoints"][3]["entities"]["mover"]["n"] = 999  # tick 180
    res, status = _cg(g, _run())
    assert status == "mismatch"
    assert "180" in _rules(res)["run.golden-mismatch"]["message"]
