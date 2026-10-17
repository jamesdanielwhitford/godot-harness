"""Stdlib validator for scene specs (02_scene.md 2.4) and ops files (2.5). Pure, no Godot.

Every check returns a list of (json_pointer, message). JSON syntax errors carry a line number.
"""
from __future__ import annotations

import json
import re

SPEC_ID = "harness.scene-spec/1"
OPS_ID = "harness.scene-ops/1"

_SAVE_RE = re.compile(r'^res://(?!\.godot/|\.harness/)[^\s"]+\.tscn$')
_NAME_RE = re.compile(r'^[^./:@%"]+$')
_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INST_RE = re.compile(r"^res://.+\.tscn$")
_GD_RE = re.compile(r"^res://.+\.gd$")
_PROP_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_/:]*$")
_RES_RE = re.compile(r"^res://")

NODE_KEYS = {"name", "type", "instance", "parent", "script", "props", "groups", "unique_name", "index", "children"}
SPEC_KEYS = {"schema", "save", "root", "overrides", "extra_nodes", "connections"}
CONN_KEYS = {"from", "signal", "to", "method", "flags", "binds"}

# op -> (required, optional)
OPS = {
    "set_prop": ({"node", "props"}, set()),
    "add_node": ({"parent", "node"}, {"index"}),
    "add_instance": ({"parent", "name", "scene"}, {"props", "index"}),
    "remove_node": ({"node"}, set()),
    "reparent": ({"node", "parent"}, {"index"}),
    "rename": ({"node", "name"}, set()),
    "connect": ({"from", "signal", "to", "method"}, {"flags", "binds"}),
    "disconnect": ({"from", "signal", "to", "method"}, set()),
    "set_script": ({"node", "script"}, set()),
    "groups": ({"node"}, {"add", "remove"}),
}


def parse_json(text: str):
    """-> (obj, None) or (None, (line, message))."""
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, (e.lineno, f"invalid JSON: {e.msg} (column {e.colno})")
    except RecursionError:
        return None, (1, "invalid JSON: nesting too deep")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _str(v, ptr, errs, what, pattern=None, hint=None) -> bool:
    if not isinstance(v, str) or v == "":
        errs.append((ptr, f"{what} must be a non-empty string"))
        return False
    if pattern is not None and not pattern.match(v):
        errs.append((ptr, f"{what} {v!r} is not valid" + (f" ({hint})" if hint else "")))
        return False
    return True


def _value(v, ptr, errs):
    if v is None or isinstance(v, (bool, int, float, str, list)):
        return
    if not isinstance(v, dict):
        errs.append((ptr, "value must be a JSON scalar, array or a {\"$...\"} form"))
        return
    forms = [k for k in v if k in ("$var", "$res", "$node", "$new", "$layers")]
    if len(forms) != 1:
        errs.append((ptr, "object value must have exactly one of $var, $res, $node, $new, $layers"))
        return
    f = forms[0]
    extra = set(v) - {f} - ({"props"} if f == "$new" else set())
    if extra:
        errs.append((ptr, f"unknown key(s) {sorted(extra)} in {f} value"))
        return
    if f in ("$var", "$new") and not isinstance(v[f], str):
        errs.append((f"{ptr}/{f}", f"{f} must be a string"))
    elif f == "$res" and not (isinstance(v[f], str) and _RES_RE.match(v[f])):
        errs.append((f"{ptr}/$res", "$res must be a res:// path"))
    elif f == "$node" and not (isinstance(v[f], str) and v[f] != ""):
        errs.append((f"{ptr}/$node", "$node must be a non-empty node path"))
    elif f == "$layers":
        if not isinstance(v[f], list) or not all(isinstance(x, str) or _is_int(x) for x in v[f]):
            errs.append((f"{ptr}/$layers", "$layers must be an array of layer names or bit numbers"))
    if f == "$new" and "props" in v:
        _props(v["props"], f"{ptr}/props", errs)


def _props(p, ptr, errs):
    if not isinstance(p, dict):
        errs.append((ptr, "props must be an object"))
        return
    for k, v in p.items():
        if not _PROP_RE.match(k):
            errs.append((f"{ptr}/{k}", f"property name {k!r} is not valid"))
            continue
        _value(v, f"{ptr}/{k}", errs)


