"""A9 [data] layer: AC-09.1, AC-09.2 and the hook-line contract of spec 3.1 (files read as data, nothing imported).

Red until B9a lands: templates/ and sample/ do not exist yet, so every test fails on a missing path (not a
collection error). The snapshot schema helper (tests/fixtures/a9/snapshot_check.py) gets its own tests here.
"""
import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "templates"
SAMPLE = REPO / "sample"
TPL_SIM = TEMPLATES / "sim_view" / "sim"
TPL_VIEW = TEMPLATES / "sim_view" / "view"
TPL_PROJ = TEMPLATES / "project"

_spec = importlib.util.spec_from_file_location("a9_snapshot_check", REPO / "tests" / "fixtures" / "a9" / "snapshot_check.py")
snapshot_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snapshot_check)


def need(p: Path) -> Path:
    assert p.exists(), f"missing {p.relative_to(REPO)} (A9 builder B9a/B9b has not produced it)"
    return p


def gd_names(d: Path) -> list:
    need(d)
    return sorted(p.name for p in d.glob("*.gd"))


# ------------------------------------------------------------------------------------------ AC-09.1
SIM_FILES = ["sim_thing.gd", "sim_world.gd", "sim_rules.gd", "sim_codec.gd", "sim_snapshot.gd"]
VIEW_FILES = ["thing_view.gd", "sim_view.gd", "sim_host.gd"]


def test_ac_09_1_1_template_sim_files_exist():
    assert gd_names(TPL_SIM) == sorted(SIM_FILES)


def test_ac_09_1_2_template_view_files_exist():
    assert gd_names(TPL_VIEW) == sorted(VIEW_FILES)


def test_ac_09_1_3_sample_sim_core_is_byte_copy_of_template():
    assert gd_names(SAMPLE / "sim" / "core") == gd_names(TPL_SIM)
    for n in gd_names(TPL_SIM):
        assert (SAMPLE / "sim" / "core" / n).read_bytes() == (TPL_SIM / n).read_bytes(), n


def test_ac_09_1_4_sample_view_core_is_byte_copy_of_template():
    assert gd_names(SAMPLE / "view" / "core") == gd_names(TPL_VIEW)
    for n in gd_names(TPL_VIEW):
        assert (SAMPLE / "view" / "core" / n).read_bytes() == (TPL_VIEW / n).read_bytes(), n


def test_ac_09_1_5_scene_manager_is_byte_copy_of_template():
    a = need(SAMPLE / "autoloads" / "scene_manager.gd")
    b = need(TPL_PROJ / "autoloads" / "scene_manager.gd")
    assert a.read_bytes() == b.read_bytes()


# ------------------------------------------------------------------------------------------ AC-09.2
def read_project(p: Path) -> str:
    return need(p / "project.godot").read_text()


PROJECTS = [pytest.param(TPL_PROJ, id="template"), pytest.param(SAMPLE, id="sample")]


