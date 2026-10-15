"""P0 contract: shim, dispatcher, common flags, project resolution, run dir (AC-00.1-10). Layer: contract."""
import re
import time
from pathlib import Path

import pytest

from helpers.h import (FIXTURES, REPO, assert_contract, copy_fixture, run_h, verbs_in_tree, verbs_under_test)

CLOSED_VERBS = {"doctor", "sync", "import", "api", "check", "lint", "digest", "scene-gen", "scene-edit", "test", "run",
                "trace", "shot", "baseline", "lsp", "selftest", "init"}
VERBS = verbs_under_test()


def out_env(tmp_path):
    return {"HARNESS_OUT": str(tmp_path / "out")}


def test_ac_00_1_help_lists_every_verb_fast():
    walls = []
    for _ in range(3):
        r = run_h("--help")
        walls.append(r.wall)
    assert r.rc == 0
    assert_contract(r, nodir=True, help_output=True)
    assert len(r.lines) <= 40
    assert r.lines[0] == "usage: h <verb> [args]"
    listed = {}
    for ln in r.lines[1:]:
        m = re.match(r"^  (\S+)  (\S.*)$", ln)
        assert m, f"help line does not match '  <verb>  <HELP>': {ln!r}"
        listed[m.group(1)] = m.group(2)
        assert len(m.group(2)) <= 70, f"HELP over 70 chars: {ln!r}"
    for v in set(verbs_in_tree()) | {"doctor", "sync", "import", "api", "check", "selftest"}:
        assert v in listed, f"verb {v} missing from `h --help`: {sorted(listed)}"
    assert set(listed) <= CLOSED_VERBS, f"verbs outside the closed v0 list: {set(listed) - CLOSED_VERBS}"
    assert min(walls) <= 0.5, f"h --help took {walls}"


def test_ac_00_2_unknown_verb_one_line_rc_2():
    r = run_h("nosuchverb")
    assert r.rc == 2
    assert_contract(r, nodir=True)
    assert len(r.lines) == 1, r.stdout
    assert re.match(r"^ERROR h unknown verb 'nosuchverb'", r.lines[0])


def test_ac_00_2_unknown_verb_suggests_close_name():
    r = run_h("chek")
    assert r.rc == 2 and len(r.lines) == 1
    assert "(did you mean 'check'?)" in r.lines[0]


def test_ac_00_2_bare_h_prints_usage_rc_2():
    r = run_h()
    assert r.rc == 2
    assert r.lines[0] == "usage: h <verb> [args]"
    assert not r.stderr.strip()


@pytest.mark.parametrize("verb", VERBS)
@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_ac_00_3_verb_help_is_short_and_makes_no_run_dir(verb, flag, tmp_path):
    r = run_h(verb, flag, cwd=tmp_path, env=out_env(tmp_path))
    assert r.rc == 0, r
    assert 0 < len(r.lines) <= 40
    assert "usage" in r.stdout.lower(), "--help prints usage text"
    assert not re.match(r"^(OK|FAIL|SKIP|WARN|PASS|ERROR) ", r.lines[0]), "--help must not run the verb"
    assert_contract(r, nodir=True, help_output=True)
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir()), "--help must not create a run dir"
    assert not (tmp_path / ".harness").exists()


@pytest.mark.parametrize("verb", VERBS)
def test_ac_00_4_unknown_flag_is_a_usage_error(verb, tmp_path, mkproj):
    p = mkproj()
    r = run_h(verb, "--project", p, "--no-such-flag", cwd=tmp_path, env=out_env(tmp_path))
    assert r.rc == 2, r
    assert re.match(rf"^ERROR {re.escape(verb)} usage: ", r.lines[0]), r.lines[0]
    assert r.lines[-1].startswith("log: ")
    assert_contract(r)


