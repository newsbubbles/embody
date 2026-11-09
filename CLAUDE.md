# embody, for the agent reading this

You are connected to embody through the `embody` MCP server (see `.mcp.json`): one main principal called `claude`, with the author capability, plus any extra principals you ask for by name with `principal=` on the playing tools. Everything you can do to a world is one of its tools. There is no LLM inside the engine; you are the imagination, the engine is the bookkeeping.

The `embody` skill (`.claude/skills/embody/SKILL.md`) is the role reference: narrator, author, mind. Read it before you play or build. The short version:

## The loop

1. `worlds()` to see what exists. Empty? `load_world(file="worlds/ferry_at_dusk.py")` loads the sample, or build your own.
2. `join(world_id, entity)` to embody someone, or `use(world_id)` to stand outside as the author.
3. `perceive()` gives the whole bundle: where you are, who and what is here, exits, what you hold, who you know, the verbs you could try and why some are not possible right now, and events since you last looked.
4. `say(text, to=...)` for words (no `to`: said into the room), `act(verb, target, params)` for deeds. `intend` keeps your character's goals, `recall(about=...)` is the graph query around someone within what you may know. A rejection comes back as `{ok: false, reason, hint, alternatives}`. Read the reason, do not retry the same call.
5. The world is turn-based while paused: each act moves it a turn (`elapsed` in the result) and returns everything that touched you since you last looked. `wait(timeout)` blocks until something happens near you and returns a light bundle; `wait(full=true)` for the whole card.

When a person is playing through you: narrate what `perceive` returns in prose, log their words with `say`, turn their intent into one `act`, then stop and let them choose. Never invent state. If the engine says the door is locked, the door is locked. What the world's `policy` calls `fixed` stays fixed; under `fill` you may spawn small things tagged `improvised: true`.

## NPCs

They answer from their dialog tables and act on behaviors on their own. When one needs a mind, give it one: a subagent that calls `join(world, "Mara", principal="mara")`, loops on `wait(principal="mara")`, answers with `say(..., to=..., principal="mara")`, checks `recall(about=...)` before deciding and writes `remember(...)` and `intend(...)`. Or be it yourself for a beat: `perceive(from_entity="Mara")`, `say_as("Mara", text, to=...)`, `act_as("Mara", verb, target)`.

## Building a world

Read `guide()` (docs/SCRIPTING.md) before writing scripts. `worlds/ferry_at_dusk.py` is the worked example of a village (talk, chores, a storyline on facts) and `worlds/glass_reach.py` with `worlds/rules_d20.py` the worked example of a world with rules as verbs (dice, wounds, duels, factions): `define(s)` for scripts and schemas, `populate(s)` for the rest, `build(s)` for a new world. `load_world(file, upgrade=true)` renews a live world's code. `fork_world(source, id)` starts a fresh game on the same state.

## Working on the engine

- `uv sync --all-extras`, then `timeout 120 uv run pytest -q tests` (the suite runs in about two seconds; a hang means a clock bug, so always run it with a timeout).
- Layout: `src/embody/script.py` the interpreter, `store.py` SQLite, `world.py` the graph, events, actions and clock, `ops.py` sessions and capabilities, `mirror.py` the markdown projection, `cli.py` and `mcp_server.py` the two front doors, `tools/watch.py` the read-only live viewer.
- DESIGN.md is the authority on what embody is. ROADMAP.md tracks where it stands. Change them when the design or the state changes.
- Libraries only when they bring a real efficiency gain. The engine depends on nothing but Python; the MCP server is an extra.
- Docs are written without em-dashes.
