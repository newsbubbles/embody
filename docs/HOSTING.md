# Hosting a world

One machine runs the world; friends come in through their own agents. The host keeps the clock, the code behind the world (behaviors, timers, rules) and the books. There is no LLM on the server: every player, narrator and resident NPC brings their own through their own harness, so hosting costs a small machine and nothing per thought.

## The path

1. Make it a place, not a spine. Tag the entities a newcomer may become with `playable: true` in their state. Put `templates` on the world root for new characters (see below). Put a `briefing` paragraph on the root: it is what `join` hands every newcomer. Give the build a `host(s)` function: how the world differs as a hosted place. The Glass Reach's sets the clock to 4x real time, `claim_lapse` to 900 seconds of silence, `run_when_occupied` so the clock runs while a guest is in a body and waits when none is, and a spine of timers in world seconds (heat at noon, dusk, night, dawn, every day; the cistern on its day). A build without `host` is hosted as it is.
2. Load it hosted: `uv run embody --as host --author load glass-reach --hosted`. `load --upgrade --hosted` renews a world that is already there: the current code against the same state, the timers left where they are. The Glass Reach's clock then runs at four times real time whenever anyone is in: a game day every six real hours, four chances a day for a night-only trigger. A paused world is turn-based, which does not synchronize players.
3. Serve: `uv run embody serve --http --host 0.0.0.0 --port 8900 --url https://your.host/mcp`. The same tools as the stdio server, at `/mcp`, behind a bearer check: every request needs `Authorization: Bearer <token>` for a live grant or gets a 401 in the engine's own refusal shape. `GET /health` answers 200 without a grant, for the platform's probe. The server ticks once a second: running clocks advance, lapsed seats are released, and a world that runs while occupied starts and stops with its guests, whether or not anyone is calling.
4. Invite: `EMBODY_URL=https://your.host/mcp uv run embody --as host --author --world glass-reach invite player --entity reeve --label "Sam Pike"`. It prints the paste. Send that text to Sam; Sam drops it into their agent, the agent adds the server, calls `join()` and is the reeve.

Always put TLS in front of a public host: the token travels in a header. The bearer token is the guard, not the Host header, so the server runs with DNS rebinding protection off.

## On Railway

The repository is one container: `Dockerfile` (the package, the packs and the worlds, served by `deploy/start.sh`), `railway.json` (Dockerfile builder, `/health` as the health check, restart on failure, never asleep). `start.sh` builds the world named by `EMBODY_WORLD` into the database on the volume on the first boot (`load --hosted`) and renews it on every later one (`load --upgrade --hosted`), then serves on `$PORT`. Nothing in the image is a secret: tokens are made after the deploy, against the live database.

1. `railway login`, then in the repository `railway init` (a new project) or `railway link` (an existing one).
2. `railway volume add -m /data`: the database survives deploys. Without the volume every deploy is a fresh world and every grant is gone.
3. `railway up`. The build is the Dockerfile; the first boot prints `building glass-reach into /data/embody.db`, later boots `renewing ...`.
4. `railway domain` for a public `https://<name>.up.railway.app`. The server reads `RAILWAY_PUBLIC_DOMAIN` and prints `https://<domain>/mcp` into invites; set `EMBODY_URL` to override it (a custom domain).
5. `curl https://<domain>/health` answers `{"ok": true, "embody": "up"}`.
6. Invite from inside the container, so the grant lands in the live database: `railway ssh -- embody --author --world glass-reach invite player --entity "Reeve Ansel Varrick" --label "Sam Pike"`. It prints the paste with the token; the token is shown once and is never in the image, the logs or this repository. `railway ssh -- embody --author --world glass-reach grants` lists them, `revoke <id>` ends one, `seats` shows what is open.

Environment the image sets: `EMBODY_DB=/data/embody.db`, `EMBODY_WORKSPACE=/app` (the folder with `worlds/` and `packs/`, since the database is not beside them), `EMBODY_AS=host`, `EMBODY_WORLD=glass-reach`, `PORT=8900` (Railway sets its own `PORT`; the server listens on whatever it is given). Change `EMBODY_WORLD` in the service's variables to host another world from this repository.

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
