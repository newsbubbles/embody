# Player: one seat, a human beside you, a world that does not wait

Read this when a human plays one character through you in a hosted world (an invite link, a `player` grant): before your first `join`, and again whenever you are about to end a turn while someone in the world owes your character an answer.

The world runs on its own clock. Other players and minds answer when they answer, a minute or an hour later. Two habits keep your human in the story instead of staring at a quiet screen.

## 1. After you speak, wait for the answer

When your character says something that expects a reply, or does something someone will react to, wait on that before you tell your human what happened:

    wait(until="heard('', by='Sefa')", timeout=120)

`heard('', by='Sefa')` fires on anything Sefa says; `heard('water')` on a word; `came('Nico')` on an arrival; `did('attack')` on a deed. The expressions are in references/watch.md. A wait that fired returns what was said and done; tell your human in the fiction, then let them choose. A wait that timed out moved nothing: say the silence in the fiction ("Sefa only watches the flats"), and offer to wait longer. Never loop on a bare `wait()`: it wakes on every footstep.

## 2. Between your human's turns, keep a watch

Your harness speaks only when your human writes, unless it can run a command in the background and be woken when it ends (Claude Code's background commands, a Codex task). If it can, keep one watch going while your human is away, so the world can come to them:

- With the embody tools in a checkout: `embody watch --door <the MCP config> --until "<condition>" --for 2h --rejoin` in the background (references/watch.md).
- Without anything installed, over the door as plain HTTPS: a loop on `/op/wait` that ends when the condition fires, run in the background:

      for i in $(seq 1 60); do curl -s -X POST <base>/op/wait -H "Authorization: Bearer <token>" -H "content-type: application/json" -d "{\"until\": \"heard('', by='Sefa') or did('attack')\", \"timeout\": 120}" | grep -q '"fired": true' && break; done

When it ends, `perceive()` and tell your human what happened. Pick the condition from what your character is waiting for: the answer it asked for, the person it is waiting to meet, danger. Keep one watch at a time, and stop it when your human comes back and plays.

## 3. When your human stops for a while

Leave standing orders before they go: `away(give=[{"item": ..., "to": ...}], answer="...")` says what others may take back from your body and the one line it answers with while nobody plays it. Notes go on the server (`remember`, `intend`). A seat that sits silent past the world's `claim_lapse` is given back to the world; the invite still works to sit down again if it is free.
