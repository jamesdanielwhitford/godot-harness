"""A1 contract: seeded faults of A1 (AC-01.28). Layer: selftest via `h selftest --area A1`."""
import re

import pytest

from helpers.h import assert_contract, run_h


@pytest.mark.slow
@pytest.mark.godot
def test_ac_01_28_selftest_a1_catches_everything(tmp_path):
    r = run_h("selftest", "--area", "A1", env={"HARNESS_OUT": str(tmp_path / "out"), "HARNESS_TMP": str(tmp_path / "ht")}, timeout=600)
    assert_contract(r)
    assert r.rc == 0, r
    assert re.match(r"^20 total, 20 caught, 0 missed \(must 0, nice 0\), 0 slow, 0 overflow, 0 broken$", r.stats["faults"]), r.stats
    assert re.match(r"^4 total, 4 pass, 0 false-positive$", r.stats["clean"]), r.stats
    assert r.wall <= 300, f"{r.wall:.0f}s"
