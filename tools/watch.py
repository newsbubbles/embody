"""Live world graph on this machine: a read-only web view of an embody database.

    uv run python tools/watch.py --port 8765

The viewer lives in the package (embody.watch) so the hosted server can serve the same page at /watch behind its
bearer door; this file is the local way to run it. Without --db it watches the workspace's database the way the
CLI finds it: $EMBODY_DB, then embody.db in the current folder, then a legacy worlds/embody.db.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from embody.watch import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
