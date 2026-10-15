"""Dispatcher with verb auto-discovery from harness/verbs/<verb>.py (contract 2.1)."""
import importlib
import pkgutil
import sys

from . import verbs

MAX_HELP = 40


def cli_name(module_name):
    if module_name.endswith("_"):
        module_name = module_name[:-1]
    return module_name.replace("_", "-")


def discover():
    """{cli verb name: module name}"""
    found = {}
    for m in pkgutil.iter_modules(verbs.__path__):
        if not m.name.startswith("_"):
            found[cli_name(m.name)] = m.name
    return dict(sorted(found.items()))


def _load(modname):
    return importlib.import_module(f"{verbs.__name__}.{modname}")


def _edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _top_help(names):
    lines = ["usage: h <verb> [args]"]
    for name, mod in names.items():
        try:
            helptext = _load(mod).HELP
        except Exception as e:  # a broken verb must not break `h --help`
            helptext = f"(broken: {type(e).__name__})"
        lines.append(f"  {name}  {helptext}")
    return "\n".join(lines[:MAX_HELP]) + "\n"


def _verb_help(name, mod):
    lines = [f"usage: h {name} [options]", mod.HELP]
    usage = getattr(mod, "USAGE", None)
    if usage:
        lines += usage.strip("\n").splitlines()
    lines += ["common options: --project DIR  --strict  -h/--help"]
    return "\n".join(lines[:MAX_HELP]) + "\n"


def main(argv):
    names = discover()
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(_top_help(names))
        return 0 if argv else 2
    verb = argv[0]
    if verb not in names:
        close = sorted(names, key=lambda n: _edit_distance(verb, n))
        hint = f" (did you mean '{close[0]}'?)" if close and _edit_distance(verb, close[0]) <= 2 else ""
        print(f"ERROR h unknown verb '{verb}'{hint}"[:240])
        return 2
    mod = _load(names[verb])
    rest = argv[1:]
    before_dd = rest[: rest.index("--")] if "--" in rest else rest
    if "-h" in before_dd or "--help" in before_dd:
        sys.stdout.write(_verb_help(verb, mod))
        return 0
    try:
        return int(mod.run(rest) or 0)
    except SystemExit as e:
        return int(e.code or 0)
