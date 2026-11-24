# Scripting embody

Scripts are the code side of an entity. They are written in a subset of Python and run by embody's own interpreter: deterministic, fuel-limited, no imports, no file or network access. Three shapes:

| component | functions | runs when |
|---|---|---|
| action | `check(ctx)` optional, `apply(ctx)` required, `finish(ctx)` optional | a principal calls `act(verb, target)` |
| listener | `on(ctx, event)` (or the `fn` named in the schema) | an event bubbles past the entity that carries it; with `unless_embodied: true`, only while no principal embodies that entity |
| behavior | `tick(ctx)` | every `every` world seconds, while nobody embodies the entity |

A script is stored once with `define_script(id, source)` and referenced from schemas:

```python
define_schema("door", extends="thing", state={"open": False, "locked": False},
              actions={"open": {"script": "door_open", "doc": "Open it"}})
define_schema("person", extends="creature",
              actions={"go": {"script": "go", "doc": "Walk to a connected place", "targets": "place"}})
define_schema("arena", extends="place", space={"dims": 2, "bounds": [8, 8], "grid": True},
              listeners=[{"script": "turns", "kinds": ["before_act"]}])
define_schema("rat", extends="creature", behaviors=[{"script": "wander", "every": 5}])
define_schema("fighter", extends="creature", behaviors=[{"script": "thirst", "every": 60, "always": True}])
```

## Worlds are folders

A world is a folder under `worlds/`, named by its id. Everything about it that is code or text lives there, in plain files git can track; the database (`embody.db` at the workspace root) is the build of those files plus what happened in play.

```
worlds/<id>/
  build.py        WORLD = {"id", "name", "seed", "description", "requires"}; define(s), populate(s), upgrade(s)
  scripts/*.py    one script per file, the file stem is the script id
  changes.jsonl   live authoring, one op per line, replayed by a fresh build
  saves/*.json    save(name) writes here; commit the ones worth keeping
  notes/          playtest notes, the handoff to the next author round
  tests/          pytest finds them
packs/<name>/
  pack.py         PACK = {"name", "description"}; an optional define(s) for shared schemas
  scripts/*.py    verbs and rules a world takes with "requires": ["<name>"]
```

`load_world(id)` builds it: for each pack in `requires`, the pack's scripts and its `define`; then the world's scripts, its `define` (schemas), its `populate` (entities, rules, timers) and the replay of `changes.jsonl`. A world script with the same name as a pack script wins, and the pack's is never defined. `load_world(id, upgrade=true)` runs packs, scripts, `define` and `upgrade(s)` against the live world: new code, same state and history.

Scripts share code with `use("name")` on a line of its own: the file `scripts/_name.py` (or `name.py`) is pasted in its place when the world loads. Files that start with `_` are includes, never scripts of their own. `packs/d20/scripts/_common.py` carries the dice helpers its verbs share.

Live authoring lands in the folder too. `create_world(name, id=...)` makes `worlds/<id>/` with a build.py skeleton and starts a git repository there (unless the folder already sits inside one). `define_script` writes `scripts/<id>.py`; `define_schema`, `spawn`, `patch`, `connect`, `set_rule`, `schedule` and the other author ops append to `changes.jsonl` with the arguments as you gave them. Name things, then: `spawn("thing", "Pell's Mill", "Hat")` replays on a fresh build, an entity id would not. When the world settles, move what changes.jsonl holds into `populate` or `upgrade` and start the file over.

`save(name)` writes the whole world (entities, events, scripts, schemas, timers) to `saves/<name>.json`; `restore(path, id=...)` brings it back under its own id or a new one. A fork, or a game restored under a new id, has no folder of its own: it runs its source's code, so it saves into the source's folder as `saves/<id>-<time>.json`. Saves are the archive of a game; the database is only where the live ones run. Versions, forks and backups of the code are git's job: commit the folder, branch it, tag it. The engine's `fork_world` is for a fresh game on the same state, not for versions.

## Holder verbs and object verbs

