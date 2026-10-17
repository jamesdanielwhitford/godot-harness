"""h digest: print a scene, resource or the project as text, with full output on disk (A2 2.1)."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .. import godot, out
from ..scenes import model, pipeline

HELP = "print a scene, resource or the project overview as short text"
USAGE = """
h digest [--project DIR] <scene.tscn|res.tres> [--node PATH] [--expand] [--json] [--strict]
h digest [--project DIR] --project-summary [--json]
--node PATH        only that node and its subtree (root-relative or %Name)
--expand           also list nodes inside instances, marked (from <scene>)
--json             add a `json:` stat line (artifacts/digest.json is always written)
--project-summary  name, main scene, autoloads, input actions, layer names, scenes
Full output: <run dir>/artifacts/digest.txt and digest.json."""

CONFIG_TABLE = "scene"
CONFIG_KEYS = {"project_exclude": list}
DEFAULT_EXCLUDE = ["res://addons"]


def _parser():
    p = out.common_parser("digest")
    p.add_argument("target", nargs="?")
    p.add_argument("--node", default=None)
    p.add_argument("--expand", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--project-summary", action="store_true", dest="summary")
    return p


def _emit_stats(r, fixed: int, lines: list, findings: list, digest_txt_header: list) -> None:
    """Add stat lines honouring the 40-line limit; the full list goes to artifacts/digest.txt."""
    full = digest_txt_header + [f"{k}: {v}" for k, v in lines]
    (r.artifacts_dir / "digest.txt").write_text("\n".join(full) + "\n")
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
    where = r._display_dir() + "artifacts/digest.txt"
    r.stat("more", f"{len(lines) - keep} lines in {where}")


def _action_names(project: Path) -> list:
    """Keys of the [input] section of project.godot, in file order."""
    names, inside = [], False
    for ln in pipeline.read_text(project / "project.godot").splitlines():
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            inside = s == "[input]"
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)=", ln) if inside else None
        if m:
            names.append(m.group(1))
    return names


def _scene_files(project: Path, exclude: list) -> list:
    ex = [project / e[len("res://"):] for e in exclude if e.startswith("res://")]
    found = []
    for dp, dns, fns in os.walk(project):
        d = Path(dp)
        dns[:] = sorted(n for n in dns if not n.startswith(".") and not (d / n / ".gdignore").exists()
                        and (d / n) not in ex)
        for fn in sorted(fns):
            if fn.endswith(".tscn"):
                found.append("res://" + (d / fn).relative_to(project).as_posix())
    return sorted(found)


def _summary(r, args, project: Path, t0: float):
    exclude = r.config.get("scene", {}).get("project_exclude", DEFAULT_EXCLUDE)
    scenes = _scene_files(project, exclude)
    godot.binary(r, project)
    godot.ensure_imported(r, project)
    lst = r.artifacts_dir / "scenes.txt"
    lst.write_text("".join(s + "\n" for s in scenes))
    inv, rec = pipeline.run_digest_runner(r, project, "project", list_file=lst)
    r.add_findings(inv.findings)
    if rec is None:
        if not pipeline.has_errors(r.findings):
            r.finding(None, None, "scene.load-failed", "error", "the digest runner produced no data", source="verb")
        return r.finish("project: no data")
    wanted = _action_names(project)
    acts = {n: ev for n, ev in rec["actions"]}
    lines = [("name", rec["name"]), ("main_scene", rec["main_scene"] or "none")]
    for n, p in rec["autoload"]:
        lines.append(("autoload", f"{n} {p}"))
    for n in wanted:
        if n in acts:
            lines.append(("action", f"{n} " + (", ".join(acts[n]) if acts[n] else "none")))
    for kind in sorted(rec["layers"]):
        items = sorted(rec["layers"][kind])
        lines.append((f"layers-{kind}", " ".join(f"{i}={nm}" for i, nm in items)))
    lines.append(("scenes", str(len(rec["scenes"]))))
    for s in rec["scenes"]:
        lines.append(("scene", f"{s['path']} {s['root'] if s['root'] else '?'} nodes={s['nodes']}"))
    layers = {k: {str(i): nm for i, nm in v} for k, v in rec["layers"].items()}
    d = {"schema": pipeline.DIGEST_SCHEMA, "kind": "project", "path": None, "project": {
        "name": rec["name"], "main_scene": rec["main_scene"], "autoload": rec["autoload"],
        "actions": {n: acts.get(n, []) for n in wanted}, "layers": layers, "scenes": rec["scenes"]}}
    (r.artifacts_dir / "digest.json").write_text(pipeline.dump_json(d))
    if args.json:
        r.stat("json", r._display_dir() + "artifacts/digest.json")
    _emit_stats(r, len(r.stats), lines, r.findings, [f"project: {project}"] + [f"{k}: {v}" for k, v in r.stats[1:]])
    return r.finish(f"project {rec['name']}: {len(rec['scenes'])} scenes ({time.monotonic() - t0:.1f}s)")


def _main(r, args, project: Path):
    t0 = time.monotonic()
    if args.summary:
        if args.target:
            r.error(2, "usage: a target cannot be combined with --project-summary")
        if args.node or args.expand:
            r.error(2, "usage: --node and --expand need a scene target")
        return _summary(r, args, project, t0)
    if not args.target:
        r.error(2, "usage: a scene or resource target (or --project-summary) is required")
    res, fs = pipeline.resolve_target(r, project, args.target, (".tscn", ".tres"))
    is_scene = fs.suffix == ".tscn"
    if (args.node or args.expand) and not is_scene:
        r.error(2, "usage: --node and --expand need a .tscn target")
    godot.binary(r, project)
    godot.ensure_imported(r, project)
    inv, rec = pipeline.run_digest_runner(r, project, "scene" if is_scene else "resource", res, expand=args.expand)
    r.add_findings(inv.findings)
    text = pipeline.read_text(fs)
    if rec is None:
        d = None
    elif is_scene:
        d = pipeline.assemble_scene(res, rec, text)
    else:
        d = pipeline.assemble_resource(res, rec, text)
    node = None
    if args.node and d is not None:
        node = _find_node(d, args.node)
        if node is None:
            r.error(2, f"usage: unknown node '{args.node}' in {res}")
    if d is None or d.get("_status") != "ok" or is_scene:
        r.add_findings(pipeline.structural_findings(d, res) if is_scene or d is None else
                       pipeline.structural_findings(d, res))
    if d is None:
        return r.finish(f"{res}: no digest")
    (r.artifacts_dir / "digest.json").write_text(pipeline.dump_json(d))
    if args.json:
        r.stat("json", r._display_dir() + "artifacts/digest.json")
    lines = model.render(d, node)
    _emit_stats(r, len(r.stats), lines, r.findings, [f"project: {project}"] + [f"{k}: {v}" for k, v in r.stats[1:]])
    el = time.monotonic() - t0
    if is_scene:
        reason = f"{res}: {len(d['nodes'])} nodes, {len(d['connections'])} connections ({el:.1f}s)"
    else:
        reason = f"{res}: {len(d['resource']['props'])} properties ({el:.1f}s)"
    return r.finish(reason)


def _find_node(d: dict, want: str):
    if want.startswith("%"):
        for n in d["nodes"]:
            if n.get("unique") and model.name_of(n["path"]) == want[1:]:
                return n["path"]
        return None
    want = want.strip("/") or "."
    if want.startswith("./"):
        want = want[2:]
    return want if any(n["path"] == want for n in d["nodes"]) else None


def run(argv):
    return out.invoke("digest", argv, _parser(), _main)
