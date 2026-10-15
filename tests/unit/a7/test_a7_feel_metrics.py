"""A7 unit layer: harness.feel on synthetic CSVs (spec 07_feel.md AC-07.1 .. AC-07.8). Owner: T7.

Calls go through feel_adapt (signatures are not fixed by the spec). These tests are red until B7 step 1 lands.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

import feel_adapt as fa


def _rewrite(path: Path, edit) -> None:
    """Apply edit(rows: list[dict]) to the CSV at path in place."""
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        rows = list(rd)
    edit(rows)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def ramp(tmp_path):
    return fa.csv_copy("run_ramp", tmp_path)


@pytest.fixture
def arc(tmp_path):
    return fa.csv_copy("jump_arc", tmp_path)


@pytest.fixture
def cam(tmp_path):
    return fa.csv_copy("camera_step", tmp_path)


# ---- AC-07.1 -----------------------------------------------------------------------------------------------
def test_ac_07_1_run_ramp_max_speed_accel_decel(ramp):
    t = fa.read(ramp)
    ms = fa.measure(t, "run.max_speed", action="right")
    assert not ms.undefined and ms.value == pytest.approx(220.0)
    ac = fa.measure(t, "run.accel_time", action="right")
    assert ac.value == 6
    assert ac.seconds == pytest.approx(0.1, abs=1e-6)
    dc = fa.measure(t, "run.decel_time", action="right")
    assert dc.value == 6


def test_ac_07_1_accel_time_frac_param(ramp):
    t = fa.read(ramp)
    assert fa.measure(t, "run.accel_time", action="right", frac=0.5).value == 3


def test_ac_07_1_instant_velocity_measures_one_tick_never_zero(ramp):
    def instant(rows):
        for r in rows:
            k = int(r["tick"])
            if 3 <= k < 20:
                r["player.velocity.x"] = "220.000000"
    _rewrite(ramp, instant)
    t = fa.read(ramp)
    assert fa.measure(t, "run.accel_time", action="right").value == 1


# ---- AC-07.2 -----------------------------------------------------------------------------------------------
def test_ac_07_2_jump_arc_metrics(arc):
    t = fa.read(arc)
    want = {"jump.takeoff_speed": 600, "jump.apex_px": 30, "jump.time_to_apex": 5, "jump.fall_time": 5,
            "jump.air_time": 10, "jump.fall_rise_ratio": 1.0}
    for name, v in want.items():
        m = fa.measure(t, name, action="jump")
        assert not m.undefined, f"{name} undefined: {m.reason}"
        assert m.value == pytest.approx(v), name


def test_ac_07_2_apex_is_reported_up_positive(arc):
    m = fa.measure(fa.read(arc), "jump.apex_px", action="jump")
    assert m.value > 0


def test_ac_07_2_no_takeoff_is_undefined_with_reason(arc):
    def flat(rows):
        for r in rows:
            r["player.velocity.y"] = "0.000000"
    _rewrite(arc, flat)
    m = fa.measure(fa.read(arc), "jump.takeoff_speed", action="jump")
    assert m.undefined
    assert "no takeoff within 3 ticks of press" in m.reason


# ---- AC-07.3 press / release ticks come from in.* columns exactly per 2.4 ----------------------------------
def test_ac_07_3_press_tick_is_first_row_with_rising_in_column(ramp):
    # press at row 3: accel counts steps 3..8 = 6. A press taken as row 2 or 4 would give 7 or 5.
    assert fa.measure(fa.read(ramp), "run.accel_time", action="right").value == 6


def test_ac_07_3_release_tick_is_first_row_with_zero_after_press(ramp):
    # release at row 20: decel counts 20..25 = 6 (from the shared ramp). Move the release one row later.
    def later(rows):
        for r in rows:
            if int(r["tick"]) == 20:
                r["in.right"] = "1"
                r["player.velocity.x"] = "220.000000"
            elif 21 <= int(r["tick"]) <= 25:
                r["player.velocity.x"] = f"{max(0.0, 220.0 - 40.0 * (int(r['tick']) - 20)):.6f}"
    _rewrite(ramp, later)
    m = fa.measure(fa.read(ramp), "run.decel_time", action="right")
    assert not m.undefined
    # release is now row 21 and vx first drops to <= 11 at row 26: 26 - 21 + 1 = 6.
    # A release wrongly taken as row 20 would give 7.
    assert m.value == 6


def test_ac_07_3_input_already_held_at_row_zero_is_not_a_press(ramp):
    def held(rows):
        for r in rows:
            r["in.right"] = "1"
    _rewrite(ramp, held)
    m = fa.measure(fa.read(ramp), "run.accel_time", action="right")
    assert m.undefined, "a column that is >0 from row 0 has no press tick (rows start at 1 for presses)"


# ---- AC-07.4 windows ---------------------------------------------------------------------------------------
def test_ac_07_4_window_longest_true_prefix():
    T, F = True, False
    assert fa.window({0: T, 1: T, 2: T, 3: T, 4: F, 5: F, 6: F}) == (3, False)
    assert fa.window({0: T, 1: F, 2: F}) == (0, False)


def test_ac_07_4_window_gap_flag_when_later_offset_jumps_after_failure():
    T, F = True, False
    assert fa.window({0: T, 1: T, 2: F, 3: T, 4: F}) == (1, True)


def test_ac_07_4_window_offset_zero_false_is_a_sweep_error():
    with pytest.raises(Exception):
        r = fa.window({0: False, 1: False, 2: False})
        # a non-raising implementation must at least not report a valid window
        raise AssertionError(f"returned {r!r}")


# ---- AC-07.5 camera ----------------------------------------------------------------------------------------
def test_ac_07_5_camera_step_lag_settle_overshoot(cam):
    t = fa.read(cam)
    assert fa.measure(t, "camera.lag_px", action="right").value == pytest.approx(40)
    assert fa.measure(t, "camera.settle_time", action="right").value == 4
    assert fa.measure(t, "camera.overshoot_px", action="right").value == pytest.approx(2)


def test_ac_07_5_camera_settle_depends_on_eps(cam):
    assert fa.measure(fa.read(cam), "camera.settle_time", action="right", eps=5).value == 2


def test_ac_07_5_instant_camera_settles_in_zero_with_no_overshoot(cam):
    def snap(rows):
        for r in rows:
            r["camera.get_screen_center_position.x"] = r["player.position.x"]
    _rewrite(cam, snap)
    t = fa.read(cam)
    assert fa.measure(t, "camera.settle_time", action="right").value == 0
    assert fa.measure(t, "camera.overshoot_px", action="right").value == 0


def test_ac_07_5_residual_offset_is_vector_length_at_last_row(cam):
    assert fa.measure(fa.read(cam), "camera.residual_offset_px").value == pytest.approx(5.0)


# ---- AC-07.6 tween -----------------------------------------------------------------------------------------
def test_ac_07_6_tween_duration(tmp_path):
    p = fa.csv_copy("tween", tmp_path)
    m = fa.measure(fa.read(p), "tween.duration", col="box.position.x", from_tick=5)
    assert not m.undefined and m.value == 10


def test_ac_07_6_tween_requires_col(tmp_path):
    p = fa.csv_copy("tween", tmp_path)
    assert fa.measure(fa.read(p), "tween.duration", from_tick=5).undefined


# ---- AC-07.7 rate comparison -------------------------------------------------------------------------------
RATE_TOL = 0.10


def test_ac_07_7_constant_seconds_is_rate_independent():
    assert fa.spread({30: 0.1, 60: 0.1, 120: 0.1}, slack_s=1 / 30) <= RATE_TOL


def test_ac_07_7_tick_counter_is_rate_dependent():
    assert fa.spread({30: 0.1667, 60: 0.0833, 120: 0.0417}, slack_s=1 / 30) > RATE_TOL


def test_ac_07_7_tick_quantisation_ok_only_thanks_to_slack():
    v = {30: 3 / 30, 60: 7 / 60, 120: 12 / 120}
    assert fa.spread(v, slack_s=1 / 30) <= RATE_TOL
    assert fa.spread(v, slack_s=0.0) > RATE_TOL  # px-like metrics get no slack


# ---- AC-07.8 judging and approval ----------------------------------------------------------------------------
def _target(metric="run.accel_time", lo=4.0, hi=8.0, unit="ticks"):
    return {"metric": metric, "min_value": lo, "max_value": hi, "unit": unit,
            "approved_by": "J. Whitford", "approved_on": "2026-10-01", "tick_rate": 60}


def test_ac_07_8_ticks_target_converts_through_seconds_at_other_rate():
    # 12 ticks at 120 Hz = 0.1 s = 6 ticks at the target's 60 Hz: in [4, 8]
    assert fa.judge_verdict(12, "ticks", 120, _target(), seconds=0.1) == "pass"
    # 20 ticks at 120 Hz = 0.167 s = 10 ticks at 60 Hz: out of range
    assert fa.judge_verdict(20, "ticks", 120, _target(), seconds=20 / 120) == "fail"


def test_ac_07_8_unit_family_mismatch_is_an_error():
    assert fa.judge_verdict(6, "ticks", 60, _target(unit="px")) == "error"


def test_ac_07_8_bounds_inclusive_after_six_decimal_rounding():
    t = _target(metric="jump.apex_px", lo=70.0, hi=95.0, unit="px")
    assert fa.judge_verdict(95.0, "px", 60, t) == "pass"
    assert fa.judge_verdict(95.0000004, "px", 60, t) == "pass"
    assert fa.judge_verdict(95.000001, "px", 60, t) == "fail"
    assert fa.judge_verdict(70.0, "px", 60, t) == "pass"


@pytest.mark.parametrize("by", ["", "provisional-default", "Claude", "agent-p7", "bot", "ai", "AI", "Provisional"])
def test_ac_07_8_non_human_names_are_not_approved(by):
    assert fa.is_approved(by, "2026-10-01") is False


@pytest.mark.parametrize("by", ["J. Whitford", "fixture-human", "Aiden"])
def test_ac_07_8_human_names_are_approved(by):
    assert fa.is_approved(by, "2026-10-01") is True


@pytest.mark.parametrize("on", ["", "2026-10-1", "yesterday", "10/01/2026"])
def test_ac_07_8_approval_needs_an_iso_date(on):
    assert fa.is_approved("J. Whitford", on) is False
