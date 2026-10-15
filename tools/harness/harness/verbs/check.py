"""h check: parse + load-check scripts and scenes in one batch per phase (A1 2.1, 3.2)."""
import os
import time
from pathlib import Path

from .. import godot, out, proc, project as project_mod

HELP = "load-check scripts and scenes, find parse errors and broken scenes"
USAGE = """
h check [PATH...] [--changed] [--smoke] [--smoke-frames N] [--no-lint] [--no-deps] [--include-addons]
PATH: file or dir (cwd-relative, absolute or res://), default: the whole project.
--changed        files changed vs git HEAD (+ untracked) and their dependents
--smoke          also instantiate scenes into the tree and run N physics frames (runs project code)
--no-deps        do not add scenes/resources that reference the selected files
--no-lint        skip the lint phase
--include-addons also check addons/ (default: skipped)"""

SUFFIXES = (".gd", ".tscn", ".tres")


def _parser():
    p = out.common_parser("check")
    p.add_argument("paths", nargs="*")
    p.add_argument("--changed", action="store_true")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--smoke-frames", type=int, default=2)
    p.add_argument("--no-lint", action="store_true")
    p.add_argument("--no-deps", action="store_true")
    p.add_argument("--include-addons", action="store_true")
    return p


def _walk(root: Path, project: Path, include_addons: bool):
    for dp, dns, fns in os.walk(root):
        d = Path(dp)
        keep = []
        for n in sorted(dns):
            if n.startswith(".") or (d / n / ".gdignore").exists():
                continue
            if n == "addons" and d == project and not include_addons:
                continue
            keep.append(n)
        dns[:] = keep
        for fn in sorted(fns):
            if fn.endswith(SUFFIXES):
                yield d / fn


def _res(project: Path, p: Path) -> str:
    return "res://" + p.relative_to(project).as_posix()


def _resolve_path(r, project: Path, arg: str) -> Path:
    if arg.startswith("res://"):
        p = project / arg[len("res://"):]
    else:
        p = Path(arg).expanduser()
        p = p if p.is_absolute() else Path.cwd() / p
    p = Path(os.path.normpath(p))
    try:
        p.resolve().relative_to(project.resolve())
    except ValueError:
        r.error(2, f"usage: path outside project: {arg}")
    if not p.exists():
        r.error(2, f"usage: no such file: {arg}")
    return p.resolve()


def _git_changed(r, project: Path) -> list:
    g = proc.run(["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"], timeout=15)
    if g.rc != 0 or "true" not in g.stdout:
        r.error(2, "usage: --changed needs a git work tree")
    names = set()
    for argv in (["git", "-C", str(project), "diff", "--name-only", "--relative", "HEAD"],
                 ["git", "-C", str(project), "diff", "--name-only", "--relative", "--cached"],
                 ["git", "-C", str(project), "ls-files", "--others", "--exclude-standard"]):
        res = proc.run(argv, timeout=30)
        if res.rc == 0:
            names |= {ln.strip() for ln in res.stdout.splitlines() if ln.strip()}
    return [n for n in sorted(names) if (project / n).is_file()]


def build_file_set(r, project: Path, args) -> tuple:
    """-> (selected files, all files incl. dependents) as sorted lists of res:// paths."""
    inc = args.include_addons
    selected = set()
    if not args.paths and not args.changed:
        selected = {_res(project, f) for f in _walk(project, project, inc)}
        return sorted(selected), sorted(selected), False
    for a in args.paths:
        p = _resolve_path(r, project, a)
        if p.is_dir():
            in_addons = "addons" in p.relative_to(project.resolve()).parts
            for f in _walk(p, project, inc or in_addons):
                selected.add(_res(project, f))
        elif p.name.endswith(SUFFIXES):
            selected.add(_res(project, Path(p)))
    if args.changed:
        for n in _git_changed(r, project):
            rel = Path(n)
            parts = rel.parts
            if any(x.startswith(".") for x in parts[:-1]) or (parts[0] == "addons" and not inc):
                continue
            if rel.name.endswith(SUFFIXES):
                selected.add("res://" + rel.as_posix())
    allf = set(selected)
    if not args.no_deps and selected:
        needles = [f'path="{s}"' for s in selected]
        for f in _walk(project, project, inc):
            if not f.name.endswith((".tscn", ".tres")) or _res(project, f) in allf:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(n in text for n in needles):
                allf.add(_res(project, f))
    return sorted(selected), sorted(allf), True


def _lint(r, project, args, selected, allf, scoped):
    """-> phase text. Calls harness.lint.run_lint when available (R-29)."""
    if args.no_lint:
        return "lint skipped (--no-lint)"
    import importlib
    modname = __package__.rsplit(".", 1)[0] + ".lint"
    try:
        lint = importlib.import_module(modname)
    except ModuleNotFoundError as e:
        if e.name == modname:
            return "lint skipped (harness.lint not installed)"
        raise
    t0 = time.monotonic()
    lint.run_lint(r, project, allf if scoped else None, "full")
    return f"lint {time.monotonic() - t0:.1f}s"


def _main(r, args, project):
    from .. import checkrun
    t0 = time.monotonic()
    if args.smoke_frames < 1 or args.smoke_frames > 600:
        r.error(2, "usage: --smoke-frames must be within 1-600")
    selected, files, scoped = build_file_set(r, project, args)
    godot.binary(r, project)
    kinds = {s: sum(1 for f in files if f.endswith(s)) for s in SUFFIXES}
    files_stat = ", ".join(f"{n} {s}" for s, n in kinds.items() if n) or "0 .gd"
    if not files:
        r.stat("import", "skipped")
        r.stat("files", "0 .gd")
        r.stat("phases", "scripts 0.0s, scenes 0.0s, "
                         f"{'lint skipped (--no-lint)' if args.no_lint else 'lint skipped (nothing to check)'}, "
                         f"smoke {'on' if args.smoke else 'off'}")
        return r.finish(f"0 findings in 0 files ({time.monotonic() - t0:.1f}s)")
    godot.ensure_imported(r, project)
    r.stat("files", files_stat)
    imp = getattr(r, "import_invocation", None)
    timings = {}
    if imp is not None and imp.failed:
        r.check("SKIP", "scripts", "import failed")
        r.check("SKIP", "scenes", "import failed")
        lint_txt = "lint skipped (import failed)"
    else:
        found = checkrun.load_check(r, project, files, smoke=args.smoke_frames if args.smoke else 0)
        r.add_findings(found)
        timings = r.extra.get("check", {}).get("timings", {})
        lint_txt = _lint(r, project, args, selected, files, scoped)
    r.extra.setdefault("check", {})["files"] = files
    r.stat("phases", f"scripts {timings.get('scripts', 0.0):.1f}s, scenes {timings.get('scenes', 0.0):.1f}s, "
                     f"{lint_txt}, smoke {'on' if args.smoke else 'off'}")
    e = sum(1 for f in r.findings if f["severity"] == "error")
    w = sum(1 for f in r.findings if f["severity"] == "warning")
    el = time.monotonic() - t0
    if e or w:
        reason = f"{e} error{'s' if e != 1 else ''}, {w} warning{'s' if w != 1 else ''} in {len(files)} files ({el:.1f}s)"
    else:
        reason = f"0 findings in {len(files)} files ({el:.1f}s)"
    return r.finish(reason)


def run(argv):
    return out.invoke("check", argv, _parser(), _main)
