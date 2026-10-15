"""AC-00.17 (render limits via out.Run) and AC-00.18 (exception -> rc 3). Layer: unit (R-01: harness.out).

The only public surface used is `out.Run(verb, argv, project=None)` with finding/stat/check/finish
(contract 2.9); the rendered text is read back from summary.txt in the run dir, which must equal stdout.
"""
import importlib
import json
import re
from pathlib import Path

import pytest

RE_FINDING = re.compile(r"^(?P<loc>\S+): \[(?P<rule>[^\]]+)\] (?P<sev>error|warning|info): (?P<msg>.*)$")
RE_TRUNC = re.compile(r"^\.\.\. (\d+) more findings \((\d+) errors, (\d+) warnings\) in findings\.jsonl$")


class _LazyOut:
    """Attribute access imports harness.out, so a missing module fails the test rather than collection/setup."""

    def __getattr__(self, name):
        return getattr(importlib.import_module("harness.out"), name)


@pytest.fixture
def out(monkeypatch, tmp_path):
    monkeypatch.setenv("HARNESS_OUT", str(tmp_path / "out"))
    monkeypatch.delenv("HARNESS_PROJECT", raising=False)
    return _LazyOut()


def newest_run(tmp_path, verb="unitverb"):
    dirs = sorted((tmp_path / "out").glob(f"*-{verb}-*"))
    assert dirs, f"no run dir under {tmp_path / 'out'}"
    return dirs[-1]


def finish_with(out, tmp_path, fill, argv=None):
    with out.Run("unitverb", argv or ["unitverb"], None) as r:
        fill(r)
        rc = r.finish("unit reason")
    d = newest_run(tmp_path)
    text = (d / "summary.txt").read_text()
    return rc, text.splitlines(), d


def test_ac_00_17_hundred_findings_fit_in_40_lines(out, tmp_path, capsys):
    def fill(r):
        for i in range(60):
            r.finding(f"res://s/f{i:03d}.gd", i + 1, "lint.demo", "error", f"error number {i}")
        for i in range(40):
            r.finding(f"res://s/g{i:03d}.gd", i + 1, "lint.demo", "warning", f"warning number {i}")

    rc, lines, d = finish_with(out, tmp_path, fill)
    assert rc == 1
    assert capsys.readouterr().out.rstrip("\n") == "\n".join(lines).rstrip("\n"), "stdout must equal summary.txt"
    assert len(lines) <= 40
    assert lines[0].startswith("FAIL unitverb ")
    assert lines[-1].startswith("log: ")
    shown = [RE_FINDING.match(x) for x in lines if RE_FINDING.match(x)]
    sev = [m.group("sev") for m in shown]
    assert sev == sorted(sev, key=["error", "warning", "info"].index), "errors before warnings"
    shown_e, shown_w = sev.count("error"), sev.count("warning")
    trunc = [RE_TRUNC.match(x) for x in lines if RE_TRUNC.match(x)]
    assert len(trunc) == 1, "100 findings cannot fit in 40 lines: need one truncation line"
    k, e, w = map(int, trunc[0].groups())
    assert e == 60 - shown_e and w == 40 - shown_w and k == e + w
    errs = [m.group("loc") for m in shown if m.group("sev") == "error"]
    assert errs == sorted(errs), "errors ordered by path"
    rows = [json.loads(x) for x in (d / "findings.jsonl").read_text().splitlines() if x.strip()]
    assert len(rows) == 100, "findings.jsonl is uncapped"
    run = json.loads((d / "run.json").read_text())
    assert run["findings_total"] == 100 and run["truncated"] is True
    assert run["counts"] == {"error": 60, "warning": 40, "info": 0}


def test_ac_00_17_duplicates_collapse_with_count(out, tmp_path):
    def fill(r):
        for _ in range(3):
            r.finding("res://a.gd", 5, "lint.demo", "error", "same message")
        r.finding("res://a.gd", 6, "lint.demo", "error", "other message")

    rc, lines, d = finish_with(out, tmp_path, fill)
    same = [x for x in lines if "same message" in x]
    assert len(same) == 1 and re.search(r" \(x3\)$", same[0]), same
    assert len([x for x in lines if "other message" in x]) == 1
    assert len(list((d / "findings.jsonl").read_text().splitlines())) == 4


def test_ac_00_17_long_lines_are_cut_to_240(out, tmp_path):
    def fill(r):
        r.finding("res://a.gd", 1, "lint.demo", "error", "x" * 600)
        r.stat("note", "y" * 600)

    rc, lines, d = finish_with(out, tmp_path, fill)
    assert all(len(x) <= 240 for x in lines), [len(x) for x in lines]
    assert any(x.endswith("...") for x in lines)


def test_ac_00_17_warnings_only_gives_warn(out, tmp_path):
    def fill(r):
        r.finding("res://a.gd", 1, "lint.demo", "warning", "just a warning")

    rc, lines, d = finish_with(out, tmp_path, fill)
    assert rc == 5 and lines[0].startswith("WARN unitverb ")


def test_ac_00_17_clean_run_passes_and_info_does_not_change_verdict(out, tmp_path):
    def fill(r):
        r.finding(None, None, "godot.leak", "info", "1 instance leaked")

    rc, lines, d = finish_with(out, tmp_path, fill)
    assert rc == 0 and lines[0].startswith("PASS unitverb ")
    assert any(x.startswith("-: [godot.leak] info:") for x in lines)


def test_ac_00_17_check_and_stat_lines_render_in_grammar_order(out, tmp_path):
    def fill(r):
        r.stat("files", "3 .gd")
        r.check("OK", "thing one", "fine")
        r.check("SKIP", "autoload Rng", "not shipped")

    rc, lines, d = finish_with(out, tmp_path, fill)
    assert "files: 3 .gd" in lines
    assert "OK   thing one: fine" in lines or any(re.match(r"^OK +thing one: fine$", x) for x in lines)
    assert any(re.match(r"^SKIP +autoload Rng: not shipped$", x) for x in lines)
    assert lines.index("files: 3 .gd") < min(i for i, x in enumerate(lines) if x.startswith("OK "))


def test_ac_00_18_exception_in_body_is_rc_3_with_traceback(out, tmp_path):
    try:
        with out.Run("unitverb", ["unitverb"], None):
            raise RuntimeError("boom-marker")
    except (RuntimeError, SystemExit):
        pass  # the context manager may swallow, re-raise or exit; the run dir is the contract
    d = newest_run(tmp_path)
    lines = (d / "summary.txt").read_text().splitlines()
    assert re.match(r"^ERROR unitverb internal: ", lines[0]), lines[0]
    assert lines[-1].startswith("log: ")
    run = json.loads((d / "run.json").read_text())
    assert run["rc"] == 3 and run["verdict"] == "ERROR"
    tb = (d / "traceback.txt").read_text()
    assert "RuntimeError" in tb and "boom-marker" in tb
