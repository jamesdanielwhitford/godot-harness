"""A2 write pipeline helpers: target resolution, digest runs, dependents, backup/rollback, load-check split.

Everything that talks to Godot goes through godot.run / checkrun.load_check (contract 2.8, REVIEW R-30).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .. import checkrun, godot
from . import model

DIGEST_SCHEMA = "harness.digest/1"


def lib_path() -> str:
    return str(godot.runner_path("_scene_lib").absolute())


def fs_of(project: Path, res: str) -> Path:
    return Path(project) / res[len("res://"):]


def res_of(project: Path, p: Path) -> str | None:
    try:
        rel = Path(os.path.normpath(p)).resolve().relative_to(Path(project).resolve())
    except ValueError:
        return None
    return "res://" + rel.as_posix()


def resolve_target(r, project: Path, arg: str, suffixes: tuple, what: str = "target"):
    """-> (res path, fs path). Missing, wrong suffix or outside the project: rc 2 usage error."""
    if arg.startswith("res://"):
        p = Path(project) / arg[len("res://"):]
    else:
        p = Path(arg).expanduser()
        p = p if p.is_absolute() else Path.cwd() / p
    p = Path(os.path.normpath(p))
    res = res_of(project, p)
    if res is None or res == "res://":
        r.error(2, f"usage: {what} is outside the project: {arg}")
    if p.suffix not in suffixes:
        r.error(2, f"usage: {what} must be a {'/'.join(suffixes)} file: {arg}")
    if not p.is_file():
        r.error(2, f"usage: no such file: {arg}")
    return res, p


def read_text(p: Path) -> str:
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def display_loc(project: Path, p: Path) -> str:
    """Finding location for a spec/ops file: res:// inside the project, else cwd-relative or absolute."""
    res = res_of(project, p)
    if res is not None:
        return res
    try:
        rel = os.path.relpath(p, Path.cwd())
        if not rel.startswith(".."):
            return rel
    except ValueError:
        pass
    return str(Path(p).absolute())


# ---- digest ------------------------------------------------------------------------------------------------------
def run_digest_runner(r, project: Path, mode: str, res: str | None = None, expand: bool = False, list_file=None):
    user = ["--mode", mode, "--lib", lib_path()]
    if res:
        user += ["--path", res]
    if expand:
        user.append("--expand")
    if list_file:
        user += ["--list", str(list_file)]
    inv = godot.run(r, "runner", project, runner="scene_digest", user_args=user)
    rec = next((x for x in inv.records if x.get("t") == "data" and x.get("kind") in ("digest", "resource", "project")), None)
    return inv, rec


def assemble_scene(res: str, rec: dict, text: str) -> dict:
    info = model.parse_text(text)
    d = {"schema": DIGEST_SCHEMA, "kind": "scene", "path": res, "uid": info["uid"], "format": info["format"],
         "inherits": rec.get("inherits"), "editable": info["editable"], "deps": info["deps"],
         "ext_uids": info["ext_uids"], "nodes": rec.get("nodes", []),
         "connections": sorted(rec.get("connections", []), key=model.conn_key), "resource": None, "project": None}
    d["_instantiated"] = rec.get("instantiated")
    d["_status"] = rec.get("status", "ok")
    return d


def assemble_resource(res: str, rec: dict, text: str) -> dict:
    info = model.parse_text(text)
    return {"schema": DIGEST_SCHEMA, "kind": "resource", "path": res, "uid": info["uid"], "format": info["format"],
            "inherits": None, "editable": [], "deps": info["deps"], "ext_uids": info["ext_uids"], "nodes": [],
            "connections": [], "resource": {"type": rec.get("type"), "script_class": rec.get("script_class"),
                                            "props": rec.get("props", {})}, "project": None, "_status": rec.get("status", "ok")}


def public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def dump_json(d: dict) -> str:
    return json.dumps(public(d), sort_keys=True, indent=1) + "\n"


def structural_findings(d: dict | None, res: str) -> list:
    """Findings the verb derives from the digest data (the engine log is scanned by godot.py)."""
    out: list = []
    if d is None:
        return [_f(res, "scene.load-failed", "the digest runner produced no data")]
    st = d.get("_status", "ok")
    if st == "load-failed":
        out.append(_f(res, "scene.load-failed", "ResourceLoader.load returned null (see the engine messages)"))
    elif st == "instantiate-failed":
        out.append(_f(res, "scene.load-failed", "PackedScene.instantiate() returned null (see the engine messages)"))
    for n in d.get("nodes", []):
        if n.get("vanished"):
            p = n["path"]
            par = model.parent_of(p)
            out.append(_f(res, "scene.vanished-node",
                          f"node '{p}' is dropped at load: parent '{par}' does not exist",
                          "parent= is root-relative, never with the root name"))
    return out


