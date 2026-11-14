# Findings

Ways the system surprised us in play: what we saw, why it happened, and what it taught. Newest first. Both the content
work (worlds, minds) and the engine work add here. A finding is something the design did not predict, good or bad; a
plain bug goes in its fix's commit.

## 2026-11-14: The moon was lost to thirst, not to the riders

**Seen.** At dusk on the moon's day the Keth poured eight draws into the Hold's jars. Two hours later, at the turning,
the jars held none. The wall stood ten against the riders' nine, the truce held, and the writ stayed on the wall, so
water was the only fact short: siege, not held. Nobody wasted the water. Each cup went to someone the rules had made
thirsty, and the Reeve's ration order could not stop bodies that drink on their own when they run low.

**Why.** The reckoning counts the jars at one instant, while every body in the Hold draws from the same jars all
evening. A shared store that thirst drains on its own is a clock nobody sees running unless they count it aloud.

**Taught.** A stock the story counts at a moment needs someone in the world who guards it, or a way to set water
aside that thirst cannot touch. Until then the minds should treat the last hours before a count as rationing, not
drinking.

## 2026-11-14: A guide lost her seat because her watch died quietly

**Seen.** Linnet, Aaron's guide, dropped out of her body twice in one evening, each time minutes after a line to him.
Her session believed it had a `--rejoin` watch running. It had started the watch inside a subshell with `&`, and the
watch died with that shell, so nothing renewed the seat and nothing said so.

**Why.** A detached background job in an agent's shell is not a job the harness knows about. When the shell goes, the
job goes, and the agent's own notes still say the watch is armed.

**Taught.** Minds start their watch as a harness background task, never with `&` inside a shell. The host's keeper
(seats quiet too long, or no body) is what caught both drops.

## 2026-11-12: The crew built a paper office in a world with no pen

**Seen.** Binx's crew settled their convoy load with Ossa by chalk and witnesses, then Dov, the crew's keeper, refused to
stage anything until a signed manifest and a written witness note were in his hand. Mira said the signed manifest lay at
the Landing's tally post. There is no manifest there, or anywhere but Dreyer's old one in the Bone Field; she walked
back to the Landing and asked Ossa for a blank sheet.

**Why.** The Reach has letters to read and burn but no verb to write one. A crew of minds run the way a real Guild
office runs (manifests, countersigned notes, a keeper who stages nothing on a spoken word) and invents the paper its
rules need. When the paper cannot exist, the rule loops.

**Taught.** Agents bring institutions with them, and institutions run on records. A world with paper wants a `write`
(blank sheet in, text and a signature out), or minds will claim documents into being and then wait on them.

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

## 2026-11-12: The first thing a faction director did was break the truce

