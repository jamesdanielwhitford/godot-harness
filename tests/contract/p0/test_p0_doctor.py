"""P0 contract: `h doctor` follows the stdout contract (AC-00.26, C3/C4). Layer: contract."""
import re

from helpers.h import assert_contract, run_h

REQUIRED = ("godot", "gdunit4", "odiff", "venv", "xvfb-run", "compare")


def test_ac_00_26_doctor_passes_in_a_bootstrapped_env(tmp_path):
    r = run_h("doctor", env={"HARNESS_OUT": str(tmp_path / "out")})
    assert_contract(r)
    assert r.rc == 0, r
    assert re.match(r"^PASS doctor \d+/\d+ checks ok$", r.lines[0]), r.lines[0]
    names = {c[1]: c[0] for c in r.checks}
    for n in REQUIRED:
        assert names.get(n) == "OK", (n, r.stdout)
    assert "4.7.stable.official.5b4e0cb0f" in r.check("godot")[2]
    assert r.wall <= 5, f"{r.wall:.1f}s"


def test_ac_00_26_missing_required_tools_is_rc_4(tmp_path):
    r = run_h("doctor", env={"HARNESS_CACHE": str(tmp_path / "emptycache"), "HARNESS_OUT": str(tmp_path / "out")})
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r
    assert r.lines[0].startswith("ERROR doctor ")
    failed = {c[1] for c in r.checks if c[0] == "FAIL"}
    assert {"gdunit4", "odiff"} <= failed, r.stdout
    for n in REQUIRED:
        assert r.check(n) is not None, f"every required check is still reported: {n}"
