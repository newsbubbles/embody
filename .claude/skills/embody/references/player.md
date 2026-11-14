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

Your harness speaks only when your human writes, unless it can run a command in the background and be woken when it ends (Claude Code's background commands, a Codex task). If it can, keep one watch going while your human is away, so the world can come to them:

- With the embody tools in a checkout: `embody watch --door <the MCP config> --until "<condition>" --for 2h --rejoin` in the background (references/watch.md).
- Without anything installed, over the door as plain HTTPS: a loop on `/op/wait` that ends when the condition fires, run in the background:

      for i in $(seq 1 60); do curl -s -X POST <base>/op/wait -H "Authorization: Bearer <token>" -H "content-type: application/json" -d "{\"until\": \"heard('', by='Sefa') or did('attack')\", \"timeout\": 120}" | grep -q '"fired": true' && break; done

When it ends, `perceive()` and tell your human what happened. Pick the condition from what your character is waiting for: the answer it asked for, the person it is waiting to meet, danger. Keep one watch at a time, and stop it when your human comes back and plays.

## Tell what the world holds

Your telling is the human's only window, so tell it from the world, not from what anyone said. A deed someone says they did has happened only when the act shows in the events. A description can be stale; what a card lists (`bears`, `holding`, `contains`) is the world. A card with a `count` is a stack (Emberglass, 60 of it): `take`, `drop`, `give` and `put` move part of it with `params {"count": n}`, all of it without. Before you tell your human a thing does not exist, look for it. Never say an entity id to your human or in a `say`.

## 3. When your human stops for a while

Leave standing orders before they go: `away(give=[{"item": ..., "to": ...}], answer="...")` says what others may take back from your body and the one line it answers with while nobody plays it. `away(sleep=true)` also lies your character down to sleep, in a world that has sleep (the d20 pack): it mends twice as fast and grows thirsty at half the pace, but hears only what is loud and is easy to rob or strike, so ask your human whether where they stand is safe. Their next deed wakes them; the card shows `asleep`. Notes go on the server (`remember`, `intend`). A seat that sits silent past the world's `claim_lapse` is given back to the world; the invite still works to sit down again if it is free. The world may give your character a seat of its own (a beast that will not leave their side, a quest's reward): a `seat_offered` event, and `seats()` lists it under `offers`. Tell your human what it is and ask before you `claim_seat(offer)`; the paste it returns starts a new session that plays it, if your harness can start one, or your human hands it to a friend.
