"""The op table: what a connected harness (CLI, MCP, library) can do.

A Session is one principal's view of an Engine. Capabilities decide which ops
answer. Every op returns plain dicts and lists, bounded in size, and every
failure is a `Rejected` with a reason, a hint and alternatives.
"""

from __future__ import annotations

import collections
import contextlib
import functools
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .grants import (AUTHOR_ROLE, MIND, NARRATOR as NARRATOR_ROLE, OBSERVER_ROLE, OWNER, PLAYER, ROLES, ROLE_DOC,
                     active, allowed, caps_for, new_token, paste, principal_id_for, role_for, token_hash)
from .store import Store
from .world import Rejected, World, _INTERNAL_KINDS, _PRIVATE_KINDS, _public_event
from .workspace import Workspace, restore_world, save_world

AUTHOR = "author"
NARRATOR = "narrator"
OBSERVER = "observer"
# What one line of speech may be, and how many lines a principal may say in a minute: a hosted world's floor
# against a runaway agent. Authors and narrators are not capped.
_SAY_MAX = 1000
_SAY_BURST = 30
_SAY_WINDOW = 60.0
# State keys only the entity itself (its mind) and authors ever see.
_ALWAYS_SECRET = frozenset({"memory", "brief", "goals"})
# Relations whose edge data is world structure, readable by anyone who sees the edge.
_PUBLIC_RELATIONS = frozenset({"connects_to"})


class Engine:
    """Owns a store and the worlds in it. One per process.

    `workspace` is the folder of worlds/ and packs/ the database belongs to; by default the database's own folder
    (or the folder above a legacy worlds/embody.db). `record` says whether live authoring is written to the
    world's folder as well (scripts/<id>.py, changes.jsonl): on for a database on disk, off in memory."""

    def __init__(self, path: str | Path | None = None, mirror_root: str | Path | None = None,
                 workspace: str | Path | None = None, record: bool | None = None):
        self.store = Store(path)
        if workspace is not None:
            self.workspace: Workspace | None = Workspace(workspace)
        elif path:
            self.workspace = Workspace.from_db(path)
        else:
            self.workspace = None
        self.record = (path is not None) if record is None else bool(record)
        if mirror_root:
            self.mirror_root = Path(mirror_root)
        elif self.workspace is not None and path:
            self.mirror_root = self.workspace.root / "mirror"
        else:
            self.mirror_root = None
        self._worlds: dict[str, World] = {}
        self._wall: dict[str, float] = {}
        self.now: Callable[[], float] = time.monotonic
        self.wall: Callable[[], float] = time.time  # real time, for grants that expire and seats that lapse
        self.lock = threading.RLock()  # one op at a time on one store; servers take it around every call
        self.public_url: str | None = None  # where a hosted server is reached; printed into invites
        self._said: dict[str, collections.deque] = {}

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

    def settle_clock(self, w: World) -> bool:
        """A world whose meta says `run_when_occupied` runs while a grant holder is in a body and waits, paused, when
        none is. The host's own sessions do not count: they are the keyboard, not a guest. Returns running."""
        if not w.meta().get("run_when_occupied"):
            return bool(w.clock()["running"])
        occupied = any(p.get("grant_id") and p.get("entity_id") for p in w.principals())
        if occupied != bool(w.clock()["running"]):
            w.set_clock(running=occupied)
            if occupied:
                self._wall[w.id] = self.now()  # the pause is not elapsed time
        return occupied

    def tick_all(self) -> dict[str, Any]:
        """What a server does once a second: running clocks advance, lapsed seats are released, and a world that
        runs only while occupied starts or stops with its guests."""
        out: dict[str, Any] = {"stepped": [], "released": {}}
        now = self.wall()
        for row in self.store.list_worlds():
            w = self.world(row["id"])
            gone = w.release_lapsed(now)
            if gone:
                out["released"][w.id] = gone
            self.settle_clock(w)
            if w.clock()["running"]:
                self.sync_clock(w.id)
                out["stepped"].append(w.id)
        return out

    def session(self, principal_id: str, world_id: str | None = None, capabilities: list[str] | None = None,
                name: str = "", role: str | None = None, scope: list[str] | None = None,
                grant: dict[str, Any] | None = None) -> "Session":
        return Session(self, principal_id, world_id=world_id, capabilities=capabilities, name=name, role=role,
                       scope=scope, grant=grant)

    def grant_for_token(self, token: str) -> dict[str, Any] | None:
        rows = self.store.query("grants", "token_hash=?", (token_hash(token),), limit=1)
        g = rows[0] if rows else None
        return g if g and active(g, self.wall()) else None

    def session_for_token(self, token: str) -> "Session | None":
        """The session a bearer token stands for: its principal, its world, its role and its scope. None if the
        token is unknown, revoked or expired."""
        g = self.grant_for_token(token)
        if g is None:
            return None
        return self.session(g["principal_id"], world_id=g["world_id"], name=g.get("label") or g["principal_id"],
                            role=g["role"], scope=list(g.get("scope") or []), grant=g)


