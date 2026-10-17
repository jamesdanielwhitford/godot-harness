"""Pure digest model (A2): text rendering, change lines, the expected-effects model and the comparison.

Public names (REVIEW R-01): render, diff, expected, compare. Stdlib only, no side effects.

A digest is the dict of 02_scene.md 2.7. An effect is one of
  {"e":"add","path","kind","type","instance","script","groups","unique","props","prevs"}
  {"e":"remove","path"}                    {"e":"move","from","to","prevs"}   (prevs None = keep position)
  {"e":"set","path","prop","value","is_default"}
  {"e":"conn+"|"conn-","c":{from,signal,to,method,flags,binds?}}
  {"e":"group+"|"group-","path","group"}   {"e":"editable+","path"}
  {"e":"script","path","script","dropped":[...]}
"""
from __future__ import annotations

import copy
import re

VALUE_CUT = 60


# ---- text helpers --------------------------------------------------------------------------------------------
def cut(s: str, n: int = VALUE_CUT) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 3] + "..."


def kind_text(n: dict) -> str:
    if n.get("kind") == "instance":
        return f"<{n.get('instance')}>"
    if n.get("kind") == "override":
        return "(override)"
    return n.get("type") or "Node"


def node_line(n: dict) -> str:
    parts = [n["path"], kind_text(n)]
    if n.get("unique"):
        parts.append("%unique")
    if n.get("groups"):
        parts.append("groups=" + ",".join(n["groups"]))
    if n.get("script"):
        parts.append("script=" + n["script"])
    for k, v in n.get("props", {}).items():
        parts.append(f"{k}={cut(v)}")
    if n.get("from"):
        parts.append(f"(from {n['from']})")
    if n.get("vanished"):
        parts.append("!vanished")
    return " ".join(parts)


def conn_text(c: dict, flags_always: bool = False) -> str:
    f = "" if c["from"] == "." else c["from"]
    t = "" if c["to"] == "." else c["to"]
    s = f"{f}.{c['signal']} -> {t}.{c['method']}"
    if flags_always or c.get("flags", 2) != 2:
        s += f" flags={c.get('flags', 2)}"
    if c.get("binds"):
        s += f" binds={c['binds']}"
    return s


def conn_key(c: dict) -> tuple:
    return (c["from"], c["signal"], c["to"], c["method"], int(c.get("flags", 2)), c.get("binds", "") or "")


def render(d: dict, node: str | None = None) -> list:
    """Digest -> [(key, value)] stat lines in contract order. `node`: subtree filter (root-relative path)."""
    out: list = []
    if d["kind"] == "scene":
        uid = d.get("uid") or "none"
        out.append(("scene", f"{d['path']} format={d.get('format') if d.get('format') is not None else '?'} uid={uid}"))
        if d.get("inherits"):
            out.append(("inherits", d["inherits"]))
        sel = d["nodes"]
        if node is not None:
            sel = [n for n in sel if n["path"] == node or n["path"].startswith(node + "/")]
        for n in sel:
            out.append(("node", node_line(n)))
        inside = {n["path"] for n in sel}
        for c in sorted(d["connections"], key=conn_key):
            if node is None or (c["from"] in inside and c["to"] in inside):
                out.append(("conn", conn_text(c)))
        ed = [e for e in d.get("editable", []) if node is None or e in inside]
        if ed:
            out.append(("editable", ", ".join(ed)))
        if d.get("deps"):
            out.append(("deps", ", ".join(d["deps"])))
    elif d["kind"] == "resource":
        r = d["resource"]
        s = f"{d['path']} type={r.get('type')}"
        if r.get("script_class"):
            s += f" script_class={r['script_class']}"
        out.append(("resource", s))
        for k, v in r.get("props", {}).items():
            out.append(("prop", f"{k}={cut(v)}"))
        if d.get("deps"):
            out.append(("deps", ", ".join(d["deps"])))
    return out


