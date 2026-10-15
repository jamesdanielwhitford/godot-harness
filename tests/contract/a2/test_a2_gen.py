"""A2 `h scene-gen` contract tests (AC-02.11 .. AC-02.21)."""
from __future__ import annotations

import json
import re
import time

import pytest
from a2util import (assert_rule, assert_saved_none, digest, digest_json, fs, gen, n_node_decls, node_line, node_paths,
                    read, rule_findings, spec_of, write_spec)
from helpers.h import assert_contract, run_h, tree_hash, write

pytestmark = pytest.mark.godot

HERO = "res://scripts/hero.gd"
S = "specs"


def sp(host, name):
    return host / S / name


def test_ac_02_11_gen_child_then_main(host):
    r = gen(host, sp(host, "child.scene.json"), sp(host, "main.scene.json"))
    assert r.rc == 0 and r.verdict == "PASS", r
    assert len([c for c in r.checks if c[0] == "OK"]) == 2, r.checks
    for inv in r.invocations():
        assert inv["scan_verdict"] == "PASS", inv
    main = read(host, "res://gen/main.tscn")
    assert 'node_paths=PackedStringArray("target")' in main
    for name in n_node_decls(main) + n_node_decls(read(host, "res://gen/child.tscn")):
        assert "@" not in name
    d = digest(host, "res://gen/main.tscn")
    assert all("@" not in p.split(" ")[0] for p in d.stat_all("node"))
    chk = assert_contract(run_h("check", "--project", host, cwd=host.parent))
    assert chk.rc == 0 and chk.verdict == "PASS", chk


def test_ac_02_12_overrides_and_extra_nodes(host):
    r = gen(host, sp(host, "ov.scene.json"))
    assert r.rc == 0, r
    assert '[editable path="A"]' in read(host, "res://gen/ov.tscn")
    d = digest(host, "res://gen/ov.tscn")
    assert node_line(d, "A/Sprite").startswith("A/Sprite (override) position=Vector2(50, 50)"), d.stat_all("node")
    assert node_line(d, "A/Inner/Extra").startswith("A/Inner/Extra Marker2D")


def test_ac_02_13_new_subresource_and_layers(host):
    r = gen(host, sp(host, "shapes.scene.json"))
    assert r.rc == 0, r
    text = read(host, "res://gen/shapes.tscn")
    assert text.count('[sub_resource type="RectangleShape2D"') == 1
    d = digest(host, "res://gen/shapes.tscn")
    assert "collision_layer=world|player" in node_line(d, "Zone")


def test_ac_02_13_unknown_layer_name_is_bad_value(host, tmp_path):
    p = write_spec(tmp_path, "l.json", spec_of({"name": "R", "type": "Node2D", "children": [
        {"name": "Z", "type": "Area2D", "props": {"collision_layer": {"$layers": ["nope"]}}}]}))
    r = gen(host, p)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert_rule(r, "scene.bad-value")
    assert_saved_none(r)


def test_ac_02_14_inherited_spec(host):
    r = gen(host, sp(host, "inherited.scene.json"))
    assert r.rc == 0, r
    text = read(host, "res://gen/inherited.tscn")
    root_line = next(ln for ln in text.splitlines() if ln.startswith("[node") and "parent=" not in ln)
    assert "instance=ExtResource(" in root_line and "type=" not in root_line, root_line
    assert "[editable" not in text
    d = digest(host, "res://gen/inherited.tscn")
    assert d.stats.get("inherits") == "res://scenes/child.tscn", d.stat_items
    assert "speed=900" in node_line(d, ".")
    assert "position=Vector2(7, 8)" in node_line(d, "Sprite")


def _bad(root, **kw):
    return spec_of(root, save="res://gen/bad.tscn", **kw)


