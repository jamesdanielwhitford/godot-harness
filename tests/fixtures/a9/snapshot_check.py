"""Tiny stdlib validator for sim_snapshot.schema.json (A9 spec 2.5) plus the two semantic rules of 2.5.
Loaded by path (importlib) from tests/unit/a9 and tests/gd/a9; there is no jsonschema in the venv. Owner: T9."""
import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("sim_snapshot.schema.json")


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _type_ok(v, t) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "string":
        return isinstance(v, str)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return True


def _validate(v, schema: dict, path: str, errs: list) -> None:
    t = schema.get("type")
    if t and not _type_ok(v, t):
        errs.append(f"{path}: expected {t}, got {type(v).__name__} {v!r}")
        return
    if "minimum" in schema and isinstance(v, (int, float)) and v < schema["minimum"]:
        errs.append(f"{path}: {v} < minimum {schema['minimum']}")
    if "pattern" in schema and isinstance(v, str) and not re.search(schema["pattern"], v):
        errs.append(f"{path}: {v!r} does not match {schema['pattern']}")
    if isinstance(v, dict):
        for k in schema.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing required '{k}'")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        pn = schema.get("propertyNames", {}).get("pattern")
        for k, val in v.items():
            if pn and not re.search(pn, k):
                errs.append(f"{path}: property name {k!r} does not match {pn}")
            if k in props:
                _validate(val, props[k], f"{path}.{k}", errs)
            elif addl is False:
                errs.append(f"{path}: unexpected property '{k}'")
            elif isinstance(addl, dict):
                _validate(val, addl, f"{path}.{k}", errs)


def validate(snapshot: dict) -> list:
    """Schema errors plus: things.t<id>.id == <id> and every id < next_id. Empty list = valid."""
    errs: list = []
    _validate(snapshot, load_schema(), "$", errs)
    if errs:
        return errs
    nxt = snapshot["next_id"]
    for key, th in snapshot["things"].items():
        n = int(key[1:])
        if th.get("id") != n:
            errs.append(f"$.things.{key}: id {th.get('id')!r} != {n}")
        if n >= nxt:
            errs.append(f"$.things.{key}: id {n} >= next_id {nxt}")
    return errs
