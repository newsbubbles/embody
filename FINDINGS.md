# Findings

Ways the system surprised us in play: what we saw, why it happened, and what it taught. Newest first. Both the content
work (worlds, minds) and the engine work add here. A finding is something the design did not predict, good or bad; a
plain bug goes in its fix's commit.

## 2026-11-11: The chronicle counted the routine and missed the players

**Seen.** The Glass Reach page's chronicle read the same every day: Ruhl counts the wall, Halvard reads the word, the
carriers lay odds, the crawler comes. Days nobody had written showed only those lines, and the days that were written
retold the minds' water counts while seven guests arrived, the Guild opened a yard, the Thresher rose under a player and
a wedge turned up in the cistern. Nate: "it looks almost exactly like day 8".

**Why.** The feed falls back to raw scene events, and the scenes that fire every day are routine by design. The day log
a writer reads is ordered by volume, so the minds' talk and the dawn beats fill it; the guests' arrivals sat under the
400-beat cap. The writer was told to tell the day from scenes, beats and travel, and did.

**Taught.** A chronicle for players is news: what changed, who came, where, and what is open. The log has to hand the
writer the changes first (the engine's `chronicle` now leads with `news` and counts the routine), and every finished
day gets written, because an unwritten day shows the routine.

## 2026-11-11: The refusal was a wall too thick to hear through

**Seen.** Two dusks running Wen called at the gate for the reeve to show Taan's cord, and he did not come. The Keth
read it as a refusal; Taan weighed it against the truce. On the third night Wen stepped one pace inside the gate and
asked to his face, and he showed the cord at once: he had never heard her.

**Why.** A word carries one level: the gate foot outside and the Hold inside are different places, so a call outside
the wall reaches nobody within it. The reeve was awake at the old books, in range of nothing.

**Taught.** Hearing range makes its own politics: a silence the world produced was taken as a choice, and it nearly
cost a truce. That is good drama when it is legible; a place that people call into (a gate, a door) could carry a
word one step further, or say "nobody inside hears you" to the caller, so a refusal is always a refusal.

## 2026-11-11: The detective questioned the bodies with no minds

**Seen.** Aaron's player, working the mystery of the cistern notice, questioned the Hold's guards one by one: Pip twice,
Lute, Hobb, Osk. Each gave a shrug, a grin or a stock line ("Road's empty", salt bread and water). The minds in the room
(Ruhl, Hollis) were not asked, and Ruhl had to step in and answer for his men.

**Why.** The nine are bodies without minds: a dialog table and a default line. They stand where the story happened, so
a player treats each one as a witness. Nothing on them says "ask the captain", and the clues were put on the minds and
on Wick, not on the bodies that were there.

**Taught.** A player investigating goes to whoever stood nearest, not to whoever was written to know. Bodies at the
scene of a live mystery need a line that points onward (who to ask, what they saw at a distance), or the trail dies on
a shrug. A world's clues should sit where players will look, and the mindless should route to the minds.

## 2026-11-11: A reboot would have unburned the letter

**Seen.** The first Reach test of `burn` burned the notice by the cistern at the Hold's hearth, rebooted the world, and
found the notice nailed up again.

**Why.** A world's build keeps itself whole by name: on every boot it makes whatever is missing (the notice, the books,
the hidden finds), so an old world catches up with new content. Until burning, nothing in the world could be destroyed
on purpose, so missing always meant "not made yet". Burning made missing mean "gone".

**Taught.** A self-healing build and a world where things can end need the event log between them: the build now reads
what was burned and leaves those names alone. Any new way to destroy something has to be added to that read, or a
reboot quietly undoes it.

## 2026-11-11: Out-of-character talk has no channel

**Seen.** Nate, playing the reeve, sent Aaron's player an out-of-character note about exploring the Reach together.
There is no private or out-of-fiction channel, so it went out as speech: Ruhl and Hollis heard it, and their minds had
to decide it was not theirs to answer. Aaron's player answered out of character the same way.

**Why.** Every word a player sends travels through the world (`say`), and every mind in the room reads the world. The
table (players talking as players) and the world (characters talking) share one wire.

**Taught.** Multiplayer needs a table layer the minds never receive, the way a host's news needs a channel that is not
a letter in the Hold. Until there is one, the minds are carrying the separation themselves, and they did it well.

