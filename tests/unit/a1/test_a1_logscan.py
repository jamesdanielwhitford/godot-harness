"""AC-01.26: logscan strips ANSI and falls back to the res://F:L token in the matched line (R-06). Layer: unit."""
import importlib
from pathlib import Path

import pytest

LOGS = Path(__file__).resolve().parents[2] / "fixtures" / "logs"


def scan(text, extra_ignore=()):
    """Lazy import so a missing module fails the test (not collection)."""
    return importlib.import_module("harness.logscan").scan(text, list(extra_ignore))


def test_ac_01_26_ansi_is_stripped_before_matching():
    out = scan("\x1b[1mERROR: x\x1b[0m\n")
    assert [f["rule"] for f in out] == ["godot.error"]
    assert "\x1b" not in out[0]["message"]


def test_ac_01_26_location_falls_back_to_token_in_matched_line():
    out = scan("ERROR: res://a.tscn:7 - Parse Error: y\n")
    assert len(out) == 1
    assert (out[0]["path"], out[0]["line"], out[0]["severity"]) == ("res://a.tscn", 7, "error")


def test_ac_01_26_fixture_log_with_both():
    out = scan((LOGS / "ansi_location.log").read_text())
    assert sorted((f["path"], f["line"]) for f in out if f["path"]) == [("res://a.tscn", 7)]
    assert len(out) == 2 and all(f["rule"] == "godot.error" for f in out)


def test_ac_01_26_cpp_locations_are_never_used():
    out = scan("ERROR: boom\n   at: crash (core/os/os.cpp:100)\n")
    assert out[0]["path"] is None and out[0]["line"] is None
