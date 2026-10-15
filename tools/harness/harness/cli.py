"""Dispatcher with verb auto-discovery from harness/verbs/<verb>.py (plan B2)."""
import importlib
import pkgutil
import sys

from . import verbs


def discover():
    return sorted(m.name for m in pkgutil.iter_modules(verbs.__path__) if not m.name.startswith("_"))


def main(argv):
    names = discover()
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: h <verb> [args]\nverbs: " + " ".join(names))
        return 0 if argv else 2
    verb = argv[0]
    if verb not in names:
        print(f"h: unknown verb '{verb}'. verbs: {' '.join(names)}", file=sys.stderr)
        return 2
    mod = importlib.import_module(f"{__package__}.verbs.{verb}")
    return int(mod.run(argv[1:]) or 0)
