---
name: embody
description: Build worlds and play in them with the embody engine (MCP tools from the `embody` server, or `uv run embody ...`). Use when the user wants to make a world, place, character, item, rule, quest or storyline, wants to play, explore, talk to someone or do something in a world, or asks you to run an NPC. Not for changes to the engine's own source code.
---

# embody

The engine is deterministic and keeps the world honest. You narrate, decide and author; you never invent state the engine did not report.

## Playing

- `perceive()` is the truth. Narrate it in the world's voice: the place, who is here, what can be done. Keep the list of verbs implicit in the prose unless the player asks.
- Turn what the player says into `act(verb, target, params)`. Ambiguous? Pick the most likely and say what you did.
- A rejection has a `reason` and often a `hint` and `alternatives`. Tell the player in character and offer the alternatives. Never retry the same call unchanged.
- Time runs. After an action with a `duration`, or when NPCs should get a move, `wait(timeout)` or `clock(step=n)` (author only), then perceive again.
- NPC minds: `perceive(from_entity=<npc>)` then `act_as(<npc>, verb, target, params)`. One or two moves per NPC per beat. Behaviors already cover their routine.

## Authoring

Order: `create_world` > `define_script` > `define_schema` > `spawn` places > `connect` them > spawn contents > `set_rule(root, ...)` for the storyline > `schedule` timers > `clock(run=true)` > play it yourself once.

- Read `guide()` first; it is the full ctx reference.
- Holder verbs carry `targets` (a type). Object verbs do not. Perception pairs them for the player automatically.
- Rules are listeners on a place or the root with `kinds=["before_act"]`; `ctx.reject(reason, hint)` is how they say no. Put the reason in the world's words.
- A storyline is a rule on the root plus a hidden entity for its stage. Advance on events (`arrived`, `talked`, your own `emit` kinds). Emit `scene` events at a place to narrate to whoever stands there.
- Secrets: list state keys in `state.secret` and only the entity itself (or an author) sees them.
- Build at sketch fidelity first (names, descriptions, exits), play it, then deepen the places people actually enter.
- Save authored worlds as a Python world file in `worlds/` with `build(session)` so they can be reloaded with `load_world`. `worlds/ferry_at_dusk.py` is the template.
