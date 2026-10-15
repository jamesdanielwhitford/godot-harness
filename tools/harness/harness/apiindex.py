"""Godot API index for `h api` (A1 2.4, 3.5): build from extension_api.json + @GDScript.xml, load, look up, suggest."""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA = "harness.api-index/1"
_DATA = Path(__file__).resolve().parent / "data" / "renames_3to4.json"

_BB_REF = re.compile(r"\[(?:param|member|method|signal|constant|enum|annotation|theme_item|constructor|operator)\s+([^\]]+)\]")
_BB_TAG = re.compile(r"\[/?(?:b|i|u|s|code|codeblock|codeblocks|gdscript|csharp|center|kbd|br|lb|rb|indent|color[^\]]*|font[^\]]*|"
                     r"url[^\]]*|img[^\]]*|table[^\]]*|cell[^\]]*|ul|ol|li)\]")
_BB_CLASS = re.compile(r"\[([A-Za-z_@][A-Za-z0-9_.@]*)\]")


def clean_doc(text: str) -> str:
    """First sentence of a Godot description, BBCode removed, <= 160 chars."""
    if not text:
        return ""
    t = text.strip().splitlines()[0] if text.strip() else ""
    t = _BB_REF.sub(r"\1", t)
    t = _BB_TAG.sub("", t)
    t = _BB_CLASS.sub(r"\1", t)
    t = " ".join(t.split())
    m = re.search(r"[.!?](\s|$)", t)
    if m:
        t = t[: m.start() + 1]
    t = t.lstrip("[")
    return t if len(t) <= 160 else t[:157] + "..."


def _type(t) -> str:
    if not t:
        return "Variant"
    if t.startswith("typedarray::"):
        return f"Array[{_type(t[len('typedarray::'):])}]"
    for p in ("enum::", "bitfield::"):
        if t.startswith(p):
            return t[len(p):]
    return t


def _args(args, vararg=False) -> str:
    parts = []
    for a in args or []:
        s = f"{a['name']}: {_type(a.get('type'))}"
        if "default_value" in a:
            s += f" = {a['default_value']}"
        parts.append(s)
    if vararg:
        parts.append("...")
    return ", ".join(parts)


def _ret(m) -> str:
    rv = m.get("return_value")
    if rv:
        return _type(rv.get("type"))
    if m.get("return_type"):
        return _type(m["return_type"])
    return "void"


def _method_sig(m) -> str:
    return (f"{'static ' if m.get('is_static') else ''}func {m['name']}({_args(m.get('arguments'), m.get('is_vararg'))})"
            f" -> {_ret(m)}")


def build(api_json: Path, gdscript_xml: Path | None, version: str) -> dict:
    d = json.loads(Path(api_json).read_text())
    entries: dict = {}
    classes: dict = {}

    def add(key, kind, sig, doc, in_=None):
        e = {"k": kind, "sig": sig, "d": clean_doc(doc)}
        if in_:
            e["in"] = in_
        entries[key] = e

    def add_class(c, builtin: bool):
        name = c["name"]
        inh = c.get("inherits", "")
        names = []
        counts = [0, 0, 0]
        sig = f"class {name}" + (f" extends {inh}" if inh else "")
        add(name, "builtin" if builtin else "class", sig, c.get("brief_description") or c.get("description", ""))
        for m in c.get("methods", []):
            add(f"{name}.{m['name']}", "method", _method_sig(m), m.get("description", ""), name)
            names.append(m["name"])
            counts[0] += 1
        for p in c.get("properties", []) or c.get("members", []):
            add(f"{name}.{p['name']}", "property", f"var {p['name']}: {_type(p.get('type'))}", p.get("description", ""),
                name)
            names.append(p["name"])
            counts[1] += 1
        for s in c.get("signals", []):
            add(f"{name}.{s['name']}", "signal", f"signal {s['name']}({_args(s.get('arguments'))})",
                s.get("description", ""), name)
            names.append(s["name"])
            counts[2] += 1
        for k in c.get("constants", []):
            add(f"{name}.{k['name']}", "constant", f"const {k['name']} = {k.get('value')}", k.get("description", ""),
                name)
            names.append(k["name"])
        for en in c.get("enums", []):
            add(f"{name}.{en['name']}", "constant", f"enum {en['name']}", "", name)
            names.append(en["name"])
            for v in en.get("values", []):
                add(f"{name}.{v['name']}", "constant", f"const {v['name']} = {v.get('value')}", v.get("description", ""),
                    name)
                names.append(v["name"])
        classes[name] = {"inh": inh, "n": counts, "names": sorted(set(names))}

    for c in d.get("classes", []):
        add_class(c, False)
    for c in d.get("builtin_classes", []):
        add_class(c, True)
    gnames = []
    for u in d.get("utility_functions", []):
        add(f"@GlobalScope.{u['name']}", "function", _method_sig(u), u.get("description", ""), "@GlobalScope")
        gnames.append(u["name"])
    for en in d.get("global_enums", []):
        for v in en.get("values", []):
            add(f"@GlobalScope.{v['name']}", "constant", f"const {v['name']} = {v.get('value')}", v.get("description", ""),
                "@GlobalScope")
            gnames.append(v["name"])
    for k in d.get("global_constants", []):
        add(f"@GlobalScope.{k['name']}", "constant", f"const {k['name']} = {k.get('value')}", k.get("description", ""),
            "@GlobalScope")
        gnames.append(k["name"])
    classes["@GlobalScope"] = {"inh": "", "n": [len(d.get("utility_functions", [])), 0, 0], "names": sorted(set(gnames))}

    gnames = []
    if gdscript_xml and Path(gdscript_xml).is_file():
        root = ET.parse(gdscript_xml).getroot()

        def xml_sig(el, prefix):
            ret = el.find("return")
            params = []
            for p in el.findall("param"):
                s = f"{p.get('name')}: {p.get('type') or 'Variant'}"
                if p.get("default") is not None:
                    s += f" = {p.get('default')}"
                params.append(s)
            if "vararg" in (el.get("qualifiers") or ""):
                params.append("...")
            r = f" -> {ret.get('type')}" if ret is not None and prefix == "func" else ""
            return f"{prefix} {el.get('name')}({', '.join(params)}){r}"

        for m in root.findall("./methods/method"):
            add(f"@GDScript.{m.get('name')}", "function", xml_sig(m, "func"), (m.findtext("description") or ""),
                "@GDScript")
            gnames.append(m.get("name"))
        for a in root.findall("./annotations/annotation"):
            add(f"@GDScript.{a.get('name')}", "annotation", xml_sig(a, "annotation"), (a.findtext("description") or ""),
                "@GDScript")
            gnames.append(a.get("name"))
        for k in root.findall("./constants/constant"):
            add(f"@GDScript.{k.get('name')}", "constant", f"const {k.get('name')} = {k.get('value')}",
                (k.text or ""), "@GDScript")
            gnames.append(k.get("name"))
    classes["@GDScript"] = {"inh": "", "n": [len(gnames), 0, 0], "names": sorted(set(gnames))}
    return {"schema": SCHEMA, "godot_version": version, "count": len(entries), "classes": classes,
            "entries": entries}


