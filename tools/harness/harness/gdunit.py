"""gdUnit4 helpers for `h test` (A4 spec 3.1).

Public (unit tests, REVIEW R-01): parse_results(xml_text) and parse_console(log_text). Both are pure, stdlib only.
Everything else here is private to the verb; it imports other harness modules inside functions only.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_AT_LOC = re.compile(r"at '[^']*' in (res://[^:\s]+):(\d+)")
_AT_LINE = re.compile(r"^\s*at '.*' in res://")
_RES_LOC = re.compile(r"(res://[^:\s]+):(\d+)")
_STAT_RE = re.compile(r"(\d+) test cases \| (\d+) errors \| (\d+) failures \| (\d+) flaky \| (\d+) skipped \| "
                      r"(\d+) orphans")
_TEST_LINE = re.compile(r"^\s*(res://\S+) > (.+?) (STARTED|PASSED|FAILED|ERROR|SKIPPED)\b")
_ORPHAN_LINE = re.compile(r"WARNING:\s*Detected (\d+) possible orphan nodes")
SUITE_RE = re.compile(r"^extends\s+(GdUnitTestSuite\b|\"res://addons/gdUnit4/src/GdUnitTestSuite.gd\")", re.M)
FUNC_RE = re.compile(r"^func\s+(test_\w+)\s*\(", re.M)


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


# ---- results.xml ------------------------------------------------------------------------------------------------
def _collapse(text: str) -> str:
    keep = [ln.strip() for ln in text.splitlines() if not _AT_LINE.match(ln)]
    return re.sub(r"\s+", " ", " ".join(k for k in keep if k)).strip()


def _float(s) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def parse_results(xml_text: str) -> list:
    """-> [{suite, name, status, duration_s, path, line, message}] in document order."""
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        return []
    rows = []
    for ts in root.iter("testsuite"):
        pkg = (ts.get("package") or "").strip("/")
        name = ts.get("name") or ""
        suite = "res://" + (f"{pkg}/" if pkg else "") + name + ".gd"
        for tc in ts.findall("testcase"):
            status, body, attr_msg = "passed", "", ""
            for tag, st in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
                el = tc.find(tag)
                if el is not None:
                    status, body, attr_msg = st, el.text or "", el.get("message") or ""
                    break
            path = line = message = None
            if status in ("failed", "error"):
                locs = _AT_LOC.findall(body)
                if locs:
                    path, line = locs[-1][0], int(locs[-1][1])
                else:
                    m = _RES_LOC.search(attr_msg)
                    if m:
                        path, line = m.group(1), int(m.group(2))
                message = _collapse(body) or _collapse(attr_msg)
            elif status == "skipped":
                message = _collapse(body) or _collapse(attr_msg) or None
            rows.append({"suite": suite, "name": tc.get("name") or "", "status": status,
                         "duration_s": _float(tc.get("time")), "path": path, "line": line, "message": message})
    return rows


# ---- console ----------------------------------------------------------------------------------------------------
def _base_name(n: str) -> str:
    return re.split(r"[: ]", n, maxsplit=1)[0]


def parse_console(log_text: str) -> dict:
    """-> {counts, hung, orphans, lines}. counts: tests/errors/failures/flaky/skipped/orphans (empty when none)."""
    lines = strip_ansi(log_text).splitlines()
    overall = None
    stats = []
    open_tests: dict = {}
    order: list = []
    last_end = None
    last_suite = None
    orphans = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("Overall Summary:"):
            m = _STAT_RE.search(s)
            if m:
                overall = [int(x) for x in m.groups()]
            continue
        if s.startswith("Statistics:"):
            m = _STAT_RE.search(s)
            if m:
                stats.append([int(x) for x in m.groups()])
            continue
        m = _TEST_LINE.match(ln)
        if m:
            suite, name, ev = m.group(1), m.group(2), m.group(3)
            last_suite = suite
            key = (suite, name)
            if ev == "STARTED":
                open_tests[key] = True
                order.append(key)
            else:
                open_tests.pop(key, None)
                last_end = key
            continue
        m = _ORPHAN_LINE.search(ln)
        if m:
            n = int(m.group(1))
            if last_end is not None:
                orphans.append({"suite": last_end[0], "test": _base_name(last_end[1]), "count": n})
            elif last_suite is not None:
                orphans.append({"suite": last_suite, "test": "", "count": n})
    vals = overall or ([sum(c) for c in zip(*stats)] if stats else None)
    counts = {}
    if vals:
        counts = dict(zip(("tests", "errors", "failures", "flaky", "skipped", "orphans"), vals))
    hung = [{"suite": k[0], "test": _base_name(k[1])} for k in order if k in open_tests]
    return {"counts": counts, "hung": hung, "orphans": orphans, "lines": lines}


# ---- private helpers for the verb ---------------------------------------------------------------------------------
def _dist(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def did_you_mean(word: str, options) -> str:
    best = sorted(options, key=lambda o: _dist(word, o))
    if best and _dist(word, best[0]) <= 2:
        return f" (did you mean '{best[0]}'?)"
    return ""


def func_lines(project: Path, suite_res: str) -> dict:
    """{test name: 1-based line} of a suite file."""
    try:
        text = (Path(project) / suite_res[len("res://"):]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out = {}
    for i, ln in enumerate(text.splitlines(), 1):
        m = FUNC_RE.match(ln)
        if m and m.group(1) not in out:
            out[m.group(1)] = i
    return out


def is_suite_text(text: str) -> bool:
    return bool(SUITE_RE.search(text))


def list_suites(project: Path, under: Path) -> dict:
    """{res path: [test names]} of every GdUnitTestSuite file below `under` (or `under` itself if a file)."""
    project = Path(project)
    found = {}
    files = []
    if under.is_file():
        files = [under]
    else:
        for dp, dns, fns in os.walk(under):
            dns[:] = sorted(d for d in dns if not d.startswith(".") and d != "addons")
            files += [Path(dp) / f for f in sorted(fns) if f.endswith(".gd")]
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not is_suite_text(text):
            continue
        res = "res://" + f.relative_to(project).as_posix()
        names = []
        for m in FUNC_RE.finditer(text):
            if m.group(1) not in names:
                names.append(m.group(1))
        found[res] = names
    return dict(sorted(found.items()))


def resolve_targets(error, project: Path, test_dir: str, targets: list) -> dict:
    """-> {suite res path: None (whole suite) | set(test names)}. `error(msg)` raises a usage error (rc 2)."""
    project = Path(project).resolve()
    cwd = Path.cwd()
    base = project / test_dir[len("res://"):] if test_dir.startswith("res://") else project / test_dir
    sel: dict = {}

    def add(suite, names):
        if suite in sel and sel[suite] is None:
            return
        if names is None:
            sel[suite] = None
        else:
            sel.setdefault(suite, set()).update(names)

    if not targets:
        for suite in list_suites(project, base) if base.exists() else {}:
            add(suite, None)
        return sel
    for t in targets:
        left, sep, tname = t.rpartition("::") if "::" in t else (t, "", "")
        pathform = left.startswith("res://") or "/" in left or left.endswith(".gd")
        if pathform:
            p = project / left[len("res://"):] if left.startswith("res://") else Path(left).expanduser()
            if not left.startswith("res://") and not p.is_absolute():
                p = cwd / p
            p = Path(os.path.normpath(p))
            try:
                p.relative_to(project)
            except ValueError:
                try:
                    p = p.resolve()
                    p.relative_to(project)
                except ValueError:
                    error(f"path outside the project: {t}")
            if not p.exists():
                error(f"no such test path: {t}")
            if p.is_dir():
                if sep:
                    error(f"'::' after a directory: {t}")
                for suite in list_suites(project, p):
                    add(suite, None)
                continue
            if p.suffix != ".gd":
                error(f"not a .gd file: {t}")
            res = "res://" + p.relative_to(project).as_posix()
            suites = list_suites(project, p)
            if res not in suites:
                error(f"not a gdUnit4 suite (extends GdUnitTestSuite): {res}")
        else:
            allsuites = list_suites(project, base) if base.exists() else {}
            hits = [s for s in allsuites if Path(s).stem == left]
            if not hits:
                error(f"unknown suite '{left}'" + did_you_mean(left, sorted({Path(s).stem for s in allsuites})))
            if len(hits) > 1:
                error(f"suite '{left}' is ambiguous: {', '.join(hits)}")
            res = hits[0]
            suites = allsuites
        if sep:
            names = suites[res]
            if tname not in names:
                error(f"no test '{tname}' in {res}" + did_you_mean(tname, names))
            add(res, [tname])
        else:
            add(res, None)
    return sel


def git_changed(error, project: Path, test_dir: str) -> dict:
    """Suites selected by --changed (spec 2.1): {res: None}."""
    from . import proc
    project = Path(project).resolve()
    g = proc.run(["git", "-C", str(project), "rev-parse", "--show-toplevel"], timeout=15)
    if g.rc != 0 or not g.stdout.strip():
        error("--changed needs a git work tree")
    top = Path(g.stdout.strip()).resolve()
    st = proc.run(["git", "-C", str(project), "status", "--porcelain", "--untracked-files=all"], timeout=60)
    if st.rc != 0:
        error("--changed: git status failed")
    changed = []
    for ln in st.stdout.splitlines():
        if len(ln) < 4:
            continue
        code, rest = ln[:2], ln[3:]
        if "D" in code and "R" not in code:
            continue
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        f = (top / rest).resolve()
        try:
            changed.append(f.relative_to(project))
        except ValueError:
            continue
    base_res = test_dir if test_dir.endswith("/") else test_dir + "/"
    base = project / base_res[len("res://"):]
    allsuites = list_suites(project, base) if base.exists() else {}
    sel: dict = {}
    for rel in changed:
        if rel.suffix != ".gd":
            continue
        res = "res://" + rel.as_posix()
        if res in allsuites:
            sel[res] = None
        elif not rel.name.startswith("test_"):
            for s in allsuites:
                if Path(s).name == f"test_{rel.name}":
                    sel[s] = None
    return dict(sorted(sel.items()))