def test_ac_00_6_run_dir_contents(mkproj):
    p = mkproj()
    r = run_h("check", "--project", p, timeout=120)
    assert_contract(r)
    run = r.run_json()
    assert re.match(r"^\d{8}T\d{6}Z-check-[0-9a-f]{4}$", run["run_id"])
    assert r.log_dir.resolve().parent == (p / ".harness" / "out").resolve()
    assert (p / ".harness" / ".gdignore").exists()
    assert (r.log_dir.parent / "latest").resolve() == r.log_dir.resolve()
    assert (r.log_dir / "godot").is_dir() or run["invocations"] == []
    for inv in run["invocations"]:
        assert (r.log_dir / inv["log"]).exists() or Path(inv["log"]).exists()
    r2 = run_h("check", "--project", p, timeout=120)
    assert_contract(r2)
    assert r2.log_dir != r.log_dir
    assert (r2.log_dir.parent / "latest").resolve() == r2.log_dir.resolve()
    assert r.log_dir.exists(), "older run dir is kept"


def test_ac_00_7_harness_out_overrides_run_dir_root(mkproj, tmp_path):
    p = mkproj()
    out = tmp_path / "elsewhere"
    r = run_h("check", "--project", p, env={"HARNESS_OUT": str(out)}, timeout=120)
    assert_contract(r)
    assert r.log_dir.resolve().parent == out.resolve()
    assert not (p / ".harness" / "out").exists()


def test_ac_00_7_harness_out_also_applies_to_projectless_verbs(tmp_path):
    out = tmp_path / "o"
    r = run_h("doctor", env={"HARNESS_OUT": str(out)})
    assert_contract(r)
    assert r.log_dir.resolve().parent == out.resolve()


