"""Black-box helpers for the `h` CLI tests (contract 2.12; REVIEW R-38, R-39, R-50, R-51). Owner: T1.

Public API: run_h, Result, copy_fixture, apply_fault, assert_contract, run_godot, GodotResult, write, scene_for_script.
Nothing here imports tools/harness; everything is subprocess + files.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import signal
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
H = REPO / "tools" / "harness" / "h"
FIXTURES = REPO / "tests" / "fixtures"
PROJECTS = FIXTURES / "projects"
SELFTEST = REPO / "selftest"
GODOT_VERSION = "4.7.stable.official.5b4e0cb0f"

# ---- grammar (contract 2.3, 2.7; R-38, R-50) ----------------------------------------------------------
RULE_ID = r"[a-z0-9][a-zA-Z0-9._-]*"
RE_RULE_ID = re.compile(rf"^{RULE_ID}$")
RE_VERDICT = re.compile(r"^(PASS|FAIL|WARN|ERROR) (\S+) (.{1,100})$")
RE_CHECK = re.compile(r"^(OK|FAIL|SKIP|WARN) +([^:]+): (.*)$")
RE_FINDING = re.compile(rf"^(?P<loc>-|\S.*?): \[(?P<rule>{RULE_ID})\] (?P<sev>error|warning|info): (?P<rest>.*)$")
RE_STAT = re.compile(r"^([a-z][a-z0-9_-]*): (.*)$")
RE_TRUNC = re.compile(r"^\.\.\. (\d+) more findings \((\d+) errors, (\d+) warnings\) in findings\.jsonl$")
RE_LOG = re.compile(r"^log: (.+/)$")
RE_RUN_ID = r"^\d{8}T\d{6}Z-%s-[0-9a-f]{4}$"
RC_FOR_VERDICT = {"PASS": {0}, "FAIL": {1}, "WARN": {5}, "ERROR": {2, 3, 4}}

HELPER_ENV_DROP = ("HARNESS_PROJECT", "HARNESS_OUT", "HARNESS_TIMEOUT_SCALE", "HARNESS_ROOT")


class HelperError(AssertionError):
    """A test-helper step failed (not the verb under test)."""


# ---- Result ----------------------------------------------------------------------------------------------
@dataclass
class Result:
    rc: int
    stdout: str
    stderr: str
    argv: list
    cwd: Path
    wall: float
    lines: list = field(default_factory=list)
    verdict: str | None = None
    verb: str | None = None
    reason: str | None = None
    stats: dict = field(default_factory=dict)        # key -> first value
    stat_items: list = field(default_factory=list)   # [(key, value)] in order
    checks: list = field(default_factory=list)       # [(status, name, detail)]
    findings: list = field(default_factory=list)     # shown finding lines, parsed
    trunc: tuple | None = None                       # (K, e, w)
    log_dir: Path | None = None
    kinds: list = field(default_factory=list)        # classification of lines[1:]
    extra: dict = field(default_factory=dict)

    # -- accessors
    def __str__(self) -> str:
        return f"rc={self.rc} wall={self.wall:.1f}s argv={self.argv}\n{self.stdout}{self.stderr}"

    def stat_all(self, key: str) -> list:
        return [v for k, v in self.stat_items if k == key]

    def check(self, name: str):
        for c in self.checks:
            if c[1] == name:
                return c
        return None

    def run_json(self) -> dict:
        return json.loads((self.require_log_dir() / "run.json").read_text())

    def findings_jsonl(self) -> list:
        p = self.require_log_dir() / "findings.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

    def invocations(self) -> list:
        return self.run_json()["invocations"]

    def require_log_dir(self) -> Path:
        if self.log_dir is None:
            raise AssertionError(f"no log: line in output\n{self}")
        return self.log_dir

    def artifact(self, rel: str) -> Path:
        return self.require_log_dir() / "artifacts" / rel

    def all_findings(self) -> list:
        """findings.jsonl (authoritative, uncapped) as dicts with keys path,line,rule,severity,message,hint."""
        return self.findings_jsonl()

    def has_finding(self, rule: str | None = None, path: str | None = None, line: int | None = None,
                    severity: str | None = None, msg_re: str | None = None, shown_only: bool = False) -> bool:
        pool = self.findings if shown_only else self.findings_jsonl()
        for f in pool:
            if rule is not None and f["rule"] != rule:
                continue
            if path is not None and f["path"] != path:
                continue
            if line is not None and f["line"] != line:
                continue
            sev = f.get("severity", f.get("sev"))
            if severity is not None and sev != severity:
                continue
            if msg_re is not None and not re.search(msg_re, f["message"]):
                continue
            return True
        return False

    def matches(self, regex: str) -> bool:
        return re.search(regex, self.stdout, re.MULTILINE) is not None


def _split_loc(loc: str):
    if loc == "-":
        return None, None
    m = re.match(r"^(.+?):(\d+)$", loc)
    if m:
        return m.group(1), int(m.group(2))
    return loc, None


def _parse_finding(m) -> dict:
    rest = m.group("rest")
    count = 1
    hint = None
    for _ in range(2):
        mx = re.search(r" \(x(\d+)\)$", rest)
        if mx:
            count = int(mx.group(1))
            rest = rest[: mx.start()]
        mh = re.search(r" \(hint: (.*)\)$", rest)
        if mh and hint is None:
            hint = mh.group(1)
            rest = rest[: mh.start()]
    path, line = _split_loc(m.group("loc"))
    return {"loc": m.group("loc"), "path": path, "line": line, "rule": m.group("rule"),
            "severity": m.group("sev"), "message": rest, "hint": hint, "count": count}


def parse_stdout(stdout: str) -> dict:
    lines = stdout.splitlines()
    out: dict[str, Any] = {"lines": lines, "verdict": None, "verb": None, "reason": None, "stats": {},
                           "stat_items": [], "checks": [], "findings": [], "trunc": None,
                           "log_dir": None, "kinds": []}
    if not lines:
        return out
    m = RE_VERDICT.match(lines[0])
    if m:
        out["verdict"], out["verb"], out["reason"] = m.group(1), m.group(2), m.group(3)
    for ln in lines[1:]:
        mt = RE_TRUNC.match(ln)
        if mt:
            out["trunc"] = (int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
            out["kinds"].append("trunc")
            continue
        ml = RE_LOG.match(ln)
        if ml:
            out["log_dir"] = ml.group(1)
            out["kinds"].append("log")
            continue
        mc = RE_CHECK.match(ln)
        if mc:
            out["checks"].append((mc.group(1), mc.group(2).strip(), mc.group(3)))
            out["kinds"].append("check")
            continue
        mf = RE_FINDING.match(ln)
        if mf:
            out["findings"].append(_parse_finding(mf))
            out["kinds"].append("finding")
            continue
        ms = RE_STAT.match(ln)
        if ms and not ms.group(2).startswith("["):
            out["stat_items"].append((ms.group(1), ms.group(2)))
            out["stats"].setdefault(ms.group(1), ms.group(2))
            out["kinds"].append("stat")
            continue
        out["kinds"].append("other")
    return out


def _env(env: dict | None) -> dict:
    e = dict(os.environ)
    for k in HELPER_ENV_DROP:
        e.pop(k, None)
    for k, v in (env or {}).items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = str(v)
    return e


def run_h(*args, cwd=None, env=None, timeout=120) -> Result:
    """Run tools/harness/h with args. Returns a parsed Result. env values of None delete the variable."""
    argv = [str(H), *[str(a) for a in args]]
    cwd_p = Path(cwd) if cwd else Path.cwd()
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=str(cwd_p), env=_env(env), capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as ex:
        raise AssertionError(f"`h {' '.join(map(str, args))}` did not finish within {timeout}s "
                             f"(stdout so far: {(ex.stdout or b'')[:500]!r})") from None
    wall = time.monotonic() - t0
    parsed = parse_stdout(p.stdout)
    log_dir = None
    if parsed["log_dir"]:
        ld = Path(parsed["log_dir"])
        log_dir = ld if ld.is_absolute() else (cwd_p / ld)
    return Result(rc=p.returncode, stdout=p.stdout, stderr=p.stderr, argv=argv, cwd=cwd_p, wall=wall,
                  lines=parsed["lines"], verdict=parsed["verdict"], verb=parsed["verb"],
                  reason=parsed["reason"], stats=parsed["stats"], stat_items=parsed["stat_items"],
                  checks=parsed["checks"], findings=parsed["findings"], trunc=parsed["trunc"],
                  log_dir=log_dir, kinds=parsed["kinds"])


# ---- fixtures (contract 2.10, 2.11; R-10, R-51) ------------------------------------------------------------
_COPY_EXCLUDE = (".godot", ".harness")
_SAMPLE_EXCLUDE = (".godot", ".harness")


def fixture_path(name: str) -> Path:
    for base in (PROJECTS, FIXTURES):
        p = base / name
        if p.is_dir():
            return p
    raise HelperError(f"unknown fixture '{name}' (looked in {PROJECTS} and {FIXTURES})")


def _ignore_sample(src, names):
    src_p = Path(src)
    ign = set(n for n in names if n in _SAMPLE_EXCLUDE)
    sample = REPO / "sample"
    if src_p == sample / "addons":
        ign |= {n for n in names if n in ("harness", "gdUnit4")}
    return ign


def copy_fixture(name: str, dest, *, sync_sample: bool = True) -> Path:
    """Copy fixture `name` ("clean_min", "scene_cases", ..., "none", or "@sample") to `dest`; return dest.

    Excludes .godot/ and .harness/. "@sample" also excludes addons/harness/ and addons/gdUnit4/ and then runs
    `h sync --no-gdunit --project <copy>` (REVIEW R-51); a non-zero rc is a helper error.
    """
    dest = Path(dest)
    if name == "none":
        dest.mkdir(parents=True, exist_ok=True)
        return dest
    if name == "@sample":
        src = REPO / "sample"
        if not src.is_dir():
            raise HelperError("@sample requested but sample/ does not exist yet (A9)")
        shutil.copytree(src, dest, ignore=_ignore_sample, dirs_exist_ok=True, symlinks=True)
        if sync_sample:
            out = dest.parent / f".sync-out-{dest.name}"
            r = run_h("sync", "--no-gdunit", "--project", dest, env={"HARNESS_OUT": out})
            if r.rc != 0:
                raise HelperError(f"@sample copy: `h sync --no-gdunit` rc={r.rc}\n{r.stdout}")
        return dest
    src = fixture_path(name)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*_COPY_EXCLUDE), dirs_exist_ok=True, symlinks=True)
    return dest


def write(project, rel: str, text: str) -> Path:
    p = Path(project) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def scene_for_script(project, scene_rel: str, script_res: str, root_type: str = "Node") -> Path:
    """Write a minimal hand-written scene (r1_4 section 3 form): one root node with the script attached."""
    text = (
        "[gd_scene format=3]\n\n"
        f'[ext_resource type="Script" path="{script_res}" id="1_a"]\n\n'
        f'[node name="Root" type="{root_type}"]\n'
        'script = ExtResource("1_a")\n'
    )
    return write(project, scene_rel, text)


def fault_dir(fault_id: str) -> Path:
    for sub in ("faults", "clean"):
        p = SELFTEST / sub / fault_id
        if p.is_dir():
            return p
    raise HelperError(f"no such fault/clean entry: {fault_id}")


def load_fault(fault_id: str) -> dict:
    return tomllib.loads((fault_dir(fault_id) / "fault.toml").read_text())


def apply_fault(fault_id: str, project, skip_ops_with_path: tuple = ()) -> dict:
    """Apply the `apply` ops of selftest entry `fault_id` to `project` (a temp copy). Returns the parsed toml."""
    fd = fault_dir(fault_id)
    spec = tomllib.loads((fd / "fault.toml").read_text())
    project = Path(project)
    for op in spec.get("apply", []):
        target = project / op["path"]
        kind = op["op"]
        if kind == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            if "from" in op:
                target.write_bytes((fd / op["from"]).read_bytes())
            else:
                target.write_text(op["text"])
        elif kind == "replace":
            txt = target.read_text()
            n = op.get("count", 1)
            if txt.count(op["old"]) != n:
                raise HelperError(f"{fault_id}: replace in {op['path']} matched {txt.count(op['old'])}x, want {n}")
            target.write_text(txt.replace(op["old"], op["new"]))
        elif kind == "delete":
            target.unlink()
        else:
            raise HelperError(f"{fault_id}: unknown op {kind}")
    return spec


def tree_hash(root) -> dict:
    """{relpath: sha256} of every file under root (for byte-identical checks)."""
    import hashlib
    out = {}
    root = Path(root)
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def live_processes_mentioning(needle: str) -> list:
    """Pids (other than ours) whose cmdline contains `needle` (no surviving Godot after a hang)."""
    hits = []
    me = os.getpid()
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            stat = (d / "stat").read_text()
        except OSError:
            continue
        if needle in cmd and "pytest" not in cmd:
            # skip zombies
            if re.search(r"\) Z ", stat):
                continue
            hits.append((int(d.name), cmd[:200]))
    return hits


# ---- assert_contract (contract 2.3-2.5, 2.12) --------------------------------------------------------------
RUN_JSON_REQUIRED = ["schema", "run_id", "verb", "argv", "cwd", "project", "started_at", "duration_s", "rc",
                     "verdict", "reason", "counts", "findings_total", "truncated", "invocations"]
INVOCATION_REQUIRED = ["n", "kind", "argv", "timeout_s", "rc", "timed_out", "duration_s", "log", "scan_verdict"]

RUN_JSON_SCHEMA = {
    "type": "object", "required": RUN_JSON_REQUIRED,
    "properties": {
        "schema": {"const": "harness.run/1"}, "run_id": {"type": "string"}, "verb": {"type": "string"},
        "cwd": {"type": "string"}, "argv": {"type": "array", "items": {"type": "string"}},
        "project": {"type": ["string", "null"]}, "duration_s": {"type": "number"},
        "started_at": {"type": "string"}, "rc": {"enum": [0, 1, 2, 3, 4, 5]}, "reason": {"type": "string"},
        "verdict": {"enum": ["PASS", "FAIL", "WARN", "ERROR"]}, "findings_total": {"type": "integer"},
        "truncated": {"type": "boolean"},
        "counts": {"type": "object", "required": ["error", "warning", "info"],
                   "properties": {k: {"type": "integer"} for k in ("error", "warning", "info")}},
        "godot": {"type": ["object", "null"]},
        "invocations": {"type": "array", "items": {
            "type": "object", "required": INVOCATION_REQUIRED,
            "properties": {"n": {"type": "integer"}, "kind": {"type": "string"},
                           "argv": {"type": "array", "items": {"type": "string"}},
                           "timeout_s": {"type": "number"}, "rc": {"type": "integer"},
                           "timed_out": {"type": "boolean"}, "duration_s": {"type": "number"},
                           "log": {"type": "string"}, "scan_verdict": {"enum": ["PASS", "WARN", "FAIL"]},
                           "runner_rc": {"type": ["integer", "null"]}, "retried": {"type": "boolean"},
                           "display_failed": {"type": "boolean"}}}},
        "extra": {"type": "object"}}}

_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
          "boolean": bool, "null": type(None)}


def _ok_type(v, t) -> bool:
    ts = t if isinstance(t, list) else [t]
    for x in ts:
        py = _TYPES[x]
        if x in ("integer", "number") and isinstance(v, bool):
            continue
        if isinstance(v, py):
            return True
    return False


def validate_schema(v, schema: dict, path: str = "$") -> list:
    """Tiny stdlib validator for the subset of JSON Schema used by RUN_JSON_SCHEMA. Returns error strings."""
    errs = []
    if "const" in schema and v != schema["const"]:
        errs.append(f"{path}: want const {schema['const']!r}, got {v!r}")
    if "enum" in schema and v not in schema["enum"]:
        errs.append(f"{path}: {v!r} not in {schema['enum']}")
    if "type" in schema and not _ok_type(v, schema["type"]):
        errs.append(f"{path}: wrong type {type(v).__name__}, want {schema['type']}")
        return errs
    if isinstance(v, dict):
        for k in schema.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing required key '{k}'")
        for k, sub in schema.get("properties", {}).items():
            if k in v:
                errs += validate_schema(v[k], sub, f"{path}.{k}")
    if isinstance(v, list) and "items" in schema:
        for i, it in enumerate(v):
            errs += validate_schema(it, schema["items"], f"{path}[{i}]")
    return errs


def validate_run_json(run: dict) -> list:
    errs = validate_schema(run, RUN_JSON_SCHEMA)
    try:
        import jsonschema  # optional (contract C9); the stdlib validator above is the floor
        try:
            jsonschema.validate(run, RUN_JSON_SCHEMA)
        except jsonschema.ValidationError as ex:  # pragma: no cover
            errs.append(f"jsonschema: {ex.message}")
    except ImportError:
        pass
    try:
        _dt.datetime.fromisoformat(str(run.get("started_at", "")).replace("Z", "+00:00"))
    except ValueError:
        errs.append(f"started_at is not an ISO date-time: {run.get('started_at')!r}")
    return errs


def assert_contract(r: Result, *, nodir: bool = False, help_output: bool = False, check_latest: bool = True) -> Result:
    """Assert the stdout grammar and run-dir invariants of contract 2.3-2.5.

    nodir=True: the three outputs without a run dir (help, bare `h`, unknown verb): only line grammar.
    help_output=True: exempt from the 40-line limit.
    """
    def fail(msg):
        raise AssertionError(f"contract violation: {msg}\n--- result ---\n{r}")

    if r.stderr.strip():
        fail("a verb must not print to stderr")
    if not r.lines:
        fail("empty stdout")
    for i, ln in enumerate(r.lines):
        if not help_output and len(ln) > 240:
            fail(f"line {i + 1} longer than 240 chars")
    if not help_output and len(r.lines) > 40:
        fail(f"{len(r.lines)} lines > 40")
    if r.verdict is None:
        if nodir and help_output:
            return r
        fail("line 1 is not `<PASS|FAIL|WARN|ERROR> <verb> <reason>`")
    if r.rc not in RC_FOR_VERDICT[r.verdict]:
        fail(f"rc {r.rc} does not match verdict {r.verdict}")
    if nodir:
        return r

    # order: stats, checks, findings, truncation, log (contract 2.3)
    order = {"stat": 1, "check": 2, "finding": 3, "trunc": 4, "log": 5, "other": 9}
    seq = [order[k] for k in r.kinds]
    if "other" in r.kinds:
        bad = [r.lines[i + 1] for i, k in enumerate(r.kinds) if k == "other"]
        fail(f"line(s) match no grammar form: {bad[:3]}")
    if seq != sorted(seq):
        fail("lines are not in the order stats, checks, findings, truncation, log")
    if r.kinds.count("log") != 1 or r.kinds[-1] != "log":
        fail("exactly one `log: <dir>/` line, and it must be last")
    stat_keys = [k for k, _ in r.stat_items]
    if "project" in stat_keys and stat_keys[0] != "project":
        fail("`project:` must be the first stat line")
    for f in r.findings:
        if not RE_RULE_ID.match(f["rule"]):
            fail(f"rule id {f['rule']!r} breaks the R-38 pattern")
        loc = f["loc"]
        if loc != "-" and not (loc.startswith("res://") or loc.startswith("/") or loc.startswith(".") or "/" in loc or "." in loc):
            fail(f"odd finding location {loc!r}")
    rank = {"error": 0, "warning": 1, "info": 2}
    sev_seq = [rank[f["severity"]] for f in r.findings]
    if sev_seq != sorted(sev_seq):
        fail("findings not ordered errors, warnings, info")

    # invariants
    n_err = sum(f["count"] for f in r.findings if f["severity"] == "error")
    n_warn = sum(f["count"] for f in r.findings if f["severity"] == "warning")
    if r.trunc:
        n_err += r.trunc[1]
        n_warn += r.trunc[2]
    fail_checks = [c for c in r.checks if c[0] == "FAIL"]
    warn_checks = [c for c in r.checks if c[0] == "WARN"]
    strict = "--strict" in [str(a) for a in r.argv]
    if r.verdict == "FAIL" and not (n_err or fail_checks or (strict and (n_warn or warn_checks))):
        fail("FAIL needs at least one error finding or FAIL check line")
    if r.verdict == "WARN":
        if not (n_warn or warn_checks):
            fail("WARN needs at least one warning finding or WARN check line")
        if n_err:
            fail("WARN must not have error findings")
    if r.verdict == "PASS" and (n_err or n_warn):
        fail("PASS must not have error/warning findings")

    # run dir
    ld = r.log_dir
    if ld is None or not ld.is_dir():
        fail(f"log dir {ld} does not exist")
    run = json.loads((ld / "run.json").read_text()) if (ld / "run.json").exists() else fail("run.json missing")
    errs = validate_run_json(run)
    if errs:
        fail("run.json schema: " + "; ".join(errs[:5]))
    if run["rc"] != r.rc or run["verdict"] != r.verdict or run["verb"] != r.verb or run["reason"] != r.reason:
        fail("run.json rc/verdict/verb/reason differ from stdout")
    if not re.match(RE_RUN_ID % re.escape(run["verb"]), run["run_id"]) or ld.name != run["run_id"]:
        fail(f"run id {run['run_id']!r} / dir {ld.name!r} breaks the run-id pattern")
    summ = ld / "summary.txt"
    if not summ.exists() or summ.read_text().rstrip("\n") != r.stdout.rstrip("\n"):
        fail("summary.txt differs from stdout")
    fj = ld / "findings.jsonl"
    rows = [json.loads(x) for x in fj.read_text().splitlines() if x.strip()] if fj.exists() else fail("findings.jsonl missing")
    if len(rows) != run["findings_total"]:
        fail(f"findings.jsonl has {len(rows)} rows, run.json says {run['findings_total']}")
    for row in rows:
        for k in ("path", "line", "rule", "severity", "message", "hint", "source", "invocation"):
            if k not in row:
                fail(f"findings.jsonl row lacks '{k}': {row}")
        if not RE_RULE_ID.match(row["rule"]) or row["severity"] not in rank:
            fail(f"bad findings.jsonl row {row}")
    for sev in ("error", "warning", "info"):
        if run["counts"][sev] != sum(1 for x in rows if x["severity"] == sev):
            fail(f"run.json counts.{sev} differs from findings.jsonl")
    if bool(r.trunc) != bool(run["truncated"]):
        fail("truncation line and run.json `truncated` disagree")
    if not r.trunc:
        if n_err != run["counts"]["error"] or n_warn != run["counts"]["warning"]:
            fail(f"shown findings ({n_err} errors, {n_warn} warnings) differ from run.json counts {run['counts']}")
    else:
        if n_err != run["counts"]["error"] or n_warn != run["counts"]["warning"]:
            fail(f"shown+truncated ({n_err}/{n_warn}) differ from run.json counts {run['counts']}")
    tb = ld / "traceback.txt"
    if (r.rc == 3) != tb.exists():
        fail("traceback.txt must exist exactly when rc == 3")
    if check_latest:
        latest = ld.parent / "latest"
        if not latest.is_symlink() or latest.resolve() != ld.resolve():
            fail(f"{latest} is not a symlink to this run dir")
    if not (ld.parent.parent / ".gdignore").exists():
        fail(f"{ld.parent.parent}/.gdignore missing")
    return r


# ---- direct Godot call for runner-protocol tests only (R-39) ----------------------------------------------
@dataclass
class GodotResult:
    rc: int
    text: str
    records: list
    timed_out: bool
    argv: list


def godot_binary(project=None) -> Path:
    """Resolve the binary as contract 2.8.1: HARNESS_GODOT > harness.toml `godot` > tools/bin/godot."""
    env = os.environ.get("HARNESS_GODOT")
    if env:
        return Path(env)
    if project is not None:
        toml = Path(project) / "harness.toml"
        if toml.exists():
            g = tomllib.loads(toml.read_text()).get("harness", {}).get("godot", "")
            if g:
                return (Path(project) / g)
    return REPO / "tools" / "bin" / "godot"


def run_godot(args, project, timeout: int = 60) -> GodotResult:
    """Run Godot headless on `project` with extra `args` (e.g. ["-s", runner, "--", "--mode", "scripts"]).

    Only for runner-protocol tests (A1 AC-01.27). stdout+stderr are combined; `@@H <json>` lines are parsed
    into `records`. The process group is killed on timeout.
    """
    argv = [str(godot_binary(project)), "--headless", "--path", str(project), *[str(a) for a in args]]
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         cwd=str(project), text=True, start_new_session=True)
    timed_out = False
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = p.communicate()
    records = []
    for ln in out.splitlines():
        if ln.startswith("@@H "):
            try:
                records.append(json.loads(ln[4:]))
            except json.JSONDecodeError:
                records.append({"t": "bad-json", "raw": ln})
    return GodotResult(rc=p.returncode, text=out, records=records, timed_out=timed_out, argv=argv)


def verbs_in_tree() -> list:
    """CLI verb names derived from the file names under tools/harness/harness/verbs (contract 2.1).

    Reads the directory listing only (no source)."""
    d = REPO / "tools" / "harness" / "harness" / "verbs"
    names = []
    if d.is_dir():
        for p in sorted(d.glob("*.py")):
            stem = p.stem
            if stem.startswith("_"):
                continue
            if stem.endswith("_"):
                stem = stem[:-1]
            names.append(stem.replace("_", "-"))
    return names


A1_VERBS = ["doctor", "sync", "import", "api", "check", "selftest"]


def verbs_under_test() -> list:
    """The six A1-owned verbs plus whatever else has been built."""
    return sorted(set(A1_VERBS) | set(verbs_in_tree()))