def section(text: str, name: str) -> str:
    m = re.search(rf"^\[{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    assert m, f"no [{name}] section"
    return m.group(1)


@pytest.mark.parametrize("proj", PROJECTS)
def test_ac_09_2_1_settings_keys(proj):
    t = read_project(proj)
    for needle in (
        "config_version=5",
        'config/features=PackedStringArray("4.7")',
        "physics/common/physics_ticks_per_second=60",
        "physics/common/physics_jitter_fix=0.0",
        'rendering/renderer/rendering_method="gl_compatibility"',
        'rendering/renderer/rendering_method.mobile="gl_compatibility"',
        'window/stretch/mode="canvas_items"',
    ):
        assert needle in t, needle
    names = ["world", "player", "enemy", "hazard", "pickup", "trigger"]
    for i, n in enumerate(names, 1):
        assert f'2d_physics/layer_{i}="{n}"' in t, f"layer_{i}"


ACTIONS = ["move_left", "move_right", "move_up", "move_down", "jump", "confirm", "cancel", "pause"]


@pytest.mark.parametrize("proj", PROJECTS)
def test_ac_09_2_2_eight_actions_with_key_and_joypad(proj):
    inp = section(read_project(proj), "input")
    blocks = {}
    cur = None
    for line in inp.splitlines():
        m = re.match(r"^(\w+)=\{", line)
        if m:
            cur = m.group(1)
            blocks[cur] = line
        elif cur:
            blocks[cur] += "\n" + line
    for a in ACTIONS:
        assert a in blocks, f"action {a} missing"
        b = blocks[a]
        assert "InputEventKey" in b, f"{a}: no key event"
        assert "physical_keycode" in b, f"{a}: key events must be physical"
        assert "InputEventJoypad" in b, f"{a}: no joypad event"


@pytest.mark.parametrize("proj", PROJECTS)
def test_ac_09_2_3_autoload_exact_order(proj):
    al = section(read_project(proj), "autoload")
    pairs = re.findall(r'^(\w+)="([^"]*)"', al, re.M)
    assert [n for n, _ in pairs] == ["Harness", "Rng", "CommandBus", "Trace", "SceneManager"]
    d = dict(pairs)
    assert d["Harness"] == "*res://addons/harness/harness.gd"
    assert d["Rng"] == "*res://addons/harness/rng.gd"
    assert d["CommandBus"] == "*res://addons/harness/command_bus.gd"
    assert d["Trace"] == "*res://addons/harness/trace.gd"
    assert d["SceneManager"] == "*res://autoloads/scene_manager.gd"


@pytest.mark.parametrize("proj", PROJECTS)
def test_ac_09_2_4_harness_toml(proj):
    d = tomllib.loads(need(proj / "harness.toml").read_text())
    h = d["harness"]
    assert h["tick_rate"] == 60
    assert h["sim_dirs"] == ["res://sim"]
    assert h["test_dir"] == "res://tests"
    assert d["lint"]["replay_dirs"] == ["res://"]  # R-08


def test_ac_09_2_5_no_ui_actions_or_raw_keys_in_sample_scripts():
    need(SAMPLE)
    bad = []
    for p in SAMPLE.rglob("*.gd"):
        rel = p.relative_to(SAMPLE).as_posix()
        if rel.startswith(("addons/", ".godot/", ".harness/", "tests/a9/")):
            continue
        txt = p.read_text()
        for pat in (r'"ui_', r"InputMap\.add_action", r"\bKEY_"):
            if re.search(pat, txt):
                bad.append(f"{rel}: {pat}")
    assert not bad, bad
    assert list(SAMPLE.rglob("*.gd")), "sample has no scripts"


def test_ac_09_2_6_template_project_files():
    for f in ("project.godot", "harness.toml", "autoloads/scene_manager.gd", ".gitignore", "README.md"):
        need(TPL_PROJ / f)
    gi = (TPL_PROJ / ".gitignore").read_text().split()
    for pat in (".godot/", ".harness/", "addons/gdUnit4/", "addons/harness/"):
        assert pat in gi, pat
    assert len((TPL_PROJ / "README.md").read_text().splitlines()) <= 30


def test_ac_09_2_7_readme_lengths():
    assert len(need(TEMPLATES / "sim_view" / "README.md").read_text().splitlines()) <= 40
    assert len(need(SAMPLE / "README.md").read_text().splitlines()) <= 40


def test_ac_09_2_8_sample_scene_manager_surface():
    t = need(SAMPLE / "autoloads" / "scene_manager.gd").read_text()
    for needle in ("signal transition_started", "signal transition_finished", "func goto(", "func set_slot(",
                   "func is_busy(", "func current_path(", "func pending_path(", "func stats("):
        assert needle in t, needle
    assert "change_scene_to" not in t  # P10: slot swapping only


# ------------------------------------------------------------------------------------------ spec 3.1 hook lines
HOOKS = [
    ("sim/tactics/tactics_world.gd", 'var debug_note: String = "" # HOOK-SIM-FIELD'),
    ("sim/tactics/tactics_world.gd", 'var st = SimCodec.int_dict_of(d, "stats", err) # HOOK-STATS-LOAD'),
    ("sim/tactics/tactics_rules.gd", "pass # HOOK-RULES-APPLY"),
    ("sim/tactics/tactics_rules.gd", "var bonus := world.rng.randi_range(0, 1) # HOOK-DAMAGE-RNG"),
    ("sim/core/sim_world.gd", '"version": schema_version(), # HOOK-VERSION'),
    ("view/core/sim_view.gd", "_reconcile() # HOOK-VIEW-RECONCILE"),
    ("game/tactics/tactics_view.gd", "pass # HOOK-VIEW-EVENT"),
    ("autoloads/scene_manager.gd", "_pending = path # HOOK-PENDING"),
    ("game/platformer/player.gd", 'var axis := Input.get_axis("move_left", "move_right") # HOOK-INPUT-AXIS'),
    ("sim/platformer/player_motor.gd", "return roundi(tuning.coyote_time * tick_rate) # HOOK-COYOTE"),
]


@pytest.mark.parametrize("rel,line", HOOKS, ids=[h[1].split("# ")[-1] for h in HOOKS])
def test_hook_line_present_exactly_once(rel, line):
    """The FAULT-A9-* replace ops need each hook line once (else the entry is BROKEN)."""
    t = need(SAMPLE / rel).read_text()
    assert t.count(line) == 1, f"{rel}: hook line {line!r} occurs {t.count(line)}x"


def test_hook_lines_in_templates_too():
    for rel, marker in (("sim/sim_world.gd", '"version": schema_version(), # HOOK-VERSION'),
                        ("view/sim_view.gd", "_reconcile() # HOOK-VIEW-RECONCILE"),
                        ("autoloads/scene_manager.gd", "_pending = path # HOOK-PENDING")):
        base = TPL_PROJ if rel.startswith("autoloads") else TEMPLATES / "sim_view"
        assert marker in need(base / rel).read_text(), rel


# ------------------------------------------------------------------------------------------ schema helper self-test
def _good():
    return {"schema": "sample.tactics", "version": 1, "tick": 0, "next_id": 3,
            "rng": {"seed": "7", "state": "-123456789012345678"},
            "things": {"t1": {"id": 1, "kind": "unit"}, "t2": {"id": 2, "kind": "unit"}}, "data": {}}


def test_schema_helper_accepts_good_snapshot():
    assert snapshot_check.validate(_good()) == []


@pytest.mark.parametrize("mut,frag", [
    (lambda d: d.pop("version"), "version"),
    (lambda d: d.__setitem__("tick", 1.5), "tick"),
    (lambda d: d["rng"].__setitem__("state", 5), "state"),
    (lambda d: d["rng"].__setitem__("state", "1.0"), "state"),
    (lambda d: d["things"].__setitem__("x1", {"id": 1, "kind": "u"}), "x1"),
    (lambda d: d["things"]["t1"].__setitem__("id", 2), "t1"),
    (lambda d: d.__setitem__("next_id", 2), "t2"),
    (lambda d: d.__setitem__("extra", 1), "extra"),
    (lambda d: d.__setitem__("schema", "Bad Name"), "schema"),
])
def test_schema_helper_rejects_bad_snapshots(mut, frag):
    d = _good()
    mut(d)
    errs = snapshot_check.validate(d)
    assert errs and any(frag in e for e in errs), errs
