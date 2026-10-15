"""AC-09.21 [e2e, slow, needs network]: a fresh clone under $HARNESS_TMP bootstraps, then `h check`, `h test` and
`h run sample/scenarios/ --twice` (all `--project sample`) exit 0, and the clone's `git status --porcelain sample`
stays empty (generated dirs are git-ignored; `.uid` files are committed). Clones the committed HEAD of this repo."""
import os
import subprocess
from pathlib import Path

import pytest

from helpers.h import REPO


@pytest.mark.slow
@pytest.mark.godot
def test_ac_09_21_fresh_clone_runs_the_sample(tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(REPO), str(clone)], check=True, capture_output=True, timeout=300)
    assert (clone / "sample" / "project.godot").is_file(), "sample/ is not committed in HEAD"
    cache = os.environ.get("HARNESS_CACHE")
    env = dict(os.environ, HARNESS_TMP=str(tmp_path / "ht"))
    for k in ("HARNESS_GODOT", "HARNESS_OUT", "HARNESS_PROJECT", "HARNESS_REPO", "HARNESS_ROOT"):
        env.pop(k, None)
    if cache:
        env["HARNESS_CACHE"] = cache
    p = subprocess.run(["bash", str(clone / "tools" / "bootstrap.sh")], cwd=clone, env=env, capture_output=True,
                       text=True, timeout=1500)
    assert p.returncode == 0, (p.stdout + p.stderr)[-2000:]
    h = str(clone / "tools" / "harness" / "h")
    for args in (["check"], ["test"], ["run", "sample/scenarios/", "--twice"]):
        q = subprocess.run([h, *args, "--project", str(clone / "sample")], cwd=clone, env=env, capture_output=True,
                           text=True, timeout=900, stdin=subprocess.DEVNULL)
        assert q.returncode == 0, f"h {' '.join(args)} rc={q.returncode}\n{q.stdout}{q.stderr}"
        assert q.stdout.startswith("PASS"), q.stdout[:300]
    st = subprocess.run(["git", "status", "--porcelain", "sample"], cwd=clone, capture_output=True, text=True)
    assert st.stdout.strip() == "", f"verbs dirtied the tree:\n{st.stdout}"
