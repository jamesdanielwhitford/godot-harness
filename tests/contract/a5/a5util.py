"""A5 contract-test utilities (scenario variants, hand-built goldens). Uses the shared helpers; does not replace them."""
import hashlib
import json
from pathlib import Path

from helpers.h import run_h

JUMP = "res://scenarios/jump.json"
MOVER = "res://scenarios/mover.json"


def hr(project, *args, env=None, timeout=240, check=True):
    """`h run <args> --project <project>`; asserts the stdout/run-dir contract (unless check=False)."""
    r = run_h("run", *[str(a) for a in args], "--project", str(project), env=env, timeout=timeout)
    if check:
        assert_contract(r)
    return r


def multi_check_lines(r):
    """[(status, name, detail)] for lines like `OK   res://scenarios/a.json: 6/6 asserts, hash ...`."""
    import re
    out = []
    for ln in r.lines:
        m = re.match(r"^(OK|FAIL|WARN|SKIP) +(\S+\.json): (.*)$", ln)
        if m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def load_json(path):
    return json.loads(Path(path).read_text())


def write_variant(project, name, mutate, base="jump.json"):
    """Copy scenarios/<base> to scenarios/<name> after `mutate(dict)`; return the res:// path."""
    p = Path(project) / "scenarios" / base
    d = json.loads(p.read_text())
    mutate(d)
    out = Path(project) / "scenarios" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=2) + "\n")
    return "res://scenarios/" + name


def wrong_variant(d):
    """jump.json variant whose `player.position.x ge 400 @tick 100` assert fails (no teleport; tick-90 assert dropped)."""
    d["commands"] = []
    d["asserts"] = [a for a in d["asserts"] if a.get("tick") != 90]
    d["asserts"].append({"tick": 100, "path": "player.position.x", "op": "ge", "value": 400})


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mover_golden(project, scenario_rel="scenarios/mover.json", *, n600=600, bogus_hashes=True, stale=False,
                 ticks=600):
    """Hand-written golden for mover.json (n = k, x = 1.5 k at tick k). Checkpoints 0, 60, ..., `ticks`.

    bogus_hashes: final/chain hashes are zeros, so the hash comparison cannot match and values are compared.
    n600: value of mover.n at the last checkpoint (599 gives the off-by-one mismatch of AC-05.18).
    """
    src = Path(project) / scenario_rel
    sha = sha256_file(src)
    if stale:
        sha = "0" * 64
    cps = []
    for k in range(0, ticks + 1, 60):
        n = n600 if k == ticks else k
        cps.append({"tick": k, "hash": "0" * 64, "entities": {"mover": {"n": n, "x": 1.5 * k}}})
    g = {"schema": "harness.golden/1", "scenario_sha256": sha, "recorded_at": "2026-10-15T00:00:00Z",
         "meta": {}, "final_hash": "0" * 64, "chain_hash": "0" * 64, "tol": 0.001, "checkpoints": cps}
    out = src.parent / (src.stem + ".golden.json")
    out.write_text(json.dumps(g, indent=2) + "\n")
    return out