# ---- text parsing (header facts the engine does not give) --------------------------------------------------------
_HDR = re.compile(r"^\[gd_(scene|resource)\b([^\]]*)\]", re.M)
_EXT = re.compile(r"^\[ext_resource\b([^\]]*)\]", re.M)
_ATTR = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s\]]+)')
_EDIT = re.compile(r'^\[editable\s+path="([^"]*)"\]', re.M)


def _attrs(s: str) -> dict:
    return {k: (v[1:-1] if v.startswith('"') else v) for k, v in _ATTR.findall(s)}


def parse_text(text: str) -> dict:
    """-> {uid, format, ext_uids {path: uid}, deps [paths], editable [paths]} from a .tscn/.tres source."""
    uid, fmt = None, None
    m = _HDR.search(text)
    if m:
        a = _attrs(m.group(2))
        uid = a.get("uid")
        fmt = int(a["format"]) if a.get("format", "").isdigit() else None
    ext_uids: dict = {}
    deps: set = set()
    for em in _EXT.finditer(text):
        a = _attrs(em.group(1))
        if a.get("path"):
            deps.add(a["path"])
            if a.get("uid"):
                ext_uids[a["path"]] = a["uid"]
    return {"uid": uid, "format": fmt, "ext_uids": dict(sorted(ext_uids.items())), "deps": sorted(deps),
            "editable": _EDIT.findall(text)}


# ---- diff -----------------------------------------------------------------------------------------------------
def diff(a: dict, b: dict) -> list:
    """Change lines (`+ path kind`, `- path`, `~ path prop: old -> new`, ...) from digest a to digest b; [] when equal."""
    out: list = []
    na = {n["path"]: n for n in a.get("nodes", [])}
    nb = {n["path"]: n for n in b.get("nodes", [])}
    for p, n in nb.items():
        if p not in na:
            out.append(f"+ {p} {kind_text(n)}")
    for p in na:
        if p not in nb:
            out.append(f"- {p}")
    for p, n in nb.items():
        o = na.get(p)
        if o is None:
            continue
        if kind_text(o) != kind_text(n):
            out.append(f"~ {p} kind: {kind_text(o)} -> {kind_text(n)}")
        if (o.get("script") or None) != (n.get("script") or None):
            out.append(f"~ {p} script: {o.get('script') or 'none'} -> {n.get('script') or 'none'}")
        for k, v in n.get("props", {}).items():
            ov = o.get("props", {}).get(k)
            if ov != v:
                out.append(f"~ {p} {k}: {cut(ov) if ov is not None else '(unset)'} -> {cut(v)}")
        for k in o.get("props", {}):
            if k not in n.get("props", {}):
                out.append(f"~ {p} {k}: {cut(o['props'][k])} -> (unset)")
        for g in n.get("groups", []):
            if g not in o.get("groups", []):
                out.append(f"+ group {p} {g}")
        for g in o.get("groups", []):
            if g not in n.get("groups", []):
                out.append(f"- group {p} {g}")
        if bool(o.get("unique")) != bool(n.get("unique")):
            out.append(f"~ {p} unique: {bool(o.get('unique'))} -> {bool(n.get('unique'))}")
    ca = {conn_key(c): c for c in a.get("connections", [])}
    cb = {conn_key(c): c for c in b.get("connections", [])}
    for k, c in cb.items():
        if k not in ca:
            out.append(f"+ conn {conn_text(c)}")
    for k, c in ca.items():
        if k not in cb:
            out.append(f"- conn {conn_text(c)}")
    for e in b.get("editable", []):
        if e not in a.get("editable", []):
            out.append(f"+ editable {e}")
    for e in a.get("editable", []):
        if e not in b.get("editable", []):
            out.append(f"- editable {e}")
    return out


# ---- expected-effects model -----------------------------------------------------------------------------------
def parent_of(p: str) -> str:
    return "." if "/" not in p else p.rsplit("/", 1)[0]


def name_of(p: str) -> str:
    return p.rsplit("/", 1)[-1]


def _under(p: str, base: str) -> bool:
    return p == base or p.startswith(base + "/")


