"""A7 contract: scenario mode, --rates, --movie (spec 07_feel.md AC-07.13, 14, 19). Owner: T7."""
from __future__ import annotations

import csv
import os
import re
import shutil
from pathlib import Path

import pytest

from a7util import SUITE, metrics_json, report_text, trace
from helpers.h import apply_fault

pytestmark = pytest.mark.godot

JUMP = "res://feel/jump.json"


# ---- AC-07.13 scenario mode ---------------------------------------------------------------------------------
def test_ac_07_13_scenario_mode_measures_without_a_target(feel):
    r = trace(feel, JUMP, "--nodes", "Player", "--metric", "jump.apex_px:action=jump", timeout=120)
    assert r.rc == 0, str(r)
    assert r.verdict == "PASS"
    m = re.search(r"^OK +jump\.apex_px: (-?\d+(?:\.\d+)?) px \(no target\)$", r.stdout, re.MULTILINE)
    assert m, r.stdout
    assert 70.0 <= float(m.group(1)) <= 95.0


def test_ac_07_13_trace_stat_names_a_nine_column_csv(feel):
    r = trace(feel, JUMP, "--nodes", "Player", "--metric", "jump.apex_px:action=jump", timeout=120)
    assert r.rc == 0, str(r)
    t = r.stats["trace"]
    m = re.search(r"\((\d+) rows x (\d+) columns\)", t)
    assert m and int(m.group(2)) == 9 and int(m.group(1)) == 121, t
    csv_path = r.artifact("traces/jump.csv")
    assert csv_path.is_file()
    with open(csv_path, newline="") as f:
        header = next(csv.reader(f))
    assert len(header) == 9, header
    assert header[0] == "tick"
    assert "player.position.x" in header or "Player.position.x" in header or "player.position.y" in header


def test_ac_07_13_scenario_mode_stat_lines(feel):
    r = trace(feel, JUMP, "--nodes", "Player", "--metric", "jump.apex_px:action=jump", timeout=120)
    keys = [k for k, _ in r.stat_items]
    assert keys[:5] == ["project", "import", "sync", "scenario", "trace"], keys


def test_ac_07_13_nodes_is_required_in_scenario_mode(feel):
    r = trace(feel, JUMP, "--metric", "jump.apex_px:action=jump", timeout=60)
    assert r.rc == 2 and r.verdict == "ERROR", str(r)


def test_ac_07_13_window_metric_needs_a_suite(feel):
    r = trace(feel, JUMP, "--nodes", "Player", "--metric", "jump.coyote_window", timeout=60)
    assert r.rc == 2 and r.verdict == "ERROR", str(r)


def test_ac_07_13_unknown_metric_in_scenario_mode_is_rc_2(feel):
    r = trace(feel, JUMP, "--nodes", "Player", "--metric", "jump.no_such_thing", timeout=60)
    assert r.rc == 2, str(r)
    assert r.has_finding(rule="feel.unknown-metric")


# ---- AC-07.14 --rates -----------------------------------------------------------------------------------------
@pytest.mark.slow
def test_ac_07_14_clean_fixture_is_rate_independent(feel):
    r = trace(feel, SUITE, "--rates", "30,60,120", timeout=300)
    assert r.rc == 0, str(r)
    assert r.wall <= 60, f"{r.wall:.0f}s > 60s budget for --rates 30,60,120 (spec 3.8)"
    mj = metrics_json(r)
    assert mj["rates"] == [30, 60, 120]
    for name, m in mj["measurements"].items():
        assert set(m["by_rate"]) == {"30", "60", "120"}, (name, m["by_rate"])
    text = report_text(r)
    assert re.search(r"30\s*Hz|@\s*30|\b30\b.*\b60\b.*\b120\b", text), "no per-rate table in the report"


@pytest.mark.slow
def test_ac_07_14_tick_counter_coyote_is_rate_dependent(feel):
    spec = apply_fault("FAULT-A7-08", feel)
    r = trace(feel, *spec["run"]["args"], timeout=400)
    assert r.rc == 1, str(r)
    assert r.has_finding(rule="feel.rate-dependent", severity="error", msg_re="jump\\.coyote_window")
    msg = next(f["message"] for f in r.findings_jsonl() if f["rule"] == "feel.rate-dependent"
               and "coyote" in f["message"])
    for rate in ("30", "60", "120"):
        assert rate in msg, f"{rate} Hz missing from: {msg}"


def test_ac_07_14_base_rate_must_be_in_the_list(feel):
    r = trace(feel, SUITE, "--rates", "30,120", timeout=60)
    assert r.rc == 2 and r.verdict == "ERROR", str(r)


def test_ac_07_14_rates_out_of_range_is_rc_2(feel):
    r = trace(feel, SUITE, "--rates", "60,5000", timeout=60)
    assert r.rc == 2, str(r)


# ---- AC-07.19 --movie ---------------------------------------------------------------------------------------
@pytest.mark.xvfb
@pytest.mark.slow
def test_ac_07_19_movie_writes_an_avi_and_prints_no_image_data(feel):
    r = trace(feel, SUITE, "--movie", "run", timeout=400)
    assert r.rc == 0, str(r)
    avi = r.artifact("movie/run.avi")
    assert avi.is_file() and avi.stat().st_size > 10_000, avi
    assert "movie/run.avi" in report_text(r)
    assert "RIFF" not in r.stdout and "\x00" not in r.stdout


def _path_without(prog: str, tmp: Path) -> str:
    """A PATH whose directories hold everything the current PATH holds except `prog` (symlinks)."""
    bindir = tmp / "bin"
    bindir.mkdir()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name == prog or (bindir / name).exists():
                continue
            src = os.path.join(d, name)
            if os.path.isfile(src) and os.access(src, os.X_OK):
                (bindir / name).symlink_to(src)
    return str(bindir)


@pytest.mark.slow
def test_ac_07_19_movie_without_xvfb_run_is_an_environment_error(feel, tmp_path):
    assert shutil.which("xvfb-run"), "test premise: xvfb-run is installed (tools/bootstrap.sh doctor)"
    path = _path_without("xvfb-run", tmp_path)
    r = trace(feel, SUITE, "--movie", "run", timeout=400, env={"PATH": path})
    assert r.rc == 4 and r.verdict == "ERROR", str(r)
