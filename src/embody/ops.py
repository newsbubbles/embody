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
from .world import Rejected, World, _INTERNAL_KINDS, _PRIVATE_KINDS, _public_event

AUTHOR = "author"
OBSERVER = "observer"
# State keys only the entity itself (its mind) and authors ever see.
_ALWAYS_SECRET = frozenset({"memory", "brief", "goals"})
# Relations whose edge data is world structure, readable by anyone who sees the edge.
_PUBLIC_RELATIONS = frozenset({"connects_to"})


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
                        "running": s["clock"]["running"], "forked_from": w.meta().get("forked_from")})
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

    def fork_world(self, source_id: str, id: str, name: str = "") -> World:
        """Copy a world, state and full history, under a new id. Principals are not copied: a fork starts
        with nobody in it. The source is untouched."""
        src = self.world(source_id)
        if self.store.get("world", None, id):
            raise Rejected(f"world {id!r} already exists", hint="pick another id")
        st = self.store
        st.begin()
        try:
            row = dict(src._row)
            row["id"] = id
            row["name"] = name or f"{src.name} (fork)"
            meta = dict(row.get("meta") or {})
            meta["forked_from"] = {"world": source_id, "seq": st.next_seq(source_id) - 1, "t": src.t}
            row["meta"] = meta
            st.put("world", row)
            for table in ("schema", "script", "entity", "edge", "hyperedge", "event", "scheduled"):
                for r in st.query(table, "world_id=?", (source_id,)):
                    r = dict(r)
                    r["world_id"] = id
                    st.put(table, r)
            w = World.open(st, id)
            w.emit("forked", actor=None, target=w.root_id, reach=0,
                   payload={"from": source_id, "at_seq": meta["forked_from"]["seq"], "t": src.t})
            st.commit()
        except Exception:
            st.rollback()
            raise
        self._worlds[id] = w
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
            self.world.refresh()
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

    def fork_world(self, source: str, id: str, name: str = "") -> dict[str, Any]:
        """(author) A new game on the same world state: everything copied, history kept, nobody embodied.
        Point this session at the fork afterwards with use or join."""
        self._need(AUTHOR)
        w = self.engine.fork_world(source, id, name)
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
            cursor = w.entity_cursor(me)  # the entity's own "since I last looked", whoever drives it
        if cursor is None:
            cursor = max(0, w.store.next_seq(w.id) - 1 - events)
        ent = w.need(me)
        here_id = ent["parent_id"]
        here = w.get(here_id) if here_id else None
        ck = w.clock()
        bundle: dict[str, Any] = {
            "world": w.id, "t": w.t,
            "clock": {"running": ck["running"], "rate": ck["rate"], "turn": w.meta().get("turn_seconds")},
            "ambient": self._ambient(here),
            "you": self._card(ent, full=True),
            "goals": [g for g in ent["state"].get("goals") or [] if g.get("status", "active") == "active"],
            "holding": [self._card(c) for c in w.children(me)],
            "here": self._place_card(here) if here else None,
            "present": [self._card(c) for c in w.children(here_id) if c["id"] != me and not c["state"].get("hidden")]
            if here_id else [],
            "exits": self._exits(here_id) if here_id else [],
            "relations": self._relations(me),
            "knows": self._knows(me),
            "known_places": [{"id": pid, "name": w.get(pid)["name"]} for pid in w.known_places(me) if w.get(pid)],
            "affordances": [a for a in w.affordances(me)],
            "events": self._events_for(me, w.events(since=cursor, touching=me, limit=events)),
            "cursor": w.store.next_seq(w.id) - 1,
        }
        if p is not None:
            w.set_cursor(self.pid, bundle["cursor"])
        else:
            w.set_entity_cursor(me, bundle["cursor"])
        return bundle

    def _ambient(self, here: dict[str, Any] | None) -> dict[str, Any]:
        """Facts every perceive carries: the root's `ambient` dict (time of day, weather, light) with the
        place's own `ambient` laid over it. Worlds patch these; the engine only shows them."""
        w = self.world
        root = w.get(w.root_id)
        out = dict((root["state"].get("ambient") or {}) if root else {})
        if here:
            out.update(here["state"].get("ambient") or {})
        return out

    def _privileged(self) -> bool:
        return AUTHOR in self.capabilities or OBSERVER in self.capabilities

    def _events_for(self, me: str | None, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The public view of events for one viewer. Authors and observers see everything but the internal
        kinds. An embodied viewer never sees another entity's private events (remembered, intended) and sees
        `patched` only on itself; an author's edit to another entity is not news, its result is in perceive."""
        w = self.world
        out = []
        full = self._privileged()
        for e in rows:
            if e["kind"] in _INTERNAL_KINDS:
                continue
            if not full and e["target_id"] != me:
                if e["kind"] in _PRIVATE_KINDS:
                    continue
                if e["kind"] == "patched":
                    # an author's edit to someone else is the world changing under you, not news you heard;
                    # what it changed shows in the next perceive, the raw diff stays with the author
                    continue
            out.append(_public_event(e))
        return out

    def _knows(self, me: str) -> list[dict[str, Any]]:
        """Who this entity knows: each `knows` edge with its data (standing, notes) and the last exchanges
        between the two, pulled from the log. The log stays the single source of truth."""
        w = self.world
        out = []
        for e in w.edges(me, "knows", "out"):
            o = w.get(e["target"])
            if o is None:
                continue
            out.append({"who": e["target"], "name": o["name"], "type": o["type"], **e["data"],
                        "here": o["parent_id"] == w.need(me)["parent_id"],
                        "last_exchanges": [{"t": x["t"], "who": x["actor"], "kind": x["kind"],
                                            "text": x["payload"].get("text") or x["payload"].get("about")}
                                           for x in w.exchanges(me, e["target"], limit=5)]})
        return out[:30]

    def _visible_state(self, e: dict[str, Any], full: bool = False) -> dict[str, Any]:
        secret = set(e["state"].get("secret", [])) | _ALWAYS_SECRET
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
        full = AUTHOR in self.capabilities or OBSERVER in self.capabilities
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
            card["knows"] = self._knows(eid)
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
        me = touching if not self._privileged() else None
        return self._events_for(me, w.events(since=since, until=until, kinds=kinds, touching=touching,
                                             limit=min(limit, 500)))

    # ---- acting -----------------------------------------------------------------------

    def act(self, verb: str, target: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """One deed. The result carries every event that touched you since you last looked: what the act
        caused, what the turn brought, and what others did near you in between (a line addressed to you
        while you were deciding), so a player or a mind never has to perceive again to catch up."""
        self._tick()
        me = self._me()
        p = self._principal()
        since = p["cursor_seq"] if p else self.world.store.next_seq(self.world.id) - 1
        tid = self._resolve(target) if target else None
        r = self.world.act(me, verb, tid, params, principal_id=self.pid)
        r = self._turn(r)
        w = self.world
        r["events"] = self._events_for(me, w.events(since=since, touching=me, limit=200))
        r["cursor"] = w.store.next_seq(w.id) - 1
        w.set_cursor(self.pid, r["cursor"])
        return r

    def _turn(self, r: dict[str, Any]) -> dict[str, Any]:
        """Turn-based play: with the clock paused and meta.turn_seconds set, each act of an embodied principal
        moves the world by one turn (or by the act's own duration when that is longer), so behaviors and
        timers get their move between a player's actions."""
        w = self.world
        turn = float(w.meta().get("turn_seconds") or 0)
        if turn <= 0 or w.clock()["running"]:
            return r
        dt = max(turn, float(r.get("duration") or 0))
        evs = w.step(dt)
        if evs:
            r["events"] = list(r.get("events", [])) + evs
        r["elapsed"] = dt
        r["t"] = w.t
        return r

    def act_many(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Ordered. Stops at the first rejection and returns what happened up to it."""
        done = []
        for i, s in enumerate(steps):
            try:
                done.append(self.act(s["verb"], s.get("target"), s.get("params")))
            except Rejected as r:
                return {"ok": False, "done": done, "failed_at": i, "step": s, **r.to_dict()}
        return {"ok": True, "done": done}

    def say(self, text: str, reach: int = 1, to: str | None = None) -> dict[str, Any]:
        """Speak as the entity you embody. `to` addresses someone here; the room still hears it."""
        self._tick()
        me = self._me()
        ev = self.world.say(me, text, reach=reach, to=self._resolve(to) if to else None)
        self.world._bump_cursor(self.pid)
        return {"ok": True, "event": _public_event(ev)}

    def say_as(self, entity: str, text: str, reach: int = 1, to: str | None = None) -> dict[str, Any]:
        """Author only: a free line from any entity. How a narrator gives an NPC words its table does not have."""
        self._need(AUTHOR)
        self._tick()
        ev = self.world.say(self._resolve(entity), text, reach=reach, to=self._resolve(to) if to else None)
        return {"ok": True, "event": _public_event(ev)}

    def remember(self, text: str, entity: str | None = None) -> dict[str, Any]:
        """Write a note into an entity's secret memory: who you are, what you want, what you decided, what you
        think of someone. Your own entity by default; authors may write for any entity."""
        self._tick()
        if entity is not None:
            self._need(AUTHOR)
            eid = self._resolve(entity)
        else:
            eid = self._me()
        note = self.world.remember(eid, text, actor=eid)
        if entity is None:
            self.world._bump_cursor(self.pid)
        return {"ok": True, "entity": eid, "note": note, "memory_size": len(self.world.need(eid)["state"].get("memory", []))}

    def intend(self, text: str | None = None, why: str | None = None, id: str | None = None,
               status: str | None = None, priority: int | None = None, entity: str | None = None) -> dict[str, Any]:
        """Track a goal. New goal: intend(text, why). Change one: intend(id=..., status='done'|'dropped'|'active',
        text=..., why=..., priority=...). Goals are secret state on the entity; active ones come back in every
        perceive under `goals`. Authors may pass entity=<id or name> to set goals for any entity."""
        self._tick()
        if entity is not None:
            self._need(AUTHOR)
            eid = self._resolve(entity)
        else:
            eid = self._me()
        g = self.world.intend(eid, text=text, why=why, id=id, status=status, priority=priority, actor=eid)
        if entity is None:
            self.world._bump_cursor(self.pid)
        goals = self.world.need(eid)["state"].get("goals") or []
        return {"ok": True, "entity": eid, "goal": g,
                "goals": [x for x in goals if x.get("status", "active") == "active"]}

    def recall(self, about: str | None = None, relation: str | None = None, limit: int = 20,
               entity: str | None = None) -> dict[str, Any]:
        """A graph query from one entity's point of view, with its permissions. Without `about`: everyone and
        everything linked to you (edges, group relations), with the data you are allowed to read. With `about`:
        all you know about one entity, drawn from the graph, the log and your own notes: your edge to them,
        what they have told you, what you have said and done to each other, the notes and goals that name them.
        Edge data is yours to read when the edge starts at you or is world structure; what others think of you
        stays theirs. Authors and observers read everything and may pass entity=<id or name>."""
        self._tick()
        w = self.world
        full = self._privileged()
        if entity is not None:
            if not full:
                raise Rejected("recalling from another entity needs the author or observer capability",
                               hint="recall() works from the entity you embody")
            me = self._resolve(entity)
        else:
            me = self._me()
        limit = max(1, min(int(limit), 100))
        ent = w.need(me)

        def edge_view(e: dict[str, Any]) -> dict[str, Any]:
            other = e["target"] if e["source"] == me else e["source"]
            o = w.get(other)
            readable = full or e["source"] == me or e["relation"] in _PUBLIC_RELATIONS or bool(e["data"].get("public"))
            v = {"relation": e["relation"], "direction": "out" if e["source"] == me else "in",
                 "with": other, "name": o["name"] if o else None, "type": o["type"] if o else None,
                 "here": bool(o and o["parent_id"] == ent["parent_id"])}
            if readable:
                v["data"] = e["data"]
            return v

        if about is None:
            edges = [edge_view(e) for e in w.edges(me, relation, "both") if e["relation"] != "connects_to"]
            groups = [{"relation": h["relation"], "participants": h["participants"], "data": h["data"], "id": h["id"]}
                      for h in w.hyperedges(me, relation)]
            return {"entity": me, "edges": edges[:limit], "groups": groups[:limit],
                    "goals": [g for g in ent["state"].get("goals") or [] if g.get("status", "active") == "active"],
                    "known_places": [{"id": pid, "name": w.get(pid)["name"]} for pid in w.known_places(me) if w.get(pid)]}

        them = self._resolve(about)
        o = w.need(them)
        known = {e["target"] for e in w.edges(me, "knows", "out")}
        if not full and o["state"].get("hidden") and o["parent_id"] != ent["parent_id"] and them not in known:
            # a hidden entity that never crossed your path is nobody to you
            raise Rejected(f"you know nothing of {about!r}", hint="recall() lists who you know")
        name = (o["name"] or "").lower()
        mine = [edge_view(e) for e in w.edges(me, relation, "both") if e["source"] == them or e["target"] == them]
        shared = [{"relation": h["relation"], "participants": h["participants"], "data": h["data"], "id": h["id"]}
                  for h in w.hyperedges(me, relation) if them in h["participants"]]
        rows = w.store.query(
            "event", "world_id=? AND ((actor_id=? AND target_id=?) OR (actor_id=? AND target_id=?))",
            (w.id, me, them, them, me), order="seq DESC", limit=limit)
        between = self._events_for(me, list(reversed(rows)))
        notes = [n for n in (ent["state"].get("memory") or []) if name and name in str(n.get("text", "")).lower()]
        goals = [g for g in (ent["state"].get("goals") or [])
                 if name and (name in str(g.get("text", "")).lower() or name in str(g.get("why") or "").lower())]
        return {"entity": me, "about": self._card(o, full=full), "edges": mine, "groups": shared,
                "exchanges": [{"t": x["t"], "who": x["actor"], "kind": x["kind"],
                               "text": x["payload"].get("text") or x["payload"].get("about")}
                              for x in w.exchanges(me, them, limit=min(limit, 10))],
                "between": between[-limit:], "notes": notes[-limit:], "goals": goals,
                "here": o["parent_id"] == ent["parent_id"]}

    def wait(self, timeout: float = 30.0, kinds: list[str] | None = None, poll: float = 0.1, full: bool = False,
             clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
        """Block until an event touches me (or the timeout). Returns the light bundle: the hour, where I am,
        who is here and the new events, with the cursor moved past them. `full=True` returns perceive()
        instead. A mind loops on this, so a quiet minute costs a few lines, not the whole card."""
        me = self._me()
        p = self._principal()
        start = clock()
        while True:
            self._tick()
            w = self.world
            evs = [e for e in self._events_for(me, w.events(since=p["cursor_seq"], touching=me, limit=50))
                   if not kinds or e["kind"] in kinds]
            timed_out = clock() - start >= timeout
            if evs or timed_out:
                if full:
                    b = self.perceive()
                else:
                    ent = w.need(me)
                    here = w.get(ent["parent_id"]) if ent["parent_id"] else None
                    b = {"world": w.id, "t": w.t, "ambient": self._ambient(here),
                         "here": {"id": here["id"], "name": here["name"]} if here else None,
                         "present": [{"id": c["id"], "name": c["name"]} for c in w.children(ent["parent_id"])
                                     if c["id"] != me and not c["state"].get("hidden")] if here else [],
                         "events": evs, "cursor": w.store.next_seq(w.id) - 1}
                    w.set_cursor(self.pid, b["cursor"])
                if timed_out:
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

    def patch(self, entity: str, changes: dict[str, Any], replace: bool = False) -> dict[str, Any]:
        """Dict values merge into existing dicts (add one dialog topic without resending the rest);
        replace=True sets each key whole; a None value deletes the key."""
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self.world.patch(eid, changes, actor=self._actor_or_none(), replace=replace)
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

    def unschedule(self, id: str) -> dict[str, Any]:
        """Cancel a pending timer by its id from timers()."""
        self._need(AUTHOR)
        item = self.world.unschedule(id)
        return {"ok": True, "unscheduled": id, "kind": item["kind"]}

    def clock(self, run: bool | None = None, rate: float | None = None, step: float | None = None,
              turn: float | None = None) -> dict[str, Any]:
        """Read or set the clock. run/rate: realtime. step: advance by n seconds now. turn: seconds the world
        moves after each embodied act while paused (turn-based chat play); 0 turns it off."""
        if run is not None or rate is not None or step is not None or turn is not None:
            self._need(AUTHOR)
        self._tick()
        w = self.world
        out: dict[str, Any] = {}
        if run is not None or rate is not None:
            w.set_clock(running=run, rate=rate)
        if turn is not None:
            w.set_meta({"turn_seconds": float(turn) if turn > 0 else None})
        if step is not None:
            out["events"] = w.step(step)
        out.update(w.clock())
        out["turn"] = w.meta().get("turn_seconds")
        out["timers"] = self._timers()
        return out

    def _timers(self, limit: int = 20) -> list[dict[str, Any]]:
        """Pending scheduled events, soonest first. Behaviors' ticks are left out."""
        w = self.world
        out = []
        for s in w.pending():
            if s["kind"] == "tick":
                continue
            e = w.get(s["entity_id"]) if s.get("entity_id") else None
            out.append({"id": s["id"], "kind": s["kind"], "at": s["t"], "in": round(s["t"] - w.t, 3),
                        "entity": s.get("entity_id"), "name": e["name"] if e else None,
                        "every": s.get("every"), "payload": s.get("payload") or {}})
            if len(out) >= limit:
                break
        return out

    def timers(self) -> list[dict[str, Any]]:
        """What is scheduled and when (fog in 38 s, dawn in 200 s). Ticks of behaviors are left out."""
        self._tick()
        return self._timers()

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
        """Author ops (spawn, patch, move, destroy) are the narrator's hand, not the character's. An entity actor
        on them made secret patches and notes show up in the embodying player's own feed. So: none."""
        return None


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
    "worlds", "use", "create_world", "fork_world", "join", "leave",
    "perceive", "inspect", "find", "history", "act", "act_many", "say", "remember", "intend", "recall", "wait",
    "define_schema", "define_script", "schemas", "scripts", "script_source",
    "spawn", "patch", "move", "destroy", "link", "connect", "unlink", "relate", "unrelate",
    "set_rule", "clear_rule", "schedule", "unschedule", "clock", "timers", "summary", "mirror", "act_as", "say_as",
]
