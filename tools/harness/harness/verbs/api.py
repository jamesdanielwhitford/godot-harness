"""h api: Godot 4.7 API lookup from a cached index (A1 2.4, 3.5)."""
import os
import shutil
from pathlib import Path

from .. import apiindex, godot, out, pins

HELP = "look up Godot 4.7 classes, members, functions; find renamed APIs"
USAGE = """
h api <Name>                    Class | Class.member | global function | annotation | constant
h api <Name> --all              list the members of a class (max 30, then `more:`)
h api --search <substr> [--limit N]   case-insensitive substring over keys (default 20, max 30)
h api --exists <Name>           hook mode: PASS = 2 lines, FAIL = 3 lines
h api --rebuild                 (re)build the cache index with Godot
Names that exist only in Godot 3 give `suggest:` and an [api.renamed] finding."""


def _parser():
    p = out.common_parser("api")
    p.add_argument("name", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--search", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--exists", default=None)
    p.add_argument("--rebuild", action="store_true")
    return p


def index_paths(version):
    d = pins.cache_dir() / "api" / version
    return d, d / "index.json"


def rebuild(r, version):
    """Dump the extension API + docs with Godot (no --path, R-05) and build index.json atomically."""
    d, idx_path = index_paths(version)
    tmp = os.environ.get("HARNESS_TMP") or (os.environ.get("TMPDIR") or "/tmp") + "/godot-harness"
    scratch = Path(tmp) / f"api-{r.run_id}"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        inv = godot.run(r, "doctool", None, args=["--dump-extension-api-with-docs"], cwd=scratch)
        r.add_findings([f for f in inv.findings if f["severity"] == "error"])
        if not (scratch / "extension_api.json").is_file():
            r.error(3, "godot did not write extension_api.json (see godot/01-doctool.log)")
        (scratch / "doc").mkdir(exist_ok=True)
        inv2 = godot.run(r, "doctool", None, args=["--doctool", str(scratch / "doc")], cwd=scratch)
        r.add_findings([f for f in inv2.findings if f["severity"] == "error"])
        xml = scratch / "doc" / "modules" / "gdscript" / "doc_classes" / "@GDScript.xml"
        if not xml.is_file():
            cands = list((scratch / "doc").rglob("@GDScript.xml"))
            xml = cands[0] if cands else None
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scratch / "extension_api.json", d / "extension_api.json")
        if xml is not None:
            shutil.copyfile(xml, d / "@GDScript.xml")
        idx = apiindex.build(d / "extension_api.json", d / "@GDScript.xml" if xml is not None else None, version)
        apiindex.save(idx, idx_path)
        return idx
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _version(r):
    cfg = r.config or {}
    return cfg.get("harness", {}).get("godot_version") or pins.load()["godot_version_string"]


def get_index(r, version, force=False):
    d, idx_path = index_paths(version)
    if not force:
        idx = apiindex.load(idx_path, version)
        if idx is not None:
            return idx
    return rebuild(r, version)


def _doc_stats(r, key, e, q, idx):
    r.stat("kind", e["k"])
    r.stat("sig", e["sig"])
    if e.get("in") and "." in q and not q.startswith("@") and e["in"] != q.split(".", 1)[0]:
        r.stat("defined-in", e["in"])
    if e["k"] in ("class", "builtin"):
        c = idx["classes"].get(key, {})
        inh = apiindex.chain(idx, c.get("inh", "")) if c.get("inh") else []
        if inh:
            r.stat("inherits", " < ".join(inh))
        n = c.get("n", [0, 0, 0])
        r.stat("members", f"{n[0]} methods, {n[1]} properties, {n[2]} signals")
    if e.get("d"):
        r.stat("doc", e["d"])


def _not_found(r, idx, q, exists_mode):
    new = apiindex.renamed(idx, q)
    if new:
        r.finding(None, None, "api.renamed", "error", f"{q} was renamed in Godot 4", hint=f"use {new}")
        if not exists_mode:
            r.stat("suggest", new)
        return r.finish(f"'{q}' not in Godot 4.7 (renamed: {new})")
    if exists_mode:
        r.finding(None, None, "api.not-found", "error", f"{q} does not exist in Godot 4.7")
        return r.finish(f"'{q}' not in Godot 4.7")
    cands = apiindex.suggest(idx, q)
    r.finding(None, None, "api.not-found", "error", f"{q} does not exist in Godot 4.7",
              hint=f"did you mean {', '.join(cands)}?" if cands else None)
    return r.finish(f"'{q}' not in Godot 4.7")


def _main(r, args, project):
    version = _version(r)
    if args.rebuild:
        idx = get_index(r, version, force=True)
        r.stat("index", f"{idx['count']} entries")
        return r.finish(f"index rebuilt ({idx['count']} entries)")
    q = args.exists or args.name
    if not q and args.search is None:
        r.error(2, "usage: need a name, --search, --exists or --rebuild")
    idx = get_index(r, version)
    if args.search is not None:
        limit = max(1, min(args.limit, 30))
        s = args.search.lower()
        hits = sorted(k for k in idx["entries"] if s in k.lower())
        for k in hits[:limit]:
            r.stat("match", f"{k}  {idx['entries'][k]['sig']}")
        if len(hits) > limit:
            r.stat("more", f"{len(hits) - limit} (narrow the search)")
        if not hits:
            r.finding(None, None, "api.not-found", "error", f"no key contains '{args.search}'")
            return r.finish(f"no match for '{args.search}'")
        return r.finish(f"{len(hits)} match{'es' if len(hits) != 1 else ''} for '{args.search}'")
    hit = apiindex.lookup(idx, q)
    if hit is None:
        return _not_found(r, idx, q, bool(args.exists))
    key, e = hit
    if args.exists:
        return r.finish(f"{q} exists ({e['k']})")
    _doc_stats(r, key, e, q, idx)
    if args.all and e["k"] in ("class", "builtin"):
        names = idx["classes"].get(key, {}).get("names", [])
        for n in names[:30]:
            ent = idx["entries"].get(f"{key}.{n}")
            if ent:
                r.stat("match", f"{key}.{n}  {ent['sig']}")
        if len(names) > 30:
            r.stat("more", f"{len(names) - 30} (narrow the search)")
    return r.finish(f"{q} ({e['k']})")


def run(argv):
    return out.invoke("api", argv, _parser(), _main, need_project=False)
