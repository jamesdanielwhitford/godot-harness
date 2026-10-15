"""fault.toml loader/validator and the entry runner pieces of `h selftest` (contract 2.10)."""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import out, proc

ID_RE = re.compile(r"^(FAULT|CLEAN)-(P0|A(?:10|[1-9]))-\d{2}$")
SAMPLE_EXCLUDE = (".godot", ".harness")
COPY_EXCLUDE = (".godot", ".harness")
VERDICTS = ("PASS", "FAIL", "WARN", "ERROR")


class Broken(Exception):
    """An apply op or fixture step failed (result BROKEN)."""


@dataclass
class Entry:
    id: str
    kind: str            # FAULT | CLEAN
    area: str
    title: str
    fixture: str
    severity: str
    source: str
    apply: list
    verb: str
    args: list
    env: dict
    no_project: bool
    exp_rc: int
    exp_verdict: str
    regex: list
    not_regex: list
    max_seconds: float
    dir: Path
    toml_path: Path


def _fixtures_root() -> Path:
    return out.repo_root() / "tests" / "fixtures" / "projects"


def validate(data: dict, d: Path) -> list:
    """Return a list of schema error strings."""
    errs = []
    for k in ("id", "area", "title", "fixture", "severity"):
        if not isinstance(data.get(k), str) or not data.get(k):
            errs.append(f"missing or invalid '{k}'")
    fid = data.get("id")
    if isinstance(fid, str):
        m = ID_RE.match(fid)
        if not m:
            errs.append(f"id '{fid}' does not match (FAULT|CLEAN)-(P0|A1..A10)-NN")
        else:
            if fid != d.name:
                errs.append(f"id '{fid}' differs from directory name '{d.name}'")
            if data.get("area") != m.group(2):
                errs.append(f"area '{data.get('area')}' does not match id")
    if data.get("severity") not in ("must", "nice"):
        errs.append("severity must be must or nice")
    fx = data.get("fixture")
    if isinstance(fx, str) and fx not in ("none", "@sample") and not (_fixtures_root() / fx).is_dir():
        errs.append(f"unknown fixture '{fx}'")
    ap = data.get("apply", [])
    if not isinstance(ap, list):
        errs.append("apply must be a list")
        ap = []
    for i, op in enumerate(ap):
        if not isinstance(op, dict) or op.get("op") not in ("write", "replace", "delete"):
            errs.append(f"apply[{i}]: op must be write, replace or delete")
            continue
        if not isinstance(op.get("path"), str):
            errs.append(f"apply[{i}]: missing path")
        if op["op"] == "write" and ("text" in op) == ("from" in op):
            errs.append(f"apply[{i}]: write needs exactly one of text, from")
        if op["op"] == "replace" and not (isinstance(op.get("old"), str) and isinstance(op.get("new"), str)):
            errs.append(f"apply[{i}]: replace needs old and new")
    run = data.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("verb"), str):
        errs.append("run.verb missing")
    else:
        if not isinstance(run.get("args", []), list):
            errs.append("run.args must be a list")
        if not isinstance(run.get("env", {}), dict):
            errs.append("run.env must be a table")
    exp = data.get("expect")
    if not isinstance(exp, dict):
        errs.append("expect missing")
    else:
        if isinstance(exp.get("rc"), bool) or not isinstance(exp.get("rc"), int):
            errs.append("expect.rc missing or not an integer")
        if exp.get("verdict") not in VERDICTS:
            errs.append("expect.verdict must be PASS, FAIL, WARN or ERROR")
        for k in ("regex", "not_regex"):
            v = exp.get(k, [])
            if not isinstance(v, list):
                errs.append(f"expect.{k} must be a list")
                continue
            for rx in v:
                try:
                    re.compile(rx)
                except (re.error, TypeError):
                    errs.append(f"expect.{k}: invalid regex {rx!r}")
        ms = exp.get("max_seconds", 60)
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or ms <= 0:
            errs.append("expect.max_seconds must be a positive number")
    return errs


def load_entries(faults_dir: Path, areas=(), id_glob=None):
    """-> (entries sorted by id, [(toml path, message)] schema errors)."""
    entries, errors = [], []
    areas = {a.upper() for a in areas}
    for sub in ("faults", "clean"):
        base = Path(faults_dir) / sub
        if not base.is_dir():
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            tp = d / "fault.toml"
            if not tp.is_file():
                continue
            try:
                data = tomllib.loads(tp.read_text(encoding="utf-8"))
            except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
                errors.append((tp, f"invalid TOML: {e}"))
                continue
            errs = validate(data, d)
            if errs:
                errors += [(tp, m) for m in errs]
                continue
            if areas and data["area"].upper() not in areas:
                continue
            if id_glob and not fnmatch.fnmatch(data["id"], id_glob):
                continue
            run, exp = data["run"], data["expect"]
            entries.append(Entry(
                id=data["id"], kind=data["id"].split("-")[0], area=data["area"], title=data["title"],
                fixture=data["fixture"], severity=data["severity"], source=data.get("source", ""),
                apply=data.get("apply", []), verb=run["verb"], args=[str(a) for a in run.get("args", [])],
                env={k: str(v) for k, v in run.get("env", {}).items()}, no_project=bool(run.get("no_project", False)),
                exp_rc=exp["rc"], exp_verdict=exp["verdict"], regex=list(exp.get("regex", [])),
                not_regex=list(exp.get("not_regex", [])), max_seconds=float(exp.get("max_seconds", 60)), dir=d,
                toml_path=tp))
    entries.sort(key=lambda e: e.id)
    return entries, errors