def save(index: dict, path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(index, separators=(",", ":")))
    os.replace(tmp, path)


def load(path: Path, version: str | None = None) -> dict | None:
    try:
        idx = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if idx.get("schema") != SCHEMA or (version and idx.get("godot_version") != version):
        return None
    return idx


# ---- lookup -------------------------------------------------------------------------------------------------------
def chain(idx: dict, cls: str) -> list:
    out, seen = [], set()
    while cls and cls not in seen and cls in idx["classes"]:
        out.append(cls)
        seen.add(cls)
        cls = idx["classes"][cls]["inh"]
    return out


def _bare_keys(q: str) -> list:
    return [q, f"@GDScript.{q}", f"@GlobalScope.{q}"]


def lookup(idx: dict, q: str):
    """-> (key, entry) or None. For inherited members entry['in'] names the defining class."""
    ents = idx["entries"]
    if "." in q and not q.startswith(("@GDScript.", "@GlobalScope.")):
        cls, member = q.split(".", 1)
        for c in chain(idx, cls):
            key = f"{c}.{member}"
            if key in ents:
                return key, ents[key]
        for c in chain(idx, cls) or _ci_chain(idx, cls):
            for n in idx["classes"][c]["names"]:
                if n.lower() == member.lower():
                    return f"{c}.{n}", ents[f"{c}.{n}"]
        return None
    for k in _bare_keys(q):
        if k in ents:
            return k, ents[k]
    low = q.lower()
    for k in ents:
        if "." in k and not k.startswith("@"):
            continue
        base = k.split(".", 1)[1] if k.startswith(("@GDScript.", "@GlobalScope.")) else k
        if base.lower() == low:
            return k, ents[k]
    return None


def _ci_chain(idx: dict, cls: str) -> list:
    for name in idx["classes"]:
        if name.lower() == cls.lower():
            return chain(idx, name)
    return []


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def suggest(idx: dict, q: str, n: int = 3) -> list:
    limit = max(2, len(q) // 4)
    ql = q.lower()
    scored = []
    if "." in q:
        cls, member = q.split(".", 1)
        pool = []
        for c in chain(idx, cls) or _ci_chain(idx, cls):
            pool += [(f"{cls}.{m}", m) for m in idx["classes"][c]["names"]]
        ml = member.lower()
        for full, m in pool:
            dist = lev(ml, m.lower())
            if dist <= limit:
                scored.append((dist, full))
    else:
        for k in idx["entries"]:
            if "." in k and not k.startswith("@"):
                continue
            base = k.split(".", 1)[1] if k.startswith(("@GDScript.", "@GlobalScope.")) else k
            if abs(len(base) - len(q)) > limit:
                continue
            dist = lev(ql, base.lower())
            if dist <= limit:
                scored.append((dist, base))
    scored.sort()
    out = []
    for _, s in scored:
        if s not in out:
            out.append(s)
    return out[:n]


def renames() -> dict:
    return json.loads(_DATA.read_text())


def _unq(s: str) -> str:
    return s.strip().strip('"')


def renamed(idx: dict, q: str) -> str | None:
    """Godot 3 -> 4 rename of q (class, builtin type, global function/enum, member), as a new query string."""
    r = renames()
    if "." not in q:
        for table in ("class_renames", "builtin_types_renames", "gdscript_function_renames", "enum_renames"):
            for old, new, cls in r[table]:
                if old == q and (table != "gdscript_function_renames" or cls == ""):
                    return _unq(new)
        return None
    cls, member = q.split(".", 1)
    ch = chain(idx, cls) or _ci_chain(idx, cls)
    for table in ("gdscript_properties_renames", "gdscript_function_renames", "gdscript_signals_renames"):
        for old, new, c in r[table]:
            if old == member and (c == "" or c in ch):
                return f"{cls}.{_unq(new)}"
    return None
