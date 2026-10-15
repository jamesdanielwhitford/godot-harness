"""A6 contract fixtures (T6). Uses the shared mkproj/mkwarm fixtures from tests/conftest.py."""
import pytest


@pytest.fixture
def sm(mkwarm):
    """Fresh per-test copy of an imported `shot_min` (keeps .godot/, drops .harness/)."""
    return mkwarm("shot_min")


@pytest.fixture
def sm_cold(mkproj):
    """Fresh, never-imported copy of `shot_min` (the verb must import it itself)."""
    return mkproj("shot_min")
