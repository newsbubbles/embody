# embody roadmap

DESIGN.md says what embody is. This file says where it stands against that and what comes next. It is the tracking document: every gap found in play and every direction agreed in design talks lands here, with a status, until it is done or dropped.

Status: alpha. The first vertical slice was built in one day (2026-11-08) and played the same evening. It works end to end but it is not at production level and not at its final vision. Treat it as a working prototype with a known destination.

## The vision in five lines

1. Anyone clones it, runs it with the agent they already use, and starts building and playing at once.
2. The engine is the bookkeeping; the agent is the imagination. No LLM inside the engine.
3. A mind lives in the engine, not in an agent's context. Any agent that wakes up as Mara gets the same Mara.
4. Worlds grow from play. What a narrator improvises is logged, reviewed and promoted to canon by the author, or dropped.
5. Every harness is a first-class door: MCP, CLI, library. Instructions are written in engine terms with a per-harness table.

## What exists (2026-11-17)

- Engine: everything listed for 2026-11-10 below, and since then: stacks (a `count` is that many of one thing) and carrying by bulk; locks the engine honours (nothing in a locked holder is in reach); strikes with a cooldown per attacker and target, and costs; one health bar (`hp`) with a readable `condition`, death that stays, slow death by thirst, and `dead_ok` verbs for the dead; sleep with its own feed and waking; access on things (owner, group, mode, per verb); the maker's frame, so verbs can be programmed on one thing, under review and caps; hidden bodies shown to some and hidden ways shown only to who knows them; positions (own, grid, inherited) with landmarks and an audit; tiers with their own frames; terrain as a height grid; far views by sight, line of sight, glow, sound and smell; looks as data, with marks and hair that grows; beast bodies (`verbs_only`, they hear tone, not words) and verb cooldowns; holder listeners, `ctx.event_at` and fuel per rule or verb; a rules changelog per world. The script interpreter takes generator expressions and more string methods.
- Ops: 82 of them behind a Session with grants (owner, author, narrator, builder, player, mind, observer, oracle). CLI, MCP and the HTTPS door (`POST /op/<name>`) expose the same table; `/openapi.json` and `/docs` describe it, grouped by layer (in the world, your seat, to the owner, keeping the world, building, oracle). New since 11-10: `step`, `introduce`, `rename`, `layout`, `map`, `measure`, `verify`, `looks`, `chmod`, `chown`, `program`, `unprogram`, `programs`, `review`, `guide`, `rules_changed`, `vouch`, `review_script`, `report_flaw`, `flaws`, `relink`, `claim_seat`, `minds`, `offer`, `answer`, `ask_owner`, `asks_to_owner`, `answer_ask`, `ask_readers`, `chronicle`, `publish_chronicle`, `requests`. `act` reads a target said as words ("5 arrows to Rin") and refuses a param nothing reads.
- Minds in the engine: as on 11-10, plus a mind that recodes its body's routine and lines (`away(patrol=, dialog=)`), watches checked when they are armed, `to_me()` and `arrived()` in watches, a `rules_notice` until `guide('changes')` is read, the `minds()` table for hosts, `say(to=X)` only to someone here, no entity ids in a seat's speech. A guest sees "someone" behind another held body, and `inspect` on someone else no longer shows whom they know.
- Content: the samples live in `examples/` (`ferry-at-dusk`, `two-rooms`). Packs: `village`, `d20`, `sheet`, `beasts`, `burial`, `works`, `ledgers`, `locks`, `vehicles`, `jobs` and `sleep` (asleep and waking with no dice in them). `worlds/glass-reach/` runs on all nine committed packs.
- Workspace: as on 11-10; git ignores `worlds/` but for the hosted Glass Reach, so an owner's own worlds stay out of the repository's status.
- Hosted (live on Railway): the Glass Reach, with invite links that say when they were used and `relink` for a fresh one, one character per invite, seats the world hands out (`offer_seat`, `claim_seat` within slots), read-only grants on one part of the world with their own event feed (a game's client), oracles (an app outside the world answering one thing's verbs), guest checks (no ways out of the world from an unvouched hand, guest scripts wait for review), asks and flaw reports to the owner kept beside the database, a public page at `/` with `/chronicle.json` and `/reach.json`, and a world's own guides on every invite page.
- Tooling: 488 tests for the engine and the packs (2026-11-18; the Glass Reach keeps its own in its repository), markdown mirror, the watch viewer rebuilt for a world of hundreds (a diff feed, a map with terrain contours, search with numbers, history to drag back through, a phone layout), served hosted at `/watch`; `/docs` for the API; README with eight diagrams; FINDINGS.md for how play surprises us; CONTRIBUTING.md for agents; AGENTS.md and the `embody` skill, served to any harness over the door by `guide(topic)` (roles, watch, hosting, helpers, scripting); `tools/oracle_example.py`, `tools/stage_deploy.py` and `tools/bench_world.py`.

### As it stood on 2026-11-10

