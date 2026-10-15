"""A3 lint test data shared by the contract tests (owner T3). Not a copy of tests/helpers: only A3 constants
and tiny wrappers around helpers.h. Source: .claude/plans/specs/03_lint.md section 6.1 (corpus) and 4 (ACs)."""
from __future__ import annotations

from pathlib import Path

from helpers.h import REPO, copy_fixture, run_h, write  # noqa: F401  (re-exported for the tests)

RULES_DIR = REPO / "tools" / "harness" / "rules"
T = "\t"

# ---- section 6.1: cases/*.gd -> (text, expected [(line, rule, severity)]) -------------------------------------
CASES: dict[str, tuple[str, list]] = {
    "c01_kinematic": ("extends KinematicBody2D\nfunc _ready():\n\tpass\n", [(1, "class-KinematicBody2D", "error")]),
    "c02_onready": ("extends Node\nonready var a = 1\nfunc _ready():\n\tpass\n", [(2, "syn-onready", "error")]),
    "c03_export": ("extends Node\nexport var a = 1\nfunc _ready():\n\tpass\n", [(2, "syn-export", "error")]),
    "c04_yield": ('extends Node\nfunc _ready():\n\tyield(get_tree().create_timer(1.0), "timeout")\n',
                  [(3, "syn-yield", "error")]),
    "c05_connect3": ('extends Node\nfunc _ready():\n\tconnect("tree_exited", self, "_x")\nfunc _x():\n\tpass\n',
                     [(3, "syn-connect-3arg", "error")]),
    "c06_instance": ("extends Node\nfunc _ready():\n\tvar s = PackedScene.new()\n\tvar n = s.instance()\n",
                     [(4, "syn-instance", "error")]),
    "c07_tool": ("tool\nextends Node\n", [(1, "syn-tool", "error")]),
    "c08_setget": ("extends Node\nvar a = 1 setget set_a\nfunc set_a(v):\n\ta = v\n", [(2, "syn-setget", "error")]),
    "c09_rect": ("extends Control\nfunc _ready():\n\trect_position = Vector2(1,1)\n",
                 [(3, "syn-rect-props-gd", "warning")]),
    "c10_randrange": ("extends Node\nfunc _ready():\n\tprint(rand_range(0,1))\n", [(3, "fn-rand_range", "error")]),
    "c11_variant_infer": ('extends Node\nfunc _ready():\n\tvar d := {}\n\tvar x := d.get("a")\n\tprint(x)\n',
                          [(4, "syn-dict-get-infer", "warning")]),
    "c12_poolarr": ("extends Node\nvar a: PoolStringArray\n", [(2, "syn-poolarray", "error")]),
    "c13_os_ticks": ("extends Node\nfunc _ready():\n\tprint(OS.get_ticks_msec())\n", [(3, "syn-os-ticks", "error")]),
    "c14_file": ("extends Node\nfunc _ready():\n\tvar f = File.new()\n", [(3, "syn-file-dir-class", "error")]),
    "c15_move_and_slide": ("extends CharacterBody2D\nfunc _physics_process(d):\n"
                           "\tvelocity = move_and_slide(velocity, Vector2.UP)\n",
                           [(3, "syn-move-and-slide-args", "error")]),
    "c16_changescene": ('extends Node\nfunc _ready():\n\tget_tree().change_scene("res://a.tscn")\n',
                        [(3, "fn-change_scene", "error")]),
    "c17_stepify": ("extends Node\nfunc _ready():\n\tprint(stepify(1.234,0.1))\n", [(3, "fn-stepify", "error")]),
    "c18_emit_str": ('extends Node\nsignal foo\nfunc _ready():\n\temit_signal("fooo")\n',
                     [(4, "syn-yield-signal-string-emit", "warning"), (4, "lint.signal-name", "error")]),
    "c19_get_node_in_var": ("extends Node\nvar a = $Missing\nfunc _ready():\n\tprint(a)\n",
                            [(2, "syn-get-node-ready-var", "error")]),
    "c20_ok_baseline": ("extends Node\n@export var a: int = 1\n@onready var b = 2\nfunc _ready():\n\tprint(a, b)\n", []),
    "c21_lambda_capture": ("extends Node\nfunc _ready():\n\tvar n := 0\n\tvar f := func(): n += 1\n\tf.call()\n"
                           "\tprint(n)\n", [(4, "syn-lambda-capture-reassign", "warning")]),
    "c22_tween_new": ('extends Node\nfunc _ready():\n\tvar t = Tween.new()\n\tt.interpolate_property(self,"x",0,1,1)\n',
                      [(3, "syn-tween-new", "error"), (4, "syn-tween-interpolate", "error")]),
    "c23_shadow_dot_super": ("extends Node\nfunc _ready():\n\t._ready()\n", [(3, "syn-dot-super", "warning")]),
    "c24_typedarray": ('extends Node\nvar a: Array[int] = [1, "x"]\n', []),
    "c25_deg2rad": ("extends Node\nfunc _ready():\n\tprint(deg2rad(90))\n", [(3, "fn-deg2rad", "error")]),
    "c26_empty": ("extends Node\nfunc _ready():\n\tvar a = []\n\tprint(a.empty())\n", [(4, "syn-empty-call", "error")]),
    "c27_hallucinated": ("extends Node\nfunc _ready():\n\tself.get_player_position()\n\tvar v = Vector2(1,1)\n"
                         "\tv.length_squared_fast()\n", []),
    "c28_tabspace": ("extends Node\nfunc _ready():\n\tvar a = 1\n        print(a)\n", [(4, "lint.indent-mixed", "error")]),
    "c29_int_div": ("extends Node\nfunc _ready():\n\tvar a: int = 5 / 2\n\tvar b: float = 5 / 2\n\tprint(a,b)\n", []),
    "c30_preload_dyn": ('extends Node\nfunc _ready():\n\tvar p = "res://x.tscn"\n\tvar s = preload(p)\n', []),
    "c31_assign_ret_void": ("extends Node\nfunc f() -> void:\n\tpass\nfunc _ready():\n\tvar a = f()\n", []),
    "c32_get_tree_input": ('extends Node\nfunc _ready():\n\tInput.is_action_pressed("nope")\n'
                           '\tprint(Input.is_action_pressed("nope"))\n',
                           [(3, "lint.input-action", "error"), (4, "lint.input-action", "error")]),
    "d01_untyped_connect": ('extends Node\nfunc _ready():\n\tvar b = Button.new()\n\tb.connect("pressed", self, "_x")\n'
                            'func _x():\n\tpass\n', [(4, "syn-connect-3arg", "error")]),
    "d02_untyped_move": ("extends Node\nfunc _ready():\n\tvar b = Node2D.new()\n\tb.rect_position = Vector2.ZERO\n",
                         [(4, "prop-rect_position", "error")]),
    "d03_signal_connect_str": ('extends Node\nfunc _ready():\n\tvar b = Button.new()\n\tb.connect("pressed", _x)\n'
                               '\tb.connect("nosuch", _x)\nfunc _x():\n\tpass\n', [(5, "lint.signal-name", "error")]),
}

