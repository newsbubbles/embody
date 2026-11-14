"""Live world graph: a read-only web view of an embody database.

Standalone, on this machine (no login; it is your own database):

    uv run python tools/watch.py --port 8765

Without --db it watches the workspace's database the way the CLI finds it: $EMBODY_DB, then embody.db in the
current folder, then a workspace from before the folders with its database at worlds/embody.db. The world list
also shows the folders under worlds/ that are not built yet.

Hosted, the same page is served by the MCP server at /watch behind its bearer door (mcp_server.Bearer): the page
itself is public, the data behind it answers only to a grant whose role may read everything (owner, author,
narrator, observer), and only for that grant's world. The page asks for the token once and keeps it in the tab.

Standalone it opens the database read-only (SQLite WAL lets it read while the engine writes); hosted it reads
through the engine's own connection under its lock. Nothing here writes anything; it is a window, not a hand.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
PAGE = HERE / "watch.html"
WATCH_ROLES = ("owner", "author", "narrator", "observer")  # who may look through the hosted window


def _loads(v):
    if v is None:
        return None
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


# What the viewer undoes to show the past: each of these events carries what it changed from.
_UNDO = ("moved", "patched", "spawned", "destroyed", "renamed")
_UNDO_SQL = ", ".join(f"'{k}'" for k in _UNDO)


def _rewind(ents: list[dict], rows) -> list[dict]:
    """The entities as they were before `rows` (newest first): a move goes back where it came from, a patch puts back
    what it had (`before`), a spawn is unmade, a rename takes the old name. A destroyed entity comes back with its
    type, name and place but no state: the log does not keep it, and the page says so (`past: "destroyed"`)."""
    by = {e["id"]: e for e in ents}
    order = [e["id"] for e in ents]
    for kind, target, payload in rows:
        p = _loads(payload) or {}
        e = by.get(target)
        if kind == "spawned":
            by.pop(target, None)
        elif kind == "destroyed":
            if e is None:
                by[target] = {"id": target, "type": p.get("type") or "thing", "parent": p.get("parent"),
                              "name": p.get("name") or "", "state": {}, "pos": None, "version": 0, "updated_seq": 0,
                              "past": "destroyed"}
                order.append(target)
        elif e is None:
            continue
        elif kind == "moved":
            e["parent"] = p.get("from", e["parent"])
            if "from_pos" in p:
                e["pos"] = p["from_pos"]
        elif kind == "patched":
            for k, b in (p.get("before") or {}).items():
                if b is None:
                    e["state"].pop(k, None)
                else:
                    e["state"][k] = b
        elif kind == "renamed":
            e["name"] = p.get("old", e["name"])
    return [by[i] for i in dict.fromkeys(order) if i in by]


def _has_table(c, name: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _col(row, key: str):
    """A column an older database may not have yet (the store adds them on open)."""
    return row[key] if key in row.keys() else None


def find_db(root: Path = Path(".")) -> Path:
    """The CLI's rule for the database when none is given, looked for under root."""
    env = os.environ.get("EMBODY_DB")
    if env:
        return Path(env)
    if not (root / "embody.db").exists() and (root / "worlds" / "embody.db").exists():
        return root / "worlds" / "embody.db"
    return root / "embody.db"


def workspace_of(db: Path) -> Path:
    """The folder of worlds/ and packs/ a database belongs to: its own, or the one above a legacy worlds/embody.db."""
    p = db.resolve().parent
    return p.parent if p.name == "worlds" else p