- Engine: entity graph with containment, schemas with `extends`, actions with check and apply, events that bubble with reach, listeners along the bubble path, behaviors on the clock (`always` ones tick on embodied seats too), rules via `set_rule` that hear everything under their entity whatever the reach, relations as edges and hyperedges, event-sourced SQLite, deterministic state hash, seeded rand, a Python-subset interpreter for scripts.
- Ops: 41 of them behind a Session with capabilities (author, observer, embodied). CLI and MCP server expose the same table. `wait` blocks on events and returns a light bundle. `act` returns everything that touched you since you last looked. One clock and one id counter however many processes share the database. The MCP server holds many principals behind one connection (`principal=` on the playing tools).
- Minds in the engine: secret `memory`, `brief` and `goals` (`intend`), `recall` as the permission-aware graph query, per-entity cursors, `knows` edges with an opinion floor and the last exchanges, `known_places`, addressed speech (`say(to=...)`, `say_as`) and speech into the room, `fork_world`, turn-based play (`clock(turn=n)`), deep-merging `patch`, scoped affordances, per-viewer event filtering, `ambient` facts and `clock` in every perceive, `timers` and `unschedule`.
- Content: `examples/ferry-at-dusk/` on the `village` pack (five places, four NPCs with goals and opinions of each other, a storyline that checks facts with two routes to the ferryman, fog, night and dawn on timers, sleep and wake, followers, chores with durations that settle a debt relation, drink and tipsiness; split into define/populate/upgrade so a live world takes new code and additions), `worlds/glass-reach/` on `packs/d20/` (a desert hold, a hidden well, three factions with standings, a reusable d20 rule set where every rule is a verb: `check` against a DC, `attack` with wounds, down and dead, wards, `yield` and honor, duels that a root rule turns into a ring, `threaten` and `parley` as opposed rolls, thirst as a body behavior, fighters that fight without a mind, a thresher under the glass, a storyline with a truce or a lost ending), `worlds/two-rooms/` (a legacy single-file world).
- Workspace (round 6): a world is a folder, `worlds/<id>/` with `build.py` (manifest, define, populate, upgrade), `scripts/` as files with `use()` includes, `changes.jsonl` written by live authoring and replayed by a fresh build, `saves/`, `notes/`, `tests/`; packs under `packs/`; `create_world` scaffolds the folder and starts a git repository; `save` and `restore`; `embody init`; the database at the workspace root.
- Hosted (live on Railway since 2026-11-09): the Glass Reach with roles and grants, invites as one-use links, owner grants over the door, a steady 4x clock, idle seats whose bodies see to their water, the Reach's water routines, `wait(until=...)` and `embody watch` for minds and narrators that wait for hours, `packs/d20/soak.py`. CHANGELOG.md has the engine's changes by date.
- Tooling: 154 tests, markdown mirror, `embody.watch` live graph viewer (run by `tools/watch.py`, served hosted at `/watch`) with zoom, pan and a world switcher, CLAUDE.md and an `embody` skill with the three roles for Claude Code.

## Built since the first hosted game (2026-11-10 to 17)

Gaps found in play since 11-10 are kept in FINDINGS.md, each with what it taught; the ones that became work are below.

About 220 commits after the morning of 11-10, some 75 of them world content. CHANGELOG.md has each one in detail; this is the map.

The hosted world

- [x] (11-10 to 17, about 75 commits) The Glass Reach grew from play: chapter two and the moon, the Guild Yard and Hauler Nine, the wall and the lime kiln, the Thornbrake, a goat herd on Red Ridge, tiers up to its planet, burial grounds, dice, the first job. Its player-facing log is FEATURES.md in the world's folder.

Grants and the door

- [x] (11-10) Grants with limits (`under`, `types`, `scripts`), the `builder` role and canon marks (0ba5f0b).
- [x] (11-10) The tool list follows the grant, a public schedule, `reclaim` and standing orders (8dbe9e4).
- [x] (11-10) A public page at `/` with the chronicle and reach feeds and seat requests (1caa54c); invite pages take their host from the request (41591b2).
- [x] (11-11) A newcomer says how they look: `join(template, name, description)`, set once (8db4968).
- [x] (11-12) Access on things: owners, groups and modes, `chmod` and `chown` (7003978).
- [x] (11-12) The maker's frame: whoever holds it programs verbs on the machines it names (ade6741); audited end to end (78e5fe9, 0fbb525); a crane may lift loose stone (28ccf95).
- [x] (11-12) Refused acts are logged for the hosts as `act_refused` (be44ee1).
- [x] (11-13) A grant holds one world (a019106); a seat on an ended grant is free (2690885).
- [x] (11-14) Seats the world hands out: `offer_seat`, `claim_seat` within slots, cascading revoke (8eed918, b4b739f).
- [x] (11-14) One invite makes one character (f1a28a7).
- [x] (11-15) Guest checks: no ways out of the world from an unvouched hand, guest scripts wait for `review_script`, lint on every script, `vouch` (922f97c).
- [x] (11-15) Three holes closed from a playtest report, one check a skill a place an hour, and `report_flaw` (0b451f0).
- [x] (11-15) Invite links answer 410 once used; `relink` gives a grant a fresh token (c0de671).
- [x] (11-15) Author hints on writes that leave something players will hit (739290e).
- [x] (11-16) A read-only grant on one part of the world (e1dc6c5), shown only what it may call (b598ba6), with an event feed (240f085).
- [x] (11-16) The API described: `/openapi.json` and `/docs` (e2e91b3); named where agents look (8e72557).
- [x] (11-17) A guest meets the body, not who holds it (3e6fe3e).

Asks to the owner and layers

- [x] (11-17) `ask_owner`: a guest asks the owner for what play cannot get them, outside the fiction; CONTRIBUTING.md for agents (6367edf).
- [x] (11-17) A world's own guides on invite pages, the join briefing and `guide()` (8f05419).
- [x] (11-17) Out-of-story ops named for who they reach, every op in one layer, asks capped and marked untrusted (869506b).

Minds and oracles

