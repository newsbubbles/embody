"""Ledgers: the verbs, filters, sorting and paging, the totals and their spread, verify against the log, privacy
against other bodies, binding with a lock, both deliveries, recording on its own, and the book across a reboot."""

import json
import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "books", "name": "The books", "seed": 7, "description": "A yard, a far house, and what people write down.",
         "requires": ["village", "locks", "ledgers"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here",
                                      "params": {"count": "how many of a stack"}},
                             "give": {"script": "give", "doc": "Hand over", "targets": "creature", "scope": "here",
                                      "params": {"item": "what", "count": "how many"}},
                             "go": {"script": "go", "doc": "Walk", "targets": "place"}})
    s.define_schema("slate", extends="ledger", doc="A Guild tally-slate.",
                    state={"records": ["given", "taken"], "delivery": "relay", "relay": "Relay",
                           "lines": {"default": "{who} checks {device}.", "copy": False}})

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    far = s.spawn("place", root, "Far House")["id"]
    s.connect(yard, far)
    ruhl = s.spawn("person", yard, "Ruhl")["id"]
    bel = s.spawn("person", yard, "Bel")["id"]
    cy = s.spawn("person", far, "Cy")["id"]
    slate = s.spawn("slate", ruhl, "Tally Slate", state={"keeper": "Ruhl", "line": "guild-1", "contacts": ["house-1"]})["id"]
    s.spawn("lock", slate, "Slate Lock", state={"code": "1234", "break_dc": 1})
    s.spawn("ledger", bel, "Count Cord", state={"line": "cord-1", "contacts": ["guild-1"]})
    s.spawn("slate", cy, "House Slate", state={"line": "house-1", "records": []})
    s.spawn("ledger_relay", far, "Relay")
    s.spawn("thing", ruhl, "Leaf", state={"portable": True, "text": "", "bulk": 0})
    s.spawn("thing", ruhl, "Water", state={"portable": True, "count": 10, "bulk": 0})
    s.spawn("thing", yard, "Emberglass", state={"portable": True, "count": 30, "bulk": 0})
    s.clock(run=False)
