"""Run directory, stdout rendering and common flags (contract 2.3-2.5, 2.9). Stdlib only, import-safe.

Typical verb:

    def run(argv):
        p = out.common_parser("check")
        p.add_argument("--no-lint", action="store_true")
        return out.invoke("check", argv, p, _main)

    def _main(r, args, project):        # r: out.Run
        ...
        return r.finish("0 findings in 3 files (1.2s)")

`out.invoke` resolves the project, validates env, loads harness.toml and turns usage/config problems into ERROR
runs. Lower level API (what the contract lists): `Run`, `render`, `common_parser`.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import secrets
import shutil
import sys
import time
import traceback
from pathlib import Path

MAX_LINE = 240
MAX_HINT = 100  # stdout hints only; findings.jsonl keeps them in full
KEEP_RUNS = 50
MIN_AGE_S = 600
SEV_RANK = {"error": 0, "warning": 1, "info": 2}
_RUN_DIR_RE = re.compile(r"^\d{8}T\d{6}Z-[a-z0-9-]+-[0-9a-f]{4}$")


class UsageError(Exception):
    """Bad command line (rc 2)."""


class Stop(BaseException):
    """Raised by Run.error(): stop the verb with an ERROR verdict (rc 2, 3 or 4)."""

    def __init__(self, rc: int, reason: str):
        super().__init__(reason)
        self.rc = rc
        self.reason = reason


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse would print to stderr and exit
        raise UsageError(message)

    def exit(self, status=0, message=None):
        raise UsageError(message or "exit")


def common_parser(verb: str | None = None) -> argparse.ArgumentParser:
    p = _Parser(prog=f"h {verb}" if verb else "h", add_help=False, allow_abbrev=False)
    p.add_argument("--project", default=None, metavar="DIR")
    p.add_argument("--strict", action="store_true")
    return p


# ---- rendering ---------------------------------------------------------------------------------------------
def _cut(s: str, n: int = MAX_LINE) -> str:
    s = s.replace("\r", " ").replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def _loc(f: dict) -> str:
    p, ln = f.get("path"), f.get("line")
    if not p:
        return "-"
    return f"{p}:{ln}" if ln else str(p)


def _sort_key(f: dict):
    return (SEV_RANK.get(f.get("severity"), 3), f.get("path") or "", f.get("line") or 0, f.get("rule") or "")


def finding_line(f: dict, count: int = 1) -> str:
    s = f"{_loc(f)}: [{f['rule']}] {f['severity']}: {str(f['message']).strip()}"
    if f.get("hint"):
        hint = str(f["hint"]).replace("\r", "").replace("\n", " / ")
        if len(hint) > MAX_HINT:
            hint = hint[: MAX_HINT - 3] + "..."
        s += f" (hint: {hint})"
    if count > 1:
        s += f" (x{count})"
    return _cut(s)


def render(verb, verdict, reason, stats, checks, findings, log_dir, max_lines=40) -> list[str]:
    """Contract 2.3. stats: [(key, value)]; checks: [(status, name, detail)]; findings: dicts."""
    reason = (reason or "done").replace("\n", " ")
    if len(reason) > 100:
        reason = reason[:97] + "..."
    head = [f"{verdict} {verb} {reason}"]
    head += [_cut(f"{k}: {v}") for k, v in stats]
    head += [_cut(f"{st:<4} {name}: {detail if detail != '' else '-'}") for st, name, detail in checks]
    tail = [f"log: {log_dir}"]
    budget = max_lines - len(tail)
    if findings:
        budget -= 2  # always leave room for one finding and the truncation line
    if len(head) > budget:
        head = head[: max(budget, 1)]
    room = max_lines - len(tail) - len(head)

    groups: dict = {}
    order = []
    for f in sorted(findings, key=_sort_key):
        key = (f["severity"], _loc(f), f["rule"], str(f["message"]), f.get("hint"))
        if key in groups:
            groups[key][1] += 1
        else:
            groups[key] = [f, 1]
            order.append(key)
    main = [groups[k] for k in order if groups[k][0]["severity"] != "info"]
    infos = [groups[k] for k in order if groups[k][0]["severity"] == "info"]
    trunc = []
    if len(main) <= room:
        shown = main + infos[: room - len(main)]
    else:
        keep = max(room - 1, 0)
        shown = main[:keep]
        hidden = main[keep:]
        e = sum(c for f, c in hidden if f["severity"] == "error")
        w = sum(c for f, c in hidden if f["severity"] == "warning")
        trunc = [f"... {e + w} more findings ({e} errors, {w} warnings) in findings.jsonl"]
    return head + [finding_line(f, c) for f, c in shown] + trunc + tail


# ---- the run -----------------------------------------------------------------------------------------------
def repo_root() -> Path:
    env = os.environ.get("HARNESS_REPO")
    return Path(env) if env else Path(__file__).resolve().parents[3]


def _peek_project(argv) -> Path | None:
    """Best-effort project dir (no errors) so the run dir lands in the right place."""
    cand = None
    for i, a in enumerate(argv):
        if a == "--":
            break
        if a == "--project" and i + 1 < len(argv):
            cand = argv[i + 1]
        elif a.startswith("--project="):
            cand = a.split("=", 1)[1]
    if cand is None:
        cand = os.environ.get("HARNESS_PROJECT") or None
    if cand:
        p = Path(cand).expanduser().resolve()
        return p if (p / "project.godot").is_file() else None
    p = Path.cwd().resolve()
    for d in [p, *p.parents]:
        if (d / "project.godot").is_file():
            return d
    return None


class Run:
    """with out.Run(verb, argv, project=None) as r: ...   (contract 2.9)"""

    def __init__(self, verb: str, argv, project=None):
        self.verb = verb
        self.argv = [str(a) for a in argv]
        self.project: Path | None = Path(project) if project else None
        self.started = _dt.datetime.now(_dt.timezone.utc)
        self._t0 = time.monotonic()
        self.run_id = f"{self.started.strftime('%Y%m%dT%H%M%SZ')}-{verb}-{secrets.token_hex(2)}"
        self.findings: list[dict] = []
        self.stats: list[tuple] = []
        self.checks: list[tuple] = []
        self.invocations: list[dict] = []
        self.extra: dict = {}
        self.godot_info: dict | None = None
        self.config: dict | None = None
        self.strict = "--strict" in (self.argv[: self.argv.index("--")] if "--" in self.argv else self.argv)
        self.rc: int | None = None
        self._dir: Path | None = None
        self._finished = False

    # -- run dir
    def out_root(self) -> Path:
        env = os.environ.get("HARNESS_OUT")
        if env:
            return Path(env).expanduser().absolute()
        if self.project is not None:
            return self.project / ".harness" / "out"
        return repo_root() / ".harness" / "out"

    @property
    def dir(self) -> Path:
        if self._dir is None:
            root = self.out_root()
            root.mkdir(parents=True, exist_ok=True)
            try:
                (root.parent / ".gdignore").touch()
            except OSError:
                pass
            self._prune(root)
            d = root / self.run_id
            d.mkdir()
            self._dir = d
        return self._dir

    @property
    def artifacts_dir(self) -> Path:
        d = self.dir / "artifacts"
        d.mkdir(exist_ok=True)
        return d

    @property
    def godot_dir(self) -> Path:
        d = self.dir / "godot"
        d.mkdir(exist_ok=True)
        return d

    def _prune(self, root: Path):
        try:
            dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and _RUN_DIR_RE.match(p.name))
        except OSError:
            return
        now = time.time()
        for p in dirs[: max(len(dirs) - (KEEP_RUNS - 1), 0)]:
            try:
                if now - p.stat().st_mtime >= MIN_AGE_S:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass

    # -- collecting
    def finding(self, path, line, rule, severity, message, hint=None, source="verb", invocation=None):
        self.findings.append({"path": path, "line": line, "rule": rule, "severity": severity,
                              "message": str(message), "hint": hint, "source": source, "invocation": invocation})

    def add_findings(self, findings):
        for f in findings:
            self.findings.append({"path": f.get("path"), "line": f.get("line"), "rule": f["rule"],
                                  "severity": f["severity"], "message": str(f["message"]), "hint": f.get("hint"),
                                  "source": f.get("source", "verb"), "invocation": f.get("invocation")})

    def stat(self, key: str, value):
        self.stats.append((key, str(value).replace("\n", " ")))

    def check(self, status: str, name: str, detail: str = ""):
        assert status in ("OK", "FAIL", "SKIP", "WARN"), status
        self.checks.append((status, name.replace(":", " ").strip(), str(detail).replace("\n", " ")))

    def error(self, rc: int, reason: str):
        raise Stop(rc, reason)

    def record_invocation(self, entry: dict):
        self.invocations.append(entry)

    # -- finishing
    def _verdict(self):
        errs = any(f["severity"] == "error" for f in self.findings) or any(c[0] == "FAIL" for c in self.checks)
        warns = any(f["severity"] == "warning" for f in self.findings) or any(c[0] == "WARN" for c in self.checks)
        if errs:
            return "FAIL", 1
        if warns:
            return ("FAIL", 1) if self.strict else ("WARN", 5)
        return "PASS", 0

    def finish(self, reason: str) -> int:
        verdict, rc = self._verdict()
        return self._emit(verdict, rc, reason)

    def finish_error(self, rc: int, reason: str, tb: str | None = None) -> int:
        if rc == 3:
            (self.dir / "traceback.txt").write_text(tb or f"harness failure (no exception): {reason}\n")
        return self._emit("ERROR", rc, reason)

    def _display_dir(self) -> str:
        d = self.dir.absolute()
        try:
            rel = os.path.relpath(d, Path.cwd())
            if not rel.startswith(".."):
                return rel.rstrip("/") + "/"
        except ValueError:
            pass
        return str(d).rstrip("/") + "/"

    def _emit(self, verdict: str, rc: int, reason: str) -> int:
        if self._finished:
            return self.rc if self.rc is not None else rc
        self._finished = True
        self.rc = rc
        reason = (reason or "done").replace("\n", " ")
        if len(reason) > 100:
            reason = reason[:97] + "..."
        d = self.dir
        lines = render(self.verb, verdict, reason, self.stats, self.checks, self.findings, self._display_dir())
        truncated = any(ln.startswith("... ") and " more findings (" in ln for ln in lines)
        rows = sorted(self.findings, key=_sort_key)
        counts = {s: sum(1 for f in rows if f["severity"] == s) for s in ("error", "warning", "info")}
        with open(d / "findings.jsonl", "w") as fh:
            for f in rows:
                fh.write(json.dumps({k: f.get(k) for k in ("path", "line", "rule", "severity", "message", "hint",
                                                             "source", "invocation")}) + "\n")
        run = {"schema": "harness.run/1", "run_id": self.run_id, "verb": self.verb, "argv": self.argv,
               "cwd": str(Path.cwd()), "project": str(self.project) if self.project else None,
               "started_at": self.started.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "duration_s": round(time.monotonic() - self._t0, 3), "rc": rc, "verdict": verdict, "reason": reason,
               "counts": counts, "findings_total": len(rows), "truncated": truncated, "godot": self.godot_info,
               "invocations": self.invocations, "extra": self.extra}
        (d / "run.json").write_text(json.dumps(run, indent=1, default=str) + "\n")
        text = "\n".join(lines) + "\n"
        (d / "summary.txt").write_text(text)
        self._update_latest(d)
        sys.stdout.write(text)
        sys.stdout.flush()
        return rc

    def _update_latest(self, d: Path):
        link = d.parent / "latest"
        tmp = d.parent / f".latest-{secrets.token_hex(3)}"
        try:
            os.symlink(d.name, tmp)
            os.replace(tmp, link)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass

    # -- context manager
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            if not self._finished:
                self.finish_error(3, "internal: verb returned without finish()")
                raise SystemExit(3)
            return False
        if issubclass(et, Stop):
            raise SystemExit(self.finish_error(ev.rc, ev.reason))
        if issubclass(et, (SystemExit, KeyboardInterrupt, GeneratorExit)):
            return False
        text = "".join(traceback.format_exception(et, ev, tb))
        msg = f"internal: {et.__name__}: {ev}".replace("\n", " ")
        if self._finished:
            sys.stderr.write(text)
            raise SystemExit(3)
        rc = self.finish_error(3, msg, tb=text)
        raise SystemExit(rc)


# ---- the standard verb wrapper ---------------------------------------------------------------------------------
def timeout_scale() -> float:
    raw = os.environ.get("HARNESS_TIMEOUT_SCALE")
    if raw is None or raw == "":
        return 1.0
    try:
        v = float(raw)
    except ValueError:
        raise UsageError(f"HARNESS_TIMEOUT_SCALE must be a number, got {raw!r}") from None
    if not 0.1 <= v <= 10:
        raise UsageError(f"HARNESS_TIMEOUT_SCALE must be within 0.1-10, got {raw}")
    return v


def invoke(verb: str, argv, parser, main, need_project: bool = True, soft_project: bool = False):
    """Run `main(r, args, project)` inside a Run with usage/project/config handling. Returns the rc."""
    argv = list(argv)
    try:
        with Run(verb, argv, _peek_project(argv)) as r:
            try:
                args = parser.parse_args(argv)
            except UsageError as e:
                r.error(2, f"usage: {e}")
            try:
                timeout_scale()
            except UsageError as e:
                r.error(2, f"usage: {e}")
            if getattr(args, "strict", False):
                r.strict = True
            project = None
            from . import config as config_mod
            from . import project as project_mod
            explicit = getattr(args, "project", None)
            if need_project or explicit or soft_project:
                try:
                    project = project_mod.resolve(explicit)
                except project_mod.ProjectError as e:
                    if need_project or explicit:
                        r.error(2, str(e))
            if project is not None:
                r.project = project
                r.stat("project", project)
                try:
                    r.config = config_mod.load(project)
                except config_mod.ConfigError as e:
                    for m in e.messages:
                        r.finding("res://harness.toml", None, "harness.config", "error", m)
                    r.error(2, f"harness.toml: {e.messages[0]}"[:100])
            rc = main(r, args, project)
            if rc is None:
                rc = r.rc if r.rc is not None else 0
            return rc
    except SystemExit as e:
        return int(e.code or 0)
