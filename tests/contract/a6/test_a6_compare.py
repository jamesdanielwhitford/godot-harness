"""A6 contract: `h shot --compare` against the approved baseline (AC-06.8-12, 23). Layer: contract. Needs Godot + Xvfb."""
import json
import re
import subprocess

import pytest

from a6_util import (HUD, MAIN, META_REL, PNG_REL, PROPOSED_META_REL, PROPOSED_PNG_REL, edit_meta, load_meta, patch,
                     save_meta, sha256, shot)
from helpers.h import apply_fault, assert_contract
from pathlib import Path

pytestmark = [pytest.mark.godot, pytest.mark.xvfb]


def compare(sm, tmp_path, *extra):
    r = shot(sm, tmp_path, MAIN, "--compare", *extra)
    assert_contract(r)
    return r


def compare_json(r):
    return json.loads(r.artifact("compare.json").read_text())


# ---- AC-06.8 -----------------------------------------------------------------------------------------------
def test_ac_06_8_clean_compare_is_identical(sm, tmp_path):
    r = compare(sm, tmp_path)
    assert r.rc == 0 and r.verdict == "PASS", r
    assert r.matches(r"^OK +main-t30: identical"), r.stdout
    assert r.stats["target"].startswith(MAIN), r.stats


def test_ac_06_8_planted_hud_shift_fails_with_pixel_count(sm, tmp_path):
    apply_fault("FAULT-A6-01", sm)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert r.has_finding(rule="shot.diff", severity="error", msg_re=r"\d+ px \([0-9.]+%\)"), r.stdout
    rows = compare_json(r)
    row = [x for x in rows if x["name"] == "main-t30"][0]
    assert row["px"] > 0 and row["verdict"] != "identical", row
    assert r.artifact("shots/main-t30.diff.png").is_file()


# ---- AC-06.9 -----------------------------------------------------------------------------------------------
def _other_mesa(m):
    m["env"]["api"] = "other Mesa"


def test_ac_06_9_tolerant_mode_clean_scene_is_identical(sm, tmp_path):
    edit_meta(sm, _other_mesa)
    r = compare(sm, tmp_path)
    assert r.rc == 0 and r.matches(r"^OK +main-t30: identical"), r


def test_ac_06_9_tolerant_mode_still_fails_on_large_change(sm, tmp_path):
    edit_meta(sm, _other_mesa)
    apply_fault("FAULT-A6-01", sm)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.has_finding(rule="shot.diff", severity="error"), r    # 0.72% > 0.1%
    assert "tolerant" in r.stdout, r.stdout


def test_ac_06_9_ignore_rect_covering_the_change_passes(sm, tmp_path):
    apply_fault("FAULT-A6-01", sm)
    edit_meta(sm, lambda m: m.__setitem__("ignore", [[0, 0, 200, 60]]))
    r = compare(sm, tmp_path)
    assert r.rc == 0 and r.verdict == "PASS", r


def test_ac_06_9_ignore_rect_in_tolerant_mode_passes(sm, tmp_path):
    apply_fault("FAULT-A6-01", sm)

    def f(m):
        _other_mesa(m)
        m["ignore"] = [[0, 0, 200, 60]]
    edit_meta(sm, f)
    r = compare(sm, tmp_path)
    assert r.rc == 0, r


def _provisional(m):
    m["approved_by"] = "provisional-default"
    m["approved_at"] = None


def test_ac_06_9_provisional_baseline_clean_is_warn(sm, tmp_path):
    edit_meta(sm, _provisional)
    r = compare(sm, tmp_path)
    assert r.rc == 5 and r.verdict == "WARN", r
    assert r.matches(r"^OK +main-t30: identical"), r.stdout
    warns = [f for f in r.all_findings() if f["rule"] == "shot.baseline-unapproved"]
    assert len(r.all_findings()) == 1 and len(warns) == 1, r.all_findings()
    assert warns[0]["severity"] == "warning" and "provisional-default" in warns[0]["message"], warns


def test_ac_06_9_provisional_baseline_with_diff_is_fail_plus_warning(sm, tmp_path):
    edit_meta(sm, _provisional)
    apply_fault("FAULT-A6-01", sm)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert r.has_finding(rule="shot.diff", severity="error"), r
    assert r.has_finding(rule="shot.baseline-unapproved", severity="warning"), r


