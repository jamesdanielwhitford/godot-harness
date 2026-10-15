"""A6 contract: `h baseline propose|approve|list` (AC-06.21, 22, 24). Layer: contract. Needs Godot + Xvfb."""
import re

import pytest

from a6_util import (BASELINE_REL, META_REL, PNG_REL, PROPOSED_META_REL, PROPOSED_PNG_REL, baseline, check_meta_schema,
                     edit_meta, load_meta, patch, run_h_no_tty, run_h_tty, sha256, shot)
from helpers.h import assert_contract, tree_hash

pytestmark = [pytest.mark.godot, pytest.mark.xvfb]
MAIN = "res://scenes/main.tscn"


def approved_pair(p):
    return (p / PNG_REL).read_bytes(), (p / META_REL).read_bytes()


def make_proposal(p, tmp_path, shift=False):
    if shift:
        patch(p, "scripts/main.gd", "panel.position = Vector2(10, 10)", "panel.position = Vector2(30, 10)")
    r = baseline(p, tmp_path / "prop", "propose", MAIN, "--tick", "30")
    assert_contract(r)
    assert r.rc == 0, r
    return r


# ---- AC-06.21 -----------------------------------------------------------------------------------------------
def test_ac_06_21_propose_writes_pending_pair_and_keeps_approved(sm, tmp_path):
    (sm / "baselines" / ".gdignore").unlink()
    before = approved_pair(sm)
    r = baseline(sm, tmp_path, "propose", MAIN, "--tick", "30")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "baseline", r
    assert r.check("main-t30")[0] == "OK" and "proposed" in r.check("main-t30")[2], r.checks
    assert (sm / PROPOSED_PNG_REL).is_file()
    meta = load_meta(sm, PROPOSED_META_REL)
    assert check_meta_schema(meta) == [], check_meta_schema(meta)
    assert meta["status"] == "proposed" and meta["name"] == "main-t30" and meta["tick"] == 30
    assert meta.get("approved_by") in (None, "") and meta.get("approved_at") in (None, "")
    assert meta["image"]["sha256"] == sha256(sm / PROPOSED_PNG_REL)
    assert (sm / "baselines" / ".gdignore").is_file(), "propose must (re)create baselines/.gdignore"
    assert approved_pair(sm) == before, "the approved pair must stay byte-identical"
    r2 = shot(sm, tmp_path / "cmp", MAIN, "--compare")
    assert_contract(r2)
    assert r2.rc == 0 and r2.matches(r"^OK +main-t30: identical"), r2


def test_ac_06_21_propose_overwrites_older_proposal(sm, tmp_path):
    make_proposal(sm, tmp_path)
    first = (sm / PROPOSED_META_REL).read_bytes()
    patch(sm, "scripts/main.gd", "panel.position = Vector2(10, 10)", "panel.position = Vector2(40, 10)")
    r = baseline(sm, tmp_path / "again", "propose", MAIN, "--tick", "30")
    assert r.rc == 0, r
    assert (sm / PROPOSED_META_REL).read_bytes() != first


def test_ac_06_21_propose_refuses_unstable_scene(sm, tmp_path):
    from helpers.h import apply_fault
    apply_fault("FAULT-A6-02", sm)
    r = baseline(sm, tmp_path, "propose", MAIN, "--tick", "30")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="shot.unstable"), r
    assert not (sm / PROPOSED_PNG_REL).exists() and not (sm / PROPOSED_META_REL).exists()


# ---- AC-06.22 -----------------------------------------------------------------------------------------------
def test_ac_06_22_approve_without_tty_is_rc2_and_changes_nothing(sm, tmp_path):
    make_proposal(sm, tmp_path, shift=True)
    before = tree_hash(sm / "baselines")
    r = run_h_no_tty(["baseline", "approve", MAIN, "--project", sm], tmp_path / "x")
    assert_contract(r)
    assert r.rc == 2 and r.verdict == "ERROR", r
    assert r.has_finding(rule="shot.approve-needs-tty", severity="error"), r
    assert tree_hash(sm / "baselines") == before


def test_ac_06_22_approve_yes_replaces_the_approved_pair(sm, tmp_path):
    make_proposal(sm, tmp_path, shift=True)
    prop_sha = sha256(sm / PROPOSED_PNG_REL)
    old_sha = sha256(sm / PNG_REL)
    assert prop_sha != old_sha
    r, tty = run_h_tty(["baseline", "approve", MAIN, "--project", sm], tmp_path / "ap", ["yes"])
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", (r, tty)
    assert re.match(r"^approved by \S+", r.check("main-t30")[2]), r.checks
    assert sha256(sm / PNG_REL) == prop_sha
    meta = load_meta(sm)
    assert meta["status"] == "approved" and meta["approved_by"] and meta["approved_at"], meta
    assert meta["image"]["sha256"] == prop_sha
    assert not (sm / PROPOSED_PNG_REL).exists() and not (sm / PROPOSED_META_REL).exists()
    assert tty.strip(), "the prompt goes to the terminal, not stdout"


def test_ac_06_22_approve_no_skips_and_changes_nothing(sm, tmp_path):
    make_proposal(sm, tmp_path, shift=True)
    before = tree_hash(sm / "baselines")
    r, tty = run_h_tty(["baseline", "approve", MAIN, "--project", sm], tmp_path / "ap", ["no"])
    assert_contract(r)
    assert r.check("main-t30") and r.check("main-t30")[0] == "SKIP", (r, tty)
    assert tree_hash(sm / "baselines") == before


# ---- AC-06.24 -----------------------------------------------------------------------------------------------
def test_ac_06_24_list_clean_is_pass(sm, tmp_path):
    r = baseline(sm, tmp_path, "list")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", r
    assert len(r.checks) == 1 and r.checks[0][0] == "OK", r.checks
    assert "main-t30" in r.checks[0][1] and "approved by fixture T6" in r.checks[0][2], r.checks


def test_ac_06_24_list_with_pending_proposal_is_warn(sm, tmp_path):
    make_proposal(sm, tmp_path)
    r = baseline(sm, tmp_path / "l", "list", MAIN)
    assert_contract(r)
    assert r.rc == 5 and r.verdict == "WARN", r
    assert any(c[0] == "WARN" and "proposal pending" in c[2] for c in r.checks), r.checks
    assert not any(c[0] == "FAIL" for c in r.checks)


def test_ac_06_24_list_provisional_is_warn(sm, tmp_path):
    edit_meta(sm, lambda m: m.update(approved_by="provisional-default", approved_at=None))
    r = baseline(sm, tmp_path, "list")
    assert_contract(r)
    assert r.rc == 5, r
    assert any(c[0] == "WARN" and "provisional" in c[2] for c in r.checks), r.checks


def test_ac_06_24_list_tampered_is_fail(sm, tmp_path):
    from helpers.h import apply_fault
    apply_fault("FAULT-A6-07", sm)
    r = baseline(sm, tmp_path, "list")
    assert_contract(r)
    assert r.rc == 1 and any(c[0] == "FAIL" and "tampered" in c[2] for c in r.checks), r


def test_ac_06_24_approve_with_nothing_pending_is_warn(sm, tmp_path):
    r, _tty = run_h_tty(["baseline", "approve", MAIN, "--project", sm], tmp_path, [])
    assert_contract(r)
    assert r.rc == 5 and r.verdict == "WARN", r
    assert r.matches(r"^WARN +proposals: none pending$"), r.stdout
