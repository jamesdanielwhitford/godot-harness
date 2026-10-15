"""A2 `h digest` contract tests (AC-02.1 .. AC-02.10). Black-box; every result passes assert_contract."""
from __future__ import annotations

import json
import re
import shutil

import pytest
from a2util import (CASES, copy_case, digest, digest_json, node_line, node_paths, rule_findings, strip_volatile,
                    validate_digest_json, write_spec)
from helpers.h import assert_contract, run_h, write

pytestmark = pytest.mark.godot

COMPLEX = "res://scenes/complex.tscn"


def test_ac_02_1_digest_complex_nodes_and_lines(host):
    r = digest(host, COMPLEX)
    assert r.rc == 0 and r.verdict == "PASS", r
    assert node_paths(r) == [".", "A", "A/Sprite", "A/Inner/Extra", "B", "Area", "Area/Shape"]
    nodes = r.stat_all("node")
    assert any(v.startswith("A <res://scenes/child.tscn>") for v in nodes), nodes
    assert any(v.startswith("A/Sprite (override)") for v in nodes), nodes
    assert "target=@A" in node_line(r, "B")
    assert "collision_layer=world|player" in node_line(r, "Area")
    conns = r.stat_all("conn")
    assert "A.hit -> B._on_hit" in conns, conns
    assert "Area.area_entered -> ._on_hit flags=3" in conns, conns
    assert r.stat_all("editable") == ["A"], r.stat_items
    assert r.stats["project"].rstrip("/") == str(host)


def test_ac_02_1_digest_accepts_relative_fs_path_from_project_cwd(host):
    r = assert_contract(run_h("digest", "--project", host, "scenes/complex.tscn", cwd=host))
    assert r.rc == 0 and node_paths(r)[0] == "."


def test_ac_02_2_digest_is_deterministic(host):
    a = digest(host, COMPLEX)
    b = digest(host, COMPLEX)
    assert strip_volatile(a) == strip_volatile(b)
    assert a.artifact("digest.json").read_bytes() == b.artifact("digest.json").read_bytes()
    assert a.artifact("digest.txt").exists()


@pytest.mark.parametrize("case,name_re", [("c10", r"Nope/A"), ("c11", r"\bB\b"), ("c12", r"\bB\b")])
def test_ac_02_3_vanished_node_cases(host, case, name_re):
    dest = copy_case(host, case, f"broken/{case}.tscn")
    r = digest(host, f"res://broken/{case}.tscn")
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert any(v.endswith("!vanished") or " !vanished" in v for v in r.stat_all("node")), r.stat_items
    fs_ = rule_findings(r, "scene.vanished-node")
    assert fs_, r
    assert any(re.search(name_re, f["message"]) for f in fs_), fs_
    assert all(f["severity"] == "error" for f in fs_)


@pytest.mark.parametrize("case", ["c08", "c18", "c23"])
def test_ac_02_4_load_error_cases_fail(host, case):
    copy_case(host, case, f"broken/{case}.tscn")
    r = digest(host, f"res://broken/{case}.tscn")
    assert r.rc == 1 and r.verdict == "FAIL", r
    assert any(f["severity"] == "error" for f in r.all_findings()), r


def test_ac_02_4_two_roots_is_load_failed(host):
    copy_case(host, "c13", "broken/c13.tscn")
    r = digest(host, "res://broken/c13.tscn")
    assert r.rc == 1, r
    assert rule_findings(r, "scene.load-failed"), r


def test_ac_02_5_json_flag_and_schema(host):
    r = digest(host, COMPLEX, "--json")
    assert r.rc == 0, r
    assert "json" in r.stats, r.stat_items
    d = digest_json(r)
    assert validate_digest_json(d) == []
    assert d["kind"] == "scene" and d["path"] == COMPLEX
    assert [n["path"] for n in d["nodes"]] == node_paths(r)
    assert len(d["connections"]) == 2
    assert d["editable"] == ["A"]
    # ext_uids carries the uid written in the file (editor_style.tscn has one for hero.gd)
    e = digest(host, "res://scenes/editor_style.tscn", "--json")
    ed = digest_json(e)
    assert ed["uid"] == "uid://dk3w2h5n7ra4q"
    assert ed["ext_uids"].get("res://scripts/hero.gd", "").startswith("uid://")


