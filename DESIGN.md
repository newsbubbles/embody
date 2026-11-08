# embody: design

Status: pre-alpha, the first vertical slice is being built. This document is the authority on what embody is. The README is how to use it.

## 1. What it is

A deterministic world engine for agents. A server holds one or more worlds. A world is a hierarchical entity graph: a root entity, locations inside it, things and characters inside those. Every entity has a type, state, and actions. Every change to a world is an action. Every action emits events that propagate up the tree. Anyone, human or agent, participates by embodying an entity through whatever harness they already use: MCP, the CLI, or the Python library.

The engine stores, validates and steps world state. It does not narrate, plan, roleplay or judge. Those jobs belong to whoever is connected. There is no LLM inside the engine.

The short way to say it: Unity for text and logic games, where the editor is an agent.

## 2. Why this shape

Large language models are bad at keeping track of world state and only passable at roleplay. They are good at deciding what to do when the state is handed to them in a bounded, well-shaped bundle, and good at writing small pieces of code. So the engine does the bookkeeping deterministically and gives agents operations ("ops") that are decision-sized. A weaker model with good ops beats a stronger model with a vague prompt.

The predecessor (adventuremode 2, private) put the LLM inside the loop: prompt chains built entities, narrated, classified intent, and were meant to generate action code at runtime. The code generation never ran. Everything an LLM did there is either an op here or belongs to the connected agent.

## 3. The DOM, taken seriously

Building a world engine by hand keeps recreating the browser DOM. embody borrows its whole shape.

| DOM | embody |
|---|---|
| `document` | world root entity |
| element tree | containment tree: world > region > location > container > item |
| element type, prototype chain | schema with `extends` |
| attributes | entity `state` |
| methods | actions |
| events, bubbling | world events bubbling up the containment tree |
| event listeners | listeners attached to entities, scoped to their subtree |
| CSS cascade | rules: a location overrides the world's defaults for everything inside it |
| script components | behaviors (run on the clock) |
| `querySelector` | `find` over type, state, relation |
| MutationObserver | subscriptions for embodied principals |
| the browser | the harness someone connects with |

Perception is bubbling. A sound in a room is an event on the room; it bubbles to the building and the region; anything embodied under those nodes with the right sense receives it. Walls, range and darkness are filters on the path.

Rules are the cascade. "No combat in the tavern" is a listener on the tavern that rejects attack actions in its subtree.

## 4. Data model

Borrowed from hypermemory's graph: nodes, binary edges, hyperedges, each with a typed data dict.

