"""harness.lint: Godot-free lint (A3). Public API for A1 `h check` and A8 hooks (spec 2.3).

    run_lint(run, project, paths=None, mode="full") -> None     mode "full" | "hook"; never starts Godot
    lsp_diag(run, project, files, start=False) -> bool          lint.lsp findings from the opt-in LSP daemon
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from . import checks, project as proj, rules, scan, suppress

LINT_DEFAULTS = {"severity": {}, "exclude": ["res://addons/**"], "replay_dirs": [], "rng_files": ["**/rng.gd"],
                 "remap_files": ["**/*remap*.gd", "**/*rebind*.gd", "**/*keybind*.gd"], "lsp_in_hook": True}
KIND_ORDER = (".gd", ".tscn", ".tres")


def lint_config(run, project: Path) -> dict:
    cfg = getattr(run, "config", None)
    if cfg is None:
        from .. import config
        try:
            cfg = config.load(project)
        except config.ConfigError as e:
            for m in e.messages:
                run.finding("res://harness.toml", None, "harness.config", "error", m)
            run.error(2, f"harness.toml: {e.messages[0]}"[:100])
        run.config = cfg
    lc = dict(LINT_DEFAULTS)
    lc.update(cfg.get("lint", {}))
    lc["sim_dirs"] = cfg.get("harness", {}).get("sim_dirs", ["res://sim"])
    errs = rules.validate_severity_map(lc["severity"])
    if errs:
        for m in errs:
            run.finding("res://harness.toml", None, "harness.config", "error", m)
        run.error(2, f"harness.toml: {errs[0]}"[:100])
    return lc


def _to_path(project: Path, p) -> Path:
    s = str(p)
    if s.startswith("res://"):
        return project / s[len("res://"):]
    q = Path(s).expanduser()
    return q if q.is_absolute() else Path.cwd() / q


def gather(project: Path, paths) -> list:
    """-> sorted list of (Path, kind) under the given files/dirs (all of the project when paths is None)."""
    found: dict = {}
    roots = [project] if paths is None else [_to_path(project, p) for p in paths]
    for root in roots:
        root = Path(os.path.normpath(root))
        try:
            root.relative_to(project)
        except ValueError:
            root = Path(os.path.realpath(root))
        if root.is_dir():
            for dp, dns, fns in os.walk(root):
                dns[:] = sorted(d for d in dns if not d.startswith("."))
                for fn in fns:
                    kind = scan.file_kind(fn)
                    if kind == "project.godot" and Path(dp) != project:
                        kind = None
                    if kind:
                        found[Path(dp) / fn] = kind
        elif root.is_file():
            kind = scan.file_kind(root.name)
            if kind:
                found[root] = kind
    return sorted(found.items(), key=lambda kv: str(kv[0]))


def file_scope(res: str, lc: dict):
    if rules.in_dirs(res, lc["sim_dirs"]):
        return "sim"
    if rules.in_dirs(res, lc["replay_dirs"]):
        return "det"
    return None


def _lint_one(res, kind, text, lc, info):
    """-> list of dict(line, rule, severity, message, hint) before severity overrides/suppression."""
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    scope = file_scope(res, lc) if kind != "project.godot" else None
    exempt = {"lint.det-global-rng": rules.glob_match(res, lc["rng_files"]),
              "lint.raw-keycode": rules.glob_match(res, lc["remap_files"])}

    def allowed(rule):
        rs = rule["scope"]
        if exempt.get(rule["id"], False):
            return False
        if rs == "sim":
            return scope == "sim"
        if rs == "det":
            return scope is not None
        return True

    out = []
    for line, rule in scan.regex_hits(kind, text, lines, allowed):
        sev = rule["severity"]
        if rule["scope"] == "det" and scope == "sim":
            sev = "error"
        out.append({"line": line, "rule": rule["id"], "severity": sev, "message": rule["message"],
                    "hint": rule["hint"]})
    extra = []
    if kind == ".gd":
        extra += checks.indent_mixed(text, lines)
        extra += checks.input_actions(lines, info)
        extra += checks.signal_names(text, lines, info, res)
        if scope is not None:
            extra += checks.det_idle_gd(lines)
        if scope == "sim":
            extra += checks.sim_node_types(lines, info)
    elif kind == ".tscn" and scope is not None:
        extra += checks.det_idle_tscn(lines)
    for line, rid, msg, hint in extra:
        d = rules.default_rule(rid)
        sev = d["severity"]
        if d["scope"] == "det" and scope == "sim":
            sev = "error"
        out.append({"line": line, "rule": rid, "severity": sev, "message": msg or d["message"],
                    "hint": hint or d["hint"]})
    # one finding per (line, rule)
    seen, uniq = set(), []
    for f in out:
        k = (f["line"], f["rule"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq, lines


def run_lint(run, project: Path, paths=None, mode: str = "full") -> None:
    project = Path(project)
    t0 = time.monotonic()
    try:
        lc = lint_config(run, project)
        rules.rules_data()
    except rules.RulesError as e:
        run.error(3, str(e))
    files = gather(project, paths)
    info = proj.ProjectInfo(project)
    known_ids = set(rules.all_rule_ids())
    counts = {".gd": 0, ".tscn": 0, ".tres": 0}
    has_project_godot = False
    skipped = 0
    suppressed = 0
    gd_files = []
    for path, kind in files:
        res = proj.res_of(project, path)
        if rules.glob_match(res, lc["exclude"]):
            skipped += 1
            continue
        if kind == "project.godot":
            has_project_godot = True
        else:
            counts[kind] += 1
        if kind == ".gd":
            gd_files.append(res)
        text = proj.read_text(path)
        found, lines = _lint_one(res, kind, text, lc, info)
        sup_targets, sup_ids = ({}, [])
        if kind == ".gd" and "lint-ignore" in text:
            sup_targets, sup_ids = suppress.parse(lines)
            for ln, rid in sup_ids:
                if rid not in known_ids:
                    sev = rules.resolve_severity("lint.bad-suppress", "warning", lc["severity"])
                    if sev != "off":
                        run.finding(res, ln, "lint.bad-suppress", sev, f"unknown rule id '{rid}' in lint-ignore",
                                    hint="use a real rule id")
        for f in found:
            sev = rules.resolve_severity(f["rule"], f["severity"], lc["severity"])
            if sev == "off":
                continue
            if f["rule"] in sup_targets.get(f["line"], ()):
                suppressed += 1
                run.finding(res, f["line"], f["rule"], "info", f"suppressed: {f['message']}")
                continue
            run.finding(res, f["line"], f["rule"], sev, f["message"], hint=f["hint"] or None)
    run.stat("files", ", ".join([f"{counts['.gd']} .gd", f"{counts['.tscn']} .tscn", f"{counts['.tres']} .tres"])
             + (", project.godot" if has_project_godot else ""))
    run.stat("rules", rules.rule_count())
    if mode == "hook" and skipped:
        run.stat("skipped", f"{skipped} (excluded)")
    if suppressed:
        run.stat("suppressed", suppressed)
    if mode == "hook":
        run.stat("lsp", _hook_lsp(run, project, lc, gd_files))
    run.extra["lint"] = {"mode": mode, "files": sum(counts.values()) + (1 if has_project_godot else 0),
                         "skipped": skipped, "suppressed": suppressed, "seconds": round(time.monotonic() - t0, 3)}


def _hook_lsp(run, project: Path, lc: dict, gd_res: list) -> str:
    if not lc["lsp_in_hook"]:
        return "off"
    from . import lsp_daemon
    if lsp_daemon.running_state(project) is None:
        return "not running"
    if not gd_res:
        return "used"
    before = len(run.findings)
    from . import lsp_client
    files = [project / r[len("res://"):] for r in gd_res]
    lsp_diag(run, project, files, start=False)
    timeouts = [f for f in run.findings[before:] if f["rule"] == "lint.lsp-timeout"]
    return "timeout" if timeouts else "used"


def lsp_diag(run, project: Path, files, start: bool = False) -> bool:
    """Adds lint.lsp findings for `files`; start=True starts a daemon, diags and stops it (oneshot)."""
    from . import lsp_daemon, lsp_client
    project = Path(project)
    started_here = False
    state = lsp_daemon.running_state(project)
    if state is None:
        if not start:
            return False
        state = lsp_daemon.start(run, project)
        if state is None:
            return False
        started_here = True
    try:
        for f in files:
            f = _to_path(project, f)
            res = proj.res_of(project, f)
            for fd in lsp_client.diagnose(state["port"], project, f, res):
                sev = {1: "error", 2: "warning"}.get(fd["severity"], "info")
                if fd["kind"] == "timeout":
                    run.finding(res, None, "lint.lsp-timeout", "warning", "no diagnostics from the LSP within 5 s",
                                hint="the daemon may be busy; retry or use h check")
                else:
                    run.finding(res, fd["line"], "lint.lsp", sev, fd["message"])
    finally:
        if started_here:
            lsp_daemon.stop(project)
    return True


def proj_res(project: Path, p) -> str:
    p = Path(p)
    try:
        return proj.res_of(project, p)
    except ValueError:
        return proj.res_of(project, Path(os.path.realpath(p)))
