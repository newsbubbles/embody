# embody, for the agent reading this

You are connected to embody through the `embody` MCP server (see `.mcp.json`): one principal called `claude`, with the author capability. Everything you can do to a world is one of its tools. There is no LLM inside the engine; you are the imagination, the engine is the bookkeeping.

## The loop

1. `worlds()` to see what exists. Empty? `load_world(file="worlds/ferry_at_dusk.py")` loads the sample, or build your own (below).
2. `join(world_id, entity)` to embody someone, or `use(world_id)` to stand outside as the author.
3. `perceive()` gives the whole bundle: where you are, who and what is here, exits, what you hold, the verbs you could try and why some are not possible right now, and events since you last looked.
4. `act(verb, target, params)` is the only way to change the world on purpose. A rejection comes back as `{ok: false, reason, hint, alternatives}`. Read the reason, do not retry the same call.
5. `wait(timeout)` blocks until something happens near you, then perceives.

When a person is playing through you: narrate what `perceive` returns in prose, in the world's voice, and turn what they say into `act` calls. Never invent state. If the engine says the door is locked, the door is locked.

## Running NPCs

Non-player characters already act on their own through behaviors (the dog follows, the miller wanders). When one needs a mind, you are it: `perceive(from_entity="Mara")` is her context bundle, `act_as("Mara", "talk", "Traveler", {"about": "..."})` is her move. Keep NPC turns short and in character. Subagents can do this in parallel: give each one the entity it plays and the rule "perceive from it, act as it, nothing else".

## Building a world

Read `guide()` (docs/SCRIPTING.md) before writing scripts. The order that works:

1. `create_world(name, seed)`.
2. `define_script(id, source)` for each verb, rule, behavior and the storyline. Scripts are a Python subset run by the engine. An action has `check(ctx)` and `apply(ctx)`; a listener has `on(ctx, event)`; a behavior has `tick(ctx)`.
3. `define_schema(id, extends, state, actions, listeners, behaviors, space)`. A verb with `targets` is the holder's (go targets a place); a verb without `targets` belongs to the object (open on a door).
4. `spawn` places under the root, `connect` them (optionally `via` a door), spawn things and people inside.
5. `set_rule(root, "story", kinds=[...])` for a storyline that must hear everything; keep its stage on a hidden entity.
6. `schedule` timed events, `clock(run=true)`, then `join` and play it yourself before handing it to anyone.

`worlds/ferry_at_dusk.py` is the worked example: three places, four NPCs, a storyline on rails, fog on a timer. Copy its shape.

## Working on the engine

- `uv sync --all-extras`, then `timeout 120 uv run pytest -q tests` (the suite runs in about a second; a hang means a clock bug, so always run it with a timeout).
- Layout: `src/embody/script.py` the interpreter, `store.py` SQLite, `world.py` the graph, events, actions and clock, `ops.py` sessions and capabilities, `mirror.py` the markdown projection, `cli.py` and `mcp_server.py` the two front doors.
- DESIGN.md is the authority on what embody is. Change it when the design changes.
- Libraries only when they bring a real efficiency gain. The engine depends on nothing but Python; the MCP server is an extra.
- Docs are written without em-dashes.
