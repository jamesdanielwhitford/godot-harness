"""AC-00.16: logscan.scan on the section 3.4 excerpts (tests/fixtures/logs/*.log). Layer: unit (R-01 allowlist)."""
import importlib
from pathlib import Path

import pytest

LOGS = Path(__file__).resolve().parents[2] / "fixtures" / "logs"
ALL_LOGS = sorted(p.name for p in LOGS.glob("*.log"))


def scan(text, extra_ignore=()):
    """Lazy import so a missing module fails the test (not collection)."""
    return importlib.import_module("harness.logscan").scan(text, list(extra_ignore))


def read(name):
    return (LOGS / name).read_text()


def sig(findings):
    return sorted((f["rule"], f["path"], f["line"], f["severity"]) for f in findings)


def test_ac_00_16_parse_error_gives_parse_error_and_script_load_failed():
    assert sig(scan(read("parse_error.log"))) == sorted([
        ("godot.parse-error", "res://bad.gd", 3, "error"),
        ("godot.script-load-failed", "res://bad.gd", None, "error"),
    ])


def test_ac_00_16_runtime_script_error():
    assert sig(scan(read("runtime_error.log"))) == [("godot.script-error", "res://rt.gd", 4, "error")]


def test_ac_00_16_push_error_is_godot_error_at_backtrace_frame():
    assert sig(scan(read("push_error.log"))) == [("godot.error", "res://pe.gd", 4, "error")]


def test_ac_00_16_push_warning_is_godot_warning():
    assert sig(scan(read("push_warning.log"))) == [("godot.warning", "res://pe.gd", 3, "warning")]


def test_ac_00_16_leak_is_info_without_location():
    assert sig(scan(read("leak.log"))) == [("godot.leak", None, None, "info")]


def test_ac_00_16_banner_hooks_and_benign_lines_give_nothing():
    assert scan(read("banner.log")) == []
    assert scan(read("benign.log")) == []


def test_ac_00_16_crash_lines():
    rules = {f["rule"] for f in scan(read("crash.log"))}
    assert "godot.crash" in rules
    assert "godot.error" in rules


def test_ac_00_16_rule_order_first_match_wins():
    found = scan(read("rule_order.log"))
    by_rule = {f["rule"]: f for f in found}
    assert set(by_rule) == {"godot.parent-vanished", "godot.vanished", "godot.load-failed", "godot.warning"}
    assert by_rule["godot.parent-vanished"]["severity"] == "error"
    assert by_rule["godot.vanished"]["severity"] == "error"
    assert by_rule["godot.load-failed"]["path"].startswith("res://a.tres")
    assert by_rule["godot.warning"]["severity"] == "warning"


@pytest.mark.parametrize("name", ALL_LOGS)
def test_ac_00_16_no_finding_has_a_non_res_path(name):
    for f in scan(read(name)):
        assert f["path"] is None or f["path"].startswith("res://"), f
        assert set(f) >= {"path", "line", "rule", "severity", "message"}


def test_ac_00_16_non_protected_rule_honours_extra_ignore():
    assert scan("ERROR: some noisy thing\n", ["noisy"]) == []
    assert [f["rule"] for f in scan("ERROR: other thing\n", ["noisy"])] == ["godot.error"]


def test_ac_00_16_protected_rules_ignore_extra_ignore():
    out = scan('SCRIPT ERROR: Parse Error: noisy\n  at: GDScript::reload (res://x.gd:2)\n', ["noisy"])
    assert [f["rule"] for f in out] == ["godot.parse-error"]
