"""A7 contract: `h selftest --area A7` (spec 07_feel.md AC-07.24). Owner: T7."""
from __future__ import annotations

import json
import re

import pytest

from helpers.h import assert_contract, run_h

pytestmark = [pytest.mark.godot, pytest.mark.slow]


def test_ac_07_24_selftest_area_a7_catches_every_fault_and_passes_clean(tmp_path):
    r = run_h("selftest", "--area", "A7", env={"HARNESS_OUT": tmp_path / "out"}, timeout=420)
    assert_contract(r)
    assert r.rc == 0, str(r)
    assert r.verdict == "PASS"
    assert re.search(r"^faults: 11 total, 11 caught", r.stdout, re.MULTILINE), r.stdout
    assert re.search(r"^clean: 2 total, 2 pass, 0 false-positive", r.stdout, re.MULTILINE), r.stdout
    assert r.wall <= 300, f"{r.wall:.0f}s > 300s budget"
    matrix = json.loads(r.artifact("matrix.json").read_text())
    entries = matrix["entries"] if isinstance(matrix, dict) and "entries" in matrix else matrix
    ids = sorted(e["id"] for e in entries)
    assert ids == sorted([f"FAULT-A7-{i:02d}" for i in range(1, 12)] + ["CLEAN-A7-01", "CLEAN-A7-02"])
