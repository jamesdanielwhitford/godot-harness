"""A1 contract: `h api` (AC-01.19-24). Layer: contract. The index is built once per module into a temp HARNESS_CACHE
(`h api --rebuild`), so these tests never depend on the developer's cache."""
import re

import pytest

from helpers.h import GODOT_VERSION, assert_contract, run_h


@pytest.fixture(scope="module")
def api_env(tmp_path_factory):
    """Returns a callable; the index is built on first call so a failing rebuild fails the test, not the setup."""
    cache = {}

    def _get():
        if "env" not in cache:
            base = tmp_path_factory.mktemp("api")
            env = {"HARNESS_CACHE": str(base / "cache"), "HARNESS_TMP": str(base / "ht"), "HARNESS_OUT": str(base / "out")}
            r = run_h("api", "--rebuild", env=env, timeout=180)
            assert r.rc == 0, f"`h api --rebuild` failed:\n{r}"
            cache["env"] = env
        return cache["env"]

    return _get


def api(env, *args, timeout=60):
    return run_h("api", *args, env=env() if callable(env) else env, timeout=timeout)


def test_ac_01_19_property_signature(api_env):
    r = api(api_env, "Node2D.position")
    assert_contract(r)
    assert r.rc == 0 and r.verdict == "PASS" and r.verb == "api", r
    assert r.stats["sig"] == "var position: Vector2"
    assert r.stats["kind"] == "property"
    assert r.wall <= 0.5, f"{r.wall:.2f}s"


def test_ac_01_19_inherited_member_reports_defining_class(api_env):
    r = api(api_env, "CharacterBody2D.position")
    assert_contract(r)
    assert r.rc == 0 and r.stats.get("defined-in") == "Node2D", r.stats


def test_ac_01_19_method_with_default_arguments(api_env):
    r = api(api_env, "Input.is_action_just_pressed")
    assert_contract(r)
    assert r.rc == 0 and "exact_match: bool = false" in r.stats["sig"], r.stats


def test_ac_01_19_gdscript_function_annotation_and_constant(api_env):
    r = api(api_env, "preload")
    assert_contract(r)
    assert r.rc == 0 and r.stats["kind"] == "function"
    r = api(api_env, "@export_range")
    assert_contract(r)
    assert r.rc == 0 and r.stats["kind"] == "annotation"
    r = api(api_env, "KEY_A")
    assert_contract(r)
    assert r.rc == 0 and r.stats["kind"] == "constant"


def test_ac_01_19_class_lists_inheritance_and_member_counts(api_env):
    r = api(api_env, "CharacterBody2D")
    assert_contract(r)
    assert r.rc == 0 and r.stats["kind"] == "class"
    assert "Node2D" in r.stats["inherits"] and r.stats["inherits"].endswith("Object"), r.stats
    assert re.match(r"^\d+ methods, \d+ properties, \d+ signals$", r.stats["members"]), r.stats


def test_ac_01_20_renamed_class(api_env):
    r = api(api_env, "KinematicBody2D")
    assert_contract(r)
    assert r.rc == 1 and r.verdict == "FAIL"
    assert "not in Godot 4.7" in r.lines[0]
    assert r.stats.get("suggest") == "CharacterBody2D"
    assert r.has_finding(rule="api.renamed", severity="error")


def test_ac_01_20_typo_gets_did_you_mean(api_env):
    r = api(api_env, "Node2D.positon")
    assert_contract(r)
    assert r.rc == 1
    f = [x for x in r.findings_jsonl() if x["rule"] == "api.not-found"]
    assert f and "Node2D.position" in (f[0]["hint"] or ""), f


def test_ac_01_20_renamed_member(api_env):
    r = api(api_env, "Control.rect_position")
    assert_contract(r)
    assert r.rc == 1
    assert any("position" in ((x["hint"] or "") + x["message"]) for x in r.findings_jsonl())
    assert r.has_finding(rule="api.renamed")


