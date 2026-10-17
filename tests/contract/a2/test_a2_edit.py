"""A2 `h scene-edit` contract tests (AC-02.22 .. AC-02.30)."""
from __future__ import annotations

import difflib
import re

import pytest
from a2util import (assert_rule, assert_saved_none, copy_case, digest, digest_json, edit, fs, node_line, node_paths,
                    read, rule_findings, snapshot)
from helpers.h import assert_contract, run_h, write

pytestmark = pytest.mark.godot

CX = "res://scenes/complex.tscn"
V = lambda t: {"$var": t}


def before_after(host, scene, ops, flags=()):
    b = digest(host, scene, "--json")
    r = edit(host, scene, ops, flags=flags)
    a = digest(host, scene, "--json")
    return r, digest_json(b), digest_json(a)


def nodes_by_path(d):
    return {n["path"]: n for n in d["nodes"]}


def conn_keys(d):
    return sorted(f'{c["from"]}.{c["signal"]}->{c["to"]}.{c["method"]}/{c["flags"]}' for c in d["connections"])


def assert_untouched(b, a, touched):
    """Every node outside `touched` is identical in both digests (digest-after == digest-before + change)."""
    nb, na = nodes_by_path(b), nodes_by_path(a)
    for p in set(nb) & set(na):
        if p in touched:
            continue
        assert nb[p] == na[p], f"node {p} changed unexpectedly: {nb[p]} -> {na[p]}"
    assert b["editable"] == a["editable"] or "editable" in touched


@pytest.mark.parametrize("scene", ["res://scenes/complex.tscn", "res://scenes/inh.tscn", "res://scenes/editor_style.tscn"])
def test_ac_02_22_empty_ops_roundtrip(host, scene):
    r, b, a = before_after(host, scene, [])
    assert r.rc == 0 and r.verdict == "PASS", r
    assert b == a
    text = read(host, scene)
    if scene.endswith("inh.tscn"):
        root = next(ln for ln in text.splitlines() if ln.startswith("[node") and "parent=" not in ln)
        assert "instance=ExtResource(" in root
    if scene.endswith("complex.tscn"):
        assert '[editable path="A"]' in text


def test_ac_02_23_set_prop(host):
    r, b, a = before_after(host, CX, [{"op": "set_prop", "node": "B", "props": {"speed": 300}}])
    assert r.rc == 0, r
    assert any(re.match(r"^~ B speed: .* -> 300$", c) for c in r.stat_all("change")), r.stat_all("change")
    assert nodes_by_path(a)["B"]["props"]["speed"] == "300"
    assert_untouched(b, a, {"B"})
    assert conn_keys(b) == conn_keys(a)


def test_ac_02_23_set_prop_on_override_keeps_editable(host):
    r, b, a = before_after(host, CX, [{"op": "set_prop", "node": "A/Sprite", "props": {"rotation": 0.5}}])
    assert r.rc == 0, r
    assert any(c.startswith("~ A/Sprite rotation:") for c in r.stat_all("change")), r.stat_all("change")
    assert nodes_by_path(a)["A/Sprite"]["kind"] == "override"
    assert nodes_by_path(a)["A/Sprite"]["props"]["position"] == "Vector2(50, 50)"
    assert "rotation" in nodes_by_path(a)["A/Sprite"]["props"]
    assert '[editable path="A"]' in read(host, CX)
    assert_untouched(b, a, {"A/Sprite"})


def test_ac_02_23_set_prop_on_inner_adds_editable(host):
    p = fs(host, CX)
    p.write_text(p.read_text().replace('[editable path="A"]\n', ""))
    assert '[editable' not in p.read_text()
    r = edit(host, CX, [{"op": "set_prop", "node": "A/Sprite", "props": {"rotation": 0.25}}])
    assert r.rc == 0, r
    assert "+ editable A" in r.stat_all("change"), r.stat_all("change")
    assert '[editable path="A"]' in read(host, CX)