GEN_CASES = {
    "unknown-property": (_bad({"name": "R", "type": "Node2D", "props": {"positoin": {"$var": "Vector2(1, 1)"}}}),
                         "scene.unknown-property", r"positoin", "position"),
    "unknown-type": (_bad({"name": "R", "type": "Node2D", "children": [{"name": "X", "type": "Spirte2D"}]}),
                     "scene.unknown-type", r"Spirte2D", "Sprite2D"),
    "bad-value": (_bad({"name": "R", "type": "Node2D", "props": {"position": "abc"}}), "scene.bad-value", r"", None),
    "bad-value-var": (_bad({"name": "R", "type": "Node2D", "props": {"position": {"$var": "Vector2(1,"}}}),
                      "scene.bad-value", r"", None),
    "string-node-export": (_bad({"name": "R", "type": "Node2D", "script": HERO, "props": {"target": "Child"},
                                 "children": [{"name": "Child", "type": "Node2D"}]}),
                           "scene.bad-value", r"", "$node"),
    "not-stored": (_bad({"name": "R", "type": "Node2D", "props": {"name": "Other"}}), "scene.not-stored", r"", None),
    "missing-resource-res": (_bad({"name": "R", "type": "Sprite2D", "props": {"texture": {"$res": "res://nope.png"}}}),
                             "scene.missing-resource", r"", None),
    "missing-resource-instance": (_bad({"name": "R", "type": "Node2D", "children": [
        {"name": "I", "instance": "res://scenes/gone.tscn"}]}), "scene.missing-resource", r"", None),
    "missing-resource-script": (_bad({"name": "R", "type": "Node2D", "script": "res://scripts/ghost.gd"}),
                                "scene.missing-resource", r"", None),
    "duplicate-name": (_bad({"name": "R", "type": "Node2D", "children": [
        {"name": "A", "type": "Node2D"}, {"name": "A", "type": "Node2D"}]}), "scene.duplicate-name", r"", None),
    "node-not-found-ref": (_bad({"name": "R", "type": "Node2D", "script": HERO, "props": {"target": {"$node": "Ghost"}}}),
                           "scene.node-not-found", r"", None),
    "node-not-found-override": (_bad({"name": "R", "type": "Node2D", "children": [
        {"name": "A", "instance": "res://scenes/child.tscn"}]}, overrides={"A/Nope": {"visible": False}}),
        "scene.node-not-found", r"", None),
    "node-not-found-extra-parent": (_bad({"name": "R", "type": "Node2D"},
                                         extra_nodes=[{"parent": "Ghost", "name": "X", "type": "Node2D"}]),
                                    "scene.node-not-found", r"", None),
    "bad-connection-method": (_bad({"name": "R", "type": "Node2D", "script": HERO, "children": [
        {"name": "B", "type": "Node2D", "script": HERO}]},
        connections=[{"from": "B", "signal": "hit", "to": ".", "method": "_on_nope"}]), "scene.bad-connection", r"", None),
    "bad-connection-signal": (_bad({"name": "R", "type": "Node2D", "script": HERO, "children": [
        {"name": "B", "type": "Node2D", "script": HERO}]},
        connections=[{"from": "B", "signal": "nosuchsignal", "to": ".", "method": "_on_hit"}]),
        "scene.bad-connection", r"", None),
}


@pytest.mark.parametrize("case", sorted(GEN_CASES))
def test_ac_02_15_bad_spec_rejected_nothing_written(host, tmp_path, case):
    spec, rule, msg_re, hint = GEN_CASES[case]
    p = write_spec(tmp_path, f"{case}.scene.json", spec)
    r = gen(host, p)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert_saved_none(r)
    assert not fs(host, "res://gen/bad.tscn").exists()
    fs_ = assert_rule(r, rule, startswith_slash=True)
    if msg_re:
        assert any(re.search(msg_re, f["message"]) for f in fs_), fs_
    if hint:
        assert any(hint in (f["hint"] or "") for f in fs_), f"hint {hint!r} not in {fs_}"


def test_ac_02_15_pointer_names_the_property(host, tmp_path):
    spec, *_ = GEN_CASES["unknown-property"]
    r = gen(host, write_spec(tmp_path, "p.scene.json", spec))
    assert any(f["message"].startswith("/root/props/positoin") for f in rule_findings(r, "scene.unknown-property"))
    spec, *_ = GEN_CASES["unknown-type"]
    r = gen(host, write_spec(tmp_path, "t.scene.json", spec))
    assert any(f["message"].startswith("/root/children/0/type") for f in rule_findings(r, "scene.unknown-type"))


def test_ac_02_16_three_errors_reported_in_one_run(host, tmp_path):
    p = write_spec(tmp_path, "three.scene.json", _bad({"name": "R", "type": "Node2D",
                   "props": {"positoin": {"$var": "Vector2(1, 1)"}, "rotation": "abc"},
                   "children": [{"name": "X", "type": "Spirte2D"}]}))
    r = gen(host, p)
    assert r.rc == 1, r
    errs = [f for f in r.all_findings() if f["severity"] == "error" and f["rule"].startswith("scene.")]
    assert len(errs) >= 3, errs
    assert {"scene.unknown-property", "scene.unknown-type", "scene.bad-value"} <= {f["rule"] for f in errs}


SCHEMA_CASES = {
    "missing-save": ('{"root": {"name": "R", "type": "Node2D"}}', None),
    "type-and-instance": (json.dumps({"save": "res://gen/x.tscn", "root": {"name": "R", "type": "Node2D",
                                      "instance": "res://scenes/child.tscn"}}), None),
    "unknown-key-chlidren": (json.dumps({"save": "res://gen/x.tscn", "root": {"name": "R", "type": "Node2D",
                                         "chlidren": []}}), None),
    "save-not-tscn": (json.dumps({"save": "res://gen/x.tres", "root": {"name": "R", "type": "Node2D"}}), None),
    "save-under-godot": (json.dumps({"save": "res://.godot/x.tscn", "root": {"name": "R", "type": "Node2D"}}), None),
    "invalid-json": ('{"save": "res://gen/x.tscn",\n "root": {"name": "R",\n  "type": }}\n', r":\d+$"),
}


