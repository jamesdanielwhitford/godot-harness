"""h lsp: opt-in GDScript language server daemon per project (A3 spec 2.2)."""
import os
import time
from pathlib import Path

from .. import out

HELP = "per-project GDScript language server: start, stop, diag"
USAGE = """
h lsp start  [--project DIR]
h lsp status [--project DIR]
h lsp stop   [--project DIR | --all]
h lsp diag   FILE... [--project DIR] [--oneshot]"""


def _parser():
    p = out.common_parser("lsp")
    p.add_argument("action", choices=["start", "status", "stop", "diag"])
    p.add_argument("files", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--oneshot", action="store_true")
    return p


def _main(r, args, project):
    from ..lint import lsp_daemon
    if args.action == "stop" and args.all:
        n = lsp_daemon.stop_all()
        return r.finish(f"stopped {n} daemon{'s' if n != 1 else ''}")
    act = args.action
    if act == "status":
        state, st = lsp_daemon.status(project)
        r.stat("state", state)
        if state == "running":
            r.stat("pid", st["pid"])
            r.stat("port", st["port"])
            try:
                up = time.time() - _dt_epoch(st["started_at"])
            except (ValueError, KeyError):
                up = 0
            r.stat("uptime_s", max(int(up), 0))
        return r.finish(state)
    if act == "stop":
        was = lsp_daemon.stop(project)
        r.stat("state", "stopped")
        return r.finish("stopped" if was else "not running")
    if act == "start":
        st = lsp_daemon.start(r, project)
        if st is None:
            return r.finish("daemon failed to start")
        r.stat("pid", st["pid"])
        r.stat("port", st["port"])
        r.stat("state", "running")
        return r.finish("already running" if r.extra.get("lsp_already_running") else "started")
    return _diag(r, args, project)


def _dt_epoch(s: str) -> float:
    import calendar
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def _diag(r, args, project):
    from .. import lint as lint_mod
    from ..lint import lsp_daemon
    if not args.files:
        r.error(2, "usage: lsp diag needs at least one FILE")
    files = []
    for a in args.files:
        if a.startswith("res://"):
            p = project / a[len("res://"):]
        else:
            p = Path(a).expanduser()
            p = p if p.is_absolute() else Path.cwd() / p
        p = Path(os.path.normpath(p))
        try:
            p.relative_to(project)
        except ValueError:
            try:
                p = p.resolve()
                p.relative_to(project)
            except ValueError:
                r.error(2, f"usage: path outside project: {a}")
        if not p.is_file():
            r.error(2, f"usage: no such file: {a}")
        files.append(p)
    if not args.oneshot and lsp_daemon.running_state(project) is None:
        r.error(4, "lsp daemon not running (h lsp start)")
    t0 = time.monotonic()
    ok = lint_mod.lsp_diag(r, project, files, start=args.oneshot)
    if not ok:
        if any(f["rule"] == "lint.lsp-daemon" for f in r.findings):
            return r.finish("daemon failed to start")
        r.error(4, "lsp daemon not running (h lsp start)")
    e = sum(1 for f in r.findings if f["severity"] == "error")
    w = sum(1 for f in r.findings if f["severity"] == "warning")
    r.stat("files", f"{len(files)} .gd")
    if e or w:
        return r.finish(f"{e} error{'s' if e != 1 else ''}, {w} warning{'s' if w != 1 else ''} in {len(files)} files "
                        f"({time.monotonic() - t0:.2f}s)")
    return r.finish(f"0 findings in {len(files)} files ({time.monotonic() - t0:.2f}s)")


def run(argv):
    argv = list(argv)
    need_project = not ("stop" in argv and "--all" in argv)
    return out.invoke("lsp", argv, _parser(), _main, need_project=need_project)
