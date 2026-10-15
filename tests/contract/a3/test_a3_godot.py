"""A3 contract tests that need the engine: oracle, h check integration, LSP daemon, selftest.
AC-03.22 .. 03.28. Every LSP test isolates its daemons with a private HARNESS_CACHE and always runs `lsp stop --all`."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from a3_common import CASES, fresh, lint, lint_findings, write
from helpers.h import assert_contract, live_processes_mentioning, run_h, tree_hash

pytestmark = pytest.mark.godot

BAD_GD = "extends Node\nfunc _ready() -> void:\n\tvar a: int = 1\n\tvar b: int = = 2\n"
O_GD = 'extends Node\nfunc _ready():\n\tprint(rand_range(0,1))\n\tconnect("tree_exited", self, "_x")\n'


def _env(tmp_path, **kw):
    e = {"HARNESS_CACHE": str(tmp_path / "cache"), "HARNESS_OUT": str(tmp_path / "out")}
    e.update(kw)
    return e


def lsp(tmp_path, *args, cwd=None, timeout=90, **kw):
    return run_h("lsp", *args, cwd=cwd, env=_env(tmp_path, **kw), timeout=timeout)


def _stop_all(tmp_path):
    run_h("lsp", "stop", "--all", env=_env(tmp_path), timeout=30)


def _gone(needle: str, secs: float = 5.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        if not live_processes_mentioning(needle):
            return True
        time.sleep(0.2)
    return not live_processes_mentioning(needle)


# ---- AC-03.22 oracle ----------------------------------------------------------------------------------------
def test_ac_03_22_oracle_reports_converter_rewrites(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/o.gd", O_GD)
    before = tree_hash(p)
    r = assert_contract(lint(p, "--godot3-oracle", "scripts/o.gd", cwd=p, timeout=60))
    assert r.rc == 1, str(r)
    o = {f["line"]: f for f in lint_findings(r, "lint.g3-oracle") if f["path"] == "res://scripts/o.gd"}
    assert 3 in o and "randf_range" in o[3]["hint"], o
    assert 4 in o and "Callable(" in o[4]["hint"], o
    assert all(f["severity"] == "warning" for f in o.values())
    inv = r.invocations()
    assert [i["kind"] for i in inv] == ["oracle"], inv
    assert tree_hash(p) == before, "oracle must not touch project files"
    assert not (p / ".godot").exists(), "oracle must not create .godot/ in the project"
    assert r.wall <= 10, f"{r.wall:.1f}s"


def test_ac_03_22_oracle_needs_paths(tmp_path):
    p = fresh(tmp_path)
    r = assert_contract(lint(p, "--godot3-oracle"))
    assert r.rc == 2 and r.lines[0].startswith("ERROR lint usage: "), str(r)


def test_ac_03_22_oracle_without_godot_is_rc4(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/o.gd", O_GD)
    r = assert_contract(lint(p, "--godot3-oracle", "scripts/o.gd", cwd=p, env={"HARNESS_GODOT": "/nonexistent/godot"}))
    assert r.rc == 4 and r.verdict == "ERROR", str(r)


# ---- AC-03.23 h check integration ---------------------------------------------------------------------------
def test_ac_03_23_check_shows_lint_findings(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/y.gd", CASES["c04_yield"][0])
    r = assert_contract(run_h("check", "--project", p, env={"HARNESS_OUT": str(tmp_path / "out")}, timeout=150))
    assert r.rc == 1 and r.verdict == "FAIL", str(r)
    assert r.matches(r"\[syn-yield\]"), str(r)


# ---- AC-03.24 LSP lifecycle ---------------------------------------------------------------------------------
def test_ac_03_24_lsp_lifecycle(tmp_path):
    p = fresh(tmp_path)
    try:
        r1 = assert_contract(lsp(tmp_path, "start", "--project", p))
        assert r1.rc == 0, str(r1)
        pid, port = r1.stats["pid"], r1.stats["port"]
        assert pid.isdigit() and port.isdigit()
        r2 = assert_contract(lsp(tmp_path, "start", "--project", p))
        assert r2.rc == 0 and r2.stats["pid"] == pid and "already running" in r2.reason, str(r2)
        st = assert_contract(lsp(tmp_path, "status", "--project", p))
        assert st.rc == 0 and st.stats["state"] == "running" and st.stats["pid"] == pid, str(st)
        sp = assert_contract(lsp(tmp_path, "stop", "--project", p))
        assert sp.rc == 0, str(sp)
        assert _gone(str(p)), f"daemon survived stop: {live_processes_mentioning(str(p))}"
        st2 = assert_contract(lsp(tmp_path, "status", "--project", p))
        assert st2.rc == 0 and st2.stats["state"] == "stopped", str(st2)
        sp2 = assert_contract(lsp(tmp_path, "stop", "--project", p))
        assert sp2.rc == 0                                              # stop when not running is fine
    finally:
        _stop_all(tmp_path)


def test_ac_03_24_stale_state_file_is_reported_and_removed(tmp_path):
    p = fresh(tmp_path)
    dead = subprocess.Popen(["true"])
    dead.wait()
    key = hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:12]
    d = tmp_path / "cache" / "lsp"
    d.mkdir(parents=True)
    sf = d / f"{key}.json"
    sf.write_text(json.dumps({"schema": "harness.lsp/1", "pid": dead.pid, "pgid": dead.pid, "port": 1, "project": str(p.resolve()),
                              "godot": "/nonexistent", "version": "x", "started_at": "2026-01-01T00:00:00Z",
                              "log": str(d / f"{key}.log")}))
    try:
        st = assert_contract(lsp(tmp_path, "status", "--project", p))
        assert st.rc == 0 and st.stats["state"] == "stale", str(st)
        assert not sf.exists(), "stale state file must be removed"
        st2 = assert_contract(lsp(tmp_path, "status", "--project", p))
        assert st2.stats["state"] == "stopped"
    finally:
        _stop_all(tmp_path)


# ---- AC-03.25 lsp diag --------------------------------------------------------------------------------------
def test_ac_03_25_diag_without_daemon_is_rc4(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/bad.gd", BAD_GD)
    r = assert_contract(lsp(tmp_path, "diag", "--project", p, str(p / "scripts" / "bad.gd")))
    assert r.rc == 4 and r.verdict == "ERROR" and "lsp daemon not running" in r.stdout, str(r)


def test_ac_03_25_diag_finds_parse_error_and_clean_file_and_speed(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/bad.gd", BAD_GD)
    try:
        assert lsp(tmp_path, "start", "--project", p).rc == 0
        r = assert_contract(lsp(tmp_path, "diag", "--project", p, str(p / "scripts" / "bad.gd")))
        assert r.rc == 1 and r.matches(r"^res://scripts/bad\.gd:4: \[lint\.lsp\] error:"), str(r)
        ok = assert_contract(lsp(tmp_path, "diag", "--project", p, str(p / "scripts" / "player.gd")))
        assert ok.rc == 0 and ok.verdict == "PASS", str(ok)
        files = [str(p / f) for f in ("scripts/player.gd", "scripts/base.gd", "scripts/rng.gd", "scripts/input_remap.gd", "sim/world.gd")]
        t0 = time.monotonic()
        five = assert_contract(lsp(tmp_path, "diag", "--project", p, *files))
        wall = time.monotonic() - t0
        assert five.rc == 0, str(five)
        assert wall <= 1.5, f"5 files on a warm daemon took {wall:.2f}s"
    finally:
        _stop_all(tmp_path)


def test_ac_03_25_oneshot_gives_same_finding_and_leaves_no_daemon(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/bad.gd", BAD_GD)
    try:
        r = assert_contract(lsp(tmp_path, "diag", "--oneshot", "--project", p, str(p / "scripts" / "bad.gd"), timeout=120))
        assert r.rc == 1 and r.matches(r"^res://scripts/bad\.gd:4: \[lint\.lsp\] error:"), str(r)
        assert _gone(str(p)), "oneshot left a daemon running"
        st = assert_contract(lsp(tmp_path, "status", "--project", p))
        assert st.stats["state"] == "stopped"
    finally:
        _stop_all(tmp_path)


# ---- AC-03.26 hook + LSP ------------------------------------------------------------------------------------
def test_ac_03_26_hook_without_daemon_says_not_running(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/bad.gd", BAD_GD)
    r = assert_contract(lint(p, "--hook", "scripts/bad.gd", cwd=p, env=_env(tmp_path)))
    assert r.stats.get("lsp") == "not running" and r.invocations() == [], str(r)


def test_ac_03_26_hook_with_daemon_used_and_off_by_config(tmp_path):
    p = fresh(tmp_path)
    write(p, "scripts/bad.gd", BAD_GD)
    try:
        assert lsp(tmp_path, "start", "--project", p).rc == 0
        r = assert_contract(lint(p, "--hook", "scripts/bad.gd", cwd=p, env=_env(tmp_path)))
        assert r.stats.get("lsp") == "used", str(r)
        assert r.has_finding("lint.lsp", "res://scripts/bad.gd", 4, "error"), str(r)
        write(p, "harness.toml", "[lint]\nlsp_in_hook = false\n")
        r2 = assert_contract(lint(p, "--hook", "scripts/bad.gd", cwd=p, env=_env(tmp_path)))
        assert r2.stats.get("lsp") == "off" and not r2.has_finding("lint.lsp"), str(r2)
    finally:
        _stop_all(tmp_path)


# ---- AC-03.27 two daemons -----------------------------------------------------------------------------------
def test_ac_03_27_two_copies_two_daemons_and_stop_all(tmp_path):
    a = fresh(tmp_path, sub="a")
    b = fresh(tmp_path, sub="b")
    try:
        ra = assert_contract(lsp(tmp_path, "start", "--project", a))
        rb = assert_contract(lsp(tmp_path, "start", "--project", b))
        assert ra.rc == 0 and rb.rc == 0, f"{ra}\n{rb}"
        assert ra.stats["port"] != rb.stats["port"] and ra.stats["pid"] != rb.stats["pid"]
        sa = lsp(tmp_path, "status", "--project", a)
        sb = lsp(tmp_path, "status", "--project", b)
        assert sa.stats["state"] == "running" and sb.stats["state"] == "running"
        stop = assert_contract(run_h("lsp", "stop", "--all", env=_env(tmp_path), cwd=tmp_path, timeout=30))
        assert stop.rc == 0, str(stop)
        assert _gone(str(a)) and _gone(str(b)), "stop --all left a daemon"
        assert lsp(tmp_path, "status", "--project", a).stats["state"] == "stopped"
        assert lsp(tmp_path, "status", "--project", b).stats["state"] == "stopped"
    finally:
        _stop_all(tmp_path)


# ---- AC-03.28 selftest --------------------------------------------------------------------------------------
@pytest.mark.slow
def test_ac_03_28_selftest_area_a3(tmp_path):
    t0 = time.monotonic()
    r = assert_contract(run_h("selftest", "--area", "A3", env={"HARNESS_OUT": str(tmp_path / "out")}, timeout=300))
    wall = time.monotonic() - t0
    assert r.rc == 0, str(r)
    assert re.match(r"^27 total, 27 caught, 0 missed", r.stats["faults"]), r.stats
    assert re.match(r"^3 total, 3 pass, 0 false-positive", r.stats["clean"]), r.stats
    assert wall <= 180, f"{wall:.0f}s"
    m = json.loads(r.artifact("matrix.json").read_text())
    entries = m if isinstance(m, list) else m.get("entries", m)
    assert len(entries) == 30
