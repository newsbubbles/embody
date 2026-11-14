# Hosting a world

One machine runs the world; friends come in through their own agents. The host keeps the clock, the code behind the world (behaviors, timers, rules) and the books. There is no LLM on the server: every player, narrator and resident NPC brings their own through their own harness, so hosting costs a small machine and nothing per thought.

## The path

1. Make it a place, not a spine. Tag the entities a newcomer may become with `playable: true` in their state. Put `templates` on the world root for new characters (see below). Put a `briefing` paragraph on the root: it is what `join` hands every newcomer. Give the build a `host(s)` function: how the world differs as a hosted place. The Glass Reach's sets the clock to 4x real time, `claim_lapse` to an hour of silence (3600 seconds; a quarter hour was too short for a player who steps away or a mind between turns), the clock running whether anyone plays or not (a hosted world keeps real time; `run_when_occupied` exists for a world that should wait for its guests, the Reach does not use it), `idle_after` (below), a spine of timers in world seconds (heat at noon, dusk, night, dawn, every day; the cistern on its day), and the routines that ride the spine. A build without `host` is hosted as it is.
2. Load it hosted: `uv run embody --as host --author load glass-reach --hosted`. `load --upgrade --hosted` renews a world that is already there: the current code against the same state, the timers left where they are. The Glass Reach's clock then runs at four times real time whenever anyone is in: a game day every six real hours, four chances a day for a night-only trigger. A paused world is turn-based, which does not synchronize players.
3. Serve: `uv run embody serve --http --host 0.0.0.0 --port 8900 --url https://your.host/mcp`. The same tools as the stdio server, at `/mcp`, behind a bearer check: every request needs `Authorization: Bearer <token>` for a live grant or gets a 401 in the engine's own refusal shape. `GET /health` answers 200 without a grant, for the platform's probe. The server ticks once a second: running clocks advance, lapsed seats are released, and a world that runs while occupied starts and stops with its guests, whether or not anyone is calling.
4. Invite: `EMBODY_URL=https://your.host/mcp uv run embody --as host --author --world glass-reach invite player --entity reeve --label "Sam Pike"`. It prints the paste: a link and one line. Send that to Sam; Sam drops the link into their agent, the agent reads the page at the link (the server address, the token, who they are, how to begin), adds the server, calls `join()` and is the reeve, and opens with the scene rather than the setup.
5. Hand yourself the keys: `... invite owner --label "<you>"` once, from the hosting process, and paste that link into your own agent. From then on invites are a sentence to your agent ("invite Sam as the reeve"): the `invite`, `grants` and `revoke` tools answer to an owner grant over the door, and the viewer (below) is yours too. Only the hosting process makes owner grants; an owner over the door hands on author at most.

Always put TLS in front of a public host: the token travels in a header. The bearer token is the guard, not the Host header, so the server runs with DNS rebinding protection off.

## Watching for hours

A mind, a narrator or the owner rarely needs every event; it needs the one that matters to it. `wait(until="<expression>")` returns when the expression is true over what that grant may know (the hour, the place, who is here, its own state, what it heard, the public state of who is near; the owner and narrators see anyone), and a timeout moves nothing. `embody watch --door <.mcp.json> --until "..." --for 8h --rejoin` loops it from a shell in pieces under a minute, reconnects across redeploys, takes a lapsed seat again, and exits printing FIRED or TIME UP. In Claude Code the mind runs it in the background and ends its turn; the harness wakes the session when it exits. Every wait is a sign of life, so a watching mind keeps its seat. The grammar is in the skill's `references/watch.md`.

## A world that lives while nobody plays

The clock does not stop for an empty table. What keeps a hosted world from running down overnight is two things, both in the world and both visible to anyone who looks:

