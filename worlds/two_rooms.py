"""The test world as a loadable world file: two rooms, a locked door, a key, a guard.

    uv run embody --as gm --author load worlds/two_rooms.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for tests.test_world

from tests.test_world import build as _build  # noqa: E402


def build(session):
    w = _build(session.engine.store, seed=7)
    return session.use(w.id)
