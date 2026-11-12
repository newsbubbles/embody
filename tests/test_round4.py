"""Round four: one clock across processes, events you could witness, act results that catch you up,
a light wait, edits that are not news, and the CLI mind's missing switches."""

from pathlib import Path

import pytest

from embody.cli import load_world, main as cli_main
from embody.ops import AUTHOR, Engine
from embody.store import Store
from embody.world import World

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def ferry(path=None):
    eng = Engine(path, workspace=REPO, record=False) if path else Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    return eng, gm


def test_two_processes_share_one_clock_and_one_id_counter(tmp_path):
    """Playtest three: the MCP server and a CLI mind each cached the world row, so events were stamped
    t=189 after t=201 and the two could have handed out the same entity id."""
    db = tmp_path / "w.db"
    eng1, gm = ferry(str(db))
    eng2 = Engine(str(db))
    you = eng2.session("you")
    you.join("ferry-at-dusk", "Traveler")
    t0 = gm.world.t
    r = you.act("talk", "Mara", {"about": "tam"})          # process two moves the world a turn
    assert r["t"] == pytest.approx(t0 + 3)
    gm.perceive(from_entity="Mara")                        # process one ticks and sees it
    assert gm.world.t == pytest.approx(t0 + 3)
    gm.spawn("thing", "Ashford Square", "Cat")              # process one takes an id
    cat = gm.world.find(name="Cat")[0]["id"]
    you.perceive()
    r = you.act("go", "Pell's Mill")
    hat = eng2.session("gm2", capabilities=[AUTHOR])
    hat.use("ferry-at-dusk")
    hat.spawn("thing", "Pell's Mill", "Hat")                 # process two takes the next one, not the same
    assert hat.world.find(name="Hat")[0]["id"] != cat
    assert hat.world.find(name="Cat")[0]["id"] == cat


def test_you_only_witness_events_in_the_place_you_stood_in():
    eng, gm = ferry()
    mara = eng.session("mara-mind")
    mara.join("ferry-at-dusk", "Mara")
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.perceive()
    you.act("go", "Pell's Mill")                             # leave the square
    mara.say("He's gone. Good.")                            # said in the square, Traveler at the mill
    r = you.act("go", "Ashford Square")                      # walk back in
    texts = [e["payload"].get("text") for e in r["events"] if e["kind"] == "say"]
    assert "He's gone. Good." not in texts
    b = you.perceive(cursor=0, events=500)
    texts = [e["payload"].get("text") for e in b["events"] if e["kind"] == "say"]
    assert "He's gone. Good." not in texts
    mara.say("Back already?")
    assert any(e["payload"].get("text") == "Back already?" for e in you.perceive()["events"])


def test_act_result_carries_what_touched_you_since_you_last_looked():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.perceive()
    mara = eng.session("mara-mind")
    mara.join("ferry-at-dusk", "Mara")
    mara.say("You there. Yes, you.", to="Traveler")        # while the player was deciding
    r = you.act("talk", "Mara", {"about": "tam"})
    kinds = [e["kind"] for e in r["events"]]
    assert "say" in kinds and "talked" in kinds
    assert any(e["payload"].get("text") == "You there. Yes, you." for e in r["events"])
    assert "elapsed" in r and "turn" not in r and r["cursor"] >= r["events"][-1]["seq"]
    # the next act does not repeat them
    r2 = you.act("talk", "Mara", {"about": "ale"})
    assert not any(e["payload"].get("text") == "You there. Yes, you." for e in r2["events"])


def test_wait_is_light_unless_asked_for_the_whole_card():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.perceive()
    mara = eng.session("mara-mind")
    mara.join("ferry-at-dusk", "Mara")
    mara.say("Psst.", to="Traveler")
    b = you.wait(timeout=0, clock=lambda: 0.0, sleep=lambda s: None)
    assert set(b) >= {"t", "ambient", "here", "present", "events", "cursor"}
    assert "affordances" not in b and "you" not in b
    assert b["here"]["name"] == "Ashford Square" and any(c["name"] == "Mara" for c in b["present"])
    assert [e["payload"]["text"] for e in b["events"] if e["kind"] == "say"] == ["Psst."]
    # the cursor moved: a second wait times out with nothing, small
    b2 = you.wait(timeout=0, clock=lambda: 0.0, sleep=lambda s: None)
    assert b2["timed_out"] is True and b2["events"] == []
    assert "affordances" in you.wait(timeout=0, full=True, clock=lambda: 0.0, sleep=lambda s: None)


def test_an_edit_to_someone_else_is_not_news():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.perceive()
    gm.patch("Mara", {"mood": "tired", "dialog": {"owl": "An owl?"}})
    gm.patch("Traveler", {"mood": "tipsy"})
    b = you.perceive()
    pat = [e for e in b["events"] if e["kind"] == "patched"]
    assert len(pat) == 1 and pat[0]["payload"]["changes"] == {"mood": "tipsy"}
    assert next(c for c in b["present"] if c["name"] == "Mara")["state"].get("mood") == "tired"


def test_cli_say_to_and_light_wait(tmp_path, capsys):
    db = tmp_path / "w.db"
    ferry(str(db))
    cli_main(["--db", str(db), "--as", "mara", "join", "ferry-at-dusk", "Mara"])
    cli_main(["--db", str(db), "--as", "you", "join", "ferry-at-dusk", "Traveler"])
    cli_main(["--db", str(db), "--as", "you", "say", "An ale, please.", "--to", "Mara"])
    capsys.readouterr()
    cli_main(["--db", str(db), "--as", "mara", "wait", "--timeout", "0"])
    out = capsys.readouterr().out
    assert "An ale, please." in out and "Ashford Square" in out and "Holding" not in out
    s = Store(str(db))
    w = World(s, "ferry-at-dusk")
    last = [e for e in w.events(limit=500) if e["kind"] == "say"][-1]
    assert last["target_id"] == w.find(name="Mara")[0]["id"]