def _remap(p: str, old: str, new: str) -> str:
    if p == old:
        return new
    if p.startswith(old + "/"):
        return new + p[len(old):]
    return p


def _blank_override(n: dict) -> bool:
    return n.get("kind") == "override" and not n.get("props") and not n.get("groups") and not n.get("script")


def normalize(d: dict) -> dict:
    """Drop empty override entries (the engine does not write them)."""
    d["nodes"] = [n for n in d.get("nodes", []) if not _blank_override(n)]
    return d


def _insert_pos(nodes: list, path: str, prevs) -> int:
    par = parent_of(path)
    sib = [i for i, n in enumerate(nodes) if parent_of(n["path"]) == par and n["path"] != path]
    if prevs:
        for pv in prevs:
            pp = path[: len(path) - len(name_of(path))] + pv if par != "." else pv
            for i in sib:
                if nodes[i]["path"] == pp:
                    j = i + 1
                    while j < len(nodes) and _under(nodes[j]["path"], pp):
                        j += 1
                    return j
    if prevs is not None and sib:
        return sib[0]
    return len(nodes)


def expected(before: dict, effects: list) -> dict:
    """Digest after applying `effects` to `before` (a deep copy; `before` is not modified)."""
    d = copy.deepcopy(before)
    nodes = d.setdefault("nodes", [])
    conns = d.setdefault("connections", [])
    ed = d.setdefault("editable", [])
    for fx in effects:
        e = fx.get("e")
        if e == "add":
            n = {"path": fx["path"], "kind": fx.get("kind", "node"), "type": fx.get("type"),
                 "instance": fx.get("instance"), "script": fx.get("script"), "groups": list(fx.get("groups", [])),
                 "unique": bool(fx.get("unique")), "props": dict(fx.get("props", {})), "vanished": False, "from": None}
            nodes.insert(_insert_pos(nodes, fx["path"], fx.get("prevs")), n)
        elif e == "remove":
            nodes[:] = [n for n in nodes if not _under(n["path"], fx["path"])]
            conns[:] = [c for c in conns if not _under(c["from"], fx["path"]) and not _under(c["to"], fx["path"])]
            ed[:] = [x for x in ed if not _under(x, fx["path"])]
        elif e == "move":
            old, new = fx["from"], fx["to"]
            moved = [n for n in nodes if _under(n["path"], old)]
            if fx.get("prevs") is not None:
                nodes[:] = [n for n in nodes if not _under(n["path"], old)]
                for n in moved:
                    n["path"] = _remap(n["path"], old, new)
                pos = _insert_pos(nodes, new, fx["prevs"])
                nodes[pos:pos] = moved
            else:
                for n in moved:
                    n["path"] = _remap(n["path"], old, new)
            for n in nodes:
                for k, v in list(n["props"].items()):
                    if isinstance(v, str) and v.startswith("@") and _under(v[1:], old):
                        n["props"][k] = "@" + _remap(v[1:], old, new)
            for c in conns:
                c["from"] = _remap(c["from"], old, new)
                c["to"] = _remap(c["to"], old, new)
            ed[:] = [_remap(x, old, new) for x in ed]
        elif e == "set":
            n = next((x for x in nodes if x["path"] == fx["path"]), None)
            if n is None:
                n = {"path": fx["path"], "kind": "override", "type": None, "instance": None, "script": None,
                     "groups": [], "unique": False, "props": {}, "vanished": False, "from": None}
                nodes.append(n)
            if fx.get("is_default"):
                n["props"].pop(fx["prop"], None)
            else:
                n["props"][fx["prop"]] = fx["value"]
        elif e == "conn+":
            if conn_key(fx["c"]) not in {conn_key(c) for c in conns}:
                conns.append(dict(fx["c"]))
        elif e == "conn-":
            k = conn_key(fx["c"])
            conns[:] = [c for c in conns if conn_key(c) != k]
        elif e == "group+":
            n = next((x for x in nodes if x["path"] == fx["path"]), None)
            if n is None:
                n = {"path": fx["path"], "kind": "override", "type": None, "instance": None, "script": None,
                     "groups": [], "unique": False, "props": {}, "vanished": False, "from": None}
                nodes.append(n)
            if fx["group"] not in n["groups"]:
                n["groups"].append(fx["group"])
        elif e == "group-":
            for n in nodes:
                if n["path"] == fx["path"] and fx["group"] in n["groups"]:
                    n["groups"].remove(fx["group"])
        elif e == "editable+":
            if fx["path"] not in ed:
                ed.append(fx["path"])
        elif e == "script":
            for n in nodes:
                if n["path"] == fx["path"]:
                    n["script"] = fx.get("script")
                    for k in fx.get("dropped", []):
                        n["props"].pop(k, None)
    return normalize(d)


