# The Guild's speakers and its reckoner

2026-11-11, from Nate's side conversation. The Carriers' Guild is the Reach's Spacing Guild: it carries for whoever
holds the gate and takes no side, and it would have tools nobody else has. In embody an object's verbs are tools its
holder gains, so a device is a capability the world itself gates: who holds it, where it is, whether it is locked,
whether someone took it. Hauler Nine (`drive`), the locks (`pick`, `break`) and a stolen plan (`build`) already work
this way.

## The speaker

A palm-sized slab of dark glass with a Guild seal cut in its back. When it is woken, a hologram stands up out of it:
small, the colour of the ember that powers it, flickering at the edges.

Verbs, all on the speaker in hand:

- `call` (to: a speaker, or a name in the contacts; words; `seen`): a live line to whoever holds that speaker,
  wherever they are. What is said comes through, and `seen` is what the caller's hologram shows on the far end: the
  caller writes it ("a lean woman in a Guild coat, the Landing's tally post behind her, worried"). The receiving
  holder's feed gets the words and the picture, and the room around them sees a hologram talking.
- `send` (to; words; `seen`): the same, stored. It waits on the far speaker until someone reads it.
- `read`: the messages stored on this speaker, each with its picture, oldest first, then cleared or kept.
- `contacts`: the speakers this one knows, by the names their holders gave them. An address book, so an agent does
  not have to remember who holds which slab.

What the network says truly and what it does not: every call and message carries the speaker it came from, and the
far end shows that truthfully ("from the Landing's speaker"). The picture and the words are the caller's own claim. A
hologram can lie with its face but never with its source; a stolen speaker calls as the speaker it is, so whoever
holds the Landing's slab can sound like Ossa only until someone asks the right question.

Forwarding: `send` can carry on a message read on this speaker, picture and all, marked as forwarded from where it
first came.

## Keeping it scarce

The Reach's tension is distance: Wick runs, the Keth carry at dusk, a word takes a night to cross the Flats. A speaker
in every hand ends that. So:

- There are few, and they are the Guild's: the Landing (Ossa), the wardens' post (Marr), the Old Salt Works (the
  Guild's agent there, or none), the Guild Yard, and the Master up the road, who is a voice on a speaker and nothing
  else for now.
- They run on emberglass. A call spends a shard; a sent message a shard per three. A speaker holds a few shards
  (`put` them in). That gives shards a use besides sitting in a strongbox, and the Guild's sixty shards a reason.
- Hold one that is not yours and the Guild will want it back. Ossa knows each speaker by its seal.

## The reckoner (a mentat)

A Guild reckoner rides the crawler from the Master up the road and sits at the Landing: a person whose verb answers
from the world's true state. `consult` (question, paid in shards) for a few fixed questions, computed exactly:

- how the moon leans: the numbers the reckoning will use, men on the wall, water, the riders, today;
- what the Hold holds in water, and for how many days at its count;
- where the convoy's water is promised, and to whom.

The reckoner works for the Guild, which sells to everyone; a house can buy the same answer as its enemy. A reckoner of
another house (Dreyer's clerk was one, before he yielded) could answer true but short, by its own rule.

## How it would be built

A small pack (`relay`) or Reach scripts: a `speaker` schema with the four verbs, `seen` a parameter of `call` and
`send`, the network as state on the speakers (no engine change: a script can already put words in a holder's feed in
another place), the shard charge, and `consult` on the reckoner. No language model in the engine: the hologram shows
what a person wrote, and the reckoner's answers are templates over the world's numbers.

Introduced like everything else: Ossa holds the Landing's speaker and explains it, Marr keeps the post's, the wright
knows how they are made, and the Hold has heard of them and never held one.

## Built (2026-11-11)

Nate: build it, after the moon, with the High Landing in people's memories and Dreyer scheming toward the Guild's
arrival. Scripts: `speaker.py` (the five verbs and the primer), `reckoner_consult.py` (the `consult` verb on the person
schema), `reach_speakers.py` (the arrival and the naming); the lore in build.py, `keep_high_landing`.

- **The High Landing**: the Guild's platform in orbit, fifty kilometres keel to tip and twenty across the wide deck,
  seen from the ground as the slow star before dawn. Emberglass goes up to it on the lifters at the Master's station.
  Ossa, Marr (served aboard), Garran (born aboard), Mira (a reckoner sister), Dov, Pell, Quill, the wright (trained in
  its crystal shops), Taan (the Keth's Glass Eater) and Ruhl remember it. Chapter three or four opens it.
- **A day after the moon** the crawler brings Factor Ivo Senn and Reckoner Aurel Quist to the Landing with five slabs:
  the Landing's (Ossa), the wardens' post's (Marr), the Guild Yard's (the wright, or Mira Ost), the factor's, and Scar
  Gate's, which Senn carries.
- **Things explain themselves**: a slab that comes into new hands (the Guild's hand-over, a give, a take) wakes once for
  that holder with the Guild's primer: what it is, how it works, what it costs, whose it is. Every holder remembers it,
  and Senn's brief tells him to explain it to anyone he gives one.
- **Two days after he comes** Senn names the gate's holder on the Guild's tally: the house the moon left at the gate,
  unless the other house put more glass in his hand, ten shards at least. The gate's slab goes to that house's head.
  Halvard knows this from house letters and has it as a goal: the riders' paychest or the buried vein, into Senn's hand.
  The story keeps `guild_recognizes` and `guild_bought` for the next chapter.
