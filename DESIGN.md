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

Rules are the cascade. "No combat in the tavern" is a listener on the tavern that rejects attack actions in its subtree. A rule installed on an entity hears every event under it, whatever the reach the emitter chose: a rule on the root is the table's rule. Schema listeners hear only what bubbles past them.

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

Every entity is three things at once: content (its state), code (its components) and ops (its actions, as seen by whoever stands near it). Perceiving an object means seeing what you can do with it, with each precondition already evaluated. The world is a tree of scoped, constrained ops, and the agent is the bridge between those ops and the outer world. An action with `targets` (a type) is the holder's own verb, done to something of that type: `go` targets a place, `take` a thing. An action without `targets` is done to its holder: `open` on a door. Perception pairs the first kind with everything reachable of that type and lists the second kind under the object that carries it.

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
| `say(text, reach?, to?)` | words; `to` addresses one entity so the line is in both logs |
| `remember(text)` | a note into my entity's secret `memory`; the next mind in this body reads it |
| `intend(text, why, id, status, priority)` | my entity's secret `goals`: add one with its motivation, or change one's status (`active`, `done`, `dropped`), reason or priority. Every perceive shows the active ones |
| `recall(about?, relation?)` | the graph around me within my permissions: my edges (the data of an edge is mine to read when it starts at me, is world structure or is flagged public), my groups, goals, known places; with `about`, one entity's card as I may see it, our edges, the exchanges and events between us, my notes and goals that name them |
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
| `clock(run \| pause \| step \| rate \| turn)` | world time; `turn` makes every embodied act move the paused world by n seconds |
| `schedule`, `timers`, `unschedule` | an event in the future, what is pending and when, cancel one |
| `act_as`, `say_as` | drive any entity without embodying it: the game master's NPC beat |
| `fork_world(source, id)` | a fresh game on the same state: copy with history, nobody embodied, source untouched |
| `mirror()` | regenerate the markdown projection |

Observer: `perceive` and `recall` from any entity, `history`, `find`, no mutation.

Author ops carry no entity as actor, even while the same principal embodies someone: a `spawn` or `patch` by the game master is the world's doing, not the Traveler's, so it never lands in the player's own feed as theirs. What an author improvises is tagged on the entity (`improvised: true`); the tag is the provenance. Every feed is filtered per viewer: an entity's `remembered` and `intended` events reach only its own mind and authors, and a `patched` event on someone else shows only the public keys.

Error shape, every time: why it failed, what is true instead, what would make it possible. "`go(hall_b)` rejected: no path from hall_a. `open(door_7)` is available to you and would connect them."

The bundle also carries `clock` (running, rate, turn) and `ambient`, the world root's ambient facts (time of day, weather, light) overlaid by the place's own, so a narrator or mind never guesses the hour.

The `perceive` bundle is the NPC subagent's entire context. Paired with `wait`, an NPC costs nothing while nothing happens near it, and wakes with the diff.

A mind lives in the engine, not in an agent's context. The entity carries the author's `brief` and its own `memory` (always secret), `knows` edges to whoever it has met (a deterministic opinion floor nudges `standing` on gifts and blows; the last exchanges come from the log), `known_places` from its own moves, and its own `goals` with their motivations, managed through `intend` and shown in every perceive so a mind decides from what it wants. `recall` is the mind's graph query: relationships, groups, notes and goals around one person, within what that mind may know. Any agent that wakes up as Mara gets the same Mara. A dialog table is the floor: its listener carries `unless_embodied`, so an embodied mind takes the mouth and the table returns when it leaves.

One server connection speaks for many principals: the playing ops take a `principal` name, and an extra principal never gets the author capability. A subagent in the same session can therefore embody an NPC properly instead of sharing the narrator's body.

Lazy world building: an entity can carry `state.fidelity = "sketch"`. When an embodied principal approaches a sketch, the engine emits `approach_sketch`. An author-privileged agent subscribed to it fills the place in before the player arrives. The engine only emits and stores.

## 8. Space: the transform hierarchy

Every container may declare a `space`: `dims` (0 to 3), `bounds`, `units`, `grid` or continuous. Every child carries `pos` (and optional `facing`) in its parent's space. Zero dims is a text room where reach means "same parent." Two dims is a tactical grid. Three is a stage. `connects_to` edges carry an anchor position on each side so a map assembles itself from the graph.

Reach, line of sight and hearing become distance checks when a space exists and fall back to peers when it does not, so the same action scripts work in a text room and on a grid. Rendering to a tilemap, glTF or Blender is a client concern.

