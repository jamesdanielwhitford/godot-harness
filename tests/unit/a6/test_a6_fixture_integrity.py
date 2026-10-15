"""A6 unit: integrity of the shot_min fixture and the A6 selftest entries (no harness import, pure data). AC-06.27:
visual.py is not public, so the only unit-level checks are on the data the contract tests rely on."""
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests" / "contract" / "a6"))
from a6_util import check_meta_schema, read_png                     # noqa: E402

FIX = REPO / "tests" / "fixtures" / "projects" / "shot_min"
FAULT_IDS = [f"FAULT-A6-{i:02d}" for i in range(1, 13)]
CLEAN_IDS = [f"CLEAN-A6-{i:02d}" for i in range(1, 4)]


def entry(i):
    for sub in ("faults", "clean"):
        d = REPO / "selftest" / sub / i
        if d.is_dir():
            return d
    raise AssertionError(i)


def test_fixture_baseline_meta_matches_png():
    meta = json.loads((FIX / "baselines/scenes/main/main-t30.json").read_text())
    png = FIX / "baselines/scenes/main/main-t30.png"
    assert check_meta_schema(meta) == []
    assert meta["image"]["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert read_png(png)[:2] == (640, 360) and png.stat().st_size <= 20 * 1024
    assert meta["approved_by"] == "fixture T6" and meta["status"] == "approved"
    assert '"status": "approved"' in (FIX / "baselines/scenes/main/main-t30.json").read_text()
    assert (FIX / "baselines" / ".gdignore").is_file()


def test_fixture_hook_lines_are_unique():
    for rel, hook in (("scripts/main.gd", "HOOK-READY"), ("scripts/main.gd", "HOOK-PROCESS"), ("scripts/hud.gd", "HOOK-HUD")):
        text = (FIX / rel).read_text()
        assert text.count(f"\tpass # {hook}\n") == 1, (rel, hook)
    assert (FIX / "scripts/main.gd").read_text().count("panel.position = Vector2(10, 10)") == 1


@pytest.mark.parametrize("fid", FAULT_IDS + CLEAN_IDS)
def test_selftest_entry_is_well_formed_and_applies(fid, tmp_path):
    d = entry(fid)
    t = tomllib.loads((d / "fault.toml").read_text())
    assert t["id"] == fid and t["area"] == "A6" and t["fixture"] == "shot_min"
    assert t["severity"] in ("must", "nice") and t["run"]["verb"] == "shot"
    assert t["expect"]["regex"], "each entry needs an expected regex"
    # replay the apply ops on a throwaway copy of the fixture: every replace must match exactly once
    import shutil
    proj = tmp_path / "p"
    shutil.copytree(FIX, proj)
    for op in t.get("apply", []):
        target = proj / op["path"]
        if op["op"] == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((d / op["from"]).read_bytes()) if "from" in op else target.write_text(op["text"])
        elif op["op"] == "replace":
            txt = target.read_text()
            assert txt.count(op["old"]) == op.get("count", 1), (fid, op["path"])
            target.write_text(txt.replace(op["old"], op["new"]))


def test_minimum_counts_and_png_sizes():
    assert len([i for i in FAULT_IDS if entry(i)]) == 12 >= 6
    assert (REPO / "selftest/faults/FAULT-A6-07/files/other.png").stat().st_size <= 20 * 1024
    assert read_png(REPO / "selftest/faults/FAULT-A6-07/files/other.png")[:2] == (640, 360)
    assert sum(1 for i in FAULT_IDS if tomllib.loads((entry(i) / "fault.toml").read_text())["severity"] == "must") >= 11
