# Changelog

What changed in the engine, newest first: the core, the ops, the server and the packs. A world's own story lives in its folder (`worlds/<id>/notes/`) and its event log, not here. Every entry names what an agent or a host sees differently.

The version in `pyproject.toml` is 0.1.0 until the first release; until then entries go by date.

## Unreleased

- The chronicle: `chronicle(day)` (owner and authors) gives one world day of the log sorted for whoever writes it up: the world's own prose, what was said (a guest's words marked `player`), the beats, who went where, counts by kind and what is already published; notes and intents stay their owners'. `publish_chronicle(day, text, title)` puts the day on the page's `/chronicle.json` under `days`; again replaces it, an empty text withdraws it. No model in the engine: the writing is the agent's.
- `history` counts only what it shows: the kinds the engine keeps to itself (ticks, definitions, before_act) and a `kinds` filter apply before the limit, so a living world's log is no longer pages of nothing. `newest=true` reads the last `limit` events.
- Layout: one frame over the tree. The root may carry a `frame` (metres, z up, y north, optional `bounds` and a `geo` anchor); any entity a `layout` (`at`, `heading`, one extent: `radius`, `size` or a `footprint` polygon, `floor`, `ceiling`, a `mesh` reference, a `note`); a connects_to edge a drawn `route` and a `length`. Containment stays the story and layout never moves anything in the tree: what has no `at` of its own is where its container is, a body that changes place drops its own spot, a grid inside a room maps into the frame by `space.frame_origin` and `cell`. New ops: `layout(placements, paths, frame, replace)` writes many at once for authors and narrators (held to grant limits, every shape checked, what only looks wrong returned as warnings); `map(under, depth, sketch, width)` and `measure(a, b, point)` (distance, bearing, height, containment, overlap) for every role that reads the world; `perceive(layout=true)` gives distance and bearing to what is here and to each exit. Layout stays out of every card unless asked. The Glass Reach is laid out from its canon (the Hold at the origin, Red Ridge about 4.4 km east-north-east), each piece once, so a live edit survives a reboot.
- d20: healing costs water. A bare-hands `tend` spends a draw to wash the wound (a skin in hand, else a cask or source here), held or slipped, and is refused with nowhere to draw from; `mend` costs a point of water for every second point of vigor it gives back. Medicine still needs no water.
- d20: rest heals. A `mend` behavior on every combatant gives back a point of vigor a beat to a body with water in it (ten minutes in a turn-based story, the world's own with `set_pace`); above half the wound closes, and a body a wound put down gets up on its own at 2 (`rose`, by rest). New verb `tend`: bare hands (survival vs 12) get someone down up at 1; with `medicine` in hand (a new thing schema with `doses` and `heals`) a dose heals at once, no roll, the down included. `keep_behaviors(w)` gives bodies made before a behavior existed its tick. The Glass Reach mends a point every six world hours, and Iska of the Keth carries the Reach's one medicine, a pouch of glassroot salve (four doses, given once).
- A hosted world can have a public page at `/`: a folder served beside the door (`--site`, `$EMBODY_SITE`, or `worlds/<world>/site/`), with byte ranges for video. Two feeds built on the server from the world, for a world whose meta says `public_feed`: `/chronicle.json` (its scene prose, never anyone's words) and `/reach.json` (the clock, phases and counts, no names or places). `POST /seat-request` keeps requests beside the database, limited by address and never recording it; the owner reads them with the new `requests()` op. `tools/stage_deploy.py` ships the committed tree plus a site folder that stays out of git. The Glass Reach opens its feeds and lists its sides.
- Invite pages carry no host name. A stored page names its server by a mark the door fills in with the host the agent reached it on (`X-Forwarded-Host` and `-Proto` behind a proxy), and an invite minted over the door uses the host it came in on, unless the operator set `--url` or `$EMBODY_URL`. A custom domain needs no change to any page or link already out.
- A player's agent is told how to wait. The invite page for a player or mind in a running world says to `wait(until="heard('', by=...)")` for the answer before telling the human, never to loop on a bare `wait()`, and carries a background watch loop over `/op/wait` for between the human's turns (a guest has no checkout and no `embody watch`). The skill has a player reference, `references/player.md`, and its index points players at it.
- The MCP tool list follows the grant: a player sees the tools a player may call, an observer its reading tools; the host's own process sees all. `invite` over MCP and on the command line (`--under`, `--types`, `--scripts`) takes `limits`.
- `timers()` for players and minds: the next of each kind the world's meta lists as `public_timers` (the Reach: heat, dusk, night, dawn), with `when` in words and without what the timer carries. Authors, narrators and observers see every timer as before.
- Things remember whom they were taken from: a thing that passes from one body to another by someone's act, and not as a gift, carries `taken_from` until it goes home. An author's own moves leave no mark.
- `reclaim(thing)`: take back from an idle body where you stand what is yours (`taken_from` or `owner`), or what its standing orders give you. `perceive()` lists what you may reclaim under `reclaim`. World meta `reclaim: false` turns it off.
- `away(give=[{"item", "to"}], answer=...)`: standing orders for your body while your seat is idle. Others see them on your card, with `idle: true`, while you are away; the answer is said once per asker per ten world minutes (`say` with `away: true`). `away()` clears them.
- The door as plain HTTPS: `POST /op/<tool>` (and `GET /op`) beside `/mcp`, same bearer, same role check, so a pasted link plays in the session it was pasted into even when the harness loads new MCP servers only at start. The invite page says so and shows a curl line.
- A template invite (a Keth, a guard) says on its page who the guest will be, and `seats()` on that grant shows only that template.
- The global flags (`--db`, `--as`, `--world`, `--author`, `--observer`, `--json`) follow any subcommand again; `embody serve --as claude --author`, as `.mcp.json` writes it, had stopped starting.
- Grant limits: `invite(..., limits={"under": ..., "types": [...], "scripts": "prefix_"})` for an author, narrator or builder. Every write op checks them; a script the grant defines carries them on its first line (`# limits: {...}`) and is held to them whoever's act runs it, including writes through `entity.state`. A verb's script may also touch the one who chose the verb.
- The `builder` role: an author's hand under one entity (`limits.under` is required), without create, fork, save, restore, mirror or setting the clock.
- Canon: an entity whose state says `canon: true` refuses patch, move and destroy (of it or anything holding it) from every grant but the owner, and from limited scripts; only the owner sets or lifts the mark.
- The page and the join briefing say the character's notes go on the server, and that the agent's own memory of its human stays its own.
- The skill, AGENTS.md and CLAUDE.md open with what a pasted link means: a hosted world, played in this session, no repository needed.

## 2026-11-10

- Character notes are on the server, and a player's agent is told so. `remember`, `intend` and `recall` were always player ops; the invite page and the join briefing now say to keep notes there, not in files on the agent's side. A guest's note is at most 2000 characters.
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
