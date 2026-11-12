# ferry-at-dusk-3, the Traveler as a mind (2026-11-08)

A Claude Code subagent played the Traveler through the CLI (principal `traveler`), bounded to 14 acts. It used 6, closed two of its four goals and left. Hob was Nate's seat (not yet moved), so Hob's silence below is expected, not a bug. Written by the maintainer from the mind's report; the play session's own notes are in ferry-at-dusk-3-2026-11-08.md.

## What worked

- Journal and goals drove it: it read `memory` and `goals`, called `recall` on Tam and Mara before dealing with them, crossed back with Tam on the raft (raft, Tam, Biscuit and the Traveler all moved to the Landing), walked to the square, told Mara the story, raised the jugs with Hob, asked about the dog.
- It wrote a `remember` after every beat and moved goals to `done` or changed their `why`. g1 (cross back) and g2 (pay the story) closed; g3 (jugs) and g4 (Biscuit) stayed active with new whys.
- Hob's walk behavior brought him into the square on his own, right as the Traveler arrived, saying "Tam owes me for three jugs." Good accident.

## Engine

- The CLI `say` has no `--to`; only `--reach <int>`. Every line the mind spoke went to the room, so nothing was ever addressed to Mara or Hob and a mind listening for a `say` addressed to it would hear none. Add `--to <name>` to the CLI (the op has it).
- `op --json-args` on the shell breaks on an apostrophe inside single quotes ("Tam's"). A `--text` shortcut for `remember` and `intend`, or reading args from stdin, would spare minds that dance.

## World

- Mara does not recognise the story as payment. Her line promises "the three I promised are waiting" on a story, but `talk` about the story returns her default line and `talk drink` says "One was the deal." Give her a `story|tale|owe` topic that sets a fact (`story_paid`) and hands over the ales, or drop the promise line.
- The jugs have nothing behind them: no coin, no `pay` or `work` verb, nothing to `give`. Settling g3 needs a thing (coin, barley, mended rope) or a verb that counts as settlement, plus a Hob topic that accepts it.
- Biscuit has no home to go to. Both dog topics say the same "follows anyone with a bone." g4 needs a person who takes the dog (a feed topic that sets `friend`, or a `takes_dog` behavior) or the goal is unreachable.
- Tam says nothing on the raft or at the Landing; the return crossing is one log line. One line after a crossing would land.
- Litter: the quarter mug of Dark ale left on the ground in the square from game 2 reads as trash. Promote (Mara clears it) or let the author destroy it.

## Hob with a mind or a table

- When Hob is embodied the table stops answering by design (`unless_embodied`). While Nate is away from his seat, two direct appeals and three waits (50 s) got nothing. Worth deciding: when the embodying principal has not acted for N seconds, does the table answer again, or does the narrator hold the mind's lines until the seat is back?
