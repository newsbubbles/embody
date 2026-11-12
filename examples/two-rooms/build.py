"""The test world as a loadable world: two rooms, a locked door, a key, a guard. A legacy build(session) world,
no manifest: the loader still takes those.

    uv run embody --as gm --author load examples/two-rooms
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for tests.test_world

from tests.test_world import build as _build  # noqa: E402

def build(session):
    w = _build(session.engine.store, seed=7)
    return session.use(w.id)
