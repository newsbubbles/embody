"""The op table: what a connected harness (CLI, MCP, library) can do.

A Session is one principal's view of an Engine. Capabilities decide which ops
answer. Every op returns plain dicts and lists, bounded in size, and every
failure is a `Rejected` with a reason, a hint and alternatives.
"""

from __future__ import annotations

import collections
import contextlib
import functools
import inspect
import json
import math
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .grants import (HOST_MARK, LINK_HOURS, link_for, request_origin, new_code, page, AUTHOR_ROLE, BUILDER, MIND, NARRATOR as NARRATOR_ROLE, OBSERVER_ROLE, OWNER, PLAYER, ROLES, ROLE_DOC,
                     active, allowed, caps_for, new_token, paste, principal_id_for, role_for, token_hash)
from . import layout as geo
from .script import Script, ScriptError
from .store import Store
from . import access as acl
from .world import ALWAYS_SECRET, LIMITS_HEAD, Rejected, World, _INTERNAL_KINDS, _PRIVATE_KINDS, _public_event, own_verbs
from .workspace import Workspace, restore_world, save_world

AUTHOR = "author"
NARRATOR = "narrator"
OBSERVER = "observer"
# What one line of speech may be, and how many lines a principal may say in a minute: a hosted world's floor
# against a runaway agent. Authors and narrators are not capped.
_SAY_MAX = 1000
_SAY_BURST = 30
_NOTE_MAX = 2000  # a guest's remember() note, in characters
_DESCRIPTION_MAX = 800  # how a newcomer looks, set once at join(template=..., description=...)
_SAY_WINDOW = 60.0
# State keys only the entity itself (its mind) and authors ever see.
# State keys nobody but the host reads: a mind's memory, its brief and goals, and the host's plan for the world
# (`policy` on the root). The `secret` list on an entity adds its own.
_ALWAYS_SECRET = ALWAYS_SECRET
# Of a template on the root, what a newcomer may read: enough to pick one. The brief and the state are the host's.
_TEMPLATE_PUBLIC = ("type", "place", "doc")
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
        self.public_url_fixed = False  # the operator named the URL (--url, $EMBODY_URL): it wins over the request's host
        db = Path(str(self.store.path)) if getattr(self.store, "path", None) not in (None, ":memory:") else None
        self.requests_path: Path | None = db.with_name("seat-requests.jsonl") if db else None  # the site's seat requests
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
        none is. The host's own sessions do not count: they are the keyboard, not a guest. Returns running. A hosted
        world that should keep real time leaves this off and runs its clock; idle seats are World.idle()'s business."""
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
        token is unknown, revoked or expired. The token's first use spends its invite link."""
        g = self.grant_for_token(token)
        if g is None:
            return None
        if g.get("code_hash") or g.get("page"):
            self.spend_link(g)
        return self.session(g["principal_id"], world_id=g["world_id"], name=g.get("label") or g["principal_id"],
                            role=g["role"], scope=list(g.get("scope") or []), grant=g)

    def spend_link(self, g: dict[str, Any]) -> None:
        """Forget the invite link's code and the page that carried the token: from here the engine holds the hash only."""
        g["code_hash"] = None
        g["code_expires"] = None
        g["page"] = None
        self.store.set("grants", g["world_id"], g["id"], code_hash=None, code_expires=None, page=None)

    def url_now(self) -> str | None:
        """The MCP URL for an invite minted now: the operator's own, else the host this request came in on, else the
        default (a Railway domain, or the address the server bound)."""
        origin = request_origin.get()
        if origin and not self.public_url_fixed:
            return f"{origin}/mcp"
        return self.public_url

    def invite_page(self, code: str, origin: str | None = None) -> tuple[int, dict[str, Any] | str]:
        """What the door serves at /i/<code>: the page with the token while the link is good, else a refusal that says
        what happened and what to do. Reading the page does not spend the link; the token's first use does."""
        rows = self.store.query("grants", "code_hash=?", (token_hash(code),), limit=1)
        g = rows[0] if rows else None
        if g is None:
            return 404, {"ok": False, "reason": "no such invite, or one already taken up",
                         "hint": "a link works once and for a day; ask the host for a fresh one"}
        now = self.wall()
        if not active(g, now):
            return 410, {"ok": False, "reason": "this invite was revoked or has expired", "hint": "ask the host for a fresh one"}
        if g.get("code_expires") is not None and float(g["code_expires"]) <= now:
            self.spend_link(g)
            return 410, {"ok": False, "reason": "this invite link is older than a day and has gone stale",
                         "hint": "ask the host for a fresh one"}
        base = origin or (self.url_now() or "").removesuffix("/mcp")
        return 200, (g.get("page") or "").replace(HOST_MARK, base)