TSCN: dict[str, tuple[str, list]] = {
    "g3": (
        "[gd_scene load_steps=2 format=2]\n\n"
        '[ext_resource path="res://scenes/ok.gd" type="Script" id=1]\n\n'
        '[node name="Root" type="Spatial"]\n'
        "script = ExtResource( 1 )\n\n"
        '[node name="Body" type="KinematicBody2D" parent="."]\n'
        "rect_position = Vector2( 10, 10 )\n",
        [(1, "tscn-g3-header", "error"), (3, "tscn-ext-path-first", "error"), (3, "tscn-g3-numeric-id", "error"),
         (5, "tscnclass-Spatial", "error"), (6, "tscn-extresource-spaces", "error"),
         (8, "tscnclass-KinematicBody2D", "error"), (9, "tscn-rect-props", "error")]),
    "g4_mixed": (
        "[gd_scene load_steps=2 format=3]\n\n"
        '[ext_resource type="Script" path="res://scenes/ok.gd" id="1"]\n\n'
        '[node name="Root" type="Node2D"]\n'
        "script = ExtResource( 1 )\n\n"
        '[node name="Body" type="Sprite" parent="."]\n'
        "rect_position = Vector2( 10, 10 )\n"
        "nonexistent_prop = 5\n\n"
        '[node name="Sub" type="Node2D" parent="Missing"]\n',
        [(6, "tscn-extresource-spaces", "error"), (8, "tscnclass-Sprite", "error"), (9, "tscn-rect-props", "error")]),
    "g4_ok": (
        "[gd_scene load_steps=2 format=3]\n\n"
        '[ext_resource type="Script" path="res://scenes/ok.gd" id="1"]\n\n'
        '[node name="Root" type="Node2D"]\n'
        'script = ExtResource("1")\n\n'
        '[node name="Body" type="CharacterBody2D" parent="."]\n', []),
    "g4_badscript": (
        "[gd_scene format=3]\n\n"
        '[ext_resource type="Script" path="res://cases/c02_onready.gd" id="1"]\n\n'
        '[node name="Root" type="Node"]\n'
        'script = ExtResource("1")\n', []),
}

GODOT3_PROJECT_GODOT = (
    "; Engine configuration file.\nconfig_version=5\n\n[application]\n\nconfig/name=\"godot3_scripts\"\n"
    'config/features=PackedStringArray("4.7")\n\n[input]\n\njump={\n"deadzone": 0.5,\n"events": []\n}\n')


def expected_godot3() -> set:
    """{(res path, line, rule, severity)} for the whole godot3_scripts fixture (AC-03.2)."""
    exp = set()
    for name, (_text, rows) in CASES.items():
        for line, rule, sev in rows:
            exp.add((f"res://cases/{name}.gd", line, rule, sev))
    for name, (_text, rows) in TSCN.items():
        for line, rule, sev in rows:
            exp.add((f"res://scenes/{name}.tscn", line, rule, sev))
    return exp


def finding_set(r) -> set:
    """Set of (path, line, rule, severity) from findings.jsonl (uncapped, authoritative), info rows excluded."""
    return {(f["path"], f["line"], f["rule"], f["severity"]) for f in r.findings_jsonl() if f["severity"] != "info"}


def lint_findings(r, rule=None) -> list:
    return [f for f in r.findings_jsonl() if f["severity"] != "info" and (rule is None or f["rule"] == rule)]


def fresh(tmp_path, name: str = "lint_base", sub: str = "proj") -> Path:
    return copy_fixture(name, tmp_path / sub)


def lint(project, *args, env=None, cwd=None, timeout=60):
    """run_h("lint", ...) with HARNESS_OUT inside the temp dir so repo trees stay untouched (B3)."""
    e = {"HARNESS_OUT": str(Path(project).parent / "out")}
    e.update(env or {})
    return run_h("lint", "--project", project, *args, env=e, cwd=cwd, timeout=timeout)


STRICT_TOML = '[lint]\nreplay_dirs = ["res://"]\n'

