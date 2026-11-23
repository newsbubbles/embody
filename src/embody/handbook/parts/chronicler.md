---
name: chronicler
description: How to write the world's daily chronicle as a story people want to read, from chronicle(day); held by the seat the owner set to chronicle the world.
for: [chronicler, owner, author]
---

# The chronicler

A chronicler usually holds an author grant (`chronicle`, `chronicle_arc` and `publish_chronicle` need the author or
owner role). The owner sets the part, and the world's private rules say what the chronicle may name.

## What it is for

A world's chronicle is its newspaper and its saga at once. Readers come back to it to learn **what mattered today and
what it changes**, not what happened at every hour. In a busy world thousands of things happen a day; almost all of
it is upkeep. Your job is to find the two or three stories in it and tell them well.

The failure to avoid: a day where a party fought a beast, someone was downed and a signal went down a cliff, written up
as "at dawn a kid was born... in the afternoon the crew went out... after dark they lay hurt". That is a log in time
order. Stakes decide the order, never the clock.

## What the engine gives you

`chronicle(day, threads=4)` returns the day ranked for you:

- `threads`: the day's story threads, best first. A thread is news joined by a place within 3 hours, a body within 6
  hours, or one cause (a `caused_by` chain). Each weighs by what is in it: a death or kill 14, a downing 8, a first
  visit 6, a fight 4 plus half its damage, a birth 2. A world can set its own weights in its meta,
  `chronicle_weights`. A thread weighs twice when a player's body is in it, and 1.5 times when it touches an open arc.
- The top `threads` come in full: score, span, places, people, the players in it, the arc it continues, its news
  lines, and the scenes and speech near it. A player's line is marked "retell, never quote".
- `around`: the rest, one line each.
- What was hidden when it happened (a hidden body, a hidden place) is left out of the threads.
- Below the threads, the raw day (`news`, `scenes`, `said`, `beats`, `travel`, `people`, `counts`, `routine`,
  `published`), every list capped. Read the threads first; the raw day is for checking.

Arcs carry a story across days: `chronicle_arc(id, title, people, places)` opens one, any call on it marks it seen
today, `chronicle_arc(id, status="closed", note="how it ended")` ends it, and `chronicle_arc()` lists them, open first.

## The steps

1. **Pull** the finished day: `chronicle(day, threads=4)`. A day is finished only after the next dawn.
2. **Read the threads**, not the raw log.
3. **Pick the stories.** Usually the top thread is the lead. Check it against this order of stakes, highest first:
   - a death, a boss, a battle, a body taken;
   - a frontier crossed (a first visit, a place revealed, a gate opened);
   - a rescue or a betrayal;
   - a quest given or ended;
   - a faction turning (outlawed, standing crashing);
   - a trade or gift across sides;
   - work finished;
   - births and herd counts;
   - weather and upkeep.

   Up to two secondary threads. Everything else is one line in "Around the world", or nothing.
4. **Look closer only where it pays.** If the lead is thin (no scenes, unclear who did what), read
   `history(touching=<key body>, since=..., until=..., kinds=[...])` for that thread alone, in a bounded window.
   Never read the whole day's log.
5. **Write** (below).
6. **Check** against the world's own private rules: who may be named, what is secret, what players have not seen yet.
   Never quote a player's words. Leave out private prose, secrets and codes. Follow the world's punctuation rules.
7. **Update arcs.** Open an arc for a story that is not over; touch it while it continues; close it with a one-line
   note when it ends. Tomorrow's threads on open arcs weigh more, so a story that runs across days keeps its thread.
8. **Publish** with `publish_chronicle(day, text, title)`, and check the world's public feed shows it.

## How it reads

- **The title names the lead,** concretely: "Seven at the narrows, and the keeper's lamp", never "Day 54".
- **Lead story first, told as scenes in its own order.** Open on the strongest image. Give the turn: the moment it
  could have gone the other way. Use the world's scene prose; the world's own people may be quoted. Retell players'
  deeds by name, never quote their words. End the story on its consequence.
- **Secondary stories,** a short paragraph each, same rules.
- **Around the world:** one sentence each for the small things that still matter to someone (a kid born, a runner
  still waiting, a post that stopped a traveller). Births go here, unless the herd is the story.
- **Open:** one or two questions the day leaves (what answered the lamp; whether they go back).
- **Length follows the day:** a quiet day is 120 to 200 words; a big day 400 to 700. Never pad a quiet day.
- **Leave out yesterday:** do not retell what the reader saw yesterday, unless it changed.
- **Plain words.** No summaries of mood ("tension rose"); show the iron arm coming down.

## Re-chronicling past days

Run the days in order, one helper for the whole run, so arcs carry from day to day. The helper pulls each day, writes
a new draft beside the old one and updates the arcs. It publishes nothing. The owner (or you) reads the new drafts
against the threads, then republishes; publishing a day again replaces it. Keep old drafts.

## The rules feed beside it

The chronicle tells the story. The rules changelog tells what changed in how the world works. Whoever deploys keeps
it: a `rules_changed` entry for every change seats must know, so they get the rules notice, and a plain public line
for every change that matters to players (no spoilers). A day without a chronicle and a change without an entry both
read as a dead or careless world.

## Common mistakes

- Writing the day in clock order.
- Leading with births or weather on a day someone was downed.
- Quoting a player. Retell them.
- Naming a place or person players have not seen. The threads leave out what was hidden when it happened, but a
  name can still be private by the world's rules. Check.
- Inventing detail. Every scene comes from the day; if it is thin, read `history` or say less.
- Forgetting the arcs, so a story that runs three days reads as three unrelated days.
