"""A2 contract fixtures (T2). `host` = fresh per-test copy of an imported scene_host (B3)."""
import pytest


@pytest.fixture
def host(mkwarm):
    return mkwarm("scene_host")


@pytest.fixture
def fresh_host(mkproj):
    return mkproj("scene_host")
