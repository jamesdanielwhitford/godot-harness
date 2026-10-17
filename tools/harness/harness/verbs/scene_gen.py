"""h scene-gen: build scenes from JSON specs with the engine and verify every write (A2 2.2, 3.3)."""
from __future__ import annotations

import time
from pathlib import Path

from .. import godot, out
from ..scenes import model, pipeline, schema

HELP = "build .tscn scenes from JSON specs with the engine, then verify"
USAGE = """
h scene-gen [--project DIR] <spec.json>... [--force] [--strict]
Specs run in order; a later spec may instance an earlier one. Each spec is validated,
built by the engine, saved, re-read and compared with the spec; any error restores the old file.
--force   replace an existing target (keeps its uid, re-checks direct dependents)
Spec format: docs/ or .claude/plans/specs/02_scene.md section 2.4."""


def _parser():
    p = out.common_parser("scene-gen")
    p.add_argument("specs", nargs="*")
    p.add_argument("--force", action="store_true")
    return p


def _name(res: str) -> str:
    return res[len("res://"):] if res.startswith("res://") else res


def _load_specs(r, project: Path, args) -> list:
    loaded, bad = [], 0
    for a in args.specs:
        p = Path(a).expanduser()
        p = p if p.is_absolute() else Path.cwd() / p
        loc = pipeline.display_loc(project, p)
        if not p.is_file():
            r.error(2, f"usage: no such spec file: {a}")
        text = p.read_text(encoding="utf-8", errors="replace")
        obj, err = schema.parse_json(text)
        if err is not None:
            r.finding(loc, err[0], "scene.spec-schema", "error", err[1])
            bad += 1
            continue
        errs = schema.validate_spec(obj)
        for ptr, msg in errs:
            r.finding(loc, None, "scene.spec-schema", "error", f"{ptr}: {msg}" if ptr else msg)
        bad += len(errs)
        if not errs:
            loaded.append((p.absolute(), obj, loc))
    if bad:
        r.error(2, f"{bad} spec error{'s' if bad != 1 else ''}, nothing written")
    return loaded


def _gen_one(r, project: Path, idx: int, specfile: Path, spec: dict, loc: str, force: bool, strict: bool) -> dict:
    """-> {ok, saved, replaced, uid, after, changes, findings}"""
    save = spec["save"]
    fs = pipeline.fs_of(project, save)
    res = {"ok": False, "saved": None, "replaced": False, "uid": None, "after": None, "changes": [], "findings": []}
    fnd: list = res["findings"]
    before, bak, deps, pre = None, None, [], set()
    existed = fs.exists()
    if existed:
        res["replaced"] = True
        inv, rec = pipeline.run_digest_runner(r, project, "scene", save)
        text = pipeline.read_text(fs)
        before = pipeline.assemble_scene(save, rec, text) if rec else None
        res["uid"] = model.parse_text(text)["uid"]
        bak = pipeline.backup(r, fs)
        exclude = r.config.get("scene", {}).get("project_exclude", ["res://addons"])
        deps = pipeline.find_dependents(project, save, res["uid"], exclude)
        pre = pipeline.precheck(r, project, deps)
    user = ["--lib", pipeline.lib_path(), "--spec", str(specfile), "--out", save, "--loc", loc]
    if res["uid"]:
        user += ["--uid", res["uid"]]
    root = spec["root"]
    if root.get("instance"):
        seed = r.artifacts_dir / f"seed{idx}.tscn"
        seed.write_text(pipeline.seed_text(root["instance"], root["name"]))
        user += ["--seed", str(seed)]
    inv = godot.run(r, "runner", project, runner="scene_gen", user_args=user)
    fnd += inv.findings
    gen = next((x for x in inv.records if x.get("t") == "data" and x.get("kind") == "gen"), None)
    ok = gen is not None and not pipeline.has_errors(inv.findings) and not inv.failed
    after = None
    if ok:
        mine, broken = pipeline.postcheck(r, project, save, deps, pre, "replacement" if existed else "creation")
        fnd += mine + broken
        inv2, rec2 = pipeline.run_digest_runner(r, project, "scene", save)
        fnd += inv2.findings
        after = pipeline.assemble_scene(save, rec2, pipeline.read_text(fs)) if rec2 else None
        fnd += pipeline.structural_findings(after, save)
        if after is not None:
            fnd += [dict(f, path=save, source="verb", invocation=None) for f in model.verify_gen(spec, gen, after)]
        ok = not pipeline.has_errors(fnd)
        if ok and strict and any(f["severity"] == "warning" for f in fnd):
            ok = False
    if not ok:
        changed = fs.exists() and (bak is None or fs.read_bytes() != Path(bak).read_bytes())
        if changed or (bak is None and fs.exists()):
            pipeline.rollback(r, fs, bak)
        return res
    res.update(ok=True, saved=save, after=after)
    if before is not None and after is not None:
        res["changes"] = model.diff(before, after)
    return res


