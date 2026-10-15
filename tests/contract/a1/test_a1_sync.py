"""A1 contract: `h sync` and the harness.sync library behaviour (AC-01.18). Layer: contract.
HARNESS_REPO points at a copy of tests/fixtures/harness_trees/sync_src and HARNESS_CACHE at a copy of gdunit_cache [U: the
shim must keep a HARNESS_REPO that is already set; the spec says tests drive it this way]."""
import json
import re
import shutil

import pytest

from helpers.h import FIXTURES, assert_contract, run_h, write

TREES = FIXTURES / "harness_trees"


@pytest.fixture
def env(tmp_path):
    repo = tmp_path / "harness_repo"
    cache = tmp_path / "cache"
    shutil.copytree(TREES / "sync_src", repo)
    shutil.copytree(TREES / "gdunit_cache", cache)
    return {"HARNESS_REPO": str(repo), "HARNESS_CACHE": str(cache), "HARNESS_OUT": str(tmp_path / "out"),
            "HARNESS_TMP": str(tmp_path / "ht")}


def sync(p, env, *args):
    return run_h("sync", "--project", p, *args, env=env)


def snapshot(p):
    return {str(f.relative_to(p)): f.read_bytes() for f in sorted(p.rglob("*")) if f.is_file()}


def test_ac_01_18_mirrors_harness_files_and_adds_autoload(mkproj, env):
    p = mkproj()
    r = sync(p, env, "--no-gdunit")
    assert_contract(r)
    assert r.rc == 0, r
    assert (p / "addons/harness/harness.gd").read_text() == (TREES / "sync_src/addons/harness/harness.gd").read_text()
    assert not (p / "addons/harness/runners").exists(), "runners/ must not be mirrored"
    pg = (p / "project.godot").read_text()
    assert re.search(r'^\[autoload\]\s*$', pg, re.M)
    assert 'Harness="*res://addons/harness/harness.gd"' in pg
    assert any(c[0] == "SKIP" and c[1] == "autoload Rng" and "not shipped" in c[2] for c in r.checks), r.checks
    meta = json.loads((p / "addons/harness/.sync.json").read_text())
    assert meta["schema"] == "harness.sync/1" and re.match(r"^[0-9a-f]{64}$", meta["source_hash"])
    assert meta["gdunit4_commit"] is None
    assert not (p / "addons/gdUnit4").exists(), "--no-gdunit must not install gdUnit4"


def test_ac_01_18_second_run_changes_nothing(mkproj, env):
    p = mkproj()
    assert sync(p, env, "--no-gdunit").rc == 0
    before = snapshot(p)
    r = sync(p, env, "--no-gdunit")
    assert_contract(r)
    assert r.rc == 0
    assert any(c[1] == "addons/harness" and "(0 changed)" in c[2] for c in r.checks), r.checks
    assert snapshot(p) == before, "second sync must be byte-identical (project.godot included)"


def test_ac_01_18_check_mode_reports_stale_and_writes_nothing(mkproj, env):
    p = mkproj()
    assert sync(p, env, "--no-gdunit").rc == 0
    ok = sync(p, env, "--no-gdunit", "--check")
    assert_contract(ok)
    assert ok.rc == 0, ok
    (p / "addons/harness/harness.gd").write_text("extends Node\n# edited\n")
    before = snapshot(p)
    r = sync(p, env, "--no-gdunit", "--check")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="harness.sync-stale", severity="error"), r
    assert snapshot(p) == before, "--check must not write"


def test_ac_01_18_conflicting_autoload_is_an_error_and_unchanged(mkproj, env):
    p = mkproj()
    pg = p / "project.godot"
    pg.write_text(pg.read_text() + '\n[autoload]\n\nHarness="*res://somewhere/else.gd"\n')
    before = pg.read_bytes()
    r = sync(p, env, "--no-gdunit")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="harness.sync-conflict", severity="error"), r
    assert pg.read_bytes() == before


def test_ac_01_18_autoload_inserted_after_last_key_of_existing_section(mkproj, env):
    p = mkproj()
    pg = p / "project.godot"
    pg.write_text(pg.read_text().replace("[rendering]", '[autoload]\n\nOther="*res://o.gd"\n\n[display]\n\nwindow/size/viewport_width=640\n\n[rendering]'))
    r = sync(p, env, "--no-gdunit")
    assert_contract(r)
    assert r.rc == 0, r
    lines = pg.read_text().splitlines()
    i_other = lines.index('Other="*res://o.gd"')
    assert lines[i_other + 1] == 'Harness="*res://addons/harness/harness.gd"', lines[i_other:i_other + 4]
    assert lines.index("[display]") > i_other + 1


def test_ac_01_18_already_listed_autoloads_leave_project_byte_identical(mkproj, env):
    p = mkproj()
    pg = p / "project.godot"
    pg.write_text(pg.read_text() + '\n[autoload]\n\nHarness="*res://addons/harness/harness.gd"\nSceneManager="*res://sm.gd"\n')
    before = pg.read_bytes()
    r = sync(p, env, "--no-gdunit")
    assert_contract(r)
    assert r.rc == 0
    assert pg.read_bytes() == before


def test_ac_01_18_gdunit4_is_copied_without_tests_and_uids(mkproj, env):
    p = mkproj()
    r = sync(p, env)
    assert_contract(r)
    assert r.rc == 0, r
    addon = p / "addons/gdUnit4"
    assert (addon / "plugin.cfg").exists() and (addon / "src/a.gd").exists()
    assert not (addon / "test").exists(), "test/ must not be copied"
    assert not list(addon.rglob("*.uid")), "*.uid must not be copied"
    assert any(c[0] == "OK" and c[1] == "gdunit4" for c in r.checks), r.checks


def test_ac_01_18_empty_cache_without_no_gdunit_is_environment_error(mkproj, env, tmp_path):
    p = mkproj()
    env = {**env, "HARNESS_CACHE": str(tmp_path / "emptycache")}
    r = sync(p, env)
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r
    assert "gdUnit4 not in cache" in r.stdout or r.has_finding(msg_re="gdUnit4 not in cache") or "gdUnit4" in r.lines[0]


def _own_gdunit(p, version):
    write(p, "addons/gdUnit4/plugin.cfg", f'[plugin]\n\nname="gdUnit4"\nversion="{version}"\nscript="plugin.gd"\n')
    write(p, "addons/gdUnit4/own_file.gd", "extends Node\n")


def test_ac_01_18_users_own_gdunit4_at_another_version_is_never_overwritten(mkproj, env):
    p = mkproj()
    _own_gdunit(p, "6.0.0")
    before = snapshot(p / "addons/gdUnit4")
    r = sync(p, env)
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r
    assert "harness pins 6.2.2" in r.stdout, r.stdout
    assert snapshot(p / "addons/gdUnit4") == before


def test_ac_01_18_harness_installed_gdunit4_is_overwritten_on_pin_change(mkproj, env):
    p = mkproj()
    _own_gdunit(p, "6.0.0")
    write(p, "addons/harness/.sync.json",
          json.dumps({"schema": "harness.sync/1", "source_hash": "0" * 64, "gdunit4_commit": "0127a55f4543dfc24746f6e5c7ba6f94105d51f2"}))
    r = sync(p, env)
    assert_contract(r)
    assert r.rc == 0, r
    assert 'version="6.2.2"' in (p / "addons/gdUnit4/plugin.cfg").read_text()
    assert not (p / "addons/gdUnit4/test").exists()
