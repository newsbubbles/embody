"""SQLite persistence for embody worlds.

One file holds one or more worlds. Every table is keyed by world_id. The
event table is the append-only log; everything else is a projection of it.
The schema is plain SQL so a Postgres driver later is a port, not a redesign.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS world (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    seed INTEGER NOT NULL,
    t REAL NOT NULL DEFAULT 0,
    clock_rate REAL NOT NULL DEFAULT 1,
    clock_running INTEGER NOT NULL DEFAULT 0,
    root_id TEXT,
    counters TEXT NOT NULL DEFAULT '{}',
    meta TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS schema (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    extends TEXT,
    doc TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT '{}',
    space TEXT,
    actions TEXT NOT NULL DEFAULT '{}',
    listeners TEXT NOT NULL DEFAULT '[]',
    behaviors TEXT NOT NULL DEFAULT '[]',
    senses TEXT NOT NULL DEFAULT '[]',
    version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (world_id, id)
);
CREATE TABLE IF NOT EXISTS script (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    source TEXT NOT NULL,
    doc TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (world_id, id)
);
CREATE TABLE IF NOT EXISTS entity (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    type TEXT NOT NULL,
    parent_id TEXT,
    name TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT '{}',
    pos TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_seq INTEGER NOT NULL,
    updated_seq INTEGER NOT NULL,
    PRIMARY KEY (world_id, id)
);
CREATE INDEX IF NOT EXISTS entity_parent ON entity (world_id, parent_id);
CREATE INDEX IF NOT EXISTS entity_type ON entity (world_id, type);
CREATE TABLE IF NOT EXISTS edge (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    source TEXT NOT NULL, target TEXT NOT NULL,
    relation TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (world_id, id)
);
CREATE INDEX IF NOT EXISTS edge_source ON edge (world_id, source, relation);
CREATE INDEX IF NOT EXISTS edge_target ON edge (world_id, target, relation);
CREATE TABLE IF NOT EXISTS hyperedge (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    relation TEXT NOT NULL,
    participants TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (world_id, id)
);
CREATE TABLE IF NOT EXISTS event (
    world_id TEXT NOT NULL, seq INTEGER NOT NULL,
    t REAL NOT NULL,
    kind TEXT NOT NULL,
    actor_id TEXT,
    target_id TEXT,
    reach INTEGER NOT NULL DEFAULT 1,
    payload TEXT NOT NULL DEFAULT '{}',
    caused_by INTEGER,
    path TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (world_id, seq)
);
CREATE INDEX IF NOT EXISTS event_target ON event (world_id, target_id, seq);
CREATE TABLE IF NOT EXISTS scheduled (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    t REAL NOT NULL,
    kind TEXT NOT NULL,
    entity_id TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    every REAL,
    PRIMARY KEY (world_id, id)
);
CREATE INDEX IF NOT EXISTS scheduled_t ON scheduled (world_id, t);
CREATE TABLE IF NOT EXISTS principal (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    capabilities TEXT NOT NULL DEFAULT '[]',
    entity_id TEXT,
    cursor_seq INTEGER NOT NULL DEFAULT 0,
    role TEXT,
    grant_id TEXT,
    last_seen REAL,
    last_act REAL,
    PRIMARY KEY (world_id, id)
);
CREATE TABLE IF NOT EXISTS grants (
    world_id TEXT NOT NULL, id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    role TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT '[]',
    entity_id TEXT,
    template TEXT,
    label TEXT NOT NULL DEFAULT '',
    token_hash TEXT,
    created REAL NOT NULL,
    expires REAL,
    revoked INTEGER NOT NULL DEFAULT 0,
    last_used REAL,
    PRIMARY KEY (world_id, id)
);
CREATE INDEX IF NOT EXISTS grants_token ON grants (token_hash);
"""

# Columns added after a table was first shipped: a database from before gets them on open.
_ADDED_COLS = {"principal": (("role", "TEXT"), ("grant_id", "TEXT"), ("last_seen", "REAL"), ("last_act", "REAL")),
               "grants": (("brief", "TEXT"), ("code_hash", "TEXT"), ("code_expires", "REAL"), ("page", "TEXT"))}