def test_ac_02_23_add_node(host):
    r, b, a = before_after(host, CX, [{"op": "add_node", "parent": ".", "node": {"name": "C", "type": "Sprite2D"}}])
    assert r.rc == 0, r
    assert "+ C Sprite2D" in r.stat_all("change"), r.stat_all("change")
    assert "C" in nodes_by_path(a) and "C" not in nodes_by_path(b)
    assert_untouched(b, a, {"C"})
    assert len(a["nodes"]) == len(b["nodes"]) + 1


def test_ac_02_23_add_instance(host):
    r, b, a = before_after(host, CX, [{"op": "add_instance", "parent": ".", "name": "A2",
                                       "scene": "res://scenes/child.tscn", "props": {"position": V("Vector2(1, 2)")}}])
    assert r.rc == 0, r
    assert any(c.startswith("+ A2 ") for c in r.stat_all("change")), r.stat_all("change")
    n = nodes_by_path(a)["A2"]
    assert n["kind"] == "instance" and n["instance"] == "res://scenes/child.tscn"
    assert_untouched(b, a, {"A2"})


def test_ac_02_23_remove_node_drops_subtree_and_connections(host):
    r, b, a = before_after(host, CX, [{"op": "remove_node", "node": "Area"}])
    assert r.rc == 0, r
    ch = r.stat_all("change")
    assert "- Area" in ch, ch
    assert not [p for p in nodes_by_path(a) if p == "Area" or p.startswith("Area/")]
    assert not [c for c in a["connections"] if c["from"].startswith("Area")]
    assert any(c.startswith("- conn ") and "area_entered" in c for c in ch), ch
    assert_untouched(b, a, {"Area", "Area/Shape"})


def test_ac_02_23_reparent_with_index(host):
    r, b, a = before_after(host, CX, [{"op": "reparent", "node": "B", "parent": "Area", "index": 0}])
    assert r.rc == 0, r
    assert "> B -> Area/B" in r.stat_all("change"), r.stat_all("change")
    order = [n["path"] for n in a["nodes"]]
    assert order.index("Area/B") < order.index("Area/Shape"), order
    assert "A.hit->Area/B._on_hit/2" in conn_keys(a), conn_keys(a)
    assert nodes_by_path(a)["Area/B"]["groups"] == ["g1", "g2"]


def test_ac_02_23_rename_follows_connections_and_node_refs(host):
    ops = [{"op": "set_prop", "node": ".", "props": {"target": {"$node": "B"}}},
           {"op": "rename", "node": "B", "name": "Bee"}]
    r, b, a = before_after(host, CX, ops)
    assert r.rc == 0, r
    assert "> B -> Bee" in r.stat_all("change"), r.stat_all("change")
    na = nodes_by_path(a)
    assert "Bee" in na and "B" not in na
    assert "A.hit->Bee._on_hit/2" in conn_keys(a), conn_keys(a)
    assert na["."]["props"]["target"] == "@Bee", na["."]["props"]
    assert na["Bee"]["groups"] == ["g1", "g2"]


def test_ac_02_23_connect(host):
    r, b, a = before_after(host, CX, [{"op": "connect", "from": "A", "signal": "hit", "to": ".", "method": "_on_hit"}])
    assert r.rc == 0, r
    assert any(c.startswith("+ conn A.hit -> ._on_hit") for c in r.stat_all("change")), r.stat_all("change")
    assert len(a["connections"]) == len(b["connections"]) + 1
    assert_untouched(b, a, set())


def test_ac_02_23_disconnect(host):
    r, b, a = before_after(host, CX, [{"op": "disconnect", "from": "A", "signal": "hit", "to": "B", "method": "_on_hit"}])
    assert r.rc == 0, r
    assert any(c.startswith("- conn A.hit -> B._on_hit") for c in r.stat_all("change")), r.stat_all("change")
    assert len(a["connections"]) == len(b["connections"]) - 1
    assert_untouched(b, a, set())


def test_ac_02_23_set_script_null_drops_script_props(host):
    r, b, a = before_after(host, CX, [{"op": "set_script", "node": "B", "script": None}])
    assert r.rc == 0, r
    nb = nodes_by_path(a)["B"]
    assert not nb.get("script") and "target" not in nb["props"], nb
    assert_untouched(b, a, {"B"})


