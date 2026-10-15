"""Mirror addons/harness (+ gdUnit4) into a project and enable autoloads (A1 2.3, 3.1; REVIEW R-16, R-33, R-53).

Public: sync_project(run, project, gdunit=True, check=False), ensure_synced(run, project) -> str,
install_gdunit4(run, project) -> str, status(project) -> str.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from . import out, pins

SYNC_FILE = "addons/harness/.sync.json"
AUTOLOAD_PREFIX = "*res://addons/harness/"


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def source_dir() -> Path:
    return out.repo_root() / "addons" / "harness"


def source_files() -> list:
    """[(relpath, abs path)] mirrored into the project: everything but runners/, *.uid and .import files."""
    base = source_dir()
    res = []
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base)
            if rel.parts[0] == "runners" or p.suffix in (".uid", ".import") or rel.name == ".sync.json":
                continue
            res.append((rel.as_posix(), p))
    return res


def source_hash(files=None) -> str:
    h = hashlib.sha256()
    for rel, p in sorted(files if files is not None else source_files()):
        h.update(rel.encode() + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def read_meta(project: Path) -> dict | None:
    try:
        d = json.loads((Path(project) / SYNC_FILE).read_text())
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _meta_text(src_hash: str, gd_commit) -> str:
    return json.dumps({"schema": "harness.sync/1", "source_hash": src_hash, "gdunit4_commit": gd_commit},
                      indent=1) + "\n"


def _dest_files(dest: Path) -> dict:
    res = {}
    if dest.is_dir():
        for p in sorted(dest.rglob("*")):
            if p.is_file() and p.relative_to(dest).as_posix() != ".sync.json":
                res[p.relative_to(dest).as_posix()] = p
    return res


def diff_mirror(project: Path) -> tuple[list, list, list]:
    """(missing_or_changed rels, extra rels, source files) for addons/harness."""
    files = source_files()
    dest = Path(project) / "addons" / "harness"
    have = _dest_files(dest)
    todo = [rel for rel, p in files if rel not in have or have[rel].read_bytes() != p.read_bytes()]
    extra = sorted(set(have) - {rel for rel, _ in files})
    return todo, extra, files


def mirror(project: Path) -> tuple[int, int, str]:
    """Write the mirror. Returns (n files, n changed, source hash)."""
    todo, extra, files = diff_mirror(project)
    dest = Path(project) / "addons" / "harness"
    for rel, p in files:
        if rel in todo:
            t = dest / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, t)
    for rel in extra:
        (dest / rel).unlink()
    # drop empty dirs left behind
    if dest.is_dir():
        for d in sorted((x for x in dest.rglob("*") if x.is_dir()), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass
    return len(files), len(todo) + len(extra), source_hash(files)


# ---- project.godot autoloads --------------------------------------------------------------------------------------
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _autoload_range(lines: list):
    start = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if start is None:
            if s == "[autoload]":
                start = i
        elif s.startswith("[") and s.endswith("]"):
            return start, i
    return (start, len(lines)) if start is not None else (None, None)


def autoload_plan(project: Path, names: list) -> dict:
    """{'shipped': [...], 'unshipped': [...], 'missing': [...], 'present': [...], 'conflicts': [(name, value)]}"""
    pg = (Path(project) / "project.godot").read_text(encoding="utf-8")
    lines = pg.splitlines(keepends=True)
    a, b = _autoload_range(lines)
    existing = {}
    if a is not None:
        for ln in lines[a + 1:b]:
            m = _KEY_RE.match(ln.rstrip("\r\n"))
            if m:
                existing[m.group(1)] = m.group(2)
    plan = {"shipped": [], "unshipped": [], "missing": [], "present": [], "conflicts": []}
    src = source_dir()
    for n in names:
        if not (src / f"{snake(n)}.gd").is_file():
            plan["unshipped"].append(n)
            continue
        plan["shipped"].append(n)
        want = f'"{AUTOLOAD_PREFIX}{snake(n)}.gd"'
        if n not in existing:
            plan["missing"].append(n)
        elif existing[n] == want:
            plan["present"].append(n)
        else:
            plan["conflicts"].append((n, existing[n]))
    return plan


def add_autoloads(project: Path, names: list):
    """Insert missing `Name="*res://addons/harness/x.gd"` lines after the last key of [autoload]; never reorder."""
    if not names:
        return
    f = Path(project) / "project.godot"
    text = f.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    a, b = _autoload_range(lines)
    new = [f'{n}="{AUTOLOAD_PREFIX}{snake(n)}.gd"\n' for n in names]
    if a is None:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n[autoload]\n\n" + "".join(new)
    else:
        last = a
        for i in range(a + 1, b):
            if _KEY_RE.match(lines[i].rstrip("\r\n")):
                last = i
        if not lines[last].endswith("\n"):
            lines[last] += "\n"
        lines[last + 1:last + 1] = new
        text = "".join(lines)
    f.write_text(text, encoding="utf-8")


# ---- gdUnit4 ------------------------------------------------------------------------------------------------------
def _pin_version() -> str:
    return pins.load()["gdunit4_tag"].lstrip("v")


def _plugin_version(plugin_cfg: Path) -> str | None:
    try:
        m = re.search(r'^version\s*=\s*"([^"]*)"', plugin_cfg.read_text(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def _gd_cache_dir() -> Path:
    return pins.cache_dir() / "gdunit4" / "addons" / "gdUnit4"


def _gd_state(project: Path) -> str:
    """'missing' | 'present' | 'other' (a different version is in the project)."""
    cfg = Path(project) / "addons" / "gdUnit4" / "plugin.cfg"
    if not cfg.is_file():
        return "missing"
    return "present" if _plugin_version(cfg) == _pin_version() else "other"


def install_gdunit4(run, project) -> str:
    """present | installed (was missing) | installed (pin changed); rc 4 when impossible (REVIEW R-33, R-53)."""
    project = Path(project)
    state = _gd_state(project)
    if state == "present":
        return "present"
    meta = read_meta(project)
    harness_installed = bool(meta and meta.get("gdunit4_commit"))
    if state == "other" and not harness_installed:
        cfg = project / "addons" / "gdUnit4" / "plugin.cfg"
        run.error(4, f"gdUnit4 {_plugin_version(cfg)} in project, harness pins {_pin_version()} (run h sync)")
    src = _gd_cache_dir()
    if not src.is_dir():
        run.error(4, "gdUnit4 not in cache (run tools/bootstrap.sh)")
    dst = project / "addons" / "gdUnit4"
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    def ignore(d, names):
        ign = {n for n in names if n.endswith(".uid")}
        if Path(d) == src:
            ign |= {n for n in names if n == "test"}
        return ign

    shutil.copytree(src, dst, ignore=ignore)
    return "installed (was missing)" if state == "missing" else "installed (pin changed)"


# ---- public entry points ------------------------------------------------------------------------------------------
def _names(run) -> list:
    cfg = getattr(run, "config", None) or {}
    return list(cfg.get("harness", {}).get("autoloads", ["Harness", "Rng", "CommandBus", "Trace"]))


def sync_project(run, project, gdunit: bool = True, check: bool = False) -> str:
    """`h sync`: adds check lines/findings to `run`; returns a short reason."""
    project = Path(project)
    names = _names(run)
    todo, extra, files = diff_mirror(project)
    plan = autoload_plan(project, names)
    gd_state = _gd_state(project) if gdunit else None

    for n, v in plan["conflicts"]:
        run.finding("res://project.godot", None, "harness.sync-conflict", "error",
                    f"autoload {n} already set to {v}", hint=f"remove it or set {n} to "
                    f"{AUTOLOAD_PREFIX}{snake(n)}.gd")
    if check:
        stale = 0
        if todo or extra:
            first = (todo + extra)[0]
            run.finding(f"res://addons/harness/{first}", None, "harness.sync-stale", "error",
                        f"addons/harness differs from the harness source ({len(todo)} changed, {len(extra)} extra)",
                        hint="run h sync")
            stale += 1
        for n in plan["missing"]:
            run.finding("res://project.godot", None, "harness.sync-stale", "error",
                        f"autoload {n} is not enabled", hint="run h sync")
            stale += 1
        if gdunit and gd_state != "present":
            run.finding("res://addons/gdUnit4", None, "harness.sync-stale", "error",
                        "gdUnit4 " + ("is not installed" if gd_state == "missing" else "has another version"),
                        hint="run h sync")
            stale += 1
        meta = read_meta(project)
        if not stale and (meta is None or meta.get("source_hash") != source_hash(files)):
            run.finding("res://addons/harness/.sync.json", None, "harness.sync-stale", "error",
                        "sync metadata is missing or out of date", hint="run h sync")
            stale += 1
        run.check("OK" if not todo and not extra else "FAIL", "addons/harness",
                  f"{len(files)} files ({len(todo) + len(extra)} changed)")
        for n in plan["unshipped"]:
            run.check("SKIP", f"autoload {n}", "not shipped")
        return "stale parts: %d" % stale if stale else "up to date"

    # gdUnit4 first: its errors (rc 4) must stop before anything is written
    gd_result = None
    if gdunit:
        gd_result = install_gdunit4(run, project)
    n_files, n_changed, h = mirror(project)
    if not plan["conflicts"]:
        add_autoloads(project, plan["missing"])
    meta = read_meta(project) or {}
    gd_commit = meta.get("gdunit4_commit")
    if gdunit and gd_result and gd_result.startswith("installed"):
        gd_commit = pins.load()["gdunit4_commit"]
    new_meta = _meta_text(h, gd_commit)
    mf = project / SYNC_FILE
    if not mf.is_file() or mf.read_text() != new_meta:
        mf.parent.mkdir(parents=True, exist_ok=True)
        mf.write_text(new_meta)
    run.check("OK", "addons/harness", f"{n_files} files ({n_changed} changed)")
    if gdunit:
        p = pins.load()
        run.check("OK", "gdunit4", f"{p['gdunit4_tag']} {p['gdunit4_commit'][:12]} ({gd_result})")
    for n in plan["shipped"]:
        if any(c[0] == n for c in plan["conflicts"]):
            run.check("FAIL", f"autoload {n}", "conflict")
        else:
            run.check("OK", f"autoload {n}", "added" if n in plan["missing"] else "present")
    for n in plan["unshipped"]:
        run.check("SKIP", f"autoload {n}", "not shipped")
    return f"{n_files} files synced ({n_changed} changed)"


def ensure_synced(run, project) -> str:
    """`fresh` | `ran (<why>)`: mirror addons/harness when project.godot declares a harness autoload and the
    recorded source hash is missing/different. Never edits project.godot, never installs gdUnit4."""
    project = Path(project)
    try:
        pg = (project / "project.godot").read_text(encoding="utf-8")
    except OSError:
        return "fresh"
    if AUTOLOAD_PREFIX not in pg:
        return "fresh"
    meta = read_meta(project)
    h = source_hash()
    if meta and meta.get("source_hash") == h:
        return "fresh"
    why = "not synced" if meta is None else "source changed"
    n_files, n_changed, h = mirror(project)
    mf = project / SYNC_FILE
    new_meta = _meta_text(h, (meta or {}).get("gdunit4_commit"))
    if not mf.is_file() or mf.read_text() != new_meta:
        mf.parent.mkdir(parents=True, exist_ok=True)
        mf.write_text(new_meta)
    return f"ran ({why})"


def status(project) -> str:
    """'fresh' | 'stale' | 'not synced' (for doctor)."""
    meta = read_meta(project)
    if meta is None:
        return "not synced"
    if meta.get("source_hash") != source_hash():
        return "stale"
    todo, extra, _ = diff_mirror(Path(project))
    return "stale" if (todo or extra) else "fresh"
