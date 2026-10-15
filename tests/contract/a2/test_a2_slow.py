"""A2 budgets and selftest (AC-02.31, AC-02.32). Marked slow."""
from __future__ import annotations

import json
import statistics
import time

import pytest
from a2util import write_spec
from helpers.h import assert_contract, run_h, write

pytestmark = [pytest.mark.godot, pytest.mark.slow]


def median3(fn):
    ts = []
    for i in range(3):
        t0 = time.monotonic()
        r = fn(i)
        ts.append(time.monotonic() - t0)
        assert r.rc in (0, 5), r
    return statistics.median(ts)


def test_ac_02_31_digest_budget(host):
    def go(_):
        return assert_contract(run_h("digest", "--project", host, "res://scenes/complex.tscn", cwd=host.parent))
    assert median3(go) <= 2.0


def test_ac_02_31_project_summary_budget_50_scenes(host):
    for i in range(50):
        write(host, f"scenes/many/s{i:02d}.tscn", '[gd_scene format=3]\n\n[node name="S" type="Node2D"]\n')

    def go(_):
        return assert_contract(run_h("digest", "--project", host, "--project-summary", cwd=host.parent))
    assert median3(go) <= 3.0


def test_ac_02_31_scene_gen_budget_30_nodes(host, tmp_path):
    def go(i):
        kids = [{"name": f"N{k:02d}", "type": "Node2D"} for k in range(29)]
        p = write_spec(tmp_path, f"big{i}.json", {"save": f"res://gen/big{i}.tscn",
                                                  "root": {"name": "Big", "type": "Node2D", "children": kids}})
        return assert_contract(run_h("scene-gen", "--project", host, p, cwd=host.parent))
    assert median3(go) <= 5.0


def test_ac_02_31_scene_edit_budget_10_ops_3_dependents(host, tmp_path):
    def go(i):
        ops = [{"op": "groups", "node": "Inner", "add": [f"r{i}_{k}"]} for k in range(10)]
        p = tmp_path / f"ops{i}.json"
        p.write_text(json.dumps({"ops": ops}))
        return assert_contract(run_h("scene-edit", "--project", host, "res://scenes/child.tscn", p, cwd=host.parent))
    assert median3(go) <= 6.0


def test_ac_02_32_selftest_area_a2():
    r = assert_contract(run_h("selftest", "--area", "A2", timeout=400))
    assert r.rc == 0, r
    f = r.stats.get("faults", "")
    assert f.startswith("15 total"), f
    assert r.stats.get("clean", "").startswith("3 total, 3 pass"), r.stats
    assert r.wall <= 240
    m = json.loads(r.artifact("matrix.json").read_text())
    entries = m if isinstance(m, list) else m.get("entries", m)
    assert len(entries) == 18