def _node(n, ptr, errs, instances: list, need_parent=False):
    if not isinstance(n, dict):
        errs.append((ptr, "node must be an object"))
        return
    for k in n:
        if k not in NODE_KEYS:
            errs.append((f"{ptr}/{k}", f"unknown key '{k}'"))
    if "name" not in n:
        errs.append((ptr, "missing required key 'name'"))
    else:
        _str(n["name"], f"{ptr}/name", errs, "name", _NAME_RE, "no . / : @ % or quotes")
    has_t, has_i = "type" in n, "instance" in n
    if has_t == has_i:
        errs.append((ptr, "exactly one of 'type' and 'instance' is required"))
    if has_t:
        _str(n["type"], f"{ptr}/type", errs, "type", _TYPE_RE)
    if has_i:
        if _str(n["instance"], f"{ptr}/instance", errs, "instance", _INST_RE, "res://....tscn"):
            instances.append((f"{ptr}/instance", n["instance"]))
    if need_parent:
        if "parent" not in n:
            errs.append((ptr, "missing required key 'parent'"))
        else:
            _str(n["parent"], f"{ptr}/parent", errs, "parent")
    elif "parent" in n:
        _str(n["parent"], f"{ptr}/parent", errs, "parent")
    if "script" in n:
        _str(n["script"], f"{ptr}/script", errs, "script", _GD_RE, "res://....gd")
    if "props" in n:
        _props(n["props"], f"{ptr}/props", errs)
    if "groups" in n:
        g = n["groups"]
        if not isinstance(g, list) or not all(isinstance(x, str) and x for x in g) or len(set(g)) != len(g):
            errs.append((f"{ptr}/groups", "groups must be an array of unique non-empty strings"))
    if "unique_name" in n and not isinstance(n["unique_name"], bool):
        errs.append((f"{ptr}/unique_name", "unique_name must be a boolean"))
    if "index" in n and not (_is_int(n["index"]) and n["index"] >= 0):
        errs.append((f"{ptr}/index", "index must be an integer >= 0"))
    if "children" in n:
        if not isinstance(n["children"], list):
            errs.append((f"{ptr}/children", "children must be an array"))
        else:
            for i, c in enumerate(n["children"]):
                _node(c, f"{ptr}/children/{i}", errs, instances)


def validate_spec(spec) -> list:
    errs: list = []
    if not isinstance(spec, dict):
        return [("", "spec must be a JSON object")]
    for k in spec:
        if k not in SPEC_KEYS:
            errs.append((f"/{k}", f"unknown key '{k}'"))
    if "schema" in spec and spec["schema"] != SPEC_ID:
        errs.append(("/schema", f"schema must be '{SPEC_ID}'"))
    for req in ("save", "root"):
        if req not in spec:
            errs.append(("", f"missing required key '{req}'"))
    if "save" in spec:
        s = spec["save"]
        if not isinstance(s, str) or not _SAVE_RE.match(s):
            errs.append(("/save", "save must be a res://....tscn path outside .godot/ and .harness/"))
    instances: list = []
    if "root" in spec:
        _node(spec["root"], "/root", errs, instances)
        if isinstance(spec["root"], dict):
            for k in ("parent", "index"):
                if k in spec["root"]:
                    errs.append((f"/root/{k}", f"root cannot have '{k}'"))
    if "overrides" in spec:
        o = spec["overrides"]
        if not isinstance(o, dict):
            errs.append(("/overrides", "overrides must be an object"))
        else:
            for k, v in o.items():
                _props(v, f"/overrides/{k}", errs)
    if "extra_nodes" in spec:
        x = spec["extra_nodes"]
        if not isinstance(x, list):
            errs.append(("/extra_nodes", "extra_nodes must be an array"))
        else:
            for i, n in enumerate(x):
                _node(n, f"/extra_nodes/{i}", errs, instances, need_parent=True)
    if "connections" in spec:
        c = spec["connections"]
        if not isinstance(c, list):
            errs.append(("/connections", "connections must be an array"))
        else:
            for i, cn in enumerate(c):
                _conn(cn, f"/connections/{i}", errs)
    if isinstance(spec.get("save"), str):
        for ptr, inst in instances:
            if inst == spec["save"]:
                errs.append((ptr, "a scene cannot instance itself (instance equals save)"))
    return errs


