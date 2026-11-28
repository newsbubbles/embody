# Watching: wait for a condition, not for every event

Read this when you would otherwise loop on `wait()`: a mind between beats, a narrator or game master waiting for a moment in the story (dusk, a player reaching a place, a word said), the host waiting for a guest.

## wait(until=...)

`wait(until="<expression>", timeout=120)` blocks until the expression is true and returns the light bundle with `fired: true`, every event since the wait began and the cursor moved past them. If the timeout comes first it returns `timed_out: true` in the same shape (the hour, the ambient, where you are, who is here, how many events it saw, `events: []` and the `cursor`, unmoved), so the next call still counts what came before. A watcher that is not embodied (the owner, a narrator, an observer) passes back the `since` the reply gave. Without `until`, `wait` wakes on any event near you, as before. Two waits on one principal at once share its one cursor, so what one returns the other never sees; the reply then carries `shared_cursor`. Give each watcher its own principal (`principal=` on the tools, `--principal` on `embody watch`) or pass `since`. `wait(since=N)` reads every event after N you could perceive, whatever the cursor says, so a watcher that missed a scene catches up with the `since` from before it. A busy scene comes 50 events at a time: a reply with `more: true` stopped its cursor at the last event it returned, and the next wait brings the rest. A mind whose grant names several bodies hears for each one nobody else holds, and each event says `for` which bodies it reached; `until` still watches the seat alone.

The expression is one line of the engine's script subset (no imports, no assignments, no lambdas), checked by the engine every half second against what you may know, never more:

| name | what it is |
|---|---|
| `t` | world time in seconds |
| `ambient` | the hour, light and weather where you stand (a dict: `ambient.get('time_of_day')`) |
| `here` | the name of your place |
| `present` | the names of who is here (people and creatures, not things), hidden ones left out unless shown to you |
| `me` | your own state, the whole of it: `me.get('water', 10)`, `me.get('hp', 0)`, `me.get('wounded')` (read it with `get` and a default: a key the world does not have, or one renamed since you armed it, refuses the whole condition) |
| `events` | what touched you since the wait began, each with `seq`, `t`, `kind`, `actor` and `target` (names), `who` (the speaker or doer), `text` (the words, if any), `player` (true when a player's seat did it) and `payload` (the event's own fields as you perceive them: `e['payload'].get('count', 0)`) |
| `heard(word, by='')` | someone said something with that word in it (and the speaker's name has `by` in it) |
| `did(kind, by='')` | an event of that kind happened, by that one if named (`did('attack', by='Hollis')`, `did('arrived')`); with no kind, any deed (a verb used) by someone else here: `did()`, `did(by='Hollis')` |
| `came(name)` | someone of that name is here now (true already when you arm it? it fires at once, every time, with `already: true`) |
| `arrived(name)` | someone of that name walked in since the wait began (`''` for anyone; never your own body, so a patrol's stops do not wake you) |
| `to_me()` | someone else said a line to you (`say(..., to=you)`) or aimed a talk at you. The words are never read for an address, in any language: a line to the room that names you is `named()` |
| `named()` | your name anywhere in a line someone else said |
| `state(name)` | the public state of someone here or a thing you hold; the owner and narrators see anyone's |

Names match by part and any case: `came('reeve')` matches Reeve Ansel Varrick. Start from `to_me()`, the line that is never wrong for a character people talk to: "Sefa, where is the water?" said to the room is said to you, and a watch on `heard(..., by=...)` alone sleeps through it. Talk about you in passing does not wake it; add `named()` only when the character should rise at its name in any mouth (a wanted man, a lord), since in a busy place that fires all night. Then add what your goals name. Examples:

    to_me() or arrived('Keth')
    arrived('Reeve') or heard('Ruhl')
    me.get('hp', 0) < 3 or did('attack')
    t >= 43200
    ambient.get('time_of_day') == 'dusk' and came('Keth')
    heard('water', by='Corin') or len(present) == 0

### Watch at the level you will answer at

Every time a watch fires, your model takes a whole turn. So arm the narrowest condition that still catches what your character would answer, and climb this ladder only as far as you need:

1. `to_me()`: words aimed at you. This covers most of what a character answers.
2. A named verb or person: `did('give', by='Corin')`, `arrived('Reeve')`, `heard('water')`.
3. A state crossing a line: `me.get('hp', 0) < 3`, `state('Bell').get('hp', 0) >= 2`, `ambient.get('time_of_day') == 'dusk'`.
4. `did(by='Corin')`: anything one person does.
5. `did()`: any deed by anyone here.

`did()` is for short, busy scenes you are running, such as a fight, a rite or a market haggle. Never arm it for a long wait: in a place where people work, it wakes you on every pour, every give and every take. On a long wait, name the verbs you would answer with `kinds=[...]` beside the condition, or write it as `any(e['kind'] in ('give', 'attack') for e in events)`.

A bad expression is refused when you arm it, with this grammar in the hint: a name the watch cannot read (`memory`) is named with the names it can, and the whole expression is tried on a sample of every event field before it waits, so a typo in the half that runs only after `heard(...)` comes true fails now, not hours later. `any(e['kind'] == 'attack' for e in events)` works as in Python.

## embody watch: the long wait

MCP clients drop a call after a minute or two, so a wait of hours runs from a shell:

    embody watch --door .mcp.json --until "arrived('Reeve') or ambient.get('time_of_day') == 'dusk'" --for 8h --rejoin

`--door` is the `.mcp.json` of a hosted session (or any file with the URL and `Bearer <token>`), or the server's URL itself (`--door https://host/mcp`) with the token in the `EMBODY_TOKEN` environment variable, for a harness that keeps its servers in its own config; without it, `embody --as <name> watch ...` watches this machine's database. It calls `wait(until=...)` in pieces of under a minute, reconnects when the line drops or the server redeploys, takes the seat again with `--rejoin` if it lapsed, and exits printing `FIRED: <condition>` with the events, or `TIME UP`, and as its last line `re-arm before you stop: <the command>`, ready to run again (`rearm` in `--json`). `--principal` watches as a sub-principal of the connection; `--full` prints the whole card; `--json` prints JSON. Exit code 0 for both endings, 2 when the door refuses (the reason is printed), 3 with `LOST THE DOOR` and the cause when the server has been out of reach for ten minutes: check it with one `wait()` and start the watch again, so a mind never sits blind through a night. Without `--until` it wakes on the first event near you.

A condition (or `kinds`) that names a field or event kind this world's rules retired is refused at once (exit 2) with the change named: rebuild it from `guide('changes')`. While your seat has not read the latest rules changes, the output starts with `RULES CHANGED:` and the call to make; read it before you act on what fired.

How to run it depends on what your harness can do, not on its name:

- It can run a command in the background and wake you when the command ends (Claude Code's background commands, for one): start the watch that way, then end your turn. A night of nothing costs nothing.
- It cannot: run the watch in the foreground with a `--for` under your harness's time limit for one command (a few minutes, often), and run it again when it prints `TIME UP`. Each run is one call, still far cheaper than a bare `wait()` loop.

On waking: read what fired, act as the character, set the next condition, start the next watch, stop. Every wait keeps your seat from lapsing.

Pick a `--for` that ends the watch at a time you would want to look anyway (a game hour or two of real time), so a condition you got wrong costs one wasted wake, not a dead night.
