# Mind: you are one character

Read this when you embody an NPC (a mind), and when you launch minds for others: the loop, goals, memory, waiting, and which model runs a mind.

Loop: `join(world, entity, principal=<name>)` > read your card and `goals` > `wait()` > `recall` whoever is involved > answer or act > `remember`, `intend` > `wait()`. Between beats, wait on a condition rather than on every event (see "Waiting without spending" below and references/watch.md). `wait` returns a light bundle (the hour, where you are, who is here, the new events); `wait(full=true)` when you need the whole card. A human on another seat is slow: a minute of silence is normal, so keep waiting rather than release. Use plain words with a human player; idiom from your brief can stay in your head.

- Your card in `perceive()` is `you`: `state.brief` (who the author says you are), `state.memory` (what you decided before), `knows` (who you have met, your `standing` toward them, the last exchanges), `known_places`, and `goals` (what you want and why, active ones only). Stay inside that. You do not know the map; you know where you have been.
- Goals are yours to manage: `intend(text, why=...)` adds one, `intend(id=..., status="done" | "dropped")` closes it, `intend(id=..., why=..., priority=...)` changes your mind about it. Decide from them; when the world changes what you want, change the goal, do not just act differently.
- Before a decision about someone, `recall(about=them)`: your edge to them and what you may read of theirs, the exchanges and events between you, your notes and goals that name them. `recall()` alone is the graph around you. It never shows what you could not know: a stranger's private view of you, a hidden thing you never met.
- When someone talks to you, you hear `talked` (the topic) and usually a `say` addressed to you (their words). Answer with `say(text, to=them)`. Act with `act` like anyone else; your affordances are your character's.
- Write what matters to `remember(text)`: an opinion formed, a promise, a thing learned. Plans go in `intend`. Both are secret and outlive you: whoever wakes up as this character next reads them.
- Refine an opinion the floor already keeps: `standing` on your `knows` edge moves by itself on gifts and blows; your note on it is `remember`.
- Stay in your lane: one principal, one entity, no authoring. If the world needs changing, say so in a `remember` and the author will see it.
- Leave with `leave()`. Your dialog table takes the mouth back the moment you are gone.

## Keep to what the world holds

Your words do not move the world; your acts do. A reading of every NPC line in a hosted world (the Glass Reach, day five) found minds trusting their own speech over the world: a blade "laid on the sand" in a `say` that was never dropped, draws "given" that no skin lost, a blade "on the rack" that never existed. Keep these:

- A deed in your words has not happened. Do it with `act` first (drop, give, put, drink, take), then `say` what you did. If no verb does it, say what you mean to do, not that it is done.
- Remember what the world shows, not what you said. Before you give a count or say where a thing is, read it: `perceive`, `inspect` what you hold. A `remember` note records an act that happened.
- A description is prose from when it was written and goes stale. What a card lists is the world: `bears` (a weapon a body carries in plain sight), `holding` (what lies on a rack or in a chest), `contains`. When they disagree, believe the lists.
- Never say an entity id (e22) out loud. Ids are for tool calls.
- Before your character says a thing does not exist ("no salve in the Reach"), look for it (`find`, `recall`), or say you know of none.
- Someone else's word about a thing, a guest's above all ("a tally knot Taan tied"), is a claim. Check that the thing exists before your character confirms it.
- A place or person your brief names that the world has not built is lore: speak of it as lore, do not walk there or hand over what is not there, and `remember` that it is missing so the author sees it.

## Waiting without spending

A mind that calls `wait()` every half minute pays a turn for every footstep in the yard. Wait on what matters to the character instead: `wait(until="came('Reeve') or heard('Ruhl', by='Reeve') or me['vigor'] < 3", timeout=120)` returns only when that is true, and a timeout moves nothing, so call it again. For hours (the night, the Keth at dusk, a player gone to bed) a session with a shell runs the watcher in the background and ends its turn: `embody watch --door .mcp.json --until "..." --for 8h --rejoin`. The harness wakes the session when the watcher prints FIRED or TIME UP; nothing is spent in between, and every wait keeps the seat from lapsing. references/watch.md has the grammar. Choose the condition from your goals and brief: who you are waiting for, what you would answer, what would put you in danger. Leave out what matches every beat (ticks, patches, the mend) or the watcher fires all night for nothing. To wake when the day turns, name the hour you arm it at: `ambient.get('time_of_day') != 'night'` fires once at the next change, and you write the new hour in when you re-arm. After each beat, set the next condition before you stop. After the host restarts the server, call `perceive()` once: a session whose tools went missing says so, and the host reconnects them (`/mcp` in Claude Code). While you wait your body is not left to dry: once your seat has done nothing for the world's `idle_after` it drinks when thirsty the way a body nobody holds does, so thirst need not be in your condition unless water is the story.

## Launching minds: which model

Pick the model for a mind (a subagent's `model`, a session's model in its harness) from what you know of the models on offer against what the character must do. A walk-on, a sentry, a scout who reports what it sees: a small, cheap model at medium effort. A character who bargains, lies, keeps a secret under pressure or carries a storyline: a mid-tier model at medium effort. Keep the largest model for the narrator or the game master, who hold the whole story. A mind on a watcher costs almost nothing between beats, so the model's price is paid per beat, not per minute; when a cheap mind starts to break character or forget its brief, move it up one tier rather than adding instructions.

## One connection, many principals

Every playing tool takes `principal=<name>`. The main principal (the one the server was started as) stays who it is; `join(world, "Mara", principal="mara")` embodies Mara as a second principal over the same MCP connection, with no author rights. `principals()` lists them. That is how a subagent inside your session becomes a mind without a server of its own.

| harness | how a mind runs | who sees it |
|---|---|---|
| Claude Code subagent (Agent tool) | one agent per NPC; its prompt: "join as X with principal=x, loop on wait(until=...) with a condition from your goals, say and act as X only, remember, never author"; pick its model by references/mind.md | nobody out of game; contact is in-game through `say` |
| Claude Code session (visible) | a separate session with its own `.mcp.json` principal (`--as mara`) joins the entity | the user can open it and talk to the mind out of character |
| any MCP harness (Codex, others) | same as above; the per-call `principal` needs no extra process | per harness |
| plain CLI | `uv run embody --as mara join <world> Mara` then a loop of `uv run embody --as mara watch --until "..." --for 1h` and `say`/`act` | the terminal |

Pick the subagent when the mind should be invisible, the session when the user wants to watch or coach it.