Slice scope: `space` and `pos` generic from the first schema; zero dims and 2D grid implemented; 3D later, as a number not a rewrite.

### Layout: one frame over the tree (2026-11-10)

The tree is how the story moves: what holds what, who can reach what, where a path goes. It is not a set of nested shapes. A cavern under a ridge, a yard inside a gate, a road that runs between two places: the tree says how you get there; the layout says where it is. They are two views of one world and neither bends the other, so laying out a world never means moving entities in the tree.

- **One frame for the whole world.** The root's `frame` names it: `units` (metres), `up` (`z`), which axis is `north` (`y`), optional `bounds` and an optional `geo` anchor (a latitude and longitude for x = y = 0). Every layout in the world is in this frame. No relative spaces to compose, so a viewer, an agent and a script all read the same numbers.
- **A layout on any entity** (`state.layout`, out of everyone's cards; read it with `map`, `measure` or `perceive(layout=true)`): `at` (x, y and optionally z), `heading` (degrees from north, clockwise), and an extent: `radius`, `size` (width, depth, height, a box turned by the heading) or `footprint` (a polygon of world x, y points). `floor` and `ceiling` make an extent a prism in z. `mesh` is a reference a client may load (a URL, an asset id); the engine never reads it. Extents are 2.5D on purpose: a footprint and a height is what an agent can reason about with plain measurements; real geometry belongs to a mesh.
- **Paths carry their own geometry.** A `connects_to` edge may carry `route` (points in the frame) and `length` (metres along it). The story path and the drawn path are the same edge.
- **What has no layout inherits.** A body or a thing without its own `at` is at its container's. When an entity changes container its own `at` is dropped (it arrived; it is somewhere in the new place until someone places it), and what it carries goes with it.
- **A gameplay space can sit in the frame.** A container's `space` may carry `frame_origin` and `cell` (metres per unit, and an optional `heading`), so a grid inside a room maps to world positions.
- **Ops.** `layout(placements, paths, frame)` writes many at once, checks every shape, and answers with warnings, never a refusal for a choice: a thing outside the place it is in, a route shorter than the straight line. `map(under, depth)` reads a subtree back with every position (own or inherited), the paths, the warnings and a top-down text sketch. `measure(a, b)` is the ruler: distances on the ground and in 3D, compass bearing, height difference, area, containment, overlap. `perceive(layout=true)` adds where you stand, and distance and bearing to what is here and to each exit.
- **Who sees it.** Authors, narrators and observers read the whole layout. A player or a mind gets it through perceive: what it can see, nothing hidden.

## 9. Storylines

A storyline is an entity outside the containment tree (under the world's `storylines` branch), hidden from embodied principals, visible to author and observer. It holds stages; each stage is a listener with a condition over events and state and effects applied as the storyline's own principal: spawn the ghost, unlock the gate, emit a `rumor` event in the tavern so the barkeep hears it. Open world is everything the rails do not touch. The GM agent can author or bend storylines live with the same ops.

## 10. Time

A world clock runs continuously, at a configurable rate, pausable and steppable. Actions have durations: `act` applies instant effects now and schedules a completion event at `t + duration`. Scheduled events are rows; the clock delivers them. Behaviors run at their interval. Everything the clock does is an event in the log, so replay is still exact.

## 11. Persistence

Event log plus projections in SQLite. One world is one file; copy it to share it. The schema is plain SQL so a Postgres backend for shared worlds is a driver, not a redesign. One writer per world (an action queue) keeps determinism without locks. Snapshots every N events so joining does not replay history. Subscriptions are filtered by bubble path; a client never receives the whole world.

A world's code is a folder, `worlds/<id>/`, and the folder is canonical: `build.py` with its manifest, `scripts/` as one file per script, `changes.jsonl` for what was authored live, `notes/`, `tests/`, and anything else the world needs (a model's weights, a map) as files, never as blobs in the database. The database is the build of that folder plus the history of play; a save is one JSON file in `saves/`. Shared verbs and rules are packs, `packs/<name>/`, that a world `requires`. Versions, forks and backups of the code are git's, and `create_world` starts a repository in the folder. The engine does not reinvent what the harness around it already does well: editing files, diffing, history, search.

## 12. Markdown mirror

Every world projects to a read-only directory: containment is directories, each entity is a markdown file with its state, relations and the verbs available on it. Regenerated on change. Agents read it with their normal file tools; writes go only through `act`. Committed mirrors give a world a git history for free.

## 13. Oracles and authority

An external system (webhook, sensor, feed) is a principal of kind `oracle` embodying an entity whose actions are "report X". World listeners decide what a report means. Representation, observation and authority are separate grants: an entity standing for a real server is just a node, reading its telemetry is a sense, acting on the real server is an action gated by a capability.

## 14. Many players, one hosted world

The engine already holds several principals in one world; the hosted version puts that world on a server and lets each player reach it with the agent they already use, or with no agent at all. Two players whose entities stand in the same place see each other's events through their own agents. That is the whole multiplayer: the engine needs no new idea, it needs a door that is safe to leave open.

Accounts and grants. An account owns principals. A grant is `(principal, world, role, scope)`, checked in the engine on every op, never in the harness. Roles: `owner` (everything, including grants), `author` (schemas, scripts, spawn, rules), `narrator` (`act_as`, `say_as`, `clock`, spawn under the world's `fill` policy, no schemas or scripts), `player` (join one of the entities the grant names or any entity tagged `playable`), `mind` (join exactly the entities the grant names, read their `brief` and `memory`, nothing else of anyone's), `observer` (read everything, write nothing). The flat capability list becomes the single-player shorthand for a grant with world-wide scope. Every token a player's agent carries is one grant, so a mind agent that gets prompt-injected in play can at most misplay its own entity.

Limits, builders and canon. Settled with Nate on 2026-11-10. A grant may carry `limits`: `under`, the entity it may change (that subtree; the rest it reads), `types`, what it may spawn (anything that `is_a` a listed type, plus its own schemas), and `scripts`, the prefix its scripts, schemas and event kinds carry. A script it defines keeps the limits on its own first line, so the script stays held when anyone's act runs it, and through files, saves and rebuilds; a verb's script may also touch the one who chose the verb and what they carry. Limits narrow a role and never widen it. `builder` is the author's hand without the world-wide ops (create, fork, save, restore, mirror, setting the clock) and needs `under`: a plot, a shop, a ship, built while people play. Canon is the owner's mark: an entity whose state says `canon` is not patched, moved or destroyed by any other grant or by a limited script, and only the owner sets or lifts the mark.

Access. Settled with Nate on 2026-11-12. Who may read, change and use one thing is the thing's own `access`: an owner (a principal or a body), a group (members listed on the root) and a mode like a file's, rwx for owner, group and everyone else, plus per-verb rules. It lives in the engine, not a pack, because the authoring ops and the script sandbox are what it guards and a pack's scripts run inside them; packs use it for game mechanics (a charter that adds its holder to a guild, a robot that answers its owner, a spell on what the caster owns). The owner and author roles pass it on the authoring ops; in the world nobody does, since there it is the body that acts. A limited grant reads its own plot in full and the rest as a player would. A thing with no access works as before. Next: a maker grant (write verbs on what you own, with quotas and the owner's review), then in-world packs. docs/ACCESS.md is the reference.

