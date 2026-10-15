"""Shared helpers for the A2 contract tests (owner T2). Builds on tests/helpers/h.py; no harness imports."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from helpers.h import REPO, assert_contract, run_h, tree_hash, validate_schema, write

CASES = REPO / "tests" / "fixtures" / "r1_4_cases"          # verbatim r1_4 case copies (owner T1)
SPEC_DIR = "specs"

# JSON Schema of artifacts/digest.json (02_scene.md 2.7), the subset helpers.h.validate_schema understands.
_S = ["string", "null"]
DIGEST_SCHEMA = {
    "type": "object", "required": ["schema", "kind", "path"],
    "properties": {
        "schema": {"const": "harness.digest/1"}, "kind": {"enum": ["scene", "resource", "project"]},
        "path": {"type": _S}, "uid": {"type": _S}, "format": {"type": ["integer", "null"]},
        "inherits": {"type": _S}, "editable": {"type": "array", "items": {"type": "string"}},
        "deps": {"type": "array", "items": {"type": "string"}}, "ext_uids": {"type": "object"},
        "nodes": {"type": "array", "items": {
            "type": "object", "required": ["path", "kind", "props", "groups", "unique", "vanished"],
            "properties": {"path": {"type": "string"}, "kind": {"enum": ["node", "instance", "override"]},
                           "type": {"type": _S}, "instance": {"type": _S}, "script": {"type": _S},
                           "groups": {"type": "array", "items": {"type": "string"}}, "unique": {"type": "boolean"},
                           "props": {"type": "object"}, "vanished": {"type": "boolean"}, "from": {"type": _S}}}},
        "connections": {"type": "array", "items": {
            "type": "object", "required": ["from", "signal", "to", "method", "flags"],
            "properties": {"from": {"type": "string"}, "signal": {"type": "string"}, "to": {"type": "string"},
                           "method": {"type": "string"}, "flags": {"type": "integer"}, "binds": {"type": "string"}}}},
        "resource": {"type": ["object", "null"]}, "project": {"type": ["object", "null"]}}}


def res(path: str) -> str:
    return path if path.startswith("res://") else "res://" + path


def digest(proj, target=None, *flags, cwd=None, check=True):
    args = ["digest", "--project", str(proj), *flags]
    if target is not None:
        args.insert(3, target)
    r = run_h(*args, cwd=cwd or Path(proj).parent)
    return assert_contract(r) if check else r


def gen(proj, *specs, flags=(), cwd=None, timeout=180):
    r = run_h("scene-gen", "--project", str(proj), *[str(s) for s in specs], *flags, cwd=cwd or Path(proj).parent,
              timeout=timeout)
    return assert_contract(r)


def edit(proj, scene, ops, flags=(), tmp=None, cwd=None, timeout=180):
    """ops: a list of op dicts, a full dict, or a Path to an ops file."""
    if isinstance(ops, Path):
        p = ops
    else:
        body = ops if isinstance(ops, dict) else {"ops": ops}
        tmp = Path(tmp or Path(proj).parent)
        p = tmp / "ops" / f"ops_{abs(hash(json.dumps(body, sort_keys=True))) % 10**8}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(body))
    r = run_h("scene-edit", "--project", str(proj), res(scene), str(p), *flags, cwd=cwd or Path(proj).parent,
              timeout=timeout)
    return assert_contract(r)


def write_spec(tmp, name: str, spec: dict) -> Path:
    p = Path(tmp) / "specs_in" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(spec, indent=1))
    return p


def spec_of(root: dict, save="res://gen/t.tscn", **kw) -> dict:
    d = {"save": save, "root": root}
    d.update(kw)
    return d


def node_paths(r) -> list:
    return [v.split(" ")[0] for v in r.stat_all("node")]


def node_line(r, path: str):
    for v in r.stat_all("node"):
        if v.split(" ")[0] == path:
            return v
    return None


def changes(r) -> list:
    return r.stat_all("change")


def digest_json(r) -> dict:
    return json.loads(r.artifact("digest.json").read_text())


def rule_findings(r, rule: str) -> list:
    return [f for f in r.all_findings() if f["rule"] == rule]


def strip_volatile(r) -> list:
    """stdout lines minus the log line and the `(1.2s)` timing in the verdict line."""
    out = []
    for i, ln in enumerate(r.lines):
        if ln.startswith("log: "):
            continue
        if i == 0:
            ln = re.sub(r"\s*\(\d+(\.\d+)?s\)\s*$", "", ln)
        out.append(ln)
    return out


def fs(proj, res_path: str) -> Path:
    assert res_path.startswith("res://")
    return Path(proj) / res_path[len("res://"):]


def read(proj, res_path: str) -> str:
    return fs(proj, res_path).read_text()


def snapshot(proj, *res_paths):
    return {p: fs(proj, p).read_bytes() for p in res_paths}


def assert_saved_none(r):
    assert r.stats.get("saved", "").startswith("none"), f"expected `saved: none`\n{r}"


def assert_rule(r, rule: str, *, startswith_slash: bool = False, loc_re: str | None = None):
    fs_ = rule_findings(r, rule)
    assert fs_, f"no [{rule}] finding in findings.jsonl\n{r}"
    if startswith_slash:
        assert any(f["message"].startswith("/") for f in fs_), f"[{rule}] message lacks a JSON pointer: {fs_}"
    if loc_re:
        assert any(re.search(loc_re, f["path"] or "-") for f in fs_), f"[{rule}] not located at /{loc_re}/: {fs_}"
    return fs_


def copy_case(proj, case: str, dest_rel: str) -> Path:
    """Copy an r1_4 case (tests/fixtures/r1_4_cases/<case>*.tscn) into the temp project."""
    src = next(CASES.glob(f"{case}_*.tscn"))
    dest = Path(proj) / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    return dest


def validate_digest_json(d: dict) -> list:
    return validate_schema(d, DIGEST_SCHEMA)


def n_node_decls(text: str) -> list:
    return re.findall(r'^\[node name="([^"]*)"', text, re.M)
