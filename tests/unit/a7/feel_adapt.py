"""Tolerant adapter around `harness.feel` for the A7 unit tests (owner: T7).

The spec (07_feel.md 2.5, REVIEW R-01) names the public functions `read_trace, measure, window, rate_spread, judge,
is_approved` but fixes no signatures [U]. Every call below tries a short list of plausible call forms, so a builder
that chose a different but sensible shape fails here only if NONE of the forms fit. The result normaliser accepts a
number, a dict, an object with attributes, or a tuple. Assumed shapes are listed in .claude/handoff/A7/test_notes.md.
"""
from __future__ import annotations

import shutil
from pathlib import Path

CSV_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "feel_csv"


class Undefined(Exception):
    pass


def _feel():
    from harness import feel  # noqa: PLC0415 (allowed by REVIEW R-01, unit layer only)
    return feel


def csv_copy(name: str, dest_dir: Path) -> Path:
    """Copy <name>.csv and <name>.meta.json into dest_dir (tests mutate copies, never the fixture)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("csv", "meta.json"):
        shutil.copy2(CSV_DIR / f"{name}.{ext}", dest_dir / f"{name}.{ext}")
    return dest_dir / f"{name}.csv"


def read(path: Path):
    return _feel().read_trace(str(path))


def _attempts(fn, variants):
    last = None
    for v in variants:
        try:
            return v()
        except TypeError as ex:  # wrong call form, try the next one
            last = ex
    raise last


def _get(res, *names):
    for n in names:
        if isinstance(res, dict) and n in res:
            return res[n]
        if hasattr(res, n):
            return getattr(res, n)
    return None


class Meas:
    def __init__(self, raw):
        self.raw = raw
        self.undefined = False
        self.reason = ""
        if isinstance(raw, (int, float)):
            self.value, self.unit, self.seconds = float(raw), None, None
            return
        if isinstance(raw, tuple) and raw and isinstance(raw[0], (int, float)):
            self.value = float(raw[0])
            self.unit = raw[1] if len(raw) > 1 else None
            self.seconds = raw[2] if len(raw) > 2 else None
            return
        v = _get(raw, "value")
        self.value = None if v is None else float(v)
        self.unit = _get(raw, "unit")
        s = _get(raw, "seconds")
        self.seconds = None if s is None else float(s)
        verdict = _get(raw, "verdict", "status")
        undef = _get(raw, "undefined")
        self.reason = str(_get(raw, "reason", "message") or "")
        if self.value is None or undef or (isinstance(verdict, str) and verdict.lower() == "undefined"):
            self.undefined = True


def measure(trace, metric: str, **params) -> Meas:
    fe = _feel()
    try:
        raw = _attempts(fe.measure, [
            lambda: fe.measure(trace, metric, dict(params)),
            lambda: fe.measure(trace, metric, **params),
            lambda: fe.measure(trace, metric, params=dict(params)),
        ])
    except TypeError:
        raise
    except Exception as ex:  # noqa: BLE001 - an undefined metric may be signalled by an exception
        m = Meas(0.0)
        m.undefined = True
        m.reason = f"{type(ex).__name__}: {ex}"
        return m
    return Meas(raw)


def window(offsets: dict):
    fe = _feel()
    res = fe.window(offsets)
    assert isinstance(res, (tuple, list)) and len(res) == 2, f"window() must return (width, gap): {res!r}"
    return int(res[0]), bool(res[1])


def spread(by_rate: dict, slack_s: float, base: int = 60) -> float:
    """Relative spread of per-rate values (seconds) with the given slack (seconds)."""
    fe = _feel()
    res = _attempts(fe.rate_spread, [
        lambda: fe.rate_spread(by_rate, base, slack_s),
        lambda: fe.rate_spread(by_rate, base=base, slack=slack_s),
        lambda: fe.rate_spread(by_rate, slack=slack_s),
        lambda: fe.rate_spread(by_rate, base, slack_s > 0),
        lambda: fe.rate_spread(by_rate, tick_metric=slack_s > 0),
        lambda: fe.rate_spread(by_rate),
    ])
    if isinstance(res, (tuple, list)):
        res = res[0]
    return float(res)


def judge_verdict(value: float, unit: str, rate: int, target: dict, seconds: float | None = None) -> str:
    """Returns a lower-case verdict word; an error is returned as 'error' (raise or verdict)."""
    fe = _feel()
    try:
        res = _attempts(fe.judge, [
            lambda: fe.judge(value, unit, rate, target, seconds),
            lambda: fe.judge(value, unit, rate, target),
            lambda: fe.judge({"value": value, "unit": unit, "seconds": seconds}, target, rate),
            lambda: fe.judge({"value": value, "unit": unit, "seconds": seconds}, target),
        ])
    except TypeError:
        raise
    except Exception:  # noqa: BLE001
        return "error"
    if isinstance(res, tuple):
        res = res[0]
    if isinstance(res, bool):
        return "pass" if res else "fail"
    w = _get(res, "verdict", "status")
    return str(w if w is not None else res).lower()


def is_approved(by: str, on: str) -> bool:
    fe = _feel()
    return bool(_attempts(fe.is_approved, [
        lambda: fe.is_approved(by, on),
        lambda: fe.is_approved({"approved_by": by, "approved_on": on}),
    ]))