def _f(rule: str, msg: str) -> dict:
    return {"path": None, "line": None, "rule": rule, "severity": "error", "message": msg, "hint": None}


def compare(exp: dict, after: dict) -> list:
    """Findings (dicts with `rule`) for what differs between the expected and the actual digest."""
    out: list = []
    exp = normalize(copy.deepcopy(exp))
    after = normalize(copy.deepcopy(after))
    ne = {n["path"]: n for n in exp.get("nodes", [])}
    na = {n["path"]: n for n in after.get("nodes", [])}
    for p in ne:
        if p not in na:
            out.append(_f("scene.lossy-save", f"node '{p}' is missing from the saved scene"))
    for p in na:
        if p not in ne:
            out.append(_f("scene.unexpected-change", f"node '{p}' appeared in the saved scene"))
    for p, e in ne.items():
        a = na.get(p)
        if a is None:
            continue
        if e.get("kind") != a.get("kind") or (e.get("type") or None) != (a.get("type") or None) \
                or (e.get("instance") or None) != (a.get("instance") or None):
            out.append(_f("scene.unexpected-change",
                          f"node '{p}' changed from {kind_text(e)} to {kind_text(a)}"))
        if (e.get("script") or None) != (a.get("script") or None):
            rule = "scene.lossy-save" if e.get("script") and not a.get("script") else "scene.unexpected-change"
            out.append(_f(rule, f"node '{p}' script is {a.get('script') or 'none'}, expected {e.get('script') or 'none'}"))
        for k, v in e.get("props", {}).items():
            if k not in a.get("props", {}):
                out.append(_f("scene.lossy-save", f"node '{p}' lost property '{k}' (expected {cut(v)})"))
            elif a["props"][k] != v:
                out.append(_f("scene.unexpected-change",
                              f"node '{p}' property '{k}' is {cut(a['props'][k])}, expected {cut(v)}"))
        for k in a.get("props", {}):
            if k not in e.get("props", {}):
                out.append(_f("scene.unexpected-change", f"node '{p}' gained property '{k}' = {cut(a['props'][k])}"))
        eg, ag = set(e.get("groups", [])), set(a.get("groups", []))
        for g in sorted(eg - ag):
            out.append(_f("scene.lossy-save", f"node '{p}' lost group '{g}'"))
        for g in sorted(ag - eg):
            out.append(_f("scene.unexpected-change", f"node '{p}' gained group '{g}'"))
        if bool(e.get("unique")) != bool(a.get("unique")):
            out.append(_f("scene.unexpected-change", f"node '{p}' unique name flag changed"))
    ce = {conn_key(c) for c in exp.get("connections", [])}
    ca = {conn_key(c) for c in after.get("connections", [])}
    for k in sorted(ce - ca):
        out.append(_f("scene.lossy-save", "connection " + conn_text({"from": k[0], "signal": k[1], "to": k[2],
                                                                    "method": k[3], "flags": k[4]}) + " is missing"))
    for k in sorted(ca - ce):
        out.append(_f("scene.unexpected-change", "connection " + conn_text({"from": k[0], "signal": k[1], "to": k[2],
                                                                           "method": k[3], "flags": k[4]}) + " appeared"))
    for x in exp.get("editable", []):
        if x not in after.get("editable", []):
            out.append(_f("scene.lossy-save", f"[editable path=\"{x}\"] is missing"))
    for x in after.get("editable", []):
        if x not in exp.get("editable", []):
            out.append(_f("scene.unexpected-change", f"[editable path=\"{x}\"] appeared"))
    common = set(ne) & set(na)
    groups_e: dict = {}
    groups_a: dict = {}
    for n in exp.get("nodes", []):
        if n["path"] in common:
            groups_e.setdefault(parent_of(n["path"]), []).append(n["path"])
    for n in after.get("nodes", []):
        if n["path"] in common:
            groups_a.setdefault(parent_of(n["path"]), []).append(n["path"])
    for par, order in groups_e.items():
        if order != groups_a.get(par, []):
            out.append(_f("scene.unexpected-change", f"children of '{par}' are in a different order: "
                                                     f"{[name_of(x) for x in groups_a.get(par, [])]} instead of "
                                                     f"{[name_of(x) for x in order]}"))
    return out