# ---- preparing the temp copy ---------------------------------------------------------------------------------------
def _ignore_sample(sample: Path):
    def ign(src, names):
        s = set(n for n in names if n in SAMPLE_EXCLUDE)
        if Path(src) == sample / "addons":
            s |= {n for n in names if n in ("harness", "gdUnit4")}
        return s
    return ign


def copy_fixture(entry: Entry, proj: Path, tmp_out: Path):
    if entry.fixture == "none":
        proj.mkdir(parents=True, exist_ok=True)
        return
    if entry.fixture == "@sample":
        sample = out.repo_root() / "sample"
        if not sample.is_dir():
            raise Broken("fixture @sample: sample/ does not exist yet")
        shutil.copytree(sample, proj, ignore=_ignore_sample(sample), symlinks=True)
        env = dict(os.environ, HARNESS_OUT=str(tmp_out))
        r = proc.run([str(out.repo_root() / "tools" / "harness" / "h"), "sync", "--no-gdunit", "--project", str(proj)],
                     timeout=120, env=env)
        if r.rc != 0:
            raise Broken(f"@sample sync failed (rc {r.rc}): {r.stdout.splitlines()[0] if r.stdout else ''}")
        return
    shutil.copytree(_fixtures_root() / entry.fixture, proj, ignore=shutil.ignore_patterns(*COPY_EXCLUDE), symlinks=True)


def apply_ops(entry: Entry, proj: Path):
    for i, op in enumerate(entry.apply):
        target = proj / op["path"]
        try:
            target.resolve().relative_to(proj.resolve())
        except ValueError:
            raise Broken(f"apply[{i}]: path escapes the project: {op['path']}") from None
        kind = op["op"]
        if kind == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            if "from" in op:
                src = entry.dir / op["from"]
                if not src.is_file():
                    raise Broken(f"apply[{i}]: missing source file {op['from']}")
                target.write_bytes(src.read_bytes())
            else:
                target.write_text(op["text"])
        elif kind == "replace":
            if not target.is_file():
                raise Broken(f"apply[{i}]: replace target not found: {op['path']}")
            text = target.read_text()
            want = op.get("count", 1)
            got = text.count(op["old"])
            if got != want:
                raise Broken(f"apply[{i}]: replace in {op['path']} matched {got} times, expected {want}")
            target.write_text(text.replace(op["old"], op["new"]))
        elif kind == "delete":
            if not target.exists():
                raise Broken(f"apply[{i}]: delete target not found: {op['path']}")
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()


def build_argv(entry: Entry, proj: Path) -> list:
    sub = {"{project}": str(proj), "{fault_dir}": str(entry.dir)}

    def fmt(a):
        for k, v in sub.items():
            a = a.replace(k, v)
        return a

    argv = [str(out.repo_root() / "tools" / "harness" / "h"), entry.verb]
    if not entry.no_project:
        argv += ["--project", str(proj)]
    return argv + [fmt(a) for a in entry.args]


# ---- judging ---------------------------------------------------------------------------------------------------------
def judge(entry: Entry, rc: int, stdout: str, seconds: float) -> tuple:
    """-> (result, explanation). result: CAUGHT|PASS|MISSED|SLOW|OVERFLOW|FALSEPOS (BROKEN is set by the caller)."""
    lines = stdout.splitlines()
    verdict = lines[0].split(" ", 1)[0] if lines else ""
    problems = []
    if rc != entry.exp_rc:
        problems.append(f"rc={rc}")
    if verdict != entry.exp_verdict:
        problems.append(f"verdict {verdict or 'none'}")
    for rx in entry.regex:
        if not re.search(rx, stdout, re.MULTILINE):
            problems.append(f"no match for /{rx}/")
    for rx in entry.not_regex:
        if re.search(rx, stdout, re.MULTILINE):
            problems.append(f"forbidden /{rx}/ matched")
    ok_name = "CAUGHT" if entry.kind == "FAULT" else "PASS"
    bad_name = "MISSED" if entry.kind == "FAULT" else "FALSEPOS"
    if len(lines) > 40:
        return ("OVERFLOW" if entry.kind == "FAULT" else "FALSEPOS"), f"{len(lines)} lines"
    if problems:
        return bad_name, "; ".join(problems)
    if seconds > entry.max_seconds:
        return ("SLOW" if entry.kind == "FAULT" else "FALSEPOS"), f"{seconds:.1f}s > {entry.max_seconds:g}s"
    return ok_name, ""
