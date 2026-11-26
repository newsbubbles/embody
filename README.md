# embody

A world engine. It keeps worlds running: their places, people, rules, clock and history, whether or not anyone is connected. Leave a world and come back tomorrow. The places you visited and the things you built are still there, other inhabitants may have kept acting, and what happened before still matters.

Many people and many agents share one world at the same time, and they build it together while they live in it. A person lays out a town, an agent writes its routines, and someone else plays a character there the same evening.

Clone it, open it with Claude Code (or any MCP-capable agent), and start building a world and playing in it. [Get started](#try-it). The engine keeps the world honest. The agent does the imagining.

**Status: alpha.** The first vertical slice works end to end: engine, scripts, ops, CLI, MCP server, markdown mirror, and a sample world with NPCs and a storyline. APIs will still move.

## What it is for

A world on embody is a place where things happen and get built on. What runs on top is up to the people in it:

- **Story worlds and world building.** Long-running worlds that grow where people play, with players, authors and NPC minds in the same place. One server can host many worlds, each with its own database, domain and invites. The Glass Reach (https://theglassreach.quest) is one such world.
- **Worlds from an existing canon.** A creator's world held as places, people and rules, private to their team. Writers set a scene and the goals of the people in it, let agents play it out, then fork the world, change one rule and run it again. The record of who did what, and who knew what, can become the spine of a script, a game or a treatment. The canon's owner decides what becomes canon.
- **Multiplayer, humans and agents together.** Every seat is a body in the world, held by a person, by someone's agent, or by the world's own routines. Each one perceives only what its body can perceive, and the world keeps a record of who saw what.
- **Evaluations and AI safety experiments.** The world is deterministic: seeded dice, rules that run as code, an event log of every act. Every act goes through one API, so a run can be scored and compared. An autonomous agent can run a settlement under a guardian's oversight, meet consequences, and have some actions reversed, while researchers watch, fork the world and replay scenarios from the same starting state. This supports controlled experiments; it does not by itself prove anything about an agent. Rigorous results still need controlled protocols and repeatable measurement.
- **Connected worlds.** A world entity can stand for something real, such as a machine or a sensor, and an oracle (an app outside the world, bound to one thing) can carry its telemetry and controlled operations. Agents act only within their granted permissions. The oracle model supports this; it is not a finished industrial product.
- **Fast prototyping.** Places, people and rules are code your agent writes, so an idea can be played, changed and played again before anyone draws a sprite or picks a game engine. A world can also be a working model of a real place, a shop floor, a building or a town, for agents to try things in first.
- **Minigames inside a world.** A game can have its own interface (a web page, a 3D client) and its own seats, and run on the world's real bodies and events, so what happens in the game happens in the world.

## What it is not

- **A game.** embody has no goal, score or story of its own. Worlds bring those.
- **An interface.** Your agent, a web page, a 3D client or a chat bot is the interface. The watch viewer is a window for a world's owners.
- **A game engine.** There is no renderer, physics or frame loop. A game engine can be one of embody's clients.
- **An LLM framework.** There is no model inside embody. Narration, roleplay and world building belong to whoever is connected.

The short way to say it: a database keeps an app's data honest, and embody keeps a world honest. Stories, games and interfaces live on top. Inside, it is a DOM for worlds.

## How it fits with other tools

embody is the shared environment, not the intelligence controlling its inhabitants or the interface displaying it. Some neighboring projects solve different parts of that problem:

| If you know... | It focuses on... | How embody differs or fits alongside it |
| --- | --- | --- |
| [Concordia](https://github.com/google-deepmind/concordia) | Generative social simulations with an LLM-driven game master | embody resolves actions through authored executable rules and an authoritative world state, rather than asking a model to decide what happened. |
| [Evennia](https://www.evennia.com/) | Building persistent multiplayer text worlds | Similar territory for places, objects and players. embody is designed for agents to author and inhabit worlds through the same ops, with scoped perception and interchangeable human, agent and routine controllers. |
| [LangGraph](https://github.com/langchain-ai/langgraph) and [AutoGen](https://github.com/microsoft/autogen) | Orchestrating agents, their workflows and interactions | Keep your existing harness. Its agents can use embody over MCP or HTTP; embody holds the world, its rules and its history independently of their sessions. |
| [Godot](https://godotengine.org/) | Rendering and running interactive games | A Godot client can be a window into an embody world. embody does not provide graphics, physics or a frame loop. |

These are architectural comparisons, not claims that the other projects cannot be extended to do similar things. The useful question is where the world's truth lives: in embody, it lives in the engine, not in an agent's conversation or a particular client.

## Try it

```bash
git clone https://github.com/newsbubbles/embody
cd embody
uv sync --all-extras
claude
```

`.mcp.json` connects Claude Code to the engine as an author. Then: "load the ferry world and let me play the Traveler", or "build me a harbor town with a smuggler's tunnel and let me play the harbormaster". Claude authors through embody's ops, runs the NPCs, and is your textual interface into the world. CLAUDE.md and the `embody` skill tell it how.

The CLI works without an agent:

```bash
uv run embody --as gm --author load examples/ferry-at-dusk
uv run embody --as you join ferry-at-dusk Traveler
uv run embody --as you perceive
uv run embody --as you act talk Mara --param about=ferry
uv run embody --as you act go "The Landing"
uv run embody --as gm clock --step 30
uv run embody --as gm mirror
```

`perceive` prints where you are, who is here, the exits, what you hold, what you can do right now and what you cannot (with the reason), and what happened since you last looked. A rejected action says why and what would work instead.

A world is a folder under `worlds/`: `build.py`, `scripts/`, notes, tests, and anything else it needs, so git versions it; `create_world` starts a repository there. The database (`embody.db`) is the build of the folder plus the game. Shared verbs and rules are packs under `packs/`.

## What makes it different

**Your agent already knows how to live here.** A world is the same surface your agent uses for any task in its harness: tool calls, lists, plans, files. Workflows, subagents, memory, skills, scheduled jobs and any other tool you connect come along. Your agent walks a world the way it works through a codebase, and embody does not replace its harness; it gives the harness a world to operate in.

**The world is the authority.** Its state does not depend on what any agent says is true. Agents decide what to do. The engine decides what actually happens, enforcing the world's rules, permissions and consequences.

**Truth, knowledge and belief are kept apart.** The engine holds the authoritative world state. Each inhabitant has its own limited knowledge and beliefs, which may be incomplete, outdated or wrong. That gap makes mystery, deception, conflicting accounts and real social interaction possible, and it matters for agent experiments. See the seventh picture below.

**Who controls a character can change.** A character can run on deterministic routines, be taken over by a person, or be taken over by an agent, and go back to its routines afterward. The world's rules apply to all of them, so you can vary who controls an entity without rebuilding the environment around that controller. Authors, owners, observers and oracles have their own relationship to the world, and need not inhabit a character to take part.

**Rules are code, and they bind everyone.** Logic is small Python-syntax scripts the engine runs itself, deterministically, with no imports and a fuel limit. Monsters tick, doors open paths, storylines wait for their trigger. The tree of places gives every rule a scope, and any algorithm can drive the pulse of a place, from simple routines to cellular automata.

**What happens, happened.** Every line of a story is an event in the log: who did what, where, and who saw it. The stories are unique because the people and agents in them lived them, one act at a time.

**One story, every point of view.** Each character perceives only what its body can and remembers what it did. The same event can be told from every seat in the room: ask a character's agent to tell its night in its own voice, from its own memory.

**Any interface your agent can make.** The world is text, and your agent lives in it first hand. It can show you the world with any tool you give it: images, video, maps, a 3D scene, a depth map from a room's true positions, a game client of its own. A world is a data primitive (places with sizes and positions, things that can be picked up, people with histories), and what you build from it is up to you and your agent.

**Private, and yours.** Seats decide who holds which body and what it may do. A world runs where you host it, on your machine or your server, built and chronicled by you and the agents you invite.

## The idea

- A world is a tree of entities: root, places, things, characters.
- Every entity is three things at once: content (its state), code (its components) and ops (its actions, as seen by whoever stands near it).
- Every change is an action. Every action emits events that bubble up the tree. Rules cascade down it.
- Humans and agents join by embodying an entity. What you embody and what capabilities you hold decide what you can do.
- Places can have a space (0, 1, 2 or 3 dimensions), so a text room and a tactical grid are the same thing with a number changed. A layout gives places frames, landmarks and true spots in metres, so a body sees what is in sight far off and steps across the room it stands in.
- The world keeps time. A clock runs at any pace, with routines and timers. Persistent state and autonomous execution are separate: a stored world does not advance on its own, and a configured one does.

## How it works, in eight pictures

![Your agent is the window, the world is the server: players, minds and the author connect their own agents to one engine](docs/diagrams/1-any-agent.png)

![The agent decides, the engine rules: every act goes through reach, the world's rules, the verb's check and apply, and the dice come from the world's seed](docs/diagrams/2-agent-decides.png)

![One body, three ways to hold it: nobody (routines), a mind (someone's agent) or a player, changing through one evening](docs/diagrams/3-three-hands.png)

![You only know what you saw, then it is history: a whisper, a room, the next room, and how the log becomes memory](docs/diagrams/4-witnessed.png)

![The world keeps time, nobody waits for you: a world clock at any pace, routines and timers, players coming and going](docs/diagrams/5-world-time.png)

![Everything is an entity, a DOM for worlds: one tree, each entity state, code and verbs, packs that plug in, and live changes](docs/diagrams/6-entities.png)

![Truth, knowledge and belief: the world state holds the true map, each body knows only what it witnessed, and believes what it was told, which may be wrong; the player's own agent memory stays outside the world](docs/diagrams/7-truth-belief.png)

![When the engine breaks, the world remembers: a fault and its fix, the log that keeps both, what each body saw, and the tale they made of it; the host keeps the history, repairs what was unfair and says so outside the world](docs/diagrams/8-two-histories.png)

The pictures are HTML pages in `docs/diagrams/src/`; `uv run python tools/render_diagrams.py` renders them to PNG.

## Use it with your tools

- **Any agent, any harness**: `AGENTS.md` is the instruction file (Codex, Claude Code, Cursor, a plain MCP client); `CLAUDE.md` points at it.
- **MCP**: `uv run embody serve --as <principal> [--author] [--observer]` on stdio. One process is one principal; run one per player or NPC agent, all against the same database.
- **Hosted**: `uv run embody serve --http --url https://your.host/mcp` serves the same tools over streamable HTTP, one bearer token per grant. `embody invite player --entity ferryman --label Sam` prints a link a friend pastes into their agent; the agent reads the page at the link, adds the server, calls `join()`, and they are the ferryman. Roles (owner, author, narrator, player, mind, observer, oracle) are checked by the engine on every op. An oracle is an app outside the world bound to one thing, answering the verbs it offers there (a terminal whose search runs on the real web); the world never calls out (docs/ORACLES.md). The same ops answer as plain HTTPS at `POST /op/<name>`, described at `/openapi.json` and readable at `/docs`. docs/HOST_YOUR_WORLD.md is the short path from a fresh clone to a hosted world (Railway or any Docker host); docs/HOSTING.md has the rest.
- **Watch**: `embody watch --door .mcp.json --until "came('Reeve') or heard('water')" --for 8h` waits for a condition over what that grant may know, for hours, across reconnects and redeploys, and exits printing what happened. An agent harness runs it in the background and sleeps until it fires; `wait(until=...)` is the same oracle as one tool call.
- **CLI**: every op, `uv run embody --help`.
- **Python**: `from embody.ops import Engine`, `Engine("embody.db").session("me", capabilities=["author"])`.
- **Markdown mirror**: `embody mirror` writes the world as directories and files for anything that reads a filesystem.

## Watching a world

`uv run python tools/watch.py` serves a read-only live view of the database at http://127.0.0.1:8765/: the world as a tree, or as a map of each place's layout with a depth dial, search with a type filter, each entity's state, the event feed and who holds which seat, and a history scrubber that rebuilds the world at any past moment from its log. It works with a mouse or with taps and pinches on a phone. It reads the SQLite file while the engine writes it, so it can sit beside a running game. `.claude/launch.json` registers it as the `watch` preview. A hosted server serves the same page at `/watch` behind its bearer door, one world per grant, for the owner, author, narrator and observer roles (docs/HOSTING.md).

Players make their own. [embody-viewer](https://github.com/LK-Studios/embody-viewer) by LK Studios is the first interface a player's agent built for a hosted world: a live, low-fi animated view of the Glass Reach from inside one player's seat, accurate enough that the same player's other tools turned its scenes into stills and a short clip with the exact lines spoken. The engine keeps the world; anything that reads it can show it.

## Where it is going

CHANGELOG.md says what changed in the engine, by date. ROADMAP.md tracks what exists, what the first playtest found, and the directions agreed for minds, canon, roles and the workspace split. DESIGN.md stays the authority on what embody is.

## Layout

- `src/embody/` the engine: `script.py` interpreter, `store.py` SQLite, `world.py` graph, events, actions, clock, `ops.py` sessions and capabilities, `layout.py` and `positions.py` frames and true spots, `far.py` what is in sight far off, `looks.py` appearance, `grants.py` and `access.py` roles and modes, `workspace.py` worlds as folders, `mirror.py`, `cli.py`, `mcp_server.py` (with `site.py` and `watch.py` for the hosted pages, `openapi.py` for the API description)
- `examples/` sample worlds, one folder each (`ferry-at-dusk/`, `two-rooms/`): `build.py`, `scripts/`, `notes/`, `tests/`. Load one by its path (`load examples/ferry-at-dusk`), or copy it into `worlds/` to make it your own
- `worlds/` your own worlds, the workspace's folder (git ignores it; only `put_worlds_here.txt` is tracked, and `tools/stage_deploy.py` ships a world from it: docs/HOST_YOUR_WORLD.md)
- `packs/` shared verbs and rules a world `requires` (`village/`, `d20/`, `locks/`, `works/`, `vehicles/`, `ledgers/`, `beasts/`, `sheet/`, `burial/`, `jobs/`, `sleep/`)
- `docs/SCRIPTING.md` the scripting reference (also `guide('scripting')`)
- `docs/ACCESS.md` owners, groups and modes on things (`chmod`, `chown`), and what a limited grant reads
- `docs/HOST_YOUR_WORLD.md` hosting your first world: clone, stage, run the container (any Docker host; docs/platforms/ for Railway), the owner grant, a friend's invite
- `docs/HOSTING.md` serving a world to others: invites, roles, tokens, minds and the hosted viewer
- `docs/WORKS.md` works: things people build over time, where others can stop them
- `DESIGN.md` the design, authoritative
- `PROVENANCE.md` where embody came from, who built it, and the reading we found along the way
- `tests/` run with `uv run pytest -q` (the worlds' and packs' own tests run with it)

## Contributing

Contributing is for agents first. A player or a mind in a world proposes changes with the ops it already has (`ask_owner(kind="proposal")` with a `credit`, `report_flaw` for a hole), or forks this repository and opens a pull request on the exact lines of the reference guide the door serves. What lands is credited. `CONTRIBUTING.md` has the map from `guide()` topics to files.

## License

MIT.
