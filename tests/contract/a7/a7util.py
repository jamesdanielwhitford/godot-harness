"""Plain helpers for the A7 contract tests (owner: T7). Shared helpers stay in tests/helpers/h.py."""
from __future__ import annotations

import json
from pathlib import Path

from helpers.h import assert_contract, run_h

SUITE = "res://feel/player.feel.json"
# measurement names of the fixture suite, in suite order (spec 6)
ALL_METRICS = [
    "run.max_speed", "run.accel_time", "run.decel_time",
    "jump.apex_px", "jump.time_to_apex", "jump.fall_rise_ratio",
    "jump.tap_apex_px", "jump.coyote_window", "jump.buffer_window",
    "camera.settle_time", "camera.lag_px", "jump.cut_ratio",
]
TARGETED = [m for m in ALL_METRICS if m != "jump.tap_apex_px"]
AGENT_LINE = "The agent measured these numbers; it did not judge feel."


def trace(proj, *args, timeout=240, env=None):
    """`h trace ... --project proj`, always checked against the output contract."""
    r = run_h("trace", *args, "--project", proj, timeout=timeout, env=env)
    assert_contract(r)
    return r


def metrics_json(r) -> dict:
    return json.loads(r.artifact("metrics.json").read_text())


def report_text(r) -> str:
    return r.artifact("feel_report.md").read_text()


def edit_suite(proj, fn, name="feel/player.feel.json"):
    p = Path(proj) / name
    d = json.loads(p.read_text())
    fn(d)
    p.write_text(json.dumps(d, indent=2) + "\n")


def edit_text(proj, rel, old, new, count=1):
    p = Path(proj) / rel
    t = p.read_text()
    assert t.count(old) == count, f"{rel}: {old!r} matched {t.count(old)}x, want {count}"
    p.write_text(t.replace(old, new))


def replay_kinds(r) -> list:
    """Godot invocations of kind scenario/movie recorded in run.json (rc 2 suite errors must have none)."""
    return [i["kind"] for i in r.invocations() if i["kind"] in ("scenario", "movie")]
