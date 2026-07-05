"""Auto-mark every test under ``tests/performance/`` as ``performance``.

Structural guarantee (PR #546 review): a per-file ``pytestmark`` only protects the file that
remembers it. A new performance test file that forgets the marker would otherwise (a) run its
real-sleep timing in the fast lane on every push, and (b) be invisible to CI's ``-m performance``
step — so it would never run in isolation either. Stamping the marker by directory here makes the
guarantee hold for all current and future files in this tree.
"""
import os

import pytest

_PERF_DIR = os.path.dirname(__file__)


def pytest_collection_modifyitems(config, items):
    # This hook receives the full session item list; scope the marking to this directory only.
    for item in items:
        if str(item.fspath).startswith(_PERF_DIR):
            item.add_marker(pytest.mark.performance)