FIND_PAGE = 100  # the most find returns at once; offset pages through the rest

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
        self.limits: dict[str, Any] = dict((grant or {}).get("limits") or {})
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

    def _acted(self) -> None:
        """A deed by whoever holds this body, player or mind: the seat is in use, so its body's idle behaviors wait."""
        if self.world_id:
            self.world.touch(self.pid, self.engine.wall(), acted=True)

    def _need(self, cap: str) -> None:
        """The author's hand: a narrator has it for what its role lets through (grants.ROLE_OPS keeps schemas,
        scripts and rules out of its reach before this is ever asked)."""
        if cap in self.capabilities or (cap == AUTHOR and NARRATOR in self.capabilities):
            return
        raise Rejected(f"this op needs the {cap!r} capability; you have {self.capabilities or 'none'}",
                       hint="connect with --as author to build worlds; embodied principals act through act()")

    def _staff(self) -> bool:
        """The owner and author roles pass every access check on the authoring ops (docs/ACCESS.md)."""
        return self.role in (OWNER, AUTHOR_ROLE)

    def _subjects(self) -> set[str]:
        """Who this principal is to an access check: its id, and the body it holds."""
        p = self.world.principal(self.pid) if self.world_id else None
        return {self.pid} | ({p["entity_id"]} if p and p.get("entity_id") else set())

    def _access_allows(self, eid: str, bit: str) -> bool | None:
        """The entity's access for this principal (r, w or x), or None when it has none."""
        w = self.world
        acc = acl.of(w.get(eid))
        return None if acc is None else acl.allows(acc, self._subjects(), w.get(w.root_id), bit)

    def _plot(self) -> set[str] | None:
        """The ids a limited grant reads in full: its `under` and all below. None for a grant with no `under`."""
        under = self.limits.get("under")
        if not under:
            return None
        return set(self.world.subtree_ids(under)) if self.world.get(under) else set()

    def _sees(self, eid: str, plot: set[str] | None = None) -> bool:
        """A privileged reader reads this entity in full: everywhere without limits, else inside its plot or where
        the entity's access gives it r."""
        if not self.limits.get("under"):
            return True
        if eid in (plot if plot is not None else (self._plot() or set())):
            return True
        return bool(self._access_allows(eid, "r"))

    def _readable(self, e: dict[str, Any]) -> bool:
        """Another body reads this thing's state and contents unless its access keeps r from them."""
        acc = acl.of(e)
        return acc is None or acl.allows(acc, self._subjects(), self.world.get(self.world.root_id), "r")

    def _access_hold(self, op: str, args: dict[str, Any]) -> None:
        """Access on the authoring ops, for every role but owner and author: a write on a thing with access needs its
        w (as a parent too: spawn into it, move into it); chmod and chown need its owner. Access itself changes only
        through chmod and chown, and what such a principal spawns is its own."""
        w = self.world

        def need_w(*refs: Any, any_: bool = False) -> None:
            res = []
            for r in refs:
                if r is None:
                    continue
                eid = self._resolve(r)
                ids = w.subtree_ids(eid) if op == "destroy" else [eid]
                res.append(all(self._access_allows(i, "w") is not False for i in ids))
            if res and not (any(res) if any_ else all(res)):
                raise Rejected("its access keeps that from you (no w)", hint="ask its owner to chmod it, or to chown it to you")

        if op in ("patch", "spawn", "introduce") and acl.KEY in ((args.get("changes") if op == "patch" else args.get("state")) or {}):
            raise Rejected("access changes through chmod and chown", hint=acl.HINT)
        if op in ("chmod", "chown"):
            eid = self._resolve(args["entity"])
            acc = acl.of(w.get(eid)) or {}
            if acc.get("owner"):
                if str(acc["owner"]) not in self._subjects():
                    raise Rejected(f"{w.need(eid)['name'] or eid} is not yours to {op}", hint="its owner, or the world's owner, can")
            elif not (self.limits.get("under") and w.within(eid, self.limits["under"])):
                raise Rejected(f"{w.need(eid)['name'] or eid} has no owner; only the world's owner or author gives it one",
                               hint="a builder may claim what is in its own plot")
            return
        if op in ("patch", "rename", "destroy", "act_as", "say_as", "set_rule", "clear_rule"):
            need_w(args["entity"])
        elif op in ("remember", "intend", "schedule"):
            need_w(args.get("entity"))
        elif op in ("spawn", "introduce"):
            need_w(args["parent"])
            args["state"] = {**(args.get("state") or {}), acl.KEY: {"owner": self.pid, "mode": acl.DEFAULT_MODE}}
        elif op == "move":
            need_w(args["entity"])
            need_w(args["parent"])
        elif op in ("link", "unlink"):
            need_w(args["source"], args["target"], any_=True)
        elif op == "connect":
            need_w(args["a"], args["b"], any_=True)

    def _hold(self, op: str, args: dict[str, Any]) -> None:
        """Canon and limits, before a write runs. Canon: an entity whose state says `canon` is the owner's; no other
        role patches, moves or destroys it, and only the owner sets or lifts the mark. Limits (a grant's `under`,
        `types`, `scripts`): the write lands inside them, and a script it defines carries them in its first line."""
        w = self.world
        ent = args.get("entity") if op in ("patch", "rename", "move", "destroy", "chmod", "chown") else None
        if ent is not None:
            eid = self._resolve(ent)
            hit = [x for x in (w.subtree_ids(eid) if op == "destroy" else [eid]) if (w.get(x) or {}).get("state", {}).get("canon")]
            if hit:
                raise Rejected(f"{w.need(hit[0])['name']} is canon: the owner's to change", hint="build beside it, or ask the owner")
        if "canon" in ((args.get("changes") if op == "patch" else args.get("state") if op in ("spawn", "introduce") else None) or {}):
            raise Rejected("canon is the owner's mark", hint="only the world's owner sets or lifts canon")
        if not self._staff():
            self._access_hold(op, args)
        lim = self.limits
        if not lim:
            return
        under, pre = lim.get("under"), lim.get("scripts") or ""
        where = w.need(under)["name"] if under and w.get(under) else "nowhere"

        def need(*refs: Any, any_: bool = False) -> None:
            # a thing with access is decided by its w (checked in _access_hold); without it, by the plot
            ok = [r is not None and (not under or w.within(self._resolve(r), under)
                                     or bool(self._access_allows(self._resolve(r), "w"))) for r in refs]
            if not (any(ok) if any_ else all(ok)):
                raise Rejected(f"your grant reaches only under {where}", hint=f"work inside it: find(under='{where}')")

        def named(x: Any, what: str) -> None:
            if not str(x).startswith(pre):
                raise Rejected(f"your {what} start with {pre}", hint=f"call it {pre}{x}")

        if op in ("create_world", "fork_world", "save", "restore", "mirror"):
            raise Rejected(f"{op} reaches the whole world; your grant is limited", hint="ask the owner")
        if op == "clock" and any(args.get(k) is not None for k in ("run", "rate", "step", "turn")):
            raise Rejected("the clock is the whole world's; your grant is limited", hint="clock() with no arguments reads it")
        if op == "introduce":
            need(args["parent"], *(args.get("known_by") or {}))
            if not w.may_spawn(args["type"], lim):
                raise Rejected(f"your grant may not make a {args['type']}", hint="a type its limits list, or a schema of yours",
                               alternatives=list(lim.get("types") or []))
        elif op == "spawn":
            need(args["parent"])
            if not w.may_spawn(args["type"], lim):
                raise Rejected(f"your grant may not make a {args['type']}", hint="a type its limits list, or a schema of yours",
                               alternatives=list(lim.get("types") or []))
        elif op in ("patch", "rename", "destroy", "act_as", "say_as"):
            need(args["entity"])
        elif op == "move":
            need(args["entity"], args["parent"])
        elif op in ("link", "unlink"):
            need(args["source"], args["target"], any_=True)
        elif op == "connect":
            need(args["a"], args["b"], any_=True)
        elif op == "layout":
            if args.get("frame") is not None:
                raise Rejected("the frame is the whole world's; your grant is limited", hint="lay out inside your part")
            for p in args.get("placements") or []:
                if isinstance(p, dict) and p.get("entity"):
                    need(p["entity"])
            for p in args.get("paths") or []:
                if isinstance(p, dict) and p.get("a") and p.get("b"):
                    need(p["a"], p["b"], any_=True)
        elif op == "relate":
            need(*args["participants"])
        elif op == "unrelate":
            h = w.store.get("hyperedge", w.id, args["id"])
            if h:
                need(*h["participants"])
        elif op == "schedule":
            need(args.get("entity"))
            named(args["kind"], "event kinds")
        elif op == "unschedule":
            item = [p for p in w.pending() if p["id"] == args["id"]]
            if item:
                need(item[0].get("entity_id"))
        elif op in ("remember", "intend") and args.get("entity"):
            need(args["entity"])
        elif op in ("set_rule", "clear_rule"):
            need(args["entity"])
            named(args["script"], "scripts")
        elif op == "define_script":
            named(args["id"], "scripts")
            src = args["source"]
            if src.startswith(LIMITS_HEAD):
                src = src.split("\n", 1)[1] if "\n" in src else ""
            args["source"] = LIMITS_HEAD + json.dumps(lim, sort_keys=True) + "\n" + src
        elif op == "define_schema":
            named(args["id"], "schemas")
            kw = args.get("kw") or {}
            if kw.get("extends") and not w.may_spawn(kw["extends"], lim):
                raise Rejected(f"your schemas may not extend {kw['extends']}", hint="extend a type your limits list")
            for a in list((kw.get("actions") or {}).values()) + list(kw.get("listeners") or []) + list(kw.get("behaviors") or []):
                if isinstance(a, dict) and "script" in a:
                    named(a["script"], "scripts")

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
             name: str = "", description: str = "") -> dict[str, Any]:
        """Embody an entity. A grant holder may call it bare: the seat the grant names, or the one they held last.
        template=... makes a new character from the world root's `templates` and embodies it; description=... is how
        that newcomer looks to others, set once here (nothing changes it later). Claims are one transaction: two
        agents racing for a seat get one winner and one refusal that lists what is still open."""
        if self.role == OBSERVER_ROLE:
            raise Rejected("observers do not embody", hint="use(world) then perceive(from_entity=...)")
        world_id = world_id or self.world_id
        if not world_id:
            raise Rejected("no world", hint="join(world_id, entity); worlds() lists them")
        description = (description or "").strip()
        if description and not template:
            raise Rejected("a seat keeps the description its world gave it",
                           hint="description= is for someone new: join(template=..., name=..., description=...)")
        if len(description) > _DESCRIPTION_MAX:
            raise Rejected(f"a description is at most {_DESCRIPTION_MAX} characters, not {len(description)}",
                           hint="say what others see in a few lines; keep the backstory in remember()")
        self.engine.world(world_id)
        self.world_id = world_id
        w = self.world
        now = self.engine.wall()
        with self.engine.lock:
            w.store.begin()
            try:
                if template:
                    eid = self._from_template(template, name, description)
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
        mine = self.grant.get("template") if self.grant else None
        if mine:  # an invite that makes one kind of newcomer shows that one
            return {"world": w.id, "seats": [],
                    "templates": [{"template": mine, "type": templates.get(mine, {}).get("type"),
                                   "place": templates.get(mine, {}).get("place"), "doc": templates.get(mine, {}).get("doc", "")}],
                    "hint": f"your invite makes a {mine}: ask the human for a name, then join(template='{mine}', name=...); "
                            "description=... (how they look to others) may be set then, and only then"}
        return {"world": w.id, "seats": self._seat_rows(self.engine.wall()),
                "templates": [{"template": k, "type": t.get("type"), "place": t.get("place"), "doc": t.get("doc", "")}
                              for k, t in templates.items()],
                "hint": "join(world, entity) takes an open seat; join(world, template=..., name=..., description=...) makes "
                        "someone new, and the description (how they look to others) is set then or never"}

    def _from_template(self, template: str, name: str, description: str = "") -> str:
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
        if description:  # the newcomer's own word on how they look, over the template's
            state["description"] = description
        parent = self._resolve(t["place"]) if t.get("place") else w.root_id
        eid = w.spawn(t.get("type", "creature"), parent, name=name, state=state)
        for item in t.get("kit") or []:  # what a newcomer of this kind carries in: a skin, a blade, whatever the world says
            w.spawn(item.get("type", "thing"), eid, name=item["name"], state=dict(item.get("state") or {}))
        return eid

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
               "a refusal says why and what would work; do not retry the same call",
               "tell the human what happens as a story, in prose, in the fiction: no bullets, no stat sheets, no tool names"]
        if self.role == PLAYER:
            how.insert(0, "this briefing is for you, not for them: say nothing of seats, grants, tokens or tools; open in the "
                          "world, with where they stand, who is near and what the body feels, then ask what they do")
            how.append("keep the character's notes on the server: remember(text) and intend(text); recall() reads them back, "
                       "next session or another machine (your own memory of your human stays yours)")
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
               scope: list[str] | None = None, brief: str = "", limits: dict[str, Any] | None = None) -> dict[str, Any]:
        """(owner) A grant that travels as a token. role: author, builder, narrator, player, mind or observer. entity: the
        seat kept for this invite (player) or the NPC it holds (mind; scope=[...] for more). template: the character
        it may make. expires: hours. brief: the host's word to this guest alone (their orders, their first goal); it
        rides the page and the briefing join() returns. limits (builder, narrator, author): under=<entity>, the part
        of the world it may change; types=[...], what it may spawn; scripts=<prefix>, how its scripts and schemas are
        named (default: from the principal). A builder needs under. Returns the token once, the link whose page carries it (good
        once, for a day) and the paste: the link with a line for the friend. Without a public URL the paste is the page."""
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
        lim, note = self._limits_for(role, limits, pid)
        token = new_token()
        now = self.engine.wall()
        url = self.engine.url_now() or ""
        code = new_code()
        link = link_for(url, code)
        ck = w.clock()
        names = [w.get(x)["name"] for x in sc if w.get(x)]
        waits = bool(w.meta().get("run_when_occupied"))
        tdoc = ((w.get(w.root_id)["state"].get("templates") or {}).get(template) or {}).get("doc", "") if template else ""
        stored = page(w.name, role, f"{HOST_MARK}/mcp" if link else url, token, seat=(w.get(eid)["name"] if eid and role != MIND else None),
                    scope_names=names, rate=ck["rate"] if ck["running"] or waits else 0.0, waits=waits,
                    briefing=(f"From the host, for you alone: {brief}" if brief else ""), template=template,
                    template_doc=tdoc, limits_note=note)
        text = stored.replace(HOST_MARK, url.removesuffix("/mcp"))
        exp = (now + float(expires) * 3600.0) if expires else None
        code_exp = min(now + LINK_HOURS * 3600.0, exp) if exp else now + LINK_HOURS * 3600.0
        row = {"world_id": w.id, "id": "g" + secrets.token_hex(4), "principal_id": pid, "role": role, "scope": sc,
               "entity_id": eid, "template": template, "label": label, "token_hash": token_hash(token),
               "created": now, "expires": exp, "revoked": 0, "last_used": None, "brief": brief or None,
               "code_hash": token_hash(code) if link else None, "code_expires": code_exp if link else None,
               "page": stored if link else None, "limits": lim}
        w.store.put("grants", row)
        return {"ok": True, "id": row["id"], "principal": pid, "role": role, "entity": eid, "scope": sc, "limits": lim,
                "template": template, "expires": row["expires"], "token": token, "url": url or None,
                "link": link, "link_expires": row["code_expires"], "paste": paste(w.name, role, link, text, label=label),
                "page": text,
                "hint": ("send them the paste: the link works once and for a day" if link else
                         "no public URL, so no link: send them the paste whole") + "; grants() lists grants without the token"}

    def _limits_for(self, role: str, limits: dict[str, Any] | None, pid: str) -> tuple[dict[str, Any] | None, str]:
        """Check an invite's limits and say them in a line for its page."""
        if not limits and role != BUILDER:
            return None, ""
        w = self.world
        lim = dict(limits or {})
        bad = sorted(set(lim) - {"under", "types", "scripts"})
        if bad:
            raise Rejected(f"limits know under, types and scripts, not {bad}",
                           hint="limits={'under': 'The Market Row', 'types': ['thing'], 'scripts': 'mara_'}")
        if role not in (AUTHOR_ROLE, BUILDER, NARRATOR_ROLE):
            raise Rejected(f"limits narrow a role that writes (builder, narrator, author), not a {role}",
                           hint="a player or a mind is already held to its seat")
        if role == BUILDER and not lim.get("under"):
            raise Rejected("a builder builds under something", hint="limits={'under': 'The Market Row'}")
        if lim.get("under"):
            lim["under"] = self._resolve(lim["under"])
        if lim.get("types") is not None:
            lim["types"] = [w.schema(t)["id"] for t in lim["types"]]
        pre = lim.get("scripts") or (pid.replace("-", "_") + "_")
        if not (isinstance(pre, str) and pre[:1].isalpha() and pre.replace("_", "").isalnum() and pre.islower()):
            raise Rejected(f"a script prefix is lower-case letters, digits and _, not {pre!r}", hint="scripts='mara_'")
        for g in w.store.query("grants", "world_id=? AND revoked=0", (w.id,)):
            other = (g.get("limits") or {}).get("scripts")
            if other and active(g, self.engine.wall()) and (other.startswith(pre) or pre.startswith(other)):
                raise Rejected(f"the prefix {pre!r} overlaps {other!r}, grant {g['id']}'s", hint="another scripts= prefix")
        lim["scripts"] = pre
        where = w.need(lim["under"])["name"] if lim.get("under") else "the whole world"
        note = (f"   Your hand reaches {('under ' + where) if lim.get('under') else where} and what it holds; the rest you "
                f"may read. You may spawn {', '.join(lim['types']) if lim.get('types') is not None else 'any type'}"
                f" and the schemas you define. Your scripts, schemas and event kinds start with {pre}, and they keep "
                f"your limits when they run. What the owner marked canon stays as it is.")
        return lim, note

    def requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """(owner) Seat requests left on the world's page (/seat-request), newest first: who, how to reach them, which
        side draws them, why. Kept beside the database, never in the world's log."""
        from .site import read_requests
        self._tick()
        return read_requests(self.engine.requests_path, self.world.id, limit=max(1, min(int(limit), 500)))

    def grants(self) -> list[dict[str, Any]]:
        """(owner) Every grant on this world, without the tokens."""
        self._tick()
        w = self.world
        now = self.engine.wall()
        out = []
        for g in w.store.query("grants", "world_id=?", (w.id,), order="created"):
            p = w.principal(g["principal_id"])
            out.append({k: v for k, v in g.items() if k not in ("token_hash", "world_id", "code_hash", "page")}
                       | {"active": active(g, now), "in_world": p is not None, "link_unread": bool(g.get("code_hash")),
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

    def _resolve_for(self, me: str, ref: str, verb: str, params: dict[str, Any] | None) -> str:
        """A target for a deed: an id, a unique name, or, when several share the name (stacks of Emberglass, two
        waterskins), the one in your reach that the verb would take, else the first in your reach, so its refusal
        says why. Names alone stay ambiguous only when none of them is near you."""
        w = self.world
        if w.get(ref):
            return ref
        hits = [e for e in w.find(name=ref, limit=200) if e["name"].lower() == ref.lower()]
        if len(hits) <= 1:
            return self._resolve(ref)
        near = [h["id"] for h in hits if w.reachable(me, h["id"])[0]]
        if not near:
            return self._resolve(ref)
        for eid in near:
            if w.check_action(me, verb, eid, params)[0]:
                return eid
        return near[0]

    # ---- perception --------------------------------------------------------------

    def perceive(self, cursor: int | None = None, from_entity: str | None = None, events: int = 30,
                 layout: bool = False) -> dict[str, Any]:
        self._tick()
        w = self.world
        if from_entity is not None:
            if not self._privileged():
                raise Rejected("perceiving from another entity needs the author, narrator or observer role")
            me = self._resolve(from_entity)
            if not self._sees(me):
                raise Rejected("your grant reads only its own part of the world", hint="perceive from someone under it")
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
            "reclaim": w.reclaimable(me),
            "events": self._events_for(me, w.events(since=cursor, touching=me, limit=events)),
            "cursor": w.store.next_seq(w.id) - 1,
        }
        if layout:
            bundle["layout"] = self._layout_view(me, bundle)
        if p is not None:
            w.set_cursor(self.pid, bundle["cursor"])
        else:
            w.set_entity_cursor(me, bundle["cursor"])
        return bundle

    # ---- layout: one frame over the tree (DESIGN.md section 8, Layout; geometry in layout.py) --------------------------

    def _frame(self) -> dict[str, Any] | None:
        root = self.world.get(self.world.root_id)
        return (root["state"].get("frame") if root else None) or None

    def _own_layout(self, eid: str) -> dict[str, Any]:
        e = self.world.get(eid)
        return dict((e["state"].get("layout") if e else None) or {})

    def _world_at(self, eid: str, depth: int = 0) -> list[float] | None:
        """Where an entity is in the world frame: its own `at`; else its grid position mapped through its container's
        space (`frame_origin`, `cell`, `heading`); else wherever its container is."""
        w = self.world
        e = w.get(eid)
        if e is None or depth > 64:
            return None
        own = (e["state"].get("layout") or {}).get("at")
        if own:
            return list(own)
        parent = e["parent_id"]
        if not parent:
            return None
        sp = w.space_of(parent) or {}
        if e["pos"] is not None and sp.get("frame_origin") is not None:
            o = list(sp["frame_origin"]) + [0.0] * (3 - len(sp["frame_origin"]))
            cell = float(sp.get("cell") or 1.0)
            h = math.radians(float(sp.get("heading") or 0.0))
            p = [float(x) * cell for x in e["pos"]] + [0.0] * (3 - len(e["pos"]))
            return [o[0] + p[0] * math.cos(h) + p[1] * math.sin(h),
                    o[1] - p[0] * math.sin(h) + p[1] * math.cos(h), o[2] + p[2]]
        return self._world_at(parent, depth + 1)

    def _path_rows(self, ids: set[str]) -> list[dict[str, Any]]:
        """The connects_to paths between the given places, one row a pair: the drawn route (or the straight line when
        none is laid), its length, and the bearing from one end to the other."""
        w = self.world
        out, seen = [], set()
        for a in ids:
            for e in w.edges(a, "connects_to", "out"):
                b = e["target"]
                if b not in ids or (b, a) in seen:
                    continue
                seen.add((a, b))
                pa, pb = self._world_at(a), self._world_at(b)
                route = e["data"].get("route")
                if not route and pa and pb:
                    route = [pa, pb]
                row: dict[str, Any] = {"a": a, "b": b, "a_name": w.get(a)["name"], "b_name": w.get(b)["name"],
                                       "drawn": bool(e["data"].get("route"))}
                if route:
                    row["route"] = [list(p) for p in route]
                    row["length"] = round(float(e["data"].get("length") or geo.route_length([list(p) for p in route])), 1)
                if pa and pb:
                    row["bearing"] = geo.bearing(pa, pb)
                out.append(row)
        return out

    def _layout_warnings(self, ids: list[str]) -> list[str]:
        """What looks wrong, never a refusal: a thing outside the place it is in, a path whose drawn ends sit far from
        the places it joins or whose stated length is shorter than the straight line, an extent outside the frame."""
        w = self.world
        out = []
        frame = self._frame() or {}
        bounds = frame.get("bounds")
        for eid in ids:
            e = w.get(eid)
            if e is None:
                continue
            lay = self._own_layout(eid)
            at = lay.get("at")
            parent = e["parent_id"]
            if at and parent and not w.is_a(e["type"], "place"):
                pl = self._own_layout(parent)
                if pl.get("at") and geo.contains(pl, at) is False:
                    out.append(f"{e['name']} stands outside {w.get(parent)['name']}, the place it is in "
                               f"({geo.edge_distance(pl, at):.0f} {frame.get('units', 'm')} beyond its edge)")
            if at and bounds and not all(bounds[0][i] <= at[i] <= bounds[1][i] for i in range(2)):
                out.append(f"{e['name']} is outside the frame's bounds")
            if w.is_a(e["type"], "place"):
                for ed in w.edges(eid, "connects_to", "out"):
                    other, route = ed["target"], ed["data"].get("route")
                    ol = self._own_layout(other)
                    if route and lay.get("at") and ol.get("at"):
                        gap_a = geo.edge_distance(lay, route[0]) if lay.get("radius") or lay.get("size") or lay.get("footprint") else geo.ground(lay["at"], route[0])
                        gap_b = geo.edge_distance(ol, route[-1]) if ol.get("radius") or ol.get("size") or ol.get("footprint") else geo.ground(ol["at"], route[-1])
                        if (gap_a or 0) > 50 or (gap_b or 0) > 50:
                            out.append(f"the path from {e['name']} to {w.get(other)['name']} is drawn starting or ending away from them")
                    length = ed["data"].get("length")
                    if length and lay.get("at") and ol.get("at") and float(length) + 1 < geo.ground(lay["at"], ol["at"]) - \
                            (lay.get("radius") or 0) - (ol.get("radius") or 0):
                        out.append(f"the path from {e['name']} to {w.get(other)['name']} is said to be {length} long, "
                                   f"shorter than the straight line between them")
        return sorted(set(out))

    def _layout_view(self, me: str, bundle: dict[str, Any]) -> dict[str, Any]:
        """perceive(layout=true): where you stand, and the distance and bearing to what you see here and to each exit."""
        w = self.world
        mine = self._world_at(me)
        here = w.need(me)["parent_id"]
        hl = self._own_layout(here) if here else {}
        out: dict[str, Any] = {"frame": self._frame() or dict(geo.DEFAULT_FRAME), "you": mine,
                               "here": {k: v for k, v in hl.items() if k != "note"} or None}
        if mine is None:
            out["note"] = "nothing here is laid out yet"
            return out

        def rel(eid: str) -> dict[str, Any] | None:
            at = self._world_at(eid)
            if at is None:
                return None
            b = geo.bearing(mine, at)
            return {"at": [round(x, 1) for x in at], "distance": round(geo.ground(mine, at), 1), "bearing": b[1],
                    "degrees": b[0], "dz": round(at[2] - mine[2], 1)}

        out["present"] = [{"id": c["id"], "name": c["name"], **r} for c in bundle["present"]
                          if (r := rel(c["id"])) and self._own_layout(c["id"]).get("at")]
        exits = []
        for x in bundle["exits"]:
            r = rel(x["to"])
            if r is None:
                continue
            row = {"to": x["to"], "name": x["name"], "bearing": r["bearing"], "degrees": r["degrees"],
                   "straight": r["distance"]}
            ed = next((e for e in w.edges(here, "connects_to", "out") if e["target"] == x["to"]), None) if here else None
            if ed and (ed["data"].get("length") or ed["data"].get("route")):
                row["length"] = round(float(ed["data"].get("length") or geo.route_length(ed["data"]["route"])), 1)
            exits.append(row)
        out["exits"] = exits
        return out

    def layout(self, placements: list[dict[str, Any]] | None = None, paths: list[dict[str, Any]] | None = None,
               frame: dict[str, Any] | None = None, replace: bool = False) -> dict[str, Any]:
        """Lay out many entities at once in the world's one frame: placements [{entity, at, heading, radius | size |
        footprint, floor, ceiling, mesh, note}], paths [{a, b, route, length}] on the connects_to edges between places,
        and the root's frame. Keys merge over what is there (None deletes one; replace=true sets each layout whole).
        Every shape is checked; what only looks wrong comes back as warnings."""
        self._need(AUTHOR)
        w = self.world
        self._record("layout", placements=placements, paths=paths, frame=frame, replace=replace or None)
        touched: list[str] = []
        if frame is not None:
            w.patch(w.root_id, {"frame": geo.check_frame(frame)}, actor=self._actor_or_none(), replace=True)
        if not self._frame() and (placements or paths):
            w.patch(w.root_id, {"frame": dict(geo.DEFAULT_FRAME)}, actor=self._actor_or_none(), replace=True)
        checked = []
        for p in placements or []:
            if not isinstance(p, dict) or not p.get("entity"):
                raise Rejected("each placement names its entity", hint='{"entity": "The Hold", "at": [0, 0, 0], "radius": 40}')
            eid = self._resolve(p["entity"])
            new = {k: v for k, v in p.items() if k != "entity"}
            checked.append((eid, geo.merge(self._own_layout(eid), new, replace=replace)))
        for eid, lay in checked:
            w.patch(eid, {"layout": lay}, actor=self._actor_or_none(), replace=True)
            touched.append(eid)
        for pth in paths or []:
            if not isinstance(pth, dict) or not pth.get("a") or not pth.get("b"):
                raise Rejected("each path names its two places", hint='{"a": "The Hold", "b": "The Gate Yard", "route": [[0, 0], [0, 60]]}')
            a, b = self._resolve(pth["a"]), self._resolve(pth["b"])
            if not any(e["target"] == b for e in w.edges(a, "connects_to", "out")):
                raise Rejected(f"{w.need(a)['name']} and {w.need(b)['name']} are not connected",
                               hint="a path is drawn on a connects_to edge: connect(a, b) first")
            data: dict[str, Any] = {}
            if pth.get("route") is not None:
                route = [geo._vec(q, "route point", 2, 3) for q in pth["route"]]
                if len(route) < 2:
                    raise Rejected("a route is two or more points")
                data["route"] = [q if len(q) == 3 else q + [0.0] for q in route]
            if pth.get("length") is not None:
                length = geo._num(pth["length"], "length")
                if length <= 0:
                    raise Rejected("length must be above zero")
                data["length"] = length
            fwd = dict(data)
            back = dict(data)
            if "route" in back:
                back["route"] = list(reversed(back["route"]))
            w.link(a, b, "connects_to", fwd)
            w.link(b, a, "connects_to", back)
            touched.extend([a, b])
        if touched:
            w.emit("laid_out", actor=self._actor_or_none(), target=w.root_id, reach=0,
                   payload={"entities": sorted(set(touched))})
        return {"ok": True, "laid_out": len(checked), "paths": len(paths or []), "frame": self._frame(),
                "warnings": self._layout_warnings(sorted(set(touched)))}

    def map(self, under: str | None = None, depth: int = 1, sketch: bool = True, width: int = 64) -> dict[str, Any]:
        """The layout of a subtree: the frame, every entity under `under` (default the root) to `depth` levels with its
        position (its own, or inherited from its container) and extent, the paths between the places, what is not
        laid out yet, warnings, and a top-down text sketch (north up). Read it level by level as you lay a world out."""
        self._tick()
        w = self.world
        top = self._resolve(under) if under else w.root_id
        depth = max(1, min(int(depth), 6))
        rows, frontier = [], [(top, 0)]
        while frontier and len(rows) < 300:
            eid, d = frontier.pop(0)
            for c in w.children(eid):
                rows.append((c, d + 1))
                if d + 1 < depth:
                    frontier.append((c["id"], d + 1))
        items, unplaced = [], []
        for c, d in rows:
            lay = self._own_layout(c["id"])
            at = self._world_at(c["id"])
            row = {"id": c["id"], "name": c["name"], "type": c["type"], "parent": c["parent_id"], "level": d,
                   "own": bool(lay.get("at")), "at": [round(x, 1) for x in at] if at else None}
            if lay:
                row["layout"] = lay
                if geo.area(lay):
                    row["area"] = round(geo.area(lay), 1)
            if c["state"].get("hidden"):
                row["hidden"] = True
            items.append(row)
            if not lay.get("at") and w.is_a(c["type"], "place"):
                unplaced.append(c["name"])
        places = {r["id"] for r in items if w.is_a(r["type"], "place")}
        tl = self._own_layout(top)
        out: dict[str, Any] = {"frame": self._frame(), "under": {"id": top, "name": w.need(top)["name"],
                               "layout": tl or None}, "entities": items, "paths": self._path_rows(places),
                               "not_laid_out": unplaced, "warnings": self._layout_warnings([r["id"] for r in items])}
        if sketch:
            drawn = [{"name": r["name"], "at": r["at"], "layout": r.get("layout")} for r in items if r["own"]]
            if tl.get("at"):
                drawn.insert(0, {"name": w.need(top)["name"], "at": tl["at"], "layout": tl})
            out["sketch"] = geo.sketch(drawn, [p for p in out["paths"] if p.get("route")], width=max(24, min(int(width), 120)))
        return out

    def measure(self, a: str, b: str | None = None, point: list[float] | None = None) -> dict[str, Any]:
        """The ruler. One entity: where it is, its extent, area, floor and ceiling. With b (another entity) or point
        (x, y, z): distance on the ground and in 3D, compass bearing, height difference, the gap from a's edge, and
        whether either contains the other or their extents overlap."""
        self._tick()
        w = self.world
        ea = self._resolve(a)
        la = self._own_layout(ea)
        pa = self._world_at(ea)
        if pa is None:
            raise Rejected(f"{w.need(ea)['name']} is not laid out, nor is anything it is in", hint="layout(placements=[...]) first")
        out: dict[str, Any] = {"a": {"id": ea, "name": w.need(ea)["name"], "at": pa, "own": bool(la.get("at"))}}
        if la.get("at"):
            out["a"].update({k: v for k, v in la.items() if k in ("radius", "size", "footprint", "heading", "floor", "ceiling")})
            if geo.area(la):
                out["a"]["area"] = round(geo.area(la), 1)
            if geo.z_range(la):
                out["a"]["z_range"] = list(geo.z_range(la))
        if b is None and point is None:
            return out
        if b is not None:
            eb = self._resolve(b)
            lb = self._own_layout(eb)
            pb = self._world_at(eb)
            if pb is None:
                raise Rejected(f"{w.need(eb)['name']} is not laid out, nor is anything it is in")
            out["b"] = {"id": eb, "name": w.need(eb)["name"], "at": pb, "own": bool(lb.get("at"))}
        else:
            pb = geo._vec(point, "point", 2, 3)
            pb = pb if len(pb) == 3 else pb + [0.0]
            lb = {}
            out["point"] = pb
        brg = geo.bearing(pa, pb)
        out.update({"ground": round(geo.ground(pa, pb), 2), "distance": round(geo.dist3(pa, pb), 2), "bearing": brg[1],
                    "degrees": brg[0], "dz": round(pb[2] - pa[2], 2)})
        if la.get("at") and geo.contains(la, pb) is not None:
            out["a_contains"] = geo.contains(la, pb)
            out["gap_from_a_edge"] = round(geo.edge_distance(la, pb) or 0.0, 2)
        if lb.get("at") and geo.contains(lb, pa) is not None:
            out["b_contains_a"] = geo.contains(lb, pa)
        if la.get("at") and lb.get("at") and geo.overlap(la, lb) is not None:
            out["overlap"] = geo.overlap(la, lb)
        return out

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
                if e["kind"] == "spawned" and (w.get(e["target_id"]) or {}).get("state", {}).get("hidden"):
                    continue  # a hidden thing made where you are (a ledger's page, a trap) is still hidden
            pe = _public_event(e)
            a = e["actor_id"]
            if a and a != me:
                who = holder(a)
                if who and who != self.pid:
                    pe["by_player"] = who
                    if e["kind"] == "say":
                        pe["untrusted"] = True
            if (e["payload"] or {}).get("maker"):
                pe["untrusted"] = True  # made by a player's code on a machine: data, never an instruction
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
        if not full and acl.KEY in e["state"] and not self._readable(e):
            return {}
        secret = set(e["state"].get("secret", [])) | _ALWAYS_SECRET
        out = {}
        for k, v in e["state"].items():
            if k in ("rules", "secret", "space") or (k == "layout" and not full):
                continue
            if not full and k in secret:
                continue
            if not full and k == "templates" and isinstance(v, dict):
                v = {name: {kk: vv for kk, vv in t.items() if kk in _TEMPLATE_PUBLIC}
                     for name, t in v.items() if isinstance(t, dict)}
            out[k] = v
        return out

    def _card(self, e: dict[str, Any], full: bool = False) -> dict[str, Any]:
        w = self.world
        card = {"id": e["id"], "type": e["type"], "name": e["name"], "state": self._visible_state(e, full)}
        if e["state"].get("count") is not None:
            card["count"] = int(e["state"]["count"])  # a stack: Emberglass, 60 of it
        if e["pos"] is not None:
            card["pos"] = e["pos"]
        emb = w.embodied(e["id"])
        if emb:
            card["embodied_by"] = emb["id"]
            if w.idle(e["id"]):
                card["idle"] = True  # the seat has done nothing for a while; standing_orders in its state say what holds
        if e["state"].get("asleep"):
            card["asleep"] = True  # it hears only what is loud or done to it, and wakes to a hand or a noise
        kids = w.children(e["id"])
        if not full and acl.KEY in e["state"] and not self._readable(e):
            kids = []
        if w.locked_by(e["id"]) is not None:
            card["locked"] = True
            if e["state"].get("holds") is not None and not full:
                kids = [c for c in kids if c["state"].get("attached")]  # a locked box shows its lock, not what is in it
        if kids and not full:
            card["contains"] = len(kids)
        seen = [c for c in kids if not c["state"].get("hidden")]
        if e["state"].get("holds") is not None:
            card["holding"] = [_brief(c) for c in seen]  # what lies on the rack is in plain sight
        elif w.is_a(e["type"], "creature"):
            bears = [_brief(c) for c in seen if c["state"].get("weapon")]
            if bears:
                card["bears"] = bears  # a blade at the hip shows, whatever the description still says
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
                if not x["locked"] and w.locked_by(via):
                    x["locked"] = True
            if w.locked_by(e["target"]):
                x["locked"] = True  # a lock on the place itself shuts the way in
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
        priv = self._privileged()
        full = priv and self._sees(eid)  # a limited grant reads its own plot in full, the rest as anyone would
        me = None
        if not priv:
            me = self._me()
            ok, why = w.reachable(me, eid)
            if not ok and eid not in w.ancestors(me):
                raise Rejected(why, hint="inspect works on what perceive shows")
        card = self._card(e, full=full)
        card["parent"] = e["parent_id"]
        card["schema_chain"] = [s["id"] for s in w.schema_chain(e["type"])]
        card["doc"] = w.schema(e["type"])["doc"]
        card["contents"] = [self._card(c) for c in w.children(eid) if full or not c["state"].get("hidden")]
        if not full and not self._readable(e):
            card["contents"] = []  # its access keeps r from you: what it is, not what is in it
        rels = self._relations(eid)
        own = full or eid == me or eid in self.scope
        if not own:
            # whom someone knows, what they think of them and what passed between them is theirs: another body sees
            # the groups held in the open or that it is part of, and whether it has met them
            rels = [r for r in rels if _seen_relation(r, me)]
            if me:
                card["met"] = any(x["target"] == eid for x in w.edges(me, "knows", "out"))
        card["relations"] = rels
        card["actions"] = {v: {"doc": a.get("doc", ""), "targets": a.get("targets"), "params": a.get("params", {})}
                           for v, a in w.schema_actions(e["type"]).items() if full or not a.get("hidden")}
        for v, a in own_verbs(e).items():  # verbs put on this one thing
            if isinstance(a, dict) and v not in card["actions"] and (full or not a.get("pending")):
                card["actions"][v] = {"doc": a.get("doc", ""), "targets": None, "params": a.get("params") or {},
                                      "programmed": True, **({"pending": True} if a.get("pending") else {})}
        if full:
            card["rules"] = e["state"].get("rules", [])
            card["version"] = e["version"]
        if own:
            card["knows"] = self._knows(eid)
        return card

    def find(self, type: str | None = None, name: str | None = None, under: str | None = None,
             parent: str | None = None, state: dict[str, Any] | None = None, limit: int = 30,
             offset: int = 0) -> list[dict[str, Any]]:
        """One page of matches, oldest first: at most FIND_PAGE. A full page may have more after it: ask again with
        offset moved on by the page. A limit past the page is refused, never cut short in silence."""
        if limit > FIND_PAGE or limit < 1 or offset < 0:
            raise Rejected(f"find returns 1 to {FIND_PAGE} a page (asked for limit={limit}, offset={offset})",
                           hint=f"find(..., limit={FIND_PAGE}, offset={max(0, offset)}), then offset={max(0, offset) + FIND_PAGE} "
                                "for the next page while a page comes back full; or narrow it with type=, name=, under=, "
                                "parent= or state=")
        self._tick()
        w = self.world
        if not self._privileged():
            # an embodied principal searches what it can see: its place and its holdings
            me = self._me()
            scope = w.need(me)["parent_id"] or me
            under = under or scope
        rows = w.find(type=type, name=name, under=self._resolve(under) if under else None,
                      parent=self._resolve(parent) if parent else None, state=state, limit=None)
        plot = self._plot()
        rows = [r for r in rows if not r["state"].get("hidden") or (self._privileged() and self._sees(r["id"], plot))]
        return [self._card(r) for r in rows[offset:offset + limit]]

    def history(self, since: int = 0, until: int | None = None, kinds: list[str] | None = None,
                touching: str | None = None, limit: int = 50, newest: bool = False) -> list[dict[str, Any]]:
        """The event log, oldest first, `limit` events after `since` (`newest`: the last `limit`). The kinds the
        engine keeps to itself (ticks, before_act, definitions) never count against the limit."""
        self._tick()
        w = self.world
        if AUTHOR not in self.capabilities and OBSERVER not in self.capabilities:
            touching = self._me()
        elif touching:
            touching = self._resolve(touching)
        me = touching if not self._privileged() else None
        return self._events_for(me, w.events(since=since, until=until, kinds=kinds, touching=touching,
                                             limit=max(1, min(int(limit), 500)), skip=_INTERNAL_KINDS, newest=newest))

    # ---- the chronicle --------------------------------------------------------------------------------------------

    def _day_seconds(self) -> float:
        return float(self.world.meta().get("day_seconds") or 86400)

    def _published(self, day: int | None = None) -> dict[int, dict[str, Any]]:
        """The chronicle as published: the last `chronicled` event of each day, withdrawn days left out."""
        w = self.world
        out: dict[int, dict[str, Any]] = {}
        for r in w.store.query("event", "world_id=? AND kind='chronicled'", (w.id,), order="seq"):
            p = r["payload"] or {}
            d = int(p.get("day") or 0)
            if day is not None and d != day:
                continue
            if p.get("text"):
                out[d] = {"day": d, "title": p.get("title"), "text": p["text"], "seq": r["seq"], "t": round(float(r["t"]))}
            else:
                out.pop(d, None)
        return out

    def chronicle(self, day: int | None = None, limit: int = 200) -> dict[str, Any]:
        """(owner, author) One world day of the log, sorted for whoever writes it up: what changed (`news`: people
        and places new to the world, fights, finds, downs and deaths, gifts and trades across sides, standing,
        the story's own state), the world's own prose (`scenes`), what was said (`said`), what happened (`beats`),
        who went where (`travel`), what repeats every day (`routine`, counted), counts by kind, and what is
        already published for that day. Built from the log, nothing invented. The day defaults to the current one;
        `day_seconds` in the world's meta sets its length (86400). Routine is a scene text the day before also
        had (or one already told today), an actorless beat of a kind the day before also had, the bodies' upkeep
        and the deeds themselves (`act`, whose results are the beats), and the kinds the meta lists as
        `chronicle_routine`. Notes and intents stay their owners'."""
        self._need(AUTHOR)
        self._tick()
        w = self.world
        D = self._day_seconds()
        today = int(w.t // D) + 1
        day = today if day is None else int(day)
        if not 1 <= day <= today:
            raise Rejected(f"day {day} is not in this world's past (it is day {today})", hint=f"chronicle(day=1..{today})")
        lo, hi = (day - 1) * D, day * D
        limit = max(1, min(int(limit), 1000))
        rows = w.store.query("event", "world_id=? AND t>=? AND t<?", (w.id, lo, hi), order="seq")
        skip = _INTERNAL_KINDS | _PRIVATE_KINDS | _CHRONICLE_QUIET
        meta = w.meta()
        routine_kinds = _CHRONICLE_ROUTINE | {str(k) for k in (meta.get("chronicle_routine") or [])}
        # what the day before had: the same scene again, or the same world-driven beat, is routine, not news
        told_before: set[str] = set()
        actorless_before: set[str] = set()
        for r in w.store.query("event", "world_id=? AND t>=? AND t<?", (w.id, lo - D, lo), order="seq"):
            if r["kind"] == "scene" and (r["payload"] or {}).get("text"):
                told_before.add(str(r["payload"]["text"]))
            elif not r["actor_id"]:
                actorless_before.add(r["kind"])
        routine: dict[str, int] = {}

        def routinely(k: str) -> None:
            routine[k] = routine.get(k, 0) + 1
        names: dict[str, str] = {}

        def name(eid: str | None) -> str | None:
            if not eid:
                return None
            if eid not in names:
                e = w.get(eid)
                names[eid] = (e["name"] or e["type"]) if e else eid
            return names[eid]

        def place(r: dict[str, Any]) -> str | None:
            for eid in r.get("path") or []:
                e = w.get(eid)
                if e is not None and w.is_a(e["type"], "place"):
                    return name(eid)
            return None

        held: dict[str, str | None] = {}

        def seat(eid: str | None) -> str | None:
            """Who holds a body now: player, mind or nobody (None). A role, never a label."""
            if not eid:
                return None
            if eid not in held:
                p = w.embodied(eid)
                g = w.store.query("grants", "world_id=? AND principal_id=? AND revoked=0", (w.id, p["id"]), limit=1) if p else []
                held[eid] = (g[0]["role"] if g else "host") if p else None
            return held[eid]

        def detail(p: dict[str, Any]) -> dict[str, Any]:
            out = {}
            for k, v in (p or {}).items():
                if isinstance(v, str):
                    out[k] = v if len(v) <= 160 else v[:157] + "..."
                elif isinstance(v, (int, float, bool)) or v is None:
                    out[k] = v
                elif isinstance(v, list) and len(v) <= 6 and all(isinstance(x, (str, int, float)) for x in v):
                    out[k] = [name(x) if isinstance(x, str) and w.get(x) else x for x in v]
            return out

        counts: dict[str, int] = {}
        scenes, said, beats = [], [], []
        travel: dict[str, list[str]] = {}
        people: set[str] = set()
        told_today: set[str] = set()
        for r in rows:
            k = r["kind"]
            if k in _INTERNAL_KINDS or k in _PRIVATE_KINDS:
                continue
            counts[k] = counts.get(k, 0) + 1
            t = round(float(r["t"]) - lo)
            p = r["payload"] or {}
            if k == "scene" and p.get("text"):
                if p["text"] in told_before or p["text"] in told_today:
                    routinely("scene")
                    continue
                told_today.add(p["text"])
                scenes.append({"t": t, "place": place(r), "text": p["text"]})
            elif k == "say" and p.get("text"):
                who = r["actor_id"]
                people.add(who) if who else None
                row = {"t": t, "who": name(who), "place": place(r), "text": p["text"]}
                if p.get("to"):
                    row["to"] = name(p["to"])
                if seat(who) == "player":
                    row["player"] = True
                said.append(row)
            elif k == "moved" and r["actor_id"] == r["target_id"] and p.get("to") and p.get("from") != p.get("to"):
                route = travel.setdefault(name(r["target_id"]), [name(p.get("from"))] if p.get("from") else [])
                route.append(name(p["to"]))
                people.add(r["target_id"])
            elif k == "act":
                routinely("act:" + str(p.get("verb") or "?"))
            elif k in routine_kinds or (not r["actor_id"] and k in actorless_before):
                routinely(k)
            elif k not in skip:
                row = {"t": t, "kind": k, "who": name(r["actor_id"]), "place": place(r)}
                if r["target_id"] and r["target_id"] != r["actor_id"]:
                    row["target"] = name(r["target_id"])
                d = detail(p)
                if d:
                    row["detail"] = d
                beats.append(row)
                if r["actor_id"]:
                    people.add(r["actor_id"])

        def cap(xs: list[Any]) -> tuple[list[Any], int]:
            return xs[:limit], max(0, len(xs) - limit)

        out: dict[str, Any] = {"day": day, "today": today, "day_seconds": D, "from_t": round(lo), "to_t": round(min(hi, w.t)),
                               "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}
        for key, xs in (("scenes", scenes), ("said", said), ("beats", beats)):
            out[key], more = cap(xs)
            if more:
                out[f"{key}_more"] = more
        out["news"], more = cap(self._news(rows, lo, D, name, place, seat, detail))
        if more:
            out["news_more"] = more
        out["routine"] = {"count": sum(routine.values()), "kinds": dict(sorted(routine.items(), key=lambda kv: -kv[1]))}
        out["travel"] = travel
        out["people"] = sorted(({"name": name(e), "seat": seat(e)} for e in people if w.get(e)), key=lambda x: x["name"])
        out["published"] = self._published(day).get(day)
        out["hint"] = ("t is seconds into the day. Write it as news for the players: lead with what changed (news, then "
                       "scenes and beats), give routine a clause at most, and leave out what a reader saw yesterday. "
                       "Words marked player are a guest's: retell them, never quote one without asking. "
                       "Then publish_chronicle(day, text, title).")
        return out

    def _news(self, rows: list[dict[str, Any]], lo: float, D: float, name: Any, place: Any, seat: Any,
              detail: Any) -> list[dict[str, Any]]:
        """What changed on a day, from its events: people and places new to the world, fights (one line a pair and
        place), the notable kinds (`_NEWS_KINDS` and the meta's `chronicle_news`), gifts and trades across sides,
        standing, and the story's state (the root, an entity named Story, and the meta's `chronicle_story`): each
        key's first value that day against its last."""
        w = self.world
        meta = w.meta()
        notable = _NEWS_KINDS | {str(k) for k in (meta.get("chronicle_news") or [])}
        story_ids = {w.root_id} | {e["id"] for e in w.find(name="Story", limit=5)}
        for ref in meta.get("chronicle_story") or []:
            e = w.get(str(ref)) or next(iter(w.find(name=str(ref), limit=1)), None)
            if e:
                story_ids.add(e["id"])
        visited = {(r["payload"] or {}).get("to") for r in
                   w.store.query("event", "world_id=? AND kind='moved' AND t<?", (w.id, lo))}
        news: list[dict[str, Any]] = []
        fights: dict[tuple[Any, ...], dict[str, Any]] = {}
        story: dict[str, list[Any]] = {}
        new_people: set[str] = set()

        def side(eid: str | None) -> str | None:
            e = w.get(eid) if eid else None
            f = (e or {}).get("state", {}).get("faction") if e else None
            return name(f) if isinstance(f, str) and w.get(f) else f

        def where(r: dict[str, Any]) -> str | None:
            # the event's own place, else where the one it is about was last seen that day, else stands now
            at = place(r) or last_at.get(r["target_id"])
            if at is None and r["target_id"]:
                e = w.get(r["target_id"])
                while e is not None and not w.is_a(e["type"], "place"):
                    e = w.get(e["parent_id"]) if e["parent_id"] else None
                at = name(e["id"]) if e is not None else None
            return at

        def item(r: dict[str, Any], what: str, **kw: Any) -> dict[str, Any]:
            row = {"t": round(float(r["t"]) - lo), "what": what, "place": where(r)}
            row.update({k: v for k, v in kw.items() if v not in (None, "", [], {})})
            return row

        last_at: dict[str, str] = {}
        for r in rows:
            k, p, tid, aid = r["kind"], r["payload"] or {}, r["target_id"], r["actor_id"]
            e = w.get(tid) if tid else None
            if r.get("path"):
                at = place(r)
                for x in (aid, tid):
                    if x and at:
                        last_at[x] = at
            if k == "spawned" and e is not None:
                if w.is_a(e["type"], "creature") and not e["state"].get("dead"):
                    new_people.add(tid)
                    news.append(item(r, "new_person", who=name(tid), type=e["type"], faction=side(tid)))
                elif w.is_a(e["type"], "place"):
                    visited.add(tid)
                    news.append(item(r, "new_place", name=name(tid), parent=name(e.get("parent_id")),
                                     hidden=bool(e["state"].get("hidden")) or None))
            elif k == "embodied" and tid and tid not in new_people:
                if not w.store.query("event", "world_id=? AND kind='embodied' AND target_id=? AND seq<?",
                                     (w.id, tid, r["seq"]), limit=1):
                    new_people.add(tid)
                    g = w.store.query("grants", "world_id=? AND principal_id=?", (w.id, p.get("principal")), limit=1)
                    news.append(item(r, "new_person", who=name(tid), seat=seat(tid), faction=side(tid),
                                     template=g[0].get("template") if g else None))
            elif k == "moved" and p.get("to") and p["to"] not in visited and aid == tid:
                visited.add(p["to"])
                news.append(item(r, "first_visit", who=name(tid), name=name(p["to"])))
            elif k in ("hit", "missed"):
                by = p.get("by") or aid
                key = (by, tid, place(r))
                f = fights.get(key)
                if f is None:
                    f = fights[key] = item(r, "fight", who=name(by), target=name(tid))
                    f.update({"blows": 0, "hits": 0, "damage": 0})
                    news.append(f)
                f["blows"] += 1
                if k == "hit":
                    f["hits"] += 1
                    f["damage"] += int(p.get("dmg") or 0)
            elif k in ("given", "traded"):
                by = p.get("by") or aid
                a, b = side(by), side(tid)
                if a != b:
                    what = name(p["item"]) if p.get("item") and w.get(p["item"]) else None
                    news.append(item(r, "gift" if k == "given" else "trade", who=name(by), target=name(tid), sides=[a, b],
                                     thing=what, count=p.get("count"), got=p.get("got"), gave=p.get("gave")))
            elif k == "standing":
                news.append(item(r, "standing", who=name(tid), faction=p.get("faction"), value=p.get("value"),
                                 delta=p.get("delta"), why=p.get("why")))
            elif k == "patched" and tid in story_ids:
                before, changes = p.get("before") or {}, p.get("changes") or {}
                for key, v in changes.items():
                    if key in ("ambient", "rules", "description"):
                        continue
                    if key not in story:
                        story[key] = [before.get(key), v, round(float(r["t"]) - lo), name(tid)]
                    else:
                        story[key][1], story[key][2] = v, round(float(r["t"]) - lo)
            elif k in notable:
                news.append(item(r, k, who=name(p.get("by") or aid), target=name(tid) if tid != (p.get("by") or aid) else None,
                                 detail={k: name(v) if isinstance(v, str) and w.get(v) else v for k, v in detail(p).items()
                                         if k != "by"}))

        def short(v: Any) -> Any:
            if isinstance(v, str) and w.get(v):
                return name(v)
            if isinstance(v, (str, int, float, bool)) or v is None:
                return v if not isinstance(v, str) or len(v) <= 160 else v[:157] + "..."
            text = json.dumps(v, ensure_ascii=False, default=str)
            return text if len(text) <= 160 else text[:157] + "..."

        for key, (was, now, t, holder) in story.items():
            if was != now:
                news.append({"t": t, "what": "story", "on": holder, "key": key, "was": short(was), "now": short(now)})
        return sorted(news, key=lambda x: x["t"])

    def publish_chronicle(self, day: int, text: str, title: str | None = None) -> dict[str, Any]:
        """(owner, author) Put one day's chronicle on the world's page (`days` in /chronicle.json, for a world whose
        meta says `public_feed`). Publishing a day again replaces it; an empty text withdraws it."""
        self._need(AUTHOR)
        self._tick()
        w = self.world
        today = int(w.t // self._day_seconds()) + 1
        day = int(day)
        if not 1 <= day <= today:
            raise Rejected(f"day {day} has not happened (it is day {today})", hint="chronicle() shows the day so far")
        text = str(text or "").strip()
        if len(text) > 20000:
            raise Rejected(f"a day's chronicle is at most 20000 characters (this one is {len(text)})",
                           hint="cut it, or publish the day's best part")
        if title is not None and len(str(title)) > 120:
            raise Rejected("a title is at most 120 characters")
        if not text and day not in self._published(day):
            raise Rejected(f"day {day} has nothing published to withdraw", hint="publish_chronicle(day, text)")
        self._record("publish_chronicle", day=day, title=title, chars=len(text))
        ev = w.emit("chronicled", actor=self._actor_or_none(), target=w.root_id, reach=0,
                    payload={"day": day, "title": str(title) if title else None, "text": text})
        public = bool(w.meta().get("public_feed"))
        return {"ok": True, "day": day, "seq": ev["seq"], "withdrawn": not text, "public": public,
                "hint": "on /chronicle.json under days within 30 seconds (the feed keeps that long)" if public else
                        "kept, not shown: the world's meta has no public_feed, so its page has no feeds"}

    # ---- acting -----------------------------------------------------------------------

    def act(self, verb: str, target: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """One deed. The result carries every event that touched you since you last looked: what the act
        caused, what the turn brought, and what others did near you in between (a line addressed to you
        while you were deciding), so a player or a mind never has to perceive again to catch up."""
        self._tick()
        me = self._me()
        self._acted()
        p = self._principal()
        since = p["cursor_seq"] if p else self.world.store.next_seq(self.world.id) - 1
        tid = self._resolve_for(me, target, verb, params) if target else None
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

    def reclaim(self, thing: str) -> dict[str, Any]:
        """Take back from an idle body where you stand what is yours (it was taken from you, or its `owner` is you)
        or what that body's standing orders give you. An idle body is one whose seat has done nothing for a while:
        a player gone to bed, a mind on a long watch. perceive() lists what you may reclaim. An awake holder you ask."""
        self._tick()
        w = self.world
        me = self._me()
        tid = self._resolve(thing)
        ok = {r["id"]: r for r in w.reclaimable(me)}
        if tid not in ok:
            t = w.need(tid)
            h = w.get(t["parent_id"]) if t["parent_id"] else None
            if h is None or not w.is_a(h["type"], "creature") or h["id"] == me:
                raise Rejected(f"nobody else holds {t['name']}", hint="take() what lies here")
            if h["parent_id"] != w.need(me)["parent_id"]:
                raise Rejected(f"{h['name']} is not here", hint="go where they are")
            if not w.idle(h["id"]):
                raise Rejected(f"{h['name']} is awake: ask them", hint=f"say(..., to='{h['name']}')")
            raise Rejected(f"{t['name']} is not yours, and {h['name']}'s standing orders do not give it to you",
                           hint="ask, trade, or wait for them", alternatives=[r["name"] for r in ok.values()])
        r = ok[tid]
        self._acted()
        if r["why"] != "yours":
            w.patch(tid, {"given_by": r["from"]})  # their orders gave it: a gift, not a taking
        w.move(tid, me, actor=me)
        w.emit("reclaimed", actor=me, target=tid, reach=1, payload={"from": r["from"], "why": r["why"]})
        return {"ok": True, "reclaimed": tid, "name": r["name"], "from": r["from_name"], "why": r["why"]}

    def away(self, give: list[dict[str, Any]] | None = None, answer: str | None = None,
             entity: str | None = None, sleep: bool = False) -> dict[str, Any]:
        """Standing orders for your body while your seat is idle (you went to bed, your mind is on a long watch).
        give=[{"item": <name>, "to": <name> or "anyone"}]: who may reclaim() what from you. answer: one line your
        body says to whoever speaks to it. Others see them on your card while you are idle. away() with nothing
        clears them; they stay set while you play and only work while you are idle. entity: which of a mind's
        bodies (default the one you embody). sleep=true: your body lies down to sleep now, by its own `sleep` verb
        (the d20 pack's): it mends faster and is easy prey, so do it somewhere safe. Your next deed wakes it."""
        self._tick()
        w = self.world
        eid = self._resolve(entity) if entity else self._me()
        held = w.embodied(eid)
        if not self._privileged() and (held is None or held["id"] != self.pid) and eid not in self.scope:
            raise Rejected("standing orders are for a body you hold", hint="away(...) for your own")
        orders: dict[str, Any] = {}
        for o in give or []:
            if not isinstance(o, dict) or not o.get("item"):
                raise Rejected("a give order is {'item': <name>, 'to': <name> or 'anyone'}",
                               hint='give=[{"item": "the sword", "to": "Ansel"}]')
            orders.setdefault("give", []).append({"item": str(o["item"]), "to": str(o.get("to") or "anyone")})
        if answer:
            if len(answer) > _SAY_MAX:
                raise Rejected(f"a standing answer is at most {_SAY_MAX} characters", hint="one short line")
            orders["answer"] = str(answer)
        if sleep and not w.need(eid)["state"].get("asleep"):
            if "sleep" not in w.schema_actions(w.need(eid)["type"]):
                raise Rejected("this body has no sleep verb", hint="away() without sleep; a world gets sleep from the d20 pack")
            w.act(eid, "sleep", None, {}, principal_id=self.pid)
        w.patch(eid, {"standing_orders": orders or None}, replace=True)
        return {"ok": True, "entity": eid, "standing_orders": orders, "asleep": bool(w.need(eid)["state"].get("asleep")),
                "hint": "they work while your seat is idle; away() clears them"}

    def say(self, text: str, reach: int = 1, to: str | None = None) -> dict[str, Any]:
        """Speak as the entity you embody. `to` addresses someone here; the room still hears it. Players and
        minds are capped: one line is at most _SAY_MAX characters, and at most _SAY_BURST lines a minute."""
        self._tick()
        me = self._me()
        self._acted()
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
        if not self._privileged() and len(text) > _NOTE_MAX:
            raise Rejected(f"a note is at most {_NOTE_MAX} characters; this one is {len(text)}",
                           hint="keep the gist; split a long account into several notes")
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
            if not self._sees(me):
                raise Rejected("your grant reads only its own part of the world", hint="recall someone under it")
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
        return {"entity": me, "about": self._card(o, full=full and self._sees(o["id"])), "edges": mine, "groups": shared,
                "exchanges": [{"t": x["t"], "who": x["actor"], "kind": x["kind"],
                               "text": x["payload"].get("text") or x["payload"].get("about")}
                              for x in w.exchanges(me, them, limit=min(limit, 10))],
                "between": between[-limit:], "notes": notes[-limit:], "goals": goals,
                "here": o["parent_id"] == ent["parent_id"]}

    def wait(self, timeout: float = 30.0, kinds: list[str] | None = None, poll: float = 0.1, full: bool = False,
             until: str | None = None, since: int | None = None,
             clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
        """Block until an event touches me (or the timeout). Returns the light bundle: the hour, where I am,
        who is here and the new events, with the cursor moved past them. `full=True` returns perceive()
        instead. A mind loops on this, so a quiet minute costs a few lines, not the whole card.

        `until`: a condition, one expression in the script subset, checked by the engine against what this
        principal may know (see UNTIL_DOC). The wait returns only when it is true, so a quiet hour of chatter that
        does not match costs nothing. On a timeout the cursor stays put and the reply is a few fields; call again
        (with the `since` it gave, for a watcher that is not embodied) and the events so far still count."""
        if until is not None and str(until).strip():
            return self._watch(str(until), timeout, kinds, full, since, clock, sleep)
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

    def _watch(self, until: str, timeout: float, kinds: list[str] | None, full: bool, since: int | None,
               clock: Callable[[], float], sleep: Callable[[float], None], poll: float = 0.5) -> dict[str, Any]:
        """wait(until=...): the oracle. Rescans from `since` (an embodied principal: its cursor, which does not
        move until the condition fires), keeps the last 200 events it may see, and evaluates the expression on a
        copy of what it may know: never the engine's own objects, never anyone's secrets."""
        cond = _until_script(until)
        start = clock()
        with self.engine.lock:
            self._tick()
            w = self.world
            p = w.principal(self.pid)
            me = p["entity_id"] if p and p["entity_id"] and w.get(p["entity_id"]) else None
            if me is None and not self._privileged():
                raise Rejected("you are not embodied", hint="join() your seat first, then wait(until=...)")
            if since is None:
                since = p["cursor_seq"] if (me and p) else w.store.next_seq(w.id) - 1
        scan, seen = int(since), []
        while True:
            with self.engine.lock:
                self._tick()
                w = self.world
                if me and w.get(me) is None:
                    raise Rejected(f"the entity you embodied ({me}) no longer exists", hint="join another entity")
                hi = w.store.next_seq(w.id) - 1
                if hi > scan:
                    rows = w.events(since=scan, until=hi, touching=me, limit=2000)
                    seen.extend(e for e in self._events_for(me, rows) if not kinds or e["kind"] in kinds)
                    seen = seen[-200:]
                    scan = hi
                view = self._watch_view(me, seen)
                try:
                    fired = bool(cond.call("until", env=view, fuel=20_000))
                except ScriptError as e:
                    raise Rejected(f"until: {e.reason}", hint=UNTIL_DOC) from None
                timed_out = clock() - start >= timeout
                if fired:
                    return self._watch_reply(me, until, seen, hi, full)
                if timed_out:
                    return {"world": w.id, "t": w.t, "timed_out": True, "fired": False, "until": until,
                            "since": since, "seen": len(seen), "here": view["here"], "present": view["present"]}
            sleep(poll)

    def _watch_view(self, me: str | None, seen: list[dict[str, Any]]) -> dict[str, Any]:
        """The names an until-expression sees. Plain data, copied, so a script can only read it."""
        w = self.world
        ent = w.get(me) if me else None
        here = w.get(ent["parent_id"]) if ent and ent["parent_id"] else None
        near = [c for c in w.children(here["id"]) if c["id"] != me and not c["state"].get("hidden")
                and w.is_a(c["type"], "creature")] if here else []  # who is here: people, not the jars by the cistern
        names: dict[str, str] = {}

        def nm(i: str | None) -> str | None:
            if not i:
                return None
            if i not in names:
                e = w.get(i)
                names[i] = e["name"] if e else i
            return names[i]

        evs = [{"seq": e["seq"], "t": e["t"], "kind": e["kind"], "actor": nm(e["actor"]), "target": nm(e["target"]),
                "text": str((e.get("payload") or {}).get("text") or (e.get("payload") or {}).get("about") or ""),
                "player": bool(e.get("by_player"))} for e in seen]
        cards = {c["name"]: self._visible_state(c, full=False) for c in near}
        if ent:
            cards.update({c["name"]: self._visible_state(c, full=False) for c in w.children(me)})
            cards[ent["name"]] = self._visible_state(ent, full=True)
        data = json.loads(json.dumps({
            "t": w.t, "ambient": self._ambient(here), "here": here["name"] if here else None,
            "present": [c["name"] for c in near], "me": self._visible_state(ent, full=True) if ent else {},
            "events": evs, "cards": cards}, default=str))
        privileged = self._privileged()

        def low(x: Any) -> str:
            return str(x or "").lower()

        def heard(word: str = "", by: str = "") -> bool:
            return any(e["text"] and low(word) in low(e["text"]) and low(by) in low(e["actor"]) for e in data["events"])

        def did(kind: str, by: str = "") -> bool:
            return any(e["kind"] == kind and low(by) in low(e["actor"]) for e in data["events"])

        def came(name: str) -> bool:
            return any(low(name) in low(n) for n in data["present"])

        def state(name: str) -> dict[str, Any]:
            for n, st in data["cards"].items():
                if low(name) == low(n) or low(name) in low(n):
                    return st
            if privileged:
                try:
                    e = w.get(self._resolve(name))
                except Rejected:
                    return {}
                return json.loads(json.dumps(self._visible_state(e, full=self._sees(e["id"])), default=str)) if e else {}
            return {}

        view = {k: v for k, v in data.items() if k != "cards"}
        view.update(heard=heard, did=did, came=came, state=state)
        return view

    def _watch_reply(self, me: str | None, until: str, seen: list[dict[str, Any]], hi: int,
                     full: bool) -> dict[str, Any]:
        w = self.world
        if full and me:
            b = self.perceive()
            b["fired"] = True
            b["until"] = until
            return b
        ent = w.get(me) if me else None
        here = w.get(ent["parent_id"]) if ent and ent["parent_id"] else None
        b = {"world": w.id, "t": w.t, "fired": True, "until": until, "ambient": self._ambient(here),
             "here": {"id": here["id"], "name": here["name"]} if here else None,
             "present": [{"id": c["id"], "name": c["name"]} for c in w.children(here["id"])
                         if c["id"] != me and not c["state"].get("hidden")] if here else [],
             "events": seen[-50:], "cursor": hi}
        if me:
            w.set_cursor(self.pid, hi)
        return b

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

    def introduce(self, type: str, parent: str, name: str, how: str, known_by: dict[str, str],
                  state: dict[str, Any] | None = None, scene: str | None = None, by: str | None = None,
                  remembers: list[str] | None = None, pos: list[float] | None = None,
                  after: float | None = None) -> dict[str, Any]:
        """Bring something new into the world the way the world would have it, in one call: where it is, how it
        came (INTRODUCE_HOW), who already knows it and what they know, and for a person what it knows itself.
        always_there arrives without a sound; every other way shows the room a scene. known_by {entity: note} writes
        each note into that one's memory (and, for a person, a `knows` link); {} says nobody knows it.
        after=N world seconds: announced now, arrives then. known_by learn it now (write the note as news: "a
        mason comes on the crawler in three days"); the thing, its links and the scene land when the timer fires.
        The timer is listed by timers() and unschedule cancels the arrival."""
        self._need(AUTHOR)
        w = self.world
        if how not in INTRODUCE_HOW:
            raise Rejected(f"how must say how it came: one of {', '.join(INTRODUCE_HOW)}",
                           hint="; ".join(f"{k}: {v}" for k, v in INTRODUCE_HOW.items()), alternatives=list(INTRODUCE_HOW))
        if how != "always_there" and not scene:
            raise Rejected(f"something that {how.replace('_', ' ')} is seen: give the scene the room sees",
                           hint="scene='A rider comes in off the salt, dust to the eyes.' or how='always_there' if it was")
        if how in ("delivered", "built") and not by:
            raise Rejected(f"{how} by whom?", hint="by='<who brought or made it>'")
        if not isinstance(known_by, dict):
            raise Rejected("known_by is {entity: what they know of it}", hint="known_by={} if nobody knows it")
        if after is not None and (how == "always_there" or float(after) <= 0):
            raise Rejected("after= is for something on its way: a positive number of world seconds, and a way it comes"
                           if how != "always_there" else "something always there cannot arrive later",
                           hint="after=259200 for three days, with how='arrived' or 'delivered'")
        w.schema(type)
        where = self._resolve(parent)
        knowers = {self._resolve(k): str(note) for k, note in known_by.items()}  # every name resolves before a write
        maker = self._resolve(by) if by else None
        self._record("introduce", type=type, parent=parent, name=name, how=how, known_by=known_by, state=state,
                     scene=scene, by=by, remembers=remembers, pos=pos, after=after)
        for k, note in knowers.items():
            w.remember(k, note, actor=k)
        spec = {"type": type, "parent": where, "name": name, "how": how, "by": maker, "state": state, "pos": pos,
                "known_by": knowers, "remembers": remembers, "scene": scene}
        if after is not None:
            sid = w.schedule(float(after), "introduce", entity=where, payload={"spec": spec})
            return {"ok": True, "scheduled": sid, "at": w.t + float(after), "name": name, "how": how,
                    "known_by": sorted(knowers), "hint": "it lands then, with its scene; unschedule(id) calls it off"}
        eid = w.land(spec, actor=self._actor_or_none())
        out = self._card(w.need(eid), full=True)
        out.update(how=how, known_by=sorted(knowers), remembers=len(remembers or []))
        return out

    def patch(self, entity: str, changes: dict[str, Any], replace: bool = False) -> dict[str, Any]:
        """Dict values merge into existing dicts (add one dialog topic without resending the rest);
        replace=True sets each key whole; a None value deletes the key."""
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self._record("patch", entity=entity, changes=changes, replace=replace or None)
        self.world.patch(eid, changes, actor=self._actor_or_none(), replace=replace)
        return self._card(self.world.need(eid), full=True)

    def rename(self, entity: str, name: str) -> dict[str, Any]:
        """A new name for anyone or anything (a guest who joined under a handle picks a character name). Refused
        when someone else already has it; the room hears `renamed` {old, new}, and the old name stays in the log."""
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self._record("rename", entity=entity, name=name)
        old = self.world.rename(eid, name, actor=self._actor_or_none())
        out = self._card(self.world.need(eid), full=True)
        out["was"] = old
        return out

    # ---- the maker's frame: verbs a player puts on machines (docs/ACCESS.md, phase 2) ---------------------------

    def _frames(self) -> list[dict[str, Any]]:
        """The maker's frames in the hands of the body this principal holds, revoked ones too."""
        w = self.world
        p = w.principal(self.pid)
        body = p["entity_id"] if p and p.get("entity_id") and w.get(p["entity_id"]) else None
        return [c for c in w.children(body) if isinstance(c["state"].get("maker"), dict)] if body else []

    def _frame_for(self, frame: str | None) -> dict[str, Any] | None:
        """The frame a verb is made with: for the owner and author roles the one they name, or none (their own
        hand); for anyone else a live one their body holds."""
        w = self.world
        if self._staff():
            if frame is None:
                return None
            f = w.need(self._resolve(frame))
            if not isinstance(f["state"].get("maker"), dict):
                raise Rejected(f"{f['name']} is not a maker's frame", hint="a frame is a thing whose state has `maker`")
            return f
        held = self._frames()
        if frame is not None:
            fid = self._resolve(frame)
            held = [f for f in held if f["id"] == fid]
        if not held:
            raise Rejected("you hold no maker's frame", hint="with a frame in hand you program machines (docs/ACCESS.md)")
        live = [f for f in held if not f["state"]["maker"].get("revoked")]
        if not live:
            raise Rejected(f"the grant of {held[0]['name']} is revoked", hint="ask the world's owner")
        return live[0]

    def program(self, thing: str, verb: str, source: str, doc: str = "", params: dict[str, Any] | None = None,
                frame: str | None = None) -> dict[str, Any]:
        """Put a verb on one machine, with a maker's frame in hand. `source` is a script with def apply(ctx) (and
        check(ctx) if you like), the language of every verb (guide()). The frame's `maker` names the kinds of thing
        it programs, and the thing's access must give you w. The code runs held: it changes only the machine and
        what it holds, plus whoever chose the verb; it reads public state; it makes nothing from nothing and sets
        no rules; what it says reaches others marked untrusted. With the frame's `review` on, the verb waits for
        the owner. The owner and author program anything; frame=... holds their code to that frame."""
        self._tick()
        w = self.world
        f = self._frame_for(frame)
        eid = self._resolve(thing)
        e = w.need(eid)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", str(verb or "")):
            raise Rejected(f"a verb is one short lowercase word, not {verb!r}", hint="like hail or tune_engine")
        if verb in w.schema_actions(e["type"]):
            raise Rejected(f"{e['name'] or eid} already has {verb} of its own", hint="pick another word")
        if e["state"].get("canon") and self.role != OWNER:
            raise Rejected(f"{e['name']} is canon: the owner's to change", hint="program something else")
        old = own_verbs(e).get(verb)
        limits, made, recent, now = None, [], [], self.engine.wall()
        if f is not None:
            m = f["state"]["maker"]
            types = [t for t in (m.get("types") or []) if isinstance(t, str)]
            if not any(w.is_a(e["type"], t) for t in types):
                raise Rejected(f"{f['name']} programs {', '.join(types) or 'nothing'}; {e['name'] or eid} is a {e['type']}",
                               hint="program a machine of a kind the frame names")
            made = [x for x in (f["state"].get("made") or []) if x != [eid, verb]]
            recent = [t for t in (f["state"].get("made_at") or []) if now - float(t) < 3600]
            if not self._staff():
                if self._access_allows(eid, "w") is not True:
                    raise Rejected(f"{e['name'] or eid} is not open to you (its access gives you no w)",
                                   hint="program your own machine, or ask its owner to open it to you")
                if isinstance(old, dict) and old.get("frame") not in (None, f["id"]):
                    raise Rejected(f"{verb} on {e['name'] or eid} was made with another frame", hint="pick another word")
                if len(source) > int(m.get("max_source") or 6000):
                    raise Rejected(f"the frame takes at most {int(m.get('max_source') or 6000)} characters a verb",
                                   hint="say it shorter")
                if len(made) >= int(m.get("max_scripts") or 12):
                    raise Rejected(f"{f['name']} holds {len(made)} verbs, its most", hint="unprogram one first")
                if len(recent) >= int(m.get("per_hour") or 20):
                    raise Rejected(f"{f['name']} has made {len(recent)} verbs this hour, its most", hint="wait a while")
            pre = str(m.get("scripts") or f"maker_{f['id']}_")
            limits = {"under": "self", "frame": f["id"], "scripts": pre}
        sid = f"{limits['scripts'] if limits else 'program_'}{verb}_{eid}"
        src = source.split("\n", 1)[1] if source.startswith(LIMITS_HEAD) and "\n" in source else source
        text = LIMITS_HEAD + json.dumps(limits, sort_keys=True) + "\n" + src if limits else src
        try:
            if not Script(text, name=sid).has("apply"):
                raise Rejected("a verb needs def apply(ctx)", hint="guide() has the language")
        except ScriptError as x:
            raise Rejected(x.reason, hint=x.hint) from None
        self._record("program", thing=thing, verb=verb, source=source, doc=doc or None, params=params,
                     frame=f["id"] if f else None)
        w.define_script(sid, text, str(doc)[:300])
        entry: dict[str, Any] = {"script": sid, "doc": str(doc)[:300], "params": dict(params or {})}
        if f is not None:
            entry.update(frame=f["id"], by=self.pid)
            if f["state"]["maker"].get("review") and not self._staff():
                entry["pending"] = True
            w.patch(f["id"], {"made": made + [[eid, verb]], "made_at": recent + [now]}, replace=True)
        w.patch(eid, {"programmed": {**own_verbs(e), verb: entry}}, replace=True)
        return {"ok": True, "thing": eid, "verb": verb, "script": sid, "pending": bool(entry.get("pending")),
                "limits": limits}

    def _drop_program(self, eid: str, verb: str) -> dict[str, Any]:
        w = self.world
        e = w.need(eid)
        prog = dict(own_verbs(e))
        entry = prog.pop(verb, None)
        if not isinstance(entry, dict):
            raise Rejected(f"{e['name'] or eid} has no programmed {verb}", hint="programs(thing) lists them")
        w.patch(eid, {"programmed": prog or None}, replace=True)
        f = w.get(entry.get("frame") or "")
        if f is not None:
            w.patch(f["id"], {"made": [x for x in (f["state"].get("made") or []) if x != [eid, verb]]}, replace=True)
        return entry

    def unprogram(self, thing: str, verb: str) -> dict[str, Any]:
        """Take a programmed verb off a thing: its maker, with the frame that made it in hand, or the owner."""
        self._tick()
        eid = self._resolve(thing)
        entry = own_verbs(self.world.need(eid)).get(verb)
        if not self._staff() and (not isinstance(entry, dict) or entry.get("frame") not in {f["id"] for f in self._frames()}):
            raise Rejected(f"{verb} on {thing} is not yours to take off", hint="hold the frame that made it")
        self._record("unprogram", thing=thing, verb=verb)
        self._drop_program(eid, verb)
        return {"ok": True, "thing": eid, "verb": verb}

    def programs(self, thing: str | None = None, frame: str | None = None) -> dict[str, Any]:
        """The verbs put on a thing (with their source when the frame that made them is in your hands, or you are
        the owner or author), or with no thing, what your frames (the owner: frame=...) have made."""
        self._tick()
        w = self.world
        mine = {f["id"] for f in self._frames()}

        def row(eid: str, verb: str, entry: dict[str, Any]) -> dict[str, Any]:
            out = {"thing": eid, "verb": verb, "doc": entry.get("doc", ""), "frame": entry.get("frame"),
                   "pending": bool(entry.get("pending"))}
            if self._staff() or entry.get("frame") in mine:
                src = w.store.get("script", w.id, entry["script"])
                out["source"] = src["source"].split("\n", 1)[1] if src and src["source"].startswith(LIMITS_HEAD) else (src or {}).get("source")
            return out

        if thing is not None:
            eid = self._resolve(thing)
            return {"ok": True, "verbs": [row(eid, v, x) for v, x in own_verbs(w.need(eid)).items()
                                          if isinstance(x, dict)]}
        frames = [w.need(self._resolve(frame))] if frame is not None and self._staff() else self._frames()
        out = []
        for f in frames:
            for eid, verb in f["state"].get("made") or []:
                entry = own_verbs(w.get(eid)).get(verb)
                if isinstance(entry, dict):
                    out.append(row(eid, verb, entry))
        return {"ok": True, "frames": [{"id": f["id"], "name": f["name"], "maker": f["state"]["maker"]} for f in frames],
                "verbs": out}

    def review(self, thing: str, verb: str, approve: bool = True) -> dict[str, Any]:
        """The owner's word on a verb a frame with `review` made: approve it (it goes live) or not (it comes off)."""
        self._need(AUTHOR)
        eid = self._resolve(thing)
        e = self.world.need(eid)
        entry = own_verbs(e).get(verb)
        if not isinstance(entry, dict):
            raise Rejected(f"{e['name'] or eid} has no programmed {verb}", hint="programs(thing) lists them")
        self._record("review", thing=thing, verb=verb, approve=approve)
        if not approve:
            self._drop_program(eid, verb)
            return {"ok": True, "thing": eid, "verb": verb, "removed": True}
        entry = {k: v for k, v in entry.items() if k != "pending"}
        self.world.patch(eid, {"programmed": {**own_verbs(e), verb: entry}}, replace=True)
        return {"ok": True, "thing": eid, "verb": verb, "live": True}

    def chmod(self, entity: str, mode: str, verb: str | None = None) -> dict[str, Any]:
        """Set who may read (r), change (w) and use (x) a thing: mode rwxr-x---, octal 750, or symbolic g+w, o-rwx
        (comma separated), for its owner, its group and everyone else. With verb=..., mode names the classes that
        may do that one verb to it (u, ug, a, "" for nobody; "default" drops the rule). A thing with no owner gets
        you as its owner when you are not the world's owner or author (docs/ACCESS.md)."""
        self._need(AUTHOR)
        eid = self._resolve(entity)
        self._record("chmod", entity=entity, mode=mode, verb=verb)
        claim = self.pid if not self._staff() and not (acl.of(self.world.get(eid)) or {}).get("owner") else None
        acc = self.world.set_access(eid, mode=mode, verb=verb, owner=claim, actor=self._actor_or_none())
        return {"ok": True, "entity": eid, "access": acc}

    def chown(self, entity: str, owner: str | None = None, group: str | None = None) -> dict[str, Any]:
        """Give a thing to an owner (an entity, or a principal id from grants() or seats()) and/or set its group
        ("" clears it). Group members are listed on the root under access_groups: {"masons": [ids]}."""
        self._need(AUTHOR)
        eid = self._resolve(entity)
        who = None
        if owner is not None:
            try:
                who = self._resolve(owner)
            except Rejected:
                w = self.world
                known = w.principal(owner) or w.store.query("grants", "world_id=? AND principal_id=?", (w.id, owner), limit=1)
                if not known and owner != self.pid:
                    raise Rejected(f"no entity or principal {owner!r}", hint="an entity id or name, or a principal id") from None
                who = owner
        self._record("chown", entity=entity, owner=owner, group=group)
        acc = self.world.set_access(eid, owner=who, group=group, actor=self._actor_or_none())
        return {"ok": True, "entity": eid, "access": acc}

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
        """What is scheduled and when (fog in 38 s, dawn in 200 s). Ticks of behaviors are left out. A player or a
        mind sees what everyone in the world knows: the next of each kind the world's meta lists as `public_timers`
        (the day's round, a market day), in world words, without what the timer carries."""
        self._tick()
        if self._privileged():
            return self._timers()
        public = set(self.world.meta().get("public_timers") or [])
        out: dict[str, dict[str, Any]] = {}
        for t in self._timers(limit=500):
            if t["kind"] in public and t["kind"] not in out:
                out[t["kind"]] = {"kind": t["kind"], "in": t["in"], "when": _in_words(t["in"]), "every": t["every"]}
        return list(out.values())

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


def _in_words(seconds: float) -> str:
    """World seconds from now, as a person would say it."""
    m = seconds / 60.0
    if m < 2:
        return "now, or nearly"
    if m < 90:
        return f"in about {round(m)} minutes"
    h = m / 60.0
    return f"in about {round(h)} hours" if h < 36 else f"in about {round(h / 24)} days"


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


UNTIL_DOC = ("until is one Python expression (the embody script subset: no imports, no lambdas) over what you may "
             "know: t (world seconds), ambient (dict: time_of_day, light, ...), here (your place's name), present "
             "(names of who is here), me (your own state: water, vigor, wounded, ...), events (since the wait began: "
             "seq, t, kind, actor, target, text, player), and helpers heard(word, by=''), did(kind, by=''), "
             "came(name), state(name) (the state you can see of someone here or something you hold). Examples: "
             "\"came('Reeve')\", \"heard('ruhl', by='Reeve') or me['vigor'] < 3\", \"t >= 43200\", "
             "\"ambient.get('time_of_day') == 'dusk'\". Names match by part, any case.")


def _until_script(until: str) -> Script:
    expr = " ".join(str(until).split())
    if len(expr) > 2000:
        raise Rejected("until is too long (2000 characters at most)", hint=UNTIL_DOC)
    try:
        sc = Script("def until():\n    return (" + expr + ")\n", name="until")
    except ScriptError as e:
        raise Rejected(f"until: {e.reason}", hint=UNTIL_DOC) from None
    if set(sc.functions) != {"until"}:
        raise Rejected("until is one expression, not definitions", hint=UNTIL_DOC)
    return sc


# How something new comes into the world (introduce): never from nowhere unless the game says so.
INTRODUCE_HOW = {
    "always_there": "it has been here all along and nobody remarks on it now; arrives without a sound",
    "arrived": "it came in on its own feet or wheels; the room sees it come",
    "delivered": "someone (by=) brought it; the room sees it handed over or set down",
    "built": "someone (by=) made it here; the room sees it finished",
    "appeared": "it came from nowhere, because the game says things do; the room sees that",
}

OPS = [
    "worlds", "use", "create_world", "fork_world", "save", "restore", "join", "leave", "seats",
    "invite", "grants", "revoke", "evict", "requests", "chronicle", "publish_chronicle",
    "perceive", "inspect", "find", "history", "act", "act_many", "say", "remember", "intend", "recall", "wait",
    "reclaim", "away",
    "define_schema", "define_script", "schemas", "scripts", "script_source",
    "spawn", "introduce", "patch", "rename", "move", "destroy", "link", "connect", "unlink", "relate", "unrelate", "layout", "map",
    "measure", "set_rule", "clear_rule", "schedule", "unschedule", "clock", "timers", "summary", "mirror", "act_as", "say_as",
    "chmod", "chown", "program", "unprogram", "programs", "review",
]


# What a chronicle leaves out of its beats: the bookkeeping of building and moving. Travel is told on its own.
# A day's upkeep: what bodies do every beat. Counted under routine, never news.
_CHRONICLE_ROUTINE = frozenset({"mended", "sweated", "drank", "filled", "thirsty", "parched", "quenched", "merged",
                                "opinion", "woke", "slept", "embodied", "released", "reclaimed", "finished",
                                "passing", "approaching", "repairing", "refuelled"})
# The kinds that are news wherever they happen (a world adds its own with `chronicle_news` in its meta).
_NEWS_KINDS = frozenset({"found", "downed", "killed", "outlawed", "yielded", "truce_broken", "dishonor", "lock_broken",
                         "lock_picked", "lifted", "caught", "renamed", "destroyed", "burned", "works_done", "stage_done",
                         "challenged", "agreed", "spoiled", "wounded", "rose", "searched", "stopped",
                         "broke_down", "struck"})
_CHRONICLE_QUIET = frozenset({"spawned", "patched", "linked", "unlinked", "related", "unrelated", "laid_out", "moved",
                              "left", "chronicled", "scene", "say", "unscheduled", "ledger_received"})


_PLAY_OR_WATCH = frozenset({"worlds", "use", "summary", "seats", "join", "leave", "perceive", "inspect", "find", "history",
                            "act", "say", "wait", "recall", "clock"})


def allowed_ops(role: str) -> frozenset[str]:
    from .grants import ROLE_OPS
    return ROLE_OPS.get(role, frozenset())


# Ops that write where canon and a grant's limits are checked before they run (Session._hold).
_HELD = frozenset({"spawn", "introduce", "patch", "rename", "move", "destroy", "link", "connect", "unlink", "relate", "unrelate", "schedule", "layout",
                   "unschedule", "act_as", "say_as", "remember", "intend", "set_rule", "clear_rule", "define_script",
                   "define_schema", "clock", "create_world", "fork_world", "save", "restore", "mirror", "chmod", "chown"})


def _guard(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def inner(self: Session, *a: Any, **kw: Any) -> Any:
        self._allow(name)
        if name in _HELD and self.world_id and (self.limits or self.role != OWNER):
            ba = sig.bind(self, *a, **kw)
            ba.apply_defaults()
            self._hold(name, ba.arguments)
            return fn(*ba.args, **ba.kwargs)
        return fn(self, *a, **kw)
    return inner


for _op in OPS:
    setattr(Session, _op, _guard(_op, getattr(Session, _op)))


def _seen_relation(r: dict[str, Any], me: str) -> bool:
    """A relation another body may see on someone it inspects: a group it is part of or one held in the open (a duel,
    a truce: `public`), and an edge between the two marked `public` (readable by its other end, as recall reads it).
    Whom they know, their side's standing and what they think of anyone else stay theirs."""
    public = bool((r.get("data") or {}).get("public"))
    if "participants" in r:
        return public or me in r["participants"]
    return public and r.get("with") == me


def _brief(e: dict[str, Any]) -> dict[str, Any]:
    """A thing named in someone else's card: its id and name, and its count when it is a stack."""
    out = {"id": e["id"], "name": e["name"]}
    if e["state"].get("count") is not None:
        out["count"] = int(e["state"]["count"])
    return out
