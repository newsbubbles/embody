"""Live world graph: a read-only web view of an embody database.

    uv run python tools/watch.py --db worlds/embody.db --port 8765

Opens the database read-only (SQLite WAL lets it read while the engine writes),
serves one page that polls /state.json and redraws when the event log grows.
Nothing here imports the engine or writes anything; it is a window, not a hand.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent


def _loads(v):
    if v is None:
        return None
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


class Reader:
    def __init__(self, db: Path):
        self.db = db

    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True, timeout=2.0)
        c.row_factory = sqlite3.Row
        return c

    def worlds(self) -> list[dict]:
        # newest first: a fork made a moment ago is what the watcher wants to see
        with self.conn() as c:
            out = []
            for r in c.execute("SELECT id, name, t, clock_running, clock_rate, meta FROM world ORDER BY rowid DESC"):
                meta = _loads(r["meta"]) or {}
                out.append({"id": r["id"], "name": r["name"], "t": r["t"], "running": bool(r["clock_running"]),
                            "rate": r["clock_rate"], "forked_from": meta.get("forked_from"),
                            "turn": meta.get("turn_seconds")})
            return out

    def state(self, world_id: str | None, since: int, limit: int) -> dict:
        with self.conn() as c:
            if not world_id:
                row = c.execute("SELECT id FROM world ORDER BY rowid DESC LIMIT 1").fetchone()
                if row is None:
                    return {"ok": False, "reason": "no worlds in this database"}
                world_id = row["id"]
            w = c.execute("SELECT * FROM world WHERE id=?", (world_id,)).fetchone()
            if w is None:
                return {"ok": False, "reason": f"no world {world_id}"}
            ents = [{"id": r["id"], "type": r["type"], "parent": r["parent_id"], "name": r["name"],
                     "state": _loads(r["state"]), "pos": _loads(r["pos"]), "version": r["version"],
                     "updated_seq": r["updated_seq"]}
                    for r in c.execute("SELECT * FROM entity WHERE world_id=? ORDER BY created_seq", (world_id,))]
            edges = [{"id": r["id"], "source": r["source"], "target": r["target"], "relation": r["relation"],
                      "data": _loads(r["data"])}
                     for r in c.execute("SELECT * FROM edge WHERE world_id=?", (world_id,))]
            hyper = [{"id": r["id"], "relation": r["relation"], "participants": _loads(r["participants"]),
                      "data": _loads(r["data"])}
                     for r in c.execute("SELECT * FROM hyperedge WHERE world_id=?", (world_id,))]
            prin = [{"id": r["id"], "kind": r["kind"], "name": r["name"], "entity": r["entity_id"],
                     "capabilities": _loads(r["capabilities"]), "cursor": r["cursor_seq"]}
                    for r in c.execute("SELECT * FROM principal WHERE world_id=?", (world_id,))]
            sched = [{"id": r["id"], "t": r["t"], "kind": r["kind"], "entity": r["entity_id"],
                      "payload": _loads(r["payload"]), "every": r["every"]}
                     for r in c.execute("SELECT * FROM scheduled WHERE world_id=? ORDER BY t", (world_id,))]
            maxseq = c.execute("SELECT COALESCE(MAX(seq),0) FROM event WHERE world_id=?", (world_id,)).fetchone()[0]
            evs = [{"seq": r["seq"], "t": r["t"], "kind": r["kind"], "actor": r["actor_id"], "target": r["target_id"],
                    "reach": r["reach"], "payload": _loads(r["payload"]), "caused_by": r["caused_by"],
                    "path": _loads(r["path"])}
                   for r in c.execute("SELECT * FROM event WHERE world_id=? AND seq>? ORDER BY seq DESC LIMIT ?",
                                      (world_id, since, limit))]
            schemas = {r["id"]: r["extends"] for r in c.execute("SELECT id, extends FROM schema WHERE world_id=?", (world_id,))}
        meta = _loads(w["meta"]) or {}
        return {"ok": True, "world": {"id": w["id"], "name": w["name"], "root": w["root_id"], "t": w["t"],
                                      "running": bool(w["clock_running"]), "rate": w["clock_rate"],
                                      "turn": meta.get("turn_seconds"), "forked_from": meta.get("forked_from"),
                                      "policy": None},
                "entities": ents, "edges": edges, "hyperedges": hyper, "principals": prin, "scheduled": sched,
                "schemas": schemas, "max_seq": maxseq, "events": list(reversed(evs))}


class Handler(BaseHTTPRequestHandler):
    reader: Reader

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                self._send(200, (HERE / "watch.html").read_bytes(), "text/html; charset=utf-8")
            elif u.path == "/worlds.json":
                self._send(200, json.dumps(self.reader.worlds()).encode(), "application/json")
            elif u.path == "/state.json":
                world = q.get("world", [None])[0]
                since = int(q.get("since", ["0"])[0])
                limit = int(q.get("limit", ["60"])[0])
                self._send(200, json.dumps(self.reader.state(world, since, limit)).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")
        except sqlite3.OperationalError as e:
            self._send(503, json.dumps({"ok": False, "reason": str(e)}).encode(), "application/json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="worlds/embody.db")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    Handler.reader = Reader(Path(a.db))
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"embody watch: http://{a.host}:{a.port}/  db={a.db}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