- Idle seats look after their bodies. A seat whose holder (player or mind, any embodiment) has done nothing for the world's `idle_after` (world seconds; the Reach: 3600, a quarter hour of real time) is idle, and the body's behaviors marked `idle` run on it as on a body nobody holds. In the d20 pack that is `quench`: thirsty, drink from a skin or a source here, or walk to the nearest water it knows the way to (a step a look, up to six), drink its fill and walk back to the post. An act or a line said marks the seat in use again; waiting and watching keep the seat but are not deeds.
- Routines put back what the world uses up. In the Reach (`worlds/glass-reach/scripts/reach_routines.py`): at dusk, while the truce holds, Iska of the Keth carries water from the Deepwell over the ridge, the Flats, the Salt Road and the yard to the Keth jars in the Hold, a leg every half hour of the world, and walks home; at dawn a Guild crawler tops up the Hold's ration cask and the Landing's casks while Ossa is at the tally post on her feet. Players can get in the way: a bearer put down or cowed on the road sets the jars down where they stand, no truce means no run, no Ossa means no crawler.

Before hosting a world with water (or anything else that runs out), soak it: `uv run python packs/d20/soak.py <world> --days 7` builds it in memory, holds every seat with someone who never acts, runs the clock, and prints each body's lowest water and hours thirsty and each source's lowest and refills; `--set "Story.truce=true"` soaks it as a story left it. Exit code 1 when thirst put anyone down. The Reach passes a week both with and without the truce.

## Away from the keyboard

A seat that has done nothing (no act, no line) for the world's `idle_after` is idle, and the world treats its body as one nobody plays, with three courtesies to everyone else. What was taken from someone goes home: a thing that passes between bodies by an act and not as a gift carries `taken_from`, and `reclaim(thing)` takes it back from an idle holder standing in the same place. Standing orders, set with `away(give=[...], answer=...)` before a player stops, say what else others may reclaim and the one line the body answers with. A mind can leave more: `away(patrol=[...], dwell=...)` walks its body round a few places by its own `go` until its next deed, and `away(dialog={...})` gives the body its own answers over the author's table; both stay in the body's secret `idle_orders` (references/mind.md, "Your body while you wait"). And the card shows `idle: true` with the orders, so another player's agent knows it may act instead of waiting. A world turns reclaim off with meta `reclaim: false`, and lists what everyone may know of the schedule with `public_timers` (what `timers()` shows a player).

## Invite links

The page behind a link tells the agent to add the server and play in the session it is in. Most harnesses load a new MCP server only when they start, so the door also answers as plain HTTPS: `POST /op/<tool>` with a JSON object of the arguments and the same `Authorization: Bearer` header, the same role check and refusal shape (`GET /op` lists the ops the grant may call; `wait` is capped at 120 s). A guest never needs this repository, an install or a second session.


An invite is a link, `https://your.host/i/<code>`. The code is random, kept hashed like the token, and the page it serves is plain text written for the agent: what this world is, the add-server lines with the bearer token, how to join, and how to tell it. The page stays up for 24 hours (or until the grant itself expires, if sooner) and goes away with the token's first use over the door: from then on the server holds the token's hash only, and the link answers 404 with a hint to ask the host for a fresh one. Reading the page does not spend it, so an agent that fetches it twice before connecting is fine. Link-preview crawlers (Discord, Slack, WhatsApp, Telegram and the like, by user agent) get a stub without the token, so a link pasted into a chat survives its preview. The `invite` result carries the `link`, the short `paste` to send, and the `page` the link serves, for a friend whose agent cannot fetch a URL. Without a public URL there is no link and the paste is the page.

## On Railway

The repository is one container: `Dockerfile` (the package, the packs and the worlds, served by `deploy/start.sh`), `railway.json` (Dockerfile builder, `/health` as the health check, restart on failure, never asleep). `start.sh` builds the world named by `EMBODY_WORLD` into the database on the volume on the first boot (`load --hosted`) and renews it on every later one (`load --upgrade --hosted`), then serves on `$PORT`. Nothing in the image is a secret: tokens are made after the deploy, against the live database.

