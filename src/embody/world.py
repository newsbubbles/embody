"""The world: a hierarchical entity graph with actions, events and a clock.

Everything that changes a world goes through a method here, and every change
is logged as an event. Scripts (actions, listeners, behaviors) get a `Ctx`
whose methods are the same op table, so a script is an agent without an LLM.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Iterable

from .script import Script, ScriptError, ScriptObject
from .store import Store

ROOT_TYPE = "world"
BASE_TYPE = "entity"


class Rejected(Exception):
    """An op could not be done. Says why, what is true instead, and what would work."""

    def __init__(self, reason: str, hint: str | None = None, alternatives: list[str] | None = None):
        self.reason = reason
        self.hint = hint
        self.alternatives = alternatives or []
        super().__init__(reason)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": False, "reason": self.reason, "hint": self.hint, "alternatives": self.alternatives}


class _Stop(Exception):
    pass


# --------------------------------------------------------------------------
# Views handed to scripts
# --------------------------------------------------------------------------


class StateView(ScriptObject):
    """entity.state as an object. Reads return None for missing keys. Writes patch."""

    def __init__(self, world: "World", entity_id: str):
        self._w = world
        self._id = entity_id

    def _script_get(self, name: str) -> Any:
        if name.startswith("_"):
            raise ScriptError(f"state key {name!r} is private")
        if name == "get":
            return self.get
        if name == "keys":
            return self.keys
        ent = self._w.get(self._id)
        return ent["state"].get(name)

    def _script_set(self, name: str, value: Any) -> None:
        self._w.patch(self._id, {name: value})

    def get(self, key: str, default: Any = None) -> Any:
        return self._w.get(self._id)["state"].get(key, default)

    def keys(self) -> list[str]:
        return list(self._w.get(self._id)["state"].keys())


class EntityView(ScriptObject):
    _script_attrs = ("id", "type", "name", "parent", "pos", "state", "children", "peers", "is_a", "has", "linked")

    def __init__(self, world: "World", entity_id: str):
        self._w = world
        self._id = entity_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> str:
        return self._w.get(self._id)["type"]

    @property
    def name(self) -> str:
        return self._w.get(self._id)["name"]

    @property
    def parent(self) -> "EntityView | None":
        p = self._w.get(self._id)["parent_id"]
        return EntityView(self._w, p) if p else None

    @property
    def pos(self) -> Any:
        return self._w.get(self._id)["pos"]

    @property
    def state(self) -> StateView:
        return StateView(self._w, self._id)

    def children(self, type: str | None = None) -> list["EntityView"]:
        return [EntityView(self._w, e["id"]) for e in self._w.children(self._id, type=type)]

    def peers(self, type: str | None = None) -> list["EntityView"]:
        return [EntityView(self._w, e["id"]) for e in self._w.peers(self._id, type=type)]

    def is_a(self, type: str) -> bool:
        return self._w.is_a(self.type, type)

    def has(self, relation: str, other: "EntityView | str") -> bool:
        oid = other.id if isinstance(other, EntityView) else other
        return oid in self._w.neighbors(self._id, relation)

    def linked(self, relation: str) -> list["EntityView"]:
        return [EntityView(self._w, i) for i in self._w.neighbors(self._id, relation)]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EntityView) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"<{self.type} {self._id} {self.name!r}>"


class RandView(ScriptObject):
    _script_attrs = ("random", "randint", "choice", "shuffle", "roll", "chance")

    def __init__(self, seed: int):
        self._r = random.Random(seed)

    def random(self) -> float:
        return self._r.random()

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def choice(self, xs: list[Any]) -> Any:
        if not xs:
            raise ScriptError("choice() of an empty list")
        return self._r.choice(list(xs))

    def shuffle(self, xs: list[Any]) -> list[Any]:
        ys = list(xs)
        self._r.shuffle(ys)
        return ys

    def roll(self, dice: str) -> int:
        """roll('2d6+1')"""
        s = dice.replace(" ", "").lower()
        mod = 0
        if "+" in s:
            s, m = s.split("+", 1)
            mod = int(m)
        elif "-" in s[1:]:
            i = s.rfind("-")
            s, mod = s[:i], -int(s[i + 1:])
        n, _, sides = s.partition("d")
        n = int(n) if n else 1
        return sum(self._r.randint(1, int(sides)) for _ in range(n)) + mod

    def chance(self, p: float) -> bool:
        return self._r.random() < p


def _deep_merge(base: dict[str, Any], top: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in top.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _ev(world: "World", x: Any) -> Any:
    """Normalize an entity reference from a script to an id string."""
    if isinstance(x, EntityView):
        return x.id
    return x


class Ctx(ScriptObject):
    """What a script sees. Its methods are the op table."""

    _script_attrs = (
        "actor", "target", "self", "params", "event", "t", "rand", "verb",
        "get", "find", "children", "parent", "peers", "linked", "edges", "relations", "distance", "root",
        "patch", "spawn", "move", "set_pos", "destroy", "link", "unlink", "relate", "unrelate",
        "emit", "say", "schedule", "reject", "stop", "log", "set_rule", "clear_rule",
    )

    def __init__(self, world: "World", *, actor: str | None, target: str | None, owner: str | None,
                 params: dict[str, Any] | None, event: dict[str, Any] | None, verb: str | None,
                 caused_by: int | None, seed: int):
        self._w = world
        self._actor = actor
        self._target = target
        self._owner = owner
        self.params = dict(params or {})
        self.event = event
        self.verb = verb
        self._caused_by = caused_by
        self.rand = RandView(seed)
        self.logs: list[str] = []
        self.stopped = False

    # -- identity
    @property
    def actor(self) -> EntityView | None:
        return EntityView(self._w, self._actor) if self._actor else None

    @property
    def target(self) -> EntityView | None:
        return EntityView(self._w, self._target) if self._target else None

    @property
    def self(self) -> EntityView | None:
        return EntityView(self._w, self._owner) if self._owner else None

    @property
    def t(self) -> float:
        return self._w.t

    def root(self) -> EntityView:
        return EntityView(self._w, self._w.root_id)

    # -- queries
    def get(self, id: Any) -> EntityView | None:
        id = _ev(self._w, id)
        return EntityView(self._w, id) if self._w.get(id) else None

    def find(self, type: str | None = None, under: Any = None, parent: Any = None, name: str | None = None,
             state: dict[str, Any] | None = None, limit: int = 50) -> list[EntityView]:
        rows = self._w.find(type=type, under=_ev(self._w, under), parent=_ev(self._w, parent), name=name,
                            state=state, limit=limit)
        return [EntityView(self._w, r["id"]) for r in rows]

    def children(self, id: Any, type: str | None = None) -> list[EntityView]:
        return [EntityView(self._w, e["id"]) for e in self._w.children(_ev(self._w, id), type=type)]

    def parent(self, id: Any) -> EntityView | None:
        e = self._w.get(_ev(self._w, id))
        return EntityView(self._w, e["parent_id"]) if e and e["parent_id"] else None

    def peers(self, id: Any, type: str | None = None) -> list[EntityView]:
        return [EntityView(self._w, e["id"]) for e in self._w.peers(_ev(self._w, id), type=type)]

    def linked(self, id: Any, relation: str, direction: str = "out") -> list[EntityView]:
        return [EntityView(self._w, i) for i in self._w.neighbors(_ev(self._w, id), relation, direction)]

    def edges(self, id: Any, relation: str | None = None, direction: str = "both") -> list[dict[str, Any]]:
        return self._w.edges(_ev(self._w, id), relation, direction)

    def relations(self, id: Any, relation: str | None = None) -> list[dict[str, Any]]:
        return self._w.hyperedges(_ev(self._w, id), relation)

    def distance(self, a: Any, b: Any) -> float | None:
        return self._w.distance(_ev(self._w, a), _ev(self._w, b))

    # -- mutations
    def patch(self, id: Any, changes: dict[str, Any] | None = None, **kw: Any) -> None:
        ch = dict(changes or {})
        ch.update(kw)
        self._w.patch(_ev(self._w, id), ch, actor=self._actor, caused_by=self._caused_by)

    def spawn(self, type: str, parent: Any, name: str = "", state: dict[str, Any] | None = None,
              pos: Any = None) -> EntityView:
        eid = self._w.spawn(type, _ev(self._w, parent), name=name, state=state, pos=pos,
                            actor=self._actor, caused_by=self._caused_by)
        return EntityView(self._w, eid)

    def move(self, id: Any, parent: Any, pos: Any = None) -> None:
        self._w.move(_ev(self._w, id), _ev(self._w, parent), pos=pos, actor=self._actor, caused_by=self._caused_by)

    def set_pos(self, id: Any, pos: Any) -> None:
        self._w.set_pos(_ev(self._w, id), pos, actor=self._actor, caused_by=self._caused_by)

    def destroy(self, id: Any) -> None:
        self._w.destroy(_ev(self._w, id), actor=self._actor, caused_by=self._caused_by)

    def link(self, source: Any, target: Any, relation: str, data: dict[str, Any] | None = None, **kw: Any) -> str:
        d = dict(data or {})
        d.update(kw)
        return self._w.link(_ev(self._w, source), _ev(self._w, target), relation, d,
                            actor=self._actor, caused_by=self._caused_by)

    def unlink(self, source: Any, target: Any, relation: str) -> int:
        return self._w.unlink(_ev(self._w, source), _ev(self._w, target), relation,
                              actor=self._actor, caused_by=self._caused_by)

    def relate(self, relation: str, participants: list[Any], data: dict[str, Any] | None = None, **kw: Any) -> str:
        d = dict(data or {})
        d.update(kw)
        return self._w.relate(relation, [_ev(self._w, p) for p in participants], d,
                              actor=self._actor, caused_by=self._caused_by)

    def unrelate(self, id: str) -> None:
        self._w.unrelate(id, actor=self._actor, caused_by=self._caused_by)

    def emit(self, kind: str, target: Any = None, reach: int = 1, payload: dict[str, Any] | None = None,
             **kw: Any) -> int:
        p = dict(payload or {})
        p.update(kw)
        tgt = _ev(self._w, target) if target is not None else (self._owner or self._actor)
        return self._w.emit(kind, actor=self._actor, target=tgt, reach=reach, payload=p,
                            caused_by=self._caused_by)["seq"]

    def say(self, text: str, reach: int = 1, to: Any = None) -> int:
        who = self._owner or self._actor
        return self._w.say(who, text, reach=reach, to=_ev(self._w, to) if to is not None else None,
                           caused_by=self._caused_by)["seq"]

    def schedule(self, after: float, kind: str, target: Any = None, payload: dict[str, Any] | None = None,
                 every: float | None = None, **kw: Any) -> str:
        p = dict(payload or {})
        p.update(kw)
        tgt = _ev(self._w, target) if target is not None else (self._owner or self._actor)
        return self._w.schedule(after, kind, entity=tgt, payload=p, every=every, caused_by=self._caused_by)

    def set_rule(self, entity: Any, script: str, kinds: list[str] | None = None) -> None:
        self._w.set_rule(_ev(self._w, entity), script, kinds, actor=self._actor, caused_by=self._caused_by)

    def clear_rule(self, entity: Any, script: str) -> None:
        self._w.clear_rule(_ev(self._w, entity), script, actor=self._actor, caused_by=self._caused_by)

    # -- control
    def reject(self, reason: str, hint: str | None = None) -> None:
        raise Rejected(str(reason), hint)

    def stop(self) -> None:
        """Stop this event from bubbling further (a local rule overriding the world's)."""
        self.stopped = True
        raise _Stop()

    def log(self, msg: Any) -> None:
        self.logs.append(str(msg))


# --------------------------------------------------------------------------
# The world
# --------------------------------------------------------------------------


class World:
    def __init__(self, store: Store, world_id: str):
        self.store = store
        self.id = world_id
        row = store.get("world", None, world_id)
        if row is None:
            raise Rejected(f"no world {world_id!r}", hint="use World.create or list worlds with store.list_worlds()")
        self._row = row
        self._script_cache: dict[tuple[str, int], Script] = {}
        self._schema_cache: dict[str, dict[str, Any]] = {}

    # ---- lifecycle ---------------------------------------------------------

    @classmethod
    def create(cls, store: Store, name: str, seed: int = 0, id: str | None = None,
               description: str = "") -> "World":
        wid = id or name.lower().replace(" ", "-")
        if store.get("world", None, wid):
            raise Rejected(f"world {wid!r} already exists", hint="pick another id or open it")
        store.begin()
        try:
            store.put("world", {"id": wid, "name": name, "seed": seed, "t": 0.0, "clock_rate": 1.0,
                                "clock_running": 0, "root_id": None, "counters": {},
                                "meta": {"description": description}})
            w = cls(store, wid)
            w._install_base_schemas()
            root = w.spawn(ROOT_TYPE, None, name=name, state={"description": description})
            w._row["root_id"] = root
            w._save_row()
            store.commit()
        except Exception:
            store.rollback()
            raise
        return w

    @classmethod
    def open(cls, store: Store, world_id: str) -> "World":
        return cls(store, world_id)

    def _save_row(self) -> None:
        self.store.put("world", self._row)

    @property
    def root_id(self) -> str:
        return self._row["root_id"]

    @property
    def name(self) -> str:
        return self._row["name"]

    @property
    def seed(self) -> int:
        return int(self._row["seed"])

    @property
    def t(self) -> float:
        return float(self._row["t"])

    def _next_id(self, prefix: str) -> str:
        c = self._row["counters"]
        n = c.get(prefix, 0) + 1
        c[prefix] = n
        self._save_row()
        return f"{prefix}{n}"

    def _install_base_schemas(self) -> None:
        self.define_schema(BASE_TYPE, doc="Everything is an entity.", state={"description": "", "hidden": False})
        self.define_schema(ROOT_TYPE, extends=BASE_TYPE, doc="The world root. Rules set here apply everywhere.")
        self.define_schema("place", extends=BASE_TYPE, doc="Something that contains other things. Locations.",
                           state={"description": ""})
        self.define_schema("thing", extends=BASE_TYPE, doc="A physical object.")
        self.define_schema("creature", extends=BASE_TYPE, doc="Something that can act. Characters, monsters.",
                           state={"hp": 10, "max_hp": 10})

    # ---- schemas and scripts -----------------------------------------------

    def define_schema(self, id: str, extends: str | None = None, doc: str = "", state: dict[str, Any] | None = None,
                      space: dict[str, Any] | None = None, actions: dict[str, Any] | None = None,
                      listeners: list[dict[str, Any]] | None = None, behaviors: list[dict[str, Any]] | None = None,
                      senses: list[str] | None = None) -> dict[str, Any]:
        if id != BASE_TYPE and extends is None:
            extends = BASE_TYPE
        if extends and extends != id and self.store.get("schema", self.id, extends) is None:
            raise Rejected(f"schema {id!r} extends unknown schema {extends!r}",
                           hint="define the parent schema first, or extend 'entity', 'place', 'thing' or 'creature'")
        for verb, a in (actions or {}).items():
            if not isinstance(a, dict) or "script" not in a:
                raise Rejected(f"action {verb!r} needs a dict with a 'script' key",
                               hint='actions={"open": {"script": "door_open", "doc": "Open the door", "reach": "near"}}')
        for lst in (listeners or []) + (behaviors or []):
            if not isinstance(lst, dict) or "script" not in lst:
                raise Rejected("listeners and behaviors are dicts with a 'script' key",
                               hint='listeners=[{"script": "guard_rules", "kinds": ["before_act"]}], '
                                    'behaviors=[{"script": "wander", "every": 10}]')
        old = self.store.get("schema", self.id, id)
        row = {
            "world_id": self.id, "id": id, "extends": extends if id != BASE_TYPE else None, "doc": doc,
            "state": state or {}, "space": space, "actions": actions or {}, "listeners": listeners or [],
            "behaviors": behaviors or [], "senses": senses or [], "version": (old["version"] + 1) if old else 1,
        }
        self.store.put("schema", row)
        self._schema_cache.clear()
        self.emit("schema_defined", target=None, reach=0, payload={"schema": id, "version": row["version"]})
        return row

    def define_script(self, id: str, source: str, doc: str = "") -> dict[str, Any]:
        Script(source, name=id)  # validate now, fail loudly
        old = self.store.get("script", self.id, id)
        row = {"world_id": self.id, "id": id, "source": source, "doc": doc,
               "version": (old["version"] + 1) if old else 1}
        self.store.put("script", row)
        self.emit("script_defined", target=None, reach=0, payload={"script": id, "version": row["version"]})
        return row

    def script(self, id: str) -> Script:
        row = self.store.get("script", self.id, id)
        if row is None:
            raise Rejected(f"no script {id!r}", hint="define it with define_script")
        key = (id, row["version"])
        s = self._script_cache.get(key)
        if s is None:
            s = Script(row["source"], name=id)
            self._script_cache[key] = s
        return s

    def schema(self, id: str) -> dict[str, Any]:
        s = self._schema_cache.get(id)
        if s is None:
            s = self.store.get("schema", self.id, id)
            if s is None:
                raise Rejected(f"no schema {id!r}", hint="define it with define_schema, or use an existing type")
            self._schema_cache[id] = s
        return s

    def schemas(self) -> list[dict[str, Any]]:
        return self.store.query("schema", "world_id=?", (self.id,), order="id")

    def scripts(self) -> list[dict[str, Any]]:
        return self.store.query("script", "world_id=?", (self.id,), order="id")

    def schema_chain(self, type: str) -> list[dict[str, Any]]:
        """Most specific first, ending at 'entity'."""
        chain = []
        seen = set()
        cur: str | None = type
        while cur and cur not in seen:
            seen.add(cur)
            s = self.schema(cur)
            chain.append(s)
            cur = s["extends"]
        return chain

    def is_a(self, type: str, ancestor: str) -> bool:
        return any(s["id"] == ancestor for s in self.schema_chain(type))

    def schema_actions(self, type: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for s in reversed(self.schema_chain(type)):
            out.update(s["actions"])
        return out

    def schema_defaults(self, type: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for s in reversed(self.schema_chain(type)):
            out.update(s["state"])
        return out

    def schema_space(self, type: str) -> dict[str, Any] | None:
        for s in self.schema_chain(type):
            if s["space"]:
                return s["space"]
        return None

    def schema_components(self, type: str, kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in reversed(self.schema_chain(type)):
            out.extend(s[kind])
        return out

    # ---- graph queries -------------------------------------------------------

    def get(self, id: str | None) -> dict[str, Any] | None:
        if not id:
            return None
        return self.store.get("entity", self.id, id)

    def need(self, id: str | None) -> dict[str, Any]:
        e = self.get(id)
        if e is None:
            raise Rejected(f"no entity {id!r}", hint="ids come from perceive, find or spawn; names are not ids")
        return e

    def children(self, id: str, type: str | None = None) -> list[dict[str, Any]]:
        rows = self.store.query("entity", "world_id=? AND parent_id=?", (self.id, id), order="created_seq")
        if type:
            rows = [r for r in rows if self.is_a(r["type"], type)]
        return rows

    def peers(self, id: str, type: str | None = None) -> list[dict[str, Any]]:
        e = self.need(id)
        if not e["parent_id"]:
            return []
        return [c for c in self.children(e["parent_id"], type) if c["id"] != id]

    def ancestors(self, id: str) -> list[str]:
        """Parent, grandparent, ... root."""
        out = []
        cur = self.get(id)
        while cur and cur["parent_id"]:
            out.append(cur["parent_id"])
            cur = self.get(cur["parent_id"])
        return out

    def subtree_ids(self, id: str) -> list[str]:
        out = [id]
        stack = [id]
        while stack:
            for c in self.children(stack.pop()):
                out.append(c["id"])
                stack.append(c["id"])
        return out

    def find(self, type: str | None = None, under: str | None = None, parent: str | None = None,
             name: str | None = None, state: dict[str, Any] | None = None, limit: int = 50) -> list[dict[str, Any]]:
        where = ["world_id=?"]
        params: list[Any] = [self.id]
        if parent:
            where.append("parent_id=?")
            params.append(parent)
        if name:
            where.append("lower(name) LIKE ?")
            params.append(f"%{name.lower()}%")
        rows = self.store.query("entity", " AND ".join(where), params, order="created_seq")
        if type:
            rows = [r for r in rows if self.is_a(r["type"], type)]
        if under:
            ids = set(self.subtree_ids(under))
            rows = [r for r in rows if r["id"] in ids and r["id"] != under]
        if state:
            rows = [r for r in rows if all(r["state"].get(k) == v for k, v in state.items())]
        return rows[:limit]

    def edges(self, id: str, relation: str | None = None, direction: str = "both") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if direction in ("out", "both"):
            clauses.append("source=?")
            params.append(id)
        if direction in ("in", "both"):
            clauses.append("target=?")
            params.append(id)
        where = f"world_id=? AND ({' OR '.join(clauses)})"
        params = [self.id] + params
        if relation:
            where += " AND relation=?"
            params.append(relation)
        return self.store.query("edge", where, params, order="id")

    def neighbors(self, id: str, relation: str, direction: str = "out") -> list[str]:
        out = []
        for e in self.edges(id, relation, direction):
            other = e["target"] if e["source"] == id else e["source"]
            if other not in out:
                out.append(other)
        return out

    def hyperedges(self, id: str | None = None, relation: str | None = None) -> list[dict[str, Any]]:
        rows = self.store.query("hyperedge", "world_id=?" + (" AND relation=?" if relation else ""),
                                [self.id] + ([relation] if relation else []), order="id")
        if id:
            rows = [r for r in rows if id in r["participants"]]
        return rows

    def space_of(self, container_id: str | None) -> dict[str, Any] | None:
        if not container_id:
            return None
        e = self.get(container_id)
        if e is None:
            return None
        sp = e["state"].get("space")
        if sp:
            return sp
        return self.schema_space(e["type"])

    def _place_in_space(self, container_id: str | None, pos: Any) -> list[float] | None:
        """Validate a position against the container's space: right number of dims, inside bounds, on the grid."""
        sp = self.space_of(container_id)
        if pos is None:
            if sp and sp.get("dims") and sp.get("origin") is not None:
                return [float(x) for x in sp["origin"]]
            return None
        if not sp or not sp.get("dims"):
            raise Rejected(f"{container_id} has no space; nothing in it has a position",
                           hint='give the container state.space = {"dims": 2, "bounds": [10, 10], "grid": true}')
        pos = [float(x) for x in pos]
        dims = int(sp["dims"])
        if len(pos) != dims:
            raise Rejected(f"{container_id} has {dims} dimensions; got a position with {len(pos)}")
        if sp.get("grid"):
            if any(x != int(x) for x in pos):
                raise Rejected(f"{container_id} is a grid; positions are whole numbers")
        bounds = sp.get("bounds")
        if bounds:
            for i, (x, b) in enumerate(zip(pos, bounds)):
                if x < 0 or x >= float(b):
                    raise Rejected(f"position {pos} is outside {container_id} (axis {i} runs 0 to {b})",
                                   hint="stay inside the bounds, or go to a connected place")
        return pos

    def set_pos(self, id: str, pos: Any, actor: str | None = None, caused_by: int | None = None) -> None:
        """Move within the current container."""
        e = self.need(id)
        new = self._place_in_space(e["parent_id"], pos)
        old = e["pos"]
        e["pos"] = new
        self._touch(e)
        self.emit("moved", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"from": e["parent_id"], "to": e["parent_id"], "from_pos": old, "to_pos": new})

    def distance(self, a: str, b: str) -> float | None:
        """Distance between two siblings in their parent's space. None if not comparable."""
        ea, eb = self.need(a), self.need(b)
        if ea["parent_id"] != eb["parent_id"]:
            return None
        sp = self.space_of(ea["parent_id"])
        if not sp or not sp.get("dims"):
            return 0.0
        pa, pb = ea["pos"], eb["pos"]
        if pa is None or pb is None:
            return None
        return sum((float(x) - float(y)) ** 2 for x, y in zip(pa, pb)) ** 0.5

    # ---- graph mutations (each one logs a primitive event) -----------------------

    def spawn(self, type: str, parent: str | None, name: str = "", state: dict[str, Any] | None = None,
              pos: Any = None, actor: str | None = None, caused_by: int | None = None, id: str | None = None) -> str:
        self.schema(type)
        if parent is not None:
            self.need(parent)
        elif type != ROOT_TYPE or self._row.get("root_id"):
            raise Rejected("only the world root has no parent", hint="pass the parent entity id")
        st = self.schema_defaults(type)
        st.update(state or {})
        pos = self._place_in_space(parent, pos)
        eid = id or self._next_id("e")
        seq = self.store.next_seq(self.id)
        self.store.put("entity", {"world_id": self.id, "id": eid, "type": type, "parent_id": parent, "name": name,
                                  "state": st, "pos": pos, "version": 1, "created_seq": seq, "updated_seq": seq})
        self.emit("spawned", actor=actor, target=eid, reach=1, caused_by=caused_by,
                  payload={"type": type, "name": name, "parent": parent})
        for b in self.schema_components(type, "behaviors"):
            every = float(b.get("every", 10))
            self.schedule(every, "tick", entity=eid, payload={"script": b["script"]}, every=every,
                          caused_by=caused_by, log=False)
        return eid

    def patch(self, id: str, changes: dict[str, Any], actor: str | None = None, caused_by: int | None = None,
              replace: bool = False) -> None:
        """Change state keys. A dict value merges into an existing dict (one new dialog topic does not
        resend the others); replace=True sets the key whole. A value of None deletes the key."""
        e = self.need(id)
        if not changes:
            return
        for k in changes:
            if str(k).startswith("_"):
                raise Rejected(f"state key {k!r} is private")
        before = {k: e["state"].get(k) for k in changes}
        for k, v in changes.items():
            if v is None:
                e["state"].pop(k, None)
            elif not replace and isinstance(v, dict) and isinstance(e["state"].get(k), dict):
                e["state"][k] = _deep_merge(e["state"][k], v)
            else:
                e["state"][k] = v
        self._touch(e)
        self.emit("patched", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"changes": changes, "before": before, "replace": replace})

    def _touch(self, e: dict[str, Any]) -> None:
        e["version"] += 1
        e["updated_seq"] = self.store.next_seq(self.id)
        self.store.put("entity", e)

    def move(self, id: str, parent: str, pos: Any = None, actor: str | None = None,
             caused_by: int | None = None) -> None:
        e = self.need(id)
        self.need(parent)
        if parent == id or parent in self.subtree_ids(id):
            raise Rejected("cannot move an entity into itself")
        old = e["parent_id"]
        e["parent_id"] = parent
        e["pos"] = self._place_in_space(parent, pos)
        self._touch(e)
        # Two events: the old room sees a departure, the new one an arrival.
        self.emit("left", actor=actor, target=old, reach=0, caused_by=caused_by,
                  payload={"entity": id, "to": parent})
        self.emit("moved", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"from": old, "to": parent})

    def destroy(self, id: str, actor: str | None = None, caused_by: int | None = None) -> None:
        e = self.need(id)
        if id == self.root_id:
            raise Rejected("cannot destroy the world root")
        # Logged first, while the entity still has a place in the tree, so the event's path reaches its container.
        self.emit("destroyed", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"entity": id, "type": e["type"], "name": e["name"], "parent": e["parent_id"]})
        for cid in reversed(self.subtree_ids(id)):
            self.store.execute("DELETE FROM edge WHERE world_id=? AND (source=? OR target=?)", (self.id, cid, cid))
            self.store.execute("DELETE FROM scheduled WHERE world_id=? AND entity_id=?", (self.id, cid))
            self.store.delete("entity", self.id, cid)

    def link(self, source: str, target: str, relation: str, data: dict[str, Any] | None = None,
             actor: str | None = None, caused_by: int | None = None) -> str:
        self.need(source)
        self.need(target)
        for ex in self.edges(source, relation, "out"):
            if ex["target"] == target:
                ex["data"] = {**ex["data"], **(data or {})}
                self.store.put("edge", ex)
                return ex["id"]
        gid = self._next_id("g")
        self.store.put("edge", {"world_id": self.id, "id": gid, "source": source, "target": target,
                                "relation": relation, "data": data or {}})
        self.emit("linked", actor=actor, target=source, reach=1, caused_by=caused_by,
                  payload={"edge": gid, "target": target, "relation": relation})
        return gid

    def unlink(self, source: str, target: str, relation: str, actor: str | None = None,
               caused_by: int | None = None) -> int:
        n = 0
        for ex in self.edges(source, relation, "out"):
            if ex["target"] == target:
                self.store.delete("edge", self.id, ex["id"])
                n += 1
        if n:
            self.emit("unlinked", actor=actor, target=source, reach=1, caused_by=caused_by,
                      payload={"target": target, "relation": relation})
        return n

    def relate(self, relation: str, participants: list[str], data: dict[str, Any] | None = None,
               actor: str | None = None, caused_by: int | None = None) -> str:
        for p in participants:
            self.need(p)
        hid = self._next_id("h")
        self.store.put("hyperedge", {"world_id": self.id, "id": hid, "relation": relation,
                                     "participants": list(participants), "data": data or {}})
        self.emit("related", actor=actor, target=participants[0] if participants else None, reach=0,
                  caused_by=caused_by, payload={"hyperedge": hid, "relation": relation,
                                                 "participants": list(participants)})
        return hid

    def update_relation(self, id: str, data: dict[str, Any]) -> None:
        h = self.store.get("hyperedge", self.id, id)
        if h is None:
            raise Rejected(f"no relation {id!r}")
        h["data"] = {**h["data"], **data}
        self.store.put("hyperedge", h)

    def unrelate(self, id: str, actor: str | None = None, caused_by: int | None = None) -> None:
        h = self.store.get("hyperedge", self.id, id)
        if h is None:
            raise Rejected(f"no relation {id!r}")
        self.store.delete("hyperedge", self.id, id)
        self.emit("unrelated", actor=actor, target=None, reach=0, caused_by=caused_by,
                  payload={"hyperedge": id, "relation": h["relation"]})

    def set_rule(self, entity: str, script: str, kinds: list[str] | None = None, actor: str | None = None,
                 caused_by: int | None = None) -> None:
        self.script(script)
        e = self.need(entity)
        rules = [r for r in e["state"].get("rules", []) if r["script"] != script]
        rules.append({"script": script, "kinds": kinds or ["before_act"]})
        self.patch(entity, {"rules": rules}, actor=actor, caused_by=caused_by)

    def clear_rule(self, entity: str, script: str, actor: str | None = None, caused_by: int | None = None) -> None:
        e = self.need(entity)
        rules = [r for r in e["state"].get("rules", []) if r["script"] != script]
        self.patch(entity, {"rules": rules}, actor=actor, caused_by=caused_by)

    # ---- events ------------------------------------------------------------------

    def emit(self, kind: str, actor: str | None = None, target: str | None = None, reach: int = 1,
             payload: dict[str, Any] | None = None, caused_by: int | None = None) -> dict[str, Any]:
        """Record an event and let listeners along its bubble path react.

        reach: how many levels above the target the event travels. 0 = the
        target only, 1 = its container (the room hears it), -1 = all the way
        to the world root.
        """
        path: list[str] = []
        if target:
            path.append(target)
            anc = self.ancestors(target)
            path.extend(anc if reach < 0 else anc[:reach])
        seq = self.store.next_seq(self.id)
        ev = {"world_id": self.id, "seq": seq, "t": self.t, "kind": kind, "actor_id": actor, "target_id": target,
              "reach": reach, "payload": payload or {}, "caused_by": caused_by, "path": path}
        self.store.put("event", ev)
        if kind not in _SILENT_KINDS:
            self._dispatch(ev)
            if kind in self._OPINION and self._row["meta"].get("opinion_floor", True):
                self._opinion_floor(ev)
        return ev

    def _listeners_for(self, entity_id: str) -> list[dict[str, Any]]:
        e = self.get(entity_id)
        if e is None:
            return []
        out = list(self.schema_components(e["type"], "listeners"))
        out.extend(e["state"].get("rules", []))
        return out

    def _dispatch(self, ev: dict[str, Any], actor: str | None = None, target: str | None = None,
                  verb: str | None = None, params: dict[str, Any] | None = None) -> list[str]:
        """Run listeners along the path, target first. A listener may reject or stop."""
        logs: list[str] = []
        for node in ev["path"]:
            for lst in self._listeners_for(node):
                kinds = lst.get("kinds") or []
                if kinds and ev["kind"] not in kinds:
                    continue
                if lst.get("unless_embodied") and self.embodied(node):
                    continue  # the table is the floor; an embodied mind answers instead
                s = self.script(lst["script"])
                fn = lst.get("fn", "on")
                if not s.has(fn):
                    continue
                ctx = Ctx(self, actor=actor or ev["actor_id"], target=target or ev["target_id"], owner=node,
                          params=params, event=_event_view(ev), verb=verb, caused_by=ev["seq"],
                          seed=self._seed_for(ev["seq"], node))
                try:
                    s.call(fn, [ctx, _event_view(ev)], fuel=20_000)
                except _Stop:
                    logs.extend(ctx.logs)
                    return logs
                except ScriptError as e:
                    raise Rejected(f"listener {lst['script']!r} on {node} failed: {e.reason}",
                                   hint=e.hint or "fix the listener script") from None
                logs.extend(ctx.logs)
        return logs

    def _seed_for(self, seq: int, salt: str) -> int:
        h = hashlib.sha256(f"{self.seed}:{seq}:{salt}".encode()).digest()
        return int.from_bytes(h[:8], "big")

    def events(self, since: int = 0, until: int | None = None, kinds: list[str] | None = None,
               touching: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Events after `since`. `touching`: only events whose path includes this id or its parent."""
        where = "world_id=? AND seq>?"
        params: list[Any] = [self.id, since]
        if until is not None:
            where += " AND seq<=?"
            params.append(until)
        rows = self.store.query("event", where, params, order="seq", limit=None if touching else limit)
        if kinds:
            rows = [r for r in rows if r["kind"] in kinds]
        if touching:
            e = self.get(touching)
            watch = {touching}
            if e and e["parent_id"]:
                watch.add(e["parent_id"])
            rows = [r for r in rows if watch & set(r["path"]) or r["actor_id"] == touching]
            rows = rows[:limit]
        return rows

    # ---- actions -----------------------------------------------------------------

    def resolve_action(self, actor_id: str, verb: str, target_id: str | None) -> tuple[dict[str, Any], str]:
        """Find the action definition for verb. Returns (definition, owner_id)."""
        actor = self.need(actor_id)
        if target_id:
            target = self.need(target_id)
            acts = self.schema_actions(target["type"])
            if verb in acts and acts[verb].get("targets") is None:
                return acts[verb], target_id
        acts = self.schema_actions(actor["type"])
        if verb in acts:
            tt = acts[verb].get("targets")
            if tt is not None and target_id is None:
                raise Rejected(f"{verb} needs a target", hint=f"{verb} works on a {tt}; pick one perceive lists")
            if tt not in (None, "any") and target_id and not self.is_a(self.need(target_id)["type"], tt):
                raise Rejected(f"you can only {verb} a {tt}, and {target_id} is a {self.need(target_id)['type']}")
            return acts[verb], actor_id
        known = sorted(set(self.schema_actions(actor["type"])) |
                       (set(self.schema_actions(self.need(target_id)["type"])) if target_id else set()))
        raise Rejected(f"no action {verb!r} on {target_id or actor_id}",
                       hint=f"verbs here: {', '.join(known) or 'none'}. Use perceive to see affordances.",
                       alternatives=known)

    def reachable(self, actor_id: str, target_id: str) -> tuple[bool, str]:
        """Can actor act on target? self, container, siblings, inventory, or a connected place."""
        if actor_id == target_id:
            return True, ""
        actor = self.need(actor_id)
        target = self.need(target_id)
        if target_id == actor["parent_id"]:
            return True, ""
        if target["parent_id"] == actor_id:
            return True, ""
        if target["parent_id"] == actor["parent_id"] and actor["parent_id"] is not None:
            if target["state"].get("hidden"):
                return False, f"{target_id} is hidden"
            return True, ""
        if actor["parent_id"]:
            for e in self.edges(actor["parent_id"], "connects_to", "out"):
                # The next place is reachable, and so is whatever the passage goes through (a door).
                if target_id == e["target"] or target_id == e["data"].get("via"):
                    return True, ""
        if target["parent_id"] == actor["parent_id"] is None:
            return True, ""
        return False, f"{target_id} ({target['name'] or target['type']}) is not within reach of {actor_id}"

    def check_action(self, actor_id: str, verb: str, target_id: str | None = None,
                     params: dict[str, Any] | None = None) -> tuple[bool, str | None]:
        """Preconditions only. Returns (ok, reason)."""
        try:
            self._prepare(actor_id, verb, target_id, params, dry=True)
            return True, None
        except Rejected as r:
            return False, r.reason

    def _prepare(self, actor_id: str, verb: str, target_id: str | None, params: dict[str, Any] | None,
                 dry: bool) -> tuple[dict[str, Any], str, Script]:
        adef, owner = self.resolve_action(actor_id, verb, target_id)
        reach = adef.get("reach", "near")
        if target_id and reach == "near":
            ok, why = self.reachable(actor_id, target_id)
            if not ok:
                raise Rejected(why, hint="move closer, or pick something perceive lists")
            rng = adef.get("range")
            if rng is not None:
                d = self.distance(actor_id, target_id)
                if d is not None and d > float(rng):
                    raise Rejected(f"{target_id} is {d:.1f} away; {verb} reaches {rng}",
                                   hint="move closer first")
        elif target_id and reach == "self" and target_id != actor_id:
            raise Rejected(f"{verb} can only target yourself")
        s = self.script(adef["script"])
        if not s.has("apply"):
            raise Rejected(f"script {adef['script']!r} has no apply(ctx)", hint="actions need def apply(ctx)")
        # Rules: before_act bubbles all the way up so world rules see it; a local rule may stop() or reject it.
        payload = {"verb": verb, "params": dict(params or {}), "owner": owner}
        if dry:
            tgt = target_id or actor_id
            ev = {"world_id": self.id, "seq": self.store.next_seq(self.id), "t": self.t, "kind": "before_act",
                  "actor_id": actor_id, "target_id": tgt, "reach": -1, "payload": payload, "caused_by": None,
                  "path": [tgt] + self.ancestors(tgt)}
        else:
            ev = self.emit("before_act", actor=actor_id, target=target_id or actor_id, reach=-1, payload=payload)
        self._dispatch(ev, actor=actor_id, target=target_id, verb=verb, params=params)
        if s.has("check"):
            ctx = Ctx(self, actor=actor_id, target=target_id, owner=owner, params=params, event=None, verb=verb,
                      caused_by=None, seed=self._seed_for(self.store.next_seq(self.id), "check"))
            try:
                res = s.call("check", [ctx], fuel=5_000)
            except ScriptError as e:
                raise Rejected(f"check for {verb!r} failed: {e.reason}", hint=e.hint) from None
            if res is False:
                raise Rejected(f"{verb} is not possible right now")
            if isinstance(res, str) and res:
                raise Rejected(res)
        return adef, owner, s

    def act(self, actor_id: str, verb: str, target_id: str | None = None, params: dict[str, Any] | None = None,
            principal_id: str | None = None) -> dict[str, Any]:
        """The only way state changes on purpose. Returns {ok, events, logs} or raises Rejected."""
        params = dict(params or {})
        self.need(actor_id)
        self.store.begin()
        start_seq = self.store.next_seq(self.id) - 1
        try:
            adef, owner, s = self._prepare(actor_id, verb, target_id, params, dry=False)
            logs: list[str] = []
            ev = self.emit("act", actor=actor_id, target=target_id or actor_id, reach=1,
                           payload={"verb": verb, "params": params, "target": target_id})
            ctx = Ctx(self, actor=actor_id, target=target_id, owner=owner, params=params, event=_event_view(ev),
                      verb=verb, caused_by=ev["seq"], seed=self._seed_for(ev["seq"], "apply"))
            try:
                result = s.call("apply", [ctx], fuel=50_000)
            except ScriptError as e:
                raise Rejected(f"{verb} failed while applying: {e.reason}", hint=e.hint) from None
            logs.extend(ctx.logs)
            dur = float(adef.get("duration", 0) or 0)
            if dur > 0 and s.has("finish"):
                self.schedule(dur, "finish", entity=owner, caused_by=ev["seq"],
                              payload={"script": adef["script"], "actor": actor_id, "target": target_id,
                                       "verb": verb, "params": params})
            if principal_id:
                self._bump_cursor(principal_id)
            self.store.commit()
        except Rejected as r:
            self.store.rollback()
            if not r.alternatives:
                r.alternatives = [a["verb"] + (f" {a['target']}" if a.get("target") else "")
                                  for a in self.affordances(actor_id) if a["ok"]][:12]
            raise
        except Exception:
            self.store.rollback()
            raise
        evs = self.events(since=start_seq, limit=500)
        return {"ok": True, "verb": verb, "target": target_id, "result": result,
                "duration": float(adef.get("duration", 0) or 0),
                "events": [_public_event(e) for e in evs if e["kind"] not in _INTERNAL_KINDS], "logs": logs}

    def affordances(self, actor_id: str, target_id: str | None = None) -> list[dict[str, Any]]:
        """Every verb the actor could try on itself and on reachable entities, with preconditions evaluated."""
        actor = self.need(actor_id)
        candidates: list[str] = [actor_id]
        if target_id:
            candidates = [target_id]
        else:
            if actor["parent_id"]:
                candidates.append(actor["parent_id"])
                candidates.extend(c["id"] for c in self.children(actor["parent_id"]) if c["id"] != actor_id
                                  and not c["state"].get("hidden"))
                candidates.extend(self.neighbors(actor["parent_id"], "connects_to"))
            candidates.extend(c["id"] for c in self.children(actor_id))
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None]] = set()

        def add(verb: str, adef: dict[str, Any], tid: str | None) -> None:
            key = (verb, tid)
            if key in seen or adef.get("hidden"):
                return
            seen.add(key)
            ok, reason = self.check_action(actor_id, verb, tid)
            tgt = self.get(tid) if tid else None
            out.append({"verb": verb, "target": tid, "target_name": tgt["name"] if tgt else None, "ok": ok,
                        "reason": reason, "doc": adef.get("doc", ""), "params": adef.get("params", {})})

        # Verbs the actor carries. One with `targets` (a type) pairs with every reachable entity of that type;
        # one without is the actor's own (rest, shout, look).
        actor_verbs = self.schema_actions(actor["type"])
        here = actor["parent_id"]
        held = {c["id"] for c in self.children(actor_id)}
        exits = set(self.neighbors(here, "connects_to")) if here else set()
        for verb, adef in actor_verbs.items():
            tt = adef.get("targets")
            if tt is None:
                add(verb, adef, None)
                continue
            scope = adef.get("scope", "any")
            for cid in candidates:
                if cid == actor_id and adef.get("reach") != "self":
                    continue
                # scope keeps the impossible pairs out of the list: drop what you do not hold, go where you stand
                if scope == "held" and cid not in held:
                    continue
                if scope == "here" and (cid in held or cid == here or cid in exits):
                    continue
                if scope == "exits" and cid not in exits:
                    continue
                ent = self.get(cid)
                if ent and (tt == "any" or self.is_a(ent["type"], tt)):
                    add(verb, adef, cid)
        # Verbs the things around the actor carry: every object is also its ops.
        for cid in candidates:
            if cid == actor_id:
                continue
            ent = self.get(cid)
            if ent is None:
                continue
            for verb, adef in self.schema_actions(ent["type"]).items():
                if adef.get("targets") is None:  # an action with `targets` is the holder's own verb, not one done to it
                    add(verb, adef, cid)
        return out

    # ---- clock and scheduling -----------------------------------------------------

    def schedule(self, after: float, kind: str, entity: str | None = None, payload: dict[str, Any] | None = None,
                 every: float | None = None, caused_by: int | None = None, log: bool = True) -> str:
        sid = self._next_id("s")
        self.store.put("scheduled", {"world_id": self.id, "id": sid, "t": self.t + float(after), "kind": kind,
                                     "entity_id": entity, "payload": payload or {}, "every": every})
        if log:
            self.emit("scheduled", actor=None, target=entity, reach=0, caused_by=caused_by,
                      payload={"id": sid, "kind": kind, "at": self.t + float(after)})
        return sid

    def pending(self) -> list[dict[str, Any]]:
        return self.store.query("scheduled", "world_id=?", (self.id,), order="t, id")

    def embodied(self, entity_id: str) -> dict[str, Any] | None:
        rows = self.store.query("principal", "world_id=? AND entity_id=?", (self.id, entity_id), limit=1)
        return rows[0] if rows else None

    def step(self, dt: float) -> list[dict[str, Any]]:
        """Advance world time by dt, delivering everything due. Returns public events produced."""
        if dt < 0:
            raise Rejected("dt must be >= 0")
        start_seq = self.store.next_seq(self.id) - 1
        end_t = self.t + float(dt)
        while True:
            due = self.store.query("scheduled", "world_id=? AND t<=?", (self.id, end_t), order="t, id", limit=1)
            if not due:
                break
            item = due[0]
            self._row["t"] = max(self.t, float(item["t"]))
            self._save_row()
            self.store.delete("scheduled", self.id, item["id"])
            if item["every"]:
                # A periodic item that fell behind fires once and skips ahead; it never replays a long gap.
                nxt = float(item["t"]) + float(item["every"])
                if nxt <= end_t:
                    nxt = end_t + float(item["every"])
                item["t"] = nxt
                self.store.put("scheduled", item)
            self._deliver(item)
        self._row["t"] = end_t
        self._save_row()
        evs = self.events(since=start_seq, limit=1000)
        return [_public_event(e) for e in evs if e["kind"] not in _INTERNAL_KINDS]

    def _deliver(self, item: dict[str, Any]) -> None:
        kind, eid, p = item["kind"], item["entity_id"], item["payload"]
        if eid and self.get(eid) is None:
            return
        if kind == "tick":
            if eid is None or self.embodied(eid):
                return  # controller swap: an embodied entity is driven by its principal
            s = self.script(p["script"])
            if not s.has("tick"):
                return
            ev = self.emit("tick", actor=eid, target=eid, reach=0, payload={"script": p["script"]})
            ctx = Ctx(self, actor=eid, target=None, owner=eid, params=None, event=_event_view(ev), verb=None,
                      caused_by=ev["seq"], seed=self._seed_for(ev["seq"], "tick"))
            self.store.begin()
            try:
                s.call("tick", [ctx], fuel=50_000)
                self.store.commit()
            except (ScriptError, Rejected) as e:
                self.store.rollback()
                self.emit("script_error", actor=eid, target=eid, reach=0,
                          payload={"script": p["script"], "fn": "tick", "reason": getattr(e, "reason", str(e))})
            return
        if kind == "finish":
            s = self.script(p["script"])
            ev = self.emit("finished", actor=p.get("actor"), target=eid, reach=1,
                           payload={"verb": p.get("verb"), "target": p.get("target")})
            ctx = Ctx(self, actor=p.get("actor"), target=p.get("target"), owner=eid, params=p.get("params"),
                      event=_event_view(ev), verb=p.get("verb"), caused_by=ev["seq"],
                      seed=self._seed_for(ev["seq"], "finish"))
            self.store.begin()
            try:
                s.call("finish", [ctx], fuel=50_000)
                self.store.commit()
            except (ScriptError, Rejected) as e:
                self.store.rollback()
                self.emit("script_error", actor=eid, target=eid, reach=0,
                          payload={"script": p["script"], "fn": "finish", "reason": getattr(e, "reason", str(e))})
            return
        # Any other scheduled kind is just an event that fires later (listeners may react).
        self.emit(kind, actor=p.get("actor"), target=eid, reach=int(p.get("reach", 1)), payload=p)

    def set_clock(self, running: bool | None = None, rate: float | None = None) -> dict[str, Any]:
        if running is not None:
            self._row["clock_running"] = 1 if running else 0
        if rate is not None:
            if rate <= 0:
                raise Rejected("rate must be > 0", hint="use running=False to pause")
            self._row["clock_rate"] = float(rate)
        self._save_row()
        return self.clock()

    def clock(self) -> dict[str, Any]:
        return {"t": self.t, "running": bool(self._row["clock_running"]), "rate": float(self._row["clock_rate"]),
                "pending": self.store.count("scheduled", "world_id=?", (self.id,))}

    def say(self, who: str, text: str, reach: int = 1, to: str | None = None,
            caused_by: int | None = None) -> dict[str, Any]:
        """Speech. Addressed speech targets the listener so it shows in both their logs; the room still hears it."""
        self.need(who)
        payload: dict[str, Any] = {"text": str(text)}
        target = who
        if to:
            self.need(to)
            payload["to"] = to
            target = to
        return self.emit("say", actor=who, target=target, reach=reach, payload=payload, caused_by=caused_by)

    # ---- principals -----------------------------------------------------------

    def join(self, principal_id: str, entity_id: str, kind: str = "agent", name: str = "",
             capabilities: list[str] | None = None) -> dict[str, Any]:
        self.need(entity_id)
        other = self.embodied(entity_id)
        if other and other["id"] != principal_id:
            raise Rejected(f"{entity_id} is already embodied by {other['id']}",
                           hint="pick another entity, or spawn one with author capability")
        old = self.store.get("principal", self.id, principal_id)
        ecur = self.entity_cursor(entity_id)
        row = {"world_id": self.id, "id": principal_id, "kind": kind, "name": name or principal_id,
               "capabilities": capabilities if capabilities is not None else (old["capabilities"] if old else []),
               "entity_id": entity_id,
               "cursor_seq": ecur if ecur is not None else (old["cursor_seq"] if old else self.store.next_seq(self.id) - 1)}
        self.store.put("principal", row)
        self.emit("embodied", actor=entity_id, target=entity_id, reach=1,
                  payload={"principal": principal_id, "as": kind})
        return row

    def leave(self, principal_id: str) -> None:
        p = self.store.get("principal", self.id, principal_id)
        if p is None:
            return
        self.store.delete("principal", self.id, principal_id)
        if p["entity_id"]:
            self.emit("released", actor=p["entity_id"], target=p["entity_id"], reach=1,
                      payload={"principal": principal_id})

    def principal(self, principal_id: str) -> dict[str, Any] | None:
        return self.store.get("principal", self.id, principal_id)

    def principals(self) -> list[dict[str, Any]]:
        return self.store.query("principal", "world_id=?", (self.id,), order="id")

    def _bump_cursor(self, principal_id: str) -> None:
        p = self.store.get("principal", self.id, principal_id)
        if p:
            p["cursor_seq"] = self.store.next_seq(self.id) - 1
            self.store.put("principal", p)

    def set_cursor(self, principal_id: str, seq: int) -> None:
        p = self.store.get("principal", self.id, principal_id)
        if p:
            p["cursor_seq"] = seq
            self.store.put("principal", p)
            if p.get("entity_id"):
                self.set_entity_cursor(p["entity_id"], seq)

    def entity_cursor(self, entity_id: str) -> int | None:
        """Where this entity last looked. Its own, whoever is driving it."""
        v = self._row["meta"].get("cursors", {}).get(entity_id)
        return int(v) if v is not None else None

    def set_entity_cursor(self, entity_id: str, seq: int) -> None:
        self._row["meta"].setdefault("cursors", {})[entity_id] = int(seq)
        self._save_row()

    def meta(self) -> dict[str, Any]:
        return dict(self._row["meta"])

    def set_meta(self, changes: dict[str, Any]) -> dict[str, Any]:
        for k, v in changes.items():
            if v is None:
                self._row["meta"].pop(k, None)
            else:
                self._row["meta"][k] = v
        self._save_row()
        return self.meta()

    # ---- minds -------------------------------------------------------------------

    def remember(self, entity_id: str, text: str, actor: str | None = None) -> dict[str, Any]:
        """Append to the entity's secret memory. Whoever embodies it next reads the same notes."""
        e = self.need(entity_id)
        note = {"t": self.t, "seq": self.store.next_seq(self.id), "text": str(text)}
        mem = list(e["state"].get("memory") or [])
        mem.append(note)
        e["state"]["memory"] = mem
        self._touch(e)
        self.emit("remembered", actor=actor or entity_id, target=entity_id, reach=0, payload={"text": str(text)})
        return note

    def exchanges(self, a: str, b: str, limit: int = 5) -> list[dict[str, Any]]:
        """The last spoken exchanges between two entities, from the log. Newest last."""
        rows = self.store.query(
            "event",
            "world_id=? AND kind IN ('say','talked') AND ((actor_id=? AND target_id=?) OR (actor_id=? AND target_id=?))",
            (self.id, a, b, b, a), order="seq DESC", limit=limit)
        return [_public_event(r) for r in reversed(rows)]

    def known_places(self, entity_id: str) -> list[str]:
        """Places this entity has arrived at, from its own moved events, plus where it stands."""
        rows = self.store.query("event", "world_id=? AND kind='moved' AND target_id=?", (self.id, entity_id),
                                order="seq")
        out: list[str] = []
        for r in rows:
            to = r["payload"].get("to")
            if to and to not in out and self.get(to):
                out.append(to)
        e = self.get(entity_id)
        if e and e["parent_id"] and e["parent_id"] not in out:
            out.append(e["parent_id"])
        return out

    _OPINION = {"given": 2, "hit": -3, "attacked": -3, "talked": 0, "say": 0}

    def _opinion_floor(self, ev: dict[str, Any]) -> None:
        """A deterministic floor under relationships: meeting makes a `knows` edge both ways, gifts and blows
        move `standing` on the receiver's side. A mind refines the edge data; the engine never speaks."""
        kind = ev["kind"]
        actor, target = ev["actor_id"], ev["target_id"]
        if kind == "say":
            target = ev["payload"].get("to")
        if not actor or not target or actor == target:
            return
        a, b = self.get(actor), self.get(target)
        if not a or not b or not self.is_a(a["type"], "creature") or not self.is_a(b["type"], "creature"):
            return
        delta = self._OPINION[kind]
        for src, dst, d in ((target, actor, delta), (actor, target, 0)):
            ex = next((x for x in self.edges(src, "knows", "out") if x["target"] == dst), None)
            if ex is None:
                ex = {"world_id": self.id, "id": self._next_id("g"), "source": src, "target": dst, "relation": "knows",
                      "data": {"standing": 0, "met_t": self.t, "count": 0}}
            data = dict(ex["data"])
            data["standing"] = int(data.get("standing", 0)) + d
            data["count"] = int(data.get("count", 0)) + 1
            data["last_t"] = self.t
            data["last_kind"] = kind
            ex["data"] = data
            self.store.put("edge", ex)
        self.emit("opinion", actor=actor, target=target, reach=0, caused_by=ev["seq"],
                  payload={"kind": kind, "delta": delta})

    # ---- integrity -------------------------------------------------------------

    def state_hash(self) -> str:
        """Hash of all projected state. Equal hashes after equal action sequences = determinism."""
        h = hashlib.sha256()
        for table in ("entity", "edge", "hyperedge", "scheduled"):
            for row in self.store.query(table, "world_id=?", (self.id,), order="id"):
                # world_id left out so a fork hashes equal to its source
                row = {k: v for k, v in row.items() if k not in ("created_seq", "updated_seq", "world_id")}
                h.update(json.dumps(row, sort_keys=True, default=str).encode())
        h.update(f"{self.t}".encode())
        return h.hexdigest()

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "root": self.root_id, "t": self.t,
            "description": self._row["meta"].get("description", ""),
            "entities": self.store.count("entity", "world_id=?", (self.id,)),
            "edges": self.store.count("edge", "world_id=?", (self.id,)),
            "events": self.store.count("event", "world_id=?", (self.id,)),
            "schemas": self.store.count("schema", "world_id=?", (self.id,)),
            "principals": [{"id": p["id"], "kind": p["kind"], "entity": p["entity_id"]} for p in self.principals()],
            "clock": self.clock(),
        }


