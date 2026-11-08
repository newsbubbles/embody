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
```

## Holder verbs and object verbs

An action with `targets` (a type name, or `"any"`) is the holder's own verb, done to something of that type: `go` targets a `place`, `take` a `thing`, `attack` a `creature`. An action without `targets` is done to the entity that carries it: `open` on a door, `read` on a sign. Perception pairs the first kind with every reachable entity of the right type and lists the second kind under the object. Other action keys: `doc`, `params` (documentation of expected params), `reach` (`near` default, `self`, or `any`), `self: true` (a `near` holder verb that may also target the actor, so it is listed against yourself too: `wake`, `check`), `range` (max distance in the container's space), `duration` (world seconds until `finish` runs; in turn-based play also the length of that turn), `scope` on holder verbs (`exits`: only connected places, `here`: only what lies in the actor's place, `held`: only what the actor holds, `any`: the default), `hidden`. Scope keeps impossible pairs out of a player's affordances; the near misses keep their reasons.

## The language

What works: `def`, `return`, `if/elif/else`, `for`, `while`, `break`, `continue`, assignments and augmented assignments, tuples, lists, dicts, sets, comprehensions, f-strings, `and/or/not`, comparisons, arithmetic, slicing, calling other functions defined in the same script, top-level constants (literals only).

Builtins: `len min max abs int float str bool list dict tuple set sorted range round sum any all enumerate zip reversed isinstance`.

Methods: the usual ones on `str`, `list`, `dict`, `tuple`, `set` (`lower`, `split`, `join`, `append`, `get`, `items`...).

Not available: `import`, `class`, `try`, `with`, `lambda`, `yield`, `global`, nested `def`, `*args`, `**kwargs`, decorators, anything starting with `_`. Each call has a fuel budget (about 20k to 50k operations); a runaway loop is an error, not a hang.

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

Mutations (each one is logged as an event):

- `ctx.patch(x, {...})` or `view.state.key = value`. A dict value merges into the existing dict (add one dialog topic without resending the rest), `None` deletes the key; the op-level `patch(..., replace=True)` sets whole
- `ctx.spawn(type, parent, name="", state=None, pos=None)` returns the new view
- `ctx.move(x, parent, pos=None)`, `ctx.set_pos(x, pos)`, `ctx.destroy(x)`
- `ctx.link(a, b, relation, data=None)`, `ctx.unlink(a, b, relation)`
- `ctx.relate(relation, [participants], data=None)`, `ctx.unrelate(id)`
- `ctx.set_rule(entity, script, kinds=None)`, `ctx.clear_rule(entity, script)`

Events and time:

- `ctx.emit(kind, target=None, reach=1, **payload)` a semantic event (`opened`, `hit`, `arrived`). reach 0 = the target only, 1 = its container hears it, -1 = all the way to the root
- `ctx.say(text, reach=1, to=None)` speech from `ctx.self` (or the actor). With `to` the `say` event targets the listener (`payload.to` names them) and the room still hears it. Without `to` the line is said into the room: the event targets the speaker's place, so everyone standing there hears it and a listener on the place sees it
- `ctx.schedule(after, kind, target=None, payload=None, every=None)` an event later; listeners react to it
- `ctx.log(msg)` text returned with the act result

Control:

- `ctx.reject(reason, hint=None)` in a `check` or a `before_act` listener: refuse, with a reason the agent reads
- `ctx.stop()` in a listener: this event bubbles no further (a local rule overriding the world's)
- in `check`, returning a string also rejects with that string; returning False rejects plainly

## Events

Primitive events the engine emits for you: `spawned`, `patched`, `moved`, `left`, `destroyed` (target: the destroyed entity, emitted before it goes), `linked`, `unlinked`, `related`, `unrelated`, `embodied` (payload `principal`, `as`), `released`, `scheduled`, `unscheduled`, `finished`, `script_error`, `forked` (on the root of a copy). Speech is `say` (payload `text`, optional `to`). Silent ones that exist for the log and for minds, never for listeners: `remembered` (an entity wrote to its secret `memory`), `intended` (it changed its secret `goals`) and `opinion` (the opinion floor moved a `knows` edge: `given` +2, `hit` or `attacked` -3 on the receiver's standing toward the actor, `talked` and `say` only mark the meeting; the payload's `edges` lists each `{holder, of, delta, standing}` that moved; switch it off with world meta `opinion_floor: false`). `remembered` and `intended` are private: only the entity's own mind and authors ever see them in a feed, and a `patched` event on someone else arrives with its secret keys stripped (or not at all when nothing public changed). Semantic ones around actions: `before_act` (listeners may reject), `act` (it happened), then whatever the script emits. In a listener, `event.kind`, `event.actor`, `event.target`, `event.payload`, `event.path`, `event.seq`, `event.t`. The actor and target on an event are ids (compare with `ctx.self.id`, or `ctx.get(event.target)` for the view); `ctx.actor` and `ctx.target` are views.

Listeners run along the bubble path only: the target, then its ancestors as far as `reach` allows. A listener on a place sees everything that happens inside it (events with reach >= 1). A listener on the world root sees everything with reach -1, which includes every `before_act`: that is how world rules work. A sibling hears nothing, so a watcher that must see the whole world is attached to the root with `set_rule`. `kinds` on the listener filters which events wake it.

## Patterns

A rule that forbids a verb in one place:

```python
def on(ctx, event):
    if event.payload["verb"] == "attack":
        ctx.reject("violence is forbidden in the temple", "take it outside")
