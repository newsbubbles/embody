"""A world's handbook: the guides its agents read for their part, served by the world itself (handbook()), so how to
play a part ships with the world and updates with it, and a part nobody gave you stays out of sight.

Two layers, read live from disk: the engine's defaults (src/embody/handbook/: the index, seats, and the parts most
worlds use) under the world's own folder (worlds/<id>/handbook/, or the path its WORLD manifest names as `handbook`;
`"handbook": False` turns the world's off). A world file at a default's path replaces it, and one with `for: []` hides
it. Each file is markdown with frontmatter: `name`, `description` (what the listing shows), and `for`, the engine
roles and parts that may read it (`everyone`: any seat). A file with no `for` is the owner's and the authors' only.
The index (SKILL.md) is everyone's. A file a seat may not read answers as one that does not exist."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DEFAULTS = Path(__file__).resolve().parent / "handbook"
INDEX = "SKILL.md"
EVERYONE = "everyone"
STAFF = ("owner", "author")
MAX_BYTES = 200_000  # a page bigger than this is not served
PAGE_CHARS = 12_000  # one read returns at most this much; `page` reads on
_PATH = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.md$")


def frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """The `---` block at the top as a dict (a key: value per line; [a, b] or a following `- x` list for lists) and
    the text after it. No block: ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta: dict[str, Any] = {}
    key = None
    for raw in text[3:end].splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, v = m.group(1), m.group(2).strip()
            if v.startswith("[") and v.endswith("]"):
                meta[key] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
            elif v == "":
                meta[key] = []
            else:
                meta[key] = v.strip("'\"")
        elif key is not None and line.lstrip().startswith("- ") and isinstance(meta.get(key), list):
            meta[key].append(line.lstrip()[2:].strip().strip("'\""))
    return meta, text[end + 4:].lstrip("\n")


def world_folder(engine: Any, world_id: str | None) -> Path | None:
    """The world's own handbook folder on this server: worlds/<id>/handbook, or the path its manifest names. None when
    the world has no folder here, names none (False) or the path leaves the world folder."""
    ws = getattr(engine, "workspace", None)
    if ws is None or not world_id:
        return None
    from .workspace import _manifest
    home = Path(ws.world_dir(world_id)).resolve()
    if not (home / "build.py").exists():
        return None
    where = (_manifest(home / "build.py") or {}).get("handbook", "handbook")
    if where in (False, None, ""):
        return None
    d = (home / str(where)).resolve()
    if home != d and home not in d.parents:
        return None
    return d if d.is_dir() else None


def shelf(engine: Any, world_id: str | None) -> dict[str, dict[str, Any]]:
    """Every page, by its path in the handbook: the defaults, then the world's own over them. Each: file, meta, layer."""
    out: dict[str, dict[str, Any]] = {}
    for layer, root in (("engine", DEFAULTS), ("world", world_folder(engine, world_id))):
        if root is None or not root.is_dir():
            continue
        for f in sorted(root.rglob("*.md")):
            rel = f.relative_to(root).as_posix()
            if not _PATH.match(rel):
                continue
            try:
                if f.stat().st_size > MAX_BYTES:
                    continue
                head = f.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            meta, _ = frontmatter(head)
            out[rel] = {"file": f, "meta": meta, "layer": layer}
    return out


def readers(meta: dict[str, Any], path: str) -> set[str] | None:
    """Who may read a page: a set of roles and parts, or None for any seat."""
    if path == INDEX:
        return None
    who = meta.get("for")
    if who is None:
        return set(STAFF)
    who = [who] if isinstance(who, str) else list(who)
    names = {str(x).strip().lower() for x in who if str(x).strip()}
    return None if EVERYONE in names else names


def may_read(meta: dict[str, Any], path: str, role: str, parts: list[str]) -> bool:
    """The owner reads every page a world has not hidden (`for: []`); anyone else, the pages naming their role or a
    part of theirs, and the everyone pages."""
    r = readers(meta, path)
    if r is None:
        return True
    if role == "owner":
        return bool(r)
    return role in r or bool(r & {p.lower() for p in parts})


def listing(engine: Any, world_id: str | None, role: str, parts: list[str]) -> list[dict[str, Any]]:
    """The pages this seat may read, beyond the index: path, name, description, and whose (the world's or the engine's)."""
    rows = []
    for path, pg in sorted(shelf(engine, world_id).items()):
        if path == INDEX or not may_read(pg["meta"], path, role, parts):
            continue
        rows.append({"path": path, "name": pg["meta"].get("name") or Path(path).stem,
                     "description": pg["meta"].get("description") or "", "from": pg["layer"]})
    return rows


def read(engine: Any, world_id: str | None, path: str, role: str, parts: list[str], page: int = 1) -> dict[str, Any] | None:
    """One page's text without its frontmatter, `page` by page. None when there is no such page for this seat (it is
    missing, malformed, hidden or not this seat's: the same answer for all of them)."""
    path = (path or "").strip().lstrip("/") or INDEX
    if not _PATH.match(path):
        return None
    pg = shelf(engine, world_id).get(path)
    if pg is None or not may_read(pg["meta"], path, role, parts):
        return None
    try:
        _, body = frontmatter(pg["file"].read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    pages = max(1, -(-len(body) // PAGE_CHARS))
    n = min(max(1, int(page)), pages)
    out = {"path": path, "name": pg["meta"].get("name") or Path(path).stem, "from": pg["layer"],
           "text": body[(n - 1) * PAGE_CHARS:n * PAGE_CHARS]}
    if pages > 1:
        out.update({"page": n, "pages": pages})
    return out
