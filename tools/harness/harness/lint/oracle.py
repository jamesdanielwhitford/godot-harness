"""--godot3-oracle: ask the engine's --validate-conversion-3to4 what it would rewrite (spec 3.5). Nothing is converted."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .. import godot, project as _p  # noqa: F401

CHECK_RE = re.compile(r'Checking for conversion - \d+/\d+ file - "(.+)"')
LINE_RE = re.compile(r'^\s*Line\((\d+)\), (.+) -> (.+?)  -  LINE """ (.*) """$')
FULL_RE = re.compile(r'^\s*Line \(\d+\) - FULL LINES - """ (.*) """  =====>  """ (.*) """$')


def _tmp_root() -> Path:
    return Path(os.environ.get("HARNESS_TMP") or (os.environ.get("TMPDIR") or "/tmp") + "/godot-harness")


def run_oracle(run, project: Path, files) -> None:
    from . import proj_res
    if not files:
        return
    work = _tmp_root() / f"oracle-{run.run_id}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        (work / "project.godot").write_text('config_version=5\n[application]\nconfig/name="oracle"\n')
        names = {}
        for i, f in enumerate(files):
            name = f"f{i}_{Path(f).name}"
            shutil.copyfile(f, work / name)
            names[name] = Path(f)
        inv = godot.run(run, "oracle", work, args=["--validate-conversion-3to4"], expected_rc={0})
        for fd in inv.findings:
            if fd["rule"].startswith("harness."):
                run.add_findings([{**fd, "path": None}])
        cur = None
        seen = set()
        for ln in inv.text.splitlines():
            m = CHECK_RE.search(ln)
            if m:
                cur = Path(m.group(1)).name
                continue
            m = FULL_RE.match(ln)
            old = new = None
            if m:
                old, new = m.group(1), m.group(2)
            else:
                m = LINE_RE.match(ln)
                if m:
                    old, new = m.group(4), m.group(3)
                    new = f"{m.group(2)} -> {m.group(3)}"
            if old is None or cur not in names:
                continue
            src = names[cur]
            lines = [x.strip() for x in src.read_text(errors="replace").split("\n")]
            line = next((i + 1 for i, x in enumerate(lines) if x == old.strip()), None)
            key = (cur, line, old, new)
            if key in seen:
                continue
            seen.add(key)
            run.finding(proj_res(project, src), line, "lint.g3-oracle", "warning",
                        f"converter would rewrite: {old.strip()}", hint=f"official converter: {new}", source="verb")
    finally:
        shutil.rmtree(work, ignore_errors=True)
