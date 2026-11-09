# Glass Reach, narrator notes, 2026-11-09

Player: Nate, on his phone over Remote Control. Seat: Reeve Ansel Varrick (principal `nate-gr`). Narrator peeks as author with principal `narrator-gr` (read only: inspect, timers).

## Setup

- This narrator session had no `embody` MCP tools (the session started in D:\, not D:\embody), so play runs through the CLI: `uv run embody --as nate-gr --world glass-reach ...`. Works, but slower per turn.
- Narrator slip at t=0: I ran `act read` on the Crown's writ while gathering the opening, before Nate spoke. One turn passed (3 s). Harmless, but it was a deed he did not choose.

## What felt off

- The brief for the opening says Captain Ruhl is "around", but at t=0 Ruhl stands in the Gate Yard, not in the Hold. Dram Hollis is in the Hold with the reeve. Narrated as it is: Ruhl's voice from the yard, Dram in the room.
- Ruhl's `state.brief` is empty (None); the knows-edge notes carry his voice instead.

- `uv run embody` fails while another process holds `.venv/Scripts/embody.exe` (uv tries to resync and cannot remove the exe). `uv run --no-sync embody` works. Worth a line for narrators on the CLI.
- Mid-play the maintainer moved this file from `worlds/notes/` to `worlds/glass-reach/notes/` (repo restructure). Notes continue here.

## What he wanted that the world could not do

- t=6: "go to the yard to talk to Ruhl about water" is two deeds (go, then talk). Kept to one act per turn: walked him to the yard and stopped with Ruhl waiting. On a phone this costs him an extra message for one intent. Maybe allow a chained stated intent (go, then talk on arrival) when the second deed only follows the first.