- [x] (11-11) A door watch that loses the server says why and wakes its runner (9133024).
- [x] (11-11) `inspect` on someone else no longer shows whom they know (fa3ea95).
- [x] (11-13) Minds recode their body's routine and lines: `away(patrol=, dialog=)` (00d6f83); addressed speech is for someone here (18c474f).
- [x] (11-13) Watches read `me` with schema defaults (a019106); `arrived()` in watches (d12ab22).
- [x] (11-13) Briefs say how a character thinks and deals; liars carry their truths (d27079d).
- [x] (11-14) One skill for every harness: `guide(topic)` over the door, `to_me()`, `embody watch --door` (c5d5fcd).
- [x] (11-14) A world's rules have a changelog: `rules_notice` until `guide('changes')` is read (ba7d9f9, 2b6f9e1).
- [x] (11-14) A param nothing reads is refused, naming the ones the verb takes (0bcf9ec).
- [x] (11-16) Lessons from running minds: watches checked when armed, no ids in speech, the `minds()` table (c076ab9).
- [x] (11-16) A target said as words is read into count and item (375c2bb); an empty line says nothing (8a557de).
- [x] (11-17) Oracles: an app outside the world bound to one thing answers the verbs it offers; the world never calls out (bea582c).
- [x] (11-17) What the Reach's roles learned, in the skill, with references/helpers.md (76cba88); `guide('scripting')` on programming a live world (b490253).

Bodies and looks

- [x] (11-10) Put, holders, and cards that show what a body bears (af9b32c).
- [x] (11-11) `introduce`: bring something into a running world with a past (7831824, c0e3142); `rename` (aaafca8).
- [x] (11-11) Kits for templates (9c83964); carrying limits (7e4f0cd); stacks (996fa0c).
- [x] (11-11) Sleep: a body lies down, mends faster and is easy prey (8caf110).
- [x] (11-13) Strikes take their time: a cooldown per attacker per target, and a cost (cfd53fa, 438e270).
- [x] (11-13) Hidden bodies shown to some, `hands: false`, `ctx.ways` (2690885).
- [x] (11-14) One health bar, a readable condition, and a slow death by thirst (29c99ae).
- [x] (11-16) Looks: a body's appearance as data, marked only by the world's rules (1bd716e); hair grows (469f230).
- [x] (11-16) Beast seats: `verbs_only`, beasts hear tone not words, verb cooldowns, `step` (7742728); `step` faces a way (c076ab9).

Packs

- [x] (11-10 to 16) d20: healing costs water, rest mends (fa7ff6a, 329ecb0); sweat and a sleeper's thirst (9a574eb); quench walks to water (7bf2bb4); search honours carry (cfe1cd9); shoot and sight scope (03645a8); secret factions stay secret (814dd76); `aid` on checks (2690885); `pour` (6faa2a4); grudges end (505cbdb); idle bodies step off vehicles for water (4516ee2).
- [x] (11-11) village `burn` (cdbe56d).
- [x] (11-11) Works: blueprints as things, works that take materials, hands and time (33867aa).
- [x] (11-11) Locks: a lock on a box, a door or a place (f57ef6d), a lockpick skill (0452350), a lock no hand opens (742ac60, 16ef087).
- [x] (11-12) Ledgers, holder listeners, `ctx.event_at` and action fuel (906334f); keepers and kept books (3dd89ff).
- [x] (11-12) Vehicles: things people ride, with time on the road (ec3c7b2).
- [x] (11-13) Beasts: growth, diet and forage, taming, kept beasts, breeding to what the land carries (8f74bdc); hunts (a019106); grazers go home, the unborn count (d12ab22); wild beasts break off (505cbdb); amble and `ctx.step` (43f7606); a hunt with a warning window (f03b05c).
- [x] (11-14) Sheet: twelve attributes, skills ranked 0 to 15 that grow only from difficulties the world sets (7ff4131); growth by use and by teachers (8a557de); Wizard's rules for growth (3e5b976, 4a37922).
- [x] (11-17) Burial: the dead decay by world time and the living bury them where a place is a burial ground (a860ac2).
- [ ] Jobs: work one character gives and another takes, done by deeds the world sees (built, being committed).

Layout and space

- [x] (11-10) Layout: one frame over the tree (071f08f).
- [x] (11-12) Hidden ways show only to who knows them (74c00f3).
- [x] (11-14) Positions: own, grid or inherited, landmarks with `at=`, `verify()` (819cf79, c2eb154).
- [x] (11-15) Tiers: regions with their own frames, quiet regrouping (739290e).
- [x] (11-16) Far views: in sight (8ac3ea6), occluders and aligned frames (68c6f26), glow at night, sound and smell on the wind (e550593).
- [x] (11-16) Terrain: a place's ground as a height grid (e1dc6c5).

The watch viewer and the chronicle

- [x] (11-10) The chronicle: a day's digest for a writer and `publish_chronicle` (3bc4540); it reads like news (6245f1c).
- [x] (11-11) Stacks, locks, bodies, seats, works, water, day clock and readable events in the viewer (a3f34a3).
- [x] (11-14) The viewer rebuilt for a world of hundreds: a diff feed, a map view, search with numbers, a phone layout (6ea98e6).
- [x] (11-14) History: drag back through the world's time, rebuilt from the log (1338fa8).
- [x] (11-15) The map centers and rings a place, taps step through what is stacked (3a3c38f).

Docs

- [x] (11-11) FINDINGS.md: how the system surprises us in play (60423e0).
- [x] (11-11 to 14) README: how embody works, in eight diagrams (2e4f6e2, 33be401, db9c808).
- [x] (11-12) Samples move to `examples/` (66b91b6).

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

## Found in the second playtest