An action with `targets` (a type name, or `"any"`) is the holder's own verb, done to something of that type: `go` targets a `place`, `take` a `thing`, `attack` a `creature`. An action without `targets` is done to the entity that carries it: `open` on a door, `read` on a sign. Perception pairs the first kind with every reachable entity of the right type and lists the second kind under the object. Other action keys: `doc`, `params` (documentation of expected params), `reach` (`near` default, `self`, or `any`), `self: true` (a `near` holder verb that may also target the actor, so it is listed against yourself too: `wake`, `check`), `range` (max distance in the container's space), `duration` (world seconds until `finish` runs; in turn-based play also the length of that turn), `scope` on holder verbs (`exits`: only connected places, `here`: only what lies in the actor's place, `held`: only what the actor holds, `sight`: what is here plus the creatures one way over that the actor can see, through a way it knows with no shut door on it (a bow; give it a `reach` other than `near` and let its check say what it can hit), `any`: the default), `listed: "ok"` (a holder verb listed only against targets its check passes, for a verb that fits few of the things in reach: `pour`), `hidden`, `dead_ok` (a body's own targetless verb its seat may still use once it is dead, where every other verb answers "you are dead", whose hint names these: burial's `let_bury`). Scope keeps impossible pairs out of a player's affordances; the near misses keep their reasons. A creature's own targetless verbs (`brace`, `check`, `sleep`) are things it does, so they are listed once with no target and never against another creature.

Verbs named by data: an action with `named_by: {"key": K, "catalogue": C, "doc": field, "topic": T, "guide": text, "by": {field: {value: action keys}}}` is no verb of its own. It answers instead to every name in the entity's own state `K` (a map of name to entry): each entry, laid over the same name in the world's catalogue (the root's state `C`, {name: entry}), is a verb under its name, so a body keeps only what is its own (`{"ice": {"dice": "1d6"}}`). The merged entry's fields pick overlays from `by` (a `harm` entry gets `strikes`, `scope: sight` and its own `script`, a `mend` one `self: true`), and its `doc` field (default `words`) is the verb's doc in perceive and inspect. The script reads the entry with `ctx.named_entry(ctx.actor, K, ctx.verb)`. An entry never takes a name the schema already gives a verb, a name is one short lowercase word, and such a verb is always its holder's own, never one done to the holder. `grant_verb(body, name, overrides)` and `take_verb(body, name)` give and take one by name (the owner's and authors', never a guest grant's); a name not in the catalogue is refused with the list. `guide(T)` reads the catalogue, each entry and how to give one, with `guide` as its first line. A world's rules give one from a script by writing `K` on the body. Keep `K` among the rules-only keys (a body's `gift_book` and `gift_uses` are), so no programmed verb, frame or guest code gives a body one.

Strikes: an action with `strikes: true` is a blow, a shot, anything that does harm, and the engine paces it. After one, the striker waits a cooldown before striking that target again, and half of it before striking anyone. The cooldown is the world meta's `strike_cooldown` in real seconds, `held` (default 60, an agent's time to read the fight and decide) when a player or a mind holds either side, `free` (default 15) when nobody holds either, times the action's `cooldown_x` (2 for a heavy blow, 0.5 for a light one), times the `cooldown_x` its apply returns in its result dict (the weapon it struck with: a maul's 2, a needle's 0.5), times the clock's rate. A paused clock (turn-based play) has none. Too soon, the act is refused with the wait in real seconds, and the affordance says the same, so an agent never retries blind. `cost: {key: n}` spends that much of the striker's own state per strike (water, charge) and refuses when there is not enough. The timers live in the striker's secret state `cooldowns`. A rule that strikes on its own (a guard's tick) asks `ctx.strike_wait(a, t)` (world seconds, 0 when ready) and calls `ctx.mark_strike(a, t, x)` after.

Verb cooldowns: an action with `cooldown: n` (world seconds) holds whoever used it off that verb for n, whatever it was done to (a bleat every 20 s, a graze every six hours). Too soon, the act is refused with "you can bleat again in about N s" (real seconds) and the affordance says the same. A paused clock has none. It lives beside the strikes in the actor's secret `cooldowns`, as `verb:<verb>`.

Beasts and seats: a body (or its schema's default) with `verbs_only: [verbs]` can use those and nothing else: its own act verbs, the verbs of things around it (take, give, drop, put, write...), `say` (a whisper or a shout passes when `whisper` or `shout` is listed, or `say`) and `step` (or `go`). Anything else is refused as "a goat cannot say: it can graze, ram, bleat" (the body's `species` if it has one, else its type). A body with `beast: true` (the beasts pack gives every beast that) hears no words: every spoken line (`say`, `talked`) it perceives, waits on, reads in history or recalls comes as `{to, tone, heard: false}`, tone one of whisper (reach 0), shout (reach past 1, all capitals, or a long line with "!"), sharp (three words or fewer ending in ? or !) or calm. `understands: true` on the body overrides that; `understands_until` (world time, a herb's while, written by a world rule) does too until it passes. Rules hear everything. `verbs_only`, `beast`, `understands` and `understands_until` are rules-only keys on a body, as `looks` is.

## The language

What works: `def`, `return`, `if/elif/else`, `for`, `while`, `break`, `continue`, assignments and augmented assignments, tuples, lists, dicts, sets, comprehensions and generator expressions (`any(x > 2 for x in xs)`, evaluated whole), f-strings, `and/or/not`, comparisons, arithmetic, slicing, calling other functions defined in the same script, top-level constants (literals only).

Builtins: `len min max abs int float str bool list dict tuple set sorted range round sum any all enumerate zip reversed isinstance`.

Methods: the usual ones on `str`, `list`, `dict`, `tuple`, `set` (`lower`, `split`, `join`, `append`, `get`, `items`...).

Not available: `import`, `class`, `try`, `with`, `lambda`, `yield`, `global`, nested `def`, `*args`, `**kwargs`, decorators, anything starting with `_`. Each call has a fuel budget (about 20k to 50k operations); a runaway loop is an error, not a hang. A verb that walks a long list may ask for more with `fuel` on its action (at most a million); its `check` gets the same, or its own `check_fuel` (a check alone has 5,000 otherwise). A check that runs out tells the agent the world's script is at fault, not its call.

## ctx

Every function receives `ctx`. Entities arrive as views: `view.id`, `view.type`, `view.name`, `view.parent` (a view or None), `view.pos`, `view.state` (read `state.hp`, write `state.hp = 3`; missing keys read as None), `view.children(type=None)`, `view.peers(type=None)`, `view.is_a(type)`, `view.has(relation, other)`, `view.linked(relation)`.

Identity:

- `ctx.actor` the entity doing the action (None in a tick)
- `ctx.target` the entity acted on (None when the verb has no target)
- `ctx.self` the entity that carries this script (the door, the room with the rule, the rat)
- `ctx.params` the dict passed to act
- `ctx.verb`, `ctx.t` (world time), `ctx.event` (in listeners)
- `ctx.rand` deterministic: `random()`, `randint(a, b)`, `choice(xs)`, `shuffle(xs)`, `roll("2d6+1")`, `chance(0.3)`

Queries (ids or views both work as arguments):

- `ctx.get(id)`, `ctx.find(type=None, under=None, parent=None, name=None, state=None, limit=50)`
- `ctx.children(x, type=None)`, `ctx.parent(x)`, `ctx.peers(x, type=None)`, `ctx.root()`
- `ctx.edges(x, relation=None, direction="both")` returns dicts `{id, source, target, relation, data}`
- `ctx.linked(x, relation, direction="out")` returns views; `ctx.relations(x, relation=None)` the n-ary ones
- `ctx.distance(a, b)` within one container's space, None when not comparable
- `ctx.embodied(x)` True while a mind or a player holds that body (a rule that drives workers or guards leaves those alone)
- `ctx.acted_at(x)` world time of the last deed by whoever holds that body, None when nobody does: an idle behavior on a held seat tells its own errand from where the player went
- `ctx.leak(text)` what in a line gives the table away (an entity id of this world, a tool call), named, or None: the filter `say` puts on players and minds, for a verb that keeps someone's words in the world (an inscription)
- `ctx.knows_way(who, place)` whether that body knows the way to a place: any place not `hidden`, a hidden one only when its `known_to` names the body or its faction
- `ctx.ways(a, b, most=8)` how many ways apart two bodies (or things, or places) stand: 0 in the same place, 1 next door, None past `most` or not joined. Every way counts, hidden or shut. A tether reads it
- `ctx.offer_seat(entity, to=body, why='')` offers whoever holds that body a seat: a mind grant for the entity (`seatable: true`, nobody in it), which they claim with `claim_seat` within their slots; the world never sees a token, and the same open offer is not made twice. `ctx.withdraw_seat(entity, why='')` closes its offers and ends a claimed seat (the beast went feral). Not from a script under a grant's limits (docs/HOSTING.md)
- `ctx.move_seat(to, from_=None, notes=True)` moves whoever holds `from_` (default: the acting body) into `to` at once: the same player or mind, now playing `to`, with no offer, no claim and no new token (a transfer rig, a possession). `to` must be `seatable`, alive and free, and the old body is left as it is for the rule to decide its fate. Their grant follows them, so they come back to `to` next session; their feed starts fresh at the move; `released` and `embodied` tell the log. notes=True carries the engine notes (`memory`) along, notes=False leaves them on the old body. Not from a script under a grant's limits
- `ctx.quiet(x)` world seconds since the seat holding that body last acted or spoke, or None when nobody holds it (a rule
  that waits on a player, such as a turn in a fight, can tell a slow player from one who has gone)
- `ctx.event_at(seq)` one event of the log by its number, as `event` is in a listener (kind, actor, target, payload...), or None; notes and intents stay their owners', and a builder's script reads only events done to its own plot. A record that names the deed it came from can be checked against it
- `ctx.may(who, what, thing)` may that body do `what` ("r", "w", "x" or a verb) to the thing, by its `access` (owner, group, mode: docs/ACCESS.md); a thing with no access lets everyone. `ctx.member(who, group)` reads the groups on the root (`access_groups`). `ctx.chmod(thing, mode, verb=None)` and `ctx.chown(thing, owner=None, group=None)` change it: a world's own script anywhere, a builder's inside its plot only, and never by writing `access` by hand. The engine checks a verb against the access of the thing it is done to: its own verbs need `x`, and a per-verb rule (`verbs`) covers any verb. A builder's script reads secret state (the `secret` list, memory, brief) only of things in its plot; elsewhere those keys read as None
- A thing may carry verbs of its own in its `programmed` state, put there by `program(thing, verb, source)`: by the owner, or by whoever holds a maker's frame (a thing whose state has `maker`) on the machines it names. They show and resolve like its schema's own verbs. One put on a body with `targets` (a type or "any"; the owner's and author's only) is that body's own verb done to others: `act(verb, target)` finds it on the actor, and `ctx.target` is whom it is done to. A frame's code runs held to the thing it sits on (`under: "self"`): it changes that thing, what it holds and the one who chose the verb, never a body riding it; it spawns nothing, sets no rules, and what it says reaches others marked untrusted (docs/ACCESS.md)
- `ctx.rename(x, name)` gives a thing a new name (a written leaf); refused when someone else has it, and the room hears `renamed`. A builder's script renames inside its plot only
- `ctx.locked(x)` what keeps a box, a door or a place shut (its own `locked` state, or an `attached` child whose state says `locked`, such as a locks-pack lock), else None. `ctx.shut(x)` is the refusal to give for it: "X is locked: unlock it first" and only the ways that lock has (its key, its code, a pick, a break), or None. The engine keeps everything in a locked holder out of reach of every verb; a thing whose state has `attached` is in reach wherever its parent is

Mutations (each one is logged as an event):

- `ctx.patch(x, {...})` or `view.state.key = value`. A dict value merges into the existing dict (add one dialog topic without resending the rest), `None` deletes the key; the op-level `patch(..., replace=True)` sets whole
- `ctx.spawn(type, parent, name="", state=None, pos=None)` returns the new view
- `ctx.move(x, parent, pos=None, at=None)`, `ctx.set_pos(x, pos)`, `ctx.destroy(x)`. `at` is its spot in the new place, [x, y(, z)] or a landmark's name there (a vehicle pulling up at its stop); a name that names nothing there refuses. Without it, it lands where the one who put it down stands, else at the end of the drawn route it came by
- `ctx.step(x, to=None, heading=None, max_m=25, face=True)`: a short move inside the place a body stands in (an animal's amble, a guard pacing a wall), toward `to=[x, y]` in the place's frame or a landmark's or a thing's name there, at most `max_m` metres, stopping short of the place's edge and of anything solid, as a player's `step` does. A body with no spot of its own there takes the nearest free one. It faces the way it walked (`face=False` keeps its heading); `heading=` sets it, and with no `to` it only turns. Everyone there gets a quiet `stepped {at, frame, heading?, from}` (`from`: the {at, heading} it left), and that is the step's only record: no `patched` beside it. Returns `{at, heading, clipped, blocked_by}`, each only when it applies
- `ctx.link(a, b, relation, data=None)`, `ctx.unlink(a, b, relation)`
- `ctx.relate(relation, [participants], data=None)`, `ctx.unrelate(id)`
- `ctx.set_rule(entity, script, kinds=None, fuel=None)`, `ctx.clear_rule(entity, script)`
- `ctx.remember(x, text)` a note in x's secret memory, as `remember` writes it: what they did or saw, for their mind
- `ctx.mark(body, where, what, kind='permanent', band='near', lasts=None)` marks a body's looks (a tattoo, a scar, paint, a swapped part): `what` on the region `where`, kind worn-on, permanent, replaced or grown, seen from a band (close, near, far); a worn-on mark is gone after `lasts` world days, and a grown one may grow through `stages=[{after_days, what, band}]` read from the clock (a beard). Emits `marked` and returns the mark's id. `ctx.unmark(body, id)` takes one off (`unmarked`); `ctx.regrow(body, id, stage=0)` cuts a grown mark back to a stage (`regrown`). Only the world's rules mark a body: not a guest's script, a frame or a programmed verb

Stacks: a thing whose state has a `count` is that many of itself (coins, 60 of them). Its card shows `count`, and so does every list that names it (a rack's `holding`). village `take`, `drop`, `give` and `put` take `params {"count": n}` to move part of one; without a count they move all of it.

- `ctx.count(x)` how many of a thing there are (its `count`, else 1); `ctx.count(holder, what)` how many units of things by that name or `kind` the holder has, stacks and loose ones together: `ctx.count(me, "ember")`
- `ctx.transfer(x, to, count=None)` move a thing, or `count` units of a stack, into `to`, where it joins a like stack. Returns what holds the moved units now: the thing, the new part, or the stack it joined. Use it instead of `move` for anything that may be a stack
- `ctx.split(x, n)` part `n` units off a stack where it lies and return the part; `ctx.merge(x)` fold a stack into a like one in the same holder and return the one that holds them. A stack joins another of the same type and name whose state is the same but for `count` and the hand-over marks (`given_by`, `given_before_by`: the arriving one's win). A thing with no `count`, an attached one or one that holds things never joins
- `ctx.bulk(x)` a thing's weight in the hands: its `bulk` a unit (fractions allowed, 0.1 for a shard), else 2 for anything with a `capacity`, else 1, times its count; `ctx.load(body)` the bulk of all it holds. village and d20 measure `carry` with these

Events and time:

- `ctx.emit(kind, target=None, reach=1, **payload)` a semantic event (`opened`, `hit`, `arrived`). reach 0 = the target only, 1 = its container hears it, -1 = all the way to the root
- `ctx.say(text, reach=1, to=None, low=False, loud=False)` speech from `ctx.self` (or the actor). `low=True` keeps the line in the place: the speaker, the one it is to, what the speaker holds and anyone within the world's `low_radius` (meta, metres, 3 by default; both by their own spots) hear the words, and everyone else there reads it as `{to, tone: "low", heard: false, low: true}`. Where the place's state or the world meta sets `voice_radius` (metres; unset, a line is heard across the whole place), a normal line is heard in full only that far from the speaker, by both spots, and those further off read it as `{to, tone, heard: false, too_far: true}`; the one it is to, what the speaker holds and bodies with no spot of their own always hear it. `loud=True` (or reach past 1) is a shout and carries `shout_radius` (the place's, else the meta's, else four times the voice). With `to` the `say` event targets the listener (`payload.to` names them) and the room still hears it. Without `to` the line is said into the room: the event targets the speaker's place, so everyone standing there hears it and a listener on the place sees it
- `ctx.witnesses(*who)` in a verb's apply: who sees this deed. The verb's `act` line reaches the doer and these, no one else in the room (a hand in the pot behind the cook's back); called again, it narrows. What the verb does still happens, and anything its script says or emits reaches whom those events reach
- `ctx.gesture(text, to=None, reach=1)` a deed in words, seen and not said ("The cat opens one eye, and closes it."): a `gestured` event {text, to} by the same body `ctx.say` speaks for, which the room sees. The village pack's person_on uses it: in a table line, text in double quotes is said and the rest is a gesture, in the order written
- `ctx.schedule(after, kind, target=None, payload=None, every=None)` an event later; listeners react to it
- `ctx.act(body, verb, target=None, params=None)` make a body nobody holds do one of its verbs, as if it chose to: a keeper on a weekly timer calls an oracle verb, a press records a pressing. Every check its own act meets holds (the verb's access, an oracle's rate and open calls, `before_act` rules, costs and cooldowns), and the `act` line carries `by` (this script) and `caused_by` (the event that ran it). Returns `{ok: True, verb, target, result}`, or `{ok: False, reason, hint}` when the world refuses, so the rule can fall back. A body a mind or a player holds acts for itself and is refused (`ctx.embodied` tells you first); a limited grant's script drives only bodies inside its reach; a frame's code and a verb on trial make no acts. An act made this way may start one more through a rule; one past that is refused
- `ctx.log(msg)` text returned with the act result

Control:

- `ctx.reject(reason, hint=None)` in a `check` or a `before_act` listener: refuse, with a reason the agent reads
- `ctx.stop()` in a listener: this event bubbles no further (a local rule overriding the world's)
- in `check`, returning a string also rejects with that string; returning False rejects plainly

## Events

Primitive events the engine emits for you: `spawned`, `patched`, `moved`, `left`, `destroyed` (target: the destroyed entity, emitted before it goes), `linked`, `unlinked`, `related`, `unrelated`, `embodied` (payload `principal`, `as`), `released`, `scheduled`, `unscheduled`, `finished`, `script_error`, `forked` (on the root of a copy). These exist for the log, viewers and minds: no listener or rule hears a primitive, so a rule that cares where someone went listens to what the verb emits (`arrived`, `given`), not to `moved`. Speech is `say` (payload `text`, optional `to`; the store also keeps `wall`, the real time it was said, which `minds()` reads and no player's feed shows). Sleep is the engine's too: a body whose state says `asleep` (a `slept` event puts it there, `woke` takes it off) keeps in its feed only what is done to it and what is loud: an event whose payload says `loud`, or one with reach 2 or more. A deed by someone else on a sleeper (an event that targets it, other than the `act` envelope) wakes it, and so does a loud event on the place it lies in or on a thing there; the engine patches `asleep` false and emits `woke` {by, why}. A quiet deed names someone else as its target (d20's `lifted` names the thief). `merged` (a stack folded into a like one: target the stack that kept the units, payload `from`, `count`, `total`) is a primitive too. `renamed` (payload `old`, `new`; the author op `rename`) is news, not a primitive: the room sees it and a listener may hear it. Silent ones that exist for the log and for minds, never for listeners: `remembered` (an entity wrote to its secret `memory`), `intended` (it changed its secret `goals`) and `opinion` (the opinion floor moved a `knows` edge: `given` +2, `hit` or `attacked` -3 on the receiver's standing toward the actor, `talked` and `say` only mark the meeting; the payload's `edges` lists each `{holder, of, delta, standing}` that moved; switch it off with world meta `opinion_floor: false`). `remembered` and `intended` are private: only the entity's own mind and authors ever see them in a feed, and a `patched` event on someone else never reaches a player or a mind at all (its result shows in the next perceive), and nor does the `spawned` of a hidden thing; authors and observers see them whole. Oracles' events (docs/ORACLES.md) are news a rule may hear: `oracle_called` {verb, args, caller, timeout} when a body uses a verb an oracle answers on a thing, `oracle_answer` {request, verb, to, ok, text, data, untrusted} when it answers, `oracle_lapsed` {request, verb, to} when no answer came in time; a private call's three reach only the caller's feed. `act_refused` is the hosts' alone: an act the world turned down (a check, reach, a lock, access, a target nobody can find), logged on the body with reach 0 and payload `verb`, `target`, `asked` (the target as typed), `params` (trimmed), `reason`, `hint`. No listener hears it, no other body and not the body's own feed sees it, the chronicle leaves it out; owners, authors and observers read it with `history(kinds=["act_refused"], touching=...)`. A retry of the same refusal is logged once, and at most `refused_per_hour` (world meta, default 20, 0 logs none) per body per world hour, the last marked `capped`. Semantic ones around actions: `before_act` (listeners may reject), `act` (it happened), then whatever the script emits. In a listener, `event.kind`, `event.actor`, `event.target`, `event.payload`, `event.path`, `event.seq`, `event.t`. The actor and target on an event are ids (compare with `ctx.self.id`, or `ctx.get(event.target)` for the view); `ctx.actor` and `ctx.target` are views.

Listeners run along the bubble path only: the target, then its ancestors as far as `reach` allows. A listener on a place sees everything that happens inside it (events with reach >= 1). A listener on the world root sees everything with reach -1, which includes every `before_act`: that is how world rules work. A sibling hears nothing. `kinds` on the listener filters which events wake it.

A carried thing is the one exception: a schema listener with `holder: true` also hears what its holder does and what is done to them, wherever that happens, that is every event whose actor, target, or payload `by`, `who`, `to` or `source` is the body (or box, or place) it is a child of. A ledger in a pocket hears its holder give, take and be paid. `before_act` reaches it only when its `kinds` name it, and a `stop()` up the tree does not silence it, since the thing is not above anyone.

Rules are different. A rule installed with `set_rule(entity, script, kinds)` hears every event that happens anywhere under its entity, whatever the event's `reach`: a rule on the root is the table's rule and sees every `hit`, `agreed` or `harvested` emitted with reach 0 or 1 deep in the world. Schema listeners stay scoped by reach (a place hears what happens inside it, a sibling nothing); rules do not need the author to widen every emit. So a storyline, a referee or a watcher goes on the root with `set_rule`; a greeting or a trap stays a schema listener.

## Programming a live world

Read this before you put verbs on things in a running world with `program`: with the owner's hand, or with a maker's
frame in yours. Over the door, guide('scripting') carries the frame's own rules after this file.

- A verb arrives with `program(thing, verb, source, doc, params)`. Look before you add: `programs(thing)` lists what a
  thing has, and `find` by name first keeps a second copy of a thing from appearing. After `program`, `inspect` the
  thing and see the verb under `programmed`; `unprogram` takes one off.
- `use("name")` is pasted only when a world loads from its folder. A source sent live with `program` gets no paste:
  write into it every helper it calls.
- A view's fields are read-only: `view.parent`, `view.id`, `view.name`, `view.type`, `view.pos`. `view.state.key = v`
  writes state; to move a thing use `ctx.move` or `ctx.transfer` (stack-safe), to rename it `ctx.rename`, to place it
  `ctx.set_pos` or `ctx.step`.
- A frame's code reaches its machine, what the machine holds, and the one who chose the verb. It may move things to
  and from that caller and give them things, but it writes the caller's own state only on the keys the frame's
  `maker.actor_keys` names (none by default), and never a body's make: stats, skills, sheet, hp, water, carry, faction,
  memory, or any key the body's schema gives it. One exception reaches past the machine: a thing the world marks
  `stone: true`, lying loose where the machine stands, portable, nobody's but the caller's, within its `cargo`.
- A frame's caps: it makes at most 12 verbs, held or live (`unprogram` one to add another), 6000 characters a source, 20
  programs an hour. With review on, every new verb waits for the owner's `review`, and so does a rewrite of a live
  one: it goes back to pending. `programs` shows which are pending. With `review: "writes"` a pending verb still waits for the review, but until then it runs on a look-only trial: it reads and answers the one who used it (its return and `ctx.log`), its machine's secret keys stay sealed (what the review guards, a codex, is not read before the owner says yes), and any write ends the run with "may only look" and rolls the act back. perceive lists such a verb with `trial`, and the act's result says `trial: true`. A frame's code makes events in its own namespace
  only (`<prefix><kind>`, the prefix its frame names), and what it says reaches others as `untrusted`.
- Only the world's rules write a sheet, skills, xp, hp or carry. A verb that needs one changed emits a request in its
  own namespace, and a world rule that hears it decides and writes.
- A check. A world script or an owner's verb that rolls emits `checked` {by, place, skill, roll, mod, total, dc,
  success, margin}, the shape d20's `check` emits, so world rules that wait on a check (a find, a story beat) hear it
  as one. The world sets the dc, never the caller. A `checked` event teaches nothing: growth comes only from the
  world's rules (d20's `learn`, in its common). A frame's code cannot emit `checked` at all.
- Once a day each: keep the count on the thing, keyed by the actor's id and the world day, `int(ctx.t //
  ctx.day_seconds())`: `ctx.patch(ctx.self, {"heard": {ctx.actor.id: day}})` and refuse when it already says today.
  No timer needed.
- Explain first, act on confirm: called bare, a verb with a cost logs what it does and what it costs; called with
  `{"confirm": true}`, it acts.
- Names and refusals are the interface. Name a verb the way a player would say it, and let a refusal name the verb or
  the place that would work ("you must be at the stone to listen there").
- A description promises verbs. Every action a description offers a player (cups dipped full, a lamp to light, a
  carving to read) is a verb that does it, or a refusal in the world's words, or out of the description. Count what
  the fiction counts: a check for a lamp looks at every lamp there, not only the actor's.

## Patterns

A rule that forbids a verb in one place:

```python
def on(ctx, event):
    if event.payload["verb"] == "attack":
        ctx.reject("violence is forbidden in the temple", "take it outside")
```

A door between two rooms: spawn the door in one room and connect the rooms `via` it. The door is reachable from both sides; `go` checks `state.open` of the `via` entity.

A monster that acts on its own until a player embodies it: a behavior with `tick`. The engine skips ticks while the entity is embodied. A behavior with `"always": True` is the body, not the mind (thirst, bleeding, a wound that worsens): it ticks on an embodied seat too.

Ambient facts: put a dict `ambient` on the world root (`time_of_day`, `weather`, `light`, whatever the world cares about) and, where a place differs, an `ambient` dict on the place. Every perceive carries the two merged, the place's keys on top. A rule on the root listening for your own `fog`, `nightfall`, `dawn` timers patches them and emits `scene` events at the places; `examples/ferry-at-dusk/scripts/weather.py` is one. Timers are listed by the `timers` op and cancelled with `unschedule`.

A world file that grows: besides `define(s)` and `populate(s)`, give it an `upgrade(s)` that adds what an older build lacks (a new place, a prop in someone's pocket, a timer, the ambient dict) and checks before each step, so running it twice changes nothing. `load_world(id, upgrade=true)` runs `define` and then `upgrade` against the live world. `set_rule` is already a no-op when the same rule is installed. A rule that walks the whole world on one event (a day pass over every beast and place) may run out of its 20,000 operations as the world grows: give it `fuel=` at install (up to a million), and keep the walk short (find what changed, not everything).

A table as the floor and a mind on top: the listener that answers `talked` from a dialog table carries `unless_embodied: true`. While an agent embodies the person the table is silent and the agent hears the `talked` and the addressed `say`; when it leaves, the table answers again. State an author writes for the mind goes in `brief`; the mind's own notes go in `memory` through `remember`, its goals in `goals` through `intend`. All three are always secret.

Whole-word dialog: split the topic into words and match each `|`-separated alias of a key against them, so `ale` matches "an ale, please" and not "a tale". Entries may be dicts: `{"line": ..., "after_gift": ..., "if_state": {"friend": None}, "else": ...}`. `packs/village/scripts/person_on.py` is the script.

A turn-based pocket: a place whose `before_act` listener rejects anyone but `state.order[state.turn]`, and whose `act` listener advances `state.turn`. Outside that place the world keeps running.

A hidden place (`hidden: true`) is a secret way: perceive lists the exit to it, and a verb on it, only to a body its `known_to` names, by id or by `faction` (a string, or a list of ids and factions); `go` in the d20 and village packs refuses the rest. Add someone to `known_to` when they are shown the way.

A hidden body shown to some (`hidden: true` with a `shown_to` list of ids) is seen only by itself and by those ids: a familiar at one person's side. It is in their perceive, wait and watch `present`, and nobody else's. Every event it is in (it acts, it is acted on, it moves or speaks, or it is a `left` event's `entity`) carries `seen_by`, fixed when it happens: the body, the ids it was shown to then, and whoever did it. Nobody else's feed, wait, watch or history has it, no listener on another body hears it (a place's, a thing's and the world's rules do), and someone shown it later does not read what came before. Its unaddressed `say` reaches only those it is shown to, and a line `to=` someone else is refused ("can't hear you"). It stays hidden for everything else: nobody can target it, strike it or hand it things, the ones it is shown to included. A `reveal` verb is the world's: a script that adds to `shown_to` (and `withdraw`, one that takes away). The owner, authors and observers see it whole. A hidden thing with no `shown_to` is as before: unseen, and its deeds are not veiled.

A body with no hands (`hands: false`, in its state or its schema's defaults) does only its own verbs, the ones its schema carries: a thing's verbs (open, read, harvest, feed) are refused with "you have no hands in this world". Give it a schema with only the verbs it should have. A tether is content: the body's `go` refuses a way that takes it more than `tether_ways` from its `tethered_to` (`ctx.ways`), and a behavior pulls it back when the one it is tied to walks off.

A storyline: a hidden entity (`state.hidden = True`) holds `state.stage`; its script is installed on the root with `set_rule(root, "story", kinds=[...])` so it hears every event, and finds its entity with `ctx.find(type="story")`. Each stage waits for its trigger event, applies effects (spawn, patch, move, emit a `scene` event at a place, schedule) and advances the stage. `examples/ferry-at-dusk/scripts/story.py` is a full example.

Rules as actions, the TTRPG way: every rule of the game is a verb with a `check` and an `apply`, and the dice are `ctx.rand.roll("1d20")`, so the same seed replays the same fight. `packs/d20` is a reusable rule set: `check(skill, dc)` emits `checked` with roll, mod, total, dc and margin; `attack` rolls against a defence and emits `hit`, `missed` or `warded`, with hp, wounds, down and dead as state (one bar, `hp` and `max_hp`, the core creature's own; a world made with `vigor` has it renamed by `install_rules`); a body left down by thirst dies after its days (`thirst_death_days`); `yield`, `kill`, `brace`, `threaten`, `parley`, `challenge` (a duel hyperedge that a root rule turns into a ring nobody else may strike into), `drink`, `fill`, `search`, `harvest`, `tend` (bare hands get the down up; `medicine` in hand heals a dose); a `thirst` and a `mend` (rest) behavior on every combatant; a `fighter_tick` behavior that fights without a mind; factions as entities with `hostile` maps and `standing` edges. `install_rules(s, root)` from `packs/d20/pack.py` puts the root rules in place; `worlds/glass-reach/` builds a world on it with `"requires": ["d20", "village"]`. The narrator never decides what a 16 means: the event says it. Bodies look after themselves: `thirst` does not bite beside a `water_source`, and a `quench` behavior drinks from a held skin or a source in reach when water falls to 3, on bodies nobody embodies (an embodied seat decides for itself). The ring ends three more ways than a blow: a duelist who walks out (`arrived` elsewhere) loses by `left` and drops 2 standing with their own side, and terms `agreed` between the two are a yield. A trade (the thing is gone by the next tick) and a return (`given_before_by` is the receiver) are not gifts. A loud footfall on the sand settles: after 120 quiet seconds `tremor` falls by one, with a `tremor` event whose `why` is `quiet`. The `village` pack adds `show` (they read what you hold, you keep it), `follow` and `stay`, and `watch` (who and what is in the next place, for your eyes only, as a `watched` event at reach 0). A whisper is not a verb: `say(text, to=X, reach=0)` reaches only X and the speaker.

Vehicles, the `vehicles` pack: a `vehicle` is a place that stands inside another place, so the people there see it as a thing and act on it, and its riders and cargo are its children and go where it goes. `board` and `alight` are the way in and out, never an exit. `drive` (on it, or on a `wheel` inside it) sets it out along its road one leg at a time: halfway through each leg it moves into the next place (`passing`), at the last it pulls in (`pulled_in`). While it rolls, anyone where it is may board it, `halt` it or strike it, those aboard may alight into the road, and a thing with `blocks_road` stops it. A `timetable` and a `driver` with no mind run it on their own; a fallen driver halts the run. A world steers it through its state (`dispatch`, `hold`) and wraps its verbs with `before_act` rules. packs/vehicles/pack.py lists every key, verb and event.

Ledgers, the `ledgers` pack: a `ledger` device (a world's own look extends it) holds named ledgers that only its holder reads. `record` writes by hand, `void` corrects without erasing, `read` and `search` page through it with any mix of filters and sorts, `total` sums a filter grouped by item or party with the spread of the amounts, `verify` checks entries against the log, `copy` writes them onto paper, `transfer` and `send` copy them to another device. With `records` it writes down its holder's deeds by itself (a `holder` listener). The entries live on hidden pages in an archive, so no card, feed or chronicle shows them; the room hears one line the world sets. packs/ledgers/README.md is the guide, packs/ledgers/pack.py the reference.

A lazily built place: `state.fidelity = "sketch"`. A listener on the root emits `approach_sketch` when someone enters it; an author agent waiting on that event fills it in.
