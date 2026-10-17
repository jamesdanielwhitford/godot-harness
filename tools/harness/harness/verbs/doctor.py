"""h doctor: check the toolchain against pins.toml (contract C3, A1 2.5)."""
import os
import platform
import shutil
import sys
from pathlib import Path

from .. import out, pins, proc

HELP = "check the toolchain (godot, gdUnit4, odiff, venv, xvfb, compare)"
USAGE = """
h doctor [--project DIR] [--strict]
Checks the pinned tools; with a project also its sync and import state.
rc 0 all ok, rc 5 warnings, rc 4 a required tool is missing."""


def _godot_check(project, cfg):
    from .. import godot
    p = pins.load()
    env = os.environ.get("HARNESS_GODOT")
    if env:
        g = Path(env).expanduser()
    elif cfg and cfg["harness"].get("godot") and project is not None:
        g = Path(cfg["harness"]["godot"])
        g = g if g.is_absolute() else Path(project) / g
    else:
        g = out.repo_root() / "tools" / "bin" / "godot"
    want = (cfg or {}).get("harness", {}).get("godot_version") or p["godot_version_string"]
    if not (g.is_file() and os.access(g, os.X_OK)):
        return False, f"{g} missing (run tools/bootstrap.sh)", None
    v = godot._probe_version(g) or "no output from --version"
    return v == want, v, v


def checks(project, cfg):
    p = pins.load()
    root, cache = pins.repo_root(), pins.cache_dir()
    res = []  # (name, ok, detail)
    ok, detail, _ = _godot_check(project, cfg)
    res.append(("godot", ok, detail))

    g = cache / "gdunit4"
    c = proc.run(["git", "-C", str(g), "rev-parse", "HEAD"], timeout=10) if g.exists() else None
    head = c.stdout.strip() if c and c.rc == 0 else ""
    res.append(("gdunit4", head == p["gdunit4_commit"], f"{p['gdunit4_tag']} {head[:12] or 'missing'}"))

    plat = ("darwin-arm64" if platform.machine() == "arm64" else "darwin-x64") if sys.platform == "darwin" else "linux-x64"
    od = cache / "odiff" / "node_modules" / "@odiff" / plat / "odiff"
    res.append(("odiff", od.exists(), str(od) if od.exists() else "missing"))

    py = root / ".venv" / "bin" / "python"
    c = proc.run([str(py), "-c", "import pytest"], timeout=20) if py.exists() else None
    good = bool(c and c.rc == 0)
    res.append(("venv", good, ".venv ok" if good else ".venv missing or no pytest"))

    for tool in ("xvfb-run", "compare"):
        w = shutil.which(tool)
        if tool == "xvfb-run" and sys.platform == "darwin":
            res.append((tool, True, w or "not needed on macOS"))
            continue
        res.append((tool, bool(w), w or "missing"))
    return res


def _api_check(cfg):
    import json
    ver = (cfg or {}).get("harness", {}).get("godot_version") or pins.load()["godot_version_string"]
    idx = pins.cache_dir() / "api" / ver / "index.json"
    if not idx.is_file():
        return "SKIP", "not built (h api --rebuild)"
    try:
        n = json.loads(idx.read_text()).get("count")
        if n is None:
            n = len(json.loads(idx.read_text())["entries"])
        return "OK", f"index {n} entries"
    except (OSError, ValueError, KeyError):
        return "WARN", "index unreadable (h api --rebuild)"


def _main(r, args, project):
    from .. import godot, sync
    cfg = r.config
    bad = 0
    total = ok_n = 0
    for name, ok, detail in checks(project, cfg):
        r.check("OK" if ok else "FAIL", name, detail)
        total += 1
        ok_n += ok
        bad += not ok
    st, detail = _api_check(cfg)
    r.check(st, "api", detail)
    if st != "SKIP":
        total += 1
        ok_n += st == "OK"
    if project is not None:
        s = sync.status(project)
        if s == "fresh":
            r.check("OK", "sync", "fresh")
        elif s == "stale":
            r.check("WARN", "sync", "stale (h sync)")
        else:
            r.check("SKIP", "sync", "not synced")
        why = godot.import_staleness(project)
        if why is None:
            r.check("OK", "import", "fresh")
        else:
            r.check("WARN", "import", f"stale ({why})")
        total += 1 + (s != "not synced")
        ok_n += (why is None) + (s == "fresh")
    if bad:
        return r.finish_error(4, f"{bad} required check{'s' if bad > 1 else ''} failed (run tools/bootstrap.sh)")
    return r.finish(f"{ok_n}/{total} checks ok")


def run(argv):
    return out.invoke("doctor", argv, out.common_parser("doctor"), _main, need_project=False, soft_project=True)