- **Entity**: `id`, `world_id`, `type`, `parent_id`, `state` (dict), `pos` (position in the parent's space, optional), `version`, timestamps.
- **Edge**: `id`, `source`, `target`, `relation`, `data`. Containment is `parent_id`, not an edge, for cheap subtree queries. Everything else is an edge: `connects_to`, `knows`, `owns`, `member_of`, `hostile_to`.
- **Hyperedge**: `id`, `relation`, `participants[]`, `data`. For n-ary facts: a conversation, a trade, a fight, a treaty.
- **Schema**: `id`, `extends`, `state` (defaults and allowed keys), `space` (optional, see section 8), `actions{}`, `listeners[]`, `behaviors[]`, `senses[]`.
- **Script**: `id`, `kind` (action, listener, behavior), `source`, `version`. Scripts are rows. See section 6.
- **Event** (append-only log): `seq`, `world_id`, `t`, `kind`, `actor_id`, `target_id`, `payload`, `caused_by`. World state is a projection of the log. Replaying the log reproduces the state exactly; that is the determinism test.
- **Principal**: a connected party. `id`, `kind` (human, agent, oracle, script), `capabilities[]`, `embodied_entity_id`.

Every reference is an id. No names as keys, no back-pointers in objects.

Example, a door that opens a path: `open(door)` has precondition `not door.state.locked`, effects `door.state.open = True` and `link(hall_a, hall_b, "connects_to", via=door)`. `go(hall_b)` exists only while that edge exists. Actions rewire the graph, which changes which actions exist next.

## 5. Components: actions, listeners, behaviors

Code attaches to entities through their schema, the way components attach to GameObjects.

- **Action**: a verb with `check(ctx)` (preconditions) and `apply(ctx)` (effects). Triggered directly by `act`.
- **Listener**: `on(ctx, event)`, runs when an event bubbles past the entity. Rules, traps, storyline stages, a barkeep's deterministic greeting.
- **Behavior**: `tick(ctx)`, runs on the world clock at the schema's interval. A monster's wander, fire spreading, a market repricing.

Embodiment is a controller swap. An unembodied monster is driven by its behaviors. When a principal embodies it, behaviors yield and the principal drives. When the principal leaves, behaviors resume.

Turn-based pockets inside a realtime world: a combat scene is an entity. Its listener, scoped to its subtree, admits only the current actor's actions, advances turn order per action, and fires the monster's behavior on its turn. Outside the scene the world keeps running.

## 6. Scripts: a subset of Python the engine runs itself

Scripts are written in Python syntax and executed by embody's own AST interpreter. Nothing is passed to `eval` or `exec`. The interpreter supports: literals, names, arithmetic and comparison, boolean logic, `if`, `for` over lists and dicts, `while` (fuel-limited), function definitions, calls to the engine API and to a small set of builtins (`len`, `min`, `max`, `abs`, `int`, `str`, `sorted`, `range`), f-strings, list and dict literals, indexing, attribute access on engine objects only. No imports, no classes, no `with`, no `try`, no dunder access, no global mutation, no IO, no wall clock.

Determinism: randomness comes from `ctx.rand`, seeded from the world seed and the event sequence number, so a replay reproduces every roll. Every script run has a fuel budget; a script that runs out is rejected with the reason, and the action fails cleanly.

Why not Lua or Starlark: both work and both installed in an hour. Both are a native dependency and a second language that agents write Python-isms into. A tree-walking interpreter over a Python subset is a few hundred lines we own, agents write real Python, safety is by construction, and the subset is small enough to port to another host language later.

The engine API inside a script is the same op table agents get (query, patch, spawn, link, unlink, emit, schedule, destroy), minus perception rendering. A script is an agent without an LLM.

## 7. Ops: the agent surface

One control-complete set. Bounded output. Errors that point forward.

Embodied:

| op | purpose |
|---|---|
| `worlds()` | worlds a principal may join |
| `join(world, entity)` | embody; returns a perception bundle |
| `perceive(cursor?)` | the bundle: breadcrumb, who and what is here (sense-filtered), exits and their state, inventory and own state, events since the cursor, relationships with those present, affordances with preconditions already evaluated |
| `inspect(entity)` | one entity in full, as seen from here |
| `act(verb, target?, params?)` | the only mutation. Returns the events it caused, or a forward error |
| `act_many([...])` | ordered batch, stops at first rejection with the partial result |
| `wait(filter?, timeout)` | block until an event touches my bubble path |
| `history(filter, window)` | paged event log |
| `find(query)` | structured graph query, never vector search |

Author (needs the `author` capability):

| op | purpose |
|---|---|
| `define_schema`, `define_script` | types and code, versioned |
| `spawn`, `patch`, `destroy` | entities |
| `link`, `unlink`, `relate` | edges and hyperedges |
| `set_rule` | attach a listener to an entity |
| `clock(run \| pause \| step \| rate)` | world time |
| `mirror()` | regenerate the markdown projection |

Observer: `perceive` from any entity, `history`, `find`, no mutation.

Error shape, every time: why it failed, what is true instead, what would make it possible. "`go(hall_b)` rejected: no path from hall_a. `open(door_7)` is available to you and would connect them."

The `perceive` bundle is the NPC subagent's entire context. Paired with `wait`, an NPC costs nothing while nothing happens near it, and wakes with the diff.

Lazy world building: an entity can carry `state.fidelity = "sketch"`. When an embodied principal approaches a sketch, the engine emits `approach_sketch`. An author-privileged agent subscribed to it fills the place in before the player arrives. The engine only emits and stores.

## 8. Space: the transform hierarchy

Every container may declare a `space`: `dims` (0 to 3), `bounds`, `units`, `grid` or continuous. Every child carries `pos` (and optional `facing`) in its parent's space. Zero dims is a text room where reach means "same parent." Two dims is a tactical grid. Three is a stage. `connects_to` edges carry an anchor position on each side so a map assembles itself from the graph.

Reach, line of sight and hearing become distance checks when a space exists and fall back to peers when it does not, so the same action scripts work in a text room and on a grid. Rendering to a tilemap, glTF or Blender is a client concern.

Slice scope: `space` and `pos` generic from the first schema; zero dims and 2D grid implemented; 3D later, as a number not a rewrite.

## 9. Storylines

A storyline is an entity outside the containment tree (under the world's `storylines` branch), hidden from embodied principals, visible to author and observer. It holds stages; each stage is a listener with a condition over events and state and effects applied as the storyline's own principal: spawn the ghost, unlock the gate, emit a `rumor` event in the tavern so the barkeep hears it. Open world is everything the rails do not touch. The GM agent can author or bend storylines live with the same ops.

## 10. Time

A world clock runs continuously, at a configurable rate, pausable and steppable. Actions have durations: `act` applies instant effects now and schedules a completion event at `t + duration`. Scheduled events are rows; the clock delivers them. Behaviors run at their interval. Everything the clock does is an event in the log, so replay is still exact.

## 11. Persistence

Event log plus projections in SQLite. One world is one file; copy it to share it. The schema is plain SQL so a Postgres backend for shared worlds is a driver, not a redesign. One writer per world (an action queue) keeps determinism without locks. Snapshots every N events so joining does not replay history. Subscriptions are filtered by bubble path; a client never receives the whole world.

## 12. Markdown mirror

Every world projects to a read-only directory: containment is directories, each entity is a markdown file with its state, relations and the verbs available on it. Regenerated on change. Agents read it with their normal file tools; writes go only through `act`. Committed mirrors give a world a git history for free.

## 13. Oracles and authority

An external system (webhook, sensor, feed) is a principal of kind `oracle` embodying an entity whose actions are "report X". World listeners decide what a report means. Representation, observation and authority are separate grants: an entity standing for a real server is just a node, reading its telemetry is a sense, acting on the real server is an action gated by a capability.

## 14. The slice

1. Core library: schemas, graph, scripts, actions, events, bubble, SQLite. A test world of two rooms, a door, a key. Replay test.
2. Clock, durations, behaviors, a combat pocket.
3. `perceive`, `wait`, markdown mirror.
4. CLI and MCP server. Repo ships `.mcp.json` and `CLAUDE.md` so a clone plus `claude` is the whole setup.
5. Sample world: three full locations, NPCs with goals, one storyline. Claude Code as author and as the player's textual interface, subagents embodying NPCs.
6. Postgres, oracles, outward hooks: after the slice plays.
