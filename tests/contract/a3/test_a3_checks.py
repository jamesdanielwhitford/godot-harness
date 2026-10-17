"""A3 contract: project-aware checks and lint.* rules. AC-03.14 .. 03.20."""
from __future__ import annotations

import pytest

from a3_common import CASES, STRICT_TOML, finding_set, fresh, lint, lint_findings, write
from helpers.h import assert_contract

HDR = "extends Node\n"


def _lint_file(p, rel, text, *extra):
    write(p, rel, text)
    return assert_contract(lint(p, str(p / rel), *extra))


def _got(r, rule_prefix="lint."):
    return {(f["path"], f["line"], f["rule"], f["severity"]) for f in lint_findings(r) if f["rule"].startswith(rule_prefix)}


# ---- AC-03.14 input actions ---------------------------------------------------------------------------------
INPUT_SRC = (
    "extends Node\n"                                                       # 1
    "func _ready() -> void:\n"                                             # 2
    '\tvar a := Input.is_action_pressed("jumpp")\n'                        # 3 flagged
    '\tvar b := Input.is_action_pressed("ui_accept")\n'                    # 4
    '\tvar c := Input.is_action_pressed(&"jump")\n'                        # 5
    '\tvar d := Input.get_vector("move_left", "move_right", "jump", "jump")\n'  # 6
    '\tvar e := Input.is_action_pressed("dyn")\n'                          # 7 (added by InputMap.add_action elsewhere)
    '\tvar n := "jump"\n'                                                  # 8
    "\tvar f := Input.is_action_pressed(n)\n"                              # 9 non-literal
    '\tvar g := Input.get_axis("move_left", "nope")\n'                     # 10 flagged
    '\tvar h := InputMap.has_action("nope")\n'                             # 11 not checked
)


