"""MCP server: the op table for any MCP-capable harness.

    uv run embody serve --as gm --author

One server process is one principal. Capabilities come from the flags.
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

INSTRUCTIONS = """embody is a deterministic world engine. You are connected as one principal.
Flow: worlds() -> join(world, entity) -> perceive() -> act(verb, target) -> perceive(). Authors build with
define_script / define_schema / spawn / connect and drive NPCs with act_as or perceive(from_entity=...).
Every entity is content (state), code (its components) and ops (its actions): perceive lists what you can do
and why something is not possible right now. Errors tell you what would work instead. Call guide() before
writing scripts."""


def _wrap(fn):
    @functools.wraps(fn)
    def inner(*a: Any, **kw: Any) -> Any:
        try:
            return fn(*a, **kw)
        except Rejected as r:
            return r.to_dict()
    inner.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    return inner


def build_server(session: Session, db: Path):
    from mcp.server.mcpserver import MCPServer

    s = session
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
    def create_world(name: str, seed: int = 0, id: str | None = None, description: str = "") -> dict[str, Any]:
        """(author) Create an empty world with a root entity and the base schemas: entity, place, thing, creature."""
        return s.create_world(name, seed=seed, id=id, description=description)

    @tool()
    @_wrap
    def load_world(file: str) -> dict[str, Any]:
        """(author) Run a world file (a Python module with build(session)) against this engine. Sample worlds live in worlds/."""
        from .cli import load_world_file
        return load_world_file(s, Path(file))

    @tool()
    @_wrap
    def use(world_id: str) -> dict[str, Any]:
        """Point this session at a world without embodying anything (authors, observers)."""
        return s.use(world_id)

    @tool()
    @_wrap
    def join(world_id: str, entity: str) -> dict[str, Any]:
        """Embody an entity (by id or unique name) in a world. Returns your first perception."""
        return s.join(world_id, entity)

    @tool()
    @_wrap
    def leave() -> dict[str, Any]:
        """Release the entity you embody. Its behaviors resume."""
        return s.leave()

    @tool()
    @_wrap
    def perceive(cursor: int | None = None, from_entity: str | None = None, events: int = 30) -> dict[str, Any]:
        """Everything you sense from where you are: place, who and what is here, exits, what you hold, your relations,
        the verbs you could try (with the reason when one is not possible), and events since your cursor.
        Authors and observers may pass from_entity to perceive as any entity (the NPC context bundle)."""
        return s.perceive(cursor=cursor, from_entity=from_entity, events=events)

    @tool()
    @_wrap
    def inspect(entity: str) -> dict[str, Any]:
        """One entity in full: state, contents, relations, actions, schema chain. Must be within reach unless you are an author."""
        return s.inspect(entity)

    @tool()
    @_wrap
    def find(type: str | None = None, name: str | None = None, under: str | None = None,
             parent: str | None = None, state: dict[str, Any] | None = None, limit: int = 30) -> list[dict[str, Any]]:
        """Structured search. type matches the schema chain, name is a substring, under limits to a subtree,
        state matches exact key values. Embodied principals search their own place."""
        return s.find(type=type, name=name, under=under, parent=parent, state=state, limit=limit)

    @tool()
    @_wrap
    def history(since: int = 0, until: int | None = None, kinds: list[str] | None = None,
                touching: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Paged event log. Embodied principals see events that touched them."""
        return s.history(since=since, until=until, kinds=kinds, touching=touching, limit=limit)

    @tool()
    @_wrap
    def act(verb: str, target: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Do a verb, optionally on a target (id or unique name). The only way to change the world on purpose.
        Returns the events it caused, or a rejection with the reason and what would work instead."""
        return s.act(verb, target, params)

    @tool()
    @_wrap
    def act_many(steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Ordered batch of {verb, target?, params?}. Stops at the first rejection and returns what got done."""
        return s.act_many(steps)

    @tool()
    @_wrap
    def say(text: str, reach: int = 1) -> dict[str, Any]:
        """Speak. reach 1 = your place hears it, 2 = the place above too, -1 = the whole world."""
        return s.say(text, reach=reach)

    @tool()
    async def wait(timeout: float = 30.0, kinds: list[str] | None = None) -> dict[str, Any]:
        """Block until an event touches you or your place (or the timeout, max 120 s), then perceive."""
        import anyio
        try:
            return await anyio.to_thread.run_sync(lambda: s.wait(timeout=min(float(timeout), 120.0), kinds=kinds))
        except Rejected as r:
            return r.to_dict()

    # ---- authoring

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
                      listeners: list[dict[str, Any]] | None = None, behaviors: list[dict[str, Any]] | None = None,
                      senses: list[str] | None = None) -> dict[str, Any]:
        """(author) Define or update a type. extends defaults to entity (others: place, thing, creature).
        actions = {verb: {script, doc, targets?, params?, reach?, duration?}}; listeners = [{script, kinds, fn?}];
        behaviors = [{script, every}]; space = {dims, bounds, grid} for places with positions."""
        return s.define_schema(id, extends=extends, doc=doc, state=state, space=space, actions=actions,
                               listeners=listeners, behaviors=behaviors, senses=senses)

    @tool()
    @_wrap
    def schemas() -> list[dict[str, Any]]:
        """(author) All schemas in this world."""
        return s.schemas()

    @tool()
    @_wrap
    def scripts() -> list[dict[str, Any]]:
        """(author) All scripts in this world."""
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
        """(author) Create an entity inside parent. pos only when the parent has a space."""
        return s.spawn(type, parent, name=name, state=state, pos=pos)

    @tool()
    @_wrap
    def patch(entity: str, changes: dict[str, Any]) -> dict[str, Any]:
        """(author) Merge changes into an entity's state."""
        return s.patch(entity, changes)

    @tool()
    @_wrap
    def move(entity: str, parent: str, pos: list[float] | None = None) -> dict[str, Any]:
        """(author) Reparent an entity."""
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
        """(author) Directed edge of any relation (knows, owes, guards, connects_to...)."""
        return s.link(source, target, relation, data)

    @tool()
    @_wrap
    def unlink(source: str, target: str, relation: str) -> dict[str, Any]:
        """(author) Remove edges of that relation between the two."""
        return s.unlink(source, target, relation)

    @tool()
    @_wrap
    def relate(relation: str, participants: list[str], data: dict[str, Any] | None = None) -> dict[str, Any]:
        """(author) N-ary relation (a faction, a contract, a party) among several entities."""
        return s.relate(relation, participants, data)

    @tool()
    @_wrap
    def unrelate(id: str) -> dict[str, Any]:
        """(author) Remove an n-ary relation by id."""
        return s.unrelate(id)

    @tool()
    @_wrap
    def set_rule(entity: str, script: str, kinds: list[str] | None = None) -> dict[str, Any]:
        """(author) Attach a listener script to one entity. It sees every event bubbling through its subtree.
        kinds default to ["before_act"]; a rule calls ctx.reject(reason, hint) to forbid an action."""
        return s.set_rule(entity, script, kinds)

    @tool()
    @_wrap
    def clear_rule(entity: str, script: str) -> dict[str, Any]:
        """(author) Detach a rule."""
        return s.clear_rule(entity, script)

    @tool()
    @_wrap
    def schedule(after: float, kind: str, entity: str | None = None, payload: dict[str, Any] | None = None,
                 every: float | None = None) -> dict[str, Any]:
        """(author) Fire an event in `after` world seconds (repeating every `every`). Listeners can react to it."""
        return s.schedule(after, kind, entity=entity, payload=payload, every=every)

    @tool()
    @_wrap
    def clock(run: bool | None = None, rate: float | None = None, step: float | None = None) -> dict[str, Any]:
        """World time. Read with no arguments. (author) run=true/false starts or pauses realtime, rate scales it,
        step advances by that many world seconds now and returns what happened."""
        return s.clock(run=run, rate=rate, step=step)

    @tool()
    @_wrap
    def act_as(entity: str, verb: str, target: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """(author) Make any entity act, without embodying it. How a game master drives an NPC."""
        return s.act_as(entity, verb, target, params)

    @tool()
    @_wrap
    def summary() -> dict[str, Any]:
        """Counts, clock and principals of the current world."""
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
    build_server(session, db).run(transport="stdio")
    return 0
