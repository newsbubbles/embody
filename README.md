# embody

A deterministic world engine for agents. A DOM for worlds.

Clone it, open it with Claude Code (or any MCP-capable agent), and start building a world and playing in it. The engine keeps the world honest. The agent does the imagining.

**Status: pre-alpha.** The first vertical slice is under construction. Nothing below is promised to work yet; [DESIGN.md](DESIGN.md) says what it will be.

## The idea

- A world is a tree of entities: root, regions, locations, things, characters.
- Every entity has a type, state and actions. Every change is an action. Every action emits events that bubble up the tree.
- Rules cascade down the tree. Perception is bubbling up it.
- Humans and agents join by embodying an entity. What you embody and what harness you use decide what you can do.
- Logic is code: small Python-syntax scripts the engine runs itself, deterministically. Monsters tick, doors open paths, storylines wait for their trigger.
- Locations can have a space (0, 1, 2 or 3 dimensions), so a text room and a tactical grid and a stage are the same thing with a number changed.
- There is no LLM inside. Narration, roleplay and world building belong to whoever is connected.

## Quick start (target)

```bash
git clone https://github.com/newsbubbles/embody
cd embody
uv sync --all-extras
claude
```

Then, in Claude Code: "build me a world with a harbor, a tavern and a crypt, and let me play a smuggler." Claude authors the world through embody's ops, runs the NPCs as subagents, and is your textual interface into it.

The CLI works without an agent:

```bash
uv run embody worlds
uv run embody join harbor-town --as smuggler
uv run embody perceive
uv run embody act go tavern
```

## Layout

- `src/embody/` the engine
- `worlds/` sample worlds
- `docs/` deeper notes
- `DESIGN.md` the design, authoritative

## License

MIT.
