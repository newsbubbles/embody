"""MCP server: the op table for any MCP-capable harness.

    uv run embody serve --as gm --author

One server process holds one main principal (from the flags) and any number of extra principals an
agent asks for by name with the `principal` argument on the playing tools: a narrator embodied as
the Traveler can let a subagent join as Mara through the same connection. Extra principals never
get the author capability; authoring tools always run as the main principal.
Every tool returns a dict; a failure is {"ok": false, "reason", "hint", "alternatives"}.
"""

from __future__ import annotations

import argparse
import functools
import inspect
import os
from pathlib import Path
from typing import Any

from .ops import AUTHOR, OBSERVER, Engine, Rejected, Session

GUIDE_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "SCRIPTING.md"

INSTRUCTIONS = """embody is a deterministic world engine. You are connected as one main principal; the playing tools
take an optional `principal` to act as another one (a mind for an NPC) over this same connection.
Flow: worlds() -> join(world, entity) -> perceive() -> act(verb, target) -> perceive(). Speak with say (to=someone
to address them). remember(text) keeps your character's notes in the engine. Authors build with define_script /
define_schema / spawn / connect / patch, give NPCs free lines with say_as, drive them with act_as, and start a
fresh game on the same state with fork_world. Every entity is content (state), code (its components) and ops
(its actions): perceive lists what you can do and why something is not possible right now. Errors tell you what
would work instead. Call guide() before writing scripts."""


def _wrap(fn):
    @functools.wraps(fn)
    def inner(*a: Any, **kw: Any) -> Any:
        try:
            return fn(*a, **kw)
        except Rejected as r:
            return r.to_dict()
    inner.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    return inner


class Hub:
    """The sessions behind one server: the main principal plus the extra ones agents ask for by name."""

    def __init__(self, engine: Engine, main: Session):
        self.engine = engine
        self.main = main
        self.extra: dict[str, Session] = {}

    def session(self, principal: str | None) -> Session:
        if not principal or principal == self.main.pid:
            return self.main
        s = self.extra.get(principal)
        if s is None:
            # an extra principal gets no author capability, whatever the main one has
            s = self.engine.session(principal, world_id=self.main.world_id, capabilities=[], name=principal)
            self.extra[principal] = s
        elif s.world_id is None:
            s.world_id = self.main.world_id
        return s

    def principals(self) -> list[dict[str, Any]]:
        out = [{"principal": self.main.pid, "capabilities": self.main.capabilities, "world": self.main.world_id,
                "main": True}]
        for pid, s in self.extra.items():
            out.append({"principal": pid, "capabilities": s.capabilities, "world": s.world_id, "main": False})
        return out


