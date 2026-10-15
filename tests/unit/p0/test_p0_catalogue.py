"""Well-formedness of the P0 and A1 seeded-fault catalogue (selftest/faults, selftest/clean) and of its fixtures.
Counts follow the specs (P0: 8 faults + 2 clean; A1: 20 faults, 1 nice + 4 clean). Layer: unit (reads files only)."""
import re
import tomllib
from pathlib import Path

import pytest

from helpers.h import SELFTEST, apply_fault, copy_fixture, fixture_path

ID_RE = re.compile(r"^(FAULT|CLEAN)-(P0|A(10|[1-9]))-\d{2}$")
VERBS = {"doctor", "sync", "import", "api", "check", "lint", "digest", "scene-gen", "scene-edit", "test", "run", "trace",
         "shot", "baseline", "lsp", "selftest", "init"}


def entries(kind, area):
    return sorted(p for p in (SELFTEST / kind).glob(f"*-{area}-*") if p.is_dir())


def load(d):
    return tomllib.loads((d / "fault.toml").read_text())


ALL = entries("faults", "P0") + entries("faults", "A1") + entries("clean", "P0") + entries("clean", "A1")


def test_p0_counts():
    assert len(entries("faults", "P0")) == 8 and len(entries("clean", "P0")) == 2
    assert all(load(d)["severity"] == "must" for d in entries("faults", "P0"))


def test_a1_counts():
    f = entries("faults", "A1")
    assert len(f) == 20 and len(entries("clean", "A1")) == 4
    assert [load(d)["id"] for d in f if load(d)["severity"] == "nice"] == ["FAULT-A1-17"]


@pytest.mark.parametrize("d", ALL, ids=[d.name for d in ALL])
def test_entry_is_well_formed(d):
    spec = load(d)
    assert ID_RE.match(spec["id"]) and spec["id"] == d.name
    assert spec["area"] in ("P0", "A1") and spec["id"].split("-")[1] == spec["area"]
    assert spec["severity"] in ("must", "nice")
    if d.name.startswith("CLEAN"):
        assert spec["severity"] == "must"
    run, exp = spec["run"], spec["expect"]
    assert run["verb"] in VERBS
    for k in ("rc", "verdict", "regex", "not_regex", "max_seconds"):
        assert k in exp
    assert exp["verdict"] in ("PASS", "FAIL", "WARN", "ERROR")
    if d.name.startswith("FAULT"):
        assert len(exp["regex"]) >= 1
    for rx in exp["regex"] + exp["not_regex"]:
        re.compile(rx, re.MULTILINE)
    for op in spec["apply"]:
        assert op["op"] in ("write", "replace", "delete")
        if op["op"] == "write" and "from" in op:
            assert (d / op["from"]).is_file(), op


@pytest.mark.parametrize("d", ALL, ids=[d.name for d in ALL])
def test_apply_ops_succeed_on_a_fixture_copy(d, tmp_path):
    spec = load(d)
    p = copy_fixture(spec["fixture"], tmp_path / "proj")
    apply_fault(spec["id"], p)  # raises HelperError when a replace misses or a delete target is absent


def test_fixtures_obey_contract_2_11():
    for name in ("clean_min", "gd_host", "scene_cases"):
        p = fixture_path(name)
        assert re.match(r"^[a-z0-9_]+$", name)
        txt = (p / "project.godot").read_text()
        assert "config_version=5" in txt and f'config/name="{name}"' in txt and 'config/features=PackedStringArray("4.7")' in txt
        assert len((p / "FIXTURE.md").read_text().splitlines()) <= 5
        assert not list(p.rglob("*.uid")) and not (p / ".godot").exists() and not (p / "addons").exists()
        assert sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) < 200_000


def test_clean_min_main_scene_and_class():
    p = fixture_path("clean_min")
    assert 'run/main_scene="res://scenes/main.tscn"' in (p / "project.godot").read_text()
    assert "class_name Hello" in (p / "scripts/hello.gd").read_text()
    assert "Sprite2D" in (p / "scenes/main.tscn").read_text()


def test_gd_host_declares_the_four_harness_autoloads():
    txt = (fixture_path("gd_host") / "project.godot").read_text()
    for n, f in (("Harness", "harness"), ("Rng", "rng"), ("CommandBus", "command_bus"), ("Trace", "trace")):
        assert f'{n}="*res://addons/harness/{f}.gd"' in txt


def test_gd_cases_are_all_present():
    names = {p.stem for p in (fixture_path("gd_cases")).glob("*.gd")}
    assert len(names) == 35 and "c28_tabspace" in names and "d03_signal_connect_str" in names
    assert (fixture_path("gd_cases") / "c28_tabspace.gd").read_text().splitlines()[3] == " " * 8 + "print(a)"


def test_wrong_version_binary_is_executable_and_prints_4_6():
    import os, subprocess
    b = fixture_path("bin") / "godot_wrong_version"
    assert os.access(b, os.X_OK)
    assert subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip().startswith("4.6.stable")
