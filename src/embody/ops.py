"""The op table: what a connected harness (CLI, MCP, library) can do.

A Session is one principal's view of an Engine. Capabilities decide which ops
answer. Every op returns plain dicts and lists, bounded in size, and every
failure is a `Rejected` with a reason, a hint and alternatives.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .store import Store
from .world import Rejected, World, _INTERNAL_KINDS, _public_event

AUTHOR = "author"
OBSERVER = "observer"


class Engine:
    """Owns a store and the worlds in it. One per process."""

    def __init__(self, path: str | Path | None = None, mirror_root: str | Path | None = None):
        self.store = Store(path)
        self.mirror_root = Path(mirror_root) if mirror_root else (Path(path).parent / "mirror" if path else None)
        self._worlds: dict[str, World] = {}
        self._wall: dict[str, float] = {}
        self.now: Callable[[], float] = time.monotonic

    def worlds(self) -> list[dict[str, Any]]:
        out = []
        for row in self.store.list_worlds():
            w = self.world(row["id"])
            s = w.summary()
            out.append({"id": s["id"], "name": s["name"], "description": s["description"], "t": s["t"],
                        "entities": s["entities"], "principals": len(s["principals"]),
                        "running": s["clock"]["running"]})
        return out

    def world(self, world_id: str) -> World:
        w = self._worlds.get(world_id)
        if w is None:
            w = World.open(self.store, world_id)
            self._worlds[world_id] = w
        return w

    def create_world(self, name: str, seed: int = 0, id: str | None = None, description: str = "") -> World:
        w = World.create(self.store, name, seed=seed, id=id, description=description)
        self._worlds[w.id] = w
        return w

    def sync_clock(self, world_id: str, now: float | None = None) -> list[dict[str, Any]]:
        """If the world clock runs, advance it by the wall time elapsed since the last sync."""
        w = self.world(world_id)
        now = self.now() if now is None else now
        last = self._wall.get(world_id)
        self._wall[world_id] = now
        if not w.clock()["running"] or last is None:
            return []
        dt = (now - last) * w.clock()["rate"]
        return w.step(dt) if dt > 0 else []

    def session(self, principal_id: str, world_id: str | None = None, capabilities: list[str] | None = None,
                name: str = "") -> "Session":
        return Session(self, principal_id, world_id=world_id, capabilities=capabilities, name=name)


class Session:
    def __init__(self, engine: Engine, principal_id: str, world_id: str | None = None,
                 capabilities: list[str] | None = None, name: str = ""):
        self.engine = engine
        self.pid = principal_id
        self.name = name or principal_id
        self.world_id = world_id
        self.capabilities = list(capabilities or [])
        self.default_fuel = 20_000

    # ---- plumbing ---------------------------------------------------------

    @property
    def world(self) -> World:
        if not self.world_id:
            raise Rejected("no world chosen", hint="call worlds() then join(world, entity) or author with use(world)")
        return self.engine.world(self.world_id)

    def _principal(self) -> dict[str, Any]:
        p = self.world.principal(self.pid)
        if p is None:
            raise Rejected("you are not in this world", hint="join(world, entity) first")
        return p

    def _me(self) -> str:
        p = self._principal()
        if not p["entity_id"]:
            raise Rejected("you are not embodied", hint="join(world, entity) to embody something")
        if self.world.get(p["entity_id"]) is None:
            raise Rejected(f"the entity you embodied ({p['entity_id']}) no longer exists",
                           hint="join another entity")
        return p["entity_id"]

    def _need(self, cap: str) -> None:
        if cap not in self.capabilities:
            raise Rejected(f"this op needs the {cap!r} capability; you have {self.capabilities or 'none'}",
                           hint="connect with --as author to build worlds; embodied principals act through act()")

    def _tick(self) -> None:
        if self.world_id:
            self.engine.sync_clock(self.world_id)

    # ---- choosing a world -----------------------------------------------------

    def worlds(self) -> list[dict[str, Any]]:
        return self.engine.worlds()

    def use(self, world_id: str) -> dict[str, Any]:
        """Point this session at a world without embodying anything (authors, observers)."""
        self.engine.world(world_id)
        self.world_id = world_id
        return self.world.summary()

    def create_world(self, name: str, seed: int = 0, id: str | None = None, description: str = "") -> dict[str, Any]:
        self._need(AUTHOR)
        w = self.engine.create_world(name, seed=seed, id=id, description=description)
        self.world_id = w.id
        return w.summary()

    def join(self, world_id: str, entity: str) -> dict[str, Any]:
        self.engine.world(world_id)
        self.world_id = world_id
        w = self.world
        eid = self._resolve(entity)
        if OBSERVER in self.capabilities and AUTHOR not in self.capabilities:
            raise Rejected("observers do not embody", hint="use(world) then perceive(from=entity)")
        kind = AUTHOR if AUTHOR in self.capabilities else "agent"
        w.join(self.pid, eid, kind=kind, name=self.name, capabilities=self.capabilities)
        return self.perceive()

    def leave(self) -> dict[str, Any]:
        if self.world_id and self.world.principal(self.pid):
            self.world.leave(self.pid)
        return {"ok": True}

    def _resolve(self, ref: str) -> str:
        """An id, or a unique name (case-insensitive)."""
        w = self.world
        if w.get(ref):
            return ref
        hits = [e for e in w.find(name=ref, limit=10) if e["name"].lower() == ref.lower()]
        if len(hits) == 1:
            return hits[0]["id"]
        if not hits:
            raise Rejected(f"nothing called {ref!r}", hint="use an id from perceive or find(name=...)")
        raise Rejected(f"{len(hits)} entities are called {ref!r}: " + ", ".join(h["id"] for h in hits),
                       hint="use the id")

    # ---- perception --------------------------------------------------------------

    def perceive(self, cursor: int | None = None, from_entity: str | None = None, events: int = 30) -> dict[str, Any]:
        self._tick()
        w = self.world
        if from_entity is not None:
            if AUTHOR not in self.capabilities and OBSERVER not in self.capabilities:
                raise Rejected("perceiving from another entity needs the author or observer capability")
            me = self._resolve(from_entity)
            p = None
        else:
            me = self._me()
            p = self._principal()
        if cursor is None and p is not None:
            cursor = p["cursor_seq"]
        if cursor is None:
            cursor = max(0, w.store.next_seq(w.id) - 1 - events)
        ent = w.need(me)
        here_id = ent["parent_id"]
        here = w.get(here_id) if here_id else None
        bundle: dict[str, Any] = {
            "world": w.id, "t": w.t,
            "you": self._card(ent, full=True),
            "holding": [self._card(c) for c in w.children(me)],
            "here": self._place_card(here) if here else None,
            "present": [self._card(c) for c in w.children(here_id) if c["id"] != me and not c["state"].get("hidden")]
            if here_id else [],
            "exits": self._exits(here_id) if here_id else [],
            "relations": self._relations(me),
            "affordances": [a for a in w.affordances(me)],
            "events": [_public_event(e) for e in w.events(since=cursor, touching=me, limit=events)
                       if e["kind"] not in _INTERNAL_KINDS],
            "cursor": w.store.next_seq(w.id) - 1,
        }
        if p is not None:
            w.set_cursor(self.pid, bundle["cursor"])
        return bundle

    def _visible_state(self, e: dict[str, Any], full: bool = False) -> dict[str, Any]:
        secret = set(e["state"].get("secret", []))
        out = {}
        for k, v in e["state"].items():
            if k in ("rules", "secret", "space"):
                continue
            if not full and k in secret:
                continue
            out[k] = v
        return out

    def _card(self, e: dict[str, Any], full: bool = False) -> dict[str, Any]:
        w = self.world
        card = {"id": e["id"], "type": e["type"], "name": e["name"], "state": self._visible_state(e, full)}
        if e["pos"] is not None:
            card["pos"] = e["pos"]
        emb = w.embodied(e["id"])
        if emb:
            card["embodied_by"] = emb["id"]
        if w.children(e["id"]) and not full:
            card["contains"] = len(w.children(e["id"]))
        return card

    def _place_card(self, e: dict[str, Any]) -> dict[str, Any]:
        w = self.world
        card = self._card(e)
        card["breadcrumb"] = [{"id": a, "name": w.get(a)["name"]} for a in w.ancestors(e["id"]) if w.get(a)]
        sp = w.space_of(e["id"])
        if sp:
            card["space"] = sp
        return card

    def _exits(self, here_id: str) -> list[dict[str, Any]]:
        w = self.world
        out = []
        for e in w.edges(here_id, "connects_to", "out"):
            to = w.get(e["target"])
            if to is None:
                continue
            x: dict[str, Any] = {"to": e["target"], "name": to["name"], **{k: v for k, v in e["data"].items()}}
            via = e["data"].get("via")
            if via and w.get(via):
                v = w.get(via)
                x["via_name"] = v["name"]
                x["open"] = v["state"].get("open")
                x["locked"] = v["state"].get("locked")
            out.append(x)
        return out

    def _relations(self, me: str) -> list[dict[str, Any]]:
        w = self.world
        out = []
        for e in w.edges(me, None, "both"):
            if e["relation"] == "connects_to":
                continue
            other = e["target"] if e["source"] == me else e["source"]
            o = w.get(other)
            out.append({"relation": e["relation"], "direction": "out" if e["source"] == me else "in",
                        "with": other, "name": o["name"] if o else None, "data": e["data"]})
        for h in w.hyperedges(me):
            out.append({"relation": h["relation"], "participants": h["participants"], "data": h["data"], "id": h["id"]})
        return out[:50]

    def inspect(self, entity: str) -> dict[str, Any]:
        self._tick()
        w = self.world
        eid = self._resolve(entity)
        e = w.need(eid)
        full = AUTHOR in self.capabilities
        if not full:
            me = self._me()
            ok, why = w.reachable(me, eid)
            if not ok and eid not in w.ancestors(me):
                raise Rejected(why, hint="inspect works on what perceive shows")
        card = self._card(e, full=full)
        card["parent"] = e["parent_id"]
        card["schema_chain"] = [s["id"] for s in w.schema_chain(e["type"])]
        card["doc"] = w.schema(e["type"])["doc"]
        card["contents"] = [self._card(c) for c in w.children(eid) if full or not c["state"].get("hidden")]
        card["relations"] = self._relations(eid)
        card["actions"] = {v: {"doc": a.get("doc", ""), "targets": a.get("targets"), "params": a.get("params", {})}
                           for v, a in w.schema_actions(e["type"]).items() if full or not a.get("hidden")}
        if full:
            card["rules"] = e["state"].get("rules", [])
            card["version"] = e["version"]
        return card

    def find(self, type: str | None = None, name: str | None = None, under: str | None = None,
             parent: str | None = None, state: dict[str, Any] | None = None, limit: int = 30) -> list[dict[str, Any]]:
        self._tick()
        w = self.world
        if AUTHOR not in self.capabilities and OBSERVER not in self.capabilities:
            # an embodied principal searches what it can see: its place and its holdings
            me = self._me()
            scope = w.need(me)["parent_id"] or me
            under = under or scope
        rows = w.find(type=type, name=name, under=self._resolve(under) if under else None,
                      parent=self._resolve(parent) if parent else None, state=state, limit=min(limit, 100))
        return [self._card(r) for r in rows if AUTHOR in self.capabilities or not r["state"].get("hidden")]

    def history(self, since: int = 0, until: int | None = None, kinds: list[str] | None = None,
                touching: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self._tick()
        w = self.world
        if AUTHOR not in self.capabilities and OBSERVER not in self.capabilities:
            touching = self._me()
        elif touching:
            touching = self._resolve(touching)
        return [_public_event(e) for e in w.events(since=since, until=until, kinds=kinds, touching=touching,
                                                    limit=min(limit, 500)) if e["kind"] not in _INTERNAL_KINDS]

    # ---- acting -----------------------------------------------------------------------

    def act(self, verb: str, target: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._tick()
        me = self._me()
        tid = self._resolve(target) if target else None
        return self.world.act(me, verb, tid, params, principal_id=self.pid)

    def act_many(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Ordered. Stops at the first rejection and returns what happened up to it."""
        done = []
        for i, s in enumerate(steps):
            try:
                done.append(self.act(s["verb"], s.get("target"), s.get("params")))
            except Rejected as r:
                return {"ok": False, "done": done, "failed_at": i, "step": s, **r.to_dict()}
        return {"ok": True, "done": done}

    def say(self, text: str, reach: int = 1) -> dict[str, Any]:
        self._tick()
        me = self._me()
        ev = self.world.emit("say", actor=me, target=me, reach=reach, payload={"text": str(text)})
        self.world._bump_cursor(self.pid)
        return {"ok": True, "event": _public_event(ev)}

    def wait(self, timeout: float = 30.0, kinds: list[str] | None = None, poll: float = 0.1,
             clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
        """Block until an event touches me (or the timeout). Returns perceive() with the new events."""
        me = self._me()
        p = self._principal()
        start = clock()
        while True:
            self._tick()
            evs = [e for e in self.world.events(since=p["cursor_seq"], touching=me, limit=50)
                   if e["kind"] not in _INTERNAL_KINDS and (not kinds or e["kind"] in kinds)]
            if evs:
                return self.perceive()
            if clock() - start >= timeout:
                b = self.perceive()
                b["timed_out"] = True
                return b
            sleep(poll)

    # ---- authoring ------------------------------------------------------------------------

    def define_schema(self, id: str, **kw: Any) -> dict[str, Any]:
        self._need(AUTHOR)
        row = self.world.define_schema(id, **kw)
        return {"ok": True, "schema": id, "version": row["version"]}

    def define_script(self, id: str, source: str, doc: str = "") -> dict[str, Any]:
        self._need(AUTHOR)
        row = self.world.define_script(id, source, doc)
        return {"ok": True, "script": id, "version": row["version"]}

    def schemas(self) -> list[dict[str, Any]]:
        self._need(AUTHOR)
        return [{"id": s["id"], "extends": s["extends"], "doc": s["doc"], "actions": sorted(s["actions"]),
                 "listeners": s["listeners"], "behaviors": s["behaviors"], "state": s["state"]}
                for s in self.world.schemas()]

    def scripts(self) -> list[dict[str, Any]]:
        self._need(AUTHOR)
        return [{"id": s["id"], "doc": s["doc"], "version": s["version"], "lines": s["source"].count("\n") + 1}
                for s in self.world.scripts()]

    def script_source(self, id: str) -> dict[str, Any]:
        self._need(AUTHOR)
        row = self.world.store.get("script", self.world.id, id)
        if row is None:
            raise Rejected(f"no script {id!r}", hint="scripts() lists them")
        return {"id": id, "source": row["source"], "doc": row["doc"], "version": row["version"]}

    def spawn(self, type: str, parent: str, name: str = "", state: dict[str, Any] | None = None,
              pos: list[float] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        eid = self.world.spawn(type, self._resolve(parent), name=name, state=state, pos=pos, actor=self._actor_or_none())
        return self._card(self.world.need(eid), full=True)

    def patch(self, entity: str, changes: dict[str, Any]) -> dict[str, Any]:
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self.world.patch(eid, changes, actor=self._actor_or_none())
        return self._card(self.world.need(eid), full=True)

    def move(self, entity: str, parent: str, pos: list[float] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self.world.move(eid, self._resolve(parent), pos=pos, actor=self._actor_or_none())
        return self._card(self.world.need(eid), full=True)

    def destroy(self, entity: str) -> dict[str, Any]:
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self.world.destroy(eid, actor=self._actor_or_none())
        return {"ok": True, "destroyed": eid}

    def link(self, source: str, target: str, relation: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        gid = self.world.link(self._resolve(source), self._resolve(target), relation, data)
        return {"ok": True, "edge": gid}

    def connect(self, a: str, b: str, via: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Two-way connects_to between places, optionally through a door-like entity."""
        self._need(AUTHOR)
        d = dict(data or {})
        if via:
            d["via"] = self._resolve(via)
        ea, eb = self._resolve(a), self._resolve(b)
        return {"ok": True, "edges": [self.world.link(ea, eb, "connects_to", d), self.world.link(eb, ea, "connects_to", d)]}

    def unlink(self, source: str, target: str, relation: str) -> dict[str, Any]:
        self._need(AUTHOR)
        n = self.world.unlink(self._resolve(source), self._resolve(target), relation)
        return {"ok": True, "removed": n}

    def relate(self, relation: str, participants: list[str], data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        hid = self.world.relate(relation, [self._resolve(p) for p in participants], data)
        return {"ok": True, "relation": hid}

    def unrelate(self, id: str) -> dict[str, Any]:
        self._need(AUTHOR)
        self.world.unrelate(id)
        return {"ok": True}

    def set_rule(self, entity: str, script: str, kinds: list[str] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        self.world.set_rule(self._resolve(entity), script, kinds)
        return {"ok": True}

    def clear_rule(self, entity: str, script: str) -> dict[str, Any]:
        self._need(AUTHOR)
        self.world.clear_rule(self._resolve(entity), script)
        return {"ok": True}

    def schedule(self, after: float, kind: str, entity: str | None = None, payload: dict[str, Any] | None = None,
                 every: float | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        sid = self.world.schedule(after, kind, entity=self._resolve(entity) if entity else None, payload=payload,
                                  every=every)
        return {"ok": True, "scheduled": sid}

    def clock(self, run: bool | None = None, rate: float | None = None, step: float | None = None) -> dict[str, Any]:
        if run is not None or rate is not None or step is not None:
            self._need(AUTHOR)
        self._tick()
        w = self.world
        out: dict[str, Any] = {}
        if run is not None or rate is not None:
            w.set_clock(running=run, rate=rate)
        if step is not None:
            out["events"] = w.step(step)
        out.update(w.clock())
        return out

    def summary(self) -> dict[str, Any]:
        self._tick()
        return self.world.summary()

    def mirror(self, path: str | None = None) -> dict[str, Any]:
        """Write the markdown projection of this world to a directory (default: beside the database)."""
        from .mirror import Mirror
        self._tick()
        root = Path(path) if path else (self.engine.mirror_root / self.world.id if self.engine.mirror_root else None)
        if root is None:
            raise Rejected("no mirror directory", hint="pass path=... or open the engine with a database file")
        return Mirror(self.world, root).write()

    def act_as(self, entity: str, verb: str, target: str | None = None,
               params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Author only: make any entity act. How a GM drives an NPC without embodying it."""
        self._need(AUTHOR)
        self._tick()
        return self.world.act(self._resolve(entity), verb, self._resolve(target) if target else None, params)

    def _actor_or_none(self) -> str | None:
        p = self.world.principal(self.pid)
        return p["entity_id"] if p else None


def call(session: Session, op: str, **kw: Any) -> Any:
    """Dispatch by name, with the error shape every harness gets."""
    fn = getattr(session, op, None)
    if fn is None or op.startswith("_"):
        return Rejected(f"no op {op!r}", hint="ops: " + ", ".join(OPS)).to_dict()
    try:
        return fn(**kw)
    except Rejected as r:
        return r.to_dict()
    except TypeError as e:
        return Rejected(f"{op}: {e}", hint=f"see help for {op}").to_dict()


OPS = [
    "worlds", "use", "create_world", "join", "leave",
    "perceive", "inspect", "find", "history", "act", "act_many", "say", "wait",
    "define_schema", "define_script", "schemas", "scripts", "script_source",
    "spawn", "patch", "move", "destroy", "link", "connect", "unlink", "relate", "unrelate",
    "set_rule", "clear_rule", "schedule", "clock", "summary", "mirror", "act_as",
]