def test_ac_00_8_project_flag_relative_to_other_cwd(mkproj, tmp_path):
    p = mkproj()
    r = run_h("import", "--project", "proj", cwd=tmp_path, env=out_env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0 and Path(r.stats["project"]).resolve() == p.resolve()


def test_ac_00_8_harness_project_env(mkproj, tmp_path):
    p = mkproj()
    other = tmp_path / "elsewhere"
    other.mkdir()
    r = run_h("import", cwd=other, env={"HARNESS_PROJECT": str(p), "HARNESS_OUT": str(tmp_path / "out")}, timeout=120)
    assert_contract(r)
    assert r.rc == 0 and Path(r.stats["project"]).resolve() == p.resolve()


def test_ac_00_8_cwd_inside_project_subdir(mkproj, tmp_path):
    p = mkproj()
    r = run_h("import", cwd=p / "scripts", env=out_env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0 and Path(r.stats["project"]).resolve() == p.resolve()


def test_ac_00_8_no_project_is_rc_2(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    r = run_h("import", cwd=empty, env=out_env(tmp_path))
    assert r.rc == 2
    assert re.match(r"^ERROR import no Godot project", r.lines[0]), r.lines[0]
    assert_contract(r)


def test_ac_00_8_dir_without_project_godot_is_rc_2(tmp_path):
    d = tmp_path / "notproj"
    d.mkdir()
    r = run_h("import", "--project", d, env=out_env(tmp_path))
    assert r.rc == 2 and "no Godot project" in r.lines[0]
    assert_contract(r)


def test_ac_00_9_unknown_key_in_harness_toml(mkproj, tmp_path):
    p = mkproj()
    (p / "harness.toml").write_text("[harness]\ntick_rat = 60\n")
    r = run_h("check", "--project", p, env=out_env(tmp_path))
    assert r.rc == 2 and r.verdict == "ERROR"
    assert_contract(r)
    assert r.has_finding(rule="harness.config", path="res://harness.toml", severity="error", msg_re="tick_rat")
    assert "tick_rat" in r.stdout


def test_ac_00_9_invalid_toml(mkproj, tmp_path):
    p = mkproj()
    (p / "harness.toml").write_text("[harness\nthis is not toml = =\n")
    r = run_h("check", "--project", p, env=out_env(tmp_path))
    assert r.rc == 2
    assert_contract(r)
    assert r.has_finding(rule="harness.config", path="res://harness.toml")


@pytest.mark.parametrize("text", ["[bogus_table]\nx = 1\n", "[harness]\ntick_rate = \"sixty\"\n"])
def test_ac_00_9_unknown_table_and_wrong_type(mkproj, tmp_path, text):
    p = mkproj()
    (p / "harness.toml").write_text(text)
    r = run_h("check", "--project", p, env=out_env(tmp_path))
    assert r.rc == 2
    assert_contract(r)
    assert r.has_finding(rule="harness.config", path="res://harness.toml")


def test_ac_00_9_no_toml_means_defaults(mkproj, tmp_path):
    p = mkproj()
    assert not (p / "harness.toml").exists()
    r = run_h("import", "--project", p, env=out_env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0


def test_ac_00_9_valid_toml_is_accepted(mkproj, tmp_path):
    p = mkproj()
    (p / "harness.toml").write_text('[harness]\nschema = 1\ntick_rate = 60\nrenderer = "gl_compatibility"\n\n[scan]\nignore = ["^SOME_BENIGN_NOISE"]\n')
    r = run_h("import", "--project", p, env=out_env(tmp_path), timeout=120)
    assert_contract(r)
    assert r.rc == 0, r


@pytest.mark.parametrize("pattern", ["SCRIPT ERROR", "ERROR", "^SCRIPT ERROR: Parse Error", ".*"])
def test_ac_00_10_scan_ignore_may_not_match_protected_lines(mkproj, tmp_path, pattern):
    p = mkproj()
    (p / "harness.toml").write_text(f'[scan]\nignore = ["{pattern}"]\n')
    r = run_h("check", "--project", p, env=out_env(tmp_path))
    assert r.rc == 2, r
    assert_contract(r)
    assert r.has_finding(rule="harness.config", path="res://harness.toml")


def test_ac_00_11_missing_godot_binary(mkproj, tmp_path):
    p = mkproj()
    r = run_h("check", "--project", p, env={**out_env(tmp_path), "HARNESS_GODOT": "/nonexistent/godot"})
    assert r.rc == 4 and re.match(r"^ERROR check godot binary not found", r.lines[0]), r.lines[0]
    assert "run tools/bootstrap.sh" in r.lines[0]
    assert r.wall <= 2.0, f"took {r.wall:.1f}s"
    assert_contract(r)


def test_ac_00_12_wrong_godot_version(mkproj, tmp_path):
    p = mkproj()
    fake = FIXTURES / "bin" / "godot_wrong_version"
    r = run_h("check", "--project", p, env={**out_env(tmp_path), "HARNESS_GODOT": str(fake),
                                            "HARNESS_CACHE": str(tmp_path / "cache")})
    assert r.rc == 4 and r.verdict == "ERROR", r
    assert_contract(r)
    assert r.has_finding(rule="harness.godot-version", severity="error")


def test_ac_00_19_timeout_scale_halves_timeouts(mkproj, tmp_path):
    base = {"version": 20, "import": 180, "check_only": 30, "runner": 60, "smoke": 30, "test": 300, "scenario": 120,
            "shot": 60, "movie": 300, "doctool": 120, "oracle": 60, "lsp_start": 30}
    p = mkproj()
    r = run_h("check", "--project", p, env={**out_env(tmp_path), "HARNESS_TIMEOUT_SCALE": "0.5"}, timeout=120)
    assert_contract(r)
    invs = r.invocations()
    assert invs, "check on a fresh copy must start at least the import and runner invocations"
    for inv in invs:
        assert inv["timeout_s"] == pytest.approx(base[inv["kind"]] * 0.5), inv


@pytest.mark.parametrize("scale", ["50", "0.05", "abc"])
def test_ac_00_19_out_of_range_scale_is_usage_error(mkproj, tmp_path, scale):
    p = mkproj()
    r = run_h("check", "--project", p, env={**out_env(tmp_path), "HARNESS_TIMEOUT_SCALE": scale})
    assert r.rc == 2 and r.verdict == "ERROR", r
    assert_contract(r)


def test_ac_00_20_godot_argv_in_run_json(mkproj, tmp_path):
    p = mkproj()
    r = run_h("check", "--project", p, env=out_env(tmp_path), timeout=120)
    assert_contract(r)
    invs = r.invocations()
    assert invs
    expected_bin = (REPO / "tools" / "bin" / "godot")
    for inv in invs:
        argv = inv["argv"]
        assert Path(argv[0]).resolve() == expected_bin.resolve(), argv[:2]
        assert "--headless" in argv
        i = argv.index("--path")
        assert Path(argv[i + 1]).resolve() == p.resolve()
        assert Path(argv[i + 1]).is_absolute()
