"""Code checks of A3 (spec 3.3, 3.4). Each returns [(line, rule, message, hint)], lines 1-based."""
from __future__ import annotations

import difflib
import re

INPUT_CALLS = ("is_action_pressed", "is_action_just_pressed", "is_action_just_released", "is_action_released",
               "is_action", "get_action_strength", "get_action_raw_strength", "action_press", "action_release")
INPUT_FIRST_RE = re.compile(r"(?<![\w])(?<!func )(?:%s)\s*\(\s*&?\"([^\"]*)\"" % "|".join(INPUT_CALLS))
INPUT_MULTI_RE = re.compile(r"(?<![\w])(?<!func )(?:get_axis|get_vector)\s*\(")
LITERAL_RE = re.compile(r'&?"([^"]*)"')
SIGNAL_CALL_RE = re.compile(r'(?<![\w.])(?:(?P<recv>[A-Za-z_]\w*)\.)?(?P<fn>emit_signal|connect|disconnect|is_connected)'
                            r'\s*\(\s*&?"(?P<sig>[^"]*)"')
VAR_DECL_RE = re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*var\s+(\w+)\s*(?::\s*([A-Z]\w*)\s*(?:=|$)|:=\s*([A-Z]\w*)\.new\("
                         r"|=\s*([A-Z]\w*)\.new\()")
SIM_TYPE_RE = re.compile(r"(?:\bextends\s+|:\s*(?!=)|->\s*|\bas\s+|\bis\s+|\bArray\[)([A-Z]\w*)\b")


def is_comment(ln: str) -> bool:
    return ln.lstrip().startswith("#")


def split_args(s: str):
    """Top-level comma split of the text after an opening paren; returns (args, closed)."""
    args, cur, depth, i, q = [], [], 0, 0, None
    while i < len(s):
        c = s[i]
        if q:
            cur.append(c)
            if c == "\\" and i + 1 < len(s):
                cur.append(s[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            if depth == 0:
                args.append("".join(cur).strip())
                return args, True
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    args.append("".join(cur).strip())
    return args, False


def _close(name: str, known, n: int = 3) -> list:
    return difflib.get_close_matches(name, sorted(known), n=n, cutoff=0.6)


# ---- 3.4a input actions ------------------------------------------------------------------------------------
def input_actions(lines, info) -> list:
    out = []
    known = None
    for i, ln in enumerate(lines, 1):
        if is_comment(ln) or ("is_action" not in ln and "get_axis" not in ln and "get_vector" not in ln
                              and "get_action_" not in ln and "action_press" not in ln and "action_release" not in ln):
            continue
        names = [m.group(1) for m in INPUT_FIRST_RE.finditer(ln)]
        for m in INPUT_MULTI_RE.finditer(ln):
            args, _ = split_args(ln[m.end():])
            for a in args:
                lm = re.fullmatch(r'&?"([^"]*)"', a)
                if lm:
                    names.append(lm.group(1))
        for name in names:
            if known is None:
                known = info.known_actions()
            if name in known:
                continue
            close = _close(name, known)
            if close:
                hint = f"did you mean '{close[0]}'? add new actions under [input] in project.godot"
            else:
                proj = info.project_actions()[:5]
                hint = "add it under [input] in project.godot" + (f"; known: {', '.join(proj)}, ..." if proj else "")
            out.append((i, "lint.input-action", f"InputMap action '{name}' does not exist", hint))
    return out


# ---- 3.4b signals -----------------------------------------------------------------------------------------
def signal_names(text, lines, info, res_path) -> list:
    if not any(k in text for k in ("emit_signal", "connect", "disconnect", "is_connected")):
        return []
    out = []
    var_types: dict = {}
    for ln in lines:
        m = VAR_DECL_RE.match(ln)
        if m:
            t = m.group(2) or m.group(3) or m.group(4)
            var_types.setdefault(m.group(1), set()).add(t)
    own = None
    own_done = False
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        for m in SIGNAL_CALL_RE.finditer(ln):
            recv, fn, sig = m.group("recv"), m.group("fn"), m.group("sig")
            if recv is None or recv == "self":
                if not own_done:
                    own = info.text_signals(text, res_path)
                    own_done = True
                declared, where = own, "this script or its bases"
            else:
                types = var_types.get(recv)
                if not types or len(types) != 1:
                    continue
                t = next(iter(types))
                declared = info.class_signals(t)
                where = f"class {t}"
            if declared is None or sig in declared:
                continue
            close = _close(sig, declared, 1)
            if fn == "emit_signal":
                pref = lambda s: f"prefer {s}.emit()"  # noqa: E731
            else:
                pref = lambda s: f"prefer {s}.{'connect(cb)' if fn == 'connect' else fn.replace('_signal', '')}"  # noqa: E731
            hint = f"did you mean '{close[0]}'? {pref(close[0])}" if close else "declare it with 'signal name'"
            out.append((i, "lint.signal-name", f"signal '{sig}' is not declared on {where}", hint))
    return out


# ---- 3.4c mixed indentation -------------------------------------------------------------------------------
def indent_mixed(text, lines) -> list:
    indents = re.findall(r"^([ \t]+)[^ \t\r\n]", text, re.M)
    if not indents:
        return []
    kinds = {("t" if i[0] == "\t" else "s") + ("m" if (" " in i and "\t" in i) else "") for i in indents}
    if kinds <= {"t"} or kinds <= {"s"}:
        return []
    out = []
    style = None
    depth = 0
    triple = None
    cont = False
    for n, raw in enumerate(lines, 1):
        ln = raw.rstrip("\r")
        statement_start = depth == 0 and triple is None and not cont
        if statement_start and ln.strip() and not ln.lstrip().startswith("#"):
            ind = ln[: len(ln) - len(ln.lstrip(" \t"))]
            if ind:
                if " " in ind and "\t" in ind:
                    out.append((n, "lint.indent-mixed", "mixed tabs and spaces in indentation", ""))
                else:
                    s = "t" if ind[0] == "\t" else "s"
                    if style is None:
                        style = s
                    elif s != style:
                        out.append((n, "lint.indent-mixed",
                                    f"indented with {'tabs' if s == 't' else 'spaces'} but the file uses "
                                    f"{'tabs' if style == 't' else 'spaces'}", ""))
        # scan the line for brackets, strings, comments, continuation
        cont = False
        i, L = 0, len(ln)
        q = triple
        while i < L:
            c = ln[i]
            if q:
                if q in ('"""', "'''"):
                    if ln.startswith(q, i):
                        q = None
                        triple = None
                        i += 3
                        continue
                    if c == "\\":
                        i += 1
                else:
                    if c == "\\":
                        i += 1
                    elif c == q:
                        q = None
                i += 1
                continue
            if c == "#":
                break
            if c in "\"'":
                if ln.startswith(c * 3, i):
                    q = c * 3
                    triple = q
                    i += 3
                    continue
                q = c
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth = max(depth - 1, 0)
            elif c == "\\" and i == L - 1:
                cont = True
            i += 1
        if q and q not in ('"""', "'''"):
            q = None  # unterminated single-line string: ignore
    return out


# ---- 3.3 determinism code checks ---------------------------------------------------------------------------
def det_idle_gd(lines) -> list:
    out = []
    n = len(lines)
    for i, ln in enumerate(lines):
        if is_comment(ln):
            continue
        if "create_tween(" in ln:
            win = "\n".join(lines[i: i + 4])
            if "TWEEN_PROCESS_PHYSICS" not in win:
                out.append((i + 1, "lint.det-idle-tween", "", ""))
        if "Timer.new()" in ln and "TIMER_PROCESS_PHYSICS" not in "\n".join(lines[i: i + 6]):
            out.append((i + 1, "lint.det-idle-timer", "Timer.new() without TIMER_PROCESS_PHYSICS", ""))
        m = re.search(r"\bcreate_timer\s*\(", ln)
        if m:
            args, closed = split_args(ln[m.end():])
            if closed and not (len(args) >= 3 and args[2] == "true"):
                out.append((i + 1, "lint.det-idle-timer", "create_timer() without process_always physics flag", ""))
        if re.search(r"\b(?:AnimationPlayer|AnimationTree)\.new\s*\(", ln) and \
                "ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS" not in "\n".join(lines[i: i + 6]):
            out.append((i + 1, "lint.det-idle-anim", "", ""))
    return out


NODE_HDR_RE = re.compile(r"^\[node\s")


def det_idle_tscn(lines) -> list:
    out = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if NODE_HDR_RE.match(ln):
            tm = re.search(r'\btype="(\w+)"', ln)
            j = i + 1
            body = []
            while j < n and not lines[j].startswith("["):
                body.append(lines[j])
                j += 1
            if tm:
                typ = tm.group(1)
                if typ == "Timer" and not any(re.match(r"\s*process_callback\s*=\s*0\b", b) for b in body):
                    out.append((i + 1, "lint.det-idle-timer", "Timer node without process_callback = 0", ""))
                if typ in ("AnimationPlayer", "AnimationTree") and \
                        not any(re.match(r"\s*callback_mode_process\s*=\s*0\b", b) for b in body):
                    out.append((i + 1, "lint.det-idle-anim", f"{typ} node without callback_mode_process = 0", ""))
            i = j
        else:
            i += 1
    return out


# ---- sim: Node typed declarations --------------------------------------------------------------------------
def sim_node_types(lines, info) -> list:
    out = []
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        for m in SIM_TYPE_RE.finditer(ln):
            if info.inherits_node(m.group(1)):
                out.append((i, "lint.sim-node", f"Node type {m.group(1)} used in node-free simulation code", ""))
                break
    return out