def _main(r, args, project: Path):
    t0 = time.monotonic()
    if not args.specs:
        r.error(2, "usage: at least one spec file is required")
    specs = _load_specs(r, project, args)
    seen = set()
    for _, spec, _ in specs:
        s = spec["save"]
        if (pipeline.fs_of(project, s).exists() and not args.force) or s in seen:
            r.error(2, f"usage: {s} exists (use --force)")
        seen.add(s)
    godot.binary(r, project)
    godot.ensure_imported(r, project)
    multi = len(specs) > 1
    results, failed = [], False
    for i, (specfile, spec, loc) in enumerate(specs):
        name = _name(spec["save"])
        if failed:
            if multi:
                r.check("SKIP", name, "an earlier spec failed")
            results.append(None)
            continue
        res = _gen_one(r, project, i, specfile, spec, loc, args.force, r.strict)
        r.add_findings(res["findings"])
        results.append(res)
        if res["ok"]:
            if multi:
                n = len(res["after"]["nodes"]) if res["after"] else 0
                r.check("OK", name, f"{'replaced' if res['replaced'] else 'created'}, {n} nodes")
        else:
            failed = True
            if multi:
                nerr = sum(1 for f in res["findings"] if f["severity"] == "error")
                r.check("FAIL", name, f"{nerr} error{'s' if nerr != 1 else ''}, nothing written")
    written = [x["saved"] for x in results if x and x["ok"]]
    rolled = [x for x in results if x and not x["ok"] and x["replaced"]]
    r.extra["saved"] = written or None
    r.extra["rolled_back"] = bool(failed)
    saved_txt = ", ".join(written) if written else "none"
    if failed and not written:
        saved_txt = "none (rolled back)" if any(x and not x["ok"] and (x["replaced"]) for x in results) else "none"
    r.stat("saved", saved_txt)
    if not multi:
        res = results[0]
        r.stat("uid", f"kept {res['uid']}" if res and res["uid"] and res["ok"] else "none")
        if res and res["ok"] and res["after"] is not None:
            if res["replaced"]:
                lines = [("change", c) for c in res["changes"]] or [("change", "none")]
            else:
                lines = [(k, v) for k, v in model.render(res["after"]) if k in ("node", "conn")]
            pipeline.emit_stats(r, lines, r.findings)
    el = time.monotonic() - t0
    nerr = sum(1 for f in r.findings if f["severity"] == "error") + sum(1 for c in r.checks if c[0] == "FAIL" and False)
    if failed:
        return r.finish(f"{nerr} error{'s' if nerr != 1 else ''}, nothing written ({el:.1f}s)")
    if multi:
        return r.finish(f"{len(written)} scenes written ({el:.1f}s)")
    res = results[0]
    verb = "replaced" if res["replaced"] else "created"
    return r.finish(f"{verb} {res['saved']}, {len(res['after']['nodes'])} nodes ({el:.1f}s)")


def run(argv):
    return out.invoke("scene-gen", argv, _parser(), _main)