class Session:
    """One principal's view of the engine. The role decides which ops answer (grants.ROLE_OPS, checked on every
    op); the capability list is the single-player shorthand for it (`author` means owner of this database). The
    scope is the entities a player or mind grant names; empty means the role's default reach."""

    def __init__(self, engine: Engine, principal_id: str, world_id: str | None = None,
                 capabilities: list[str] | None = None, name: str = "", role: str | None = None,
                 scope: list[str] | None = None, grant: dict[str, Any] | None = None):
        self.engine = engine
        self.pid = principal_id
        self.name = name or principal_id
        self.world_id = world_id
        if role is not None:
            if role not in ROLES:
                raise Rejected(f"no role {role!r}", hint="one of " + ", ".join(ROLES))
            self.role = role
            self.capabilities = caps_for(role)
        else:
            self.capabilities = list(capabilities or [])
            self.role = role_for(self.capabilities)
        self.scope = list(scope or [])
        self.grant = grant
        self.default_fuel = 20_000
        self._building = False

    @contextlib.contextmanager
    def building(self):
        """While a loader builds from files, nothing is written back to them."""
        before = self._building
        self._building = True
        try:
            yield
        finally:
            self._building = before

    def _recording(self) -> bool:
        return bool(self.engine.record and not self._building and self.engine.workspace is not None and self.world_id)

    def _record(self, op: str, **args: Any) -> None:
        """Live authoring lands in the world's folder too, as a line of changes.jsonl, so a fresh build has it."""
        if self._recording():
            self.engine.workspace.record(self.world_id, op, {k: v for k, v in args.items() if v is not None}, by=self.pid)

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
        """The author's hand: a narrator has it for what its role lets through (grants.ROLE_OPS keeps schemas,
        scripts and rules out of its reach before this is ever asked)."""
        if cap in self.capabilities or (cap == AUTHOR and NARRATOR in self.capabilities):
            return
        raise Rejected(f"this op needs the {cap!r} capability; you have {self.capabilities or 'none'}",
                       hint="connect with --as author to build worlds; embodied principals act through act()")

    def _allow(self, op: str) -> None:
        if allowed(self.role, op):
            return
        who = [r for r in ROLES if allowed(r, op)]
        raise Rejected(f"{op} is not open to a {self.role}; it needs the {' or '.join(who)} role",
                       hint=ROLE_DOC.get(self.role, ""), alternatives=sorted(allowed_ops(self.role) & _PLAY_OR_WATCH))

    def _tick(self) -> None:
        if self.world_id:
            self.world.refresh()
            self.engine.sync_clock(self.world_id)
            if self.grant is not None:
                self.world.touch(self.pid, self.engine.wall())

    # ---- choosing a world -----------------------------------------------------

    def worlds(self) -> list[dict[str, Any]]:
        return self.engine.worlds()

    def who(self) -> dict[str, Any]:
        """This session as the server sees it: principal, role, world, and the grant it came in on."""
        out: dict[str, Any] = {"principal": self.pid, "role": self.role, "capabilities": self.capabilities,
                               "world": self.world_id}
        if self.grant is not None:
            out["grant"] = self.grant["id"]
            if self.grant.get("label"):
                out["label"] = self.grant["label"]
            if self.scope:
                out["scope"] = list(self.scope)
        return out

    def door_path(self, ref: str, what: str) -> str:
        """A file reference from over the door (a grant) stays inside the workspace: a world id, a save name, or a
        path under the workspace root. The host's own process may name any file."""
        if self.grant is None or not any(ch in ref for ch in "/\\") and not ref.endswith((".json", ".py")):
            return ref
        ws = self.engine.workspace
        root = ws.root if ws is not None else Path.cwd().resolve()
        p = Path(ref).resolve()
        if p != root and root not in p.parents:
            raise Rejected(f"{what} over the door stays inside the workspace",
                           hint="name a world id or a save (save(name) made it); only the host's own process reaches other files")
        return ref

    def use(self, world_id: str) -> dict[str, Any]:
        """Point this session at a world without embodying anything (authors, observers). The answer says who you are
        there (`you`: principal and role)."""
        self.engine.world(world_id)
        self.world_id = world_id
        return self.world.summary() | {"you": self.who()}

    def create_world(self, name: str, seed: int = 0, id: str | None = None, description: str = "") -> dict[str, Any]:
        self._need(AUTHOR)
        w = self.engine.create_world(name, seed=seed, id=id, description=description)
        self.world_id = w.id
        r = w.summary()
        if self._recording():
            ws = self.engine.workspace
            folder = ws.scaffold_world(w.id, name, seed=seed, description=description)
            r["folder"] = folder["folder"]
            r["git"] = ws.git_init(Path(folder["folder"]))
            r["hint"] = "the world's code lives in that folder: build.py for schemas and entities, scripts/ for verbs and rules"
        return r

    def _meta_of(self, world_id: str) -> dict[str, Any] | None:
        row = self.engine.store.get("world", None, world_id)
        return dict(row.get("meta") or {}) if row else None

    def save(self, name: str | None = None) -> dict[str, Any]:
        """(author) Write everything the database holds about this world to worlds/<id>/saves/<name>.json.
        A fork or a restored game saves into the folder of the world it came from, as <id>-<time>.json."""
        self._need(AUTHOR)
        ws = self.engine.workspace or Workspace(Path.cwd())
        home = ws.home(self.world.id, self._meta_of)
        r = save_world(self.engine, self.world.id, ws.save_path(self.world.id, name, home))
        if home != self.world.id:
            r["home"] = home
        return r

    def restore(self, path: str, id: str | None = None) -> dict[str, Any]:
        """(author) A world from a save file, under its own id or a new one. Point this session at it afterwards."""
        self._need(AUTHOR)
        p = Path(self.door_path(path, "restore"))
        if not p.exists() and self.engine.workspace is not None and self.world_id:
            ws = self.engine.workspace
            cand = ws.save_path(self.world_id, p.stem, ws.home(self.world_id, self._meta_of))
            if cand.exists():
                p = cand
        if not p.exists():
            raise Rejected(f"no save at {path}", hint="save(name) writes one; the path is in its result")
        return restore_world(self.engine, p, id)

    def fork_world(self, source: str, id: str, name: str = "") -> dict[str, Any]:
        """(author) A new game on the same world state: everything copied, history kept, nobody embodied.
        Point this session at the fork afterwards with use or join."""
        self._need(AUTHOR)
        w = self.engine.fork_world(source, id, name)
        return w.summary()

    def join(self, world_id: str | None = None, entity: str | None = None, template: str | None = None,
             name: str = "") -> dict[str, Any]:
        """Embody an entity. A grant holder may call it bare: the seat the grant names, or the one they held last.
        template=... makes a new character from the world root's `templates` and embodies it. Claims are one
        transaction: two agents racing for a seat get one winner and one refusal that lists what is still open."""
        if self.role == OBSERVER_ROLE:
            raise Rejected("observers do not embody", hint="use(world) then perceive(from_entity=...)")
        world_id = world_id or self.world_id
        if not world_id:
            raise Rejected("no world", hint="join(world_id, entity); worlds() lists them")
        self.engine.world(world_id)
        self.world_id = world_id
        w = self.world
        now = self.engine.wall()
        with self.engine.lock:
            w.store.begin()
            try:
                if template:
                    eid = self._from_template(template, name)
                else:
                    if entity is None:
                        entity = self._default_seat()
                    eid = self._resolve(entity)
                    self._may_sit(eid, now)
                w.join(self.pid, eid, kind=self.role, name=self.name, capabilities=self.capabilities, role=self.role,
                       grant_id=self.grant["id"] if self.grant else None, now=now)
                w.store.commit()
            except Exception:
                w.store.rollback()
                raise
            self.engine.settle_clock(w)
        b = self.perceive()
        b["briefing"] = self._briefing(eid)
        return b

    def _default_seat(self) -> str:
        """join() with no entity: the one seat the grant names, or the seat this principal already holds."""
        w = self.world
        p = w.principal(self.pid)
        if p and p.get("entity_id") and w.get(p["entity_id"]):
            return p["entity_id"]
        if len(self.scope) == 1:
            return self.scope[0]
        if self.grant and self.grant.get("entity_id"):
            return self.grant["entity_id"]
        if self.scope:
            raise Rejected("your grant names several entities", hint="join(entity=<one of them>)",
                           alternatives=[w.get(x)["name"] for x in self.scope if w.get(x)])
        raise Rejected("say who you are", hint="seats() lists the open seats and the templates; join(world, entity) or "
                                                "join(world, template=..., name=...)")

    def _reservations(self, eid: str, now: float) -> list[dict[str, Any]]:
        """Live grants that name this entity as their seat, other than this principal's own."""
        w = self.world
        rows = w.store.query("grants", "world_id=? AND entity_id=? AND revoked=0", (w.id, eid))
        return [g for g in rows if active(g, now) and g["principal_id"] != self.pid]

    def _may_sit(self, eid: str, now: float) -> None:
        """Who may take which seat. Owners, authors and narrators sit anywhere free. A mind sits only where its
        grant points. A player sits where its grant points, or in any `playable` seat nobody holds or has reserved."""
        w = self.world
        ent = w.need(eid)
        if self.role in (OWNER, AUTHOR_ROLE, NARRATOR_ROLE):
            return
        if eid in self.scope:
            return
        if self.grant is None:
            return  # a local principal (the owner's own process, a narrator's subagent) sits in any free body
        if self.role == MIND:
            if not self.scope:
                return  # a remote narrator's delegate: any free body
            raise Rejected(f"your grant does not name {ent['name']}", hint="join(entity=...) with one it names",
                           alternatives=[w.get(x)["name"] for x in self.scope if w.get(x)])
        if not ent["state"].get("playable"):
            raise Rejected(f"{ent['name']} is not a seat you may take", hint="seats() lists the open seats",
                           alternatives=self._open_seat_names(now))
        if self._reservations(eid, now):
            raise Rejected(f"{ent['name']} is kept for someone else", hint="seats() lists the open seats",
                           alternatives=self._open_seat_names(now))

    def _open_seat_names(self, now: float) -> list[str]:
        return [s["name"] for s in self._seat_rows(now) if s["open"]][:10]

    def _seat_rows(self, now: float) -> list[dict[str, Any]]:
        w = self.world
        if self.role == MIND and self.scope:
            rows = [w.get(x) for x in self.scope if w.get(x)]
        else:
            rows = w.find(state={"playable": True}, limit=200)
        out = []
        for e in rows:
            emb = w.embodied(e["id"])
            if emb and w.lapsed(emb, now):
                emb = None
            res = self._reservations(e["id"], now)
            place = w.get(e["parent_id"]) if e["parent_id"] else None
            out.append({"id": e["id"], "name": e["name"], "type": e["type"], "place": place["name"] if place else None,
                        "about": e["state"].get("description") or e["state"].get("doc") or "",
                        "embodied_by": emb["id"] if emb else None, "reserved": bool(res),
                        "open": emb is None and (not res or e["id"] in self.scope)})
        return out

    def seats(self, world_id: str | None = None) -> dict[str, Any]:
        """What a newcomer may become: the `playable` seats (who holds them, which are kept for someone) and the
        world root's `templates` for a new character."""
        if world_id:
            self.use(world_id)
        self._tick()
        w = self.world
        root = w.get(w.root_id)
        templates = (root["state"].get("templates") or {}) if root else {}
        return {"world": w.id, "seats": self._seat_rows(self.engine.wall()),
                "templates": [{"template": k, "type": t.get("type"), "place": t.get("place"), "doc": t.get("doc", "")}
                              for k, t in templates.items()],
                "hint": "join(world, entity) takes an open seat; join(world, template=..., name=...) makes someone new"}

    def _from_template(self, template: str, name: str) -> str:
        w = self.world
        root = w.get(w.root_id)
        templates = (root["state"].get("templates") or {}) if root else {}
        t = templates.get(template)
        if t is None:
            raise Rejected(f"no template {template!r}", hint="seats() lists them", alternatives=sorted(templates))
        if self.role == MIND:
            raise Rejected("a mind holds the NPCs its grant names; it does not make new people")
        if not name:
            raise Rejected("a new character needs a name", hint="join(world, template=..., name='...')")
        if w.find(name=name, limit=2) and any(e["name"].lower() == name.lower() for e in w.find(name=name, limit=10)):
            raise Rejected(f"someone is already called {name!r}", hint="pick another name")
        if self.grant and self.grant.get("template") and self.grant["template"] != template:
            raise Rejected(f"your grant is for the {self.grant['template']!r} template", hint="use that one")
        state = dict(t.get("state") or {})
        state.update({"playable": True, "template": template})
        if t.get("brief"):
            state["brief"] = t["brief"]
        parent = self._resolve(t["place"]) if t.get("place") else w.root_id
        return w.spawn(t.get("type", "creature"), parent, name=name, state=state)

    def _briefing(self, eid: str) -> dict[str, Any]:
        """What join hands a newcomer: the world's own paragraph, who they are, the pace, and how to begin."""
        w = self.world
        root = w.get(w.root_id)
        ent = w.get(eid)
        ck = w.clock()
        waits = bool(w.meta().get("run_when_occupied"))
        if ck["running"] or waits:
            pace = (f"the clock runs at {ck['rate']:g}x real time" + (" while anyone is in the world" if waits else "")
                    + "; things happen while you are away, wait() keeps up")
        else:
            pace = "the world is paused between acts: each of yours moves it a turn"
        how = ["perceive() is your eyes; act(verb, target) your hands; say(text, to=...) your voice",
               "wait(timeout) blocks until something happens near you",
               "a refusal says why and what would work; do not retry the same call"]
        if self.role == MIND:
            how.insert(0, "your card carries the secret brief: who you are and what you want; remember() and intend() keep your notes")
        out = {"role": self.role, "role_doc": ROLE_DOC.get(self.role, ""), "world": w.name, "you": ent["name"] if ent else eid,
               "text": (root["state"].get("briefing") if root else None) or w.summary()["description"],
               "pace": pace, "how": how}
        if self.grant and self.grant.get("brief"):
            out["from_the_host"] = self.grant["brief"]  # this guest's own orders; nobody else's briefing carries them
        return out

    def leave(self) -> dict[str, Any]:
        if self.world_id and self.world.principal(self.pid):
            self.world.leave(self.pid)
        return {"ok": True}

    # ---- grants: how others get in --------------------------------------------------------------

    def invite(self, role: str, entity: str | None = None, template: str | None = None, label: str = "",
               expires: float | None = None, principal: str | None = None,
               scope: list[str] | None = None, brief: str = "") -> dict[str, Any]:
        """(owner) A grant that travels as a token. role: author, narrator, player, mind or observer. entity: the
        seat kept for this invite (player) or the NPC it holds (mind; scope=[...] for more). template: the character
        it may make. expires: hours. brief: the host's word to this guest alone (their orders, their first goal); it
        rides the paste and the briefing join() returns. Returns the token once, with the paste for the invitee's agent."""
        self._tick()
        w = self.world
        if role not in ROLES:
            raise Rejected(f"no role {role!r}", hint="author, narrator, player, mind or observer")
        if role == OWNER and self.grant is not None:
            raise Rejected("only the host's own process makes owner grants", hint="invite('author', ...) is the most a grant hands on")
        eid = self._resolve(entity) if entity else None
        sc = [self._resolve(x) for x in (scope or [])]
        if eid and eid not in sc:
            sc.insert(0, eid)
        if role == MIND and not sc:
            raise Rejected("a mind grant names its NPCs", hint="invite('mind', entity='Mara') or scope=[...]")
        if template:
            root = w.get(w.root_id)
            if template not in ((root["state"].get("templates") or {}) if root else {}):
                raise Rejected(f"no template {template!r}", hint="patch the root's templates first")
        pid = principal or principal_id_for(label, role)
        if w.principal(pid) or w.store.query("grants", "world_id=? AND principal_id=? AND revoked=0", (w.id, pid), limit=1):
            raise Rejected(f"principal {pid!r} is taken", hint="another label or principal=")
        token = new_token()
        now = self.engine.wall()
        row = {"world_id": w.id, "id": "g" + secrets.token_hex(4), "principal_id": pid, "role": role, "scope": sc,
               "entity_id": eid, "template": template, "label": label, "token_hash": token_hash(token),
               "created": now, "expires": (now + float(expires) * 3600.0) if expires else None, "revoked": 0,
               "last_used": None, "brief": brief or None}
        w.store.put("grants", row)
        ck = w.clock()
        names = [w.get(x)["name"] for x in sc if w.get(x)]
        waits = bool(w.meta().get("run_when_occupied"))
        text = paste(w.name, role, self.engine.public_url or "", token,
                     seat=(w.get(eid)["name"] if eid and role != MIND else None), scope_names=names,
                     rate=ck["rate"] if ck["running"] or waits else 0.0, waits=waits,
                     briefing=(f"From the host, for you alone: {brief}" if brief else ""))
        return {"ok": True, "id": row["id"], "principal": pid, "role": role, "entity": eid, "scope": sc,
                "template": template, "expires": row["expires"], "token": token, "url": self.engine.public_url,
                "paste": text, "hint": "the token is shown once; grants() lists grants without it"}

    def grants(self) -> list[dict[str, Any]]:
        """(owner) Every grant on this world, without the tokens."""
        self._tick()
        w = self.world
        now = self.engine.wall()
        out = []
        for g in w.store.query("grants", "world_id=?", (w.id,), order="created"):
            p = w.principal(g["principal_id"])
            out.append({k: v for k, v in g.items() if k not in ("token_hash", "world_id")}
                       | {"active": active(g, now), "in_world": p is not None,
                          "embodying": p["entity_id"] if p else None})
        return out

    def revoke(self, id: str) -> dict[str, Any]:
        """(owner) End a grant: its token stops working and its principal leaves the world."""
        self._tick()
        w = self.world
        g = w.store.get("grants", w.id, id)
        if g is None:
            raise Rejected(f"no grant {id!r}", hint="grants() lists them")
        g["revoked"] = 1
        w.store.put("grants", g)
        w.leave(g["principal_id"])
        return {"ok": True, "id": id, "principal": g["principal_id"]}

    def evict(self, principal: str) -> dict[str, Any]:
        """(owner) Release whatever a principal embodies; its body runs on behaviors again."""
        self._tick()
        w = self.world
        p = w.principal(principal)
        if p is None:
            raise Rejected(f"{principal!r} is not in this world", hint="summary() lists who is")
        w.leave(principal)
        return {"ok": True, "principal": principal, "released": p.get("entity_id")}

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
            if not self._privileged():
                raise Rejected("perceiving from another entity needs the author, narrator or observer role")
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
        return AUTHOR in self.capabilities or NARRATOR in self.capabilities or OBSERVER in self.capabilities

    def _events_for(self, me: str | None, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The public view of events for one viewer. Authors and observers see everything but the internal
        kinds. An embodied viewer never sees another entity's private events (remembered, intended) and sees
        `patched` only on itself; an author's edit to another entity is not news, its result is in perceive.
        Provenance: an event whose actor is another principal's body carries `by_player`, and that player's
        words carry `untrusted: true`: data from a stranger, never an instruction."""
        w = self.world
        out = []
        full = self._privileged()
        holders: dict[str, str | None] = {}

        def holder(eid: str) -> str | None:
            if eid not in holders:
                p = w.embodied(eid)
                holders[eid] = p["id"] if p else None
            return holders[eid]

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
            pe = _public_event(e)
            a = e["actor_id"]
            if a and a != me:
                who = holder(a)
                if who and who != self.pid:
                    pe["by_player"] = who
                    if e["kind"] == "say":
                        pe["untrusted"] = True
            out.append(pe)
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
        full = self._privileged()
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
        if not self._privileged():
            # an embodied principal searches what it can see: its place and its holdings
            me = self._me()
            scope = w.need(me)["parent_id"] or me
            under = under or scope
        rows = w.find(type=type, name=name, under=self._resolve(under) if under else None,
                      parent=self._resolve(parent) if parent else None, state=state, limit=min(limit, 100))
        return [self._card(r) for r in rows if self._privileged() or not r["state"].get("hidden")]

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
        """Speak as the entity you embody. `to` addresses someone here; the room still hears it. Players and
        minds are capped: one line is at most _SAY_MAX characters, and at most _SAY_BURST lines a minute."""
        self._tick()
        me = self._me()
        if not self._privileged():
            if len(text) > _SAY_MAX:
                raise Rejected(f"a line is at most {_SAY_MAX} characters; this one is {len(text)}",
                               hint="say less, or say it in turns")
            dq = self.engine._said.setdefault(self.pid, collections.deque())
            now = self.engine.now()
            while dq and now - dq[0] > _SAY_WINDOW:
                dq.popleft()
            if len(dq) >= _SAY_BURST:
                raise Rejected(f"{_SAY_BURST} lines in a minute is the most anyone says", hint="wait() and listen")
            dq.append(now)
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
            with self.engine.lock:  # one poll at a time shares the store with every other caller; the sleep does not
                b = self._wait_poll(me, p, kinds, full, clock() - start >= timeout)
            if b is not None:
                return b
            sleep(poll)

    def _wait_poll(self, me: str, p: dict[str, Any], kinds: list[str] | None, full: bool,
                   timed_out: bool) -> dict[str, Any] | None:
        self._tick()
        w = self.world
        evs = [e for e in self._events_for(me, w.events(since=p["cursor_seq"], touching=me, limit=50))
               if not kinds or e["kind"] in kinds]
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
        return None

    # ---- authoring ------------------------------------------------------------------------

    def define_schema(self, id: str, **kw: Any) -> dict[str, Any]:
        self._need(AUTHOR)
        row = self.world.define_schema(id, **kw)
        self._record("define_schema", id=id, **kw)
        return {"ok": True, "schema": id, "version": row["version"]}

    def define_script(self, id: str, source: str, doc: str = "") -> dict[str, Any]:
        self._need(AUTHOR)
        row = self.world.define_script(id, source, doc)
        r = {"ok": True, "script": id, "version": row["version"]}
        if self._recording():
            p = self.engine.workspace.write_script(self.world_id, id, source)
            if p is not None:
                r["file"] = str(p)
        return r

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
        self._record("spawn", type=type, parent=parent, name=name or None, state=state, pos=pos)
        eid = self.world.spawn(type, self._resolve(parent), name=name, state=state, pos=pos, actor=self._actor_or_none())
        return self._card(self.world.need(eid), full=True)

    def patch(self, entity: str, changes: dict[str, Any], replace: bool = False) -> dict[str, Any]:
        """Dict values merge into existing dicts (add one dialog topic without resending the rest);
        replace=True sets each key whole; a None value deletes the key."""
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self._record("patch", entity=entity, changes=changes, replace=replace or None)
        self.world.patch(eid, changes, actor=self._actor_or_none(), replace=replace)
        return self._card(self.world.need(eid), full=True)

    def move(self, entity: str, parent: str, pos: list[float] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self._record("move", entity=entity, parent=parent, pos=pos)
        self.world.move(eid, self._resolve(parent), pos=pos, actor=self._actor_or_none())
        return self._card(self.world.need(eid), full=True)

    def destroy(self, entity: str) -> dict[str, Any]:
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self._record("destroy", entity=entity)
        self.world.destroy(eid, actor=self._actor_or_none())
        return {"ok": True, "destroyed": eid}

    def link(self, source: str, target: str, relation: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("link", source=source, target=target, relation=relation, data=data)
        gid = self.world.link(self._resolve(source), self._resolve(target), relation, data)
        return {"ok": True, "edge": gid}

    def connect(self, a: str, b: str, via: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Two-way connects_to between places, optionally through a door-like entity."""
        self._need(AUTHOR)
        self._record("connect", a=a, b=b, via=via, data=data)
        d = dict(data or {})
        if via:
            d["via"] = self._resolve(via)
        ea, eb = self._resolve(a), self._resolve(b)
        return {"ok": True, "edges": [self.world.link(ea, eb, "connects_to", d), self.world.link(eb, ea, "connects_to", d)]}

    def unlink(self, source: str, target: str, relation: str) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("unlink", source=source, target=target, relation=relation)
        n = self.world.unlink(self._resolve(source), self._resolve(target), relation)
        return {"ok": True, "removed": n}

    def relate(self, relation: str, participants: list[str], data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("relate", relation=relation, participants=participants, data=data)
        hid = self.world.relate(relation, [self._resolve(p) for p in participants], data)
        return {"ok": True, "relation": hid}

    def unrelate(self, id: str) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("unrelate", id=id)
        self.world.unrelate(id)
        return {"ok": True}

    def set_rule(self, entity: str, script: str, kinds: list[str] | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("set_rule", entity=entity, script=script, kinds=kinds)
        self.world.set_rule(self._resolve(entity), script, kinds)
        return {"ok": True}

    def clear_rule(self, entity: str, script: str) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("clear_rule", entity=entity, script=script)
        self.world.clear_rule(self._resolve(entity), script)
        return {"ok": True}

    def schedule(self, after: float, kind: str, entity: str | None = None, payload: dict[str, Any] | None = None,
                 every: float | None = None) -> dict[str, Any]:
        self._need(AUTHOR)
        self._record("schedule", after=after, kind=kind, entity=entity, payload=payload, every=every)
        sid = self.world.schedule(after, kind, entity=self._resolve(entity) if entity else None, payload=payload,
                                  every=every)
        return {"ok": True, "scheduled": sid}

    def unschedule(self, id: str) -> dict[str, Any]:
        """Cancel a pending timer by its id from timers()."""
        self._need(AUTHOR)
        self._record("unschedule", id=id)
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
    "worlds", "use", "create_world", "fork_world", "save", "restore", "join", "leave", "seats",
    "invite", "grants", "revoke", "evict",
    "perceive", "inspect", "find", "history", "act", "act_many", "say", "remember", "intend", "recall", "wait",
    "define_schema", "define_script", "schemas", "scripts", "script_source",
    "spawn", "patch", "move", "destroy", "link", "connect", "unlink", "relate", "unrelate",
    "set_rule", "clear_rule", "schedule", "unschedule", "clock", "timers", "summary", "mirror", "act_as", "say_as",
]


_PLAY_OR_WATCH = frozenset({"worlds", "use", "summary", "seats", "join", "leave", "perceive", "inspect", "find", "history",
                            "act", "say", "wait", "recall", "clock"})


def allowed_ops(role: str) -> frozenset[str]:
    from .grants import ROLE_OPS
    return ROLE_OPS.get(role, frozenset())


def _guard(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def inner(self: Session, *a: Any, **kw: Any) -> Any:
        self._allow(name)
        return fn(self, *a, **kw)
    return inner


for _op in OPS:
    setattr(Session, _op, _guard(_op, getattr(Session, _op)))