@pytest.mark.parametrize("case", sorted(SCHEMA_CASES))
def test_ac_02_17_spec_schema_errors_rc2_no_godot(host, tmp_path, case):
    text, loc_re = SCHEMA_CASES[case]
    p = tmp_path / "specs_in" / "s.scene.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    r = gen(host, p)
    assert r.rc == 2 and r.verdict == "ERROR", r
    fs_ = assert_rule(r, "scene.spec-schema")
    assert r.invocations() == [], "schema errors must not start Godot"
    assert r.wall <= 1.5, f"took {r.wall:.2f}s (spec says <= 1 s)"
    if loc_re:
        assert any(f["line"] is not None for f in fs_), f"invalid JSON finding must carry :LINE: {fs_}"
    assert not (host / "gen").exists() or not list((host / "gen").glob("x.tscn"))


def test_ac_02_18_existing_target_needs_force(host):
    before = fs(host, "res://scenes/editor_style.tscn").read_bytes()
    uid_line = before.decode().splitlines()[0]
    spec = {"save": "res://scenes/editor_style.tscn", "root": {
        "name": "EditorStyle", "type": "Node2D", "script": HERO, "props": {"speed": 130},
        "children": [{"name": "Sprite", "type": "Sprite2D"}]}}
    p = host.parent / "regen.scene.json"
    p.write_text(json.dumps(spec))
    r = gen(host, p)
    assert r.rc == 2 and r.verdict == "ERROR" and "use --force" in r.lines[0], r
    assert fs(host, "res://scenes/editor_style.tscn").read_bytes() == before
    r2 = gen(host, p, flags=["--force"])
    assert r2.rc == 0, r2
    assert r2.stat_all("change"), r2.stat_items
    assert "uid://dk3w2h5n7ra4q" in read(host, "res://scenes/editor_style.tscn").splitlines()[0], uid_line


def test_ac_02_19_hanging_spec_script(host, tmp_path):
    write(host, "scripts/hang.gd", "extends Node2D\n\n\nfunc _init() -> void:\n\twhile true:\n\t\tpass\n")
    write(host, "harness.toml", "[timeouts]\nrunner = 5\n")
    p = write_spec(tmp_path, "h.scene.json", spec_of({"name": "R", "type": "Node2D", "script": "res://scripts/hang.gd"},
                                                     save="res://gen/hang.tscn"))
    t0 = time.monotonic()
    r = gen(host, p)
    assert time.monotonic() - t0 <= 25
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert rule_findings(r, "harness.hang"), r
    assert not fs(host, "res://gen/hang.tscn").exists()
    assert any(i["timed_out"] and i["rc"] == 124 for i in r.invocations())


def test_ac_02_20_two_specs_second_instances_first(host, tmp_path):
    a = write_spec(tmp_path, "a.json", spec_of({"name": "A", "type": "Node2D", "children": [
        {"name": "K", "type": "Node2D"}]}, save="res://gen/a.tscn"))
    b = write_spec(tmp_path, "b.json", spec_of({"name": "B", "type": "Node2D", "children": [
        {"name": "I", "instance": "res://gen/a.tscn"}]}, save="res://gen/b.tscn"))
    r = gen(host, a, b)
    assert r.rc == 0, r
    ok = [c for c in r.checks if c[0] == "OK"]
    assert len(ok) == 2 and {c[1] for c in ok} == {"res://gen/a.tscn", "res://gen/b.tscn"}, r.checks
    assert fs(host, "res://gen/b.tscn").exists()


def test_ac_02_20_first_broken_second_skipped(host, tmp_path):
    a = write_spec(tmp_path, "a.json", spec_of({"name": "A", "type": "Spirte2D"}, save="res://gen/a.tscn"))
    b = write_spec(tmp_path, "b.json", spec_of({"name": "B", "type": "Node2D"}, save="res://gen/b.tscn"))
    r = gen(host, a, b)
    assert r.rc == 1, r
    st = {c[1]: c[0] for c in r.checks}
    assert st.get("res://gen/a.tscn") == "FAIL" and st.get("res://gen/b.tscn") == "SKIP", r.checks
    assert not fs(host, "res://gen/a.tscn").exists() and not fs(host, "res://gen/b.tscn").exists()


def test_ac_02_21_parse_broken_script_rejected(host, tmp_path):
    write(host, "scripts/broken.gd", "extends Node2D\n\nvar x = = 3\n")
    p = write_spec(tmp_path, "b.json", spec_of({"name": "R", "type": "Node2D", "script": "res://scripts/broken.gd"},
                                               save="res://gen/broken.tscn"))
    r = gen(host, p)
    assert r.rc == 1, r
    assert_rule(r, "scene.bad-script")
    pe = rule_findings(r, "godot.parse-error")
    assert any(f["path"] == "res://scripts/broken.gd" and f["line"] == 3 for f in pe), pe
    assert not fs(host, "res://gen/broken.tscn").exists()
    assert_saved_none(r)
