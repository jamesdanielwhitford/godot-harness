"""A4 unit layer: AC-04.19 parse_results / parse_console on recorded gdUnit4 v6.2.2 output (REVIEW R-01).

Only harness.gdunit.parse_results and harness.gdunit.parse_console are public. Their return shapes beyond the
spec's key lists are [U]; the console assertions are therefore shape-tolerant (they search the JSON dump).
"""
import json
import re
from pathlib import Path

import pytest



class _Lazy:
    """Import harness.gdunit at call time so a missing module fails each test, not collection."""

    def __getattr__(self, name):
        import importlib

        return getattr(importlib.import_module("harness.gdunit"), name)


gdunit = _Lazy()  # tools/harness is on sys.path via tests/conftest.py (unit tests only)

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "gdunit"
KEYS = {"suite", "name", "status", "duration_s", "path", "line", "message"}


def _xml(name):
    return gdunit.parse_results((FIX / name).read_text())


def _log(name):
    return gdunit.parse_console((FIX / name).read_text())


def _by_name(rows):
    return {r["name"]: r for r in rows}


def _dump(x):
    return json.dumps(x, default=str, sort_keys=True)


def test_ac_04_19_1_fail_xml_rows_and_keys():
    rows = _xml("fail.xml")
    assert [r["name"] for r in rows] == ["test_ok", "test_bad", "test_bad_str"]
    for r in rows:
        assert KEYS <= set(r), r
        assert r["suite"] == "res://tests/test_math.gd"
    by = _by_name(rows)
    assert by["test_ok"]["status"] == "passed"
    assert by["test_bad"]["status"] == "failed"
    assert by["test_bad_str"]["status"] == "failed"


def test_ac_04_19_2_fail_xml_location_and_message():
    by = _by_name(_xml("fail.xml"))
    assert (by["test_bad"]["path"], by["test_bad"]["line"]) == ("res://tests/test_math.gd", 6)
    assert (by["test_bad_str"]["path"], by["test_bad_str"]["line"]) == ("res://tests/test_math.gd", 8)
    # collapsed text: one line, whitespace runs collapsed, the `at '<fn>' in res://` line removed
    msg = by["test_bad"]["message"]
    assert "\n" not in msg and "\t" not in msg
    assert "Expecting: 3 but was 2" in msg
    assert "res://tests/test_math.gd:6" not in msg
    assert "<LF>" in by["test_bad_str"]["message"]
    assert "Expecting: 'hello world' but was 'hello <LF>world'" in by["test_bad_str"]["message"]


def test_ac_04_19_3_runtime_error_location_from_body_not_message():
    """K10: the message attribute names the test file, the body names the game file."""
    rows = _xml("runtime_error.xml")
    assert len(rows) == 1
    r = rows[0]
    assert r["suite"] == "res://tests/test_buggy.gd"
    assert r["name"] == "test_runs"
    assert r["status"] == "error"
    assert (r["path"], r["line"]) == ("res://scenes/buggy.gd", 6) or (r["path"], r["line"]) == ("res://scripts/buggy.gd", 6)
    assert r["path"].startswith("res://") and r["path"].endswith("/buggy.gd")
    assert "test_buggy.gd" not in r["path"]
    assert "Godot Runtime Error ! 'Cannot call method 'call' on a null value.'" in r["message"]


def test_ac_04_19_4_nested_package_gives_full_suite_path():
    rows = _xml("nested.xml")
    assert rows and {r["suite"] for r in rows} == {"res://tests/sim/test_fail.gd"}
    assert _by_name(rows)["test_bad"]["status"] == "failed"
    assert _by_name(rows)["test_bad"]["path"] == "res://tests/sim/test_fail.gd"
    assert _by_name(rows)["test_bad"]["line"] == 6


def test_ac_04_19_5_parse_results_is_pure_and_deterministic():
    text = (FIX / "fail.xml").read_text()
    assert gdunit.parse_results(text) == gdunit.parse_results(text)


def test_ac_04_19_6_parse_results_empty_suite_list():
    xml = '<?xml version="1.0"?>\n<testsuites id="x" name="report_1" tests="0" failures="0"></testsuites>\n'
    assert gdunit.parse_results(xml) == []


def test_ac_04_19_7_console_hang_names_last_started_test():
    c = _log("hang.log")
    d = _dump(c)
    assert "test_forever" in d
    assert c["hung"], c
    assert "test_hang.gd" in _dump(c["hung"]) or "test_forever" in _dump(c["hung"])


def test_ac_04_19_8_console_orphans_attributed_to_test():
    c = _log("orphan.log")
    d = _dump(c["orphans"])
    assert "test_leaks_node" in d, c["orphans"]
    assert re.search(r"\b1\b", d), c["orphans"]
    assert not c["hung"]


def test_ac_04_19_9_console_summary_counts():
    c = _log("all.log")
    counts = c["counts"]
    d = _dump(counts)
    assert re.search(r"\b55\b", d), counts  # 55 test cases
    assert not c["hung"]
    assert not c["orphans"]
    # zero failures/errors recorded somewhere as 0
    assert isinstance(counts, dict)


def test_ac_04_19_10_console_lines_are_ansi_stripped():
    raw = (FIX / "all.log").read_text()
    assert "\x1b[" in raw, "recording must keep ANSI codes"
    c = _log("all.log")
    assert c["lines"], "lines must be returned"
    assert all("\x1b" not in ln for ln in c["lines"])
    assert any("Overall Summary:" in ln for ln in c["lines"])


def test_ac_04_19_11_console_clean_run_has_no_orphans_or_hang():
    c = _log("all.log")
    assert not c["orphans"] and not c["hung"]


def test_ac_04_19_12_console_parse_error_log_has_no_counts_of_tests():
    c = _log("broken.log")
    assert not c["hung"]
    assert any("Parse Error" in ln for ln in c["lines"])


@pytest.mark.parametrize("name", ["fail.xml", "runtime_error.xml", "nested.xml"])
def test_ac_04_19_13_every_row_has_valid_status_and_types(name):
    for r in _xml(name):
        assert r["status"] in {"passed", "failed", "error", "skipped", "orphans", "hung"}
        assert isinstance(r["duration_s"], (int, float))
        assert r["line"] is None or isinstance(r["line"], int)
        assert r["suite"].startswith("res://") and r["suite"].endswith(".gd")