def build_server(session: Session, db: Path, engine: Engine | None = None):
    from mcp.server.mcpserver import MCPServer

    hub = Hub(engine or session.engine, session)
    s = session
    S = hub.session
    srv = MCPServer("embody", instructions=INSTRUCTIONS)
    tool = srv.tool

    @tool()
    @_wrap
    def guide() -> str:
        """The scripting and authoring reference: ctx API, schema fields, action/listener/behavior shapes. Read it before define_script."""
        if GUIDE_PATH.exists():
            return GUIDE_PATH.read_text(encoding="utf-8")
        return "docs/SCRIPTING.md not found beside the package"

    @tool()
    @_wrap
    def worlds() -> list[dict[str, Any]]:
        """List the worlds in this database."""
        return s.worlds()

    @tool()
    @_wrap
    def principals() -> list[dict[str, Any]]:
        """The principals this server speaks for: the main one and every extra one asked for by name."""
        return hub.principals()

    @tool()
    @_wrap
    def create_world(name: str, seed: int = 0, id: str | None = None, description: str = "") -> dict[str, Any]:
        """(author) Create an empty world with a root entity and the base schemas: entity, place, thing, creature."""
        return s.create_world(name, seed=seed, id=id, description=description)

    @tool()
    @_wrap
    def fork_world(source: str, id: str, name: str = "") -> dict[str, Any]:
        """(author) A fresh game on the same world state: copies a world with its full history under a new id,
        nobody embodied. The source is untouched. Then use(id) or join(id, entity)."""
        return s.fork_world(source, id, name)

    @tool()
    @_wrap
    def load_world(file: str, upgrade: bool = False) -> dict[str, Any]:
        """(author) Run a world file (a Python module with build(session)). upgrade=True runs only its define(session)
        against the world this session points at: scripts and schemas are redefined, state and history stay."""
        from .cli import load_world_file
        return load_world_file(s, Path(file), upgrade=upgrade)

    @tool()
    @_wrap
    def use(world_id: str, principal: str | None = None) -> dict[str, Any]:
        """Point a session at a world without embodying anything (authors, observers)."""
        return S(principal).use(world_id)

    @tool()
    @_wrap
    def join(world_id: str, entity: str, principal: str | None = None) -> dict[str, Any]:
        """Embody an entity (by id or unique name) in a world. Returns your first perception. Pass principal=<name>
        to join as another principal over this connection (a mind for an NPC while the main principal stays who it is)."""
        return S(principal).join(world_id, entity)

    @tool()
    @_wrap
    def leave(principal: str | None = None) -> dict[str, Any]:
        """Release the entity you embody. Its behaviors and dialog table resume."""
        return S(principal).leave()

    @tool()
    @_wrap
    def perceive(cursor: int | None = None, from_entity: str | None = None, events: int = 30,
                 principal: str | None = None) -> dict[str, Any]:
        """Everything you sense from where you are: place, who and what is here, exits, what you hold, who you know
        (with standing and the last exchanges), places you have been, the verbs you could try (with the reason when
        one is not possible), and events since your cursor. Your own card includes your secret memory and brief.
        Authors and observers may pass from_entity to perceive as any entity (the NPC context bundle)."""
        return S(principal).perceive(cursor=cursor, from_entity=from_entity, events=events)

    @tool()
    @_wrap
    def inspect(entity: str, principal: str | None = None) -> dict[str, Any]:
        """One entity in full: state, contents, relations, actions, schema chain. Must be within reach unless you are an author or observer."""
        return S(principal).inspect(entity)

    @tool()
    @_wrap
    def find(type: str | None = None, name: str | None = None, under: str | None = None,
             parent: str | None = None, state: dict[str, Any] | None = None, limit: int = 30,
             principal: str | None = None) -> list[dict[str, Any]]:
        """Structured search. type matches the schema chain, name is a substring, under limits to a subtree,
        state matches exact key values. Embodied principals search their own place."""
        return S(principal).find(type=type, name=name, under=under, parent=parent, state=state, limit=limit)

    @tool()
    @_wrap
    def history(since: int = 0, until: int | None = None, kinds: list[str] | None = None,
                touching: str | None = None, limit: int = 50, principal: str | None = None) -> list[dict[str, Any]]:
        """Paged event log. Embodied principals see events that touched them."""
        return S(principal).history(since=since, until=until, kinds=kinds, touching=touching, limit=limit)

    @tool()
    @_wrap
    def act(verb: str, target: str | None = None, params: dict[str, Any] | None = None,
            principal: str | None = None) -> dict[str, Any]:
        """Do a verb, optionally on a target (id or unique name). The only way to change the world on purpose.
        Returns the events it caused (and, in turn-based play, what happened in the turn that followed),
        or a rejection with the reason and what would work instead."""
        return S(principal).act(verb, target, params)

    @tool()
    @_wrap
    def act_many(steps: list[dict[str, Any]], principal: str | None = None) -> dict[str, Any]:
        """Ordered batch of {verb, target?, params?}. Stops at the first rejection and returns what got done."""
        return S(principal).act_many(steps)

    @tool()
    @_wrap
    def say(text: str, reach: int = 1, to: str | None = None, principal: str | None = None) -> dict[str, Any]:
        """Speak as the entity you embody. to=<entity> addresses someone here (it lands in both your logs; the
        room still hears it). reach 1 = your place hears it, 2 = the place above too, -1 = the whole world."""
        return S(principal).say(text, reach=reach, to=to)

    @tool()
    @_wrap
    def remember(text: str, entity: str | None = None, principal: str | None = None) -> dict[str, Any]:
        """Write a note into your character's secret memory, kept by the engine: who you are, what you want, what
        you decided, what you think of someone. Whoever embodies this entity next reads the same notes.
        Authors may pass entity=<id or name> to write for any entity."""
        return S(principal).remember(text, entity=entity)

    @tool()
    async def wait(timeout: float = 30.0, kinds: list[str] | None = None, principal: str | None = None) -> dict[str, Any]:
        """Block until an event touches you or your place (or the timeout, max 120 s), then perceive. A mind loops on this."""
        import anyio
        sess = S(principal)
        try:
            return await anyio.to_thread.run_sync(lambda: sess.wait(timeout=min(float(timeout), 120.0), kinds=kinds))
        except Rejected as r:
            return r.to_dict()

    # ---- authoring (always the main principal)

    @tool()
    @_wrap
    def define_script(id: str, source: str, doc: str = "") -> dict[str, Any]:
        """(author) Store a script: Python-subset source with def check(ctx) / apply(ctx) (actions),
        def on(ctx, event) (listeners) or def tick(ctx) (behaviors). Validated now; see guide()."""
        return s.define_script(id, source, doc)

    @tool()
    @_wrap
    def define_schema(id: str, extends: str | None = None, doc: str = "", state: dict[str, Any] | None = None,
                      space: dict[str, Any] | None = None, actions: dict[str, Any] | None = None,
                      listeners: list[dict[str, Any]] | None = None,
                      behaviors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """(author) Define or redefine an entity type. actions={verb: {script, doc, targets?, params?, reach?, duration?, scope?}}
        (targets = a type: the verb is the holder's; none: the verb is done to the object; scope held|here|exits|any
        keeps impossible pairs out of affordances). listeners=[{script, kinds?, unless_embodied?}],
        behaviors=[{script, every}], space={kind: grid|plane, ...}. Existing entities of the type pick up the new definition."""
        return s.define_schema(id, extends=extends, doc=doc, state=state, space=space, actions=actions,
                               listeners=listeners, behaviors=behaviors)

    @tool()
    @_wrap
    def schemas() -> list[dict[str, Any]]:
        """(author) Every schema in the world."""
        return s.schemas()

    @tool()
    @_wrap
    def scripts() -> list[dict[str, Any]]:
        """(author) Every script in the world, with version and length."""
        return s.scripts()

    @tool()
    @_wrap
    def script_source(id: str) -> dict[str, Any]:
        """(author) One script's source."""
        return s.script_source(id)

    @tool()
    @_wrap
    def spawn(type: str, parent: str, name: str = "", state: dict[str, Any] | None = None,
              pos: list[float] | None = None) -> dict[str, Any]:
        """(author) Create an entity inside a parent. Something improvised during play gets state {"improvised": true}."""
        return s.spawn(type, parent, name=name, state=state, pos=pos)

    @tool()
    @_wrap
    def patch(entity: str, changes: dict[str, Any], replace: bool = False) -> dict[str, Any]:
        """(author) Change state keys. A dict value merges into the existing dict (add one dialog topic without
        resending the rest); replace=True sets each key whole; a None value deletes the key."""
        return s.patch(entity, changes, replace=replace)

    @tool()
    @_wrap
    def move(entity: str, parent: str, pos: list[float] | None = None) -> dict[str, Any]:
        """(author) Reparent an entity (teleport, hand over, put inside)."""
        return s.move(entity, parent, pos=pos)

    @tool()
    @_wrap
    def destroy(entity: str) -> dict[str, Any]:
        """(author) Remove an entity and everything inside it."""
        return s.destroy(entity)

    @tool()
    @_wrap
    def connect(a: str, b: str, via: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """(author) Two-way passage between places, optionally through a door-like entity (via)."""
        return s.connect(a, b, via=via, data=data)

    @tool()
    @_wrap
    def link(source: str, target: str, relation: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """(author) Directed relation between two entities with a data dict. Linking again merges the data
        (how a mind refines a `knows` edge: standing, note)."""
        return s.link(source, target, relation, data=data)

    @tool()
    @_wrap
    def unlink(source: str, target: str, relation: str) -> dict[str, Any]:
        """(author) Remove a relation."""
        return s.unlink(source, target, relation)

    @tool()
    @_wrap
    def relate(relation: str, participants: list[str], data: dict[str, Any] | None = None) -> dict[str, Any]:
        """(author) N-ary relation (a faction, a contract, a conversation) with a data dict."""
        return s.relate(relation, participants, data=data)

    @tool()
    @_wrap
    def unrelate(id: str) -> dict[str, Any]:
        """(author) Remove an n-ary relation by id."""
        return s.unrelate(id)

    @tool()
    @_wrap
    def set_rule(entity: str, script: str, kinds: list[str] | None = None) -> dict[str, Any]:
        """(author) Attach a listener script to one entity (a rule for its subtree; on the root, for the whole world)."""
        return s.set_rule(entity, script, kinds=kinds)

    @tool()
    @_wrap
    def clear_rule(entity: str, script: str) -> dict[str, Any]:
        """(author) Detach a rule."""
        return s.clear_rule(entity, script)

    @tool()
    @_wrap
    def schedule(after: float, kind: str, entity: str | None = None, payload: dict[str, Any] | None = None,
                 every: float | None = None) -> dict[str, Any]:
        """(author) An event in the future (world seconds), once or repeating."""
        return s.schedule(after, kind, entity=entity, payload=payload, every=every)

    @tool()
    @_wrap
    def clock(run: bool | None = None, rate: float | None = None, step: float | None = None,
              turn: float | None = None) -> dict[str, Any]:
        """Read the clock; authors set it. run/rate: realtime. step: advance by n world seconds now and return what
        happened. turn: seconds the world moves after each embodied act while paused (turn-based chat play; 0 = off)."""
        return s.clock(run=run, rate=rate, step=step, turn=turn)

    @tool()
    @_wrap
    def act_as(entity: str, verb: str, target: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """(author) Make any entity act without embodying it: the game master's NPC move."""
        return s.act_as(entity, verb, target, params)

    @tool()
    @_wrap
    def say_as(entity: str, text: str, reach: int = 1, to: str | None = None) -> dict[str, Any]:
        """(author) A free line from any entity: what an NPC says when its dialog table has no answer.
        to=<entity> addresses someone here."""
        return s.say_as(entity, text, reach=reach, to=to)

    @tool()
    @_wrap
    def summary() -> dict[str, Any]:
        """Counts, clock and who is embodied in the current world."""
        return s.summary()

    @tool()
    @_wrap
    def mirror(path: str | None = None) -> dict[str, Any]:
        """(author) Write the markdown projection of the world (directories = containment, files = entities)."""
        return s.mirror(path)

    return srv


def serve(args: argparse.Namespace) -> int:
    from .cli import db_path
    db = db_path(args)
    principal = args.as_ or os.environ.get("EMBODY_AS") or "agent"
    caps = []
    if args.author or os.environ.get("EMBODY_AUTHOR"):
        caps.append(AUTHOR)
    if args.observer:
        caps.append(OBSERVER)
    eng = Engine(db)
    session = eng.session(principal, world_id=args.world if args.world and eng.store.get("world", None, args.world) else None,
                          capabilities=caps, name=getattr(args, "name", "") or principal)
    build_server(session, db, eng).run(transport="stdio")
    return 0