def _f(path, rule, msg, hint=None, sev="error", line=None):
    return {"path": path, "line": line, "rule": rule, "severity": sev, "message": msg, "hint": hint, "source": "verb",
            "invocation": None}


def has_errors(findings) -> bool:
    return any(f["severity"] == "error" for f in findings)


# ---- dependents ---------------------------------------------------------------------------------------------------
def find_dependents(project: Path, target_res: str, uid: str | None, exclude: list) -> list:
    """Direct dependents: .tscn/.tres whose text has path="<target>" or uid="<uid>". Sorted res:// paths."""
    project = Path(project)
    ex = [project / e[len("res://"):] for e in exclude if e.startswith("res://")]
    needles = [f'path="{target_res}"']
    if uid:
        needles.append(f'uid="{uid}"')
    out = []
    for dp, dns, fns in os.walk(project):
        d = Path(dp)
        dns[:] = sorted(n for n in dns if not n.startswith(".") and not (d / n / ".gdignore").exists()
                        and (d / n) not in ex)
        for fn in sorted(fns):
            if not fn.endswith((".tscn", ".tres")):
                continue
            p = d / fn
            res = "res://" + p.relative_to(project).as_posix()
            if res == target_res:
                continue
            text = read_text(p)
            if any(n in text for n in needles):
                out.append(res)
    return sorted(out)


# ---- backup / rollback ---------------------------------------------------------------------------------------------
def backup(r, fs: Path):
    """-> backup path or None when the file does not exist."""
    if not Path(fs).exists():
        return None
    d = r.artifacts_dir / "backup"
    d.mkdir(exist_ok=True)
    dst = d / Path(fs).name
    shutil.copy2(fs, dst)
    return dst


def rollback(r, fs: Path, bak) -> None:
    """Keep the rejected result under artifacts/rejected/ and restore the previous bytes (or delete a new file)."""
    fs = Path(fs)
    if fs.exists():
        d = r.artifacts_dir / "rejected"
        d.mkdir(exist_ok=True)
        try:
            shutil.copy2(fs, d / fs.name)
        except OSError:
            pass
    if bak is not None:
        shutil.copy2(bak, fs)
    elif fs.exists():
        fs.unlink()


# ---- load-check split -------------------------------------------------------------------------------------------
def fkey(f) -> tuple:
    return (f.get("path"), f.get("rule"), f.get("message"))


def precheck(r, project: Path, paths: list) -> set:
    """Findings of `paths` before the write; recorded under run.json extra.precheck, never printed."""
    if not paths:
        return set()
    found = checkrun.load_check(r, project, paths)
    r.extra.setdefault("precheck", []).extend(
        {"path": f.get("path"), "rule": f["rule"], "severity": f["severity"], "message": f["message"]} for f in found)
    return {fkey(f) for f in found if f["severity"] == "error"}


def postcheck(r, project: Path, target: str, dependents: list, pre: set, label: str):
    """One load_check of target + dependents -> (target findings, new breaking findings at dependents)."""
    found = checkrun.load_check(r, project, [target] + list(dependents))
    mine, broken = [], []
    for f in found:
        if f["severity"] == "error" and f.get("path") in dependents:
            if fkey(f) in pre:
                continue
            broken.append(_f(f["path"], "scene.breaks-dependent", f"{f['path']} breaks, new after {label} of {target}: {f['message']}"))
        elif f.get("path") in dependents:
            continue
        else:
            mine.append(f)
    return mine, broken


# ---- stat output -----------------------------------------------------------------------------------------------
def emit_stats(r, lines: list, findings: list, full_name: str = "digest.txt") -> None:
    """Add stat lines after the ones already in r.stats, honouring the 40-line limit.

    The complete list goes to artifacts/<full_name>; when it does not fit the last kept stat is
    `more: <K> lines in <path>` (contract 2.3, REVIEW R-22)."""
    fixed = len(r.stats)
    head = [f"{k}: {v}" for k, v in r.stats]
    (r.artifacts_dir / full_name).write_text("\n".join(head + [f"{k}: {v}" for k, v in lines]) + "\n")
    nf = len({(f["severity"], f.get("path"), f.get("line"), f["rule"], f["message"]) for f in findings
              if f["severity"] in ("error", "warning")})
    limit = 38 if nf == 0 else 36 - min(nf, 3)
    room = limit - fixed
    if len(lines) <= room:
        for k, v in lines:
            r.stat(k, v)
        return
    keep = max(room - 1, 0)
    for k, v in lines[:keep]:
        r.stat(k, v)
    r.stat("more", f"{len(lines) - keep} lines in {r._display_dir()}artifacts/{full_name}")


def seed_text(base: str, root_name: str) -> str:
    return ('[gd_scene format=3]\n\n[ext_resource type="PackedScene" path="%s" id="1"]\n\n'
            '[node name="%s" instance=ExtResource("1")]\n' % (base, root_name))
