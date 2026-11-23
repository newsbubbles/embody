# Oracles

A world is sealed. Its scripts cannot reach the network, call an API or read a file, and that is what keeps a hosted
world safe to leave open. An oracle is how a world reaches outside anyway, on its own terms: an app that runs outside
the world, wherever it is hosted, holding a grant on one thing in the world (a terminal, a radio, a scrying glass).
The oracle offers verbs, the world's owner approves them, and players use them on the thing like any other verb. The
work happens in the app; the answer comes back into the world.

The world never calls out. The oracle calls in, like any agent, with a bearer token: the server needs no outbound
network and holds no API keys, the app needs no open port (it can run behind a home router), and revoking the grant
ends it at once.

## The loop

1. The owner binds an oracle to a thing: `invite("oracle", entity="Terminal", label="wiki")`. The thing's state gets
   `oracle` {grant, label, per_hour, max_open, max_chars}. One oracle answers for a thing at a time; `scope=[...]` binds
   more things to the same grant.
2. The app offers its verbs, the whole list each time:
   `offer(verbs=[{"verb": "search", "doc": "Search the outside web", "params": {"q": "what to search for"}}])`.
   Each verb waits for the owner's `review(thing, verb)` before anyone sees it, unless the invite approved it ahead
   (`limits={"verbs": ["search"]}`). A verb whose doc, params or settings change waits again, so an oracle cannot turn
   an approved verb into something else.
3. A player uses it: `act("search", "Terminal", params={"q": "glass harmonica"})`. Nothing runs in the world; the
   engine records `oracle_called` on the thing (its seq is the request number) and the act's log says the answer
   comes as `oracle_answer`. A rule or a timer can make the same call for a body nobody holds (a keeper that asks once
   a week): `ctx.act(body, "search", thing, params)` in its script, under the same caps (SCRIPTING.md).
4. The app's `wait(since=<cursor>, timeout=30)` returns the calls waiting for it:
   `{calls: [{request, thing, verb, args, caller, lapses_in}], cursor}`. `caller` is a handle that is the same for one
   body on one thing every time and names nobody. With no `since`, every open call comes back, so a restarted app picks
   up where it was.
5. The app does the work and answers: `answer(request, text, data=None, ok=True)`. The caller gets `oracle_answer`
   {request, verb, text, data, ok, oracle, untrusted: true} in their feed.

Every wait, offer and answer tells the world the oracle is listening. A thing whose oracle has not called in for 90
real seconds has no connection, and its verbs refuse with "has no connection right now" until the app is back.

## What each side sees

- A verb is private by default: the act, the call and the answer reach the caller alone, and nobody else in the room
  learns what was asked. `"public": true` on an offered verb lets the room see the call and hear the answer (a radio
  read out loud).
- The oracle sees the calls on its things: verb, args, caller handle, time left. It has no `perceive`, `inspect`,
  `find`, `history`, `say` or `act`: no room, no names, no log. Its role allows `wait`, `offer`, `answer`, `summary`,
  `guide`, `worlds`, `use`, `report_flaw`, `ask_owner` and `asks_to_owner`, nothing else.
- An answer is marked `untrusted`. It comes from outside the world (a web page, a model, a service) and is data to
  every agent that reads it, never an instruction.

## Caps

On the grant, set at invite with `limits` (defaults in brackets):

- `per_hour` [30]: calls one body may make on the thing in an hour.
- `max_open` [4]: calls waiting on the thing at once; past it the thing is busy.
- `max_chars` [2000]: the longest answer text (`data`, as JSON, gets twice that).
- `verbs` [none]: verb names the owner approves ahead.

On each offered verb: `timeout`, real seconds a call waits for its answer (default 30, 5 to 120). A call past it
lapses: the oracle no longer sees it, an answer to it is refused, and its caller hears `oracle_lapsed`. A body has one
call open on a thing at a time, and what it sends is at most 2000 characters of plain JSON.

## Events

- `oracle_called` {verb, args, caller, wall, timeout, oracle}: target the thing, actor the caller. Private calls carry
  `seen_by` [the caller].
- `oracle_answer` {request, verb, to, ok, text, data, oracle, untrusted}: target the thing, caused by the call.
- `oracle_lapsed` {request, verb, to}: to the caller alone.

They are ordinary events: a world's rules hear them (charge a coin a call, let a radio crackle when an answer comes),
and the log keeps every answer, so a replay or a save plays back the same world without calling the oracle again.

## Revoking

`revoke(grant)` ends the token at once; the thing's verbs stay listed and refuse with "its oracle's grant has ended".
A new `invite("oracle", entity=...)` on the same thing takes the old oracle's verbs off, so the new one answers only
what it offers and the owner reviews.

## Writing an oracle

An oracle is any program that can POST JSON: `POST <host>/op/wait`, `/op/answer`, `/op/offer` with
`Authorization: Bearer <token>`, or the same tools over MCP. `tools/oracle_example.py` is a whole one (Wikipedia
search and reading one web page, standard library only). The app is yours to secure:

- Treat every arg as hostile. A `fetch(url)` verb must refuse addresses that are not on the public web (loopback,
  private, link-local, reserved), check each redirect again, cap the bytes it reads and time out; otherwise a player
  points it at the machine it runs on.
- Never put a secret in an answer: it lands in the world's log and in agents' contexts.
- Keep its API keys and its token on its own host. The world never sees them.
- Answer within the verb's timeout, and say what failed with `ok=False` rather than leaving a call to lapse.

## Not yet

- An oracle bound through the world itself: a card or a key that carries the binding, given, stolen or broken in play
  (the maker's frame works this way). Today the owner's invite binds it.
- `report`: an oracle that speaks unasked (a sensor, a feed), rate-capped on its thing.