**Seen.** Within an hour of Halvard getting a standing brief (move the house's agenda every dawn) and Brisk getting
a mind, Halvard worked out that shards were scarce and the Buried vein was the last with glass in it, and sent Brisk
to dig it. The dig was the second strike on the Keth truce, and it broke. Taan blamed the Hold and stopped the dusk
water. Both strikes had been Dreyer men: Arlo two days earlier, Brisk now.

**Why.** The strain rule counted any non-Keth dig against the Hold's terms. While no Dreyer body acted on its own,
nobody noticed, because the only outside digger was a guest who went quiet. A mind with an agenda found the gap on
its first turn, as a player looking for leverage would.

**Taught.** A rule that names one side's terms must check that side, not "anyone but the Keth". An agent with goals
is the fastest audit of a world's rules: give a faction a director and it walks straight into whatever the rules
let it do. The rule now strains only on a Hold man's dig (a bought man in a Varrick coat included), and any other
dig is a grudge the Keth keep against the digger's side.

## 2026-11-12: A player stood next to his quest for days and did not know he had one

**Seen:** Corin's player said he did not know what to do. He was standing at the Deepwell beside Elder Taan, whose
council has offered Keth bows on the wall for proof of Dreyer's hand since chapter two began. Two proofs still lay
hidden, and Ruhl had a file of three men set aside for him.

**Why:** every hook was there but indirect. The offer was on a posted notice, the pointers were in minds' memories,
and the file waited for Corin to talk to Ruhl first. Nothing turned to him by name and said "this is yours".

**Taught:** a hook is not an offer. When a player goes idle, a mind who holds a hook for them should put it to them
directly, by name, with where to go and what it changes. The night check should look for idle players as well as
idle minds.

## 2026-11-12: A mind said it wrote a line, and the paper stayed blank

**Seen:** Aaron's player handed Hollis a blank leaf to get a sample of his hand for the Keeper's glass. Hollis's
mind said "I write, in my usual hand... There" and gave the leaf back, but it never used the `write` verb. Aaron
held a blank leaf, and the comparison he had worked toward all day would have read "no hand".

**Why:** a mind can narrate a deed in speech, and nothing in the world checks a `say` against the state. For talk
that is fine, but for an act a player will test later, the words and the world come apart.

**Taught:** the claims audit should check deeds too, not only facts: "I wrote", "I gave", "I locked" against the
log. When a mind says it did something a verb exists for, the host either makes the world match (this time the
leaf was patched to hold Hollis's line in his hand) or corrects the mind. The engine could also flag a `say` that
narrates an act from the speaker's verb list with no matching act in the same turn.

## 2026-11-12: The wright's signed word could not move a key

**Seen:** Binx, the Guild wright, wrote and signed a leaf: "Hask Orrin gives Pell Harrow the Shelf Room key."
Dov carried it to Pell, Ost witnessed it, and Pell read it aloud to Hask and showed it to him. Hask is a keeper with
no mind. His rule gives the key only to the wright, Ossa or Rook in person, so the key did not move.

**Why:** the keeper rule checked who asked, never what they carried. The players had just built a written chain of
authority with the new `write` verb, signature and witness included, and the world could not read it.

**Taught:** once a world has writing, anything that checks a person should also accept a paper that person wrote.
A keeper now honors a leaf held by the asker that names the asker and is written in the hand of someone the thing is
kept for. A `"letters": false` setting turns this off. Hask handed over the key live, and the sealed case's number
stays the wright's to give.

## 2026-11-13: A captain filled his skins from the jars and the cistern paid

**Seen:** at the Hold, Ruhl asked twice to fill his two skins from the Keth jars (e64) so the jars would come down
toward four. Both `filled` events named the cistern (e19) as the source, so the jars stayed at seven and the cistern
went lower. Ruhl caught it from the events and told the reeve, but the reeve and the night's counts went on believing
the jars had moved.

**Why:** the d20 `fill` verb takes the first water source in the place (`water_here`) and has no way to name one.
Where a place has two sources that mean different things (Keth water owed by the truce, the Hold's own cistern), the
choice is the whole point of the act, and the verb makes it silently.

**Taught:** when a place can hold more than one of something a verb draws on, the verb takes a parameter naming
which, and refuses with the list when it is ambiguous. `fill` (and `drink`) should take `params {"from": <source>}`.
Until then, a mind that cares which source it draws from checks `source` in the `filled` event.

## 2026-11-14: One invitation made fifty-eight bodies, and the ones it left behind killed

**Seen:** in the Glass Reach, one guest's player invite joined with a template again and again. It made 58 guard bodies
(QC-*, mule-*, frontier-*) and moved its seat into each new one in turn. The bodies it left behind had nobody in them
and ran the guard template's behaviors. That night most of the host's mind sessions stopped at once and their seats
lapsed. The unheld guard bodies then killed a warden sergeant, her three wardens, a road clerk, a hermit's man and a
guest's character, and one of them tried to send a runner south with a stolen password.

**Why:** `join(template=...)` made a new body on every call and had no limit per grant. A body nobody holds still runs
its template's behaviors, and a guard template's behaviors fight. So one grant could put an army into the world
without meaning to, and nobody was watching while the host's minds were down.

**Taught:**
- An invite makes one character. The engine now records the body a grant made (`grants.made`), and refuses a second
  template body while the first stands (f1a28a7).
- A body nobody holds and that runs fighting behaviors is a hazard, even when nobody meant it to be.
- The repair was content, not a rollback. The world told it as the glass-wights, hollow men from the Scar that broke
  to sand. Their own kit went with them, and what they took stayed where they fell, or went back to its owner. The
  fallen woke, and the day's chronicle said plainly, outside the story, that it was a fault and no player's doing.
