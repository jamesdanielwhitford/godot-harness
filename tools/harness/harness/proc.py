"""Timeout-safe subprocess for non-Godot tools (odiff, git, compare, xvfb checks). Contract 2.8, 3.1."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass
class Result:
    rc: int
    stdout: str
    timed_out: bool
    duration_s: float
    error: str | None = None


def kill_group(p: subprocess.Popen, grace: float = 3.0):
    """SIGTERM the process group, SIGKILL after `grace` seconds."""
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            p.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def run(argv, timeout: float = 30, cwd=None, env=None, input: str | None = None) -> Result:
    """Run argv (stdin /dev/null unless input), combined stdout+stderr, own process group, hard timeout."""
    t0 = time.monotonic()
    try:
        p = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env, text=True, errors="replace",
                             stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        return Result(127, "", False, time.monotonic() - t0, str(e))
    timed_out = False
    try:
        out, _ = p.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group(p, grace=1.0)
        try:
            out, _ = p.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            out = ""
    rc = p.returncode if p.returncode is not None else -9
    if rc < 0:
        rc = 128 - rc
    if timed_out:
        rc = 124
    return Result(rc, out or "", timed_out, time.monotonic() - t0)
