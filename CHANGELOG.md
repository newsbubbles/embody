# Changelog

What changed in the engine, newest first: the core, the ops, the server and the packs. A world's own story lives in its folder (`worlds/<id>/notes/`) and its event log, not here. Every entry names what an agent or a host sees differently.

The version in `pyproject.toml` is 0.1.0 until the first release; until then entries go by date.

## Unreleased

- Character notes are on the server, and a player's agent is told so. `remember`, `intend` and `recall` were always player ops; the invite page and the join briefing now say to keep notes there, not in files on the agent's side. A guest's note is at most 2000 characters.

## 2026-11-10

- A hosted world lives while nobody plays. The clock keeps real time. A seat whose holder (player or mind) has done nothing for the world's `idle_after` is idle, and the body's behaviors marked `idle` run on it (d20 `quench`: a held body drinks when thirsty). An act or a line said marks the seat in use; waiting does not. `principal.acted_t` records it in world time.
- `packs/d20/soak.py`: run a world for days with every seat held and idle, and see who went dry and which sources ran out. Exit code 1 when thirst put anyone down.
- Glass Reach routines (content, not engine): the Keth water run at dusk under the truce, the Guild crawler at dawn. Players can interrupt both.
- `wait(until=...)`: `present` and `came()` are people and creatures, not things.
- A resting clock (the world pauses when no player has acted) was built, committed and never deployed; the steady clock replaced it.

## 2026-11-09

- `wait(until=...)`: a condition in the script subset over what the grant may know (`t`, `ambient`, `here`, `present`, `me`, `events`, `heard`, `did`, `came`, `state`). The cursor does not move until it fires. Observers may wait.
- `embody watch`: a shell watcher over a hosted door or the local database, in 50 s pieces, reconnecting and rejoining, for hours. Prints FIRED, TIME UP or REFUSED.
- Invites are links: `/i/<code>` hands the agent its token and a brief, once, for a day.
- Hosted bodies: a pace per world (`set_pace`), no tick rows in the log, thirst with a floor (it puts a body down, never kills), a walk to known water.
- `leave_word`: a message left with someone here for someone who is not.
- Owner grants work over the door; `last_used` is written; file paths stay inside the workspace; a guest sees its own role.
- Hosted worlds: roles (owner, author, narrator, player, mind, observer), grants, the HTTP door, seats, templates, `claim_lapse`, the viewer behind the door, the Railway container.
- Worlds are folders: a workspace with `worlds/` and `packs/`, scripts as files, live authoring recorded to the folder (`changes.jsonl`), save and restore, forks.
- One clock across processes; located witnessing; `act` carries the news.

## 2026-11-08

- Minds in the engine: secret `memory` and `brief`, a cursor per entity, `knows` with an opinion floor, `known_places`, goals with `intend`, `recall`.
- Forks, turns, principals, private feeds, timers.
- The first slice: the script interpreter, the SQLite store, the world graph with actions, events, rules and the clock; sessions and the perceive bundle; `wait`, `act_many`, capabilities, spaces; the CLI and the MCP server; the markdown mirror; the live graph viewer.
