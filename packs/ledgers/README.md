# Ledgers

A pack for devices people carry that keep accounts: a Guild tally-slate, a house slate, a Keth count-cord, a clerk's
book. Only the one who holds a device reads it. It can keep its holder's deals by itself, and its entries can be copied
onto paper, handed to another device face to face, or sent to one far away.

`pack.py` is the full reference: every state key, verb, param and event. This file is the guide.

## Start

Name the pack in the world's manifest, give the device a look of its own, and put one in someone's hands:

```python
WORLD = {"id": "...", "requires": ["village", "ledgers"]}

def define(s):
    s.define_schema("tally_slate", extends="ledger", doc="A Guild tally-slate.",
                    state={"records": ["given", "taken"], "default_ledger": "tally",
                           "lines": {"default": "{who} checks {device}.", "read": "{who} thumbs down {device}."}})

def populate(s):
    ruhl = s.spawn("person", yard, "Ruhl")["id"]
    s.spawn("tally_slate", ruhl, "Tally Slate", state={"keeper": "Ruhl", "line": "guild-ruhl"})
```

The verbs come with the schema. A world binds nothing on its people.

## What the holder does

All verbs are done to the device, with the device in your hands.

| verb | what it does | params |
|---|---|---|
| `ledgers` | the ledgers on it and their counts | `open`: a new ledger's name |
| `record` | writes an entry by hand | `kind` (in, out, count, note), `item`, `qty`, `unit`, `party`, `text`, `tags`, `ledger`, `place` |
| `void` | cancels an entry with a correcting entry | `n`, `reason` |
| `read` | one page, newest first | `page` (-1 is the last), `size`, `sort`, `order`, `ledger` |
| `search` | the entries the filters choose, sorted and paged, with how many matched | filters, `sort`, `order`, `page`, `size` |
| `total` | sums over a filter, grouped | filters, `by` (item, party, ledger, kind, unit, all) |
| `verify` | checks entries against what happened | filters |
| `copy` | writes entries as lines onto a paper in your hands | filters, `onto` |
| `transfer` | copies entries onto another device in reach | filters, `to`, `into` |
| `send` | copies entries onto a contact's device | filters, `to` (a line), `into` |
| `contacts` | its own line and the lines it knows | `add`, `drop` |

The filters are `ledger`, `text`, `party`, `item`, `place`, `kind`, `tag`, `since`, `until`, `day`, `min`, `max`,
`source` (hand, recorded, copied), `voided` (include, exclude, only) and `entries` (a list of numbers). Any mix works.
A filter that is not a usable value is refused with what it takes, so a typo does not read as "everything".

Nothing is ever erased. `void` writes a new entry that points at the one it cancels, and the cancelled entry shows
`voided_by`. `total`, `transfer` and `send` leave voided entries out unless `voided` says otherwise; `read`, `search`
and `copy` show them.

`total` gives each group its count of entries, the in and out sums, net, the running balance (in adds, out takes away,
a count sets it), and the min, max, mean, mode and standard deviation of the quantities. An agent sees the shape of the
book without more calls.

## Recording on its own

`records` names the deeds of its holder that the device writes down by itself, into its default ledger:

- a list of event kinds: `["given", "taken"]`;
- or a dict, for the entry each side gets: `{"paid": {"doer": "out", "other": "in", "unit": "shards"}}`.

The pack knows `given` (the giver writes out, the receiver writes in), `taken` (in for the taker), `put` and `dropped`
(out). Any other kind is a note for both sides unless the dict says otherwise. The entry takes its item and count from
the event's payload (`item`, `count`), its party from the other side (a body, or the place the thing was taken from),
and its source names the event, so `verify` can confirm it.

This works through the engine's `holder` listener (docs/SCRIPTING.md): a device hears the events its holder does or
has done to them, wherever that happens. The device must be a child of the holder. A full device (see `cap`) writes
nothing and counts what it missed in `missed`.

## Privacy

Entries live on hidden pages in one hidden archive under the world's root. The device keeps the pages' ids in its
secret state. So:

- no card, room view, feed, chronicle or other body's view shows an entry;
- another body cannot read a device in someone else's hands, and gets "locked" when it holds one bound to someone else;
- the room hears one short line the world sets (`lines`), or nothing when the line is `False`;
- what a holder asks (the params) and what comes back reach only the holder;
- the owner and authors see everything: inspect a page from the device's `book`.

A fixed device (`portable: False`, a relay) can be read from alongside, never written by hand. The room sees that a
verb was done to it.

## Binding and locks

`keeper` (a name or an id) binds a device to one body. Anyone else gets "locked". To let a thief break in with skill
and time, spawn a lock (the locks pack) inside the device: while the lock is locked only the keeper uses the device,
and once it is picked, broken or unlocked anyone may. A bound device with no lock in it opens to nobody else.

## Sending

Each device has a `line` (its address), a list of `contacts` (lines it knows) and a `delivery`:

- `face`: both devices must be in the same place;
- `relay`: anywhere at once, through the `ledger_relay` named in `relay`, if both devices are on the relay. The relay
  writes one note in its own "relay" ledger for each sending: from, to, when and how many, never what. A relay whose
  state says `down` (or `broken`) carries nothing;
- `none`: it cannot send. Carry it and `transfer` face to face.

`transfer` needs no line: any device in reach (in your hands, lying here, or held by someone here) takes copies.
Copies are marked with the device and entry they came from, and their first source is kept, so `verify` checks a copy
of a recorded entry against the deed it came from. The receiving holder sees a `ledger_received` event (from, count).

## A world's own verbs

A world's verb that writes into a device (a scan that reads counts off a store) uses the pack's code:

```python
use("ledgers")

def apply(ctx):
    dev = ...
    got = write_entry(ctx, dev, {"kind": "count", "item": "Water", "qty": 40, "unit": "casks",
                                 "source": {"event": ctx.event.seq, "kind": "act"}})
    if isinstance(got, str):
        ctx.reject(got)  # the device is full
```

`write_entries(ctx, dev, [fields, ...])` writes many in one go. A `source` with an `event` makes the entry checkable;
without one it reads as by hand.

## Limits

- A verb that walks the whole book asks the engine for 600k fuel: about five thousand entries for `total`, and more
  for `read` and `search`. `cap` limits the entries a device holds; past it, `record` is refused and recording stops.
- `copy` writes thirty lines at a time. `transfer` and `send` move two hundred entries at a time.
- Entries are kept in world time; `when` shows the day and hour by the device's `day_seconds`, else the root's, else
  86400.
