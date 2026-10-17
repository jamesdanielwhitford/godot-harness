"""The only place that starts Godot (contract 2.8, 2.9; REVIEW R-05, R-09, R-14, R-24, R-31, R-32, R-52).

    binary(run, project) -> Path                      locate + version-check the binary (rc 4 on problems)
    run(run, kind, project, ...) -> Invocation        one Godot process: timeout, log, scan, verdict merge
    spawn(run, kind, project, args, log_path)         long-lived process (lsp_start), own session
    ensure_imported(run, project) -> str              content-based auto-import (prints `import:`)
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import logscan, out, pins, proc

DEFAULT_TIMEOUTS = {"version": 20, "import": 180, "check_only": 30, "runner": 60, "smoke": 30, "test": 300,
                    "scenario": 120, "shot": 60, "movie": 300, "doctool": 120, "oracle": 60, "lsp_start": 30}
RUNNER_KINDS = ("runner", "smoke", "scenario", "shot", "movie")
EXPECTED_RC = {"check_only": {0, 1}, "runner": {0, 1}, "smoke": {0, 1}, "scenario": {0, 1}, "shot": {0, 1},
               "movie": {0, 1}, "import": {0}, "oracle": {0}, "version": {0}, "doctool": {0}, "test": {0},
               "lsp_start": {0}}
NO_PROJECT_KINDS = ("version", "doctool")
NO_IMPORT_KINDS = ("version", "import", "doctool", "oracle", "lsp_start")
DISPLAY_FAIL_RE = re.compile(r"Unable to create DisplayServer|Xvfb failed to start|xvfb-run: error")
IMPORT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".tga", ".wav", ".ogg", ".mp3", ".glb", ".gltf",
               ".fbx", ".obj", ".ttf", ".otf", ".woff", ".woff2"}
XVFB_ARGS = ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24"]


@dataclass
class Invocation:
    n: int
    kind: str
    argv: list
    rc: int
    timed_out: bool
    duration_s: float
    log_path: Path
    scan_verdict: str
    runner_rc: int | None = None
    retried: bool = False
    display_failed: bool = False
    records: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    timeout_s: float = 0.0
    text: str = ""

    @property
    def failed(self) -> bool:
        """Hang, crash, unexpected rc or missing runner `done` (a harness.* error finding)."""
        return any(f["rule"].startswith("harness.") and f["severity"] == "error" for f in self.findings)


# ---- configuration helpers -------------------------------------------------------------------------------------
def _cfg(run, project) -> dict:
    cfg = getattr(run, "config", None)
    if cfg is None:
        from . import config
        try:
            cfg = config.load(project) if project is not None else config.defaults()
        except config.ConfigError as e:
            for m in e.messages:
                run.finding("res://harness.toml", None, "harness.config", "error", m)
            run.error(2, f"harness.toml: {e.messages[0]}"[:100])
        run.config = cfg
    return cfg


def runner_path(name) -> Path:
    s = str(name)
    if "/" in s or s.endswith(".gd"):
        return Path(s)
    return out.repo_root() / "addons" / "harness" / "runners" / f"{s}.gd"


def timeout_for(run, kind: str, project=None, explicit=None) -> float:
    cfg = _cfg(run, project)
    base = explicit if explicit is not None else cfg.get("timeouts", {}).get(kind, DEFAULT_TIMEOUTS[kind])
    try:
        scale = out.timeout_scale()
    except out.UsageError as e:
        run.error(2, f"usage: {e}")
    return float(base) * scale


# ---- binary ------------------------------------------------------------------------------------------------------
def _version_cache_file() -> Path:
    return pins.cache_dir() / "godot_version.json"


def _probe_version(path: Path) -> str:
    st = path.stat()
    key = f"{path.resolve()}|{st.st_mtime_ns}|{st.st_size}"
    cf = _version_cache_file()
    try:
        cached = json.loads(cf.read_text())
        if isinstance(cached, dict) and key in cached:
            return cached[key]
    except (OSError, ValueError):
        cached = {}
    r = proc.run([str(path), "--version"], timeout=20 * out.timeout_scale())
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    version = lines[-1] if (lines and r.rc == 0 and not r.timed_out) else ""
    if version:
        try:
            cf.parent.mkdir(parents=True, exist_ok=True)
            data = cached if isinstance(cached, dict) else {}
            data = {k: v for k, v in list(data.items())[-20:]}
            data[key] = version
            tmp = cf.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(data))
            os.replace(tmp, cf)
        except OSError:
            pass
    return version


def binary(run, project=None) -> Path:
    """HARNESS_GODOT > harness.toml godot > $HARNESS_REPO/tools/bin/godot; checks it runs and its version."""
    cfg = _cfg(run, project)
    env = os.environ.get("HARNESS_GODOT")
    if env:
        p = Path(env).expanduser()
    elif cfg["harness"].get("godot") and project is not None:
        g = Path(cfg["harness"]["godot"]).expanduser()
        p = g if g.is_absolute() else Path(project) / g
    else:
        p = out.repo_root() / "tools" / "bin" / "godot"
    if not p.is_file() or not os.access(p, os.X_OK):
        run.error(4, f"godot binary not found: {p} (run tools/bootstrap.sh)")
    want = cfg["harness"]["godot_version"]
    got = _probe_version(p)
    run.godot_info = {"path": str(p), "version": got}
    if got != want:
        shown = got or "<no output from --version>"
        run.finding(None, None, "harness.godot-version", "error", f"godot reports {shown}, harness expects {want}",
                    hint="run tools/bootstrap.sh or set godot_version in harness.toml", source="verb")
        run.error(4, f"godot version {shown} != {want} (run tools/bootstrap.sh)")
    return p


# ---- running -----------------------------------------------------------------------------------------------------
def _build_argv(g: Path, kind: str, project, args, user_args, runner, display, cwd) -> list:
    argv: list = []
    if display == "xvfb":
        argv += XVFB_ARGS
    argv.append(str(g))
    if display == "headless":
        argv.append("--headless")
    elif display == "xvfb":
        argv += ["--rendering-method", "gl_compatibility", "--audio-driver", "Dummy"]
    else:
        raise ValueError(f"unknown display {display!r}")
    if project is not None:
        argv += ["--path", str(Path(project).resolve())]
    args = [str(a) for a in args]
    if kind == "import":
        argv.append("--import")
    elif kind in RUNNER_KINDS:
        if runner is None:
            raise ValueError(f"kind {kind} needs runner=")
        argv += ["-s", str(Path(runner_path(runner)).absolute())]
    elif kind == "check_only":
        if not args:
            raise ValueError("check_only needs args=[res://file]")
        argv += ["--check-only", "-s", args[0]]
        args = args[1:]
    argv += args
    if user_args:
        argv += ["--"] + [str(a) for a in user_args]
    return argv


def _xvfb_locks() -> dict:
    d = Path("/tmp")
    res = {}
    try:
        for p in d.glob(".X*-lock"):
            res[p.name] = p.stat().st_mtime
    except OSError:
        pass
    return res


def _cleanup_xvfb(started: float):
    """After a SIGKILL: drop stale lock + socket of Xvfb servers started after `started` whose pid is dead."""
    for name, mtime in _xvfb_locks().items():
        if mtime < started - 1:
            continue
        m = re.match(r"^\.X(\d+)-lock$", name)
        if not m:
            continue
        try:
            pid = int((Path("/tmp") / name).read_text().strip())
            os.kill(pid, 0)
            continue  # alive
        except ProcessLookupError:
            pass
        except (OSError, ValueError):
            pass
        try:
            (Path("/tmp") / name).unlink()
        except OSError:
            pass
        try:
            (Path("/tmp/.X11-unix") / f"X{m.group(1)}").unlink()
        except OSError:
            pass


def _last_line(text: str, n: int = 80) -> str:
    for ln in reversed(text.splitlines()):
        if ln.strip():
            ln = logscan.strip_ansi(ln).strip()
            return ln if len(ln) <= n else ln[: n - 3] + "..."
    return "<no output>"


def _parse_records(text: str) -> list:
    recs = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("@@H "):
            try:
                recs.append(json.loads(ln[4:]))
            except ValueError:
                recs.append({"t": "bad-json", "raw": ln[:200]})
    return recs


def _execute(run_, kind, argv, cwd, timeout_s, display, expected, project, retried=False) -> Invocation:
    n = len(run_.invocations) + 1
    log = run_.godot_dir / f"{n:02d}-{kind}.log"
    started_wall = time.time()
    t0 = time.monotonic()
    timed_out = killed = False
    with open(log, "wb") as lf:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, cwd=str(cwd),
                             start_new_session=True)
        try:
            rc = p.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                rc = p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                killed = True
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
        # sweep survivors (e.g. Xvfb) of our process group
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    duration = time.monotonic() - t0
    if timed_out:
        rc = 124
    elif p.returncode is not None and p.returncode < 0:
        rc = 128 - p.returncode
    else:
        rc = p.returncode if p.returncode is not None else rc
    if display == "xvfb" and killed:
        _cleanup_xvfb(started_wall)
    text = log.read_bytes().decode("utf-8", "replace")
    records = _parse_records(text)
    done = [r for r in records if r.get("t") == "done"]
    runner_rc = done[-1].get("rc") if done else None

    cfg = _cfg(run_, project)
    findings: list = []
    runner_f = []
    for r in records:
        if r.get("t") == "finding" and r.get("rule") and r.get("severity"):
            runner_f.append({"path": r.get("path"), "line": r.get("line"), "rule": r["rule"],
                             "severity": r["severity"], "message": str(r.get("message", "")),
                             "hint": r.get("hint"), "source": "runner", "invocation": n})
    seen = {(f["path"], f["line"], f["message"]) for f in runner_f}
    findings += runner_f
    for f in logscan.scan(text, cfg.get("scan", {}).get("ignore", [])):
        if (f["path"], f["line"], f["message"]) in seen:
            continue
        findings.append({**f, "source": "scan", "invocation": n})

    def add(rule, sev, msg, path=None, hint=None):
        findings.append({"path": path, "line": None, "rule": rule, "severity": sev, "message": msg, "hint": hint,
                         "source": "verb", "invocation": n})

    if timed_out:
        add("harness.hang", "error", f"no exit within {timeout_s:g}s (last log line: {_last_line(text)})")
    elif rc >= 128:
        add("harness.crash", "error", f"Godot died with signal {rc - 128} (rc {rc}; last log line: "
                                      f"{_last_line(text)})")
    elif rc not in expected:
        add("harness.rc", "error", f"exit code {rc}, expected {sorted(expected)} (last log line: {_last_line(text)})")
    if kind in RUNNER_KINDS and runner_rc is None and not timed_out and rc < 128:
        add("harness.runner-incomplete", "error", f"runner exited rc {rc} without a done record (project code "
                                                  f"called quit()?)")
    sev = {f["severity"] for f in findings}
    scan_verdict = "FAIL" if "error" in sev else "WARN" if "warning" in sev else "PASS"
    display_failed = display == "xvfb" and bool(DISPLAY_FAIL_RE.search(text)) and rc != 0
    inv = Invocation(n=n, kind=kind, argv=list(argv), rc=rc, timed_out=timed_out, duration_s=round(duration, 3),
                     log_path=log, scan_verdict=scan_verdict, runner_rc=runner_rc, retried=retried,
                     display_failed=display_failed, records=[r for r in records if r.get("t") != "finding"],
                     findings=findings, timeout_s=timeout_s, text=text)
    if kind in RUNNER_KINDS:
        with open(log.with_suffix(".runner.jsonl"), "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
    run_.record_invocation({"n": n, "kind": kind, "argv": list(argv), "timeout_s": timeout_s, "rc": rc,
                            "timed_out": timed_out, "duration_s": round(duration, 3),
                            "log": str(log.relative_to(run_.dir)), "scan_verdict": scan_verdict,
                            "runner_rc": runner_rc, "retried": retried, "display_failed": display_failed})
    return inv


def run(run, kind, project, args=(), user_args=(), runner=None, display="headless", timeout=None, cwd=None,
        expected_rc=None) -> Invocation:
    """Start one Godot process. Never imports and never adds findings to `run` (REVIEW R-31, R-32)."""
    if kind not in DEFAULT_TIMEOUTS:
        raise ValueError(f"unknown kind {kind!r}")
    if project is None:
        if kind not in NO_PROJECT_KINDS:
            raise ValueError(f"kind {kind} needs a project")
        if cwd is None:
            raise ValueError("project=None needs cwd=")
    g = binary(run, project)
    timeout_s = timeout_for(run, kind, project, timeout)
    workdir = Path(cwd) if cwd is not None else Path(project)
    expected = set(expected_rc) if expected_rc is not None else EXPECTED_RC[kind]
    argv = _build_argv(g, kind, project, args, user_args, runner, display, cwd)
    inv = _execute(run, kind, argv, workdir, timeout_s, display, expected, project)
    if kind == "import" and inv.rc == 134:
        inv = _execute(run, kind, argv, workdir, timeout_s, display, expected, project, retried=True)
    elif display == "xvfb" and DISPLAY_FAIL_RE.search(inv.text) and inv.rc != 0:
        inv = _execute(run, kind, argv, workdir, timeout_s, display, expected, project, retried=True)
    if kind in RUNNER_KINDS and inv.runner_rc in (2, 3):
        run.error(3, f"runner {Path(str(runner)).name} failed with rc {inv.runner_rc}: {_last_line(inv.text, 60)}")
    return inv


_run = run


def spawn(run, kind, project, args, log_path=None) -> subprocess.Popen:
    """Long-lived Godot (lsp_start): own session/process group, stdin /dev/null, log under the run dir."""
    g = binary(run, project)
    argv = _build_argv(g, kind, project, args, (), None, "headless", None)
    log = Path(log_path) if log_path else run.godot_dir / f"{len(run.invocations) + 1:02d}-{kind}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    lf = open(log, "wb")
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                         cwd=str(project) if project else None, start_new_session=True)
    lf.close()
    p.harness_argv = argv
    p.harness_log = log
    p.harness_started = time.monotonic()
    return p


def record_spawn(run, popen, ready: bool, timed_out: bool = False):
    """Record the invocation entry of a spawned process once readiness is known."""
    n = len(run.invocations) + 1
    run.record_invocation({"n": n, "kind": "lsp_start", "argv": list(popen.harness_argv), "timeout_s": 0,
                           "rc": 0 if ready else 1, "timed_out": timed_out,
                           "duration_s": round(time.monotonic() - popen.harness_started, 3),
                           "log": str(Path(popen.harness_log)), "scan_verdict": "PASS" if ready else "FAIL"})


# ---- auto-import (content based, REVIEW R-24) --------------------------------------------------------------------
def _walk(project: Path):
    """Yield (dirpath, filenames) for everything Godot imports (no hidden dirs, no .gdignore dirs)."""
    for dp, dns, fns in os.walk(project):
        dns[:] = sorted(d for d in dns if not d.startswith(".") and not (Path(dp) / d / ".gdignore").exists())
        yield Path(dp), fns


def project_classes(project: Path) -> dict:
    """{res path: class name} from `class_name X` in the first 200 lines of every project *.gd."""
    found = {}
    rx = re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*class_name\s+(\w+)")
    for dp, fns in _walk(project):
        for fn in fns:
            if not fn.endswith(".gd"):
                continue
            p = dp / fn
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    for i, ln in enumerate(fh):
                        if i >= 200:
                            break
                        m = rx.match(ln)
                        if m:
                            found["res://" + p.relative_to(project).as_posix()] = m.group(1)
                            break
            except OSError:
                pass
    return found


def cache_classes(project: Path) -> dict | None:
    cf = Path(project) / ".godot" / "global_script_class_cache.cfg"
    try:
        text = cf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    res = {}
    for blk in re.findall(r"\{[^{}]*\}", text, re.S):
        c = re.search(r'"class":\s*&?"([^"]*)"', blk)
        p = re.search(r'"path":\s*"([^"]+)"', blk)
        if c and p:
            res[p.group(1)] = c.group(1)
    return res


def import_staleness(project) -> str | None:
    """None when fresh, else the `<why>` string of C 2.8.7 / A1 3.3."""
    project = Path(project)
    if not (project / ".godot").is_dir():
        return "no .godot/"
    cache = cache_classes(project)
    if cache is None:
        return "no class cache"
    for path in sorted(cache):
        if not (project / path[len("res://"):]).is_file():
            return f"missing script ({path})"
    files = project_classes(project)
    diff = sorted(p for p in set(files) | set(cache) if files.get(p) != cache.get(p))
    if diff:
        return f"stale class cache ({diff[0]})"
    for dp, fns in _walk(project):
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() in IMPORT_EXTS:
                f = dp / fn
                imp = dp / (fn + ".import")
                try:
                    if not imp.is_file() or f.stat().st_mtime > imp.stat().st_mtime + 0.5:
                        return f"unimported asset (res://{f.relative_to(project).as_posix()})"
                except OSError:
                    pass
    return None


def run_import(r, project) -> Invocation:
    return _run(r, "import", project)


def ensure_imported(run, project) -> str:
    """Import when `.godot/` or the class cache is missing/stale. Prints `import:` and returns the value."""
    why = import_staleness(project)
    if why is None:
        run.stat("import", "fresh")
        return "fresh"
    inv = run_import(run, project)
    run.add_findings(inv.findings)
    run.import_invocation = inv
    value = f"ran ({why})"
    run.stat("import", value)
    return value