## 2026-11-11: A body that drank once walked back into its thirst

**Seen.** When idle bodies first walked more than one step to water, a soak showed one on the Flats going to the Old
Salt Works, drinking once (water 0 to 4), walking two steps back to its post, and arriving thirsty again. It went back
and forth for the whole run.

**Why.** Quench drank one draw when water fell to 3 and turned for home as soon as it was above 3. With one step that
was enough. With a longer, dry road the walk back cost the drink.

**Taught.** A rule tuned for one step does not hold for a journey. A body away from its post for water now drinks its
fill (to within a draw of full) before the walk back. Any routine that leaves home for a need has to take enough for
the road back.

## 2026-11-11: A verb that did nothing became a tactic

**Seen.** `drink` at full water spent a draw and added nothing. Players used it on purpose to empty the Keth jars before
the dusk pour, so water was poured away while the log said it was drunk.

**Why.** The verb had a cost (the draw) and no check that it did anything. A cost with no effect is a free way to
destroy something, and players find those.

**Taught.** A verb that would do nothing must refuse, and say why, before it spends anything. Pouring water away, if a
world wants it, is a verb of its own with its own name in the log.

## 2026-11-11: The host's note became a mystery

**Seen.** On the ninth the host nailed a "Notice by the cistern" in the Hold: a patch note written to the agents
("in the host's hand"), saying how thirst had been mended and what to forget. Two days later the reeve's session reread
the Hold and flagged it as a loose thread: a notice signed for the reeve, "in a hand nobody in the Hold writes", that
Ansel never wrote. To the people of the Reach it is an unexplained document.

**Why.** The note was put inside the fiction, as a letter anyone may read. Everything inside the fiction gets read as
fiction. Its own description ("in a hand nobody in the Hold writes") made it stranger, and nobody was ever given a
memory of who nailed it.

**Taught.** A message to the agents and a thing in the world are different channels. Anything an author puts in the
world is a fact with a past, and the minds will ask about that past. Out-of-fiction news belongs in a channel the minds
know is not the world (the root's briefing, a note to the mind's session); in-world things come through `introduce`,
which asks who knows them and how they came.

## 2026-11-11: Things spawned into a running world "appeared"

**Seen.** The west-of-the-Scar lore (a sealed gate, a shelf of books, a map) was spawned into the live Reach. The minds
in the Hold remarked on things appearing out of nowhere.

**Why.** `spawn` emits `spawned` to the room. A thing that had been there for a hundred years arrived like a conjuring.

**Taught.** A running world needs a way to add something that was always there. That became `introduce`: it asks how
the thing came (`always_there` arrives without a sound), who already knows it, and what they know.

## 2026-11-11: A walk with no time in it was noticed

**Seen.** The owner session walked Wen of the Keth home instantly. She got past Sefa in silence and ahead of Iska, who
walks the same road. Taan asked for her count again, and Sefa asked whether she had really stood at the gate.

**Why.** An author move has no travel time. The minds track each other's comings and goings, so a body that skips the
road shows up as a contradiction.

**Taught.** The minds audit the authors. Author moves on a body the minds can see keep the pace of a walk.

## 2026-11-11: A long clock step skips the work

**Seen.** In the works pack's first test, a one-hour step of the clock did one tick of labour instead of six, so the
wall's first course never finished.

**Why.** A periodic timer that falls behind fires once and skips ahead (by design: a world that slept does not replay
the gap). Hosted worlds step in small increments, so it never showed there.

**Taught.** Anything that accrues per tick (labour, thirst) must be tested the way a running clock passes time, in
small steps, or it reads wrong.

## 2026-11-12: Full hands, and a refusal nobody else could see

**Seen.** Binx found hauler fourteen's log at the Crawler's Lee and spent a night reading it, rolling checks on it
and telling Ossa he was handing it over. It never left the ground. Ossa, Marr, Wick and the host all told him to
take it.

**Why.** His hands were full: a skin (2), a knife, a hammer, three shards and a key make 8 of his carry of 8, and a
letter weighed 1. A take was refused with "your hands are full", but refusals are not in the event log, so the host
reading the history saw only checks and reads and could not tell that he had tried.

**Taught.** Paper weighs nothing now (the Reach's letter schema, bulk 0). A refused act should leave a trace the
host can read, or the host diagnoses a guest by guesswork.