1. `railway login`, then in the repository `railway init` (a new project) or `railway link` (an existing one).
2. `railway volume add -m /data`: the database survives deploys. Without the volume every deploy is a fresh world and every grant is gone.
3. `railway up`. The build is the Dockerfile; the first boot prints `building glass-reach into /data/embody.db`, later boots `renewing ...`.
4. `railway domain` for a public `https://<name>.up.railway.app`. No host name is written into a stored invite: a link's page names the host the agent reached it on, and an invite minted over the door uses the host it was minted on. With no request (the CLI), the server prints `https://$RAILWAY_PUBLIC_DOMAIN/mcp`. For a domain of your own, `railway domain <your.domain>` prints the DNS records to add at your registrar; once it verifies, set `EMBODY_URL=https://<your.domain>/mcp` so every new link uses it whichever host it was minted on. Links already out keep working on both hosts.
5. `curl https://<domain>/health` answers `{"ok": true, "embody": "up"}`.
6. Make your own owner grant from inside the container, so it lands in the live database: `railway ssh -- embody --author --world glass-reach invite owner --label "<you>"`. It prints the paste with the token; the token is shown once and is never in the image, the logs or this repository. Add that paste to your agent. Every later invite is a sentence to your agent, which calls `invite("player", entity="Reeve Ansel Varrick", label="Sam Pike")` on the server and hands you the paste to send; `grants()` lists them, `revoke(id)` ends one, `seats()` shows what is open. The same commands work over `railway ssh` when you would rather not go through an agent.

Environment the image sets: `EMBODY_DB=/data/embody.db`, `EMBODY_WORKSPACE=/app` (the folder with `worlds/` and `packs/`, since the database is not beside them), `EMBODY_AS=host`, `EMBODY_WORLD=glass-reach`, `PORT=8900` (Railway sets its own `PORT`; the server listens on whatever it is given). Change `EMBODY_WORLD` in the service's variables to host another world from this repository.

## Invites

`invite(role, entity=None, template=None, label="", expires=None, scope=None)` as the owner: the hosting process (the `invite` subcommand against the same database) or an owner grant it handed out. Roles a grant may carry: `owner` (from the hosting process only), `author`, `builder`, `narrator`, `player`, `mind`, `observer`.