def test_ac_01_20_unknown_name_has_no_suggestion(api_env):
    r = api(api_env, "Frobnicator")
    assert_contract(r)
    assert r.rc == 1 and r.has_finding(rule="api.not-found")
    assert "suggest" not in r.stats


def test_ac_01_21_exists_pass_is_two_lines(api_env):
    r = api(api_env, "--exists", "Node2D.position")
    assert_contract(r)
    assert r.rc == 0 and len(r.lines) == 2, r.stdout
    assert r.lines[1].startswith("log: ")
    assert r.wall <= 0.5, f"{r.wall:.2f}s"


def test_ac_01_21_exists_fail_is_three_lines(api_env):
    r = api(api_env, "--exists", "Node2D.nope")
    assert_contract(r)
    assert r.rc == 1 and len(r.lines) == 3, r.stdout
    assert r.lines[0].startswith("FAIL api")
    assert re.match(r"^-: \[api\.not-found\] error: Node2D\.nope does not exist in Godot 4\.7", r.lines[1]), r.lines[1]
    assert r.lines[2].startswith("log: ")
    assert r.wall <= 0.5, f"{r.wall:.2f}s"


def test_ac_01_21_exists_renamed_is_three_lines(api_env):
    r = api(api_env, "--exists", "KinematicBody2D")
    assert_contract(r)
    assert r.rc == 1 and len(r.lines) == 3, r.stdout
    assert "[api.renamed]" in r.lines[1]


def test_ac_01_22_search_finds_member_and_caps_output(api_env):
    r = api(api_env, "--search", "move_and")
    assert_contract(r)
    assert r.rc == 0 and len(r.lines) <= 40
    assert any(m.startswith("CharacterBody2D.move_and_slide") for m in r.stat_all("match")), r.stdout
    r = api(api_env, "--search", "move", "--limit", "5")
    assert_contract(r)
    assert len(r.stat_all("match")) <= 5
    assert "more" in r.stats, "more hits than the limit must end with a `more:` stat"


def test_ac_01_22_class_all_members_is_capped(api_env):
    r = api(api_env, "Node", "--all")
    assert_contract(r)
    assert len(r.lines) <= 40
    assert "more" in r.stats


def test_ac_01_23_rebuild_into_empty_cache(tmp_path):
    env = {"HARNESS_CACHE": str(tmp_path / "cache"), "HARNESS_TMP": str(tmp_path / "ht"), "HARNESS_OUT": str(tmp_path / "out")}
    r = run_h("api", "--rebuild", env=env, timeout=120)
    assert_contract(r)
    assert r.rc == 0, r
    d = tmp_path / "cache" / "api" / GODOT_VERSION
    for f in ("extension_api.json", "@GDScript.xml", "index.json"):
        assert (d / f).is_file(), f"{f} missing in {d}"
    assert r.wall <= 20, f"{r.wall:.1f}s"
    ht = tmp_path / "ht"
    assert not ht.exists() or not any(ht.iterdir()), f"scratch dir left in HARNESS_TMP: {list(ht.iterdir())}"
    invs = r.invocations()
    assert invs and all(i["kind"] == "doctool" for i in invs), [i["kind"] for i in invs]
    assert all("--path" not in i["argv"] for i in invs), "doctool/dump runs must not pass --path (R-05)"


def test_ac_01_24_missing_godot_with_no_index_is_rc_4(tmp_path):
    env = {"HARNESS_CACHE": str(tmp_path / "cache"), "HARNESS_OUT": str(tmp_path / "out"),
           "HARNESS_GODOT": "/nonexistent/godot"}
    r = run_h("api", "--rebuild", env=env)
    assert_contract(r)
    assert r.rc == 4 and r.verdict == "ERROR", r


def test_ac_01_24_lookup_needs_no_godot_once_the_index_exists(api_env):
    r = api({**api_env(), "HARNESS_GODOT": "/nonexistent/godot"}, "Node2D")
    assert_contract(r)
    assert r.rc == 0, r
    assert r.invocations() == []
