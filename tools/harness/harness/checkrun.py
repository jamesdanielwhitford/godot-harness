"""Phase driver of `h check` (A1 3.2): batch load-check via runners/load_check.gd, record -> finding mapping,
hang/crash/early-quit attribution with resume, scan merge, rc merge.

Public for other areas: load_check(run, project, res_paths, smoke=0) -> list[dict] (REVIEW R-30). It does not import,
does not lint and does NOT add the findings to the Run; its invocations are recorded in run.json.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from . import godot, logscan

MAX_RESUMES = 3
CHECK_LOAD = "check.load-failed"
CHECK_INST = "check.instantiate-failed"
RUNNER_RULES = ("harness.hang", "harness.crash", "harness.runner-incomplete")
_FRAME_RE = re.compile(r"^(res://.+):(\d+)$")
_PREFIX = {0: "ERROR", 1: "WARNING", 2: "SCRIPT ERROR"}


def norm_msg(m: str) -> str:
    m = " ".join(str(m).split())
    return m[len("Parse Error: "):] if m.startswith("Parse Error: ") else m


def _loc_of(rec: dict, item: str, msg: str):
    f = rec.get("file") or ""
    if f.startswith("res://"):
        ln = rec.get("line") or 0
        return f, (ln if ln > 0 else None)
    for fr in rec.get("bt") or []:
        m = _FRAME_RE.match(fr)
        if m:
            return m.group(1), int(m.group(2))
    m = logscan.TOKEN_LOC.search(msg)
    if m:
        return m.group(1), int(m.group(2))
    return item, None


def _finding(path, line, rule, sev, msg, n, source="runner", hint=None):
    return {"path": path, "line": line, "rule": rule, "severity": sev, "message": msg, "hint": hint,
            "source": source, "invocation": n}


def record_findings(item: str, status: str, recs: list, n: int) -> list:
    """Map one `end` record to findings (A1 3.2 step 6)."""
    out = []
    failed = status in ("load-failed", "instantiate-failed")
    if failed:
        pick = None
        for r in recs:
            m = r.get("msg", "")
            if "Parse Error" in m or "Invalid scene" in m or "res://" in m:
                pick = r
                break
        if pick is None and recs:
            pick = recs[0]
        if pick is not None:
            msg = pick.get("msg", "").strip().splitlines()[0] if pick.get("msg", "").strip() else status
            p, ln = _loc_of(pick, item, msg)
            ln = ln if p == item else None
        else:
            msg = "ResourceLoader.load returned null" if status == "load-failed" else "instantiate() returned null"
            ln = None
        rule = CHECK_LOAD if status == "load-failed" else CHECK_INST
        out.append(_finding(item, ln, rule, "error", msg, n))
    for r in recs:
        raw = str(r.get("msg", "")).strip()
        first = raw.splitlines()[0] if raw else ""
        line = f"{_PREFIX.get(r.get('type', 0), 'ERROR')}: {first}"
        c = logscan.classify_line(line)
        if c is None:
            rule, sev, msg = "godot.error", "error", first
        else:
            (rule, _, sev, _, kind), msg = c[0], c[1]
        if rule == "godot.script-load-failed":
            qm = re.search(r'"(res://[^"]+)"', first)
            path, ln = (qm.group(1) if qm else item), None
        elif rule in ("godot.crash",):
            path, ln = None, None
        else:
            path, ln = _loc_of(r, item, first)
        if failed and first.startswith("Condition \""):
            sev = "info"
        out.append(_finding(path, ln, rule, sev, msg, n))
    return out


def _parse_items(inv) -> tuple:
    """-> (begun paths in order, {path: end record}, done record or None)."""
    begun, ends, done = [], {}, None
    for r in inv.records:
        if r.get("t") == "data" and r.get("ev") == "begin":
            begun.append(r["path"])
        elif r.get("t") == "data" and r.get("ev") == "end":
            ends[r["path"]] = r
        elif r.get("t") == "done":
            done = r
    return begun, ends, done


def _run_phase(run, project, mode: str, items: list, kind: str, smoke: int, out_findings: list):
    pending = list(items)
    resumes = 0
    t0 = time.monotonic()
    run_no = 0
    while pending:
        run_no += 1
        lst = run.artifacts_dir / (f"{'scripts' if mode == 'scripts' else 'scenes'}"
                                   f"{'' if run_no == 1 else '-' + str(run_no)}.txt")
        lst.write_text("".join(p + "\n" for p in pending))
        user = ["--mode", mode, "--list", str(lst)] + (["--smoke", str(smoke)] if smoke else [])
        inv = godot.run(run, kind, project, runner="load_check", user_args=user)
        begun, ends, done = _parse_items(inv)
        open_item = next((p for p in begun if p not in ends), None)
        rec_msgs = set()
        for p in begun:
            e = ends.get(p)
            if e is None:
                continue
            fs = record_findings(p, e.get("status", "ok"), e.get("recs", []), inv.n)
            out_findings += fs
            rec_msgs |= {norm_msg(r.get("msg", "")) for r in e.get("recs", [])}
        # generic findings of the invocation (scan, rc, hang/crash/incomplete)
        for f in inv.findings:
            if f["source"] == "runner":
                out_findings.append(f)
            elif f["rule"] in RUNNER_RULES:
                if open_item is None or f["rule"] == "harness.runner-incomplete" and done is not None:
                    out_findings.append(f)
                else:
                    g = dict(f)
                    g["path"] = open_item
                    out_findings.append(g)
            elif f["source"] == "scan":
                if norm_msg(f["message"]) in rec_msgs:
                    continue
                out_findings.append(f)
            else:
                out_findings.append(f)
        if done is not None and not inv.timed_out and inv.rc < 128 and inv.rc != done.get("rc"):
            out_findings.append(_finding(None, None, "harness.rc", "warning",
                                         f"exit code {inv.rc} but runner reported {done.get('rc')} "
                                         f"(project code called quit()?)", inv.n, source="verb"))
        if open_item is None:
            break
        if done is not None and not inv.timed_out and inv.rc < 128:
            break  # the runner finished; nothing is open in practice
        idx = items.index(open_item) if open_item in items else len(items) - 1
        pending = [p for p in items[idx + 1:] if p in pending]
        # items that were pending but never began and come before? (cannot happen: runner is sequential)
        if pending and resumes >= MAX_RESUMES:
            run.check("SKIP", mode, f"{len(pending)} files not checked after {MAX_RESUMES} hangs")
            break
        resumes += 1
    return round(time.monotonic() - t0, 1)


def _finalize(findings: list) -> list:
    """Cross-phase dedupe by (path, line, normalised message) and the parse-error / load-failed rule."""
    parse_paths = {f["path"] for f in findings if f["rule"] == "godot.parse-error"}
    seen, res = set(), []
    for f in findings:
        if f["rule"] == "godot.script-load-failed" and f["path"] in parse_paths:
            continue
        key = (f["path"], f["line"], norm_msg(f["message"]), f["severity"])
        if key in seen:
            continue
        seen.add(key)
        res.append(f)
    return res


def load_check(run, project, res_paths: list, smoke: int = 0) -> list:
    """A1 3.2 steps 3-8 without file-set building, import or lint."""
    paths = sorted(set(res_paths))
    scripts = [p for p in paths if p.endswith(".gd")]
    scenes = [p for p in paths if p.endswith((".tscn", ".tres"))]
    found: list = []
    timings = run.extra.setdefault("check", {}).setdefault("timings", {})
    if scripts:
        timings["scripts"] = _run_phase(run, project, "scripts", scripts, "runner", 0, found)
    if scenes:
        timings["scenes"] = _run_phase(run, project, "scenes", scenes, "smoke" if smoke else "runner", smoke, found)
    return _finalize(found)
