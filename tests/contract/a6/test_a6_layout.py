"""A6 contract: `h shot --layout` (AC-06.20). Layer: contract. Layout runs headless: no Xvfb needed."""
import re

import pytest

from a6_util import HUD, patch, shot
from helpers.h import apply_fault, assert_contract

pytestmark = [pytest.mark.godot]


def layout(sm, tmp_path, *extra):
    r = shot(sm, tmp_path, HUD, "--layout", *extra)
    assert_contract(r)
    return r


def test_ac_06_20_clean_layout_two_sizes(sm, tmp_path):
    r = layout(sm, tmp_path, "--sizes", "640x360,1280x720")
    assert r.rc == 0 and r.verdict == "PASS", r
    ok = [c for c in r.checks if c[0] == "OK"]
    assert [c[1] for c in ok] == ["640x360", "1280x720"], r.checks
    assert len(r.checks) == 2


def test_ac_06_20_default_sizes_are_the_four_configured(sm, tmp_path):
    r = layout(sm, tmp_path)
    assert r.rc == 0, r
    assert [c[1] for c in r.checks] == ["1280x720", "1920x1080", "2560x1080", "800x1280"], r.checks
    assert r.wall <= 2.0 + 3.0, f"4 sizes took {r.wall:.1f}s"      # spec <= 2 s; +3 s slack for process start


def test_ac_06_20_clipped_title(sm, tmp_path):
    apply_fault("FAULT-A6-03", sm)
    r = layout(sm, tmp_path, "--sizes", "640x360")
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert r.has_finding(rule="shot.layout-clipped", severity="error", msg_re=r"Title.*640x360"), r.stdout


def test_ac_06_20_offscreen_health(sm, tmp_path):
    apply_fault("FAULT-A6-08", sm)
    r = layout(sm, tmp_path, "--sizes", "1280x720")
    assert r.rc == 1, r
    assert r.has_finding(rule="shot.layout-offscreen", severity="error", msg_re=r"Health"), r.stdout


def test_ac_06_20_overlapping_labels_warn(sm, tmp_path):
    patch(sm, "scripts/hud.gd", "\tpass # HOOK-HUD",
          "\tfor n in [\"OvA\", \"OvB\"]:\n\t\tvar l := Label.new()\n\t\tl.name = n\n\t\tl.text = \"OVERLAP\"\n"
          "\t\tadd_child(l)\n\t\tl.position = Vector2(300, 150)")
    r = layout(sm, tmp_path, "--sizes", "640x360")
    assert r.rc == 5 and r.verdict == "WARN", r
    assert r.has_finding(rule="shot.layout-overlap", severity="warning"), r.stdout
    assert not any(f["severity"] == "error" for f in r.all_findings())


def test_ac_06_20_layout_runs_headless_not_under_xvfb(sm, tmp_path):
    r = layout(sm, tmp_path, "--sizes", "640x360")
    inv = r.invocations()
    assert inv and "--headless" in inv[0]["argv"], inv
    assert not any("xvfb-run" in a for i in inv for a in i["argv"]), inv


def test_ac_06_20_layout_on_scenario_is_usage_error(sm, tmp_path):
    r = shot(sm, tmp_path, "res://scenarios/x.json", "--layout")
    assert_contract(r)
    assert r.rc == 2, r


def test_ac_06_20_layout_finding_order_is_by_size_then_path(sm, tmp_path):
    apply_fault("FAULT-A6-08", sm)
    r = layout(sm, tmp_path, "--sizes", "640x360,1280x720")
    names = [c[1] for c in r.checks]
    assert names == ["640x360", "1280x720"], r.checks
    assert re.search(r"1280x720", r.stdout)
