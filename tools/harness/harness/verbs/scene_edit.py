"""h scene-edit: apply ops to an existing scene through the engine, one save, verified (A2 2.3, 3.3)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import godot, out
from ..scenes import model, pipeline, schema

HELP = "edit a .tscn with verified ops (set_prop, rename, connect, ...)"
USAGE = """
h scene-edit [--project DIR] <scene.tscn> <ops.json> [--strict]
ops.json: {"ops": [{"op": "set_prop", "node": "Player", "props": {"speed": 300}}, ...]}
ops: set_prop add_node add_instance remove_node reparent rename connect disconnect set_script groups
All ops apply to one engine instance and are saved once; any error leaves the file untouched.
A direct dependent that breaks, or a verification mismatch, restores the old bytes.
Format: .claude/plans/specs/02_scene.md section 2.5."""


def _parser():
    p = out.common_parser("scene-edit")
    p.add_argument("scene", nargs="?")
    p.add_argument("ops", nargs="?")
    return p


def _stale_findings(project: Path, before: dict, effects: list, res: str) -> list:
    names = model.stale_names(effects)
    if not names:
        return []
    scripts = sorted({n["script"] for n in before["nodes"] if n.get("script")}
                     | {fx["script"] for fx in effects if fx.get("e") == "script" and fx.get("script")}
                     | {fx["script"] for fx in effects if fx.get("e") == "add" and fx.get("script")})
    found = []
    for sp in scripts:
        text = pipeline.read_text(pipeline.fs_of(project, sp))
        for old, what in names:
            pat = model.stale_pattern(old)
            for ln, line in enumerate(text.splitlines(), 1):
                code = line.split("#", 1)[0]
                if pat.search(code):
                    found.append({"path": sp, "line": ln, "rule": "scene.stale-ref", "severity": "warning",
                                  "message": f"'{old}' was {what} in {res} but this script still refers to it: "
                                             f"{line.strip()[:60]}",
                                  "hint": "update the script", "source": "verb", "invocation": None})
    return found


def _main(r, args, project: Path):
    t0 = time.monotonic()
    if not args.scene or not args.ops:
        r.error(2, "usage: a scene and an ops file are required")
    res, fs = pipeline.resolve_target(r, project, args.scene, (".tscn",), "scene")
    opsf = Path(args.ops).expanduser()
    opsf = (opsf if opsf.is_absolute() else Path.cwd() / opsf).absolute()
    if not opsf.is_file():
        r.error(2, f"usage: no such ops file: {args.ops}")
    loc = pipeline.display_loc(project, opsf)
    doc, err = schema.parse_json(opsf.read_text(encoding="utf-8", errors="replace"))
    if err is not None:
        r.finding(loc, err[0], "scene.spec-schema", "error", err[1])
        r.error(2, "1 ops error, nothing written")
    errs = schema.validate_ops(doc)
    if errs:
        for ptr, msg in errs:
            r.finding(loc, None, "scene.spec-schema", "error", f"{ptr}: {msg}" if ptr else msg)
        r.error(2, f"{len(errs)} ops error{'s' if len(errs) != 1 else ''}, nothing written")
    godot.binary(r, project)
    godot.ensure_imported(r, project)

    inv, rec = pipeline.run_digest_runner(r, project, "scene", res)
    text = pipeline.read_text(fs)
    before = pipeline.assemble_scene(res, rec, text) if rec else None
    bf = list(inv.findings) + pipeline.structural_findings(before, res)
    if pipeline.has_errors(bf):
        r.add_findings([f for f in bf if f["severity"] == "error"])
        r.finding(res, None, "scene.broken-input", "error",
                  "the scene already has load errors; scene-edit refuses broken input",
                  "regenerate it with scene-gen or fix the listed problems first")
        r.stat("saved", "none")
        r.stat("uid", "none")
        return r.finish(f"{res} has load errors, nothing written ({time.monotonic() - t0:.1f}s)")

    uid = before["uid"]
    bak = pipeline.backup(r, fs)
    exclude = r.config.get("scene", {}).get("project_exclude", ["res://addons"])
    deps = pipeline.find_dependents(project, res, uid, exclude)
    pre = pipeline.precheck(r, project, deps)
    user = ["--lib", pipeline.lib_path(), "--scene", res, "--ops", str(opsf), "--loc", loc]
    if uid:
        user += ["--uid", uid]
    if before["ext_uids"]:
        ef = r.artifacts_dir / "ext_uids.json"
        ef.write_text(json.dumps(before["ext_uids"]))
        user += ["--ext-uids", str(ef)]
    inv = godot.run(r, "runner", project, runner="scene_edit", user_args=user)
    fnd: list = list(inv.findings)
    edit = next((x for x in inv.records if x.get("t") == "data" and x.get("kind") == "edit"), None)
    ops_recs = sorted((x for x in inv.records if x.get("t") == "data" and x.get("kind") == "op"), key=lambda x: x["i"])
    effects = [fx for rc_ in ops_recs for fx in rc_.get("effects", [])]
    ok = edit is not None and not pipeline.has_errors(fnd) and not inv.failed
    written = False
    after = None
    if ok:
        written = True
        mine, broken = pipeline.postcheck(r, project, res, deps, pre, "edit")
        fnd += mine + broken
        inv2, rec2 = pipeline.run_digest_runner(r, project, "scene", res)
        fnd += inv2.findings
        after = pipeline.assemble_scene(res, rec2, pipeline.read_text(fs)) if rec2 else None
        fnd += pipeline.structural_findings(after, res)
        if after is not None:
            exp = model.expected(before, effects)
            fnd += [dict(f, path=res, source="verb", invocation=None) for f in model.compare(exp, after)]
        fnd += _stale_findings(project, before, effects, res)
        ok = not pipeline.has_errors(fnd)
        if ok and r.strict and any(f["severity"] == "warning" for f in fnd):
            ok = False
    else:
        if fs.exists() and fs.read_bytes() != Path(bak).read_bytes():
            written = True
    rolled = False
    if not ok and written:
        pipeline.rollback(r, fs, bak)
        rolled = True
    r.add_findings(fnd)
    r.extra["saved"] = res if ok else None
    r.extra["rolled_back"] = rolled
    r.stat("saved", res if ok else ("none (rolled back)" if rolled else "none"))
    r.stat("uid", f"kept {uid}" if ok and uid else "none")
    r.stat("dependents", f"{len(deps)} checked")
    lines = [("change", c) for c in model.change_lines(effects)]
    if lines:
        pipeline.emit_stats(r, lines, r.findings, "changes.txt")
    el = time.monotonic() - t0
    nerr = sum(1 for f in r.findings if f["severity"] == "error")
    if not ok:
        if nerr:
            return r.finish(f"{nerr} error{'s' if nerr != 1 else ''}, "
                            f"{'rolled back' if rolled else 'nothing written'} ({el:.1f}s)")
        return r.finish(f"strict: warnings, rolled back ({el:.1f}s)")
    return r.finish(f"{res}: {len(ops_recs)} ops applied, {len(lines)} changes ({el:.1f}s)")


def run(argv):
    return out.invoke("scene-edit", argv, _parser(), _main)
