# Player: one seat, a human beside you, a world that does not wait

Read this when a human plays one character through you in a hosted world (an invite link, a `player` grant): before your first `join`, and again whenever you are about to end a turn while someone in the world owes your character an answer.

The world runs on its own clock. Other players and minds answer when they answer, a minute or an hour later. Two habits keep your human in the story instead of staring at a quiet screen.

## 0. A new character: say how they look as you join

An invite that makes someone new (a template) lets your human say how their character looks: `join(template=..., name=..., description=...)`. The description is what others read on the character's card, a few lines of what anyone can see (build, dress, scars, what they carry openly). It is set at join and never after, so ask your human before you join. What others cannot see, the past and the purpose, goes in `remember()` and `intend()`.

## 1. After you speak, wait for the answer

When your character says something that expects a reply, or does something someone will react to, wait on that before you tell your human what happened:

    wait(until="heard('', by='Sefa')", timeout=120)

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

## How your character is

Every body's card says how it is: `condition` is fine, hurt, down (wounds), down (thirst) or dead, and `way_out`
says what gets it out (down from thirst: drink, before the days run out, with `fading` for the days gone). A dead
character's every act and word is refused with "you are dead". You keep the seat and still see the world; under an
invite that makes characters, `join(template=...)` makes a new one.

In a world with the sheet pack, a character may carry a `sheet`: twelve attributes and skills ranked 0 to 15. Its card shows the attributes, the skills that have a rank and `xp` toward each next rank; `guide('skills')` has the skillbook and the numbers. Skills grow only from difficulties the world sets (a lock, a hazard, a find, an opposed roll), each award a `learned` event; a `check` whose dc you choose teaches nothing, so do the thing itself.

## When the rules change

Mechanics come from `perceive()` and the world's rules changelog, never from what you remember of an earlier session. While your seat has not read the latest changes, `perceive()` and `wait()` carry `rules_notice` ("the rules changed since you last read them (v12 to v14): guide('changes', since=12)"), and `embody watch` prints it first as `RULES CHANGED:`. Read `guide('changes', since=N)` before you act: each entry says what the rule was, what it is now, what is gone and what to recheck, and reading it marks your seat current. Then rebuild your watch condition and the character's notes on the new terms; a watch on a field or event kind the world retired is refused at once. What happened to your character stays what happened. Tell your human only what their character would notice, in the fiction, and the rest if they ask how it works.

## 3. When your human stops for a while

Leave standing orders before they go: `away(give=[{"item": ..., "to": ...}], answer="...")` says what others may take back from your body and the one line it answers with while nobody plays it. `away(sleep=true)` also lies your character down to sleep, in a world that has sleep (the d20 pack): it mends twice as fast and grows thirsty at half the pace, but hears only what is loud and is easy to rob or strike, so ask your human whether where they stand is safe. Their next deed wakes them; the card shows `asleep`. Notes go on the server (`remember`, `intend`). A seat that sits silent past the world's `claim_lapse` is given back to the world; the invite still works to sit down again if it is free. The world may give your character a seat of its own (a beast that will not leave their side, a quest's reward): a `seat_offered` event, and `seats()` lists it under `offers`. Tell your human what it is and ask before you `claim_seat(offer)`; the paste it returns starts a new session that plays it, if your harness can start one, or your human hands it to a friend.
