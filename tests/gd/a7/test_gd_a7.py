"""A7 [gd] wrapper (REVIEW R-39): runs tests/gd/a7/*.gd through `h test` on the gd_host copy. Owner: T7."""
from __future__ import annotations

import pytest

from helpers.gd import cleanup, run_gd_suites
from helpers.h import assert_contract

pytestmark = pytest.mark.godot


def test_ac_07_22_trace_dormant_and_feel_targets_round_trip():
    r = run_gd_suites("a7")
    try:
        assert_contract(r)
        assert r.rc == 0, str(r)
        assert r.verdict == "PASS"
    finally:
        cleanup(r)
