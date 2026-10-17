"""h lint: Godot-free lint of scripts, scenes and project.godot (A3 spec 2.1)."""
import os
import time
from pathlib import Path

from .. import out, proc, project as project_mod

HELP = "fast Godot-free lint: Godot 3 idioms, name errors, determinism"
USAGE = """
h lint [PATH...] [--project DIR] [--strict] [--hook] [--changed] [--godot3-oracle]
PATH: file or dir (res://, cwd-relative or absolute), default: the whole project.
--hook           fast mode for hooks: needs PATHs, adds LSP diagnostics if a daemon runs
--changed        lint files changed in git (modified, added, untracked)
--godot3-oracle  also ask the engine converter what it would rewrite in the given .gd files"""

CONFIG_TABLE = "lint"
CONFIG_KEYS = {"severity": dict, "exclude": list, "replay_dirs": list, "rng_files": list, "remap_files": list,
               "lsp_in_hook": bool}


def _parser():
    p = out.common_parser("lint")
    p.add_argument("paths", nargs="*")
    p.add_argument("--hook", action="store_true")
    p.add_argument("--changed", action="store_true")
    p.add_argument("--godot3-oracle", dest="oracle", action="store_true")
    return p


def _resolve(r, project: Path, arg: str) -> Path:
    if arg.startswith("res://"):
        p = project / arg[len("res://"):]
    else:
        p = Path(arg).expanduser()
        p = p if p.is_absolute() else Path.cwd() / p
    p = Path(os.path.normpath(p))
    try:
        p.relative_to(project)
    except ValueError:
        try:
            p.resolve().relative_to(project)
            p = p.resolve()
        except ValueError:
            r.error(2, f"usage: path outside project: {arg}")
    if not p.exists():
        r.error(2, f"usage: no such file or dir: {arg}")
    return p


def _git_changed(r, project: Path) -> list:
    g = proc.run(["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"], timeout=15)
    if g.rc != 0 or "true" not in g.stdout:
        r.error(2, "usage: --changed needs a git work tree")
    names = set()
    for argv in (["git", "-C", str(project), "diff", "--name-only", "--relative", "HEAD"],
                 ["git", "-C", str(project), "diff", "--name-only", "--relative", "--cached"],
                 ["git", "-C", str(project), "ls-files", "--others", "--exclude-standard", "--full-name"]):
        res = proc.run(argv, timeout=30)
        if res.rc == 0:
            names |= {ln.strip() for ln in res.stdout.splitlines() if ln.strip()}
    out_files = []
    for n in sorted(names):
        f = project / n
        if f.is_file() and not any(x.startswith(".") for x in Path(n).parts[:-1]):
            out_files.append(f)
    return out_files


def _main(r, args, project):
    from .. import lint as lint_mod
    t0 = time.monotonic()
    if args.hook and not args.paths and not args.changed:
        r.error(2, "usage: --hook needs at least one PATH")
    if args.oracle and not args.paths:
        r.error(2, "usage: --godot3-oracle needs at least one PATH")
    paths = None
    if args.paths or args.changed:
        paths = [_resolve(r, project, a) for a in args.paths]
        if args.changed:
            paths += _git_changed(r, project)
    lint_mod.run_lint(r, project, paths, "hook" if args.hook else "full")
    nfiles = r.extra.get("lint", {}).get("files", 0)
    if args.oracle:
        from ..lint import oracle
        gd = [p for p in lint_mod.gather(project, paths) if p[1] == ".gd"]
        oracle.run_oracle(r, project, [p for p, _k in gd])
    e = sum(1 for f in r.findings if f["severity"] == "error")
    w = sum(1 for f in r.findings if f["severity"] == "warning")
    el = time.monotonic() - t0
    if e or w:
        reason = f"{e} error{'s' if e != 1 else ''}, {w} warning{'s' if w != 1 else ''} in {nfiles} files ({el:.2f}s)"
    else:
        reason = f"0 findings in {nfiles} files ({el:.2f}s)"
    return r.finish(reason)


def run(argv):
    return out.invoke("lint", argv, _parser(), _main)
