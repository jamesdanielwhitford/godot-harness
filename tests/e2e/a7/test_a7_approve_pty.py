"""A7 e2e: `h trace --approve` under a pseudo-terminal (spec 07_feel.md AC-07.18, TTY half). Owner: T7.

The human-only approval path needs stdin and stdout to be a TTY, so the verb is driven through python's `pty`.
It answers `y` to every per-target question. Self-contained: only tests/helpers/h.py is imported.
"""
from __future__ import annotations

import datetime
import os
import pty
import re
import select
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from helpers.h import H, assert_contract, copy_fixture, run_h

pytestmark = [pytest.mark.godot, pytest.mark.slow]

SUITE = "res://feel/player.feel.json"


def _human_name(cwd: Path) -> str:
    r = subprocess.run(["git", "config", "user.name"], cwd=cwd, capture_output=True, text=True)
    name = r.stdout.strip()
    return name or os.environ.get("USER", "")


def _run_on_pty(argv, cwd, answers: bytes, timeout=300):
    pid, fd = pty.fork()
    if pid == 0:  # child: exec h with the tty as stdin/stdout/stderr
        os.chdir(cwd)
        env = {k: v for k, v in os.environ.items() if k not in ("HARNESS_OUT", "HARNESS_PROJECT")}
        os.execve(argv[0], argv, env)
    os.write(fd, answers)
    out = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], 1.0)
        if r:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        else:
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(status), out.decode(errors="replace")
    try:
        _, status = os.waitpid(pid, 0)
    except ChildProcessError:
        return -1, out.decode(errors="replace")
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace")


def test_ac_07_18_approve_under_a_pty_writes_the_humans_name_and_date(tmp_path):
    proj = copy_fixture("feel_min", tmp_path / "proj")
    p = run_h("trace", SUITE, "--propose", "--project", proj, timeout=240)
    assert_contract(p)
    assert p.rc in (0, 5), str(p)
    run_dir = p.require_log_dir()
    prop = run_dir / "artifacts" / "proposed_targets.json"
    assert prop.is_file()
    targets = proj / "feel" / "targets.tres"
    before = targets.read_text()
    assert before.count('approved_by = "fixture-human"') == 11

    rc, out = _run_on_pty([str(H), "trace", SUITE, "--approve", "--from", str(run_dir), "--project", str(proj)],
                          cwd=proj, answers=b"y\n" * 40)
    assert rc == 0, out
    after = targets.read_text()
    name = _human_name(proj)
    today = datetime.date.today().isoformat()
    assert after.count(f'approved_by = "{name}"') == 11, after
    assert after.count(f'approved_on = "{today}"') == 11, after
    assert "fixture-human" not in after
    # bounds come from the proposal: every target keeps a min <= max pair
    mins = re.findall(r"^min_value = (\S+)$", after, re.MULTILINE)
    maxs = re.findall(r"^max_value = (\S+)$", after, re.MULTILINE)
    assert len(mins) == len(maxs) == 11
    assert all(float(a) <= float(b) for a, b in zip(mins, maxs))
    # the approved file now gives a clean trace verdict on the same project
    r = run_h("trace", SUITE, "--project", proj, timeout=240)
    assert_contract(r)
    assert r.rc == 0, str(r)
    shutil.rmtree(proj, ignore_errors=True)
