"""Per-project Godot LSP daemon: state file, spawn, readiness, stop (spec 2.2, 2.5, 3.7). Godot is only started through
harness.godot.spawn."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import signal
import socket
import time
from pathlib import Path

from .. import pins
from . import lsp_client


def state_dir() -> Path:
    return pins.cache_dir() / "lsp"


def key_for(project: Path) -> str:
    return hashlib.sha256(str(Path(project).resolve()).encode()).hexdigest()[:12]


def state_file(project: Path) -> Path:
    return state_dir() / f"{key_for(project)}.json"


def read_state(project: Path):
    try:
        return json.loads(state_file(project).read_text())
    except (OSError, ValueError):
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # reap a zombie child of ours
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    return True


def _port_open(port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def status(project: Path):
    """-> (state 'running'|'stopped'|'stale', state dict or None). Stale state files are removed."""
    st = read_state(project)
    if st is None:
        return "stopped", None
    if _alive(int(st.get("pid", 0))) and lsp_client.ready(int(st["port"]), Path(project).resolve(), 0.5):
        return "running", st
    try:
        state_file(project).unlink()
    except OSError:
        pass
    return "stale", st


def running_state(project: Path):
    """Cheap check used by the hook: state dict when a daemon of this project answers, else None."""
    st = read_state(project)
    if st is None:
        return None
    if _alive(int(st.get("pid", 0))) and _port_open(int(st["port"]), 0.3):
        return st
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _last_line(log: Path) -> str:
    try:
        lines = [ln for ln in log.read_text(errors="replace").splitlines() if ln.strip()]
        return lines[-1][:150] if lines else "(empty log)"
    except OSError:
        return "(no log)"


def start(run, project: Path):
    """Start (or reuse) the daemon. -> state dict, or None after adding a lint.lsp-daemon error finding."""
    from .. import godot
    project = Path(project).resolve()
    st_name, st = status(project)
    if st_name == "running":
        run.extra["lsp_already_running"] = True
        return st
    godot.ensure_imported(run, project)
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    key = key_for(project)
    log = d / f"{key}.log"
    port = free_port()
    p = godot.spawn(run, "lsp_start", project, ["--editor", "--lsp-port", str(port)], log)
    timeout = godot.timeout_for(run, "lsp_start", project)
    t0 = time.monotonic()
    ok = False
    while time.monotonic() - t0 < timeout:
        if p.poll() is not None:
            break
        if _port_open(port, 0.3) and lsp_client.ready(port, project, 2.0):
            ok = True
            break
        time.sleep(0.15)
    godot.record_spawn(run, p, ok, timed_out=not ok and p.poll() is None)
    if not ok:
        reason = "daemon exited early" if p.poll() is not None else f"daemon not ready within {timeout:g}s"
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            p.wait(timeout=3)
        except Exception:
            pass
        run.finding(None, None, "lint.lsp-daemon", "error", f"{reason}; last log line: {_last_line(log)}")
        return None
    st = {"schema": "harness.lsp/1", "pid": p.pid, "pgid": p.pid, "port": port, "project": str(project),
          "godot": os.path.realpath(p.harness_argv[0]), "version": (run.godot_info or {}).get("version", ""),
          "started_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "log": str(log)}
    state_file(project).write_text(json.dumps(st, indent=1) + "\n")
    st["_popen"] = p
    return st


def _kill_state(st: dict):
    pid = int(st.get("pid", 0))
    pgid = int(st.get("pgid", pid) or pid)
    for sig, wait in ((signal.SIGTERM, 3.0), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        t0 = time.monotonic()
        while time.monotonic() - t0 < wait:
            if not _alive(pid):
                return
            time.sleep(0.05)


def stop(project: Path) -> bool:
    """Stop this project's daemon; True when one was running (or a stale file existed)."""
    st = read_state(project)
    if st is None:
        return False
    _kill_state(st)
    try:
        state_file(project).unlink()
    except OSError:
        pass
    return True


def stop_all() -> int:
    n = 0
    d = state_dir()
    if not d.is_dir():
        return 0
    for f in sorted(d.glob("*.json")):
        try:
            st = json.loads(f.read_text())
        except (OSError, ValueError):
            st = None
        if st:
            _kill_state(st)
            n += 1
        try:
            f.unlink()
        except OSError:
            pass
    return n
