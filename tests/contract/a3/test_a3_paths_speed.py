"""A3 contract: path arguments, --hook/--changed, speed budgets. AC-03.6, 03.7, 03.21."""
from __future__ import annotations

import statistics
import subprocess
from pathlib import Path

import pytest

from a3_common import CASES, expected_godot3, finding_set, fresh, lint, write
from helpers.h import assert_contract, run_h


# ---- AC-03.21 paths ------------------------------------------------------------------------------------------
YIELD_ROW = {("res://cases/c04_yield.gd", 3, "syn-yield", "error")}


def test_ac_03_21_res_path_lints_only_that_file(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "res://cases/c04_yield.gd"))
    assert r.rc == 1 and finding_set(r) == YIELD_ROW, str(r)
    assert r.stats["files"].startswith("1 .gd, 0 .tscn, 0 .tres")


def test_ac_03_21_cwd_relative_and_absolute_paths(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "cases/c04_yield.gd", cwd=p))
    assert finding_set(r) == YIELD_ROW, str(r)
    r2 = assert_contract(lint(p, str(p / "cases" / "c04_yield.gd"), cwd=tmp_path))
    assert finding_set(r2) == YIELD_ROW, str(r2)
    r3 = assert_contract(lint(p, "c04_yield.gd", cwd=p / "cases"))
    assert finding_set(r3) == YIELD_ROW, str(r3)


def test_ac_03_21_directory_argument_recurses(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "cases", cwd=p))
    want = {e for e in expected_godot3() if e[0].startswith("res://cases/")}
    assert finding_set(r) == want, str(r)
    assert r.stats["files"].startswith("35 .gd, 0 .tscn")


def test_ac_03_21_other_extensions_ignored(tmp_path):
    p = fresh(tmp_path)
    write(p, "notes.txt", "yield(a, b)\n")
    r = assert_contract(lint(p, "notes.txt", cwd=p))
    assert r.rc == 0 and r.run_json()["findings_total"] == 0, str(r)


def test_ac_03_21_path_outside_project_is_usage_error(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    out = tmp_path / "elsewhere.gd"
    out.write_text(CASES["c04_yield"][0])
    r = assert_contract(lint(p, str(out)))
    assert r.rc == 2 and r.verdict == "ERROR" and r.lines[0].startswith("ERROR lint usage: "), str(r)


def test_ac_03_21_missing_path_is_usage_error(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "res://cases/nope.gd"))
    assert r.rc == 2 and r.lines[0].startswith("ERROR lint usage: ") and "nope.gd" in r.lines[0], str(r)


def test_ac_03_21_hook_without_path_is_usage_error(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "--hook"))
    assert r.rc == 2 and r.lines[0].startswith("ERROR lint usage: "), str(r)


def test_ac_03_21_changed_outside_git_is_usage_error(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "--changed"))
    assert r.rc == 2 and r.verdict == "ERROR", str(r)


def _git(p: Path, *args):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": __import__("os").environ["PATH"], "HOME": str(p.parent)}
    subprocess.run(["git", *args], cwd=p, env=env, check=True, capture_output=True)


def test_ac_03_21_changed_lints_only_modified_and_untracked_files(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    _git(p, "init", "-q")
    _git(p, "add", "-A")
    _git(p, "commit", "-q", "-m", "base")
    with open(p / "cases" / "c04_yield.gd", "a") as f:
        f.write("# edited\n")
    r = assert_contract(lint(p, "--changed"))
    assert finding_set(r) == YIELD_ROW, str(r)
    assert r.stats["files"].startswith("1 .gd")
    write(p, "cases/new.gd", CASES["c25_deg2rad"][0])           # untracked counts too
    r2 = assert_contract(lint(p, "--changed"))
    assert finding_set(r2) == YIELD_ROW | {("res://cases/new.gd", 3, "fn-deg2rad", "error")}, str(r2)


def test_ac_03_21_changed_with_nothing_changed_is_clean(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    _git(p, "init", "-q")
    _git(p, "add", "-A")
    _git(p, "commit", "-q", "-m", "base")
    r = assert_contract(lint(p, "--changed"))
    assert r.rc == 0 and r.run_json()["findings_total"] == 0, str(r)


def test_ac_03_21_hook_mode_reports_lsp_stat_and_no_invocations(tmp_path):
    p = fresh(tmp_path, "godot3_scripts")
    r = assert_contract(lint(p, "--hook", "cases/c04_yield.gd", cwd=p, env={"HARNESS_CACHE": str(tmp_path / "cache")}))
    assert r.rc == 1 and finding_set(r) == YIELD_ROW
    assert r.stats.get("lsp") == "not running", r.stats
    assert r.invocations() == []


# ---- AC-03.6 hook speed ------------------------------------------------------------------------------------
def _clean_script(n_lines: int, tag: str = "") -> str:
    out = ["extends Node", ""]
    i = 0
    while len(out) + 4 <= n_lines:
        out += [f"func step{tag}_{i}(a: int) -> int:", f"\tvar b: int = a + {i}", "\treturn b", ""]
        i += 1
    return "\n".join(out) + "\n"


def test_ac_03_6_hook_median_wall_le_300ms(tmp_path):
    p = fresh(tmp_path)
    txt = _clean_script(300)
    assert 295 <= len(txt.splitlines()) <= 302
    write(p, "scripts/long.gd", txt)
    env = {"HARNESS_OUT": str(tmp_path / "out"), "HARNESS_CACHE": str(tmp_path / "cache")}
    warm = run_h("lint", "--hook", "--project", p, "scripts/long.gd", cwd=p, env=env)
    assert_contract(warm)
    assert warm.rc == 0, str(warm)
    walls = []
    for _ in range(5):
        r = run_h("lint", "--hook", "--project", p, "scripts/long.gd", cwd=p, env=env)
        assert r.rc == 0
        walls.append(r.wall)
    med = statistics.median(walls)
    assert med <= 0.300, f"median hook wall {med:.3f}s > 0.3s; walls={[round(w, 3) for w in walls]}"
    assert_contract(r)


# ---- AC-03.7 full speed (slow) -----------------------------------------------------------------------------
@pytest.mark.slow
def test_ac_03_7_thousand_files_within_4s(tmp_path):
    p = fresh(tmp_path)
    for i in range(1000):
        write(p, f"bulk/f{i // 100}/m{i}.gd", _clean_script(100, str(i)))
    r = lint(p)
    assert_contract(r)
    assert r.rc == 0 and r.stats["files"].startswith("1005 .gd"), str(r)
    assert r.wall <= 4.0, f"{r.wall:.2f}s for 1000 files"
    assert r.invocations() == []
