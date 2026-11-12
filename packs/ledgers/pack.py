"""Ledgers: a thing people carry that keeps accounts nobody else reads. Packs/ledgers/README.md is the guide; this is
the reference.

A world names it in its manifest (`"requires": ["ledgers"]`); the pack defines the `ledger` schema (a device: a slate,
a book, a count-cord) and `ledger_relay`, and their verbs, so a world binds nothing on its people. A world's own look
for a device extends `ledger` and sets its state.

A device holds one or more named ledgers. Nothing written in one is ever erased: `void` writes a correcting entry that
points at the one it cancels, with a reason. An entry: `n` (its number on this device), `t` (world seconds) and `when`
(day and hour), `ledger`, `kind` (in, out, count, note; void for a correction), `item`, `qty`, `unit`, `party`, `place`,
`text`, `tags`, `author`, `source` (by hand, recorded from event N, copied from device X entry N), and on a voided one
`voided_by`.

Privacy. Entries live on pages of twenty (`ledger_page`, hidden, their `entries` secret) kept in one hidden `ledger_archive`
under the root, and the device keeps their ids in its secret `book`; so no card, room view, feed, chronicle or other
body's view shows them, and the device itself stays small however long its book. The owner and authors read them in
full (inspect a page). Only the holder's own verb returns them. Every verb needs the device in your hands (a fixed one, `portable: False`, may be read from
alongside, never written). The room hears one short line the world sets: `lines` {verb: text, "default": text} with
{who} and {device}, False to say nothing (default "{who} bends over {device}.").

Verbs, done to the device (all but `ledgers` take the filters below to choose entries):
- `ledgers`: the ledgers on it with their counts. params `open` (a name) starts a new one.
- `record`: a hand entry. params `kind`, `item`, `qty`, `unit`, `party`, `place` (default where you stand), `text`,
  `tags` (a list or "a, b"), `ledger` (default `default_ledger`, "tally").
- `void`: params `n` (the entry) and `reason`. A void and a voided entry cannot be voided again.
- `read`: a page of entries. params `page` (1 first, -1 the last), `size` (default `page_size` 10, at most 50), `sort`
  (time, amount, party, item, number) and `order` (desc, the default: newest first; asc).
- `search`: the filters, with the same sort and paging; always reports how many matched.
- `total`: the filtered entries summed, `by` item (default), party, ledger, kind, unit or all: per group the count of
  entries, the in and out sums, net, the running balance (in adds, out takes away, a count sets it), and min, max,
  mean, mode and standard deviation of the quantities. Voided entries are left out unless `voided` says otherwise.
- `verify`: the chosen entries against the world's log. Recorded entries are confirmed, or flagged with why; a hand
  entry is "unverifiable, by hand"; a copy is checked through the deed it came from.
- `copy`: write the chosen entries as lines onto a paper in your hands (a thing with `text`, the Reach's leaves):
  params `onto`. Thirty lines at a time.
- `transfer`: copy the chosen entries onto another device in reach (in your hands, lying here, or held by someone
  here): params `to`, `into` (a ledger there; default the entry's own). The copies are marked, with where they came
  from, and the source keeps its own.
- `send`: the same, to a contact's device far off: params `to` (a line from `contacts`).
- `contacts`: this device's line and the lines it knows. params `add`, `drop` (a line).

Filters (params): `ledger` (a name, or all), `text` (in the text, item, party or tags), `party`, `item`, `place`,
`kind` (one or a list), `tag`, `since` and `until` (world seconds), `day`, `min` and `max` (quantity), `source` (hand,
recorded, copied), `voided` (include, the default for read and search; exclude, the default for total; only), and
`entries` (a list of numbers).

State a world sets: `default_ledger` ("tally"), `records`, `keeper`, `cap` (entries a device holds; None is no limit),
`page_size`, `lines`, `line` (its address for `send`), `contacts` (lines it already knows), `delivery` ("face": both
devices in one place; "relay": anywhere, through `relay`; "none": it cannot send), `relay` (the name or id of a
`ledger_relay`), `day_seconds` (for `when`; else the root's, else 86400).

Recording on its own: `records` names the deeds of its holder the device writes down by itself, into the default
ledger: a list of event kinds (["given", "taken"]), or {kind: spec} where a spec says what the entry is for each side,
{"doer": "out", "other": "in", "ledger": ..., "unit": ..., "text": ...}. A side left out is not recorded. Known
kinds: given (doer out, other in), taken (doer in, other out), put and dropped (doer out); any other kind is a note
for both sides. The doer is the payload's `by`, else its `who`, else the actor; the other side is the target, else
the payload's `to` or `source`. The device must be in its holder's hands (a child of the body); the engine's `holder`
listeners carry it (docs/SCRIPTING.md). A full device skips the entry and counts it in `missed`.

Binding: `keeper` (a name or id) binds a device to one body. Anyone else gets "locked". A lock (the locks pack)
spawned inside the device is the binding's lock: while it is locked only the keeper uses the device; picked, broken
or unlocked, anyone may. A bound device with no lock in it cannot be opened by anyone else at all.

A relay (`ledger_relay`, fixed) carries what devices with `delivery: "relay"` send, at once and wherever they are. It
writes one note in its own "relay" ledger for each sending: from, to, when and how many, never what. When its state
says `down`, nothing goes through.

Events: `ledger_received` on the receiving device (reach 1, so only its holder sees it), {from, count, by}; it is
chronicle-quiet. A world's own verb writes through `write_entry(ctx, device, fields)` in scripts/_ledgers.py
(`use("ledgers")`), so its entries are numbered, capped and private like the rest.
"""

