"""Rule data loading, lazy regex compile cache, severity resolution and globs (A3 spec 2.4, 2.6, 3.2)."""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"
GENERATED = frozenset({"fn", "prop", "sig", "enum", "class", "tscnclass", "color", "theme"})
HAND_DEDUP = frozenset({"syn-rand-seed", "syn-change-scene", "syn-find-node", "tscn-g3-types", "syn-rect-props-gd",
                        "tscn-rect-props"})
SEVERITIES = ("error", "warning", "info")
SEVERITY_VALUES = ("error", "warning", "info", "off")

# rules implemented in code (no regex in the data file): id -> (scope, default severity, message, hint)
CODE_RULES = {
    "lint.input-action": ("all", "error", "InputMap action does not exist", ""),
    "lint.signal-name": ("all", "error", "unknown signal name", ""),
    "lint.indent-mixed": ("all", "error", "mixed tab and space indentation",
                          "re-indent with the file's style (tabs default)"),
    "lint.det-idle-tween": ("det", "warning", "Tween runs in idle mode (not deterministic)",
                            ".set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)"),
    "lint.det-idle-timer": ("det", "warning", "Timer runs in idle mode (not deterministic)",
                            "process_callback = Timer.TIMER_PROCESS_PHYSICS / create_timer(t, false, true)"),
    "lint.det-idle-anim": ("det", "warning", "AnimationPlayer/AnimationTree runs in idle mode (not deterministic)",
                           "callback_mode_process = ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS"),
}
OTHER_IDS = ("lint.bad-suppress", "lint.g3-oracle", "lint.lsp", "lint.lsp-timeout", "lint.lsp-daemon")

_data = None
_native = None
_actions = None


class RulesError(Exception):
    pass


def _load_json(name: str) -> dict:
    p = RULES_DIR / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RulesError(f"rule data missing or invalid: {p.name}: {e}") from None


def rules_data() -> dict:
    global _data
    if _data is None:
        d = _load_json("lint_rules.json")
        if d.get("schema") != "harness.lint-rules/1" or not isinstance(d.get("rules"), list):
            raise RulesError("rule data invalid: lint_rules.json schema")
        rules = d["rules"]
        by_id = {r["id"]: r for r in rules}
        by_ext: dict = {}
        for r in rules:
            for ext in r["applies_to"]:
                slot = by_ext.setdefault(ext, ([], {}))
                if r["anchor"]:
                    slot[1].setdefault(r["anchor"], []).append(r)
                else:
                    slot[0].append(r)
        _data = {"rules": rules, "by_id": by_id, "by_ext": by_ext, "rx": {}}
    return _data


def native_classes() -> dict:
    global _native
    if _native is None:
        _native = _load_json("native_classes.json")["classes"]
    return _native


def builtin_actions() -> list:
    global _actions
    if _actions is None:
        _actions = _load_json("builtin_actions.json")["actions"]
    return _actions


def all_rule_ids() -> list:
    return sorted(set(rules_data()["by_id"]) | set(CODE_RULES) | set(OTHER_IDS))


def rule_count() -> int:
    return len(all_rule_ids())


def compiled(rule: dict):
    """(line regex, multiline whole-text prefilter regex)"""
    cache = rules_data()["rx"]
    hit = cache.get(rule["id"])
    if hit is None:
        hit = (re.compile(rule["regex"]), re.compile(rule["regex"], re.M))
        cache[rule["id"]] = hit
    return hit


def default_rule(rule_id: str):
    """-> dict(severity, message, hint, scope) for any known id, or None."""
    r = rules_data()["by_id"].get(rule_id)
    if r:
        return r
    c = CODE_RULES.get(rule_id)
    if c:
        return {"id": rule_id, "scope": c[0], "severity": c[1], "message": c[2], "hint": c[3]}
    return None


# ---- globs over res:// paths --------------------------------------------------------------------------------
_glob_cache: dict = {}


def glob_regex(pat: str):
    rx = _glob_cache.get(pat)
    if rx is None:
        out = []
        i = 0
        while i < len(pat):
            c = pat[i]
            if pat.startswith("**/", i):
                out.append("(?:.*/)?")
                i += 3
                continue
            if pat.startswith("**", i):
                out.append(".*")
                i += 2
                continue
            if c == "*":
                out.append("[^/]*")
            elif c == "?":
                out.append("[^/]")
            else:
                out.append(re.escape(c))
            i += 1
        rx = _glob_cache[pat] = re.compile("".join(out) + r"\Z", re.S)
    return rx


def glob_match(res_path: str, patterns) -> bool:
    return any(glob_regex(p).match(res_path) for p in patterns)


def in_dirs(res_path: str, dirs) -> bool:
    for d in dirs:
        d = d.rstrip("/")
        if d in ("res:", "res:/", ""):
            return True
        if res_path == d or res_path.startswith(d + "/"):
            return True
    return False


# ---- severity resolution -----------------------------------------------------------------------------------
def validate_severity_map(sev: dict) -> list:
    """-> list of error messages (empty when ok)."""
    errs = []
    ids = all_rule_ids()
    for key, val in sev.items():
        if val not in SEVERITY_VALUES:
            errs.append(f"[lint] severity '{key}' has invalid value {val!r} (use error, warning, info or off)")
        if not any(ch in key for ch in "*?[") and key not in ids:
            errs.append(f"[lint] severity key '{key}' matches no rule")
        elif any(ch in key for ch in "*?[") and not fnmatch.filter(ids, key):
            errs.append(f"[lint] severity key '{key}' matches no rule")
    return errs


def resolve_severity(rule_id: str, default: str, sev_map: dict) -> str:
    """exact id > longest matching glob (family glob > lint.*) > default. Returns error|warning|info|off."""
    if not sev_map:
        return default
    if rule_id in sev_map:
        return sev_map[rule_id]
    best = None
    for key in sev_map:
        if any(ch in key for ch in "*?[") and fnmatch.fnmatchcase(rule_id, key):
            if best is None or len(key) > len(best):
                best = key
    return sev_map[best] if best is not None else default
