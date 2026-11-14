"""The viewer's feed as a diff: a page that says what it holds gets only what changed since, and the structure only
when its signature moved."""

from pathlib import Path

from embody.cli import load_world
from embody.ops import AUTHOR, Engine
from embody.watch import Reader

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def test_the_feed_sends_only_what_changed(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    r = Reader(tmp_path / "w.db", REPO, conn=eng.store.conn)
    full = r.state("ferry-at-dusk", 0, 50)
    assert "diff" not in full and full["edges"] is not None and full["sig"]
    assert all(s["kind"] not in ("tick", "finish") for s in full["scheduled"]) and "ticks" in full
    held = max(e["updated_seq"] for e in full["entities"])

    quiet = r.state("ferry-at-dusk", 0, 50, after=held, sig=full["sig"])
    assert quiet["diff"] is True and quiet["entities"] == []
    assert quiet["ids"] == [e["id"] for e in full["entities"]]
    assert "edges" not in quiet and "schemas" not in quiet  # the structure did not move

    gm.patch("Traveler", {"water": 2})
    one = r.state("ferry-at-dusk", 0, 50, after=held, sig=full["sig"])
    assert [e["name"] for e in one["entities"]] == ["Traveler"] and one["entities"][0]["state"]["water"] == 2

    gm.link("Traveler", "Mara", "knows")
    moved = r.state("ferry-at-dusk", 0, 50, after=held, sig=full["sig"])
    assert moved["sig"] != full["sig"] and any(e["relation"] == "knows" for e in moved["edges"])

    gone = gm.spawn("thing", gm.inspect("Ashford Square")["id"], "Lantern")["id"]
    gm.destroy(gone)
    after = r.state("ferry-at-dusk", 0, 50, after=held, sig=moved["sig"])
    assert gone not in after["ids"]  # the page drops what is no longer in the list


def test_the_past_is_now_with_every_change_since_undone(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    r = Reader(tmp_path / "w.db", REPO, conn=eng.store.conn)
    then = r.state("ferry-at-dusk", 0, 50)
    seq = then["max_seq"]
    was = {e["id"]: (e["parent"], e["name"], e["state"]) for e in then["entities"]}
    bone = next(i for i, v in was.items() if v[1] == "Bone")

    gm.patch("Traveler", {"water": 2, "fresh": True})
    gm.move("Traveler", gm.inspect("Pell's Mill")["id"])
    gm.rename("Biscuit", "Flour")
    gm.spawn("thing", gm.inspect("The Reeds")["id"], "Lantern")
    gm.destroy("Bone")

    past = r.state("ferry-at-dusk", 0, 50, at=seq)
    assert past["at"]["seq"] == seq and past["events"][-1]["seq"] == seq
    got = {e["id"]: (e["parent"], e["name"], e["state"]) for e in past["entities"]}
    assert set(got) == set(was)  # the lantern is unmade and the bone is back
    for i, v in was.items():
        if i != bone:
            assert got[i] == v, i
    back = next(e for e in past["entities"] if e["id"] == bone)
    assert back["past"] == "destroyed" and back["parent"] == was[bone][0]  # its place, not its state
    assert r.state("ferry-at-dusk", 0, 50, at_t=past["at"]["t"])["at"]["seq"] >= seq
    assert past["first"]["seq"] >= 1