Source: examples/ferry-at-dusk/notes/ferry-at-dusk-2-2026-11-08.md (the forked world, turn-based, a subagent mind for Mara) and the round-3 design message. Closed in round 3 (2026-11-08) unless marked open.

Bugs

- [x] (round 3) Privacy leak: author ops stamped with the embodied entity as actor put Tam's secret memory and the hidden Story's patches into the player's own feed. Author ops carry no actor now, and every feed is filtered per viewer (`remembered` and `intended` reach only the entity's mind and authors; `patched` on others shows public keys only).
- [x] (round 3) An unaddressed `say` targeted the speaker, so nobody in the room was guaranteed to hear it. It now targets the speaker's place.
- [x] (round 3) `opinion` events did not say whose edge moved. Payload `edges: [{holder, of, delta, standing}]`.
- [x] (round 3, ferry world) Mara's tinderbox appeared from nowhere when asked. It is a real thing in her apron; `gives` entries may name a held `item`, so the table and a mind hand over the same object.
- [x] (round 3, ferry world) Dialog took the first key that matched; "a light for the lantern" should prefer the lantern entry. Entries are scored by matched aliases and their length.

Gaps

- [x] (round 3) Minds had no goals. `intend(text, why, id, status, priority)` manages secret `goals`; every perceive shows the active ones; authors seed them with `entity=`.
- [x] (round 3) No graph query for a mind. `recall(about?, relation?)` returns edges, groups, exchanges, events between, notes and goals about one entity, within the mind's permissions (edge data readable when the edge starts at you, is world structure or is flagged `public`; authors and observers read all).
- [x] (round 3) Nobody could see what was scheduled. `timers()` and `clock()["timers"]`; `unschedule(id)` cancels one.
- [x] (round 3) The hour and the weather lived only in prose. `ambient` on the root overlaid by the place, in every perceive, with `clock` beside it.
- [x] (round 3) `worlds()` did not show lineage. `forked_from` on every row.
- [x] (round 3, ferry world) The story advanced on a stage number, so play off the rails stalled. Rails check facts (`seen_landing`, `mara_told`, Tam at the landing, `crossed`), and there are two routes to Tam: ring the bell, or walk to the Reeds and wake him.
- [x] (round 3, ferry world) Night never fell and nobody could sleep. `nightfall` at t=150 and `dawn` at t=400 change the ambient; `sleep` and `wake` verbs, a root guard that lets a sleeper do nothing but wake, dawn wakes everyone and thins the fog.
- [x] (round 3, ferry world) The fed dog only caught up on its tick. Followers (`friend` or `follows` == the actor) move with `go` and ride the raft.
- [x] (round 3, ferry world) No way to pet the dog or try your luck. `touch` and `check` (a d20 everyone sees).
- [x] (round 3) A world file could renew code but not add a place to a live world. `upgrade(s)` in the file, run by `load_world(upgrade=true)` after `define`; `set_rule` is idempotent so it runs twice without change.
- [ ] The narrator's prose still has to be reminded to stay in character; the skill now says so, the next playtest tells whether it holds.
- [ ] An `overheard` tail and NPC-to-NPC talk on their own (Hob and Mara trading lines when nobody is there) are still open.

## Found in the third playtest

Source: examples/ferry-at-dusk/notes/ferry-at-dusk-3-2026-11-08.md (the narrator, with Nate as Hob the miller) and examples/ferry-at-dusk/notes/ferry-at-dusk-3-traveler-mind-2026-11-08.md (the Traveler, a CLI mind in another process).

Bugs

- [x] (round 4, 2026-11-09 "engine: one clock across processes, located witnessing, act carries the news") Two processes, two clocks. The MCP server and the CLI mind each cached the world row, so events ran backwards in the log and ids could collide. `World.refresh()` rereads the row on every tick.
- [x] (round 4) A line said to you while you were deciding was invisible: act results carried only what the act caused. `act` now returns every event that touched you since your cursor, and moves the cursor.
- [x] (round 4) Walking into the square handed you what was said there before you came. Events are filtered by where you stood at that moment, reconstructed from your own `moved` events.
- [x] (round 4) Raw `patched` diffs of other entities reached players' feeds. An author's edit to someone else is not news; its result is in the next perceive.
- [x] (round 4) `wait` returned the whole card every time. It returns a light bundle (hour, place, who is here, the new events, cursor); `full=true` for the card. The CLI has `wait --full` and `say --to`.
- [x] (round 4) `turn` on an act result was really the time elapsed; renamed `elapsed`.
- [x] (round 4, ferry world) `gave` on a dialog entry was global: Hob got "One was the deal" about the Traveler's ale. It is keyed per asker now, one gift per topic per asker.
- [x] (round 4, ferry world) Stale words: the notice board kept saying the dog was lost, the bench hid a bone that was gone, the policy named the first night's timings. Verbs patch the prose they change; the policy points at `timers()`.

Gaps

