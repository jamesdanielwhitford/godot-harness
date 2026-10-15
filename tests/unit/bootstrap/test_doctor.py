import os
import subprocess
from pathlib import Path

H = Path(__file__).resolve().parents[3] / "tools" / "harness" / "h"


def run_h(*args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([str(H), *args], capture_output=True, text=True, timeout=60, env=e)


def test_doctor_fails_when_cache_missing(tmp_path):
    r = run_h("doctor", env={"HARNESS_CACHE": str(tmp_path)})
    assert r.returncode != 0
    assert "FAIL gdunit4" in r.stdout and "FAIL odiff" in r.stdout


def test_doctor_reports_every_check(tmp_path):
    r = run_h("doctor", env={"HARNESS_CACHE": str(tmp_path)})
    for name in ("godot", "gdunit4", "odiff", "venv", "xvfb-run", "compare"):
        assert f" {name}:" in r.stdout


def test_doctor_passes_after_bootstrap():
    r = run_h("doctor")
    assert r.returncode == 0, r.stdout
    assert "doctor: ok" in r.stdout


def test_unknown_verb():
    assert run_h("nope").returncode == 2