# Events that exist for the log, not for listeners.
_SILENT_KINDS = frozenset({"before_act", "schema_defined", "script_defined", "scheduled", "patched", "linked", "unlinked",
                           "related", "unrelated", "spawned", "destroyed", "left", "moved", "embodied", "released",
                           "tick", "script_error", "finished", "opinion", "remembered"})
# Events hidden from the public stream (perceive, act results). Primitive mutations stay in the log.
_INTERNAL_KINDS = frozenset({"before_act", "schema_defined", "script_defined", "scheduled", "tick"})


class EventView(ScriptObject):
    _script_attrs = ("seq", "t", "kind", "actor", "target", "payload", "path")

    def __init__(self, ev: dict[str, Any]):
        self.seq = ev["seq"]
        self.t = ev["t"]
        self.kind = ev["kind"]
        self.actor = ev["actor_id"]
        self.target = ev["target_id"]
        self.payload = dict(ev["payload"])
        self.path = list(ev["path"])


def _event_view(ev: dict[str, Any]) -> EventView:
    return EventView(ev)


def _public_event(e: dict[str, Any]) -> dict[str, Any]:
    return {"seq": e["seq"], "t": e["t"], "kind": e["kind"], "actor": e["actor_id"], "target": e["target_id"],
            "payload": e["payload"], "caused_by": e["caused_by"]}
