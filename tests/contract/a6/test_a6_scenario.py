"""A6 contract: scenario mode of `h shot` (AC-06.25, after B5) and `h selftest --area A6` (AC-06.26)."""
import re

import pytest

from a6_util import png_size, sha256, shot, shot_png
from helpers.h import assert_contract, run_h

JUMP = "res://scenarios/jump.json"


@pytest.mark.godot
@pytest.mark.xvfb
def test_ac_06_25_scenario_two_ticks(mkproj, tmp_path):
    p = mkproj("scenario_min")
    r = shot(p, tmp_path, JUMP, "--tick", "40,90")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", r
    for name in ("jump-t40", "jump-t90"):
        assert r.check(name) and r.check(name)[0] == "OK", r.checks
        assert shot_png(r, name).is_file() and png_size(shot_png(r, name))[0] > 0
    kinds = [i["kind"] for i in r.invocations()]
    assert "shot" in kinds, kinds
    shot_inv = [i for i in r.invocations() if i["kind"] == "shot"][0]
    assert any("xvfb-run" in a for a in shot_inv["argv"]), shot_inv["argv"]


@pytest.mark.godot
@pytest.mark.xvfb
def test_ac_06_25_scenario_shots_are_deterministic(mkproj, tmp_path):
    p = mkproj("scenario_min")
    a = shot(p, tmp_path / "a", JUMP, "--tick", "40,90")
    b = shot(p, tmp_path / "b", JUMP, "--tick", "40,90")
    assert a.rc == 0 and b.rc == 0, (a, b)
    for name in ("jump-t40", "jump-t90"):
        assert sha256(shot_png(a, name)) == sha256(shot_png(b, name)), name


@pytest.mark.godot
def test_ac_06_25_tick_beyond_scenario_length_is_usage_error(mkproj, tmp_path):
    p = mkproj("scenario_min")
    r = shot(p, tmp_path, JUMP, "--tick", "999")
    assert_contract(r)
    assert r.rc == 2 and r.verdict == "ERROR", r


@pytest.mark.godot
def test_ac_06_25_seed_flag_is_rejected_in_scenario_mode(mkproj, tmp_path):
    p = mkproj("scenario_min")
    r = shot(p, tmp_path, JUMP, "--tick", "40", "--seed", "3")
    assert_contract(r)
    assert r.rc == 2, r


@pytest.mark.godot
@pytest.mark.xvfb
def test_ac_06_25_scenario_default_tick_is_scenario_ticks(mkproj, tmp_path):
    p = mkproj("scenario_min")
    r = shot(p, tmp_path, JUMP)
    assert_contract(r)
    assert r.rc == 0, r
    assert r.check("jump-t120") and r.check("jump-t120")[0] == "OK", r.checks    # scenario `ticks` = 120


# ---- AC-06.26 -----------------------------------------------------------------------------------------------
@pytest.mark.godot
@pytest.mark.xvfb
@pytest.mark.slow
def test_ac_06_26_selftest_area_a6(tmp_path):
    r = run_h("selftest", "--area", "A6", env={"HARNESS_OUT": str(tmp_path / "out")}, timeout=400)
    assert_contract(r)
    assert r.rc in (0, 5), r                      # 5 only when a `nice` fault is missed
    assert re.search(r"^faults: 12 total, \d+ caught, \d+ missed \(must 0, nice \d+\)", r.stdout, re.M), r.stdout
    assert re.search(r"^clean: 3 total, 3 pass, 0 false-positive", r.stdout, re.M), r.stdout
    assert r.wall <= 180, f"selftest A6 took {r.wall:.0f}s"