def test_ac_02_23_set_script_attach(host):
    r, b, a = before_after(host, CX, [{"op": "set_script", "node": "Area", "script": "res://scripts/hero.gd"}])
    assert r.rc == 0, r
    assert nodes_by_path(a)["Area"]["script"] == "res://scripts/hero.gd"
    assert_untouched(b, a, {"Area"})


def test_ac_02_23_groups(host):
    r, b, a = before_after(host, CX, [{"op": "groups", "node": "B", "add": ["g3"], "remove": ["g1"]}])
    assert r.rc == 0, r
    ch = r.stat_all("change")
    assert "+ group B g3" in ch and "- group B g1" in ch, ch
    assert sorted(nodes_by_path(a)["B"]["groups"]) == ["g2", "g3"]
    assert_untouched(b, a, {"B"})


ERR_CASES = {
    "node-not-found": ("scenes/complex.tscn", [{"op": "set_prop", "node": "Nope", "props": {"visible": False}}],
                       "scene.node-not-found"),
    "duplicate-rename": ("scenes/complex.tscn", [{"op": "rename", "node": "B", "name": "A"}], "scene.duplicate-name"),
    "duplicate-add": ("scenes/complex.tscn", [{"op": "add_node", "parent": ".", "node": {"name": "A", "type": "Node2D"}}],
                      "scene.duplicate-name"),
    "internal-remove": ("scenes/complex.tscn", [{"op": "remove_node", "node": "A/Sprite"}], "scene.instance-internal"),
    "internal-rename": ("scenes/complex.tscn", [{"op": "rename", "node": "A/Sprite", "name": "Z"}],
                        "scene.instance-internal"),
    "internal-reparent-into": ("scenes/complex.tscn", [{"op": "reparent", "node": "B", "parent": "A/Inner"}],
                               "scene.instance-internal"),
    "inherited-remove": ("scenes/inh.tscn", [{"op": "remove_node", "node": "Sprite"}], "scene.instance-internal"),
    "bad-connection": ("scenes/complex.tscn", [{"op": "connect", "from": "A", "signal": "nosuchsignal", "to": "B",
                                                "method": "_on_hit"}], "scene.bad-connection"),
    "unknown-property": ("scenes/complex.tscn", [{"op": "set_prop", "node": "B", "props": {"positoin": V("Vector2(1, 1)")}}],
                         "scene.unknown-property"),
    "missing-resource": ("scenes/complex.tscn", [{"op": "add_instance", "parent": ".", "name": "G",
                                                  "scene": "res://scenes/gone.tscn"}], "scene.missing-resource"),
}


@pytest.mark.parametrize("case", sorted(ERR_CASES))
def test_ac_02_24_failing_op_writes_nothing(host, case):
    rel, ops, rule = ERR_CASES[case]
    res_path = "res://" + rel
    before = snapshot(host, res_path)
    r = edit(host, res_path, ops)
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert_saved_none(r)
    assert_rule(r, rule, startswith_slash=True)
    assert snapshot(host, res_path) == before


def test_ac_02_24_hints_for_typo_property(host):
    rel, ops, rule = ERR_CASES["unknown-property"]
    r = edit(host, "res://" + rel, ops)
    assert any("position" in (f["hint"] or "") for f in rule_findings(r, rule)), r


def test_ac_02_25_one_bad_op_discards_valid_ones(host):
    before = snapshot(host, CX)
    ops = [{"op": "set_prop", "node": "B", "props": {"speed": 777}},
           {"op": "rename", "node": "B", "name": "A"}]
    r = edit(host, CX, ops)
    assert r.rc == 1, r
    assert snapshot(host, CX) == before


def test_ac_02_26_broken_input_refused(host):
    copy_case(host, "c10", "broken/bad_parent.tscn")
    before = snapshot(host, "res://broken/bad_parent.tscn")
    r = edit(host, "res://broken/bad_parent.tscn", [{"op": "set_prop", "node": ".", "props": {"position": V("Vector2(1, 1)")}}])
    assert r.rc == 1, r
    assert_rule(r, "scene.broken-input")
    assert snapshot(host, "res://broken/bad_parent.tscn") == before


