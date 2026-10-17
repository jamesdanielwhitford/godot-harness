"""h test: run gdUnit4 suites and return a trustworthy verdict (A4 spec 04_test_runner.md)."""
import json
import shutil
import time
from pathlib import Path

from .. import godot, gdunit, out, pins, sync

HELP = "run gdUnit4 tests: verdict plus res://file:line failures"
USAGE = """
h test [TARGET ...] [--filter SUBSTR] [--changed] [--dotnet] [--project DIR] [--strict]
TARGET: res://dir/ | res://x.gd | fs path | suite stem (test_counter) | <suite>::<test_name>
(none)          every suite under [harness] test_dir (default res://tests)
--filter SUBSTR keep only tests whose name contains SUBSTR
--changed       suites changed in git (and test_<X>.gd for changed X.gd); nothing changed = PASS
--dotnet        disabled in v0 (GDScript only)
config [test]: orphans = warn|fail|ignore, push_error = warn|fail"""

CONFIG_TABLE = "test"
CONFIG_KEYS = {"orphans": str, "push_error": str}
SCRIPT = "res://addons/gdUnit4/bin/GdUnitCmdTool.gd"
ORPHAN_SEV = {"warn": "warning", "fail": "error", "ignore": "info"}


def _parser():
    p = out.common_parser("test")
    p.add_argument("targets", nargs="*")
    p.add_argument("--filter", default=None)
    p.add_argument("--changed", action="store_true")
    p.add_argument("--dotnet", action="store_true")
    return p


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _policy(r, key, allowed):
    v = r.config.get("test", {}).get(key, "warn")
    if v not in allowed:
        r.error(2, f"harness.toml: [test] {key} must be one of {'|'.join(allowed)}, got {v!r}")
    return v


def _finish(r, rc_g, state, t0, reason, tests_stat, rows, sel_info, extra_counts):
    r.max_lines = 15
    e = extra_counts
    r.extra.update({"gdunit_rc": rc_g, "total": e["total"], "passed": e["passed"], "failed": e["failed"],
                    "errors": e["errors"], "skipped": e["skipped"], "orphans": e["orphans"],
                    "suites": len(sel_info["suites"])})
    tj = {"schema": "harness.tests/1", "gdunit_rc": rc_g, "selected": sel_info, "tests": rows}
    (r.artifacts_dir / "tests.json").write_text(json.dumps(tj, indent=1) + "\n")
    return r.finish(reason.replace("<t>", f"{time.monotonic() - t0:.1f}"))


