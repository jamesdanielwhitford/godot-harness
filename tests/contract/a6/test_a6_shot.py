"""A6 contract: `h shot` capture modes (AC-06.1-7, 13-19). Layer: contract. Needs Godot + Xvfb."""
import os
import re
import statistics
import time
from pathlib import Path

import pytest

from a6_util import (MAIN, HUD, odiff_px, path_without, pixel, png_size, shot, shot_png, sha256, x_locks)
from helpers.h import apply_fault, assert_contract, live_processes_mentioning, run_h

pytestmark = [pytest.mark.godot, pytest.mark.xvfb]


# ---- AC-06.1 -----------------------------------------------------------------------------------------------
def test_ac_06_1_single_capture_contract(sm_cold, tmp_path):
    r = shot(sm_cold, tmp_path, MAIN, "--tick", "30")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "shot", r
    assert re.match(r"^1 shot captured", r.reason), r.reason
    keys = [k for k, _ in r.stat_items][:4]
    assert keys == ["project", "import", "target", "env"], r.stat_items
    assert r.stats["env"].startswith("gl_compatibility"), r.stats["env"]
    st, name, detail = r.check("main-t30")
    assert st == "OK" and re.match(r"^640x360 \S+main-t30\.png$", detail), r.checks
    png = shot_png(r, "main-t30")
    assert png.is_file() and png_size(png) == (640, 360)


# ---- AC-06.2 -----------------------------------------------------------------------------------------------
def test_ac_06_2_two_captures_are_byte_identical(sm, tmp_path):
    a = shot(sm, tmp_path / "a", MAIN, "--tick", "30")
    b = shot(sm, tmp_path / "b", MAIN, "--tick", "30")
    assert_contract(a), assert_contract(b)
    assert a.rc == 0 and b.rc == 0, (a, b)
    assert sha256(shot_png(a, "main-t30")) == sha256(shot_png(b, "main-t30"))


