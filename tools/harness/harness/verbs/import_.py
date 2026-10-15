"""h import: run `godot --import` on the project (A1 2.2)."""
import shutil
import time

from .. import godot, out

HELP = "import project resources (always runs godot --import)"
USAGE = """
h import [--force]
--force   delete .godot/ first (full re-import)
Import log findings (e.g. a scene that fails to parse at import) count."""


def _parser():
    p = out.common_parser("import")
    p.add_argument("--force", action="store_true")
    return p


def _main(r, args, project):
    t0 = time.monotonic()
    godot.binary(r, project)
    if args.force:
        shutil.rmtree(project / ".godot", ignore_errors=True)
    inv = godot.run_import(r, project)
    r.add_findings(inv.findings)
    r.stat("import", "ran (forced)" if args.force else "ran (requested)")
    dur = time.monotonic() - t0
    r.stat("duration", f"{dur:.1f}s")
    e = sum(1 for f in r.findings if f["severity"] == "error")
    w = sum(1 for f in r.findings if f["severity"] == "warning")
    if e or w:
        reason = f"{e} error{'s' if e != 1 else ''}, {w} warning{'s' if w != 1 else ''} during import ({dur:.1f}s)"
    else:
        reason = f"imported in {dur:.1f}s"
    return r.finish(reason)


def run(argv):
    return out.invoke("import", argv, _parser(), _main)
