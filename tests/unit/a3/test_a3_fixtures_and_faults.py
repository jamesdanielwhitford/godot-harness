"""A3 self-checks of the test assets (green before any implementation): fixtures match spec 6.1, fault files are
well-formed and meet the spec 5 minimum. No harness import."""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests" / "contract" / "a3"))
import a3_common as c  # noqa: E402

PROJ = REPO / "tests" / "fixtures" / "projects"
ID_RE = re.compile(r"^(FAULT|CLEAN)-(P0|A(10|[1-9]))-\d{2}$")


def test_godot3_scripts_fixture_matches_spec_6_1():
    d = PROJ / "godot3_scripts"
    for n, (text, _rows) in c.CASES.items():
        assert (d / "cases" / f"{n}.gd").read_text() == text, n
    for n, (text, _rows) in c.TSCN.items():
        assert (d / "scenes" / f"{n}.tscn").read_text() == text, n
    assert (d / "scenes" / "ok.gd").read_text() == "extends Node2D\n"
    assert (d / "project.godot").read_text() == c.GODOT3_PROJECT_GODOT
    assert len(list((d / "cases").glob("*.gd"))) == 35
    exp = c.expected_godot3()
    assert sum(1 for e in exp if e[3] == "error") == 37 and sum(1 for e in exp if e[3] == "warning") == 5


def test_fixture_minimum_files():
    for name in ("godot3_scripts", "lint_base", "lint_clean_demo"):
        d = PROJ / name
        pg = (d / "project.godot").read_text()
        assert "config_version=5" in pg and f'config/name=' in pg and 'PackedStringArray("4.7")' in pg, name
        assert 0 < len((d / "FIXTURE.md").read_text().splitlines()) <= 5, name
        assert not list(d.rglob("*.uid")) and not (d / ".godot").exists()
        assert sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) <= 200_000
    assert (PROJ / "lint_clean_demo" / "harness.toml").read_text() == '[lint]\nreplay_dirs = ["res://"]\n'
    assert (PROJ / "lint_clean_demo" / "LICENSE").read_text().startswith("MIT License")
    assert not (PROJ / "lint_base" / "harness.toml").exists()
    assert "[input]" in (PROJ / "lint_base" / "project.godot").read_text()


def test_a3_fault_files_wellformed_and_meet_minimum():
    faults = sorted((REPO / "selftest" / "faults").glob("FAULT-A3-*"))
    clean = sorted((REPO / "selftest" / "clean").glob("CLEAN-A3-*"))
    assert len(faults) == 27 and len(clean) == 3          # spec 5 (plan minimum 15 faults / 3 clean)
    nice = 0
    for d in faults + clean:
        t = tomllib.loads((d / "fault.toml").read_text())
        assert ID_RE.match(t["id"]) and t["id"] == d.name and t["area"] == "A3"
        assert t["fixture"] in ("lint_base", "lint_clean_demo")
        assert (PROJ / t["fixture"]).is_dir()
        assert t["severity"] in ("must", "nice")
        e = t["expect"]
        assert e["rc"] in (0, 1, 2, 5) and e["verdict"] in ("PASS", "FAIL", "ERROR", "WARN")
        if d.name.startswith("FAULT"):
            assert e["regex"], f"{d.name}: a fault needs >= 1 regex"
            nice += t["severity"] == "nice"
        else:
            assert t["severity"] == "must"
        for op in t["apply"]:
            assert op["op"] in ("write", "replace", "delete")
            if "from" in op:
                assert (d / op["from"]).is_file()
        for rx in e["regex"] + e["not_regex"]:
            re.compile(rx)
    assert nice == 2
    assert len(faults) - nice == 25