def test_ac_02_27_rename_breaking_a_dependent_is_rolled_back(host):
    child = "res://scenes/child.tscn"
    before = snapshot(host, child)
    r = edit(host, child, [{"op": "rename", "node": "Sprite", "name": "Body"}])
    assert r.rc == 1, r
    assert "(rolled back)" in r.stats.get("saved", ""), r.stat_items
    bd = rule_findings(r, "scene.breaks-dependent")
    assert any(f["path"] == "res://scenes/ov.tscn" for f in bd), bd
    assert snapshot(host, child) == before


def test_ac_02_27_already_broken_dependent_does_not_block(host):
    write(host, "scenes/dep_broken.tscn", "\n".join([
        "[gd_scene format=3]", "",
        '[ext_resource type="PackedScene" path="res://scenes/child.tscn" id="1_a"]', "",
        '[node name="R" type="Node2D"]', "",
        '[node name="C" parent="." instance=ExtResource("1_a")]', "",
        '[node name="X" type="Node2D" parent="Nope"]', ""]))
    r = edit(host, "res://scenes/child.tscn", [{"op": "set_prop", "node": ".", "props": {"speed": 260}}])
    assert r.rc in (0, 5), r
    assert r.verdict != "FAIL"
    assert not [f for f in rule_findings(r, "scene.breaks-dependent") if f["path"] == "res://scenes/dep_broken.tscn"]
    assert "speed" in digest_json(digest(host, "res://scenes/child.tscn", "--json"))["nodes"][0]["props"]


def _norm_ids(text):
    text = re.sub(r' unique_id=\d+', '', text)  # engine noise, spec 8.2-1 / AC-02.28
    text = re.sub(r'id="[^"]*"', 'id="ID"', text)
    return re.sub(r'(ExtResource|SubResource)\("[^"]*"\)', r'\1("ID")', text)


def test_ac_02_28_editor_style_uids_survive(host):
    scene = "res://scenes/editor_style.tscn"
    before = read(host, scene)
    r = edit(host, scene, [{"op": "set_prop", "node": "Sprite", "props": {"position": V("Vector2(9, 9)")}}])
    assert r.rc == 0, r
    after = read(host, scene)
    assert after.splitlines()[0] == before.splitlines()[0] and 'uid="uid://dk3w2h5n7ra4q"' in after.splitlines()[0]
    ext_b = [ln for ln in before.splitlines() if ln.startswith("[ext_resource")]
    ext_a = [ln for ln in after.splitlines() if ln.startswith("[ext_resource")]
    uid_re = re.compile(r'uid="(uid://[^"]+)"')
    assert [uid_re.search(x).group(1) for x in ext_a if uid_re.search(x)] == \
           [uid_re.search(x).group(1) for x in ext_b if uid_re.search(x)] and ext_a
    diff = [d for d in difflib.unified_diff(_norm_ids(before).splitlines(), _norm_ids(after).splitlines(), lineterm="", n=0)
            if d[:1] in "+-" and not d.startswith(("+++", "---"))]
    for d in diff:
        assert "unique_id=" in d or d[1:].startswith("position = "), f"unexpected diff line: {d}"


def test_ac_02_29_stale_reference_after_rename(host):
    scene = "res://scenes/player.tscn"
    ops = [{"op": "rename", "node": "Sprite", "name": "Body2"}]
    r = edit(host, scene, ops)
    assert r.rc == 5 and r.verdict == "WARN", r
    sr = rule_findings(r, "scene.stale-ref")
    assert any(f["path"] == "res://scripts/player.gd" and f["line"] == 3 for f in sr), sr
    assert "Body2" in digest(host, scene).stat_all("node").__str__()


def test_ac_02_29_stale_reference_strict_rolls_back(host):
    scene = "res://scenes/player.tscn"
    before = snapshot(host, scene)
    r = edit(host, scene, [{"op": "rename", "node": "Sprite", "name": "Body2"}], flags=["--strict"])
    assert r.rc == 1, r
    assert snapshot(host, scene) == before


def test_ac_02_30_no_effect_is_a_warning(host):
    r = edit(host, "res://scenes/child.tscn", [{"op": "set_prop", "node": ".", "props": {"speed": 250}}])
    assert r.rc == 5 and r.verdict == "WARN", r
    assert rule_findings(r, "scene.no-effect")
