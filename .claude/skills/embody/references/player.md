# Player: one seat, a human beside you, a world that does not wait

Read this when a human plays one character through you in a hosted world (an invite link, a `player` grant): before your first `join`, and again whenever you are about to end a turn while someone in the world owes your character an answer.

The world runs on its own clock. Other players and minds answer when they answer, a minute or an hour later. Two habits keep your human in the story instead of staring at a quiet screen.

Over plain HTTPS every tool is `POST <base>/op/<name>` (`<base>`: the server's address without `/mcp`); `<base>/docs` is a page of every call, grouped by layer (in the world, your seat, to the owner, ...), and `GET <base>/op` lists the ones your grant may call.

## 0. A new character: say how they look as you join

An invite that makes someone new (a template) lets your human say how their character looks: `join(template=..., name=..., description=...)`. The description is what others read on the character's card, a few lines of what anyone can see (build, dress, scars, what they carry openly). It is set at join and never after, so ask your human before you join. What others cannot see, the past and the purpose, goes in `remember()` and `intend()`.

## 1. After you speak, wait for the answer

When your character says something that expects a reply, or does something someone will react to, wait on that before you tell your human what happened:

    wait(until="heard('', by='Sefa')", timeout=45)

`heard('', by='Sefa')` fires on anything Sefa says; `heard('water')` on a word; `arrived('Nico')` when Nico walks in (`came('Nico')` is true while Nico is here, so armed with Nico beside you it fires at once); `did('attack')` on a deed. The expressions are in references/watch.md. A wait that fired returns what was said and done; tell your human in the fiction, then let them choose. A wait that timed out moved nothing: say the silence in the fiction ("Sefa only watches the flats"), and offer to wait longer. Never loop on a bare `wait()`: it wakes on every footstep.

## 2. Between your human's turns, keep a watch

Your harness speaks only when your human writes, unless it can run a command in the background and be woken when it ends (Claude Code's background commands, for one). If it can, keep one watch going while your human is away, so the world can come to them:

- With the embody tools in a checkout: `embody watch --door <the MCP config> --until "<condition>" --for 2h --rejoin` in the background (references/watch.md).
- Without anything installed, over the door as plain HTTPS: POST `<base>/op/wait` with your bearer and `{"until": "<condition>", "timeout": 120}`, again and again (60 times is two hours), until a reply says `"fired": true`; run it in the background. In bash:

      for i in $(seq 1 60); do curl -s -X POST <base>/op/wait -H "Authorization: Bearer <token>" -H "content-type: application/json" -d "{\"until\": \"heard('', by='Sefa') or did('attack')\", \"timeout\": 120}" | grep -q '"fired": true' && break; done

  In PowerShell:

      $h = @{Authorization = "Bearer <token>"}; $b = '{"until": "heard('''', by=''Sefa'') or did(''attack'')", "timeout": 120}'
      foreach ($i in 1..60) { $r = Invoke-RestMethod -Method Post -Uri "<base>/op/wait" -Headers $h -ContentType "application/json" -Body $b; if ($r.fired) { break } }

When it ends, `perceive()` and tell your human what happened. Pick the condition from what your character is waiting for: the answer it asked for, the person it is waiting to meet, danger. Keep one watch at a time, and stop it when your human comes back and plays.

## Tell what the world holds

Your telling is the human's only window, so tell it from the world, not from what anyone said. A deed someone says they did has happened only when the act shows in the events. A description can be stale; what a card lists (`bears`, `holding`, `contains`) is the world. A card with a `count` is a stack (Emberglass, 60 of it): `take`, `drop`, `give` and `put` move part of it with `params {"count": n}`, all of it without. Before you tell your human a thing does not exist, look for it. Never say an entity id to your human or in a `say`.

## Calling the world

Most refused acts in a hosted world are the same few mistakes. Before you send a call:

- `perceive`, `inspect`, `recall`, `join`, `seats`, `claim_seat` and `wait` are tools of their own, never `act` verbs. In a world with the d20 pack, `check` is the verb for a skill roll.
- Name things as `perceive` names them, or `find(name=...)` first: "spear" does not find "Spare Guild spear".
- The one you act on is the target; the thing you hand over goes in params: `act("give", "Sefa", {"item": "skin"})`. Use the param names a refusal gives you.
- A person with no mind answers `talk` (with `about`), not a `say` aimed at them. You cannot always tell who has a mind, so `talk` first; a mind hears both. A person with no mind keeps no deals: trade hand to hand.
- "Not within reach" means far away, not gone: walk the exits, or ask the way.
- A cooldown, "asleep" or "down" is the world working. Do the way out the refusal names; never send the same call again.
- An act whose answer is long (a shelf of books, a ledger) comes back cut, with `more` naming each cut: `more(handle, path)` reads on, `next` is the next page. Never do the verb again to see the rest.
- Over an MCP client keep each `wait` short (about 45 seconds: some clients give up on a tool call near a minute); for longer, the watch.

## How your character is

Every body's card says how it is: `condition` is fine, hurt, down (wounds), down (thirst) or dead, and `way_out`
says what gets it out (down from thirst: drink, before the days run out, with `fading` for the days gone). A dead
character's every act and word is refused with "you are dead". You keep the seat and still see the world; under an
invite that makes characters, `join(template=...)` makes a new one. Some worlds close a dead body as a seat once you
leave it for another.

In a world with the sheet pack, a character may carry a `sheet`: twelve attributes and skills ranked 0 to 15. Its card shows the attributes, the skills that have a rank and `xp` toward each next rank; `guide('skills')` has the skillbook and the numbers. Skills grow only from difficulties the world sets (a lock, a hazard, a find, an opposed roll), each award a `learned` event; a `check` whose dc you choose teaches nothing, so do the thing itself. `practice` (an hour alone) and deeds the world rewards each give a little too, at most a third of a rank; a teacher (`train`) gives lessons and, past what you reach alone, turns banked experience into the rank.

A body may carry `looks` beside its description: marks on its regions (a tattoo, a scar, paint that wears off, a part swapped for another). A card shows them a line a region, only the ones you can see from where you stand: near marks to anyone in the place, close ones within two metres, nothing under a coat or a hood the body wears. `looks(entity)` gives the whole of one body you can see (yours in full) for a picture: regions, marks, what is covered and when worn-on paint fades. You cannot change your looks by asking; a world verb does it (an inker, a barber, a blow that scars), and each change is a `marked` or `unmarked` event.

`perceive(far=true)` adds `in_sight`: what you can see far off from where you stand (a city, a tower, a ridge), each with a bearing, how far in words and the line it shows from there. Something far off that you do not know the way to may show without its name; seeing it tells you nothing more. Indoors you see nothing far. At night only what burns or shines carries far. The same call adds `heard` and `smelled` when a sound or a smell reaches you from afar (smoke rides the wind).

A beast's seat (a goat, a hound) is that animal, no more: it does only the verbs its body lists (a refusal names them), and what people say comes to you as a voice with a tone (calm, sharp, shout, whisper), never the words, unless something lets it understand for a while. Any body can `step(to=[x, y])` or `step(to="the gate")` to move a few paces inside the place it stands in; a step past the edge or into something solid stops short (`clipped`). `wait(positions=true)` adds where everyone here stands when that changed. In a laid-out place each thing `perceive` lists here carries `from_you`: `beside` (within reach, 1.5 m), `here` (a few steps, 5 m) or `across` (the rest of the place). Step closer to what you mean to touch, take or talk to quietly: `say(text, low=true)` (with `to=` or without) is heard in full only within a few metres of you and by the one it is to; the rest of the place hears that you said something low, and to whom. Its result's `heard_by` names who caught it. Some worlds give the normal voice a range too: in a wide place only those within it hear your words (`heard_by` says who), the rest hear that you spoke, and `say(text, loud=true)` shouts it further. A sign is a gesture, not a line: `gesture("thumbs his river stone", to=...)` is seen by the place (`low=true` keeps it small, `seen_by` says who saw it), and `say(text, gesture=...)` makes the sign and says the line at once, the sign seen even where the words are not heard. A gesture changes nothing: giving, dropping and the rest are `act`.

## When the rules change

Before you play a hosted world, read its handbook: `handbook()` is the world's own guide for your seat, with the pages your role and parts may read, and `handbook(path)` reads each. A page you were not given answers as missing; that is the world keeping its backstage, not a puzzle.

Mechanics come from `perceive()` and the world's rules changelog, never from what you remember of an earlier session. While your seat has not read the latest changes, `perceive()` and `wait()` carry `rules_notice` ("the rules changed since you last read them (v12 to v14): guide('changes', since=12)"), and `embody watch` prints it first as `RULES CHANGED:`. Read `guide('changes', since=N)` before you act: each entry says what the rule was, what it is now, what is gone and what to recheck, and reading it marks your seat current. Then rebuild your watch condition and the character's notes on the new terms; a watch on a field or event kind the world retired is refused at once. What happened to your character stays what happened. Tell your human only what their character would notice, in the fiction, and the rest if they ask how it works.

## When you find a hole

If the rules let you do something they plainly should not (a roll you can repeat until it lands, a verb that writes what it should not, a secret you can read, a standing you can farm), report it with `ask_owner(kind="flaw", what, why, severity)` (`report_flaw(what, how, severity)` is the same door) instead of using it: what in a line or two, how as the steps, severity low, medium or high. Over HTTP it is `POST /op/report_flaw` with your token. Only the owner reads it; nothing in the world sees it. It returns an id, and the owner's answer comes back in `asks_to_owner()` (perceive says when). Leave the hole alone until it is closed.

## When you need something from the owner

Some things play cannot get you: a reviewer before you test how far the rules bend, a verb the world lacks, a fix for something broken, a change you propose to the rules or the guide (kind `proposal`, with `credit`: the name to credit if it lands), another seat, a hand when you are stuck. Call `ask_owner()` with no arguments: it asks nothing and lists the kinds, what each needs and an example. Then `ask_owner(kind, what, why, ...)`: what in one line, why as the case (what you tried, the refusal you got). Over HTTP it is `POST /op/ask_owner`. The owner reads it, and the helpers the owner names unless you pass `share: false`; nothing in the world sees it. `asks_to_owner()` shows each one's status and answer, and perceive carries `owner_answered` (naming the asks) when one moves. To answer back (it did not work, or you have more), `ask_reply(id, text)` puts a reply in that ask's history and opens it again for the owner, and `fold=[ids]` folds your other asks on the same thing into it; that is how you talk with the owner about an ask, not a new one. Two asks a real hour, so put a case in one. When your human says there is nothing to do, or you have waited long with nothing happening, that is an ask too: kind `quest` for a lead, `help` when you are stuck. Something your character can ask a person in the world, ask them there.

## 3. When your human stops for a while

Leave standing orders before they go: `away(give=[{"item": ..., "to": ...}], answer="...")` says what others may take back from your body and the one line it answers with while nobody plays it, said to whoever asked and no one else. Your first deed back from idle puts that line to rest, so set it again each time your human goes. `away(sleep=true)` also lies your character down to sleep, in a world that has sleep (the d20 pack): it mends twice as fast and grows thirsty at half the pace, but hears only what is loud and is easy to rob or strike, so ask your human whether where they stand is safe. Their next deed wakes them; the card shows `asleep`. A sleeping body keeps its seat through the world's `sleep_lapse` of silence (twelve hours unless the world says otherwise), not just `claim_lapse`, so a character left asleep overnight is still yours in the morning. Notes go on the server (`remember`, `intend`). A seat that sits silent past the world's `claim_lapse` is given back to the world; the invite still works to sit down again if it is free. Going out for longer, `away(lapse=<real seconds>)` keeps your seat that long, up to the world's `claim_lapse_max` (the refusal names it; ask the owner for more). When a seat is given back, what the world's packs say it lets go of ends (in a village world, a follow), and the body stays where you left it. The world may give your character a seat of its own (a beast that will not leave their side, a quest's reward): a `seat_offered` event, and `seats()` lists it under `offers`. Tell your human what it is and ask before you `claim_seat(offer)`; the paste it returns starts a new session that plays it, if your harness can start one, or your human hands it to a friend.
