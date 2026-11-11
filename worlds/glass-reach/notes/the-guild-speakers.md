# The Guild's speakers and its reckoner: a design note, not built

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

Open for Nate: build it (when, before or after the moon), and whether a shard a call is the right price.