# ---- generator verification (scene-gen step 5) ------------------------------------------------------------------
def spec_nodes(spec: dict) -> dict:
    """path -> expected entry facts for every node the spec declares."""
    out: dict = {}
    root = spec["root"]

    def walk(n: dict, path: str, is_root: bool):
        out[path] = {"kind": "instance" if n.get("instance") else "node", "type": n.get("type"),
                     "instance": n.get("instance"), "script": n.get("script"), "groups": set(n.get("groups", [])),
                     "unique": bool(n.get("unique_name"))}
        for c in n.get("children", []):
            walk(c, c["name"] if path == "." else f"{path}/{c['name']}", False)

    walk(root, ".", True)
    for x in spec.get("extra_nodes", []):
        par = x["parent"]
        par = "." if par in (".", "") else par
        walk(x, x["name"] if par == "." else f"{par}/{x['name']}", False)
    return out


def verify_gen(spec: dict, gen: dict, after: dict) -> list:
    """Findings (scene.lossy-save) for what the saved file lacks compared with the spec and the runner's records."""
    out: list = []
    exp = spec_nodes(spec)
    got = {n["path"]: n for n in after.get("nodes", [])}
    sets = [s for s in gen.get("sets", []) if not s.get("is_default")]
    override_paths = {s["path"] for s in sets if s["path"] not in exp}
    for p, e in exp.items():
        n = got.get(p)
        if n is None:
            out.append(_f("scene.lossy-save", f"node '{p}' is missing from the saved scene"))
            continue
        if n.get("kind") != e["kind"] or (e["kind"] == "node" and (n.get("type") or None) != e["type"]) \
                or (e["kind"] == "instance" and (n.get("instance") or None) != e["instance"]):
            out.append(_f("scene.lossy-save", f"node '{p}' was saved as {kind_text(n)}, expected "
                                             f"{e['type'] if e['kind'] == 'node' else '<' + str(e['instance']) + '>'}"))
        if (n.get("script") or None) != (e["script"] or None):
            out.append(_f("scene.lossy-save", f"node '{p}' script is {n.get('script') or 'none'}, expected "
                                             f"{e['script'] or 'none'}"))
        if set(n.get("groups", [])) != e["groups"]:
            out.append(_f("scene.lossy-save", f"node '{p}' groups are {sorted(n.get('groups', []))}, expected "
                                             f"{sorted(e['groups'])}"))
        if bool(n.get("unique")) != e["unique"]:
            out.append(_f("scene.lossy-save", f"node '{p}' unique name flag is {bool(n.get('unique'))}"))
    for p, n in got.items():
        if p not in exp and p not in override_paths and not n.get("vanished"):
            out.append(_f("scene.lossy-save", f"unexpected node '{p}' in the saved scene"))
    for s in sets:
        n = got.get(s["path"])
        if n is None:
            if s["path"] in exp:
                continue
            out.append(_f("scene.lossy-save", f"override of '{s['path']}' is missing from the saved scene"))
            continue
        have = n.get("props", {}).get(s["prop"])
        if have is None:
            out.append(_f("scene.lossy-save", f"node '{s['path']}' lost property '{s['prop']}' (expected {cut(s['value'])})"))
        elif have != s["value"]:
            out.append(_f("scene.lossy-save", f"node '{s['path']}' property '{s['prop']}' is {cut(have)}, "
                                             f"expected {cut(s['value'])}"))
    have_c = {conn_key(c) for c in after.get("connections", [])}
    for c in spec.get("connections", []):
        k = (("." if c["from"] in ("", ".") else c["from"]), c["signal"], ("." if c["to"] in ("", ".") else c["to"]),
             c["method"], int(c.get("flags", 0)) | 2, "")
        if not any(h[:5] == k[:5] for h in have_c):
            out.append(_f("scene.lossy-save", f"connection {c['from']}.{c['signal']} -> {c['to']}.{c['method']} "
                                             f"is missing from the saved scene"))
    need = set()
    for p in list(override_paths) + [x["parent"] for x in spec.get("extra_nodes", [])] + list(spec.get("overrides", {})):
        if p in (".", ""):
            continue
        parts = p.split("/")
        for i in range(1, len(parts)):
            pre = "/".join(parts[:i])
            if exp.get(pre, {}).get("kind") == "instance":
                need.add(pre)
    for p in sorted(need):
        if p not in after.get("editable", []):
            out.append(_f("scene.lossy-save", f"[editable path=\"{p}\"] is missing from the saved scene"))
    live = gen.get("live_nodes")
    inst = after.get("_instantiated")
    if live is not None and inst is not None and live != inst:
        out.append(_f("scene.lossy-save", f"the saved scene instantiates {inst} nodes, the generator built {live}"))
    return out