def _conn(c, ptr, errs):
    if not isinstance(c, dict):
        errs.append((ptr, "connection must be an object"))
        return
    for k in c:
        if k not in CONN_KEYS:
            errs.append((f"{ptr}/{k}", f"unknown key '{k}'"))
    for k in ("from", "signal", "to", "method"):
        if k not in c:
            errs.append((ptr, f"missing required key '{k}'"))
        elif not isinstance(c[k], str) or not c[k]:
            errs.append((f"{ptr}/{k}", f"{k} must be a non-empty string"))
    if "flags" in c and not (_is_int(c["flags"]) and c["flags"] >= 0):
        errs.append((f"{ptr}/flags", "flags must be an integer >= 0"))
    if "binds" in c and not isinstance(c["binds"], list):
        errs.append((f"{ptr}/binds", "binds must be an array"))


def validate_ops(doc) -> list:
    errs: list = []
    if not isinstance(doc, dict):
        return [("", "ops file must be a JSON object")]
    for k in doc:
        if k not in ("schema", "ops"):
            errs.append((f"/{k}", f"unknown key '{k}'"))
    if "schema" in doc and doc["schema"] != OPS_ID:
        errs.append(("/schema", f"schema must be '{OPS_ID}'"))
    ops = doc.get("ops")
    if not isinstance(ops, list):
        errs.append(("/ops", "ops must be an array"))
        return errs
    for i, op in enumerate(ops):
        ptr = f"/ops/{i}"
        if not isinstance(op, dict):
            errs.append((ptr, "op must be an object"))
            continue
        name = op.get("op")
        if name not in OPS:
            errs.append((f"{ptr}/op", f"unknown op {name!r} (one of {', '.join(sorted(OPS))})"))
            continue
        req, opt = OPS[name]
        for k in op:
            if k != "op" and k not in req and k not in opt:
                errs.append((f"{ptr}/{k}", f"unknown key '{k}' for op '{name}'"))
        for k in sorted(req):
            if k not in op:
                errs.append((ptr, f"op '{name}' is missing required key '{k}'"))
        for k in ("node", "parent", "from", "to"):
            if name == "add_node" and k == "node":
                continue
            if k in op and not (isinstance(op[k], str) and op[k]):
                errs.append((f"{ptr}/{k}", f"{k} must be a non-empty node path"))
        for k in ("signal", "method"):
            if k in op and not (isinstance(op[k], str) and op[k]):
                errs.append((f"{ptr}/{k}", f"{k} must be a non-empty string"))
        if "name" in op:
            _str(op["name"], f"{ptr}/name", errs, "name", _NAME_RE, "no . / : @ % or quotes")
        if "scene" in op:
            _str(op["scene"], f"{ptr}/scene", errs, "scene", _INST_RE, "res://....tscn")
        if "index" in op and not (_is_int(op["index"]) and op["index"] >= 0):
            errs.append((f"{ptr}/index", "index must be an integer >= 0"))
        if "props" in op:
            _props(op["props"], f"{ptr}/props", errs)
        if "flags" in op and not (_is_int(op["flags"]) and op["flags"] >= 0):
            errs.append((f"{ptr}/flags", "flags must be an integer >= 0"))
        if "binds" in op and not isinstance(op["binds"], list):
            errs.append((f"{ptr}/binds", "binds must be an array"))
        if name == "set_script" and "script" in op and op["script"] is not None:
            _str(op["script"], f"{ptr}/script", errs, "script", _GD_RE, "res://....gd or null")
        if name == "add_node" and "node" in op:
            inst: list = []
            _node(op["node"], f"{ptr}/node", errs, inst)
        if name == "groups":
            for k in ("add", "remove"):
                if k in op and not (isinstance(op[k], list) and all(isinstance(x, str) and x for x in op[k])):
                    errs.append((f"{ptr}/{k}", f"{k} must be an array of non-empty strings"))
    return errs
