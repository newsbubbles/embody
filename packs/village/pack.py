"""Village verbs: go, take, drop, put, give, show, talk, leave_word, read, burn, follow, stay, watch, and person_on, the listener that
answers from a person's dialog table while nobody embodies them. Extracted from the Ferry at Dusk, used by the
Glass Reach too.

A world names it in its manifest (`"requires": ["village"]`) and the loader defines these scripts before the world's
own, so a world may replace any of them with a file of the same name in its scripts/ (the Glass Reach has its own
`go` for deep sand). The pack defines no schemas: a world's `person` schema binds the verbs it wants.

- go: to a connected place; via a door-like entity when the connection has one. A shut door, a locked door and a locked
  place refuse, and say what opens them (`ctx.locked`: the locks pack, or a door's own `locked`).
- take, drop: portable things here or held; give: something you hold to someone here (`gives` tables can answer).
- stacks: a thing whose state has a `count` is that many of itself (Emberglass x60). take, drop, give and put take
  `params {"count": n}` and move that many, the rest staying where it was; with no count they move the whole stack.
  What arrives joins a like stack already there (same type, name and state but for count), so sixty shards given one
  at a time make one stack of sixty. Events carry `count`; cards show it. burn takes a stack whole.
- carrying: a body whose state has `carry` holds at most that much bulk; take, give (to it) and harvest refuse past
  it, and d20's search takes only what fits (part of a stack, if that is what fits). A thing's bulk is its `bulk` a
  unit, fractions allowed (0.1 a shard: sixty weigh 6), else 2 for anything with a `capacity` (a skin), else 1, times
  its count. No `carry`, no limit.
- put: `params {"item": thing you hold, "count": n}` onto or into a holder here: a thing whose `state.holds` lists what it takes
  (["any"], or state flags such as ["weapon"]) and, optionally, `room` (how many). What lies on a holder is
  within reach of everyone in its place, and `take` takes it back down. A locked holder refuses `put`, and nothing in it is
  in reach until it is unlocked; an attached lock does not count against `room`, nor does a stack that joins one there.
- show: something you hold to someone here; they get a `shown` event with its `text` (or description), it stays yours.
- talk: `params {"about": topic}`; the person answers from `dialog` through person_on, or with `default_line`.
- leave_word: `params {"for": who, "word": message}` with someone here, for someone who is not: the keeper stores it
  in its secret `word_left` (listener `leave_word`, fn `keep`, on `word_left`, always) and whispers it once to the one
  it is for when they next talk to it (listener `leave_word` on `talked`, unless embodied). `for` is a name, a kind of
  person ("the new guard" matches the template, type or faction) or "anyone"; someone else asking after the sender
  hears that word was left, not what it says. The sender never gets its own word back. Twenty words kept per person.
- read: the `text` of a thing you hold or that is here.
- burn: a thing whose state is `burnable`, held or here, at a fire: the place or something here with `fire` or `lit`
  in its state, or a lit light in hand. It is destroyed, what it held drops where you stand, and the room sees a
  `burned` event and a scene (that it burned, never what it said). Memories and past `read` events are untouched:
  whoever read it keeps it. Bind it with a duration of a few seconds.
- follow: someone here; when they `go`, you go with them (`state.follows`). stay: stop following.
- watch: a connected place, without stepping into it: who and what is there now, for your eyes only.
- a whisper is not a verb: `say(text, to=someone, reach=0)` reaches that one person and nobody else in the room.
"""

PACK = {"name": "village", "description": "go, take, drop, put, give, show, talk, leave_word, read, burn, follow, stay, watch and the dialog-table listener person_on."}