def test_ac_02_6_player_digest_fits(host):
    r = digest(host, "res://scenes/player.tscn")
    assert r.rc == 0 and len(r.lines) <= 40
    assert "more" not in r.stats
    assert len(r.stat_all("node")) == 10


def test_ac_02_6_big_scene_cut_with_more_stat(host):
    lines = ["[gd_scene format=3]", "", '[node name="Big" type="Node2D"]', ""]
    for i in range(79):
        lines += [f'[node name="N{i:02d}" type="Node2D" parent="."]', ""]
    write(host, "scenes/big.tscn", "\n".join(lines))
    r = digest(host, "res://scenes/big.tscn")
    assert r.rc == 0 and len(r.lines) <= 40, r
    more = r.stats.get("more")
    assert more and re.match(r"^\d+ lines in .*digest\.txt$", more), r.stat_items
    full = r.artifact("digest.txt").read_text().splitlines()
    assert len([ln for ln in full if ln.startswith("node: ")]) == 80
    assert r.stat_items[-1][0] == "more"


def test_ac_02_6_node_option_prints_subtree_only(host):
    r = digest(host, "res://scenes/player.tscn", "--node", "Hurtbox")
    assert r.rc == 0, r
    assert node_paths(r) == ["Hurtbox", "Hurtbox/HurtShape"]


def test_ac_02_7_project_summary(host):
    r = run_h("digest", "--project", host, "--project-summary", cwd=host.parent)
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS", r
    assert r.stats["name"] == "scene_host"
    assert r.stats["main_scene"] == "res://scenes/complex.tscn"
    assert "GameState res://scripts/game_state.gd" in r.stat_all("autoload")
    assert any(a.startswith("jump") and "Space" in a for a in r.stat_all("action")), r.stat_all("action")
    assert r.stats["layers-2d_physics"] == "1=world 2=player 3=hazard"
    listed = sorted(v.split(" ")[0] for v in r.stat_all("scene"))
    on_disk = sorted("res://" + str(p.relative_to(host)) for p in host.rglob("*.tscn")
                     if ".godot" not in p.parts and ".harness" not in p.parts and p.relative_to(host).parts[0] != "addons")
    assert listed == on_disk
    assert "res://addons/demo/demo.tscn" not in listed
    assert r.wall <= 3.0 + 1.0, f"warm --project-summary took {r.wall:.1f}s (budget 3s + 1s timer slack)"


def test_ac_02_8_resource_digest(host):
    r = digest(host, "res://res/item.tres")
    assert r.rc == 0, r
    res_line = r.stats.get("resource", "")
    assert "type=" in res_line and "script_class=ItemData" in res_line, res_line
    props = r.stat_all("prop")
    assert any(p.startswith("label=") for p in props) and any(p.startswith("value=") for p in props), props


def test_ac_02_9_usage_errors_rc2(host, tmp_path):
    outside = tmp_path / "outside.tscn"
    shutil.copy(host / "scenes" / "child.tscn", outside)
    cases = [
        ("missing file", ["res://scenes/nope.tscn"]),
        ("gd target", ["res://scripts/hero.gd"]),
        ("outside project", [str(outside)]),
        ("unknown node", [COMPLEX, "--node", "Nope"]),
        ("target with --project-summary", [COMPLEX, "--project-summary"]),
    ]
    for label, args in cases:
        r = assert_contract(run_h("digest", "--project", host, *args, cwd=host.parent))
        assert r.rc == 2 and r.verdict == "ERROR", f"{label}\n{r}"
        assert r.lines[0].startswith("ERROR digest "), label


def test_ac_02_10_expand_lists_instance_internals(host):
    r = digest(host, COMPLEX, "--expand")
    assert r.rc == 0, r
    line = node_line(r, "A/Inner")
    assert line is not None and "(from res://scenes/child.tscn)" in line, r.stat_all("node")