```

A door between two rooms: spawn the door in one room and connect the rooms `via` it. The door is reachable from both sides; `go` checks `state.open` of the `via` entity.

A monster that acts on its own until a player embodies it: a behavior with `tick`. The engine skips ticks while the entity is embodied.

Ambient facts: put a dict `ambient` on the world root (`time_of_day`, `weather`, `light`, whatever the world cares about) and, where a place differs, an `ambient` dict on the place. Every perceive carries the two merged, the place's keys on top. A rule on the root listening for your own `fog`, `nightfall`, `dawn` timers patches them and emits `scene` events at the places; `worlds/ferry_at_dusk.py` has one. Timers are listed by the `timers` op and cancelled with `unschedule`.

A world file that grows: besides `define(s)` and `populate(s)`, give it an `upgrade(s)` that adds what an older build lacks (a new place, a prop in someone's pocket, a timer, the ambient dict) and checks before each step, so running it twice changes nothing. `load_world(file, upgrade=true)` runs `define` and then `upgrade` against the live world. `set_rule` is already a no-op when the same rule is installed.

A table as the floor and a mind on top: the listener that answers `talked` from a dialog table carries `unless_embodied: true`. While an agent embodies the person the table is silent and the agent hears the `talked` and the addressed `say`; when it leaves, the table answers again. State an author writes for the mind goes in `brief`; the mind's own notes go in `memory` through `remember`, its goals in `goals` through `intend`. All three are always secret.

Whole-word dialog: split the topic into words and match each `|`-separated alias of a key against them, so `ale` matches "an ale, please" and not "a tale". Entries may be dicts: `{"line": ..., "after_gift": ..., "if_state": {"friend": None}, "else": ...}`. `worlds/ferry_at_dusk.py` has the script (`PERSON_ON`).

A turn-based pocket: a place whose `before_act` listener rejects anyone but `state.order[state.turn]`, and whose `act` listener advances `state.turn`. Outside that place the world keeps running.

A storyline: a hidden entity (`state.hidden = True`) holds `state.stage`; its script is installed on the root with `set_rule(root, "story", kinds=[...])` so it hears every event, and finds its entity with `ctx.find(type="story")`. Each stage waits for its trigger event, applies effects (spawn, patch, move, emit a `scene` event at a place, schedule) and advances the stage. `worlds/ferry_at_dusk.py` is a full example.

A lazily built place: `state.fidelity = "sketch"`. A listener on the root emits `approach_sketch` when someone enters it; an author agent waiting on that event fills it in.
