# The Reach's chapters: the long road

Nate, 2026-11-12. The pattern: every chapter brings new players, and the world grows to hold them. Each chapter's
authority is bigger than the last one's, and each one opens ground that was only talk before.

## 1. Water to the Hold (done)

The truce with the Keth, the cistern, Hollis in his ring.

## 2. The standoff (now)

House Dreyer against House Varrick at the moon's turn. Four contests and the truce decide held, siege, fallen or
yielded (scripts/reach_moon.py, reach_chapter.py). Ends at the moon, in a death, or in the writ.

## 3. The Guild comes down hard

Whoever wins or dies, the Carriers' Guild stops being the neutral carrier and becomes the authority that leans on
everyone: the big bad. It starts with what is already built: the factor and the reckoner come down a day after the
moon with the five speakers (scripts/reach_speakers.py) and name who holds the gate for a price. **The High Landing
opens as a place you can go**: the Guild's platform, the "slow star" that crosses before dawn, fifty kilometres keel
to tip, with the reckoning halls on its third ring (already canon in build.py and the Guild-speakers notes).

## 4. The Empire

The Reach is one planet in a vast empire, as in Dune. **It is already in the canon as the Crown**: the Crown's writ,
the Crown's grant to the Tessels, the Crown's masons, the Crown surveyor, and the Host (the Crown's night riders who
keep the water law, in Taan's old lore). The Crown becomes a faction with a face, and whatever the Guild chapter left
standing answers to it. **More planets open**, each with its own environment and resources the empire values and its
own story arcs, and the arcs braid together from here on. Keep it Dune-like, not Dune: a public world should not use
Dune's names or setting.

## 5. Interlopers

Five factions by now (Varrick, Dreyer, the Keth, the Guild, the Crown). Who really runs the empire is open. New
factions and new worlds come in: perhaps a parallel empire from a far corner of the galaxy. A question for this point
is scale: are we galactic, across many star systems? Nate's guess at the population: over 1,000 players and five times
that in NPCs living their lives.

## What each step asks of the engine and the hosting

- **Chapter 3:** a place that is reached by going up, not along the road (a shuttle, or the Guild's crawler to a
  lift). The speakers' network already crosses the Reach.
- **Chapter 4:** more than one planet. Either one world with several planets as top-level places, or several worlds
  joined so bodies, items and speaker calls can cross between them. That is an engine decision, and the engine
  session owns it.
- **Chapter 5:** a thousand players and five thousand NPCs is a hosting question as much as a world one: the minds'
  cost, the tick, and one world against many (the hosting conversation with the engine session).
- **Every chapter:** places sized for the players it brings, and an introducer for every new place and thing.
