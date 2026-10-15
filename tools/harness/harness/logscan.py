"""Godot log scan (contract 2.8.4). Pure, stdlib only.

scan(text, extra_ignore=[]) -> list of {"path","line","rule","severity","message","hint"}.
"""
from __future__ import annotations

import re

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PAREN_LOC = re.compile(r"\((res://[^():]+):(\d+)\)")
TOKEN_LOC = re.compile(r"(res://[^\s():\"']+):(\d+)")
RES_PATH = re.compile(r"res://[^\s\"'():]+")

BENIGN = [re.compile(p) for p in (r"^Godot Engine v\d", r"remote port number must be between 1 and 65535",
                                   r"Could not set V-Sync mode", r"^ALSA lib ", r"cannot find card")]

# (id, regex, severity, protected, location kind)   location: "next" | "quoted" | "respath" | None
RULES = [
    ("godot.parse-error", re.compile(r"^SCRIPT ERROR: Parse Error: (.*)"), "error", True, "next"),
    ("godot.script-error", re.compile(r"^SCRIPT ERROR: (.*)"), "error", True, "next"),
    ("godot.script-load-failed", re.compile(r'^ERROR: Failed to load script "(res://[^"]+)"(.*)'), "error", True,
     "quoted"),
    ("godot.crash", re.compile(r"^(handle_crash: Program crashed|Aborted|Segmentation fault)(.*)"), "error", True,
     None),
    ("godot.load-failed", re.compile(r"^ERROR: ((?:Failed loading resource|Failed to load resource|Cannot load|"
                                     r"No loader found)(?:.*))"), "error", False, "respath"),
    ("godot.parent-vanished", re.compile(r"^WARNING: (Parent path .* has vanished.*)"), "error", False, None),
    ("godot.vanished", re.compile(r"^WARNING: (.*has vanished.*)"), "error", False, None),
    ("godot.leak", re.compile(r"^WARNING: (\d+ ObjectDB instances? (?:was|were) leaked at exit.*)"), "info", False,
     None),
    ("godot.error", re.compile(r"^ERROR: (.*)"), "error", False, "next"),
    ("godot.warning", re.compile(r"^WARNING: (.*)"), "warning", False, "next"),
]
PROTECTED = {r[0] for r in RULES if r[3]}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def classify_line(line: str):
    """-> (rule tuple, message) of the first matching rule, or None."""
    for rule in RULES:
        m = rule[1].search(line)
        if m:
            if rule[0] == "godot.crash":
                return rule, line.strip()
            if rule[0] == "godot.script-load-failed":
                return rule, line[len("ERROR: "):].strip()
            return rule, m.group(1).strip()
    return None


def _is_benign(line: str) -> bool:
    return line.startswith("@@H ") or any(b.search(line) for b in BENIGN)


def scan(text: str, extra_ignore=()) -> list[dict]:
    ignore = [re.compile(p) for p in (extra_ignore or [])]
    lines = strip_ansi(text).splitlines()
    hits = []  # (index, rule, message)
    for i, ln in enumerate(lines):
        if _is_benign(ln):
            continue
        c = classify_line(ln)
        if c:
            hits.append((i, c[0], c[1]))
    rule_lines = {i for i, _, _ in hits}
    out = []
    for i, rule, msg in hits:
        rid, _, sev, protected, kind = rule
        if not protected and any(rx.search(lines[i]) for rx in ignore):
            continue
        path = line_no = None
        if kind == "next":
            end = i
            for j in range(i + 1, min(i + 7, len(lines))):
                if j in rule_lines:
                    break
                end = j
            window = lines[i: end + 1]
            for w in window:
                m = PAREN_LOC.search(w)
                if m:
                    path, line_no = m.group(1), int(m.group(2))
                    break
            if path is None:
                m = TOKEN_LOC.search(lines[i])
                if m:
                    path, line_no = m.group(1), int(m.group(2))
        elif kind == "quoted":
            path = rule[1].search(lines[i]).group(1)
        elif kind == "respath":
            m = RES_PATH.search(lines[i])
            if m:
                path = m.group(0).rstrip(".,;")
        out.append({"path": path, "line": line_no, "rule": rid, "severity": sev, "message": msg, "hint": None})
    return out
