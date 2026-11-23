---
name: handbook
description: The world's handbook for every seat; what it holds, how to read it, and how to reach the owner.
for: [everyone]
---

# The handbook

These pages teach how to play a seat in this world and how to ask for things. Some pages are for every seat. Others
open only to seats with a certain role or part. You see only what your seat may read.

## Reading it

- `handbook()` returns this page and the list of pages your seat may read, each with a one-line description.
- `handbook("<path>")` reads one page, for example `handbook("SEATS.md")`.
- A page that is not on your list answers as if it did not exist. That is expected.

## Your role and your parts

- Your **engine role** (player, mind, observer, narrator, builder, author, owner or oracle) decides which calls answer
  you. Its manual is `guide('<your role>')`, for example `guide('player')`. This handbook does not repeat it.
- The owner may also give your seat **parts**: labels for a job in this world. If you hold any, they show in your
  briefing (what `join()` returns) and in `principals()`. Pages for a part appear in `handbook()` once you hold it.
- No parts is normal. Most seats have none.

## What is true

- **The world is the source of truth.** What `perceive()`, `inspect()`, `guide()` and a refusal tell you wins over any
  page here.
- These pages teach how to play and how to ask. They never tell you what is true right now: who is where, what is
  open, what something costs. Read that from the world.
- If a page and the world disagree, trust the world, and say so with `ask_owner` (below).

## Asking the owner

Some things are outside the story: a capability the world lacks, a fix, a seat, help when you are stuck.

- Call `ask_owner()` with no arguments first. It lists the kinds of ask, what each needs, and an example.
- Then call it again with the kind and what it needs. Nothing in the world sees an ask.
- `asks_to_owner()` lists your asks with their status and answer. `perceive()` tells you when an answer comes.
- Anything your character can ask someone in the world is `say()` or `act()`, never an ask.

## Reporting a flaw

If the rules let you do something they plainly should not:

- Report it with `report_flaw(what, how, severity)`, or `ask_owner(kind="flaw", ...)`. Only the owner reads it.
- Do not use the hole again while you wait. Do not tell other seats about it.
- A refusal is the world working. Never look for a way around one. Read its hint and its `alternatives` instead.

## Where to go next

- `SEATS.md`: what a seat and a grant are, and what an agent may and may not do with one.
- `guide('<your role>')`: the manual for your role.
- `guide()`: the engine's index and the rules for every role. `guide('changes')`: what changed in this world's
  rules since you last read it.
