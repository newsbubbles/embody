# Findings

Ways the system surprised us in play: what we saw, why it happened, and what it taught. Newest first. Both the content
work (worlds, minds) and the engine work add here. A finding is something the design did not predict, good or bad; a
plain bug goes in its fix's commit.

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
