"""A9 [contract] tests (spec 09_sim_view_sample.md section 4: AC-09.3 .. AC-09.7, 09.19, 09.20, 09.22).

Black-box: every verb runs on a temp copy of `@sample` (B3, R-51) or of templates/; every result goes through
assert_contract. Red until B9a/B9b land: copy_fixture("@sample") raises HelperError (no sample/) or the verbs fail.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from helpers.h import REPO, assert_contract, copy_fixture, run_h

pytestmark = pytest.mark.godot

SAMPLE = REPO / "sample"
TEMPLATES = REPO / "templates"


def res_scenes(proj: Path) -> list:
    out = []
    for p in sorted(proj.rglob("*.tscn")):
        rel = p.relative_to(proj).as_posix()
        if rel.startswith(("addons/", ".godot/", ".harness/")):
            continue
        out.append("res://" + rel)
    return out


def errors(r) -> list:
    return [f for f in r.all_findings() if f["severity"] == "error"]


def warnings(r) -> list:
    return [f for f in r.all_findings() if f["severity"] == "warning"]


# ---------------------------------------------------------------------------------------------- AC-09.3
def test_ac_09_3_1_check_passes_on_fresh_copy_within_60s(sample_fresh):
    r = assert_contract(run_h("check", "--project", sample_fresh, timeout=300))
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "check", str(r)
    assert r.stats["import"].startswith("ran") or r.stats["import"] == "fresh"
    assert not errors(r)
    assert r.wall <= 60, f"h check took {r.wall:.1f}s"


def test_ac_09_3_2_lint_is_clean_with_zero_findings(sp):
    r = assert_contract(run_h("lint", "--project", sp, timeout=120))
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    assert r.all_findings() == [], r.all_findings()  # no warnings either (replay_dirs = res://, physics-mode everywhere)


# ---------------------------------------------------------------------------------------------- AC-09.4
def spec_files(proj: Path) -> list:
    specs = sorted((proj / "specs").glob("*.scene.json"))
    mains = [s for s in specs if s.name == "main.scene.json"]
    return [s for s in specs if s not in mains] + mains  # main last


def test_ac_09_4_1_every_scene_has_exactly_one_spec(sp):
    scenes = res_scenes(sp)
    assert scenes, "sample has no scenes"
    saves = []
    for s in sorted((sp / "specs").glob("*.scene.json")):
        saves.append(json.loads(s.read_text())["save"])
    assert sorted(saves) == sorted(scenes)
    assert len(set(saves)) == len(saves)
    stems = {Path(s).stem for s in scenes}
    for want in ("main", "tactics", "unit_view", "platformer_game", "player", "level_1", "level_2", "feel_arena"):
        assert want in stems, want


def test_ac_09_4_2_scene_gen_force_reproduces_committed_digests(sp):
    scenes = res_scenes(sp)

    def digests() -> dict:
        out = {}
        for sc in scenes:
            r = assert_contract(run_h("digest", sc, "--json", "--project", sp, timeout=120))
            assert r.rc == 0, str(r)
            out[sc] = json.loads(r.artifact("digest.json").read_text())
        return out

    before = digests()
    specs = spec_files(sp)
    assert specs
    r = assert_contract(run_h("scene-gen", "--project", sp, *specs, "--force", timeout=300))
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    assert r.checks and all(c[0] == "OK" for c in r.checks), r.checks
    after = digests()
    for sc in scenes:
        assert after[sc] == before[sc], f"{sc}: regenerated digest differs from the committed scene"


# ---------------------------------------------------------------------------------------------- AC-09.5
def test_ac_09_5_1_player_digest_fits_without_more(sp):
    r = assert_contract(run_h("digest", "scenes/platformer/player.tscn", "--project", sp, timeout=120))
    assert r.rc == 0, str(r)
    assert "more" not in r.stats, "player.tscn digest needed a `more:` fold (> 40 lines)"
    assert len(r.lines) <= 40


def test_ac_09_5_2_project_summary_lists_autoloads_actions_layers(sp):
    r = assert_contract(run_h("digest", "--project-summary", "--project", sp, timeout=120))
    assert r.rc == 0, str(r)
    autoloads = r.stat_all("autoload")
    assert len(autoloads) == 5, autoloads
    assert [a.split()[0] for a in autoloads] == ["Harness", "Rng", "CommandBus", "Trace", "SceneManager"]
    actions = r.stat_all("action")
    assert len(actions) == 8, actions
    assert sorted(a.split()[0] for a in actions) == sorted(
        ["move_left", "move_right", "move_up", "move_down", "jump", "confirm", "cancel", "pause"])
    assert "1=world 2=player 3=enemy 4=hazard 5=pickup 6=trigger" in r.stat_all("layers-2d_physics")[0]


# ---------------------------------------------------------------------------------------------- AC-09.6
def test_ac_09_6_h_test_runs_the_samples_own_suites(sample_fresh):
    r = assert_contract(run_h("test", "--project", sample_fresh, timeout=600))
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    m = re.match(r"(\d+) total, (\d+) passed, (\d+) failed, (\d+) errors, (\d+) skipped, (\d+) orphans", r.stats["tests"])
    assert m, r.stats.get("tests")
    total, passed, failed, errs, skipped, orphans = map(int, m.groups())
    assert total >= 30 and failed == 0 and errs == 0 and orphans == 0, r.stats["tests"]
    tj = json.loads(r.artifact("tests.json").read_text())
    suites = {t["suite"] for t in tj["tests"]}
    sim = {s for s in suites if s.startswith("res://tests/sim/")}
    scenes = {s for s in suites if s.startswith("res://tests/scenes/")}
    assert len(sim) >= 4, sorted(suites)
    assert len(scenes) >= 3, sorted(suites)
    assert r.wall <= 90, f"h test took {r.wall:.1f}s"


# ---------------------------------------------------------------------------------------------- AC-09.7
REQUIRED = {
    "platformer/run.json": ("platformer_game", 1, 120, [
        ("path", "player.velocity.x", "lt", 219, {"tick": 32}),
        ("path", "player.velocity.x", "ge", 219.9, {"tick": 40}),
        ("path", "player.dx", "gt", 100, {"tick": 90})]),
    "platformer/jump.json": ("platformer_game", 1, 150, [
        ("path", "player.apex_px", "between", [46, 50], {"at_end": True}),
        ("path", "player.jumps", "eq", 1, {"at_end": True})]),
    "platformer/tap.json": ("platformer_game", 1, 150, [
        ("path", "player.apex_px", "lt", 30, {"at_end": True}),
        ("path", "player.jumps", "eq", 1, None)]),
    "platformer/level_complete.json": ("platformer_game", 1, 900, [
        ("path", "game.level", "eq", "level_2", {"at_end": True}),
        ("path", "game.sm.dropped", "eq", 0, None)]),
    "flow/fade_request.json": ("platformer_game", 1, 120, [
        ("path", "game.level", "eq", "level_2", {"at_end": True}),
        ("path", "game.sm.completed", "eq", 2, {"at_end": True})]),
    "tactics/moves.json": ("tactics", 7, 6, [
        ("path", "world.things.t1.cell", "eq", [2, 1], {"at_end": True}),
        ("metric", "events.rejected", "eq", 2, None),
        ("metric", "events.unit_moved", "eq", 1, None)]),
    "tactics/autoplay.json": ("tactics", 42, 3, [
        ("path", "world.tick", "eq", 1000, {"at_end": True}),
        ("metric", "events.snapshot_roundtrip", "eq", 1, None)]),
}


def _val_eq(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-9
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_val_eq(x, y) for x, y in zip(a, b))
    return a == b


def has_assert(sc: dict, kind: str, name: str, op: str, value, when) -> bool:
    for a in sc.get("asserts", []):
        if a.get(kind) != name or a.get("op") != op or not _val_eq(a.get("value"), value):
            continue
        if when is None or all(a.get(k) == v for k, v in when.items()):
            return True
    return False


@pytest.mark.slow
def test_ac_09_7_1_all_scenarios_pass_twice(sp):
    r = assert_contract(run_h("run", "res://scenarios/", "--twice", "--project", sp, timeout=300))
    assert r.rc == 0, str(r)
    m = re.match(r"^PASS run (\d+)/(\d+) scenarios passed", r.stdout)
    assert m, r.stdout.splitlines()[0]
    k, n = int(m.group(1)), int(m.group(2))
    assert k == n and n >= 7, (k, n)
    names = " ".join(c[1] for c in r.checks)
    for rel in REQUIRED:
        assert f"res://scenarios/{rel}" in names, f"{rel} not run"
    assert all(c[0] == "OK" for c in r.checks), r.checks
    assert r.wall <= 90, f"{r.wall:.1f}s"


@pytest.mark.slow
@pytest.mark.parametrize("rel", sorted(REQUIRED))
def test_ac_09_7_2_required_asserts_present_and_passing(sp, rel):
    scene, seed, ticks, asserts = REQUIRED[rel]
    sc = json.loads((sp / "scenarios" / rel).read_text())
    assert sc["scene"].endswith(f"/{scene}.tscn"), sc["scene"]
    assert sc["seed"] == seed and sc["ticks"] == ticks, (sc["seed"], sc["ticks"])
    for kind, name, op, value, when in asserts:
        assert has_assert(sc, kind, name, op, value, when), f"{rel}: required assert {name} {op} {value} {when} missing"
    r = assert_contract(run_h("run", f"res://scenarios/{rel}", "--project", sp, timeout=180))
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    res = json.loads(r.artifact("asserts.json").read_text())
    assert len(res) >= len(asserts)
    assert all(a["pass"] for a in res), [a for a in res if not a["pass"]]
    if rel == "tactics/autoplay.json":
        assert r.stats["golden"].startswith("match"), r.stats["golden"]


@pytest.mark.slow
def test_ac_09_7_3_golden_file_is_committed_next_to_autoplay(sp):
    g = sp / "scenarios" / "tactics" / "autoplay.golden.json"
    assert g.is_file()
    d = json.loads(g.read_text())
    assert d["schema"] == "harness.golden/1"


# ---------------------------------------------------------------------------------------------- AC-09.19
def test_ac_09_19_template_smoke(tmp_path):
    for need in (TEMPLATES / "project", TEMPLATES / "sim_view" / "sim", TEMPLATES / "sim_view" / "view"):
        assert need.is_dir(), f"missing {need.relative_to(REPO)}"
    dest = tmp_path / "proj"
    shutil.copytree(TEMPLATES / "project", dest, ignore=shutil.ignore_patterns(".godot", ".harness"))
    shutil.copytree(TEMPLATES / "sim_view" / "sim", dest / "sim" / "core")
    shutil.copytree(TEMPLATES / "sim_view" / "view", dest / "view" / "core")
    env = {"HARNESS_OUT": tmp_path / "out"}
    r = run_h("sync", "--project", dest, env=env, timeout=300)
    assert r.rc == 0, str(r)
    r = assert_contract(run_h("check", "--project", dest, timeout=300))
    assert r.rc == 0 and r.verdict == "PASS", str(r)
    r = assert_contract(run_h("lint", "--project", dest, timeout=120))
    assert r.rc == 0, str(r)
    bad = [f for f in r.all_findings() if f["rule"] == "lint.sim-node" or f["rule"].startswith("lint.det-")]
    assert bad == [], bad


# ---------------------------------------------------------------------------------------------- AC-09.20
@pytest.mark.slow
def test_ac_09_20_selftest_area_a9():
    r = run_h("selftest", "--area", "A9", timeout=700)
    assert_contract(r, nodir=False)
    assert r.rc == 0, str(r)
    m = re.search(r"(\d+) total, (\d+) caught, (\d+) missed \(must (\d+), nice (\d+)\), (\d+) slow, (\d+) overflow, (\d+) broken",
                  r.stats["faults"])
    assert m, r.stats.get("faults")
    total, caught, missed, must_missed, _nice, slow, overflow, broken = map(int, m.groups())
    assert total >= 12 and must_missed == 0 and slow == 0 and overflow == 0 and broken == 0, r.stats["faults"]
    c = re.search(r"(\d+) total, (\d+) pass, (\d+) false-positive", r.stats["clean"])
    assert c and int(c.group(1)) >= 3 and int(c.group(2)) == int(c.group(1)) and int(c.group(3)) == 0, r.stats["clean"]
    assert r.wall <= 600


# ---------------------------------------------------------------------------------------------- AC-09.22
def _baselines(proj: Path, stem: str) -> list:
    d = proj / "baselines" / "scenes" / stem
    return sorted(p for p in d.glob("*-t60.json") if ".proposed." not in p.name)


@pytest.mark.parametrize("stem", ["tactics", "platformer_game"])
def test_ac_09_22_1_baselines_are_provisional_approved(stem):
    metas = _baselines(SAMPLE, stem)
    assert metas, f"no tick-60 baseline for {stem} under sample/baselines/scenes/{stem}/"
    for m in metas:
        d = json.loads(m.read_text())
        assert d["status"] == "approved"
        assert d["approved_by"] == "provisional-default"
        assert d.get("approved_at") is None
        assert m.with_suffix(".png").is_file()
        assert not list(m.parent.glob("*.proposed.*")), "proposals must not be committed"


@pytest.mark.xvfb
@pytest.mark.parametrize("stem", ["tactics", "platformer_game"])
def test_ac_09_22_2_shot_compare_warns_only_unapproved(sp, stem):
    scene = f"res://scenes/{'tactics' if stem == 'tactics' else 'platformer'}/{stem}.tscn"
    r = assert_contract(run_h("shot", scene, "--compare", "--project", sp, timeout=300))
    assert r.rc == 5 and r.verdict == "WARN", str(r)
    assert errors(r) == []
    ws = warnings(r)
    assert ws, "provisional baseline must warn"
    assert {w["rule"] for w in ws} == {"shot.baseline-unapproved"}, ws


@pytest.mark.xvfb
def test_ac_09_22_3_trace_measures_five_targets_with_only_unapproved_warning(sp):
    r = assert_contract(run_h("trace", "res://feel/player.feel.json", "--project", sp, timeout=600))
    assert r.rc == 5 and r.verdict == "WARN", str(r)
    assert errors(r) == []
    assert {w["rule"] for w in warnings(r)} == {"feel.unapproved"}, warnings(r)
    ok = {c[1].split()[0] for c in r.checks if c[0] == "OK"}
    for metric in ("jump.apex_px", "jump.time_to_apex", "run.accel_time", "jump.coyote_window", "jump.buffer_window"):
        assert metric in ok, f"{metric} has no OK check line; got {sorted(ok)}"
    assert not [c for c in r.checks if c[0] == "FAIL"]


def test_ac_09_22_4_feel_files_are_outside_scenarios_dir(sp):
    assert (sp / "feel" / "player.feel.json").is_file()
    for n in ("run", "jump", "tap", "coyote", "buffer", "camera"):
        assert (sp / "feel" / f"{n}.json").is_file(), n
    assert (sp / "tuning" / "feel_targets.tres").is_file()
    t = (sp / "tuning" / "feel_targets.tres").read_text()
    assert t.count('approved_by = "provisional-default"') >= 5
