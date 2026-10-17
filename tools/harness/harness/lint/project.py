"""Project-level facts for lint: [input] actions, class_name index, script signals and bases (A3 spec 3.4)."""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import rules

EXTENDS_RE = re.compile(r'^(?:class_name\s+\w+(?:\s*,\s*"[^"]*")?\s+)?extends\s+("[^"]+"|[A-Za-z_][\w.]*)', re.M)
SIGNAL_RE = re.compile(r"^\s*signal\s+([A-Za-z_]\w*)", re.M)
CLASS_NAME_RE = re.compile(r"^\s*class_name\s+(\w+)")
ADD_ACTION_RE = re.compile(r'\bInputMap\.add_action\s*\(\s*&?"([^"]+)"')
INPUT_KEY_RE = re.compile(r"^([^\s=;\[]+)=")
CONFIG_VERSION_RE = re.compile(r"^config_version=(\d+)", re.M)


def read_text(p: Path) -> str:
    try:
        return p.read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""


def walk_files(project: Path, exts=(".gd",)):
    """Yield files of the project: no hidden dirs, no .godot/.harness."""
    for dp, dns, fns in os.walk(project):
        dns[:] = sorted(d for d in dns if not d.startswith("."))
        for fn in sorted(fns):
            if fn.endswith(exts) or fn in exts:
                yield Path(dp) / fn


def res_of(project: Path, p: Path) -> str:
    return "res://" + p.relative_to(project).as_posix()


class ProjectInfo:
    def __init__(self, project: Path):
        self.project = project
        self._actions = None
        self._classes = None
        self._script_cache: dict = {}

    # -- input actions
    def project_actions(self) -> list:
        if self._actions is None:
            acts = []
            text = read_text(self.project / "project.godot")
            sect = None
            for ln in text.split("\n"):
                m = re.match(r"^\[([^\]]+)\]", ln)
                if m:
                    sect = m.group(1)
                    continue
                if sect == "input":
                    k = INPUT_KEY_RE.match(ln)
                    if k:
                        acts.append(k.group(1).strip('"'))
            self._actions = acts
        return self._actions

    def dynamic_actions(self) -> set:
        if getattr(self, "_dyn", None) is None:
            dyn = set()
            for f in walk_files(self.project):
                t = read_text(f)
                if "add_action" in t:
                    dyn.update(ADD_ACTION_RE.findall(t))
            self._dyn = dyn
        return self._dyn

    def known_actions(self) -> set:
        return set(self.project_actions()) | set(rules.builtin_actions()) | self.dynamic_actions()

    # -- classes and signals
    def class_index(self) -> dict:
        if self._classes is None:
            idx = {}
            for f in walk_files(self.project):
                try:
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        for i, ln in enumerate(fh):
                            if i >= 50:
                                break
                            m = CLASS_NAME_RE.match(ln)
                            if m:
                                idx.setdefault(m.group(1), res_of(self.project, f))
                                break
                except OSError:
                    pass
            self._classes = idx
        return self._classes

    def native_chain_signals(self, cls: str):
        """Signals of a native class and its ancestors, or None when the class is unknown."""
        nat = rules.native_classes()
        if cls not in nat:
            return None
        sigs = set()
        seen = set()
        while cls and cls in nat and cls not in seen:
            seen.add(cls)
            sigs.update(nat[cls]["signals"])
            cls = nat[cls]["inherits"]
        return sigs

    def inherits_node(self, cls: str) -> bool:
        nat = rules.native_classes()
        seen = set()
        while cls and cls in nat and cls not in seen:
            if cls == "Node":
                return True
            seen.add(cls)
            cls = nat[cls]["inherits"]
        return False

    def text_signals(self, text: str, here: str, depth: int = 0):
        """Declared signals of a script text including its base chain; None when the chain cannot be resolved."""
        if depth > 12:
            return None
        sigs = set(SIGNAL_RE.findall(text))
        m = EXTENDS_RE.search(text)
        if not m:
            base_sigs = self.native_chain_signals("RefCounted")
        else:
            base = m.group(1)
            if base.startswith('"'):
                path = base.strip('"')
                base_sigs = self.path_signals(path, here, depth + 1)
            elif "." in base:
                return None
            else:
                base_sigs = self.class_signals(base, depth + 1)
        if base_sigs is None:
            return None
        return sigs | base_sigs

    def class_signals(self, name: str, depth: int = 0):
        nat = self.native_chain_signals(name)
        if nat is not None:
            return nat
        path = self.class_index().get(name)
        if path is None:
            return None
        return self.path_signals(path, path, depth)

    def path_signals(self, path: str, here: str, depth: int = 0):
        if path.startswith("res://"):
            res = path
        else:
            res = os.path.normpath(os.path.join(os.path.dirname(here[len("res://"):]), path))
            res = "res://" + res
        key = res
        if key in self._script_cache:
            return self._script_cache[key]
        self._script_cache[key] = None  # cycle guard
        f = self.project / res[len("res://"):]
        if not f.is_file():
            return None
        val = self.text_signals(read_text(f), res, depth)
        self._script_cache[key] = val
        return val