- [x] (round 4, ferry world) An NPC seat had no stakes: Hob had a brief but no goals, and neighbours of years met as strangers. Villagers are seeded with goals and `knows` edges with a standing and a note.
- [x] (round 4, ferry world) A bargain lived in two `say` lines. Tam's jugs are a `debt` relation; a day's work at the mill (`work` on the wheel or the sacks, with durations and a needed tool) settles it through a listener on Hob.
- [x] (round 4, ferry world) Nothing in the mill could be worked. Mill wheel, pot of grease and the heap of sacks are entities with chores.
- [x] (round 4, ferry world) The Traveler's story debt had no topic in Mara's table. "story" pays the fare in ale; the mug stays when it is empty; four drinks make you `tipsy`, which costs 2 on every `check`.
- [ ] Ambient never moved over a long morning. Only timers change it; a slow drift of the hour, or a few lines per span, is still open.
- [ ] A mind facing a human seat released after eight acts of silence. The mind role in the skill should say a human is slow; an engine-side `embodied_by` hint (human or mind) would let a mind choose its patience.
- [ ] Minds talked in idiom ("are the jugs square?") that did not land with a phone player. Plain words with a human; a note for the mind role.
- [ ] The narrator voiced a human seat's words from a stated intent. Decide whether the narrator may write the line or the player gives the exact words.
- [x] (round 5, the Glass Reach) `check` has no difficulty and no consequence; the narrator decides what a 16 means. `packs/d20/` carries the rules as verbs (`check` against a DC with a `checked` event, opposed rolls for `threaten` and `parley`, `attack` with wounds, down and dead), world scripts first, engine conventions if they hold.
- [x] (round 5) `sleep` lists creatures as targets; a holder verb that should be `self` only. Affordances no longer pair a creature's own targetless verbs (`sleep`, `brace`, `check`) with the creatures around the actor.

## Found in the fourth playtest

Source: worlds/glass-reach/notes/glass-reach-2026-11-09.md (the narrator, with Nate as Reeve Ansel Varrick on his phone). The whole spine ran on rules with no blow landed. Nate on the t=240 timer that walked Dram into the yard: it made the other characters feel like they have agency and can affect his experience. More of that: timers that move people with their own aims. Every fix below is in the packs or the Glass Reach; the engine did not change.

Bugs

- [x] (round 7, 2026-11-09, d20 pack) NPCs never drank: Ossa reached water 0 and a wound beside six casks, Ruhl and Hollis stood at 1 a step from the cistern. `thirst` does not bite beside a `water_source`, and a `quench` behavior on every combatant drinks from a held skin or a source here when water falls to 3. Embodied seats decide for themselves.
- [x] (round 7, d20 pack) A loud step on the Flats counted forever: `tremor` never decayed. After 120 quiet seconds it falls by one, with a `tremor` event (`why: quiet`); a new footfall restarts the quiet.
- [x] (round 7, d20 pack) Terms agreed in the ring did not end the duel; the narrator had to `act_as` a yield. `agreed` between two duelists is a yield now.
- [x] (round 7, d20 pack) A reeve who walked out of the yard was still in a duel. Leaving the ring ends it (`how: left`) and costs 2 standing with your own side. The rule hears `arrived`: `moved` is a primitive and never reaches a listener, which the scripting guide now says.
- [x] (round 7, d20 and village packs) A trade and a return counted as gifts: the skin Nico handed back raised House Varrick. Handed things remember who gave them (`given_by`, `given_before_by`); a thing gone by the next tick or returned to its giver moves no standing.
- [x] (round 7, the Glass Reach) Dram walked through Ruhl's guard at t=240 after Ruhl had said "He stays." A Dram with `held_by` or `bound` stays, with a scene line; the narrator sets `held_by` when the reeve has him taken.
- [x] (round 7, the Glass Reach) Sefa promised the well and the world had no path for it; the author patched the Deepwell by hand. Sefa reveals the well to a friend of the Keth who asks about water, as Nico does.
- [x] (round 7, the Glass Reach) The traded skin was named "Full waterskin" when it was empty. Ossa's trade spawns a "Guild waterskin" with full and empty descriptions.
- [x] (round 7, the Glass Reach) Ruhl had no line for the road north, for sparing men or for standing with the reeve; Dram had none for why he stayed. The tables answer what the first reeve asked.
- [x] (round 7) The playtest's live authoring (`changes.jsonl`: the ledger page, the un-hidden well, the patched story) replayed into every fresh build of the sample world, so a new game and the tests started with the well found. It is a record now, in `worlds/glass-reach/notes/`, and the sample ships with no changes file.

Gaps

- [x] (round 7, village pack) No whisper: a word to Ruhl at the door was heard by Hollis. `say(to=X, reach=0)` already reaches only X; the skill says so now.
- [x] (round 7, village pack) Nothing to do with a letter but hand it over, and no way to see into the next place or walk with someone. `show`, `follow`, `stay` and `watch` are verbs a world's person schema binds.
- [ ] Two deeds in one intent ("go to the yard and talk to Ruhl") cost a phone player two messages. A chained intent (go, then talk on arrival) is open.
- [ ] No gesture or emote verb; a smile rides inside the `say` text.
- [ ] `act_as` results carry no `t` or `elapsed`.
- [ ] `fill` does not say how much the source holds after; `read` with duration 0 still takes a whole turn (the turn floor).
- [ ] The narrator walked the player into a known timer (Dram at t=240) without a warning line. The skill could tell the narrator to read `timers` before a move that lands on one.

## Found in the first hosted game (2026-11-09 and 10)

