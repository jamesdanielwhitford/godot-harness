"""h sync: mirror addons/harness (+ gdUnit4) into the project and enable the harness autoloads (A1 2.3)."""
from .. import out
from .. import sync as sync_lib

HELP = "install harness addon files, autoloads and gdUnit4 into a project"
USAGE = """
h sync [--no-gdunit] [--check]
Mirrors addons/harness (not runners/), enables the autoloads listed in harness.toml [harness] autoloads,
installs the pinned gdUnit4 unless --no-gdunit. --check writes nothing and fails when anything is stale."""


def _parser():
    p = out.common_parser("sync")
    p.add_argument("--no-gdunit", action="store_true")
    p.add_argument("--check", action="store_true")
    return p


def _main(r, args, project):
    reason = sync_lib.sync_project(r, project, gdunit=not args.no_gdunit, check=args.check)
    return r.finish(reason)


def run(argv):
    return out.invoke("sync", argv, _parser(), _main)
