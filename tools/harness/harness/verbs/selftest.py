"""h selftest: run seeded faults and clean entries against the harness (contract 2.10)."""
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import faults, out, proc

HELP = "run seeded faults and clean fixtures, report what was caught"
USAGE = """
h selftest [--area A]... [--id GLOB] [--jobs N] [--keep] [--faults-dir DIR]
Runs every selftest/faults/<ID> (must be caught) and selftest/clean/<ID> (must pass) in a temp copy.
rc 0 all good, 1 a must entry failed or an entry is BROKEN/FALSEPOS, 5 only nice misses, 2 invalid fault.toml."""


def _parser():
    p = out.common_parser("selftest")
    p.add_argument("--area", action="append", default=[])
    p.add_argument("--id", default=None)
    p.add_argument("--jobs", type=int, default=None)
    p.add_argument("--keep", action="store_true")
    p.add_argument("--faults-dir", default=None)
    return p


def _tmp_root() -> Path:
    return Path(os.environ.get("HARNESS_TMP") or (os.environ.get("TMPDIR") or "/tmp") + "/godot-harness")


def _run_entry(r, entry, work: Path, entries_dir: Path) -> dict:
    ed = entries_dir / entry.id
    ed.mkdir(parents=True, exist_ok=True)
    proj = work / entry.id / "proj"
    rec = {"id": entry.id, "area": entry.area, "severity": entry.severity,
           "expected": {"rc": entry.exp_rc, "verdict": entry.exp_verdict},
           "actual": {"rc": None, "verdict": None, "seconds": 0.0, "first_line": "", "lines": 0},
           "result": "BROKEN", "detail": "", "title": entry.title}
    try:
        faults.copy_fixture(entry, proj, ed / "sync-out")
        faults.apply_ops(entry, proj)
    except faults.Broken as e:
        rec["detail"] = str(e)
        return rec
    except OSError as e:
        rec["detail"] = f"fixture copy failed: {e}"
        return rec
    argv = faults.build_argv(entry, proj)
    env = dict(os.environ)
    env.update(entry.env)
    env["HARNESS_OUT"] = str(ed / "out")
    res = proc.run(argv, timeout=entry.max_seconds + 30, cwd=str(work / entry.id), env=env)
    (ed / "stdout.txt").write_text(res.stdout)
    lines = res.stdout.splitlines()
    result, detail = faults.judge(entry, res.rc, res.stdout, res.duration_s)
    rec["actual"] = {"rc": res.rc, "verdict": lines[0].split(" ", 1)[0] if lines else None,
                     "seconds": round(res.duration_s, 2), "first_line": lines[0] if lines else "",
                     "lines": len(lines)}
    rec["result"] = result
    rec["detail"] = detail
    return rec


def _main(r, args, project):
    base = Path(args.faults_dir).expanduser() if args.faults_dir else out.repo_root() / "selftest"
    if not base.is_absolute():
        base = Path.cwd() / base
    entries, errors = faults.load_entries(base, args.area, args.id)
    if errors:
        for path, msg in errors:
            r.finding(str(path), None, "selftest.bad-fault", "error", msg)
        r.error(2, f"{len(errors)} invalid fault.toml (first: {errors[0][1]})"[:100])
    jobs = args.jobs or min(4, os.cpu_count() or 1)
    if jobs < 1:
        r.error(2, "usage: --jobs must be >= 1")
    work = _tmp_root() / f"selftest-{r.run_id}"
    work.mkdir(parents=True, exist_ok=True)
    entries_dir = r.dir / "entries"
    t0 = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            recs = list(ex.map(lambda e: _run_entry(r, e, work, entries_dir), entries))
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
    by = {e.id: e for e in entries}
    faults_r = [x for x in recs if x["id"].startswith("FAULT")]
    clean_r = [x for x in recs if x["id"].startswith("CLEAN")]
    cnt = lambda rows, name: sum(1 for x in rows if x["result"] == name)  # noqa: E731
    missed = [x for x in faults_r if x["result"] == "MISSED"]
    r.stat("faults", f"{len(faults_r)} total, {cnt(faults_r, 'CAUGHT')} caught, {len(missed)} missed "
                     f"(must {sum(1 for x in missed if x['severity'] == 'must')}, "
                     f"nice {sum(1 for x in missed if x['severity'] == 'nice')}), {cnt(faults_r, 'SLOW')} slow, "
                     f"{cnt(faults_r, 'OVERFLOW')} overflow, {cnt(faults_r, 'BROKEN')} broken")
    r.stat("clean", f"{len(clean_r)} total, {cnt(clean_r, 'PASS')} pass, {cnt(clean_r, 'FALSEPOS')} false-positive")
    bad = 0
    for x in recs:
        if x["result"] in ("CAUGHT", "PASS"):
            continue
        e = by[x["id"]]
        hard = x["result"] in ("BROKEN", "FALSEPOS") or e.severity == "must"
        a = x["actual"]
        if x["result"] == "BROKEN":
            detail = f"BROKEN {x['detail']}"
        elif x["result"] == "MISSED":
            rx = f" /{e.regex[0]}/" if e.regex else ""
            detail = (f"MISSED expected {e.exp_verdict} rc={e.exp_rc}{rx}, got {a['verdict']} rc={a['rc']} "
                      f"in {a['seconds']}s")
        else:
            detail = f"{x['result']} {x['detail']} (rc={a['rc']}, {a['seconds']}s)"
        r.check("FAIL" if hard else "WARN", x["id"], detail)
        bad += 1
    r.artifacts_dir.joinpath("matrix.json").write_text(json.dumps(recs, indent=1) + "\n")
    r.extra["selftest"] = {"jobs": jobs, "faults_dir": str(base), "entries": len(recs)}
    dt = time.monotonic() - t0
    return r.finish(f"{len(recs) - bad}/{len(recs)} entries ok ({dt:.0f}s)" if recs else "no entries selected")


def run(argv):
    return out.invoke("selftest", argv, _parser(), _main, need_project=False)
