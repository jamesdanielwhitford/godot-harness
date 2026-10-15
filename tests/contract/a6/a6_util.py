"""A6 contract-test utilities (T6): PNG reading, odiff calls, a tty-driven `h` runner, baseline meta helpers.

Black-box only: nothing here imports tools/harness. Uses tests/helpers/h.py for everything about `h` itself.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import termios
import time
import zlib
from pathlib import Path

from helpers.h import H, Result, parse_stdout, run_h

ODIFF = Path(os.environ.get("HARNESS_CACHE", Path.home() / ".cache" / "godot-harness")) / "odiff" / "node_modules" / "@odiff" / "linux-x64" / "odiff"

BASELINE_REL = "baselines/scenes/main"
META_REL = f"{BASELINE_REL}/main-t30.json"
PNG_REL = f"{BASELINE_REL}/main-t30.png"
PROPOSED_META_REL = f"{BASELINE_REL}/main-t30.proposed.json"
PROPOSED_PNG_REL = f"{BASELINE_REL}/main-t30.proposed.png"
MAIN = "res://scenes/main.tscn"
HUD = "res://scenes/hud.tscn"


def out_env(tmp_path) -> dict:
    return {"HARNESS_OUT": str(Path(tmp_path) / "out")}


def shot(project, tmp_path, *args, timeout=180, env=None, **kw) -> Result:
    e = out_env(tmp_path)
    e.update(env or {})
    return run_h("shot", *args, "--project", project, env=e, timeout=timeout, **kw)


def baseline(project, tmp_path, *args, timeout=180, env=None) -> Result:
    e = out_env(tmp_path)
    e.update(env or {})
    return run_h("baseline", *args, "--project", project, env=e, timeout=timeout)


def shot_png(r: Result, name: str) -> Path:
    return r.artifact(f"shots/{name}.png")


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- tiny PNG decoder (8-bit, non-interlaced, RGB/RGBA/gray) ---------------------------------------------
def read_png(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    pos, chunks = 8, []
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        chunks.append((typ, data[pos + 8:pos + 8 + n]))
        pos += 12 + n
    ihdr = [c for t, c in chunks if t == b"IHDR"][0]
    w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", ihdr)
    assert depth == 8 and interlace == 0, f"unsupported PNG (depth {depth}, interlace {interlace})"
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(c for t, c in chunks if t == b"IDAT"))
    stride = w * ch
    rows, prev = [], bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]
        cur = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = cur[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                cur[x] = (cur[x] + a) & 255
            elif f == 2:
                cur[x] = (cur[x] + b) & 255
            elif f == 3:
                cur[x] = (cur[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[x] = (cur[x] + pr) & 255
        rows.append(cur)
        prev = cur
    return w, h, ch, rows


def png_size(path):
    w, h, _, _ = read_png(path)
    return w, h


def pixel(path, x, y):
    w, h, ch, rows = read_png(path)
    px = rows[y][x * ch:(x + 1) * ch]
    return tuple(px[:3]) if ch >= 3 else (px[0],) * 3


def odiff_px(a, b, diff_out) -> int:
    """Pixel count that differs between two PNGs (odiff -t 0). 0 = identical."""
    p = subprocess.run([str(ODIFF), "-t", "0", "--fail-on-layout", "--parsable-stdout", str(a), str(b), str(diff_out)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    out = p.stdout.strip()
    if p.returncode == 0:
        return 0
    assert p.returncode == 22, f"odiff rc {p.returncode}: {out} {p.stderr}"
    return int(out.split(";")[0])


# ---- baseline meta helpers --------------------------------------------------------------------------------
def load_meta(project, rel=META_REL) -> dict:
    return json.loads((Path(project) / rel).read_text())


def save_meta(project, meta: dict, rel=META_REL) -> None:
    (Path(project) / rel).write_text(json.dumps(meta, indent=2) + "\n")


def edit_meta(project, fn, rel=META_REL) -> dict:
    m = load_meta(project, rel)
    fn(m)
    save_meta(project, m, rel)
    return m


def patch(project, rel, old, new, count=1) -> None:
    p = Path(project) / rel
    t = p.read_text()
    assert t.count(old) == count, f"{rel}: {old!r} found {t.count(old)}x"
    p.write_text(t.replace(old, new))


BASELINE_SCHEMA_REQUIRED = ["schema", "name", "target", "tick", "capture", "image", "env", "status", "proposed_at",
                            "proposed_by"]
BASELINE_SCHEMA_ALLOWED = set(BASELINE_SCHEMA_REQUIRED) | {"ignore", "threshold_pct", "approved_at", "approved_by", "note"}


def check_meta_schema(m: dict) -> list:
    """Spec 2.3 schema, hand-checked (required keys, no extras, key types)."""
    errs = []
    for k in BASELINE_SCHEMA_REQUIRED:
        if k not in m:
            errs.append(f"missing {k}")
    for k in m:
        if k not in BASELINE_SCHEMA_ALLOWED:
            errs.append(f"extra key {k}")
    if m.get("schema") != "harness.baseline/1":
        errs.append("schema const")
    if not str(m.get("target", "")).startswith("res://"):
        errs.append("target not res://")
    if not (isinstance(m.get("tick"), int) and m["tick"] >= 1):
        errs.append("tick")
    img = m.get("image", {})
    if not re.fullmatch(r"[0-9a-f]{64}", str(img.get("sha256", ""))) or not isinstance(img.get("w"), int):
        errs.append("image")
    env = m.get("env", {})
    for k in ("godot", "renderer", "adapter", "api"):
        if k not in env:
            errs.append(f"env.{k}")
    if m.get("status") not in ("proposed", "approved"):
        errs.append("status")
    return errs


# ---- running `h` without / with a controlling terminal ---------------------------------------------------
def _result_from(p_rc, out, err, argv, cwd, wall) -> Result:
    parsed = parse_stdout(out)
    ld = Path(parsed["log_dir"]) if parsed["log_dir"] else None
    return Result(rc=p_rc, stdout=out, stderr=err, argv=argv, cwd=Path(cwd), wall=wall, lines=parsed["lines"],
                  verdict=parsed["verdict"], verb=parsed["verb"], reason=parsed["reason"], stats=parsed["stats"],
                  stat_items=parsed["stat_items"], checks=parsed["checks"], findings=parsed["findings"],
                  trunc=parsed["trunc"], log_dir=ld, kinds=parsed["kinds"])


def _clean_env(tmp_path) -> dict:
    e = dict(os.environ)
    for k in ("HARNESS_PROJECT", "HARNESS_OUT", "HARNESS_TIMEOUT_SCALE", "HARNESS_ROOT"):
        e.pop(k, None)
    e.update(out_env(tmp_path))
    return e


def run_h_no_tty(args, tmp_path, timeout=120) -> Result:
    """Run h in a new session (no controlling terminal), stdin /dev/null."""
    argv = [str(H), *[str(a) for a in args]]
    t0 = time.monotonic()
    p = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL, env=_clean_env(tmp_path),
                       timeout=timeout, start_new_session=True)
    return _result_from(p.returncode, p.stdout, p.stderr, argv, Path.cwd(), time.monotonic() - t0)


def run_h_tty(args, tmp_path, answers, timeout=180):
    """Run h with a controlling pty. stdout/stderr stay pipes (contract output), the pty carries the prompt.

    `answers` = list of lines written one by one after the child printed something on the pty.
    Returns (Result, tty_text)."""
    argv = [str(H), *[str(a) for a in args]]
    master, slave = pty.openpty()

    def pre():
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

    t0 = time.monotonic()
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         env=_clean_env(tmp_path), preexec_fn=pre, close_fds=True)
    os.close(slave)
    tty = b""
    pending = list(answers)
    deadline = time.monotonic() + timeout
    while p.poll() is None and time.monotonic() < deadline:
        r, _, _ = select.select([master], [], [], 0.2)
        if r:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            tty += chunk
            if pending:
                time.sleep(0.3)
                os.write(master, (pending.pop(0) + "\n").encode())
    try:
        out, err = p.communicate(timeout=max(1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        raise AssertionError(f"h {args} with a tty did not finish; tty so far: {tty!r}")
    # drain the rest of the pty
    try:
        while select.select([master], [], [], 0.1)[0]:
            c = os.read(master, 4096)
            if not c:
                break
            tty += c
    except OSError:
        pass
    os.close(master)
    return _result_from(p.returncode, out, err, argv, Path.cwd(), time.monotonic() - t0), tty.decode("utf-8", "replace")


def path_without(binary: str, dest: Path) -> str:
    """A PATH made of one directory of symlinks to every executable on the current PATH except `binary`."""
    dest.mkdir(parents=True, exist_ok=True)
    for d in os.environ.get("PATH", "").split(os.pathsep):
        dp = Path(d)
        if not dp.is_dir():
            continue
        for f in dp.iterdir():
            if f.name == binary or (dest / f.name).exists() or not f.is_file() or not os.access(f, os.X_OK):
                continue
            try:
                (dest / f.name).symlink_to(f)
            except OSError:
                pass
    return str(dest)


def x_locks() -> dict:
    """{path: pid-or-None} for /tmp/.X*-lock files."""
    out = {}
    for f in Path("/tmp").glob(".X*-lock"):
        try:
            out[str(f)] = int(f.read_text().strip())
        except (OSError, ValueError):
            out[str(f)] = None
    return out
