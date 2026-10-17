"""# lint-ignore suppression comments in .gd files (A3 spec 2.7)."""
from __future__ import annotations

import re

SAME_RE = re.compile(r"#\s*lint-ignore:\s*(.*)$")
NEXT_RE = re.compile(r"^\s*#\s*lint-ignore-next-line:\s*(.*)$")


def _ids(s: str) -> list:
    return [t.strip() for t in s.split(",") if t.strip()]


def parse(lines) -> tuple:
    """-> (targets {line: set(ids)}, bad [(line, id)]) with 1-based lines; next-line form targets line+1."""
    targets: dict = {}
    bad: list = []
    for i, ln in enumerate(lines, 1):
        if "lint-ignore" not in ln:
            continue
        m = NEXT_RE.match(ln)
        if m:
            targets.setdefault(i + 1, set()).update(_ids(m.group(1)))
            for t in _ids(m.group(1)):
                bad.append((i, t))
            continue
        if ln.lstrip().startswith("#"):
            continue
        m = SAME_RE.search(ln)
        if m:
            targets.setdefault(i, set()).update(_ids(m.group(1)))
            for t in _ids(m.group(1)):
                bad.append((i, t))
    return targets, bad
