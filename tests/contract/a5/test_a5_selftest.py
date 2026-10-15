"""AC-05.28: `h selftest --area A5` catches every must fault and passes both clean entries (spec 05_scenario.md 5)."""
import json
import re
import tomllib
from pathlib import Path

import pytest

from helpers.h import REPO, SELFTEST, assert_contract, run_h

pytestmark = [pytest.mark.godot, pytest.mark.slow]

MUST = [f"FAULT-A5-{i:02d}" for i in range(1, 11)]
NICE = ["FAULT-A5-11", "FAULT-A5-12"]


def test_ac_05_28_1_entries_are_well_formed():
    """Pure file check: ids, count (>= 8 faults, 12 specified), areas, severities, clean entries."""
    got = {}
    for sub in ("faults", "clean"):
        for d in sorted((SELFTEST / sub).glob("*A5-*")):
            spec = tomllib.loads((d / "fault.toml").read_text())
            assert spec["id"] == d.name and spec["area"] == "A5"
            assert spec["fixture"] == "scenario_min" and spec["run"]["verb"] == "run"
            assert re.match(r"^(FAULT|CLEAN)-A5-\d{2}$", d.name)
            got[d.name] = spec
    assert set(MUST + NICE) <= set(got)
    assert {"CLEAN-A5-01", "CLEAN-A5-02"} <= set(got)
    assert len([k for k in got if k.startswith("FAULT")]) >= 12
    for k in MUST:
        assert got[k]["severity"] == "must"
    for k in NICE:
        assert got[k]["severity"] == "nice"
    for k, spec in got.items():
        for op in spec["apply"]:
            if op["op"] == "write" and "from" in op:
                assert (SELFTEST / ("clean" if k.startswith("CLEAN") else "faults") / k / op["from"]).is_file()


def test_ac_05_28_2_selftest_area_a5_catches_all_must_faults():
    r = run_h("selftest", "--area", "A5", timeout=600)
    assert_contract(r)
    assert r.rc in (0, 5), str(r)
    assert r.wall <= 120, f"wall {r.wall:.0f}s"
    m = re.match(r"^(\d+) total, (\d+) caught, (\d+) missed \(must (\d+), nice (\d+)\)", r.stats["faults"])
    assert m, r.stats.get("faults")
    total, caught, missed, must_missed, nice_missed = map(int, m.groups())
    assert total == 12 and must_missed == 0, r.stats["faults"]
    assert re.match(r"^2 total, 2 pass, 0 false-positive", r.stats["clean"]), r.stats["clean"]
    assert not [c for c in r.checks if c[0] == "FAIL" and c[1] in MUST]
    matrix = json.loads(r.artifact("matrix.json").read_text())
    assert len(matrix) == 14
    assert {e["id"] for e in matrix} >= set(MUST + NICE + ["CLEAN-A5-01", "CLEAN-A5-02"])
