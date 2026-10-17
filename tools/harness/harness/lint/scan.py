"""Regex pass (port of research/scripts/r1_5_lint/scan.py with anchor prefilter, dedup, scope; spec 3.2)."""
from __future__ import annotations

import re

from . import rules

IDENT_RE = re.compile(r"[A-Za-z_]\w*")


def file_kind(name: str):
    if name == "project.godot":
        return "project.godot"
    for e in (".gd", ".tscn", ".tres"):
        if name.endswith(e):
            return e
    return None


def candidates(kind: str, text: str) -> list:
    noanchor, anchored = rules.rules_data()["by_ext"].get(kind, ([], {}))
    cands = list(noanchor)
    if anchored:
        for ident in set(IDENT_RE.findall(text)):
            lst = anchored.get(ident)
            if lst:
                cands.extend(lst)
    return cands


def regex_hits(kind: str, text: str, lines: list, allowed) -> list:
    """-> [(line, rule dict)] for rules passing `allowed(rule) -> bool`. One hit per (line, rule)."""
    comment = "#" if kind == ".gd" else ";"
    hits = []
    for rule in candidates(kind, text):
        if not allowed(rule):
            continue
        rx, rx_m = rules.compiled(rule)
        if not rx_m.search(text):
            continue
        for i, ln in enumerate(lines, 1):
            if not ln:
                continue
            if ln.lstrip().startswith(comment) and (kind == ".gd" or ln.startswith(";")):
                continue
            if rx.search(ln):
                hits.append((i, rule))
    # overlap dedup: generated-family hit on a line removes hand-rule hits on that line
    gen_lines = {i for i, r in hits if r["family"] in rules.GENERATED}
    if gen_lines:
        hits = [(i, r) for i, r in hits if not (i in gen_lines and r["id"] in rules.HAND_DEDUP)]
    return hits
