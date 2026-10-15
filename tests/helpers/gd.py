"""In-engine gdUnit4 suites for addons/harness (contract 2.12, REVIEW R-39). Owner: T1.

run_gd_suites(area, fixture="gd_host") copies the fixture (or "@sample") to $HARNESS_TMP, runs `h sync`
(with gdUnit4), copies tests/gd/<area>/*.gd to <copy>/tests/<area>/ and runs
`h test --project <copy> res://tests/<area>/`. The returned Result has `.extra["copy"]` (the project copy);
callers remove it with `cleanup(result)` after assert_contract (which reads the run dir inside the copy).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from helpers.h import REPO, HelperError, Result, copy_fixture, run_h


def _tmp_root() -> Path:
    root = os.environ.get("HARNESS_TMP") or str(Path(os.environ.get("TMPDIR") or "/tmp") / "godot-harness")
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_gd_suites(area: str, fixture: str = "gd_host", timeout: int = 900) -> Result:
    src = REPO / "tests" / "gd" / area
    if not src.is_dir():
        raise HelperError(f"no suites directory {src}")
    base = Path(tempfile.mkdtemp(prefix=f"gd-{area}-", dir=_tmp_root()))
    copy = base / "proj"
    copy_fixture(fixture, copy)
    out = base / "sync-out"
    r = run_h("sync", "--project", copy, env={"HARNESS_OUT": out})
    if r.rc != 0:
        raise HelperError(f"`h sync` on the {fixture} copy failed rc={r.rc}\n{r.stdout}")
    dest = copy / "tests" / area
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.gd")):
        shutil.copy2(f, dest / f.name)
    res = run_h("test", "--project", copy, f"res://tests/{area}/", timeout=timeout)
    res.extra["copy"] = copy
    res.extra["base"] = base
    return res


def cleanup(result: Result) -> None:
    base = result.extra.get("base")
    if base:
        shutil.rmtree(base, ignore_errors=True)
