"""AC-02.33: fresh clean_min -> scene-gen x2 -> scene-edit -> digest x2 -> h check PASS; fixture tree unchanged (B3)."""
from __future__ import annotations

import json

import pytest
from helpers.h import FIXTURES, assert_contract, copy_fixture, run_h, tree_hash

pytestmark = pytest.mark.godot

HELLO = "res://scripts/hello.gd"


def test_ac_02_33_gen_edit_digest_check_flow(tmp_path):
    src = FIXTURES / "projects" / "clean_min"
    before = tree_hash(src)
    proj = copy_fixture("clean_min", tmp_path / "proj")
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "part.json").write_text(json.dumps({"save": "res://gen/part.tscn", "root": {
        "name": "Part", "type": "Node2D", "script": HELLO,
        "children": [{"name": "Sprite", "type": "Sprite2D"}, {"name": "Slot", "type": "Node2D"}]}}))
    (specs / "level.json").write_text(json.dumps({"save": "res://gen/level.tscn", "root": {
        "name": "Level", "type": "Node2D", "children": [{"name": "P", "instance": "res://gen/part.tscn"}]}}))
    g = assert_contract(run_h("scene-gen", "--project", proj, specs / "part.json", specs / "level.json", cwd=tmp_path))
    assert g.rc == 0 and g.verdict == "PASS", g
    assert g.stats.get("import", "").startswith("ran"), "fresh copy must auto-import"
    ops = tmp_path / "ops.json"
    ops.write_text(json.dumps({"ops": [
        {"op": "add_node", "parent": ".", "node": {"name": "Extra", "type": "Marker2D"}},
        {"op": "rename", "node": "Slot", "name": "Hole"},
        {"op": "connect", "from": ".", "signal": "visibility_changed", "to": ".", "method": "_ready"}]}))
    e = assert_contract(run_h("scene-edit", "--project", proj, "res://gen/part.tscn", ops, cwd=tmp_path))
    assert e.rc == 0 and e.verdict == "PASS", e
    for scene, needle in (("res://gen/part.tscn", "Hole"), ("res://gen/level.tscn", "P/Hole")):
        d = assert_contract(run_h("digest", "--project", proj, scene, "--expand", cwd=tmp_path))
        assert d.rc == 0, d
        assert any(v.split(" ")[0] == needle for v in d.stat_all("node")), (scene, d.stat_all("node"))
    c = assert_contract(run_h("check", "--project", proj, cwd=tmp_path))
    assert c.rc == 0 and c.verdict == "PASS", c
    assert tree_hash(src) == before, "fixture tree in the repo was modified (B3)"