def _main(r, args, project):
    t0 = time.monotonic()
    r.max_lines = 15
    if args.dotnet:
        r.error(2, "--dotnet is disabled in v0 (D1: GDScript only)")
    if args.changed and args.targets:
        r.error(2, "--changed cannot be combined with TARGET")
    orphan_pol = _policy(r, "orphans", ("warn", "fail", "ignore"))
    push_pol = _policy(r, "push_error", ("warn", "fail"))
    test_dir = r.config["harness"].get("test_dir", "res://tests")
    if not test_dir.startswith("res://"):
        test_dir = "res://" + test_dir.lstrip("/")

    def usage(msg):
        r.error(2, msg)

    # 1. selection (no Godot)
    if args.changed:
        sel = gdunit.git_changed(usage, project, test_dir)
    else:
        sel = gdunit.resolve_targets(usage, project, test_dir, args.targets)
    names_of = {}
    chosen = {}
    for suite in sel:
        names_of[suite] = gdunit.list_suites(project, project / suite[len("res://"):]).get(suite, [])
    for suite, names in sel.items():
        pick = names_of[suite] if names is None else [n for n in names_of[suite] if n in names]
        if args.filter is not None:
            pick = [n for n in pick if args.filter in n]
        if pick:
            chosen[suite] = pick
    suites = sorted(chosen)
    total_sel = sum(len(v) for v in chosen.values())
    sel_info = {"suites": suites, "targets": list(args.targets), "filter": args.filter, "changed": args.changed}

    # 2. gdUnit4 present / installed
    state = sync.install_gdunit4(r, project)
    gd_ver = pins.load()["gdunit4_tag"]
    given = bool(args.targets or args.filter is not None or args.changed)
    desc = " ".join(args.targets) if args.targets else ""
    if args.filter is not None:
        desc = (desc + " " if desc else "") + f"--filter {args.filter}"
    if args.changed:
        desc = "--changed"
    zero = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "orphans": 0}

    if not suites:
        if args.changed and not sel:
            r.stat("gdunit4", f"{gd_ver} {state}")
            r.stat("tests", "not run")
            r.stat("selected", "0 suites (--changed: no changed tests)")
            return _finish(r, None, state, t0, "no changed tests (<t>s)", "", [], sel_info, zero)
        what = "no tests selected" if not sel or args.filter is not None else "gdUnit4 ran 0 tests"
        r.stat("gdunit4", f"{gd_ver} {state}")
        r.stat("tests", "not run")
        if given:
            r.stat("selected", f"0 suites, 0 tests ({desc})")
        r.finding(None, None, "test.no-tests", "error", "no tests selected",
                  hint=f"targets: {desc or test_dir}; suites need 'extends GdUnitTestSuite' and func test_*")
        return _finish(r, None, state, t0, f"tests not run: {what} (<t>s)", "", [], sel_info, zero)

    # 3. import + run
    godot.ensure_imported(r, project)
    rd = f"res://.harness/gdunit/{r.run_id}"
    gargs = ["-s", SCRIPT, "--ignoreHeadlessMode", "-c", "-rd", rd]
    for s in suites:
        gargs += ["-a", s]
    for s in suites:
        for n in names_of[s]:
            if n not in chosen[s]:
                gargs += ["-i", f"{s}:{n}"]
    inv = godot.run(r, "test", project, args=gargs, expected_rc={0, 100, 101, 105})
    rc_g = inv.rc

    # 4. move the report out of the project
    rdir = project / ".harness" / "gdunit" / r.run_id
    xml_text = ""
    try:
        rep = next(iter(sorted(rdir.glob("report_*"))), None)
        if rep is not None and rep.is_dir():
            dest = r.artifacts_dir / "gdunit"
            dest.mkdir(exist_ok=True)
            for item in rep.iterdir():
                shutil.move(str(item), str(dest / item.name))
            if (dest / "results.xml").is_file():
                xml_text = (dest / "results.xml").read_text(encoding="utf-8", errors="replace")
    finally:
        shutil.rmtree(rdir, ignore_errors=True)
        gd_parent = project / ".harness" / "gdunit"
        try:
            gd_parent.rmdir()
        except OSError:
            pass

    if rc_g in (103, 104):
        r.error(4, "gdUnit4 refused headless mode" if rc_g == 103 else "gdUnit4 does not support this Godot version")

    rows = gdunit.parse_results(xml_text) if xml_text else []
    con = gdunit.parse_console(inv.text)
    flines = {s: gdunit.func_lines(project, s) for s in suites}

    def fline(suite, name):
        return flines.get(suite, {}).get(name.split(":")[0].split(" ")[0])

    findings = []
    for row in rows:
        row["duration_s"] = float(row["duration_s"])
        if row["status"] in ("failed", "error"):
            if row["path"] is None:
                row["path"], row["line"] = row["suite"], fline(row["suite"], row["name"])
            elif row["line"] is None:
                row["line"] = fline(row["suite"], row["name"])
            stem = Path(row["suite"]).stem
            rule = "test.failed" if row["status"] == "failed" else "test.error"
            findings.append({"path": row["path"], "line": row["line"], "rule": rule, "severity": "error",
                             "message": f"{stem}::{row['name']}: {row['message'] or 'failed'}", "hint": None,
                             "source": "verb", "invocation": inv.n})
    # orphans
    row_by = {(x["suite"], x["name"].split(":")[0].split(" ")[0]): x for x in rows}
    orphan_nodes = 0
    for o in con["orphans"]:
        orphan_nodes += o["count"]
        stem = Path(o["suite"]).stem
        tname = o["test"] or "(suite)"
        x = row_by.get((o["suite"], o["test"]))
        if x is not None and x["status"] == "passed":
            x["status"] = "orphans"
        findings.append({"path": o["suite"], "line": fline(o["suite"], o["test"]) if o["test"] else None,
                         "rule": "test.orphans", "severity": ORPHAN_SEV[orphan_pol],
                         "message": f"{stem}::{tname}: {o['count']} possible orphan node(s)",
                         "hint": "free() nodes you create or wrap them in auto_free()", "source": "verb",
                         "invocation": inv.n})
    # hung tests
    hung_msg = None
    for h in con["hung"][-1:]:
        if inv.timed_out:
            hung_msg = f"{Path(h['suite']).stem}::{h['test']}"
            rows.append({"suite": h["suite"], "name": h["test"], "status": "hung", "duration_s": 0.0,
                         "path": h["suite"], "line": fline(h["suite"], h["test"]),
                         "message": "did not finish before the timeout"})
    # scan findings: policy and dedup
    located = {(f["path"], f["line"]) for f in findings if f["rule"] in ("test.failed", "test.error")}
    for f in inv.findings:
        f = dict(f)
        if f["rule"] == "harness.hang" and hung_msg:
            h = con["hung"][-1]
            f["path"], f["line"] = h["suite"], fline(h["suite"], h["test"])
            f["message"] += f" in test '{hung_msg}'"
        elif f["rule"] == "harness.rc" and rc_g == 1:
            f["hint"] = "GdUnitCmdTool failed to load (see log; try h import, h sync)"
        elif f["source"] == "scan":
            if f["path"] is not None and (f["path"], f["line"]) in located:
                continue
            if f["rule"] == "godot.error" and push_pol == "warn":
                f["severity"] = "warning"
        findings.append(f)

    counts = {"total": len(rows), "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "orphans": orphan_nodes}
    for x in rows:
        st = x["status"]
        if st in ("passed", "orphans"):
            counts["passed"] += 1
        elif st == "failed":
            counts["failed"] += 1
        elif st == "error":
            counts["errors"] += 1
        elif st == "skipped":
            counts["skipped"] += 1
    ran = bool(xml_text) and bool(rows)
    if not ran and rc_g == 0:
        n = con["counts"].get("tests", 0)
        if n:
            counts.update(total=n, passed=n - con["counts"].get("errors", 0) - con["counts"].get("failures", 0))
    if rc_g == 0 and counts["total"] == 0:
        findings.append({"path": None, "line": None, "rule": "test.no-tests", "severity": "error",
                         "message": "gdUnit4 ran 0 tests", "hint": f"targets: {desc or test_dir}", "source": "verb",
                         "invocation": inv.n})
    elif rc_g == 100 and not rows:
        findings.append({"path": None, "line": None, "rule": "test.report-missing", "severity": "error",
                         "message": "gdUnit4 exited 100 but wrote no results.xml", "hint": None, "source": "verb",
                         "invocation": inv.n})
    r.add_findings(findings)

    r.stat("gdunit4", f"{gd_ver} {state}" + (f", rc {rc_g}" if rc_g != 0 else ""))
    if ran or counts["total"]:
        r.stat("tests", f"{counts['total']} total, {counts['passed']} passed, {counts['failed']} failed, "
                        f"{counts['errors']} errors, {counts['skipped']} skipped, {counts['orphans']} orphans")
    else:
        r.stat("tests", "not run")
    if given:
        r.stat("selected", f"{len(suites)} suites, {total_sel} tests ({desc})")

    if ran:
        parts = []
        if counts["failed"]:
            parts.append(f"{counts['failed']} failed")
        if counts["errors"]:
            parts.append(_plural(counts["errors"], "error", "errors"))
        if orphan_nodes:
            parts.append(_plural(orphan_nodes if not con["orphans"] else len(con["orphans"]),
                                 "orphan warning", "orphan warnings"))
        parts.append(f"{counts['passed']} passed")
        reason = f"{', '.join(parts)} of {counts['total']} tests (<t>s)"
    else:
        why = ("hang, timed out" if inv.timed_out else
               "script errors in test discovery" if rc_g == 105 else
               f"gdUnit4 exited {rc_g}" if rc_g else "gdUnit4 ran 0 tests")
        reason = f"tests not run: {why} (<t>s)"
    return _finish(r, rc_g, state, t0, reason, "", rows, sel_info, counts)


def run(argv):
    return out.invoke("test", argv, _parser(), _main)
