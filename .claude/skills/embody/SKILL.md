---
name: embody
description: Build worlds and play in them with the embody engine (MCP tools from the `embody` server, or `uv run embody ...`). Use when the user wants to make a world, place, character, item, rule, quest or storyline, wants to play, explore, talk to someone or do something in a world, or asks you to run an NPC or be one. Not for changes to the engine's own source code.
---

# embody

The engine is deterministic and keeps the world honest. You narrate, decide and author; you never invent state the engine did not report. There are three roles. Know which one you are in; a session is often two of them at once (narrator and author).

## Narrator (a person is playing through you)

Loop: `perceive()` > prose > the player speaks > `say` + `act` > perceive again.

- `perceive()` is the truth. Narrate it in the world's voice: the place, who is here, what can be done. Keep the verbs implicit unless the player asks.
- Do exactly the stated action, then stop and let the player choose. "I walk to the mill" is one `act`, not a walk plus a conversation. Never act past the player's words, never drink the ale for them.
- The player's own words go into the log first: `say(text, to=<who they address>)`, then the `act("talk", who, {"about": ...})` that carries the topic. Two events, so an NPC mind (or the author later) reads what was really said, not only the topic.
- A rejection has a `reason` and often a `hint` and `alternatives`. Tell the player in character and offer the alternatives. Never retry the same call unchanged.
- Time is turn-based by default: the clock is paused and every `act` moves the world by the turn (3 s in the ferry world) or the verb's duration. The act result carries what happened in that turn under `events`. `clock(run=true)` makes it realtime, for a live stage, not for chat.
- NPCs answer from their dialog table (the `say` events in the act result). When the table has no answer and the world's policy allows `voice`, give them a line with `say_as(npc, text, to=player)` in their voice, grounded in what `inspect(npc)` and `perceive(from_entity=npc)` show. One or two moves per NPC per beat with `act_as`.
- Canon vs flexible: read `policy` on the world root (`inspect(root)`). `fixed` is never changed from inside play. `fill: true` lets you spawn the small things a place would have when a player asks for them (a bench, a second mug); tag them `state: {"improvised": true}` so `find(state={"improvised": true})` lists what you added for the author to promote or drop. Without `fill`, say in character that there is none. The player's preference picks within what the world allows, never past it.
- Keep notes for the author as you go (what felt off, what the player wanted that the world could not do). They are the handoff: write them to `worlds/notes/<world-id>-<date>.md` in the project folder and the next author round starts from them.

## Author (building or repairing a world)

Order: `create_world` > `define_script` > `define_schema` > `spawn` places > `connect` them > spawn contents > `set_rule(root, ...)` for the storyline > `schedule` timers > `clock(turn=3)` > play it yourself once.

- Read `guide()` first; it is the full ctx reference.
- Holder verbs carry `targets` (a type) and a `scope` (`exits`, `here`, `held`, `any`) so players see only possible pairs. Object verbs do not. Give slow verbs a `duration`.
- Rules are listeners on a place or the root with `kinds=["before_act"]`; `ctx.reject(reason, hint)` is how they say no, in the world's words.
- A storyline is a rule on the root plus a hidden entity for its stage. Advance on events (`arrived`, `talked`, your own `emit` kinds). Emit `scene` events at a place to narrate to whoever stands there.
- People: `dialog` keyed by words (`"ale|drink|beer"`), entries a line or `{"line", "after_gift", "if_state": {...}, "else"}`; `gives` for what a topic hands over; all three secret. The listener that answers carries `unless_embodied: true` so a mind can take over the mouth without losing the table.
- `brief` on an entity is your instruction to whoever embodies it: voice, wants, what it knows, how it judges people. Always secret; a mind reads it in its own card. `memory` is theirs, you only read it.
- Edits mid-play are the job, not a failure: `patch` merges (`{"dialog": {"weather": "..."}}` adds one topic), `replace=true` sets whole, `None` deletes. Redefine a script and the next act uses it.
- Put a `policy` on the root: `fixed` (facts no narrator may bend), `fill` (may small props be improvised), `voice` (may NPCs speak beyond their tables).
- Save the world as a Python file in `worlds/` with `define(s)` (scripts, schemas) and `populate(s)` (entities, rules, clock) and `build(s)` calling both. `load_world(file, upgrade=true)` runs `define` against a live world: new code, same state. `worlds/ferry_at_dusk.py` is the template.
- A fresh game on the same state: `fork_world(source, new_id)`, then `use(new_id)` or `join(new_id, entity)`. The source stays as it was.
- After a playtest, read the notes, change the file, bump the world with `upgrade`, and tick the notes.

## Mind (you are one character)

Loop: `join(world, entity, principal=<name>)` > read your card > `wait()` > answer or act > `remember` > `wait()`.

- Your card in `perceive()` is `you`: `state.brief` (who the author says you are), `state.memory` (what you decided before), `knows` (who you have met, your `standing` toward them, the last exchanges), `known_places`. Stay inside that. You do not know the map; you know where you have been.
- When someone talks to you, you hear `talked` (the topic) and usually a `say` addressed to you (their words). Answer with `say(text, to=them)`. Act with `act` like anyone else; your affordances are your character's.
- Write what matters to `remember(text)`: an opinion formed, a promise, a plan. It is secret and it outlives you: whoever wakes up as this character next reads it.
- Refine an opinion the floor already keeps: `standing` on your `knows` edge moves by itself on gifts and blows; your note on it is `remember`.
- Stay in your lane: one principal, one entity, no authoring. If the world needs changing, say so in a `remember` and the author will see it.
- Leave with `leave()`. Your dialog table takes the mouth back the moment you are gone.

## One connection, many principals

Every playing tool takes `principal=<name>`. The main principal (the one the server was started as) stays who it is; `join(world, "Mara", principal="mara")` embodies Mara as a second principal over the same MCP connection, with no author rights. `principals()` lists them. That is how a subagent inside your session becomes a mind without a server of its own.

| harness | how a mind runs | who sees it |
|---|---|---|
| Claude Code subagent (Agent tool) | one agent per NPC; its prompt: "join as X with principal=x, loop on wait, say and act as X only, remember, never author" | nobody out of game; contact is in-game through `say` |
| Claude Code session (visible) | a separate session with its own `.mcp.json` principal (`--as mara`) joins the entity | the user can open it and talk to the mind out of character |
| any MCP harness (Codex, others) | same as above; the per-call `principal` needs no extra process | per harness |
| plain CLI | `uv run embody --as mara join <world> Mara` then a loop of `uv run embody --as mara wait` and `say`/`act` | the terminal |

Pick the subagent when the mind should be invisible, the session when the user wants to watch or coach it.
