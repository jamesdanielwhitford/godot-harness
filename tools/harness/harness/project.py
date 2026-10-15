"""Project resolution (contract 2.2)."""
from __future__ import annotations

import os
from pathlib import Path


class ProjectError(Exception):
    pass


def is_project(p: Path) -> bool:
    return (Path(p) / "project.godot").is_file()


def find_up(start: Path) -> Path | None:
    start = Path(start).resolve()
    for d in [start, *start.parents]:
        if is_project(d):
            return d
    return None


def resolve(arg: str | None = None, cwd: Path | None = None) -> Path:
    """--project > $HARNESS_PROJECT > nearest ancestor of cwd containing project.godot."""
    cwd = Path(cwd) if cwd else Path.cwd()
    cand = arg or os.environ.get("HARNESS_PROJECT") or None
    if cand:
        p = Path(cand).expanduser()
        p = (p if p.is_absolute() else cwd / p).resolve()
        if not is_project(p):
            raise ProjectError("no Godot project (pass --project DIR)")
        return p
    found = find_up(cwd)
    if found is None:
        raise ProjectError("no Godot project (pass --project DIR)")
    return found


def res_path(project, fs_path) -> str | None:
    """Filesystem path -> res://... (None when outside the project)."""
    project = Path(project).resolve()
    p = Path(fs_path)
    p = (p if p.is_absolute() else Path.cwd() / p)
    try:
        rel = Path(os.path.normpath(p)).relative_to(project)
    except ValueError:
        try:
            rel = p.resolve().relative_to(project)
        except ValueError:
            return None
    s = rel.as_posix()
    return "res://" if s == "." else "res://" + s


def fs_path(project, res: str) -> Path:
    if not res.startswith("res://"):
        raise ValueError(f"not a res:// path: {res}")
    return Path(project) / res[len("res://"):]
