"""A1 contract: the load_check.gd runner protocol (AC-01.27). The only A1 test that calls Godot directly (R-39),
through helpers.h.run_godot. Layer: contract."""
import pytest

from helpers.h import REPO, run_godot, write

RUNNER = REPO / "addons" / "harness" / "runners" / "load_check.gd"


def paths(recs, ev):
    return [r["path"] for r in recs if r.get("t") == "data" and r.get("ev") == ev]


def make_list(tmp_path, items):
    f = tmp_path / "list.txt"
    f.write_text("".join(i + "\n" for i in items))
    return f


@pytest.mark.godot
def test_ac_01_27_scripts_mode_prints_begin_end_pairs_and_done(mkwarm, tmp_path):
    assert RUNNER.is_file(), f"{RUNNER} does not exist yet"
    p = mkwarm()
    write(p, "scripts/a.gd", "extends Node\n")
    write(p, "scripts/b.gd", "extends Node\n\nvar x: int = 1\n")
    items = ["res://scripts/a.gd", "res://scripts/b.gd", "res://scripts/hello.gd"]
    lst = make_list(tmp_path, items)
    g = run_godot(["-s", str(RUNNER), "--", "--mode", "scripts", "--list", str(lst)], p, timeout=60)
    assert not g.timed_out
    recs = g.records
    assert paths(recs, "begin") == items
    assert paths(recs, "end") == items
    seq = [(r["ev"], r["path"]) for r in recs if r.get("t") == "data"]
    assert seq == [(ev, i) for i in items for ev in ("begin", "end")], "begin/end must alternate per item, in order"
    ends = [r for r in recs if r.get("t") == "data" and r.get("ev") == "end"]
    assert all(e["status"] == "ok" and e["recs"] == [] for e in ends), ends
    done = [r for r in recs if r.get("t") == "done"]
    assert len(done) == 1 and recs[-1] == done[0]
    assert g.rc == done[0]["rc"] == 0, g.text[-800:]


@pytest.mark.godot
def test_ac_01_27_scenes_mode_and_failing_item(mkwarm, tmp_path):
    assert RUNNER.is_file(), f"{RUNNER} does not exist yet"
    p = mkwarm()
    write(p, "scenes/bad.tscn", '[gd_scene format=3]\n\n[node name="Root" type="Node2D"]\nposition = Vector2(1, 2\n')
    items = ["res://scenes/main.tscn", "res://scenes/bad.tscn"]
    lst = make_list(tmp_path, items)
    g = run_godot(["-s", str(RUNNER), "--", "--mode", "scenes", "--list", str(lst)], p, timeout=60)
    recs = g.records
    ends = {r["path"]: r for r in recs if r.get("t") == "data" and r.get("ev") == "end"}
    assert ends["res://scenes/main.tscn"]["status"] == "ok"
    assert ends["res://scenes/bad.tscn"]["status"] == "load-failed"
    assert ends["res://scenes/bad.tscn"]["recs"], "the failing item carries the Logger records"
    done = [r for r in recs if r.get("t") == "done"]
    assert len(done) == 1 and done[0]["rc"] == 1 and g.rc == 1, g.text[-800:]


@pytest.mark.godot
def test_ac_01_27_bogus_mode_is_rc_2(mkwarm, tmp_path):
    assert RUNNER.is_file(), f"{RUNNER} does not exist yet"
    p = mkwarm()
    lst = make_list(tmp_path, ["res://scripts/hello.gd"])
    g = run_godot(["-s", str(RUNNER), "--", "--mode", "bogus", "--list", str(lst)], p, timeout=60)
    assert not g.timed_out and g.rc == 2, g.text[-800:]
