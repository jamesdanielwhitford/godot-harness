"""h doctor: check the toolchain against pins.toml. Non-zero exit if a required piece is missing."""
import shutil
import subprocess
from pathlib import Path

from .. import pins


def _run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def checks():
    p = pins.load()
    root, cache = pins.repo_root(), pins.cache_dir()
    out = []  # (name, ok, detail, required)

    godot = root / "tools" / "bin" / "godot"
    if godot.exists():
        rc, v = _run([str(godot), "--version"])
        v = v.splitlines()[-1] if v else ""
        out.append(("godot", v == p["godot_version_string"], v or "no output", True))
    else:
        out.append(("godot", False, "tools/bin/godot missing", True))

    g = cache / "gdunit4" / "gdUnit4"
    if not g.exists():
        g = cache / "gdunit4"
    rc, c = _run(["git", "-C", str(g), "rev-parse", "HEAD"]) if g.exists() else (1, "missing")
    out.append(("gdunit4", rc == 0 and c == p["gdunit4_commit"], f"{p['gdunit4_tag']} {c[:12]}", True))

    od = cache / "odiff" / "node_modules" / "@odiff" / "linux-x64" / "odiff"
    out.append(("odiff", od.exists(), str(od) if od.exists() else "missing", True))

    py = root / ".venv" / "bin" / "python"
    rc, d = _run([str(py), "-c", "import pytest"]) if py.exists() else (1, "missing")
    out.append(("venv", rc == 0, ".venv ok" if rc == 0 else ".venv missing or no pytest", True))

    out.append(("xvfb-run", bool(shutil.which("xvfb-run")), shutil.which("xvfb-run") or "missing", True))
    out.append(("compare", bool(shutil.which("compare")), shutil.which("compare") or "missing", True))
    return out


def run(argv):
    bad = 0
    for name, ok, detail, required in checks():
        print(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}")
        if required and not ok:
            bad += 1
    print("doctor: ok" if not bad else f"doctor: {bad} problem(s); run tools/bootstrap.sh")
    return 1 if bad else 0
