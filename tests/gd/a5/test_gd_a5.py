"""AC-05.25 / AC-05.26: gdUnit4 suites for Rng, Harness and CommandBus (tests/gd/a5/*.gd), run through
helpers.gd.run_gd_suites on the gd_host fixture copy (REVIEW R-39). Red until addons/harness and `h test` exist."""
import re

import pytest

from helpers.gd import cleanup, run_gd_suites
from helpers.h import assert_contract

pytestmark = [pytest.mark.godot, pytest.mark.slow]


def test_ac_05_25_26_gd_suites_pass():
    r = run_gd_suites("a5")
    try:
        assert_contract(r)
        assert r.rc == 0 and r.verdict == "PASS", str(r)
        m = re.match(r"^(\d+) total, (\d+) passed, 0 failed, 0 errors", r.stats.get("tests", ""))
        assert m, f"tests stat: {r.stats.get('tests')!r}"
        # 7 Rng cases (AC-05.25) + 7 Harness/CommandBus cases (AC-05.26)
        assert int(m.group(1)) == 14 and int(m.group(2)) == 14, r.stats["tests"]
    finally:
        cleanup(r)
