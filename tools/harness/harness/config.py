"""harness.toml loading and validation (contract 2.6).

`load(project) -> dict` returns {"harness": {...}, "timeouts": {...}, "scan": {...}, <discovered tables>: {...}}
with defaults filled in. Raises ConfigError(messages) for invalid input (the verb maps it to rc 2) and RuntimeError
when two verb modules declare the same CONFIG_TABLE (rc 3).
"""
from __future__ import annotations

import importlib
import pkgutil
import re
import tomllib
from pathlib import Path

from . import pins

TIMEOUT_KINDS = ("version", "import", "check_only", "runner", "smoke", "test", "scenario", "shot", "movie",
                 "doctool", "oracle", "lsp_start")
PROTECTED_SAMPLES = ("SCRIPT ERROR: Parse Error: x", "SCRIPT ERROR: x", 'ERROR: Failed to load script "res://x.gd"')
AUTOLOAD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

HARNESS_KEYS = {"schema": int, "godot": str, "godot_version": str, "tick_rate": int, "renderer": str,
                "autoloads": list, "sim_dirs": list, "test_dir": str}


class ConfigError(Exception):
    def __init__(self, messages):
        self.messages = list(messages)
        super().__init__("; ".join(self.messages))


def defaults() -> dict:
    return {
        "harness": {"schema": 1, "godot": "", "godot_version": pins.load()["godot_version_string"], "tick_rate": 60,
                    "renderer": "gl_compatibility", "autoloads": ["Harness", "Rng", "CommandBus", "Trace"],
                    "sim_dirs": ["res://sim"], "test_dir": "res://tests"},
        "timeouts": {},
        "scan": {"ignore": []},
    }


def discover_tables() -> dict:
    """{table: {key: type}} from CONFIG_TABLE/CONFIG_KEYS of every verb module (one declarer per table)."""
    from . import verbs
    tables: dict = {}
    owners: dict = {}
    for m in sorted(pkgutil.iter_modules(verbs.__path__), key=lambda x: x.name):
        if m.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{verbs.__name__}.{m.name}")
        except Exception as e:  # a broken verb module must not hide config errors for the others
            raise RuntimeError(f"cannot import verb module {m.name}: {e}") from e
        table = getattr(mod, "CONFIG_TABLE", None)
        if not table:
            continue
        if table in owners or table in ("harness", "timeouts", "scan"):
            raise RuntimeError(f"CONFIG_TABLE '{table}' declared twice ({owners.get(table, 'core')} and {m.name})")
        owners[table] = m.name
        tables[table] = dict(getattr(mod, "CONFIG_KEYS", {}))
    return tables


def _type_ok(v, t) -> bool:
    if isinstance(v, bool):
        return t is bool
    if t is float:
        return isinstance(v, (int, float))
    return isinstance(v, t)


def _tname(t) -> str:
    return getattr(t, "__name__", str(t))


def _check_table(name: str, data, keys: dict, errs: list):
    if not isinstance(data, dict):
        errs.append(f"[{name}] must be a table")
        return
    for k, v in data.items():
        if k not in keys:
            errs.append(f"unknown key '{k}' in [{name}]")
        elif not _type_ok(v, keys[k]):
            errs.append(f"[{name}] {k} must be {_tname(keys[k])}, got {type(v).__name__} {v!r}"[:200])


def validate_scan_ignore(patterns) -> list:
    errs = []
    for pat in patterns:
        if not isinstance(pat, str):
            errs.append(f"[scan] ignore entries must be strings, got {pat!r}")
            continue
        try:
            rx = re.compile(pat)
        except re.error as e:
            errs.append(f"[scan] ignore regex {pat!r} is invalid: {e}")
            continue
        for s in PROTECTED_SAMPLES:
            if rx.search(s):
                errs.append(f"[scan] ignore regex {pat!r} matches protected rule line {s!r}")
                break
    return errs


def load(project) -> dict:
    cfg = defaults()
    tables = discover_tables()
    for t in tables:
        cfg[t] = {}
    f = Path(project) / "harness.toml"
    if not f.is_file():
        return cfg
    try:
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ConfigError([f"invalid TOML: {e}"]) from None
    errs: list = []
    for tname, tdata in data.items():
        if tname == "harness":
            _check_table(tname, tdata, HARNESS_KEYS, errs)
        elif tname == "timeouts":
            _check_table(tname, tdata, {k: float for k in TIMEOUT_KINDS}, errs)
            for k, v in (tdata.items() if isinstance(tdata, dict) else []):
                if k in TIMEOUT_KINDS and _type_ok(v, float) and v <= 0:
                    errs.append(f"[timeouts] {k} must be > 0")
        elif tname == "scan":
            _check_table(tname, tdata, {"ignore": list}, errs)
            if isinstance(tdata, dict) and isinstance(tdata.get("ignore"), list):
                errs += validate_scan_ignore(tdata["ignore"])
        elif tname in tables:
            _check_table(tname, tdata, tables[tname], errs)
        else:
            errs.append(f"unknown table [{tname}]")
    h = data.get("harness", {})
    if isinstance(h, dict):
        if "renderer" in h and h["renderer"] != "gl_compatibility":
            errs.append("[harness] renderer: only 'gl_compatibility' is accepted in v0")
        if isinstance(h.get("autoloads"), list):
            for a in h["autoloads"]:
                if not isinstance(a, str) or not AUTOLOAD_RE.match(a):
                    errs.append(f"[harness] autoloads entry {a!r} is not an autoload name")
        for key in ("sim_dirs",):
            if isinstance(h.get(key), list) and not all(isinstance(x, str) for x in h[key]):
                errs.append(f"[harness] {key} must be a list of strings")
    if errs:
        raise ConfigError(errs)
    for tname, tdata in data.items():
        cfg.setdefault(tname, {}).update(tdata)
    return cfg
