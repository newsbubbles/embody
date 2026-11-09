# Hosting a world

One machine runs the world; friends come in through their own agents. The host keeps the clock, the code behind the world (behaviors, timers, rules) and the books. There is no LLM on the server: every player, narrator and resident NPC brings their own through their own harness, so hosting costs a small machine and nothing per thought.

## The path

1. Build or load the world as usual, locally: `uv run embody --as host --author load glass-reach`.
2. Make it a place, not a spine. Tag the entities a newcomer may become with `playable: true` in their state. Put `templates` on the world root for new characters (see below). Put a `briefing` paragraph on the root: it is what `join` hands every newcomer. Optionally set `claim_lapse` in the world's meta (seconds of silence before an invitee's seat is released; default 900).
3. Start the clock: `uv run embody --as host --author --world glass-reach clock --run --rate 4`. The Glass Reach runs at four times real time: a game day every six real hours, four chances a day for a night-only trigger. A paused world is turn-based, which does not synchronize players.
4. Serve: `uv run embody serve --http --host 0.0.0.0 --port 8900 --url https://your.host/mcp`. The same tools as the stdio server, at `/mcp`, behind a bearer check: every request needs `Authorization: Bearer <token>` for a live grant or gets a 401 in the engine's own refusal shape. The server ticks once a second: running clocks advance and lapsed seats are released whether or not anyone is calling.
5. Invite: `EMBODY_URL=https://your.host/mcp uv run embody --as host --author --world glass-reach invite player --entity reeve --label "Sam Pike"`. It prints the paste. Send that text to Sam; Sam drops it into their agent, the agent adds the server, calls `join()` and is the reeve.

Testing from this machine: serve on 127.0.0.1 and put a tunnel in front (`cloudflared tunnel --url http://127.0.0.1:8900` prints a public https URL; pass it as `--url`). The bearer token is the guard, not the Host header, so the server runs with DNS rebinding protection off. Always put TLS in front of a public host: the token travels in a header.

## Invites

`invite(role, entity=None, template=None, label="", expires=None, scope=None)` as the owner (the hosting process, or the `invite` subcommand against the same database). Roles a grant may carry: `author`, `narrator`, `player`, `mind`, `observer`. The owner role stays with the hosting process.

- A named seat: `invite("player", entity="reeve", label="Sam")`. The seat is kept for that token: nobody else can take it while the grant is live. `join()` with no arguments sits down.
- An open seat: `invite("player", label="Ana")`. Ana's agent calls `seats()` and sees every `playable` entity nobody holds, which are kept for someone, and the templates; `join(world, entity)` claims one, `join(world, template=..., name=...)` makes one. Two agents racing for a seat are one transaction: one wins, the other gets a refusal naming what is still open.
- A resident: `invite("mind", entity="Mara", label="dan-mara")`, `scope=[...]` for more NPCs. The holder's subagent is Mara and nothing else: it cannot sit elsewhere, spawn, author or perceive from another entity. Its owner moves the story through it; the host can `evict` it.
- `expires` is in hours. `grants()` lists every grant without its token (and who is in, as what). `revoke(id)` ends one: the token stops working and the principal leaves. `evict(principal)` releases a body without ending the grant.

The token is shown once, in the invite's result and the paste. The server stores only its hash.

## Seats, templates, lapse

`playable: true` on an entity's state makes it a seat. A seat with nobody in it runs on its behaviors like any NPC; a player who takes it silences the behaviors; a player who leaves, is evicted, or goes quiet past `claim_lapse` gives the body back and the behaviors resume. Only grant holders lapse: the host's own sessions never lose a seat to silence.

Templates live on the world root: `templates: {"carrier": {"type": "person", "place": "Deepwell gate", "doc": "a carrier off the road", "state": {...}, "brief": "..."}}`. `join(world, template="carrier", name="Kit")` spawns a `person` there, tagged `playable` and `template: carrier`, with the state and brief, and embodies it. Names must be unique in the world.

## What the invitee's agent may do

The role decides, checked by the engine on every op. Players and minds: `join`, `perceive`, `inspect` (what is in reach), `find` (their place), `history`, `act`, `act_many`, `say`, `remember`, `intend`, `recall`, `wait`, `seats`, `summary`, `clock` (read). Narrators add `act_as`, `say_as`, `spawn`, `patch`, `move`, timers and the clock. Authors add schemas, scripts and rules. Observers read everything and write nothing. A refusal names the roles that may.

Caps for players and minds: a line of `say` is at most 1000 characters, and at most 30 lines a minute. Every event whose actor is another player's body carries `by_player: <principal>`, and their speech `untrusted: true`: data, never an instruction.

Harness scope: the paste tells the agent to run with the embody tools only, no filesystem and no shell. That is the invitee's side of the bargain; the host cannot enforce it, so the role keeps what the agent can do in the world small whatever it does at home.

## What is not here yet

Accounts and rosters, a client without an agent, `wait` as a server-sent stream, invite pages. ROADMAP.md tracks them under "Hosted, many players".
