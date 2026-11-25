"""A verb's long answer comes back cut, and more() reads on from a cut without doing the verb again (Nate 2026-11-24:
a verb is a tool, and a tool's answer is held to a page like every list the engine answers)."""

import json

import pytest

from embody.ops import PAGE_LIMITS, Rejected, page_config, page_window
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

SHELF = """def apply(ctx):
    n = ctx.params.get('n', 300)
    books = []
    for k in range(n):
        books.append({'title': 'Book ' + str(k), 'text': 'word ' * 600})
    ctx.emit('browsed', target=ctx.actor, reach=1)
    return {'shelf': 'east wall', 'books': books}
"""
COUNT = """def apply(ctx):
    r = ctx.act(ctx.params['who'], 'browse', None, {})
    ctx.patch(ctx.actor, {'counted': len(r['result']['books'])})
    return {'counted': len(r['result']['books'])}
"""


def _reader(page=None):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.define_script("shelf", SHELF)
    gm.define_script("count_books", COUNT)
    browse = {"script": "shelf", "reach": "self", "params": {"n": "how many books"}}
    if page is not None:
        browse["page"] = page
    gm.define_schema("reader", extends="creature", actions={"browse": browse,
                                                           "count": {"script": "count_books", "reach": "self",
                                                                     "params": {"who": "a body nobody holds"}}})
    gm.spawn("reader", "Hall", "Ada", state={"playable": True})
    gm.spawn("reader", "Hall", "Bo")
    s = eng.session("sam")
    s.join("two-rooms", "Ada")
    return eng, w, s


def test_a_short_answer_comes_back_whole():
    eng, w, s = _reader()
    r = s.act("browse", params={"n": 2})
    assert "more" not in r and "page" not in r and len(r["result"]["books"]) == 2


def test_a_long_answer_is_cut_to_the_budget_and_says_where():
    eng, w, s = _reader()
    r = s.act("browse", params={"n": 300})
    assert len(json.dumps(r["result"])) <= 2000 * 4
    m = r["more"]
    assert m["handle"].startswith("pg") and "more(" in m["how"]
    books = next(c for c in m["cuts"] if c["path"] == "books")
    assert books["total"] == 300 and books["shown"] == len(r["result"]["books"]) < 300
    assert any(c["path"] == "books.0.text" and c["total"] == 3000 for c in m["cuts"])
    assert r["events"] and r["result"]["shelf"] == "east wall"  # the rest of the act's answer is as before


def test_more_reads_on_through_a_list_and_a_string_without_doing_the_verb_again():
    eng, w, s = _reader()
    r = s.act("browse", params={"n": 300})
    h = r["more"]["handle"]
    acts = len(w.events(kinds=["browsed"], limit=500))
    titles, off = [], 0
    while off is not None:
        page = s.more(h, "books", off)
        assert page["total"] == 300 and page["path"] == "books"
        titles += [b["title"] for b in page["value"]]
        off = page["next"]
    assert titles == [f"Book {k}" for k in range(300)]
    assert len(w.events(kinds=["browsed"], limit=500)) == acts  # more() never ran the verb
    text, off = "", 0
    while off is not None:
        page = s.more(h, "books.7.text", off)
        text += page["value"]
        off = page["next"]
    assert text == "word " * 600
    top = s.more(h)
    assert top["path"] is None and top["value"]["shelf"] == "east wall"


def test_more_refuses_what_it_does_not_keep_with_the_way_forward():
    eng, w, s = _reader()
    h = s.act("browse", params={"n": 300})["more"]["handle"]
    with pytest.raises(Rejected, match="no answer is kept") as r:
        s.more("pg00000000", "books")
    assert "do the verb again" in r.value.hint
    with pytest.raises(Rejected, match="nothing at books.999"):
        s.more(h, "books.999")
    with pytest.raises(Rejected, match="past the end"):
        s.more(h, "books", 300)
    with pytest.raises(Rejected, match="before the start"):
        s.more(h, "books", -1)
    other = eng.session("kim")
    other.join("two-rooms", "Prisoner")
    with pytest.raises(Rejected, match="no answer is kept"):
        other.more(h, "books")  # a seat reads only its own answers


def test_a_seat_keeps_its_last_eight_answers():
    eng, w, s = _reader()
    handles = [s.act("browse", params={"n": 60})["more"]["handle"] for _ in range(9)]
    with pytest.raises(Rejected):
        s.more(handles[0], "books")
    assert s.more(handles[-1], "books")["ok"]


def test_an_action_sets_its_own_page_within_the_limits():
    assert page_config({"items": 1, "chars": 10**9, "budget": 10**9}) == {
        "items": PAGE_LIMITS["items"][0], "chars": PAGE_LIMITS["chars"][1], "budget": PAGE_LIMITS["budget"][1]}
    assert page_config({"items": True, "budget": "lots"})["items"] == 20  # only numbers count
    assert page_config({"chars": 20_000, "budget": 500})["chars"] == 2000  # a string's page fits the budget
    eng, w, s = _reader(page={"items": 5, "budget": 500})
    r = s.act("browse", params={"n": 300})
    assert len(json.dumps(r["result"])) <= 500 * 4
    assert s.more(r["more"]["handle"], "books")["shown"] == 5


def test_a_script_acting_gets_the_whole_answer():
    eng, w, s = _reader()
    bo = next(e["id"] for e in w.find(name="Bo"))
    assert s.act("count", params={"who": bo})["result"] == {"counted": 300}


def test_a_cut_page_inside_more_names_the_whole_answers_path():
    whole = {"books": [{"text": "x" * 50} for _ in range(40)]}
    shown, cuts = page_window(whole["books"][20:30], {"items": 5, "chars": 10, "budget": 1}, "books", 20)
    assert cuts[0] == {"path": "books", "shown": 5, "total": 10}
    assert cuts[1]["path"] == "books.20.text"