def test_ac_03_14_input_action_checks(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/dyn.gd", 'extends Node\nfunc _ready() -> void:\n\tInputMap.add_action("dyn")\n')
    write(p, "scripts/in.gd", INPUT_SRC)
    r = assert_contract(lint(p))
    got = _got(r)
    assert got == {("res://scripts/in.gd", 3, "lint.input-action", "error"), ("res://scripts/in.gd", 10, "lint.input-action", "error")}, got
    f3 = [f for f in lint_findings(r, "lint.input-action") if f["line"] == 3][0]
    assert "jumpp" in f3["message"] and "jump" in f3["hint"]
    f10 = [f for f in lint_findings(r, "lint.input-action") if f["line"] == 10][0]
    assert "nope" in f10["message"]
    assert r.rc == 1


@pytest.mark.parametrize("call", ["is_action_just_pressed", "is_action_just_released", "is_action_released",
                                  "get_action_strength", "get_action_raw_strength"])
def test_ac_03_14_other_checked_calls(tmp_path, call):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/c.gd", f'extends Node\nfunc _ready() -> void:\n\tInput.{call}("nopeee")\n')
    assert r.has_finding("lint.input-action", "res://scripts/c.gd", 3, "error"), str(r)


def test_ac_03_14_project_actions_listed_when_nothing_close(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/c.gd", 'extends Node\nfunc _ready() -> void:\n\tInput.is_action_pressed("zzzzqqqq")\n')
    f = lint_findings(r, "lint.input-action")[0]
    assert any(a in f["hint"] for a in ("jump", "move_left", "move_right")), f


# ---- AC-03.15 signals ---------------------------------------------------------------------------------------
def test_ac_03_15_signal_declared_on_this_script(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/s1.gd", 'extends Node\nsignal hit\nfunc _ready() -> void:\n\temit_signal("hitt")\n')
    f = lint_findings(r, "lint.signal-name")
    assert len(f) == 1 and f[0]["line"] == 4 and f[0]["severity"] == "error"
    assert r.rc == 1 and __import__("re").search(r"\bhit\b", f[0]["hint"]), f


def test_ac_03_15_inherited_native_signal_is_known(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/s2.gd", 'extends Button\nfunc _ready() -> void:\n\temit_signal("pressed")\n')
    assert not lint_findings(r, "lint.signal-name") and r.rc in (0, 5), str(r)


def test_ac_03_15_signal_from_script_path_and_class_name_bases(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/s3.gd", 'extends "res://scripts/base.gd"\nfunc _ready() -> void:\n\temit_signal("died")\n\temit_signal("diedd")\n')
    write(p, "scripts/s4.gd", 'extends BaseThing\nfunc _ready() -> void:\n\temit_signal("died")\n\temit_signal("diedd")\n')
    r = assert_contract(lint(p))
    got = _got(r)
    # the chain resolves, so "died" is known and only the typo is flagged
    assert got == {("res://scripts/s3.gd", 4, "lint.signal-name", "error"), ("res://scripts/s4.gd", 4, "lint.signal-name", "error")}, got


def test_ac_03_15_unresolvable_base_is_skipped(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/s5.gd", 'extends SomeMissingClass\nfunc _ready() -> void:\n\temit_signal("whatever")\n')
    assert not lint_findings(r, "lint.signal-name") and r.rc in (0, 5), str(r)


def test_ac_03_15_typed_receiver_connect_unknown_signal(tmp_path):
    p = fresh(tmp_path)
    src = ('extends Node\nfunc _ready() -> void:\n\tvar b := Button.new()\n\tb.connect("nosuch", _x)\n'
           '\tb.connect("pressed", _x)\nfunc _x() -> void:\n\tpass\n')
    r = _lint_file(p, "scripts/s6.gd", src)
    f = lint_findings(r, "lint.signal-name")
    assert [(x["line"], x["severity"]) for x in f] == [(4, "error")], f


def test_ac_03_15_untyped_receiver_is_skipped(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/s7.gd", 'extends Node\nfunc hook(obj, f: Callable) -> void:\n\tobj.connect("x", f)\n')
    assert not lint_findings(r, "lint.signal-name") and r.rc == 0, str(r)


# ---- AC-03.16 determinism -----------------------------------------------------------------------------------
TSCN_TIMER = '[gd_scene format=3]\n\n[node name="Root" type="Node"]\n\n[node name="T" type="Timer" parent="."]\n'
TSCN_ANIM = '[gd_scene format=3]\n\n[node name="Root" type="Node"]\n\n[node name="A" type="AnimationPlayer" parent="."]\n'
E, W = "error", "warning"
# (relpath, text, expected under strict replay_dirs, expected under the default harness.toml)
DET = {
    "rng_sim": ("sim/a.gd", "extends RefCounted\nfunc f() -> float:\n\treturn randf()\n",
                [(3, "lint.det-global-rng", E)], [(3, "lint.det-global-rng", E)]),
    "rng_scripts": ("scripts/a.gd", "extends Node\nfunc f() -> float:\n\treturn randf()\n",
                    [(3, "lint.det-global-rng", W)], []),
    "rng_exempt_file": ("scripts/rng.gd", None, [], []),     # existing lint_base file with seed()/randi_range
    "rng_method": ("scripts/b.gd", "extends Node\nvar rng := RandomNumberGenerator.new()\nfunc f() -> float:\n\treturn rng.randf()\n", [], []),
    "shuffle_sim": ("sim/c.gd", "extends RefCounted\nfunc f(arr: Array) -> void:\n\tarr.shuffle()\n",
                    [(3, "lint.det-global-rng", E)], [(3, "lint.det-global-rng", E)]),
    "clock_sim": ("sim/d.gd", "extends RefCounted\nfunc f() -> int:\n\treturn Time.get_ticks_msec()\n",
                  [(3, "lint.det-wallclock", E)], [(3, "lint.det-wallclock", E)]),
    "clock_scripts": ("scripts/d.gd", "extends Node\nfunc f() -> int:\n\treturn Time.get_ticks_msec()\n",
                      [(3, "lint.det-wallclock", W)], []),
    "tween_idle": ("scripts/e.gd", 'extends Node\nfunc _ready() -> void:\n\tvar t := create_tween()\n\tt.tween_property(self, "modulate:a", 1.0, 0.5)\n',
                   [(3, "lint.det-idle-tween", W)], []),
    "tween_physics": ("scripts/e2.gd", 'extends Node\nfunc _ready() -> void:\n\tvar t := create_tween().set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)\n\tt.tween_property(self, "modulate:a", 1.0, 0.5)\n', [], []),
    "timer_idle": ("scripts/f.gd", "extends Node\nfunc _ready() -> void:\n\tvar t := get_tree().create_timer(1.0)\n\tprint(t)\n",
                   [(3, "lint.det-idle-timer", W)], []),
    "timer_physics": ("scripts/f2.gd", "extends Node\nfunc _ready() -> void:\n\tvar t := get_tree().create_timer(1.0, false, true)\n\tprint(t)\n", [], []),
    "tscn_timer_idle": ("scenes/t.tscn", TSCN_TIMER, [(5, "lint.det-idle-timer", W)], []),
    "tscn_timer_phys": ("scenes/t2.tscn", TSCN_TIMER + "process_callback = 0\n", [], []),
    "tscn_anim_idle": ("scenes/a.tscn", TSCN_ANIM, [(5, "lint.det-idle-anim", W)], []),
    "tscn_anim_phys": ("scenes/a2.tscn", TSCN_ANIM + "callback_mode_process = 0\n", [], []),
    "time_scale": ("scripts/g.gd", "extends Node\nfunc _ready() -> void:\n\tEngine.time_scale = 2.0\n",
                   [(3, "lint.det-time-scale", W)], [(3, "lint.det-time-scale", W)]),
}


def _det_run(tmp_path, key, strict: bool):
    rel, text, exp_strict, exp_default = DET[key]
    p = fresh(tmp_path)
    if strict:
        write(p, "harness.toml", STRICT_TOML)
    if text is not None:
        write(p, rel, text)
    r = assert_contract(lint(p, str(p / rel)))
    return r, "res://" + rel, (exp_strict if strict else exp_default)


@pytest.mark.parametrize("key", list(DET))
def test_ac_03_16_determinism_strict_replay_dirs(tmp_path, key):
    r, res, exp = _det_run(tmp_path, key, True)
    got = {(f["line"], f["rule"], f["severity"]) for f in lint_findings(r) if f["path"] == res and f["rule"].startswith("lint.")}
    assert got == set(exp), f"{key}: got {sorted(got)}, want {sorted(exp)}\n{r}"
    assert r.rc == (1 if any(s == E for _l, _r, s in exp) else 5 if exp else 0), str(r)


@pytest.mark.parametrize("key", list(DET))
def test_ac_03_16_determinism_default_replay_dirs_empty(tmp_path, key):
    r, res, exp = _det_run(tmp_path, key, False)
    got = {(f["line"], f["rule"], f["severity"]) for f in lint_findings(r) if f["path"] == res and f["rule"].startswith("lint.")}
    assert got == set(exp), f"{key}: got {sorted(got)}, want {sorted(exp)}\n{r}"


# ---- AC-03.17 sim-node --------------------------------------------------------------------------------------
SIM_SRC = ("extends Node2D\n"                 # 1
           "var p: NodePath\n"                # 2
           "var n: Sprite2D\n"                # 3
           "func f() -> void:\n"              # 4
           '\tget_node("x")\n'                # 5
           "\tget_tree()\n")                  # 6


def test_ac_03_17_sim_node_in_sim_dir(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "sim/s.gd", SIM_SRC)
    got = {(f["line"], f["severity"]) for f in lint_findings(r, "lint.sim-node") if f["path"] == "res://sim/s.gd"}
    assert got == {(1, E), (2, E), (3, E), (5, E), (6, E)}, got
    assert r.rc == 1


def test_ac_03_17_same_code_outside_sim_is_fine(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/s.gd", SIM_SRC)
    assert not lint_findings(r, "lint.sim-node"), str(r)


def test_ac_03_17_sim_dirs_config_moves_scope(tmp_path):
    p = fresh(tmp_path)
    write(p, "harness.toml", '[harness]\nsim_dirs = ["res://logic"]\n')
    write(p, "logic/s.gd", SIM_SRC)
    write(p, "sim/s.gd", SIM_SRC)
    r = assert_contract(lint(p))
    paths = {f["path"] for f in lint_findings(r, "lint.sim-node")}
    assert paths == {"res://logic/s.gd"}, paths


# ---- AC-03.18 raw keycode -----------------------------------------------------------------------------------
KEY_SRC = "extends Node\nfunc _process(_d: float) -> void:\n\tif Input.is_key_pressed(KEY_SPACE):\n\t\tpass\n"


def test_ac_03_18_raw_keycode_warns_outside_remap_code(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/player2.gd", KEY_SRC)
    assert r.rc == 5 and r.has_finding("lint.raw-keycode", "res://scripts/player2.gd", 3, "warning"), str(r)


@pytest.mark.parametrize("rel", ["scripts/input_remap.gd", "scripts/my_rebind_ui.gd", "scripts/keybind_menu.gd"])
def test_ac_03_18_remap_files_exempt(tmp_path, rel):
    p = fresh(tmp_path)
    r = _lint_file(p, rel, KEY_SRC)
    assert r.rc == 0 and not lint_findings(r, "lint.raw-keycode"), str(r)


# ---- AC-03.19 mixed indentation -----------------------------------------------------------------------------
def test_ac_03_19_c28_line_4(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "res://cases/c28_tabspace.gd"))
    assert finding_set(r) == {("res://cases/c28_tabspace.gd", 4, "lint.indent-mixed", "error")}, str(r)


def test_ac_03_19_space_aligned_continuation_in_parens_is_fine(tmp_path):
    p = fresh(tmp_path)
    src = ("extends Node\nfunc _ready() -> void:\n\tvar a := foo(1,\n\t             2)\n\tprint(a)\n"
           "func foo(x: int, y: int) -> int:\n\treturn x + y\n")
    r = _lint_file(p, "scripts/cont.gd", src)
    assert r.rc == 0 and not lint_findings(r, "lint.indent-mixed"), str(r)


def test_ac_03_19_spaces_first_then_tab_is_flagged(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/mix.gd", "extends Node\nfunc _ready() -> void:\n    var a := 1\n\tprint(a)\n")
    assert r.has_finding("lint.indent-mixed", "res://scripts/mix.gd", 4, "error"), str(r)


def test_ac_03_19_consistent_spaces_are_fine(tmp_path):
    p = fresh(tmp_path)
    r = _lint_file(p, "scripts/sp.gd", "extends Node\nfunc _ready() -> void:\n    var a := 1\n    print(a)\n")
    assert not lint_findings(r, "lint.indent-mixed"), str(r)


# ---- AC-03.20 Godot 3 project.godot -------------------------------------------------------------------------
def test_ac_03_20_config_version_4(tmp_path):
    p = fresh(tmp_path)
    pg = p / "project.godot"
    pg.write_text(pg.read_text().replace("config_version=5", "config_version=4"))
    r = assert_contract(lint(p))
    assert r.rc == 1
    f = [x for x in r.findings if x["rule"] == "lint.g3-project"]
    assert len(f) == 1 and f[0]["path"] == "res://project.godot" and f[0]["severity"] == "error" and f[0]["line"] == 2, r.findings
    assert r.stats["files"].endswith("project.godot")