Next on grants, in order: `revert` (a grant's writes since a time, undone from the event log); delegated invites, a grant that may hand on only grants narrower than itself (fewer ops, limits inside its own, the templates it names), so a guild master invites guild members and a builder invites helpers to its plot; roles as data on the world root (a name, its ops, its default limits, the invites it may make), so a world's owner defines a moderator or a guild master the way a chat server defines roles. Grants are general; guilds, factions and trades are a world's content laid on top of them.

Away from the keyboard. Settled with Nate on 2026-11-10. A held seat that has gone quiet must not hold the world hostage: an idle body gives back what was taken from someone (`taken_from`, set by the engine when a thing passes between bodies by an act and not as a gift), and its holder may leave standing orders (`away`) that say what else others may take back and the one line it answers with. The vocabulary is fixed and small on purpose, so a guest never runs code on the host's server; when play outgrows it, a player's grant may define idle scripts held to `limits={"under": <its own body>}`.

Two kinds of memory. The character's notes (`remember`, `intend`) live on the server with the character: they follow the seat to any machine, and the host can read them. The player's agent keeps its own memory as well, in its harness, of its human and how they like to play; that is theirs, and the engine neither sees nor replaces it.

Secrets have owners. An entity's `memory` and `brief` are read by whoever embodies it and by the world's owner; a player's entity's memory is the player's. Who stands behind an entity (the account) is shown only where the world policy says so; by default other players meet the entity, not the person.

Time. A world with many players runs its clock; durations price actions and `wait` wakes an agent when something happens near its entity. Turn-based play stays a single-player convenience. Over the network `wait` is a long poll with a `since` cursor and the same filter, and the server also streams events (server-sent events) for harnesses that have a monitor tool rather than a blocking one. Nothing in the engine changes; the transport grows a second shape.

No agent. The `perceive` bundle lists affordances with their preconditions evaluated, so a plain web client can render the room, the people, the exits and the verbs as text and buttons. A person can play without a model, and the person next to them can play through one. Both produce the same events.

Untrusted text. Everything another principal says reaches an agent's context as data. The server marks every event with its actor and the actor's account, caps the length and rate of `say`, and the role references for hosted play tell a mind or narrator harness to run with no filesystem or shell tools. The safest mind is one the server runs itself, in a sandbox that has only the embody tools; that is an option, not the only way. A security audit of the whole door (auth, grants, script sandbox, rate limits, abuse of `fill`) comes before the first public world.

Invites. A grant travels as an invite: one token, one paste. Settled with Nate on 2026-11-09. The text a friend drops into their agent carries the server address, the token, the role, who they are in the world and how to begin; the agent adds the MCP server, calls `join`, reads the briefing that comes back and plays. Nobody configures a character. Three kinds of invite:

- A named seat. The token names an entity (the reeve, a carrier, the captain of the guard), reserved for that token until it is claimed or the invite expires. Until a person sits down the entity runs on its behaviors like any other; when the player goes idle past the world's `claim_lapse` the seat is released and the behaviors resume, so a hosted world never has a frozen body in it.
- An open seat. The token says `player` and names nothing. The agent lists what is open (`seats`): every entity tagged `playable` that nobody embodies, and the `templates` on the world root for a new character (a faction, a trade, a starting place). `join(world, entity)` claims one, `join(world, template=..., name=...)` makes one. Two agents racing for the same seat are one SQLite transaction: one wins, the other gets a refusal that lists what is still open.
- A resident. A `mind` grant on one or more named NPCs, held by someone's subagent, which moves the story the way its owner wants while people it has never met play beside it. It reads only its own entities' `brief`, `memory` and `goals`, cannot author or spawn, and the owner can evict it. A player who takes a seat and a resident who takes an NPC are the same mechanism with different reach.

Only grant holders lapse. The owner's own sessions, and the extra principals a local process asks for by name, keep their seats through any silence: they are the host at the keyboard, not a guest who left. The role is checked by the engine on every op, not by the server in front of it, so the stdio server, the HTTP server and the CLI refuse the same things with the same words.

No LLM on the server. The host runs the clock and the code behind it: behaviors, timers, rules, the bookkeeping. Every player, narrator and resident brings their own inference through their own harness; the host pays nothing per thought, and an NPC that thinks is always someone's agent. This is what lets one person host a world for friends at the cost of a small machine.

Harness scope. A mind or player agent that holds an invite needs less reach than a developer's agent, not only in the world but on the computer it runs on. The role reference for hosted play says: a resident or a player subagent runs with the embody tools and nothing else, no filesystem, no shell, so a prompt injected through `say` can misplay one entity and touch nothing else.

Time, concretely. The Glass Reach runs at four times real time (Nate, 2026-11-09): a game day every six real hours, so one real day holds four game days spread across every time zone, long enough for a session to feel like an evening, and a trigger that fires only at night gets four chances a day. The running clock is what synchronizes players: nobody waits for anyone's turn, the world moves and `wait` wakes whoever is near what happened. A hosted world is a place people come back to, not a spine they finish.

Any harness. The instructions that tell an agent how to be a narrator, author or mind are harness-neutral and live in `AGENTS.md`; `CLAUDE.md` points there and keeps only what is Claude Code's own (the skill, `.mcp.json`). An invite paste tells a Codex, Claude Code or other MCP-capable agent the one line that adds the server.

The hosted product (sign-in, rosters, world listings, invite pages, a client with no agent) sits on top of the engine's grants and knows nothing about worlds beyond their ids.

## 15. The slice

1. Core library: schemas, graph, scripts, actions, events, bubble, SQLite. A test world of two rooms, a door, a key. Replay test.
2. Clock, durations, behaviors, a combat pocket.
3. `perceive`, `wait`, markdown mirror.
4. CLI and MCP server. Repo ships `.mcp.json` and `CLAUDE.md` so a clone plus `claude` is the whole setup.
5. Sample world: three full locations, NPCs with goals, one storyline. Claude Code as author and as the player's textual interface, subagents embodying NPCs.
6. Postgres, oracles, outward hooks: after the slice plays.