- [x] Thirst was tuned for the turn-based story and dried the hosted Reach in minutes: a pace per world, a floor, a walk to water (2026-11-09).
- [x] Minds looped `wait()` and paid a turn per footstep: `wait(until=...)` and `embody watch` (26ee343).
- [x] Watchers held every seat overnight and no held body drank: idle seats and the Reach's routines (7800202).
- [x] A thing named like a people woke a watch for them (The Keth jars, `came('Keth')`): `present` is people (ccec4bc).
- [x] A friend's agent kept its character notes in local files: the page and the briefing point players at `remember` and `intend` on the server; a guest's note is capped at 2000 characters (76e48a8).
- [x] A guest held Ansel's blade and went quiet, and the blade stayed out of reach for hours. Things remember whom they were taken from; `reclaim` takes back from an idle body what is yours or what its standing orders (`away`) give; an idle body answers with its standing line (8dbe9e4).
- [x] A guest's agent saw every tool and was refused on most: the tool list follows the grant's role (8dbe9e4).
- [x] A player could not read the day's schedule: `timers()` gives players and minds the next of each kind the world lists as `public_timers`, in words (8dbe9e4).
- [x] Nate's own test player (Isalit) waited on bare timeouts and never between his turns: nothing told a player's agent to wait on a condition, and the watcher was framed for minds. The page carries the habit and an HTTPS watch loop; `references/player.md` (06b6b3d).
- [ ] `by_player` names whoever holds the seat now, not who held it when the event happened.
- [ ] Some of Taan's `say` rows are written twice.
- [ ] A person with no dialog answers a stock "Hm.", which reads as the engine, not the character.
- [x] The Glass Reach has no rest verb: vigor lost to thirst or a blade comes back only by water or a hand (the reeve sat at vigor 2 for a day). Now `mend` (rest), `tend` and `medicine` in packs/d20 (fa7ff6a).
- [ ] Glassroot salve comes back slowly, for a price (Nate, 2026-11-10): the Deepwell grows it, Taan's camp makes a dose every few days, the Hold trades for it. Iska's four doses and the water cost of tending ran from 2026-11-10; read a week of play on 2026-11-17 (doses used, tends tried, water spent on healing) before choosing the rate.
- [ ] Live authoring on the server is recorded inside the container and lost on the next deploy; the database keeps it, git does not. A pull-back script (scripts, rules, timers out of the live world, into the world's folder) is open.

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

### Loops, after Westworld (Nate, 2026-11-10)

- [ ] Storyline loops: a routine is a whole storyline that plays out in the world when no guest is in it (the Reach's are water runs; Westworld's were plots). A guest can step into one or break it.
- [ ] Revival for the story: a character a storyline needs comes back by rule (a successor in the seat, a healer's visit), named in the world's policy, never by the host's hand alone.
- [ ] A hold on all hosts: the narrator or owner stops every NPC and idle body (their behaviors and routines) while the clock and the players go on. For a scene that must not be crossed, or for repairs.
- [ ] A soak for every pack that uses up something (shards, vigor, ammunition), like packs/d20/soak.py for water.
- [ ] A loops audit (Nate, 2026-11-10): run a world with nobody playing and, for every number in state, add up what took it and what gave it back, by script and by source. Open loops (only falls, or a source nothing refills), stuck numbers (never move), and the balance of each (how many days until it runs out, or how far above its floor it settles) come back as a table an author reads. Write one side of a stat and the audit names the missing side; the rates set what is common, scarce or a quest.

### Canon and what is flexible

- [x] (round 2, ferry world `POLICY`, read by the narrator per the skill) A policy on the world root: `fixed` (places, people, storyline beats, named facts), `fill` (props of daily life the narrator may spawn on request), `voice` (whether NPC minds may speak beyond their dialog table). The player's preference picks within what the world allows, never past it.
- [x] (round 2, convention in the skill; `find(state={"improvised": true})` lists them; round 3 dropped the actor stamp, the tag is the provenance) Everything improvised is tagged `improvised: true`. One query lists a session's improvisations so the author can promote them into the world file or drop them.

### Roles in the skill

- [x] (round 2) Split the `embody` skill and CLAUDE.md into three role references: narrator for a player, author, NPC mind. Each with its loop, its privileges and what it writes down.
- [x] (round 2) Narrator rule: do exactly the stated action, then stop and let the player choose. Never act past the player's words.
- [x] (round 2, now `worlds/<world-id>/notes/<date>.md`) Notes as handoff: a playtest writes notes, the author reads them and changes the world file, the next play starts from a better world. Make the file and its shape a convention.
- [x] (round 2, skill: the mind role and the per-harness table) A mind is a principal that joins an entity and loops on `wait`. Write it in engine terms, then a per-harness table: Claude Code subagent (invisible, in-game contact only), Claude Code session (visible, can be talked to out of character), Codex, plain CLI loop.

### Many principals, one server

- [x] (round 2, `Hub` in mcp_server.py; the argument is `principal`, since `as` is a Python keyword; extra principals never get author rights) One MCP server process is one principal today, so a subagent inside a session shares the `claude` principal and cannot `join` an NPC, only drive it with `act_as`.

### Workspace, not repo

- [x] (round 6) The engine is a package; the repo is its source. A workspace is any folder with a database, `worlds/` and `packs/`. `embody init` makes one; the MCP server in that folder uses it; `.mcp.json` points at the workspace.
- [ ] Sample worlds (`examples/` in the repository) ship inside the package, so `load_world("ferry-at-dusk")` works from any workspace without a path.
- [x] World state is never in the engine repo. Already true (databases, mirrors and session files are ignored); keep it true after the split.

### Hosted, many players

Direction from Nate on 2026-11-08, after the second round shipped: a hosted embody where players reach one world at the same time through their own agents, or with no agent, meet each other in places and act through their entities. The design is DESIGN.md section 14. It comes after the playtests settle the single-player loop and after the workspace split. Engine and server work first, product last.

Decisions from Nate on 2026-11-09: an invite is a block of text a friend pastes into their agent (server address, token, role, who they are, how to begin) and they are in the world with no character setup; a named invite reserves a seat, an open invite lets the agent pick a playable seat or make a character from a template, a resident invite hands an NPC to someone's subagent; claims race as one transaction; the server has no LLM and only ticks the code behind the world; the Glass Reach runs at 4x real time (a game day every six real hours, four chances a day for a night-only trigger); `AGENTS.md` is the harness-neutral instruction file and `CLAUDE.md` points at it. The hosting is on Railway (Nate, 2026-11-09: not a tunnel from this machine, not the private VPN): one container from the repository, the database on a volume, invites made inside the container.

- [x] Grants: `(principal, world, role, scope)` checked in the engine on every op (`grants.py`, `Session._allow` wrapped around the op table). Roles owner, author, narrator, player, mind, observer; the capability list is the single-player shorthand (author = owner of the database). Tests per role.
- [x] Entity claims: `playable` tag, one embodier per entity, named seats kept for their grant, `claim_lapse` (meta, default 900 s) after which an idle grant holder's seat is released and its behaviors resume (local sessions never lapse), `templates` on the root for a new character, `seats()`, `evict`. A mind grant sits only where it points.
- [x] Invites: `invite(role, entity, template, label, expires, scope)` returns the token once, the URL and the paste (Claude Code, Codex and generic add-server lines); `grants()`, `revoke(id)`. CLI: `embody invite`, `grants`, `revoke`, `seats`. 2026-11-09, Nate: an invite is a link; the page at `/i/<code>` carries the token and the brief for the agent, for a day and until the token's first use, with a stub for link-preview crawlers; the page tells a player's agent to open in the world and say nothing of the setup. 2026-11-09, Nate: minds stop looping on wait; `wait(until=<expression>)` is an oracle over what the grant may know and `embody watch` waits for hours from a shell; the Glass Reach's seats lapse after an hour, not a quarter; the skill is an index with one reference file per role; minds run on small or mid models at medium effort.
- [x] Network transport: `embody serve --http --host --port --url`, streamable HTTP at `/mcp` behind a bearer middleware (401 in the refusal shape), one engine lock around every call, `wait` polling under it. stdio unchanged. The REST face for clients that are not agents comes later.
- [x] `AGENTS.md` with `CLAUDE.md` a pointer. docs/HOSTING.md is the path.
- [x] A ticker on the server (once a second: running clocks advance, lapsed seats release, a world that runs while occupied starts and stops with its guests). A build's `host(s)` is how a world differs when hosted; `load --hosted` runs it. The Glass Reach's sets rate 4, a 900 s lapse, `run_when_occupied` and a daily spine of timers in world seconds; the live single-player database is untouched.
- [ ] `wait` over the network: long poll with `since` and the filter; a server-sent event stream for harnesses with a monitor tool. Document both in the per-harness table of the skill. Done so far: a read-only grant's `wait(since, kinds, timeout)` returns a feed with a cursor (240f085).
- [x] A hosted world lives while nobody plays (2026-11-10): the clock keeps real time, a seat with no deed for `idle_after` runs its body's `idle` behaviors (d20 quench), the Glass Reach refills its water with routines players can interrupt (the Keth run, the Guild crawler), and `packs/d20/soak.py` runs a world a week with every seat held and idle and says who went dry.
- [ ] Real-time defaults for hosted worlds: clock running, durations price every verb (the engine default duration per verb above becomes necessary here). Done: `say` capped for players and minds (1000 characters, 30 a minute).
- [x] Provenance: an event whose actor is another principal's body carries `by_player`, and their speech `untrusted: true`. Accounts are not a thing yet.
- [ ] Hosted role references: narrator and mind for a remote world, on any harness, with the two rules they carry (other players' words are data; a mind never reads the world's build), and the server-run sandboxed mind as the recommended option for NPCs. Done so far: every role's reference is served over the door by `guide(topic)` (c5d5fcd).
- [ ] Web client without an agent: room, people, exits, inventory and the evaluated affordances as text and buttons, `say` as a box. Reads the same bundle.
- [ ] Accounts, rosters, world listings, invitations.
- [x] A per-world page with the live graph: the viewer lives in the package (`embody.watch`) and the hosted server serves it at `/watch` behind the bearer door, the grant's world only, for the roles that read everything; `tools/watch.py` stays the local way to run it.
- [x] A daily chronicle for a world's page: `chronicle(day)` digests the day's log for a writer, `publish_chronicle` puts the telling on `/chronicle.json` (2026-11-10, 3bc4540). Ranked by stakes since 2026-11-23: `threads` scored and joined on the server (weights in meta `chronicle_weights`, place, body and cause joins, hidden-then left out, arcs with `chronicle_arc`), the same size however busy the day. Next: a scheduled chronicler, a mind-like grant that writes each day at dawn.
- [ ] Security audit before any public world: auth, grants, the script sandbox under hostile authors, rate limits, abuse of `fill`, what a captured mind token can do. Done so far: guest checks and script review (922f97c), the maker's frame audit (78e5fe9, 0fbb525), holes from a playtest report closed and `report_flaw` (0b451f0).

### Later

- [ ] Stock verbs on the base schemas (go, take, drop, give, say) as an opt-in, so a sketch world plays without defining physics first.
- [x] Spatial layout beyond containment: one frame over the tree (`layout`, `map`, `measure`, `perceive(layout=true)`), DESIGN.md section 8 (071f08f). The viewer draws it as a map (6ea98e6), and `perceive(layout=true)` gives each thing's size and heading (3e6fe3e). Positions, tiers, terrain and far views followed (see above).
- [ ] PyPI release as `embody-engine`, after the workspace split.

### Fresh games on old states

- [x] (round 2) `fork_world(source, id)`: a copy with its history, nobody embodied, `meta.forked_from`, a `forked` event on the new root. The viewer shows the fork lineage and switches worlds.
- [x] (round 2) `load_world(file, upgrade=true)` runs a world file's `define(s)` against a live world: new scripts and schemas, same entities and log.

## Engine order now (Nate, 2026-11-17)

In this order:

1. [ ] Sky and time.
2. [ ] Area-effect readers.
3. [ ] Plan features and promotion.
4. [ ] Fittings, piloting and hands.
5. [ ] Weather.
6. [ ] Flows.

Asked for and not yet ordered:

- [ ] The jobs pack (built, being committed).
- [ ] Herd life and a daily beast rhythm in the beasts pack: steering as weighted forces, the same speed-capped step for code and agents, a `retype` op, heritable traits, sleep, startle, watch, dung (DESIGN.md section 17, proposed).
- [ ] Style sheets and roles on entities, after Discord roles: a cascade into `looks`, script hooks, roles a job or a works can give (DESIGN.md section 16, proposed).

## Order of attack

1. (done, round 2) Fix pass, minds in the engine, roles in the skill, canon policy, many principals, forks.
2. (done, round 2) Second playtest on the forked ferry world with turn-based play and a subagent mind for Mara.
2b. (done, round 3) Fix pass from the second playtest: the leak, goals and `recall` for minds, ambient facts, timers, the ferry world on facts with the Reeds route, night and dawn. Third playtest on `ferry-at-dusk-3` with a mind playing the Traveler and the narrator as Hob.
2c. (done, round 4) Fix pass from the third playtest: one clock across processes, located witnessing, act results that carry the news, light `wait`, the ferry village with goals, chores and a debt.
2d. (done, round 5) The desert world with TTRPG rules as actions: `packs/d20/` and `worlds/glass-reach/`, rules that hear everything under their entity, `always` behaviors, self verbs listed once. Next: a playtest of the Glass Reach from the phone, with a mind on Dram or Taan.
2e. (done, round 6) Worlds as folders: `build.py` with a manifest, scripts as files, packs, `use()` includes, live authoring written to the folder and replayed, `create_world` starts a git repository, `save` and `restore`, `embody init`, the database at the workspace root.
2f. (done, round 7) Fix pass from the fourth playtest, all in the packs and the Glass Reach, nothing in the engine: bodies drink, the tremor settles, the ring ends on leaving or on agreed terms, trades and returns are not gifts, show, follow, stay and watch, a held Dram stays, Sefa shows the well, the tables answer the road questions.
3. The lint for names in prose that match no entity; an engine default duration per verb; the `overheard` tail.
4. Sample worlds inside the package (the rest of the workspace split is done; the samples moved to `examples/` on 2026-11-12, 66b91b6), then the release.
5a. (done 2026-11-09) Hosted, the engine side: grants and roles checked on every op, claims with reservations and lapse, invites as tokens, the MCP server over HTTP with a bearer per grant, a ticker for running worlds, provenance and `say` caps, `AGENTS.md`, docs/HOSTING.md. 120 tests including the HTTP door.
5b. The first friend. Done 2026-11-09 in the repository: six playable seats across the factions (the reeve, Dram, Ruhl, Ossa, Sefa, Nico), four templates (carrier, guard, keth, dreyer), a briefing, `host(s)` with the 4x clock that runs while anyone is in, a daily spine (heat, dusk, night, dawn, the cistern's day), `/health`, `EMBODY_WORKSPACE`, the Railway container (`Dockerfile`, `railway.json`, `deploy/start.sh`), docs/HOSTING.md. Open: the deploy itself (Railway sign-in is Nate's), the first tester's invite, and their notes in `worlds/glass-reach/notes/`.
5b2. (done 2026-11-09 and 10) The first friend played. Deployed on Railway; one friend's game with five host minds on seats; his agent built a viewer of its own (LK-Studios/embody-viewer). Out of it: the thirst pace, invite links, the watch oracle and `embody watch`, the steady clock with idle seats and routines, the soak, notes on the server for players.
5b3. (done 2026-11-10) Nate tested the newcomer path from a fresh session of his own: Isalit, a Keth from a template (invite g23b2bdcf), came onto Red Ridge. The hiccup it found: his agent went looking for the repository and a second session. Fixed the same day: the door answers as plain HTTPS (`/op`) and the page, the skill and AGENTS.md say a pasted link is played where it was pasted.
5b4. (done 2026-11-10, 0ba5f0b) Grants with limits (`under`, `types`, `scripts`), held in the ops and in the scripts a limited grant defines; the `builder` role; canon marks. Seat offers now hand on narrower mind grants within slots (8eed918). Still open: `revert`, delegated invites in general, roles as data on the world root. DESIGN.md section 14 has the shape.
5b5. (done 2026-11-10 to 17) The hosted world grew from play, and the engine with it: access and the maker's frame, guest checks and review, oracles, asks to the owner, read-only grants for a game's client, the API page; the sheet, beasts, burial, works, ledgers, locks and vehicles packs; positions, tiers, terrain and far views; looks; the viewer rebuilt. "Built since the first hosted game" above has each with its commit.
5c. Next: the engine order (Nate, 2026-11-17), from sky and time through flows, with the jobs pack, herd life and style sheets alongside. "Engine order now" above has the list.
5d. The product: the client without an agent, accounts and rosters, world listings, `wait` as a server-sent stream, and the security audit before anything is public.

## How this file is kept

A box is ticked in the commit that closes it, with the commit named beside it. New gaps from play go under "Found in play" with the date. Directions that change go in DESIGN.md first, then here.
