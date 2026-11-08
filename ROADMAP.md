# embody roadmap

DESIGN.md says what embody is. This file says where it stands against that and what comes next. It is the tracking document: every gap found in play and every direction agreed in design talks lands here, with a status, until it is done or dropped.

Status: alpha. The first vertical slice was built in one day (2026-11-08) and played the same evening. It works end to end but it is not at production level and not at its final vision. Treat it as a working prototype with a known destination.

## The vision in five lines

1. Anyone clones it, runs it with the agent they already use, and starts building and playing at once.
2. The engine is the bookkeeping; the agent is the imagination. No LLM inside the engine.
3. A mind lives in the engine, not in an agent's context. Any agent that wakes up as Mara gets the same Mara.
4. Worlds grow from play. What a narrator improvises is logged, reviewed and promoted to canon by the author, or dropped.
5. Every harness is a first-class door: MCP, CLI, library. Instructions are written in engine terms with a per-harness table.

## What exists (2026-11-08)

- Engine: entity graph with containment, schemas with `extends`, actions with check and apply, events that bubble with reach, listeners along the bubble path, behaviors on the clock, rules via `set_rule`, relations as edges and hyperedges, event-sourced SQLite, deterministic state hash, seeded rand, a Python-subset interpreter for scripts.
- Ops: 39 of them behind a Session with capabilities (author, observer, embodied). CLI and MCP server expose the same table. `wait` blocks on events. The MCP server holds many principals behind one connection (`principal=` on the playing tools).
- Minds in the engine: secret `memory` and `brief`, per-entity cursors, `knows` edges with an opinion floor and the last exchanges, `known_places`, addressed speech (`say(to=...)`, `say_as`), `fork_world`, turn-based play (`clock(turn=n)`), deep-merging `patch`, scoped affordances.
- Content: `worlds/ferry_at_dusk.py` (three places, four NPCs, storyline on rails, fog on a timer; split into define/populate so a live world takes new code), `worlds/two_rooms.py`.
- Tooling: 41 tests, markdown mirror, `tools/watch.py` live graph viewer with zoom, pan and a world switcher, CLAUDE.md and an `embody` skill with the three roles for Claude Code.

## Found in the first playtest

