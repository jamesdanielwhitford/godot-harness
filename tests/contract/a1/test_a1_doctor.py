"""A1 contract: doctor extras (AC-01.25). Layer: contract. Base doctor behaviour is in tests/contract/p0."""
from helpers.h import assert_contract, run_h


def env_out(tmp_path):
    return {"HARNESS_OUT": str(tmp_path / "out")}


def test_ac_01_25_doctor_has_an_api_check_that_never_decides_the_verdict(tmp_path):
    r = run_h("doctor", env=env_out(tmp_path))
    assert_contract(r)
    api = r.check("api")
    assert api is not None, r.stdout
    assert api[0] in ("OK", "SKIP")
    assert r.rc == 0


def test_ac_01_25_project_adds_sync_and_import_lines(mkproj, tmp_path):
    p = mkproj()
    s = run_h("sync", "--no-gdunit", "--project", p, env=env_out(tmp_path))
    assert s.rc == 0, s
    r = run_h("doctor", "--project", p, env=env_out(tmp_path))
    assert_contract(r)
    assert r.check("sync") is not None, r.stdout
    imp = r.check("import")
    assert imp is not None and imp[0] == "WARN" and imp[2].startswith("stale (no .godot/)"), r.stdout
    assert r.rc == 5 and r.verdict == "WARN", r


def test_ac_01_25_imported_project_reports_import_ok(mkwarm, tmp_path):
    p = mkwarm()
    r = run_h("doctor", "--project", p, env=env_out(tmp_path))
    assert_contract(r)
    imp = r.check("import")
    assert imp is not None and imp[0] == "OK" and imp[2] == "fresh", r.stdout


def test_ac_01_25_strict_turns_warn_into_fail(mkproj, tmp_path):
    p = mkproj()
    r = run_h("doctor", "--project", p, "--strict", env=env_out(tmp_path))
    assert_contract(r)
    assert r.rc == 1 and r.verdict == "FAIL", r


def test_ac_01_30_help_of_every_a1_verb(tmp_path):
    for v in ("check", "import", "sync", "api", "doctor", "selftest"):
        r = run_h(v, "--help", cwd=tmp_path, env=env_out(tmp_path))
        assert r.rc == 0 and 0 < len(r.lines) <= 40, (v, r)