JSON_COLS = {
    "world": {"counters", "meta"},
    "schema": {"state", "space", "actions", "listeners", "behaviors", "senses"},
    "script": set(),
    "entity": {"state", "pos"},
    "edge": {"data"},
    "hyperedge": {"participants", "data"},
    "event": {"payload", "path"},
    "scheduled": {"payload"},
    "principal": {"capabilities"},
    "grants": {"scope"},
}


def _dumps(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    """Thin dict-in, dict-out layer over SQLite. No business logic lives here."""

    def __init__(self, path: str | Path | None = None):
        self.path = str(path) if path else ":memory:"
        self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=OFF")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA_SQL)
        for table, cols in _ADDED_COLS.items():
            have = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            for col, typ in cols:
                if col not in have:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        self._depth = 0

    def close(self) -> None:
        self.conn.close()

    # ---- transactions ---------------------------------------------------

    def begin(self) -> None:
        if self._depth == 0:
            self.conn.execute("BEGIN")
        self._depth += 1

    def commit(self) -> None:
        self._depth -= 1
        if self._depth == 0:
            self.conn.execute("COMMIT")

    def rollback(self) -> None:
        self._depth = 0
        self.conn.execute("ROLLBACK")

    # ---- generic row helpers --------------------------------------------

    def _encode(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for k, v in row.items():
            if k in JSON_COLS[table]:
                out[k] = None if v is None else _dumps(v)
            elif isinstance(v, bool):
                out[k] = int(v)
            else:
                out[k] = v
        return out

    def _decode(self, table: str, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        for k in JSON_COLS[table]:
            if k in out and out[k] is not None:
                out[k] = json.loads(out[k])
        return out

    def put(self, table: str, row: dict[str, Any]) -> None:
        enc = self._encode(table, row)
        cols = ", ".join(enc)
        marks = ", ".join("?" for _ in enc)
        self.conn.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", list(enc.values()))

    def get(self, table: str, world_id: str | None, id: str) -> dict[str, Any] | None:
        if table == "world":
            cur = self.conn.execute("SELECT * FROM world WHERE id=?", (id,))
        else:
            cur = self.conn.execute(f"SELECT * FROM {table} WHERE world_id=? AND id=?", (world_id, id))
        return self._decode(table, cur.fetchone())

    def delete(self, table: str, world_id: str, id: str) -> None:
        self.conn.execute(f"DELETE FROM {table} WHERE world_id=? AND id=?", (world_id, id))

    def set(self, table: str, world_id: str, id: str, **fields: Any) -> None:
        """Change named columns of one row; the row must exist."""
        enc = self._encode(table, fields)
        sets = ", ".join(f"{k}=?" for k in enc)
        self.conn.execute(f"UPDATE {table} SET {sets} WHERE world_id=? AND id=?", [*enc.values(), world_id, id])

    def query(self, table: str, where: str = "", params: Iterable[Any] = (), order: str = "",
              limit: int | None = None) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {table}"
        if where:
            sql += " WHERE " + where
        if order:
            sql += " ORDER BY " + order
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        cur = self.conn.execute(sql, list(params))
        return [self._decode(table, r) for r in cur.fetchall()]

    def count(self, table: str, where: str = "", params: Iterable[Any] = ()) -> int:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += " WHERE " + where
        return int(self.conn.execute(sql, list(params)).fetchone()[0])

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, list(params))

    # ---- world-specific ---------------------------------------------------

    def list_worlds(self) -> list[dict[str, Any]]:
        return [self._decode("world", r) for r in self.conn.execute("SELECT * FROM world ORDER BY name").fetchall()]

    def next_seq(self, world_id: str) -> int:
        row = self.conn.execute("SELECT MAX(seq) FROM event WHERE world_id=?", (world_id,)).fetchone()
        return (row[0] or 0) + 1