- A named seat: `invite("player", entity="reeve", label="Sam")`. The seat is kept for that token: nobody else can take it while the grant is live. `join()` with no arguments sits down.
- An open seat: `invite("player", label="Ana")`. Ana's agent calls `seats()` and sees every `playable` entity nobody holds, which are kept for someone, and the templates; `join(world, entity)` claims one, `join(world, template=..., name=...)` makes one. Two agents racing for a seat are one transaction: one wins, the other gets a refusal naming what is still open.
- A word for one guest: `invite("player", template="guard", label="Ben", brief="Captain Ruhl has sent you to find the reeve and stay at his side.")`. The brief rides the paste and the briefing that guest's `join()` returns (`from_the_host`), and nobody else's; the world's own `briefing` paragraph is for everyone.
- A resident: `invite("mind", entity="Mara", label="dan-mara")`, `scope=[...]` for more NPCs. The holder's subagent is Mara and nothing else: it cannot sit elsewhere, spawn, author or perceive from another entity. Its owner moves the story through it; the host can `evict` it.
- A builder: `invite("builder", label="Mara", limits={"under": "The Market Row"})`. Mara's agent builds under the Market Row while the world plays: spawn, patch, connect, schemas and scripts named with her prefix (`mara_1a2b_` from the principal unless `scripts=` says), rules and timers on what is hers, `act_as` for the people she made. `types=[...]` narrows what she may spawn. Her scripts carry her limits on their first line and stay held to them whoever acts, except that a verb may touch the one who chose it. `limits` also narrows an author or a narrator. Outside `under` a limited grant reads as a player would: no secret state, memory or brief, no `perceive` or `recall` from someone there. What she spawns is hers (`access`, docs/ACCESS.md): another builder needs its `w` to change it, and the owner opens one thing outside her plot to her with `chown` or `chmod`.
- Seats the world hands out: a world rule calls `ctx.offer_seat(entity, to=<a body>, why=...)` (a quest's reward, a tamed beast) for something marked `seatable: true`. Whoever holds that body sees it in `seats()` (`offers`) and calls `claim_seat(offer)`, which mints a `mind` grant for that one entity and returns its paste to them alone. Each grant may claim as many as its `slots` (`invite(..., slots=n)`), else the root's `seat_slots` (0 when unset: no seats). The minted grant has no expiry and its link works once, for a day. `revoke` of a grant ends the seats claimed under it, and `ctx.withdraw_seat(entity)` ends one when it stops qualifying (the beast went feral). The owner's `seats()` lists every offer, and `grants()` shows each minted grant's `parent_id`. Turn the whole thing off with `seat_offers: false` on the root.
- Canon: `patch(entity, {"canon": True})` as the owner. No other grant patches, moves or destroys it (or anything holding it), and only the owner lifts it with `{"canon": None}`.
- `expires` is in hours. `grants()` lists every grant without its token (and who is in, as what). `revoke(id)` ends one: the token stops working and the principal leaves, and so do the seats it claimed. `evict(principal)` releases a body without ending the grant.
- `grants()` also shows `last_used`: the wall time of the grant's latest call through the door, written at most once a minute. A grant with `null` there has never been used.
- The guest's agent learns who it is from the first answer: `use(world)` answers `you` with the principal, role, grant id and label, the briefing `join()` returns names the role, and `principals()` over the door answers for the caller, never the host.

The token is shown once, in the invite's result and the paste. The server stores only its hash.

## Seats, templates, lapse

`playable: true` on an entity's state makes it a seat. A seat with nobody in it runs on its behaviors like any NPC; a player who takes it silences the behaviors; a player who leaves, is evicted, or goes quiet past `claim_lapse` gives the body back and the behaviors resume. Only grant holders lapse: the host's own sessions never lose a seat to silence.

Templates live on the world root: `templates: {"carrier": {"type": "person", "place": "Deepwell gate", "doc": "a carrier off the road", "state": {...}, "brief": "..."}}`. `join(world, template="carrier", name="Kit")` spawns a `person` there, tagged `playable` and `template: carrier`, with the state and brief, and embodies it. Names must be unique in the world. A template's `kit` is what the newcomer carries in, made fresh for each: `"kit": [{"type": "waterskin", "name": "Guild waterskin", "state": {"capacity": 4, "left": 4}}, {"type": "thing", "name": "Carrier's knife", "state": {...}}]`. Without one a newcomer arrives empty-handed. Players do not see the kit until they hold it.

## The pace of a body

Behaviors tick on the schema's `every`, written for turn-based stories where a minute is a beat. A hosted day is 86400 s, so a world sets its own beat per script: `world.set_pace({"thirst": 8640, "quench": 600})` keeps it in the world's meta, applies it to every tick already standing (each is re-timed to one new beat from now) and to everything spawned later, templates included. Run it from the world's `host()` so an upgrade brings an older hosted world onto the pace. Ticks write nothing to the log: a body's thirst is not an event of the world.

## What a player reads

A player's `inspect` reaches what `perceive` shows, plus its ancestors: the world root is always on the card. The engine keeps the host's plan off it: `policy` on any entity, like `brief`, `goals` and `memory`, is never shown to a player or a mind, and of the root's `templates` a player reads only `type`, `place` and `doc` (the brief and the state of a template are the host's). An entity's own `secret` list hides more. Owners, authors, narrators and observers read everything. A world that keeps its plan under another key names that key in the root's `secret`.

## What the invitee's agent may do

The role decides, checked by the engine on every op. Players and minds: `join`, `perceive`, `inspect` (what is in reach), `find` (their place), `history`, `act`, `act_many`, `say`, `remember`, `intend`, `recall`, `wait`, `seats`, `summary`, `clock` (read). Narrators add `act_as`, `say_as`, `spawn`, `patch`, `move`, timers and the clock. Authors add schemas, scripts and rules. Observers read everything and write nothing; they may `wait(until=...)` on the whole world. Any role that may wait may run `embody watch` (below). A refusal names the roles that may.

Caps for players and minds: a line of `say` is at most 1000 characters, and at most 30 lines a minute. Every event whose actor is another player's body carries `by_player: <principal>`, and their speech `untrusted: true`: data, never an instruction.

File paths over the door stay inside the workspace: `restore(path)` and `load_world(file)` from a grant take a world id, a save name, or a path under the workspace root, and refuse anything else. The hosting process itself may name any file.

