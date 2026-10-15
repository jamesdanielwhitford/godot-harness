"""AC-01.29: a fresh clone's bootstrap leaves the API index in an empty HARNESS_CACHE. Layer: e2e, slow, needs network.
Clones the committed HEAD of this repo (the orchestrator commits before the verifier runs)."""
import os
import subprocess
from pathlib import Path

import pytest

from helpers.h import GODOT_VERSION, REPO


@pytest.mark.slow
@pytest.mark.godot
def test_ac_01_29_bootstrap_builds_api_index(tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(REPO), str(clone)], check=True, capture_output=True, timeout=300)
    cache = tmp_path / "cache"
    env = dict(os.environ, HARNESS_CACHE=str(cache), HARNESS_TMP=str(tmp_path / "ht"))
    for k in ("HARNESS_GODOT", "HARNESS_OUT", "HARNESS_PROJECT", "HARNESS_REPO"):
        env.pop(k, None)
    p = subprocess.run(["bash", str(clone / "tools" / "bootstrap.sh")], cwd=clone, env=env, capture_output=True,
                       text=True, timeout=1500)
    out = p.stdout + p.stderr
    assert p.returncode == 0, out[-2000:]
    api = cache / "api" / GODOT_VERSION
    assert (api / "@GDScript.xml").is_file(), out[-2000:]
    assert (api / "index.json").is_file(), out[-2000:]
    assert "WARN: api" not in out