def test_ac_06_2_twice_reports_identical(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--twice")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", r
    assert r.stats.get("twice", "").startswith("identical"), r.stat_items
    assert shot_png(r, "main-t30").is_file()


# ---- AC-06.3 -----------------------------------------------------------------------------------------------
def test_ac_06_3_tick_semantics(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30,1")
    assert_contract(r)
    assert r.rc == 0, r
    p30, p1 = shot_png(r, "main-t30"), shot_png(r, "main-t1")
    assert pixel(p30, 50, 120) == (255, 165, 0)
    assert pixel(p30, 49, 120) == (25, 51, 102)      # background Color(0.1, 0.2, 0.4)
    assert pixel(p1, 21, 120) == (255, 165, 0)
    assert pixel(p1, 20, 120) == (25, 51, 102)


# ---- AC-06.4 -----------------------------------------------------------------------------------------------
@pytest.mark.slow
def test_ac_06_4_capture_wall_time_budget(sm, tmp_path):
    walls = []
    for i in range(3):
        r = shot(sm, tmp_path / f"r{i}", MAIN, "--tick", "30")
        assert r.rc == 0, r
        walls.append(r.wall)
    assert statistics.median(walls) <= 3.0, walls


# ---- AC-06.5 -----------------------------------------------------------------------------------------------
def test_ac_06_5_no_image_bytes_and_pngs_only_in_run_dir(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30")
    assert_contract(r)                                      # includes the 240-char line limit
    assert "\x89PNG" not in r.stdout and "PNG" not in r.stdout.replace(".png", "")
    assert not re.search(r"[A-Za-z0-9+/]{200,}={0,2}", r.stdout), "base64-looking blob in stdout"
    stray = [p for p in sm.rglob("*.png") if "baselines" not in p.relative_to(sm).parts]
    assert stray == [], f"PNGs written into the project outside baselines/: {stray}"
    assert shot_png(r, "main-t30").is_file()


# ---- AC-06.6 / 06.7 ------------------------------------------------------------------------------------------
def test_ac_06_6_headless_flag_is_rc4(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--headless")
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r
    assert re.match(r"^ERROR shot --headless cannot render images", r.lines[0]), r.lines[0]
    assert r.invocations() == [], "no Godot invocation may be recorded"


def test_ac_06_7_missing_xvfb_run_is_rc4(sm, tmp_path):
    bindir = path_without("xvfb-run", tmp_path / "pathbin")
    assert not (Path(bindir) / "xvfb-run").exists()
    r = shot(sm, tmp_path, MAIN, "--tick", "30", env={"PATH": bindir})
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r
    assert "xvfb" in r.stdout.lower(), r


# ---- usage errors (rc 2) -------------------------------------------------------------------------------------
@pytest.mark.parametrize("args", [
    ["--tick", "0"], ["--tick", "36001"], ["--tick", "1,2,3,4,5,6,7,8,9"], ["--name", "Bad Name"],
    ["--size", "10x10"], ["--size", "5000x100"], ["--hide-layer", "21"], ["--hide-layer", "0"],
    ["--crop", "0,0,64,32", "--node", "%Score"],
], ids=lambda a: " ".join(a))
def test_ac_06_usage_rc2_for_bad_capture_flags(sm, tmp_path, args):
    r = shot(sm, tmp_path, MAIN, *args)
    assert_contract(r)
    assert r.rc == 2 and r.verdict == "ERROR", r


def test_ac_06_usage_rc2_target_outside_project(sm, tmp_path):
    other = tmp_path / "elsewhere.tscn"
    other.write_text("[gd_scene format=3]\n\n[node name=\"X\" type=\"Node\"]\n")
    r = shot(sm, tmp_path, str(other))
    assert_contract(r)
    assert r.rc == 2, r


def test_ac_06_usage_rc2_seed_with_compare_and_layout_flags(sm, tmp_path):
    for extra in (["--compare", "--seed", "3"], ["--layout", "--tick", "5"], ["--layout", "--compare"],
                  ["--layout", "--size", "640x360"]):
        r = shot(sm, tmp_path, HUD, *extra)
        assert_contract(r)
        assert r.rc == 2, (extra, r)


# ---- AC-06.13 -----------------------------------------------------------------------------------------------
def test_ac_06_13_node_crop(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--node", "%Score", "--name", "score")
    assert_contract(r)
    assert r.rc == 0, r
    assert png_size(shot_png(r, "score")) == (101, 23)
    assert re.match(r"^101x23 ", r.check("score")[2]), r.checks


def test_ac_06_13_pixel_crop(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--crop", "0,0,64,32", "--name", "c")
    assert_contract(r)
    assert r.rc == 0, r
    assert png_size(shot_png(r, "c")) == (64, 32)


def test_ac_06_13_node_not_found(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--node", "%Nope")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="shot.node-not-found", severity="error"), r


def test_ac_06_13_crop_outside(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--crop", "900,900,10,10")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="shot.crop-outside", severity="error"), r


def test_ac_06_13_hide_unknown_node_is_node_not_found(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--hide", "%Nope")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="shot.node-not-found"), r


# ---- AC-06.14 -----------------------------------------------------------------------------------------------
def test_ac_06_14_hide_and_hide_layer_change_the_image(sm, tmp_path):
    plain = shot(sm, tmp_path / "p1", MAIN, "--tick", "30", "--name", "plain")
    hid = shot(sm, tmp_path / "h", MAIN, "--tick", "30", "--name", "hid", "--hide", "%HUD")
    lay = shot(sm, tmp_path / "l", MAIN, "--tick", "30", "--name", "lay", "--hide-layer", "1")
    plain2 = shot(sm, tmp_path / "p2", MAIN, "--tick", "30", "--name", "plain")
    for r in (plain, hid, lay, plain2):
        assert_contract(r)
        assert r.rc == 0, r
    base = shot_png(plain, "plain")
    assert odiff_px(base, shot_png(hid, "hid"), tmp_path / "d1.png") > 0
    assert odiff_px(base, shot_png(lay, "lay"), tmp_path / "d2.png") > 0
    assert sha256(base) == sha256(shot_png(plain2, "plain")), "hiding must not leak into a later plain capture"


# ---- AC-06.15 -----------------------------------------------------------------------------------------------
def test_ac_06_15_size_option(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--size", "1280x720", "--name", "big")
    assert_contract(r)
    assert r.rc == 0, r
    assert png_size(shot_png(r, "big")) == (1280, 720)
    assert re.match(r"^1280x720 ", r.check("big")[2])


def test_ac_06_15_size_reported_equals_file(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--size", "800x1280", "--name", "tall")
    assert_contract(r)
    assert r.rc == 0, r
    w, h = png_size(shot_png(r, "tall"))
    assert r.check("tall")[2].startswith(f"{w}x{h} "), (r.checks, (w, h))


def test_ac_06_multi_tick_names(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "10,30")
    assert_contract(r)
    assert r.rc == 0 and r.reason.startswith("2 shots captured"), r
    assert shot_png(r, "main-t10").is_file() and shot_png(r, "main-t30").is_file()
    r2 = shot(sm, tmp_path / "n", MAIN, "--tick", "10,30", "--name", "x")
    assert r2.rc == 0 and shot_png(r2, "x-t10").is_file() and shot_png(r2, "x-t30").is_file(), r2


# ---- AC-06.16 -----------------------------------------------------------------------------------------------
def test_ac_06_16_unseeded_particles_are_stable(sm, tmp_path):
    apply_fault("CLEAN-A6-02", sm)
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--twice")
    assert_contract(r)
    assert r.rc == 0 and r.matches(r"^twice: identical"), r


def test_ac_06_16_wall_clock_visual_is_unstable(sm, tmp_path):
    apply_fault("FAULT-A6-02", sm)
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--twice")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="shot.unstable", severity="error"), r


# ---- AC-06.17 -----------------------------------------------------------------------------------------------
def test_ac_06_17_movie_frames(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--movie", "--tick", "30")
    assert_contract(r)
    assert r.rc == 0, r
    m = re.match(r"^(30|31) frames ", r.stats.get("movie", ""))
    assert m, r.stat_items
    frames = sorted(r.artifact("movie").glob("frame*.png"))
    assert len(frames) == int(m.group(1)), (len(frames), r.stats["movie"])


# ---- AC-06.18 / 06.19 ---------------------------------------------------------------------------------------
def test_ac_06_18_script_error_in_ready_fails_though_png_exists(sm, tmp_path):
    apply_fault("FAULT-A6-09", sm)
    r = shot(sm, tmp_path, MAIN)
    assert_contract(r)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert r.has_finding(rule="godot.script-error", severity="error"), r
    assert shot_png(r, "main-t1").is_file(), "the PNG is still written; the verdict must not depend on it"


def test_ac_06_19_hang_under_xvfb_is_killed_and_cleaned(sm, tmp_path):
    apply_fault("FAULT-A6-10", sm)
    locks_before = x_locks()
    r = shot(sm, tmp_path, MAIN, "--tick", "30")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="harness.hang", severity="error"), r
    assert r.wall <= 12, f"hang with shot=5 took {r.wall:.1f}s"
    time.sleep(0.5)
    assert live_processes_mentioning(str(sm)) == [], "Godot / Xvfb survived the kill"
    for lock, pid in x_locks().items():
        if lock in locks_before:
            continue
        alive = pid is not None and Path(f"/proc/{pid}").exists()
        assert alive, f"stale X lock left behind: {lock} (pid {pid})"


# ---- tooling: odiff presence is a doctor concern, but compare/twice need it ------------------------------------
def test_ac_06_odiff_missing_is_rc4_with_twice(sm, tmp_path):
    r = shot(sm, tmp_path, MAIN, "--tick", "30", "--twice", env={"HARNESS_CACHE": str(tmp_path / "no-cache")})
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r