'''


def world(tmp_path, db=None):
    ws = tmp_path / "ws"
    if not ws.exists():
        for p in ("village", "locks", "ledgers"):
            shutil.copytree(REPO / "packs" / p, ws / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (ws / "worlds" / "books").mkdir(parents=True)
        (ws / "worlds" / "books" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(str(db) if db else None, workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "books")
    return eng, gm


def seat(eng, who):
    s = eng.session(who.lower())
    s.join("books", who)
    return s


def state(gm, name):
    return gm.world.get(gm.inspect(name)["id"])["state"]


def rec(s, **p):
    return s.act("record", "Tally Slate", params=p)["result"]["written"]


def fill(gm, ruhl):
    # a morning's work: water out to three parties, glass in, a count, a note; an hour apart
    rows = [("out", "Water", 4, "Bel"), ("out", "Water", 2, "Cy"), ("in", "Emberglass", 10, "Keth"),
            ("out", "Water", 4, "Keth"), ("count", "Water", 30, None), ("in", "Emberglass", 6, "Bel"),
            ("note", None, None, "Bel")]
    for kind, item, qty, party in rows:
        p = {"kind": kind, "text": "the " + kind}
        if item:
            p["item"] = item
        if qty is not None:
            p["qty"] = qty
        if party:
            p["party"] = party
        rec(ruhl, **p)
        gm.world.step(3600)


def test_record_read_search_sort_and_page(tmp_path):
    eng, gm = world(tmp_path)
    ruhl = seat(eng, "Ruhl")
    fill(gm, ruhl)
    r = ruhl.act("read", "Tally Slate", params={"size": 3})["result"]
    assert (r["matched"], r["pages"], r["page"]) == (7, 3, 1)
    assert [e["n"] for e in r["entries"]] == [7, 6, 5]  # newest first
    assert r["next"] == "page 2 of 3" and r["ledgers"] == ["tally"]
    assert r["entries"][1]["when"] == "day 1, 05:00" and r["entries"][1]["source"] == "by hand"
    last = ruhl.act("read", "Tally Slate", params={"size": 3, "page": -1})["result"]
    assert [e["n"] for e in last["entries"]] == [1] and "next" not in last
    asc = ruhl.act("read", "Tally Slate", params={"sort": "amount", "order": "asc", "size": 10})["result"]
    assert [e.get("qty") for e in asc["entries"]] == [None, 2, 4, 4, 6, 10, 30]
    s = ruhl.act("search", "Tally Slate", params={"party": "bel", "kind": "out, in"})["result"]
    assert sorted(e["n"] for e in s["entries"]) == [1, 6] and s["matched"] == 2
    s = ruhl.act("search", "Tally Slate", params={"min": 4, "max": 6, "item": "water"})["result"]
    assert sorted(e["n"] for e in s["entries"]) == [1, 4]
    s = ruhl.act("search", "Tally Slate", params={"text": "the note"})["result"]
    assert [e["n"] for e in s["entries"]] == [7]
    s = ruhl.act("search", "Tally Slate", params={"since": 3600 * 2, "until": 3600 * 4, "sort": "party", "order": "asc"})["result"]
    assert [e["n"] for e in s["entries"]] == [5, 3, 4]  # no party sorts first, then Keth by number
    with pytest.raises(Rejected, match="kind is one of"):
        ruhl.act("search", "Tally Slate", params={"kind": "inn"})
    with pytest.raises(Rejected, match="min takes a number"):
        ruhl.act("search", "Tally Slate", params={"min": "lots"})
    with pytest.raises(Rejected, match="no ledger 'stores'") as e:
        ruhl.act("record", "Tally Slate", params={"ledger": "stores", "text": "x"})
    assert "open one" in e.value.hint
    with pytest.raises(Rejected, match="needs qty"):
        ruhl.act("record", "Tally Slate", params={"kind": "in", "item": "Water"})
    led = ruhl.act("ledgers", "Tally Slate", params={"open": "stores"})["result"]
    assert [x["ledger"] for x in led["ledgers"]] == ["stores", "tally"] and led["written"] == 7
    rec(ruhl, ledger="Stores", kind="in", item="Rope", qty=2)
    assert ruhl.act("search", "Tally Slate", params={"ledger": "stores"})["result"]["matched"] == 1


def test_total_gives_sums_balance_and_the_spread(tmp_path):
    eng, gm = world(tmp_path)
    ruhl = seat(eng, "Ruhl")
    fill(gm, ruhl)
    t = ruhl.act("total", "Tally Slate")["result"]
    g = {x["group"]: x for x in t["groups"]}
    water = g["Water"]
    # out 4, out 2, out 4, then a count of 30: the count sets the balance
    assert (water["entries"], water["in"], water["out"], water["net"], water["balance"]) == (4, 0, 10, -10, 30)
    assert (water["min"], water["max"], water["mode"]) == (2, 30, 4)
    assert water["mean"] == 10.0 and water["stdev"] == pytest.approx(11.576, abs=0.001)
    glass = g["Emberglass"]
    assert (glass["in"], glass["balance"], glass["mean"], glass["stdev"]) == (16, 16, 8.0, 2.0)
    assert g["(none)"]["entries"] == 1 and "min" not in g["(none)"]
    by_party = {x["group"]: x for x in ruhl.act("total", "Tally Slate", params={"by": "party", "kind": "out"})["result"]["groups"]}
    assert by_party["Keth"]["out"] == 4 and by_party["Bel"]["out"] == 4 and "Cy" in by_party
    assert ruhl.act("total", "Tally Slate", params={"by": "all"})["result"]["groups"][0]["entries"] == 7


def test_void_writes_a_correction_and_erases_nothing(tmp_path):
    eng, gm = world(tmp_path)
    ruhl = seat(eng, "Ruhl")
    fill(gm, ruhl)
    with pytest.raises(Rejected, match="needs a reason"):
        ruhl.act("void", "Tally Slate", params={"n": 2})
    v = ruhl.act("void", "Tally Slate", params={"n": 2, "reason": "Cy never came"})["result"]
    assert v["voided"] == 2 and v["written"]["n"] == 8 and v["written"]["kind"] == "void" and v["written"]["voids"] == 2
    r = ruhl.act("search", "Tally Slate", params={"entries": [2, 8]})["result"]
    assert {e["n"]: e.get("voided_by") for e in r["entries"]} == {2: 8, 8: None}
    assert ruhl.act("search", "Tally Slate", params={"voided": "only"})["result"]["matched"] == 1
    water = {x["group"]: x for x in ruhl.act("total", "Tally Slate")["result"]["groups"]}["Water"]
    assert water["out"] == 8  # the voided 2 is left out of the sums
    with pytest.raises(Rejected, match="already voided, by entry 8"):
        ruhl.act("void", "Tally Slate", params={"n": 2, "reason": "again"})
    with pytest.raises(Rejected, match="itself a correction"):
        ruhl.act("void", "Tally Slate", params={"n": 8, "reason": "undo"})
    assert state(gm, "Tally Slate")["written"] == 8  # eight entries, none gone


def test_a_carried_device_records_its_holders_deeds_and_verify_checks_them(tmp_path):
    eng, gm = world(tmp_path)
    ruhl, bel = seat(eng, "Ruhl"), seat(eng, "Bel")
    ruhl.act("give", "Bel", params={"item": "Water", "count": 3})
    ruhl.act("take", "Emberglass", params={"count": 5})
    bel.act("give", "Ruhl", params={"item": "Water", "count": 1})
    r = ruhl.act("read", "Tally Slate", params={"order": "asc"})["result"]
    got = [(e["kind"], e.get("item"), e.get("qty"), e.get("party"), e["source"].split(" (")[0][:13]) for e in r["entries"]]
    assert got == [("out", "Water", 3, "Bel", "recorded from"), ("in", "Emberglass", 5, "Yard", "recorded from"),
                   ("in", "Water", 1, "Bel", "recorded from")]
    assert r["entries"][0]["place"] == "Yard" and r["entries"][0]["tags"] == ["given"]
    assert state(gm, "Count Cord")["written"] == 0  # a device with no records keeps none
    rec(ruhl, kind="out", item="Water", qty=9, party="Bel", text="by my own hand")
    v = ruhl.act("verify", "Tally Slate")["result"]
    assert (v["checked"], v["confirmed"], v["unverifiable"], v["flagged"]) == (4, 3, 1, [])
    assert {e["n"]: e["status"] for e in v["entries"]}[4] == "unverifiable, by hand"
    # someone with the owner's hand alters an entry: verify flags it against the log
    pid = state(gm, "Tally Slate")["book"][0]
    page = [dict(e) for e in gm.world.get(pid)["state"]["entries"]]
    page[0]["qty"] = 30
    gm.patch(pid, {"entries": page})
    v = ruhl.act("verify", "Tally Slate", params={"source": "recorded"})["result"]
    assert v["flagged"] == [{"n": 1, "why": "the log says 3, the entry 30"}] and v["confirmed"] == 2


def test_nobody_but_the_holder_reads_it(tmp_path):
    eng, gm = world(tmp_path)
    ruhl, bel = seat(eng, "Ruhl"), seat(eng, "Bel")
    rec(ruhl, kind="out", item="Water", qty=7, party="Dreyer", text="SECRET-DEAL with the house")
    ruhl.act("give", "Bel", params={"item": "Water", "count": 1})
    ruhl.act("read", "Tally Slate")
    seen = json.dumps([bel.perceive(cursor=0), bel.inspect("Ruhl")])
    assert "SECRET-DEAL" not in seen and "Dreyer" not in seen and "ledger_page" not in seen
    said = [e["payload"].get("text") for e in bel.perceive(cursor=0)["events"] if e["kind"] == "scene"]
    assert "Ruhl checks Tally Slate." in said  # the one line the world set
    with pytest.raises(Rejected, match="not within reach"):
        bel.act("read", "Tally Slate")
    day = gm.chronicle(day=1)
    assert "SECRET-DEAL" not in json.dumps(day) and "Dreyer" not in json.dumps(day)
    assert "SECRET-DEAL" in json.dumps(gm.inspect(state(gm, "Tally Slate")["book"][0]))  # the owner sees everything


def test_bound_to_its_keeper_until_its_lock_is_broken(tmp_path):
    eng, gm = world(tmp_path)
    ruhl, bel = seat(eng, "Ruhl"), seat(eng, "Bel")
    rec(ruhl, kind="note", text="where the glass is buried")
    ruhl.act("give", "Bel", params={"item": "Tally Slate"})
    assert state(gm, "Tally Slate")["written"] == 1  # the slate changing hands is not written in it
    with pytest.raises(Rejected, match="locked to its keeper: break Slate Lock"):
        bel.act("read", "Tally Slate")
    bel.act("break", "Slate Lock")
    for _ in range(30):
        gm.world.step(5)
    assert state(gm, "Slate Lock")["broken"]
    assert bel.act("read", "Tally Slate")["result"]["entries"][0]["text"] == "where the glass is buried"
    # a bound device with no lock in it opens to nobody else
    gm.patch(gm.inspect("Count Cord")["id"], {"keeper": "Cy"})
    with pytest.raises(Rejected, match="answers only to its keeper"):
        bel.act("read", "Count Cord")


def test_transfer_face_to_face_and_send_by_relay(tmp_path):
    eng, gm = world(tmp_path)
    ruhl, bel, cy = seat(eng, "Ruhl"), seat(eng, "Bel"), seat(eng, "Cy")
    fill(gm, ruhl)
    ruhl.act("void", "Tally Slate", params={"n": 1, "reason": "wrong"})
    t = ruhl.act("transfer", "Tally Slate", params={"to": "Count Cord", "item": "Water"})["result"]
    assert t["copied"] == 3  # four water entries, one voided: a transfer leaves the cancelled behind
    cord = bel.act("read", "Count Cord", params={"order": "asc"})["result"]
    assert cord["entries"][0]["source"] == "copied from Tally Slate entry 2 by hand" and cord["entries"][0]["n"] == 1
    assert [e["kind"] for e in bel.perceive(cursor=0)["events"]].count("ledger_received") == 1
    v = bel.act("verify", "Count Cord")["result"]
    assert v["unverifiable"] == 3  # copies of hand entries
    # by relay, to a slate a room away; the relay keeps who and how many, never what
    s = ruhl.act("send", "Tally Slate", params={"to": "house-1", "kind": "in"})["result"]
    assert (s["sent"], s["via"]) == (2, "relay")
    house = cy.act("read", "House Slate")["result"]
    assert {e.get("item") for e in house["entries"]} == {"Emberglass"} and "by relay" in house["entries"][0]["source"]
    log = gm.world.get(state(gm, "Relay")["book"][0])["state"]["entries"]
    assert [(e["party"], e["qty"], e["text"]) for e in log] == [("guild-1 > house-1", 2, "relayed")]
    assert "Emberglass" not in json.dumps(log)
    gm.patch(gm.inspect("Relay")["id"], {"down": True})
    with pytest.raises(Rejected, match="relay is down"):
        ruhl.act("send", "Tally Slate", params={"to": "house-1"})
    # face to face: the cord reaches the slate only where both are
    assert bel.act("send", "Count Cord", params={"to": "guild-1"})["result"]["sent"] == 3
    ruhl.act("go", "Far House")
    with pytest.raises(Rejected, match="face to face only: guild-1 is not here"):
        bel.act("send", "Count Cord", params={"to": "guild-1"})
    with pytest.raises(Rejected, match="not among"):
        bel.act("send", "Count Cord", params={"to": "house-1"})
    c = bel.act("contacts", "Count Cord", params={"add": "house-1"})["result"]
    assert c["contacts"] == ["guild-1", "house-1"] and c["line"] == "cord-1"
    with pytest.raises(Rejected, match="no device answers"):
        bel.act("contacts", "Count Cord", params={"add": "nowhere"})


def test_copy_onto_paper_a_cap_and_the_book_after_a_reboot(tmp_path):
    db = tmp_path / "books.db"
    eng, gm = world(tmp_path, db)
    ruhl, bel = seat(eng, "Ruhl"), seat(eng, "Bel")
    fill(gm, ruhl)
    c = ruhl.act("copy", "Tally Slate", params={"onto": "Leaf", "kind": "in"})["result"]
    assert c["copied"] == 2
    text = state(gm, "Leaf")["text"]
    assert text.startswith("From Tally Slate, copied by Ruhl") and "#3 day 1, 02:00 [tally] in 10 Emberglass, Keth" in text
    gm.patch(gm.inspect("Tally Slate")["id"], {"cap": 8})
    rec(ruhl, text="the last line")
    with pytest.raises(Rejected, match="is full"):
        rec(ruhl, text="one more")
    ruhl.act("give", "Bel", params={"item": "Water", "count": 1})  # full: recorded nowhere, counted as missed
    assert state(gm, "Tally Slate")["missed"] == 1
    gm.patch(gm.inspect("Tally Slate")["id"], {"cap": None})
    eng.store.close() if hasattr(eng.store, "close") else None
    eng2 = Engine(str(db), workspace=tmp_path / "ws", record=False)
    ruhl2, bel2 = seat(eng2, "Ruhl"), seat(eng2, "Bel")
    r = ruhl2.act("read", "Tally Slate", params={"size": 50})["result"]
    assert r["matched"] == 8 and r["entries"][0]["text"] == "the last line"
    bel2.act("give", "Ruhl", params={"item": "Water", "count": 1})  # the listener still hears after the reboot
    assert ruhl2.act("read", "Tally Slate")["result"]["entries"][0]["source"].startswith("recorded from")


def big_book(gm, n_entries):
    # a book written straight into the archive, the way write_entries keeps it
    sid = gm.inspect("Tally Slate")["id"]
    root = gm.summary()["root"]
    arc = gm.spawn("ledger_archive", root, "Ledger archive")["id"]
    book = []
    page = []
    for n in range(1, n_entries + 1):
        page.append({"n": n, "t": n * 60.0, "ledger": "tally", "kind": ["in", "out", "count", "note"][n % 4],
                     "item": ["Water", "Emberglass", "Rope"][n % 3], "qty": n % 17, "party": ["Bel", "Cy", "Keth", "Dreyer"][n % 4],
                     "text": "entry " + str(n), "tags": ["t" + str(n % 5)], "source": {"by": "hand"}})
        if len(page) == 20 or n == n_entries:
            book.append(gm.spawn("ledger_page", arc, "ledger page", state={"device": sid, "entries": page})["id"])
            page = []
    gm.patch(sid, {"book": book, "archive": arc, "written": n_entries})


def test_a_big_book_stays_in_its_fuel(tmp_path):
    eng, gm = world(tmp_path)
    ruhl = seat(eng, "Ruhl")
    big_book(gm, 500)
    assert ruhl.act("search", "Tally Slate", params={"text": "entry 1", "sort": "amount"})["result"]["matched"] == 111
    t = ruhl.act("total", "Tally Slate", params={"by": "party"})["result"]
    assert sum(g["entries"] for g in t["groups"]) == 500
    assert ruhl.act("verify", "Tally Slate")["result"]["unverifiable"] == 500
    assert ruhl.act("read", "Tally Slate", params={"page": -1})["result"]["page"] == 50
    w = rec(ruhl, text="one more")  # the next entry opens page 26
    assert w["n"] == 501 and len(state(gm, "Tally Slate")["book"]) == 26
