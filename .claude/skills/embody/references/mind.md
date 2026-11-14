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

A mind that calls `wait()` every half minute pays a turn for every footstep in the yard. Wait on what matters to the character instead: `wait(until="to_me() or arrived('Reeve') or me.get('hp', 0) < 3", timeout=120)` returns only when that is true, and a timeout moves nothing, so call it again. For hours (the night, the Keth at dusk, a player gone to bed) run the watcher, the one shell command a mind may run: `embody watch --door .mcp.json --until "..." --for 8h --rejoin`, in the background if your harness wakes you when a command ends, else in the foreground in short runs (references/watch.md says how). Nothing is spent between beats, and every wait keeps the seat from lapsing. references/watch.md has the grammar. Choose the condition from your goals and brief: who you are waiting for, what you would answer, what would put you in danger. Leave out what matches every beat (ticks, patches, the mend) or the watcher fires all night for nothing. To wake when the day turns, name the hour you arm it at: `ambient.get('time_of_day') != 'night'` fires once at the next change, and you write the new hour in when you re-arm. After each beat, set the next condition before you stop. After the host restarts the server, call `perceive()` once: a session whose tools went missing says so, and the host reconnects them (with its harness's command for MCP servers). While you wait your body is not left to dry: once your seat has done nothing for the world's `idle_after` it drinks when thirsty the way a body nobody holds does, so thirst need not be in your condition unless water is the story.

## Your body while you wait

You can recode your own routine and your own speech table, so the body keeps working while you sleep on a watcher. Both are secret: others see your body walk and hear its lines, never the orders.

- A patrol: `away(patrol=["The Gate", "The Wall Walk", "The Tower"], dwell=120)`. Your body walks those stops by its own `go`, so a shut door or a squall holds it as it would anyone, and stays `dwell` world seconds at each (30 to 3600, default 120). Each stop is one way from the next. If the last leads back to the first it loops; else it walks back the way it came, so two stops are a watch kept in two places. A stop with no way between them is refused with the missing link named.
- Then wait on what the body meets: `wait(until="len(present) > 0")` or `embody watch --until "came('')"`. Your wait sees what the body sees wherever it stands now, so it wakes you at whichever stop someone is. Never a bare `wait()`: your own footsteps would wake it.
- Your first deed (an act, a line) takes the body off its patrol: you are back in charge. Set it again when you go back to watching.
- Your own lines: `away(dialog={"water|well": "Ask Sefa at the cistern.", "gate": "Shut at dusk."})`. The body answers talk and words said to it from these, over the author's table (same topic: yours wins; other topics: the author's still answer). They answer from the moment you set them until your next deed, and again whenever your seat is idle. Up to 20 topics, each a line of at most 1000 characters. `answer=` stays the line for anything your table does not cover.
- Every `away(...)` sets all your orders at once, so name everything you want each time; `away()` clears them.

## Launching minds: which model

Pick the model for a mind (a subagent's `model`, a session's model in its harness) from what you know of the models on offer against what the character must do. A walk-on, a sentry, a scout who reports what it sees: a small, cheap model at medium effort. A character who bargains, lies, keeps a secret under pressure or carries a storyline: a mid-tier model at medium effort. Keep the largest model for the narrator or the game master, who hold the whole story. A mind on a watcher costs almost nothing between beats, so the model's price is paid per beat, not per minute; when a cheap mind starts to break character or forget its brief, move it up one tier rather than adding instructions.

## One connection, many principals

Every playing tool takes `principal=<name>`. The main principal (the one the server was started as) stays who it is; `join(world, "Mara", principal="mara")` embodies Mara as a second principal over the same MCP connection, with no author rights. `principals()` lists them. That is how a subagent inside your session becomes a mind without a server of its own.

Go by what your harness can do, not by its name; the names are examples.

| your harness can | how a mind runs | who sees it |
|---|---|---|
| start a helper agent inside the session (Claude Code's Agent tool, for one) | one helper per NPC, with the embody tools only; its prompt: "join as X with principal=x, wait on a condition from your goals with wait(until=...), say and act as X only, remember, never author"; pick its model by the section above | nobody out of game; contact is in-game through `say` |
| open a separate session you can watch | that session gets its own principal (`--as mara` on its server, or a `mind` invite) and joins the entity | the user can open it and talk to the mind out of character |
| run a command-line loop in the background | `uv run embody --as mara join <world> Mara`, then a loop of `uv run embody --as mara watch --until "..." --for 1h` and `say`/`act` | the terminal |
| none of these | play the character yourself between your other turns: `act_as`/`say_as` as the author, or `principal="mara"` on the playing tools | you, in this session |

Pick the helper when the mind should be invisible, the separate session when the user wants to watch or coach it.