# ---- change lines from effects (scene-edit output) -----------------------------------------------------------------
def change_lines(effects: list) -> list:
    out: list = []
    for fx in effects:
        e = fx.get("e")
        if e == "add":
            k = f"<{fx.get('instance')}>" if fx.get("kind") == "instance" else (fx.get("type") or "Node")
            out.append(f"+ {fx['path']} {k}")
        elif e == "remove":
            out.append(f"- {fx['path']}")
        elif e == "move":
            if fx["from"] != fx["to"]:
                out.append(f"> {fx['from']} -> {fx['to']}")
            else:
                out.append(f"> {fx['from']} (moved)")
        elif e == "set":
            old = fx.get("old")
            out.append(f"~ {fx['path']} {fx['prop']}: {cut(old) if old is not None else '(unset)'} -> {cut(fx['value'])}")
        elif e == "conn+":
            out.append(f"+ conn {conn_text(fx['c'])}")
        elif e == "conn-":
            out.append(f"- conn {conn_text(fx['c'])}")
        elif e == "group+":
            out.append(f"+ group {fx['path']} {fx['group']}")
        elif e == "group-":
            out.append(f"- group {fx['path']} {fx['group']}")
        elif e == "editable+":
            out.append(f"+ editable {fx['path']}")
        elif e == "script":
            out.append(f"~ {fx['path']} script: {fx.get('old') or 'none'} -> {fx.get('script') or 'none'}")
    return out


def stale_names(effects: list) -> list:
    """[(old name, what happened)] for renames and removals (scene.stale-ref candidates)."""
    out: list = []
    for fx in effects:
        if fx.get("e") == "move" and name_of(fx["from"]) != name_of(fx["to"]):
            out.append((name_of(fx["from"]), f"renamed to '{name_of(fx['to'])}'"))
        elif fx.get("e") == "remove":
            out.append((name_of(fx["path"]), "removed"))
    return out


def stale_pattern(name: str):
    n = re.escape(name)
    return re.compile(r'[$%]"?(?:[\w./]*/)?' + n + r'\b|["\']' + n + r'["\']')
