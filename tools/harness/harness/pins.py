import os
import tomllib
from pathlib import Path


def repo_root():
    env = os.environ.get("HARNESS_REPO")
    return Path(env) if env else Path(__file__).resolve().parents[3]


def cache_dir():
    return Path(os.environ.get("HARNESS_CACHE") or Path.home() / ".cache" / "godot-harness")


def load():
    with open(repo_root() / "tools" / "harness" / "pins.toml", "rb") as f:
        return tomllib.load(f)