# ---- AC-06.10 / 06.11 ---------------------------------------------------------------------------------------
def test_ac_06_10_renderer_mismatch_runs_no_diff(sm, tmp_path):
    apply_fault("FAULT-A6-04", sm)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.has_finding(rule="shot.renderer-mismatch", severity="error"), r
    for row in compare_json(r):
        assert not row.get("px"), f"no odiff call expected, compare.json has px: {row}"
    assert not r.artifact("shots/main-t30.diff.png").exists()


def test_ac_06_11_size_mismatch_is_not_tampered(sm, tmp_path):
    png = sm / PNG_REL
    subprocess.run(["convert", "-size", "320x180", "xc:#112233", str(png)], check=True)
    edit_meta(sm, lambda m: m.update(image={"w": 320, "h": 180, "sha256": sha256(png)}))
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.has_finding(rule="shot.size-mismatch", severity="error"), r
    assert not r.has_finding(rule="shot.baseline-tampered"), r


# ---- AC-06.12 -----------------------------------------------------------------------------------------------
def test_ac_06_12_compare_rejects_capture_flags(sm, tmp_path):
    for extra in (["--tick", "5"], ["--size", "320x180"], ["--crop", "0,0,8,8"], ["--node", "%Score"],
                  ["--hide", "%HUD"], ["--hide-layer", "1"], ["--seed", "2"]):
        r = compare(sm, tmp_path, *extra)
        assert r.rc == 2 and r.verdict == "ERROR", (extra, r)


def test_ac_06_12_compare_without_baselines_is_no_baseline(sm, tmp_path):
    r = shot(sm, tmp_path, HUD, "--compare")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="shot.no-baseline", severity="error"), r


def test_ac_06_12_compare_unknown_name_is_no_baseline(sm, tmp_path):
    r = compare(sm, tmp_path, "--name", "does-not-exist")
    assert r.rc == 1 and r.has_finding(rule="shot.no-baseline"), r


# ---- AC-06.23 -----------------------------------------------------------------------------------------------
def test_ac_06_23_only_a_proposal_is_unapproved_error(sm, tmp_path):
    (sm / PNG_REL).rename(sm / PROPOSED_PNG_REL)
    meta = load_meta(sm)
    (sm / META_REL).unlink()
    meta["status"] = "proposed"
    meta["approved_by"] = None
    meta["approved_at"] = None
    save_meta(sm, meta, PROPOSED_META_REL)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.has_finding(rule="shot.baseline-unapproved", severity="error"), r


def test_ac_06_23_status_proposed_in_approved_meta(sm, tmp_path):
    apply_fault("FAULT-A6-06", sm)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.has_finding(rule="shot.baseline-unapproved", severity="error"), r


def test_ac_06_23_png_edited_after_approval_is_tampered(sm, tmp_path):
    apply_fault("FAULT-A6-07", sm)
    r = compare(sm, tmp_path)
    assert r.rc == 1 and r.has_finding(rule="shot.baseline-tampered", severity="error"), r
    assert not r.has_finding(rule="shot.diff"), "tampering is detected before any diff"


def test_ac_06_23_meta_missing_env_is_bad_baseline(sm, tmp_path):
    edit_meta(sm, lambda m: m.pop("env"))
    r = compare(sm, tmp_path)
    assert r.rc == 2 and r.has_finding(rule="shot.bad-baseline", severity="error"), r


@pytest.mark.parametrize("who", ["provisional-default", "Agent", "claude-opus", "BOT"])
def test_ac_06_23_non_human_approver_warns(sm, tmp_path, who):
    edit_meta(sm, lambda m: m.__setitem__("approved_by", who))
    r = compare(sm, tmp_path)
    assert r.rc == 5 and r.verdict == "WARN", (who, r)
    assert r.has_finding(rule="shot.baseline-unapproved", severity="warning"), r
    assert r.matches(r"^OK +main-t30: identical"), r.stdout


@pytest.mark.parametrize("who", ["fixture T6", "Ada", "ci-bot"])
def test_ac_06_23_human_approver_is_clean(sm, tmp_path, who):
    edit_meta(sm, lambda m: m.__setitem__("approved_by", who))
    r = compare(sm, tmp_path)
    assert r.rc == 0 and r.verdict == "PASS", (who, r)
    assert not r.has_finding(rule="shot.baseline-unapproved"), r