def manifest(build_py: Path) -> dict:
    """The WORLD dict of a build.py, read without running it."""
    try:
        tree = ast.parse(build_py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WORLD" for t in node.targets):
                m = ast.literal_eval(node.value)
                return m if isinstance(m, dict) else {}
    except (OSError, SyntaxError, ValueError):
        pass
    return {}


class _Rows:
    """A cursor that hands back sqlite3.Row, over a connection of our own (closed after) or a shared one (left open)."""

    def __init__(self, conn: sqlite3.Connection, own: bool):
        self.conn, self.own = conn, own

    def __enter__(self) -> sqlite3.Cursor:
        self.cur = self.conn.cursor()
        self.cur.row_factory = sqlite3.Row
        return self.cur

    def __exit__(self, *a) -> None:
        self.cur.close()
        if self.own:
            self.conn.close()


class Reader:
    def __init__(self, db: Path, root: Path | None = None, conn: sqlite3.Connection | None = None):
        self.db = db
        self.root = root or workspace_of(db)
        self.shared = conn  # the engine's own connection when hosted; the caller holds the engine lock

    def folder(self, world_id: str, metas: dict[str, dict] | None = None) -> str | None:
        """The world's folder: its own, or up the forked_from / restored_from chain (a fork runs its source's code)."""
        seen: set[str] = set()
        wid = world_id
        while wid not in seen:
            seen.add(wid)
            if (self.root / "worlds" / wid / "build.py").exists():
                return f"worlds/{wid}"
            meta = (metas or {}).get(wid)
            if meta is None and metas is None and (self.shared is not None or self.db.exists()):
                with self.conn() as c:
                    r = c.execute("SELECT meta FROM world WHERE id=?", (wid,)).fetchone()
                meta = (_loads(r["meta"]) or {}) if r else {}
            src = ((meta or {}).get("forked_from") or (meta or {}).get("restored_from") or {}).get("world")
            if not src:
                return None
            wid = src
        return None

    def conn(self) -> _Rows:
        if self.shared is not None:
            return _Rows(self.shared, own=False)
        c = sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True, timeout=2.0)
        return _Rows(c, own=True)

    def worlds(self, only: str | None = None) -> list[dict]:
        """The worlds in the database, newest first (a fork made a moment ago is what the watcher wants to see), then
        the folders under worlds/ nobody has built yet. only=<id> narrows to one world and no folders: a grant's view."""
        out = []
        if self.shared is not None or self.db.exists():
            with self.conn() as c:
                rows = c.execute("SELECT id, name, t, clock_running, clock_rate, meta FROM world ORDER BY rowid DESC").fetchall()
            rows = [r for r in rows if only is None or r["id"] == only]
            metas = {r["id"]: (_loads(r["meta"]) or {}) for r in rows}
            for r in rows:
                meta = metas[r["id"]]
                out.append({"id": r["id"], "name": r["name"], "t": r["t"], "running": bool(r["clock_running"]),
                            "rate": r["clock_rate"], "forked_from": meta.get("forked_from"),
                            "turn": meta.get("turn_seconds"), "built": True, "folder": self.folder(r["id"], metas)})
        if only is not None:
            return out
        built = {w["id"] for w in out}
        wd = self.root / "worlds"
        if wd.is_dir():
            for d in sorted(p for p in wd.iterdir() if p.is_dir() and (p / "build.py").exists()):
                if d.name not in built:
                    m = manifest(d / "build.py")
                    out.append({"id": d.name, "name": m.get("name") or d.name, "t": None, "running": False, "rate": None,
                                "forked_from": None, "turn": None, "built": False, "folder": f"worlds/{d.name}"})
        return out

    def state(self, world_id: str | None, since: int, limit: int, after: int | None = None,
              sig: str | None = None, at: int | None = None, at_t: float | None = None) -> dict:
        """The world for the viewer. after=<the highest updated_seq the page holds> makes it a diff: only the entities
        changed since, `ids` (every id there is, so the page drops the destroyed), and the edges, hyperedges and schemas
        only when their signature differs from `sig`. The scheduled ticks come summed up either way: a world of a few
        hundred bodies has a tick each, and the page only counts them.

        at=<seq> or at_t=<world time> is the world as it stood then: the entities now with every change since undone
        (_rewind), and the events up to that moment. Edges, seats and timers stay as they are now."""
        with self.conn() as c:
            if not world_id:
                row = c.execute("SELECT id FROM world ORDER BY rowid DESC LIMIT 1").fetchone()
                if row is None:
                    return {"ok": False, "reason": "no worlds in this database"}
                world_id = row["id"]
            w = c.execute("SELECT * FROM world WHERE id=?", (world_id,)).fetchone()
            if w is None:
                return {"ok": False, "reason": f"no world {world_id}"}
            if at_t is not None:
                r = c.execute("SELECT seq FROM event WHERE world_id=? AND t<=? ORDER BY seq DESC LIMIT 1",
                              (world_id, at_t)).fetchone()
                at = r[0] if r else 0
            if at is not None:
                after = None  # the past comes whole
            q = "SELECT * FROM entity WHERE world_id=?" + (" AND updated_seq>?" if after is not None else "")
            ents = [{"id": r["id"], "type": r["type"], "parent": r["parent_id"], "name": r["name"],
                     "state": _loads(r["state"]), "pos": _loads(r["pos"]), "version": r["version"],
                     "updated_seq": r["updated_seq"]}
                    for r in c.execute(q + " ORDER BY created_seq",
                                       (world_id,) if after is None else (world_id, after))]
            ids = [r[0] for r in c.execute("SELECT id FROM entity WHERE world_id=? ORDER BY created_seq", (world_id,))] \
                if after is not None else None
            first = c.execute("SELECT seq, t FROM event WHERE world_id=? ORDER BY seq LIMIT 1", (world_id,)).fetchone()
            past = None
            if at is not None:
                ents = _rewind(ents, c.execute(
                    f"SELECT kind, target_id, payload FROM event WHERE world_id=? AND seq>? AND kind IN ({_UNDO_SQL}) "
                    "ORDER BY seq DESC", (world_id, at)))
                r = c.execute("SELECT seq, t FROM event WHERE world_id=? AND seq<=? ORDER BY seq DESC LIMIT 1",
                              (world_id, at)).fetchone()
                past = {"seq": r["seq"], "t": r["t"]} if r else {"seq": 0, "t": first["t"] if first else 0}
            edge_rows = c.execute("SELECT * FROM edge WHERE world_id=? ORDER BY id", (world_id,)).fetchall()
            hyper_rows = c.execute("SELECT * FROM hyperedge WHERE world_id=? ORDER BY id", (world_id,)).fetchall()
            schema_rows = c.execute("SELECT id, extends, space FROM schema WHERE world_id=? ORDER BY id", (world_id,)).fetchall()
            h = hashlib.sha1()
            for rows, cols in ((edge_rows, ("id", "source", "target", "relation", "data")),
                               (hyper_rows, ("id", "relation", "participants", "data")),
                               (schema_rows, ("id", "extends", "space"))):
                for r in rows:
                    h.update("\x1f".join(str(r[k]) for k in cols).encode())
                h.update(b"\x1e")
            new_sig = h.hexdigest()[:16]
            same = after is not None and sig == new_sig
            edges = None if same else [{"id": r["id"], "source": r["source"], "target": r["target"],
                                        "relation": r["relation"], "data": _loads(r["data"])} for r in edge_rows]
            hyper = None if same else [{"id": r["id"], "relation": r["relation"], "participants": _loads(r["participants"]),
                                        "data": _loads(r["data"])} for r in hyper_rows]
            labels = {r["id"]: r["label"] for r in c.execute("SELECT id, label FROM grants WHERE world_id=?", (world_id,))}                 if _has_table(c, "grants") else {}
            prin = [{"id": r["id"], "kind": r["kind"], "name": r["name"], "entity": r["entity_id"],
                     "capabilities": _loads(r["capabilities"]), "cursor": r["cursor_seq"],
                     "role": _col(r, "role"), "label": labels.get(_col(r, "grant_id")) or None,
                     "last_seen": _col(r, "last_seen"), "acted_t": _col(r, "acted_t")}
                    for r in c.execute("SELECT * FROM principal WHERE world_id=?", (world_id,))]
            sched = [{"id": r["id"], "t": r["t"], "kind": r["kind"], "entity": r["entity_id"],
                      "payload": _loads(r["payload"]), "every": r["every"]}
                     for r in c.execute("SELECT * FROM scheduled WHERE world_id=? AND kind NOT IN ('tick', 'finish') "
                                        "ORDER BY t", (world_id,))]
            ticks = c.execute("SELECT COUNT(*) FROM scheduled WHERE world_id=? AND kind IN ('tick', 'finish')",
                              (world_id,)).fetchone()[0]
            maxseq = c.execute("SELECT COALESCE(MAX(seq),0) FROM event WHERE world_id=?", (world_id,)).fetchone()[0]
            evs = [{"seq": r["seq"], "t": r["t"], "kind": r["kind"], "actor": r["actor_id"], "target": r["target_id"],
                    "reach": r["reach"], "payload": _loads(r["payload"]), "caused_by": r["caused_by"],
                    "path": _loads(r["path"])}
                   for r in (c.execute("SELECT * FROM event WHERE world_id=? AND seq>? ORDER BY seq DESC LIMIT ?",
                                       (world_id, since, limit)) if past is None else
                             c.execute("SELECT * FROM event WHERE world_id=? AND seq<=? ORDER BY seq DESC LIMIT ?",
                                       (world_id, past["seq"], limit)))]
            schemas = None if same else {r["id"]: r["extends"] for r in schema_rows}
            spaces = None if same else {r["id"]: _loads(r["space"]) for r in schema_rows if r["space"]}
        meta = _loads(w["meta"]) or {}
        return {"ok": True, "world": {"id": w["id"], "name": w["name"], "root": w["root_id"], "t": w["t"],
                                      "running": bool(w["clock_running"]), "rate": w["clock_rate"],
                                      "turn": meta.get("turn_seconds"), "forked_from": meta.get("forked_from"),
                                      "policy": None, "folder": self.folder(w["id"]),
                                      # what the page needs to read seats and the day: when a seat counts as idle (world
                                      # seconds), when it is released (real seconds), how long a day is, and now (real)
                                      "idle_after": float(meta.get("idle_after", 900.0)),
                                      "claim_lapse": float(meta.get("claim_lapse", 900.0)),
                                      "day_seconds": float(meta.get("day_seconds") or 86400), "now": time.time()},
                "entities": ents, "principals": prin, "scheduled": sched, "ticks": ticks, "max_seq": maxseq,
                "events": list(reversed(evs)), "sig": new_sig,
                "first": {"seq": first["seq"], "t": first["t"]} if first else None,
                **({"at": past} if past is not None else {}),
                **({"ids": ids, "diff": True} if ids is not None else {}),
                **({} if same else {"edges": edges, "hyperedges": hyper, "schemas": schemas, "spaces": spaces})}

    def answer(self, path: str, query: dict[str, list[str]], only: str | None = None) -> tuple[int, str, bytes]:
        """One request of the viewer's page, as (status, content type, body). path is relative to the viewer's root
        ("" or "/" is the page). only=<world id> is a grant's reach: that world and nothing else."""
        try:
            if path in ("", "/"):
                return 200, "text/html; charset=utf-8", PAGE.read_bytes()
            if path == "/info.json":
                where = {"db": self.db.name if only else str(self.db), "root": "" if only else str(self.root)}
                return 200, "application/json", json.dumps(where).encode()
            if path == "/worlds.json":
                return 200, "application/json", json.dumps(self.worlds(only)).encode()
            if path == "/state.json":
                world = query.get("world", [None])[0]
                if only is not None:
                    world = only
                since = int(query.get("since", ["0"])[0])
                limit = max(1, min(int(query.get("limit", ["60"])[0]), 500))
                after = query.get("after", [None])[0]
                sig = query.get("sig", [None])[0]
                at = query.get("at", [None])[0]
                at_t = query.get("at_t", [None])[0]
                body = self.state(world, since, limit, after=int(after) if after not in (None, "") else None, sig=sig,
                                  at=int(at) if at not in (None, "") else None,
                                  at_t=float(at_t) if at_t not in (None, "") else None)
                return 200, "application/json", json.dumps(body, separators=(",", ":")).encode()
            return 404, "application/json", json.dumps({"ok": False, "reason": f"nothing at {path} in the viewer",
                                                        "hint": "the viewer serves /, /worlds.json and /state.json"}).encode()
        except (sqlite3.OperationalError, ValueError) as e:
            return 503, "application/json", json.dumps({"ok": False, "reason": str(e)}).encode()


class Handler(BaseHTTPRequestHandler):
    """The standalone server's request handler: the page and its data for whoever can reach the port."""
    reader: Reader

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self) -> None:
        u = urlparse(self.path)
        code, ctype, body = self.reader.answer(u.path if u.path != "/" else "", parse_qs(u.query))
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None, help="the database; default: $EMBODY_DB, embody.db, or a legacy worlds/embody.db")
    ap.add_argument("--workspace", default=None, help="the folder of worlds/ and packs/; default: the database's")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else find_db(Path(a.workspace) if a.workspace else Path("."))
    Handler.reader = Reader(db, Path(a.workspace) if a.workspace else None)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"embody watch: http://{a.host}:{a.port}/  db={db}  workspace={Handler.reader.root}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