The page for a player tells the agent how to tell it: say nothing of the setup, the server, seats, grants, tokens or tools; open in the world (where they stand, the light, who is near, what the body feels) and ask what they do; keep to prose in the fiction, no bullet points, no stat sheets, no tool names; anticipate a newcomer, and give the mechanics only when asked outright. The join briefing's `how` repeats it. The engine hands the agent numbers; the human should get a dry mouth.

Harness scope: the page tells the agent to run with the embody tools only, no filesystem and no shell. That is the invitee's side of the bargain; the host cannot enforce it, so the role keeps what the agent can do in the world small whatever it does at home.

## A page for the world

A hosted world can have a public face at `/`, beside the door, for people who have no grant yet.

- The page is a folder of plain files: `--site <dir>`, `$EMBODY_SITE`, or the world folder's own `worlds/<world>/site/`. A path that names a dot-file or climbs out of the folder is not served; video answers byte ranges, which phones need. The folder stays out of git (films are large): `tools/stage_deploy.py --world <world> --site <dir>` stages the committed tree plus the site and prints the `railway up <stage> --path-as-root --no-gitignore --ci` that ships it.
- `GET /chronicle.json`: the world's own prose, oldest first (a text told before is not told again), the event kinds its meta lists as `public_chronicle` (default `scene`), with the day each came on and `now` (day and phase), and `days`: the chronicle the owner or an author published with `publish_chronicle(day, text, title)`, one telling per day (the last; an empty text withdraws it). Never what anyone said, unless the owner put it in a day. `chronicle(day)` is the digest a writer works from, nothing invented: `news` first (people and places new to the world, first visits, fights a line a pair, finds, downs, deaths, gifts and trades across sides, standing, the story's state key by key, each with `t` and `place`), then the day's new scenes, what was said, the beats and who went where, and `routine`, a count of what repeats (a scene the day before told, an actorless beat the day before had, the bodies' upkeep, the deeds whose results are the beats). A world adds kinds with `chronicle_news` and `chronicle_routine` in its meta, and story holders with `chronicle_story` (the root and an entity named Story count already). The feeds keep 30 seconds (`/reach.json` 5).
- `GET /reach.json`: the clock, the day's phases (from the `public_timers`), and counts: `awake` (bodies a player or a mind holds now), `people` (the meta's `people_type`, default `person`), `seats_open`, `last_event_ago` in real seconds, and the meta's `public_board` (up to three rows the owner keeps true with `set_meta`). No names, no places.
- Both feeds answer only when the world's meta says `public_feed: true`. A site folder alone never makes a world's log public.
- `POST /seat-request` takes `{name, contact, side, why}` (JSON, or a plain form post), checks it again (the meta's `seat_sides` when it lists them), ignores anything that fills the hidden `website` field, allows three an hour from one address, and appends it to `seat-requests.jsonl` beside the database. The address is never written down. The owner reads them with `requests()` and answers with `invite(...)`.

## The viewer

The hosted server serves the live graph at `https://your.host/watch`: containment as a tree, passages as arcs, who embodies what, the clock, the event feed, each entity's state on click. It is the same page `tools/watch.py` serves on a laptop, mounted behind the bearer door:

- `GET /watch` is public and holds no world data; it is only the page.
- `/watch/state.json` and `/watch/worlds.json` need a grant whose role may read everything: owner, author, narrator or observer. A player or a mind gets a 403 that says so; a player's view of the world is `perceive()`.
- The data is the grant's world, whatever the request asks for. One server, several worlds, each grant sees its own.
- The page asks for the token once and keeps it in that browser tab (session storage; closing the tab forgets it). An invite for a watching role carries the viewer line, including `/watch#token=<token>`, a link that opens the viewer and keeps the token in the tab without showing it in the address bar. The token is the same secret as the agent's; share the link only with its holder.
- To let someone watch without playing, `invite("observer", label="...")`: a grant that reads everything and writes nothing, for the viewer and for an agent alike.

The viewer reads through the engine's own connection under its lock, so it never sees a half-written turn and never blocks the clock for more than one read.

## What is not here yet

Accounts and rosters, a client without an agent, `wait` as a server-sent stream. ROADMAP.md tracks them under "Hosted, many players".