PACK = {"name": "ledgers", "description": "Ledgers people carry: accounts kept by hand or on their own, read only by "
                                          "whoever holds them, copied, sent, verified against the log."}

_READ = {"page": "1 is the first page, -1 the last", "size": "entries a page (10; at most 50)",
         "sort": "time, amount, party, item or number", "order": "desc (newest first) or asc"}
_FILTERS = {"ledger": "a ledger's name, or all", "text": "words in the text, item, party or tags", "party": "who",
            "item": "what", "kind": "in, out, count, note or void (or a list)", "tag": "a tag",
            "since": "world seconds", "until": "world seconds", "day": "a day number", "min": "least quantity",
            "max": "most quantity", "source": "hand, recorded or copied", "voided": "include, exclude or only",
            "entries": "a list of entry numbers", "place": "where it was written"}


BIG = 600_000  # a verb that walks the whole book: about five thousand entries (the engine's `fuel` on an action)


def define(s):
    """The device, the relay, and the archive their pages are kept in. Idempotent."""
    acts = {
        "ledgers": {"script": "ledger", "fuel": BIG, "doc": "The ledgers on it and how many entries each holds; open a new one",
                    "params": {"open": "a new ledger's name"}},
        "record": {"script": "ledger", "doc": "Write an entry by hand", "duration": 5,
                   "params": {"kind": "in, out, count or note", "item": "what", "qty": "how many", "unit": "of what measure",
                              "party": "who with", "text": "the words", "tags": "a list, or words with commas",
                              "ledger": "which ledger (its default if left out)", "place": "where (here if left out)"}},
        "void": {"script": "ledger", "fuel": BIG, "doc": "Cancel an entry with a correcting one; nothing is erased", "duration": 5,
                 "params": {"n": "the entry's number", "reason": "why"}},
        "read": {"script": "ledger", "fuel": BIG, "doc": "Read a page of it, newest first", "params": dict(_READ, ledger="a ledger, or all")},
        "search": {"script": "ledger", "fuel": BIG, "doc": "Find entries: any mix of filters, sorted and paged, with how many matched",
                   "params": dict(_FILTERS, **_READ)},
        "total": {"script": "ledger", "fuel": BIG, "doc": "Sum the entries a filter picks, grouped: counts, sums, balance and the "
                                             "spread of the amounts",
                  "params": dict(_FILTERS, by="item, party, ledger, kind, unit or all")},
        "verify": {"script": "ledger", "fuel": BIG, "doc": "Check entries against what happened", "duration": 10,
                   "params": dict(_FILTERS)},
        "copy": {"script": "ledger", "fuel": BIG, "doc": "Write entries out onto a paper in your hands", "duration": 60,
                 "params": dict(_FILTERS, onto="the paper")},
        "transfer": {"script": "ledger", "fuel": BIG, "doc": "Copy entries onto another device here", "duration": 10,
                     "params": dict(_FILTERS, to="the other device", into="a ledger there")},
        "send": {"script": "ledger", "fuel": BIG, "doc": "Send entries to a contact's device", "duration": 5,
                 "params": dict(_FILTERS, to="a line it knows (contacts)", into="a ledger there")},
        "contacts": {"script": "ledger", "doc": "Its own line and the lines it knows; learn or forget one",
                     "params": {"add": "a line to learn", "drop": "a line to forget"}},
    }
    s.define_schema("ledger", extends="thing",
                    doc="A device that keeps ledgers: only its holder reads it (packs/ledgers/pack.py).",
                    state={"portable": True, "bulk": 0, "default_ledger": "tally", "ledgers": {}, "book": [],
                           "archive": None, "written": 0, "missed": 0, "voided": {}, "records": [], "keeper": None, "cap": None, "page_size": 10,
                           "delivery": "face", "relay": None, "line": None, "contacts": [], "lines": {},
                           "secret": ["ledgers", "book", "archive", "written", "missed", "voided", "records", "contacts", "relay",
                                      "lines"],
                           "description": "A ledger."},
                    actions=acts,
                    listeners=[{"script": "ledger_hear", "holder": True}])
    s.define_schema("ledger_relay", extends="ledger",
                    doc="A fixed relay that carries what devices send, and logs who sent to whom, never what.",
                    state={"portable": False, "delivery": "relay", "default_ledger": "relay", "down": False,
                           "description": "A relay."})
    s.define_schema("ledger_page", extends="thing", doc="Twenty entries of one device's book, kept in the archive.",
                    state={"hidden": True, "portable": False, "device": None, "entries": [], "secret": ["entries"],
                           "description": "A page of a ledger."})
    s.define_schema("ledger_archive", extends="thing", doc="Where the world's ledger pages are kept. Nobody walks in.",
                    state={"hidden": True, "portable": False, "description": "The ledger archive."})
