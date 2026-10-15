"""AC-02.34: harness.scenes.model on synthetic before/effects/after triples (REVIEW R-01 allowlist).

Public names are render, diff, expected, compare (02_scene.md 8.3-1); their exact signatures are not fixed by the
spec. These tests assume [U]: expected(before_digest, effects) -> expected_digest and compare(expected, after) ->
list of finding dicts with key "rule" (or objects with .rule). Digest dicts follow 02_scene.md 2.7.
"""
from __future__ import annotations

import copy

import pytest



def _model():
    import harness.scenes.model as m  # noqa: PLC0415  (fail = collection-time ImportError is not wanted)
    return m


def node(path, kind="node", type_="Node2D", **kw):
    d = {"path": path, "kind": kind, "type": type_, "instance": None, "script": None, "groups": [], "unique": False,
         "props": {}, "vanished": False, "from": None}
    d.update(kw)
    return d


BEFORE = {"schema": "harness.digest/1", "kind": "scene", "path": "res://s.tscn", "uid": None, "format": 3,
          "inherits": None, "editable": ["A"], "deps": [], "ext_uids": {},
          "nodes": [node("."), node("A", "instance", None, instance="res://c.tscn"),
                    node("A/Sprite", "override", None, props={"position": "Vector2(1, 2)"}),
                    node("B", props={"speed": "5"}), node("C")],
          "connections": [{"from": "A", "signal": "hit", "to": "B", "method": "_m", "flags": 2}],
          "resource": None, "project": None}


def rules(findings):
    return {f["rule"] if isinstance(f, dict) else f.rule for f in findings}


def check(after):
    m = _model()
    return rules(m.compare(m.expected(copy.deepcopy(BEFORE), []), after))


def test_ac_02_34_identical_triple_is_clean():
    assert check(copy.deepcopy(BEFORE)) == set()


def test_ac_02_34_missing_node_is_lossy_save():
    a = copy.deepcopy(BEFORE)
    a["nodes"] = [n for n in a["nodes"] if n["path"] != "B"]
    assert "scene.lossy-save" in check(a)


def test_ac_02_34_missing_prop_is_lossy_save():
    a = copy.deepcopy(BEFORE)
    a["nodes"][2]["props"] = {}
    assert "scene.lossy-save" in check(a)


def test_ac_02_34_missing_editable_is_lossy_save():
    a = copy.deepcopy(BEFORE)
    a["editable"] = []
    assert "scene.lossy-save" in check(a)


def test_ac_02_34_extra_node_is_unexpected_change():
    a = copy.deepcopy(BEFORE)
    a["nodes"].append(node("Z"))
    assert "scene.unexpected-change" in check(a)


def test_ac_02_34_reordered_siblings_is_unexpected_change():
    a = copy.deepcopy(BEFORE)
    a["nodes"][3], a["nodes"][4] = a["nodes"][4], a["nodes"][3]
    assert "scene.unexpected-change" in check(a)


def test_ac_02_34_diff_reports_a_changed_prop():
    m = _model()
    a = copy.deepcopy(BEFORE)
    a["nodes"][3]["props"]["speed"] = "9"
    out = m.diff(BEFORE, a)
    text = "\n".join(out) if isinstance(out, (list, tuple)) else str(out)
    assert "speed" in text and "9" in text
    assert not m.diff(BEFORE, copy.deepcopy(BEFORE))
