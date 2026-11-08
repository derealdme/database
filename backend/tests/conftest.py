"""Shared test setup.

Unit tests (tests/unit) must run with NO database.
Integration tests (tests/integration) need MySQL + MongoDB with the schema
loaded; they are skipped unless RUN_INTEGRATION=1.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="set RUN_INTEGRATION=1 to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