Source: PLAYTEST_NOTES.md (the game master's notes) and the watch session. Each line is a defect or a gap with the fix we intend.

Bugs

- [x] (round 2, 2026-11-08 "engine: minds, forks, turns, principals") Observers cannot `inspect`: the engine grants full reads only to authors. Observers should read everything, write nothing.
- [x] (round 2) `destroyed` events carry the actor as `target` and the destroyed id only in the payload. `target` should be the destroyed entity.
- [x] (round 2) `embodied` event payload uses the key `kind`, which collides with the event's own kind. Rename to `as`.
- [x] (round 2, `scope` on holder verbs) Affordances list impossible pairs: `go` to the place you stand in, `drop` on things you do not hold, `take` on the unportable. Filter them out, keep the reasons for the near misses.
- [x] (round 2, ferry world) A player's `perceive` shows other people's whole `dialog` table. People's `dialog`, `gives` and `gave` are secret by default.
- [x] (round 2) `patch` replaces nested dicts whole, so adding one dialog topic resends all of them. Deep merge for dict values, with an explicit replace option.
- [x] (round 2, ferry world) Dialog topic match is `key in topic`, so `ale` matches `tale`. Match whole words, and let one entry serve several keys.

Gaps

- [x] (round 2, `say_as` with `to`) No engine-backed way for an NPC to speak a free line. Add `say_as(entity, text)` for authors, or let `act_as` take `say`.
- [x] (round 2, `say(to=...)` + narrator rule in the skill) The player's own words never enter the log; only the topic does. The narrator should `say` the player's line, then act. Two events.
- [x] (round 2, ferry world: talk 2 s, go 5 s, drink 3 s; turn-based play makes every act a turn) `talk` has no duration, so a conversation takes no world time.
- [ ] An engine-level default duration per verb is still open; today the world sets it.
- [x] (round 2, `clock(turn=3)` paused by default in the ferry world; `Session.act` steps the turn) A world loads with the clock running. In chat play, typing time is world time. Default to paused for chat play; the author or narrator starts it.
- [x] (round 2, ferry world `PERSON_ON`: `line`, `after_gift`, `if_state`, `else`) Dialog entries are static. Allow entries conditioned on state (`if_gave`, `if_friend`, else) so an NPC can answer differently after something changed.
- [ ] No money in the ferry world. That is a world choice, not an engine gap, but the base schemas could offer a `coin` convention.
- [ ] Prose points at things that do not exist (the bench, the well). Round 2 spawned the bench and the well in the ferry world; the lint is still open. Add an authoring lint that flags names in dialog and descriptions that match no entity, so the author decides: spawn it or keep it scenery.

## Directions from the design talks

These were agreed in conversation on 2026-11-08 and are not built. Order of attack is at the end.

### Minds live in the engine

- [x] (round 2) Secret `memory` on every entity, appended by a `remember(text)` op that logs a `remembered` event. The embodying agent keeps its character here: who you are, what you want, what you decided.
- [x] (round 2, in world meta so hashes are unchanged) A cursor per entity, so an NPC's "events since I last looked" is its own, not the game master's.
- [x] (round 2, in every perceive) A `knows` section in `perceive(from_entity=...)`: for each non-passage edge, the edge data (standing, note) plus the last few exchanges between the two, pulled from the log. The log stays the single source of truth.
- [x] (round 2, engine hook in `emit`, off with meta `opinion_floor: false`) Opinion with a deterministic floor: a small engine listener nudges `standing` on an edge on `given`, `attacked`, `talked`. A mind refines it by patching the edge.
- [x] (round 2, always secret, shown in the embodier's own card) A secret `brief` on an entity: the author's instructions to whoever embodies it (voice, wants, what it knows, how it judges people). The mind reads it in its bundle. Harness-agnostic by construction.
- [x] (round 2) Partial world knowledge: `known_places` derived from the entity's own `moved` events.
- [ ] An `overheard` tail of events that reached its place while it was not looking. A mind gets a worldview without a map.

### Canon and what is flexible

- [x] (round 2, ferry world `POLICY`, read by the narrator per the skill) A policy on the world root: `fixed` (places, people, storyline beats, named facts), `fill` (props of daily life the narrator may spawn on request), `voice` (whether NPC minds may speak beyond their dialog table). The player's preference picks within what the world allows, never past it.
- [x] (round 2, convention in the skill; `find(state={"improvised": true})` lists them) Everything improvised is tagged `improvised: true` with the narrator as actor in the event. One query lists a session's improvisations so the author can promote them into the world file or drop them.

### Roles in the skill

- [x] (round 2) Split the `embody` skill and CLAUDE.md into three role references: narrator for a player, author, NPC mind. Each with its loop, its privileges and what it writes down.
- [x] (round 2) Narrator rule: do exactly the stated action, then stop and let the player choose. Never act past the player's words.
- [x] (round 2, `worlds/notes/<world-id>-<date>.md`) Notes as handoff: a playtest writes notes, the author reads them and changes the world file, the next play starts from a better world. Make the file and its shape a convention.
- [x] (round 2, skill: the mind role and the per-harness table) A mind is a principal that joins an entity and loops on `wait`. Write it in engine terms, then a per-harness table: Claude Code subagent (invisible, in-game contact only), Claude Code session (visible, can be talked to out of character), Codex, plain CLI loop.

### Many principals, one server

- [x] (round 2, `Hub` in mcp_server.py; the argument is `principal`, since `as` is a Python keyword; extra principals never get author rights) One MCP server process is one principal today, so a subagent inside a session shares the `claude` principal and cannot `join` an NPC, only drive it with `act_as`.

### Workspace, not repo

- [ ] The engine is a package; the repo is its source. A workspace is any folder with a database and world files. `embody init` makes one; the MCP server in that folder uses it; `.mcp.json` points at the workspace.
- [ ] Sample worlds ship inside the package, so `load_world("ferry_at_dusk")` works from any workspace without a path.
- [ ] World state is never in the engine repo. Already true (databases, mirrors and session files are ignored); keep it true after the split.

### Later

- [ ] Stock verbs on the base schemas (go, take, drop, give, say) as an opt-in, so a sketch world plays without defining physics first.
- [ ] Spatial layout beyond containment: positions and distance exist, nothing uses them yet.
- [ ] PyPI release as `embody-engine`, after the workspace split.

### Fresh games on old states

- [x] (round 2) `fork_world(source, id)`: a copy with its history, nobody embodied, `meta.forked_from`, a `forked` event on the new root. The viewer shows the fork lineage and switches worlds.
- [x] (round 2) `load_world(file, upgrade=true)` runs a world file's `define(s)` against a live world: new scripts and schemas, same entities and log.

## Order of attack

1. (done, round 2) Fix pass, minds in the engine, roles in the skill, canon policy, many principals, forks.
2. Second playtest on the forked ferry world with turn-based play and a subagent mind for Mara. New gaps go under "Found in play".
3. The lint for names in prose that match no entity; an engine default duration per verb; the `overheard` tail.
4. Workspace split (`embody init`, sample worlds inside the package), then the release.

## How this file is kept

A box is ticked in the commit that closes it, with the commit named beside it. New gaps from play go under "Found in play" with the date. Directions that change go in DESIGN.md first, then here.
