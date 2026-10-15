"""Self-checks of tests/helpers/h.py (parser and assert_contract) on synthetic runs. They pass without an implementation by
design: they keep the shared helper honest so contract tests fail only because of the code under test."""
import json
from pathlib import Path

import pytest

from helpers.h import Result, assert_contract, parse_stdout, RE_RULE_ID, validate_run_json


def make_run(tmp_path, stdout, verb="check", rc=1, rows=(), counts=None, truncated=False, argv=None):
    out = tmp_path / "out"
    rid = f"20261015T142233Z-{verb}-a3f9"
    d = out / rid
    d.mkdir(parents=True)
    lines = stdout.splitlines()
    v = lines[0].split(" ", 2)
    counts = counts or {s: sum(1 for r in rows if r["severity"] == s) for s in ("error", "warning", "info")}
    run = {"schema": "harness.run/1", "run_id": rid, "verb": verb, "argv": argv or [verb], "cwd": "/x", "project": None,
           "started_at": "2026-10-15T14:22:33Z", "duration_s": 1.0, "rc": rc, "verdict": v[0], "reason": v[2],
           "counts": counts, "findings_total": len(rows), "truncated": truncated, "invocations": []}
    (d / "run.json").write_text(json.dumps(run))
    (d / "summary.txt").write_text(stdout)
    (d / "findings.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "latest").symlink_to(rid)
    (tmp_path / ".gdignore").write_text("")
    stdout = stdout.replace("log: LOG/", f"log: {d}/")
    (d / "summary.txt").write_text(stdout)
    p = parse_stdout(stdout)
    return Result(rc=rc, stdout=stdout, stderr="", argv=argv or ["h", verb], cwd=tmp_path, wall=0.1, lines=p["lines"],
                  verdict=p["verdict"], verb=p["verb"], reason=p["reason"], stats=p["stats"], stat_items=p["stat_items"],
                  checks=p["checks"], findings=p["findings"], trunc=p["trunc"], log_dir=d, kinds=p["kinds"])


def row(sev="error", rule="godot.parse-error", path="res://a.gd", line=1):
    return {"path": path, "line": line, "rule": rule, "severity": sev, "message": "m", "hint": None, "source": "scan", "invocation": 1}


GOOD = ("FAIL check 1 error in 1 files (0.1s)\nproject: /p\nimport: fresh\n"
        "res://a.gd:1: [godot.parse-error] error: m\nlog: LOG/\n")


def test_parse_stdout_classifies_every_line_kind():
    p = parse_stdout("FAIL check x\nproject: /p\nOK   a b.c: fine\nSKIP autoload Rng: not shipped\n"
                     "res://a.gd:12: [godot.parse-error] error: m (hint: h) (x2)\n-: [api.not-found] error: q\n"
                     "... 3 more findings (2 errors, 1 warnings) in findings.jsonl\nlog: .harness/out/x/\n")
    assert p["kinds"] == ["stat", "check", "check", "finding", "finding", "trunc", "log"]
    f = p["findings"][0]
    assert (f["path"], f["line"], f["hint"], f["count"]) == ("res://a.gd", 12, "h", 2)
    assert p["findings"][1]["path"] is None
    assert p["checks"][0][1] == "a b.c"


def test_rule_id_pattern_allows_upper_case_r1_5_ids():
    for ok in ("class-KinematicBody2D", "godot.parse-error", "syn-yield", "a0"):
        assert RE_RULE_ID.match(ok)
    for bad in ("Godot.x", "-x", ".x", ""):
        assert not RE_RULE_ID.match(bad)


def test_assert_contract_accepts_a_well_formed_run(tmp_path):
    assert_contract(make_run(tmp_path, GOOD, rows=[row()]))


def test_assert_contract_rejects_fail_without_error(tmp_path):
    bad = GOOD.replace("res://a.gd:1: [godot.parse-error] error: m\n", "")
    with pytest.raises(AssertionError):
        assert_contract(make_run(tmp_path, bad, rows=[]))


def test_assert_contract_rejects_wrong_order(tmp_path):
    bad = GOOD.replace("project: /p\nimport: fresh\n", "") .replace("log:", "files: 1 .gd\nlog:")
    with pytest.raises(AssertionError):
        assert_contract(make_run(tmp_path, bad, rows=[row()]))


def test_assert_contract_rejects_summary_mismatch(tmp_path):
    r = make_run(tmp_path, GOOD, rows=[row()])
    (r.log_dir / "summary.txt").write_text("PASS other\n")
    with pytest.raises(AssertionError):
        assert_contract(r)


def test_assert_contract_rejects_over_41_lines(tmp_path):
    many = "".join(f"res://a.gd:{i}: [godot.parse-error] error: m{i}\n" for i in range(1, 45))
    text = "FAIL check many\n" + many + "log: LOG/\n"
    with pytest.raises(AssertionError):
        assert_contract(make_run(tmp_path, text, rows=[row(line=i) for i in range(1, 45)]))


def test_run_json_schema_validator_flags_missing_keys():
    assert validate_run_json({"schema": "harness.run/1"})
