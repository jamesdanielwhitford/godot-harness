"""Dev only (run from .venv): generate lint_rules.json, native_classes.json, builtin_actions.json (spec 03 section 3.1).

    .venv/bin/python tools/harness/rules/build_lint_data.py [--no-actions]

Reads .claude/research/scripts/r1_5_lint/lint_rules_full.yaml and $HARNESS_CACHE/api/<ver>/extension_api.json, asks
Godot (30 s timeout) for InputMap.get_actions() in an empty project. Output is byte-stable (sorted keys).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
YAML = REPO / ".claude" / "research" / "scripts" / "r1_5_lint" / "lint_rules_full.yaml"
PINS = REPO / "tools" / "harness" / "pins.toml"
GENERATED = {"fn", "prop", "sig", "enum", "class", "tscnclass", "color", "theme"}
EXTS = {".gd", ".tscn", ".tres"}

LINT_RULES = [
    {"id": "lint.det-global-rng", "applies_to": [".gd"], "severity": "warning", "scope": "det",
     "regex": r"(?:(?<![\w.])(?<!func )(?:randf|randi|randf_range|randi_range|randfn|randomize|seed)\s*\("
              r"|\.(?:shuffle|pick_random)\s*\(\s*\))",
     "message": "global RNG used in deterministic code",
     "hint": "use the seeded Rng autoload / a RandomNumberGenerator, never the global RNG"},
    {"id": "lint.det-wallclock", "applies_to": [".gd"], "severity": "warning", "scope": "det",
     "regex": r"\b(?:Time\.(?:get_ticks_msec|get_ticks_usec|get_unix_time_from_system|get_datetime_\w+_from_system"
              r"|get_date_\w+_from_system|get_time_\w+_from_system)|Engine\.get_(?:process_frames|frames_drawn))\s*\(",
     "message": "wall clock or frame counter read in deterministic code",
     "hint": "count physics ticks (Engine.get_physics_frames or own counter)"},
    {"id": "lint.det-time-scale", "applies_to": [".gd"], "severity": "warning", "scope": "all",
     "regex": r"\bEngine\.(?:time_scale\s*=(?!=)|set_time_scale\s*\()",
     "message": "Engine.time_scale changed",
     "hint": "replays and feel metrics assume 1.0; run more ticks per wall second instead"},
    {"id": "lint.sim-node", "applies_to": [".gd"], "severity": "error", "scope": "sim",
     "regex": r"\bNodePath\b|\bget_node(?:_or_null)?\s*\(|\bget_tree\s*\(|(?<![\w\"'])\$[A-Za-z_\"]"
              r"|(?<![\w\"'])%[A-Z]\w*|\^\"",
     "message": "Node API used in node-free simulation code",
     "hint": "sim state is node-free: store int ids, rebuild the view from events (A9)"},
    {"id": "lint.raw-keycode", "applies_to": [".gd"], "severity": "warning", "scope": "all",
     "regex": r"(?<![\w.])KEY_[A-Z0-9_]+\b|\bKey\.[A-Z]\w*|\.(?:physical_)?keycode\b"
              r"|\bInput\.is_(?:physical_)?key_pressed\s*\(",
     "message": "raw key code outside remap code",
     "hint": "use InputMap actions; raw keys only in remap code (P15)"},
    {"id": "lint.g3-project", "applies_to": ["project.godot"], "severity": "error", "scope": "all",
     "regex": r"^config_version=[0-4]\s*$",
     "message": "Godot 3 project file (config_version < 5)",
     "hint": "Godot 3 project: --convert-3to4 on a copy, then review"},
]


def godot_version() -> str:
    for ln in PINS.read_text().splitlines():
        m = re.match(r'godot_version_string\s*=\s*"([^"]+)"', ln)
        if m:
            return m.group(1)
    raise SystemExit("no godot_version_string in pins.toml")


def cache_dir() -> Path:
    return Path(os.environ.get("HARNESS_CACHE") or Path.home() / ".cache" / "godot-harness")


def build_rules(ver: str) -> dict:
    rows = yaml.safe_load(YAML.read_text())
    rules = []
    seen = set()
    for r in rows:
        rid = r["id"]
        assert rid not in seen, rid
        seen.add(rid)
        fam = rid.split("-", 1)[0]
        risk = r["false_positive_risk"]
        anchor = None
        if fam in GENERATED:
            anchor = rid.split("-", 1)[1]
            assert re.fullmatch(r"[A-Za-z_]\w*", anchor) and anchor in r["regex"], rid
        applies = [e for e in str(r["applies_to"]).split(",") if e in EXTS]
        assert applies, rid
        re.compile(r["regex"])
        rec = {"id": rid, "regex": r["regex"], "applies_to": applies,
               "severity": "error" if risk == "low" else "warning", "message": str(r["message"]),
               "hint": str(r["godot4_replacement"]), "family": fam, "anchor": anchor, "scope": "all", "risk": risk,
               "demo_corpus_hits": int(r.get("demo_corpus_hits") or 0)}
        rules.append(rec)
    for r in LINT_RULES:
        re.compile(r["regex"])
        rules.append({**r, "family": "lint", "anchor": None, "risk": "n/a"})
    return {"schema": "harness.lint-rules/1", "godot": ver, "rules": rules}


def build_native(ver: str) -> dict:
    api = json.loads((cache_dir() / "api" / ver / "extension_api.json").read_text())
    classes = {}
    for c in api["classes"]:
        classes[c["name"]] = {"inherits": c.get("inherits", ""), "signals": sorted(s["name"] for s in c.get("signals", []))}
    return {"schema": "harness.native-classes/1", "godot": ver, "classes": classes}


def build_actions(ver: str) -> dict:
    godot = REPO / "tools" / "bin" / "godot"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "project.godot").write_text('config_version=5\n[application]\nconfig/name="x"\n')
        (Path(td) / "a.gd").write_text(
            "extends SceneTree\nfunc _init():\n\tvar a = InputMap.get_actions()\n\tprint('ACTIONS:' + ','.join(PackedStringArray(a)))\n\tquit()\n")
        res = subprocess.run([str(godot), "--headless", "--path", td, "-s", "a.gd"], capture_output=True, text=True,
                             timeout=30)
    m = re.search(r"^ACTIONS:(.*)$", res.stdout, re.M)
    if not m:
        raise SystemExit("no ACTIONS line:\n" + res.stdout + res.stderr)
    return {"schema": "harness.builtin-actions/1", "godot": ver, "actions": sorted(set(m.group(1).split(",")))}


def dump(path: Path, data: dict):
    path.write_text(json.dumps(data, sort_keys=True, indent=None, separators=(",", ":"), ensure_ascii=False) + "\n")


def main(argv):
    ver = godot_version()
    data = build_rules(ver)
    dump(HERE / "lint_rules.json", data)
    print("rules", len(data["rules"]))
    nat = build_native(ver)
    dump(HERE / "native_classes.json", nat)
    print("classes", len(nat["classes"]))
    if "--no-actions" not in argv and (not (HERE / "builtin_actions.json").exists() or "--actions" in argv):
        act = build_actions(ver)
        dump(HERE / "builtin_actions.json", act)
        print("actions", len(act["actions"]))


if __name__ == "__main__":
    main(sys.argv[1:])
