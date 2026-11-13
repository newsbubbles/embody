"""The watch oracle: wait(until=...) fires on a condition over what the watcher may know, keeps the cursor
while it waits, refuses bad expressions with the grammar, and `embody watch` loops it."""

import json
from pathlib import Path

import pytest

from embody.cli import load_world, main as cli_main
from embody.ops import AUTHOR, Engine, Rejected
from embody.watch_door import read_door

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
NOW = dict(clock=lambda: 0.0, sleep=lambda s: None)


def ferry(path=None):
    eng = Engine(path, workspace=REPO, record=False) if path else Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    return eng, gm


def two():
    eng, gm = ferry()
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    you.perceive()
    mara = eng.session("mara-mind")
    mara.join("ferry-at-dusk", "Mara")
    return eng, gm, you, mara


def test_until_fires_only_on_its_condition_and_keeps_what_came_before():
    eng, gm, you, mara = two()
    mara.say("Psst.", to="Traveler")
    b = you.wait(timeout=0, until="heard('ale')", **NOW)
    assert b["timed_out"] is True and b["fired"] is False and "events" not in b
    assert b["here"] == "Ashford Square" and "Mara" in b["present"] and b["seen"] >= 1
    mara.say("Want an ale?", to="Traveler")
    b = you.wait(timeout=0, until="heard('ALE', by='mara')", **NOW)
    assert b["fired"] is True and b["until"] == "heard('ALE', by='mara')"
    says = [e["payload"]["text"] for e in b["events"] if e["kind"] == "say"]
    assert says == ["Psst.", "Want an ale?"]  # the cursor stayed put while it waited
    assert you.wait(timeout=0, until="heard('ale')", **NOW)["timed_out"] is True  # and moved when it fired


def test_until_reads_time_place_people_and_my_own_state():
    eng, gm, you, mara = two()
    assert you.wait(timeout=0, until="came('mara') and here == 'Ashford Square'", **NOW)["fired"] is True
    assert you.wait(timeout=0, until="t >= 1000000000", **NOW)["timed_out"] is True
    gm.patch("Traveler", {"water": 2})
    assert you.wait(timeout=0, until="me.get('water', 10) < 3", **NOW)["fired"] is True
    assert you.wait(timeout=0, until="did('say', by='Mara')", **NOW)["timed_out"] is True
    # who is here means people: a thing with a name like someone's does not come in (the Keth jars, 2026-11-10)
    gm.spawn("thing", gm.inspect("Ashford Square")["id"], "Mara's ale jug", state={"portable": False})
    assert you.wait(timeout=0, until="came('jug')", **NOW)["timed_out"] is True


def test_came_is_who_is_here_arrived_waits_for_a_walk_in_and_both_replies_list_the_same_present():
    # a Codex player's watch on came('Ansel') woke at once on every arming: Ansel was already in the room
    eng, gm, you, mara = two()
    gm.spawn("thing", gm.inspect("Ashford Square")["id"], "Jug", state={"portable": False})
    b = you.wait(timeout=0, until="came('mara')", **NOW)
    assert b["fired"] is True and b["already"] is True and "arrived(name)" in b["note"]
    quiet = you.wait(timeout=0, until="arrived('mara')", **NOW)
    assert quiet["timed_out"] is True
    mara.act("go", "Pell's Mill")
    mara.act("go", "Ashford Square")
    b = you.wait(timeout=0, until="arrived('mara')", **NOW)
    assert b["fired"] is True and "already" not in b and any(e["kind"] == "arrived" for e in b["events"])
    # the fired reply's present is the timed-out one's: people and creatures, not the jug
    assert sorted(p["name"] for p in b["present"]) == sorted(quiet["present"]) and "Jug" not in quiet["present"]


def test_until_reads_my_state_with_the_schema_defaults_beneath():
    # Halvard's watch on me['water'] was refused, "key 'water' not found": a body by a source never dries, so its
    # water was never written, though every rule reads it as the schema's 10. A watch reads it the same way.
    eng, gm = ferry()
    gm.define_schema("wayfarer", extends="creature", state={"water": 10, "max_water": 10})
    gm.spawn("wayfarer", gm.inspect("Ashford Square")["id"], "Halvard")
    h = eng.session("halvard-mind")
    h.join("ferry-at-dusk", "Halvard")
    hid = gm.inspect("Halvard")["id"]
    row = gm.world.get(hid)
    gm.world.store.put("entity", {**row, "state": {k: v for k, v in row["state"].items() if k != "water"}})  # never written
    assert "water" not in gm.world.get(hid)["state"]
    assert h.wait(timeout=0, until="me['water'] < 3", **NOW)["timed_out"] is True
    gm.patch("Halvard", {"water": 2})
    assert h.wait(timeout=0, until="me['water'] < 3", **NOW)["fired"] is True

def test_until_sees_only_what_the_watcher_may_know_and_cannot_write():
    eng, gm, you, mara = two()
    gm.patch("Mara", {"plan": "poison the ale", "secret": ["plan"]})
    assert you.wait(timeout=0, until="state('Mara').get('plan') == 'poison the ale'", **NOW)["timed_out"] is True
    assert mara.wait(timeout=0, until="me.get('plan') == 'poison the ale'", **NOW)["fired"] is True
    you.wait(timeout=0, until="me.update({'mood': 'hacked'}) or True", **NOW)
    assert "mood" not in gm.inspect("Traveler")["state"] or gm.inspect("Traveler")["state"]["mood"] != "hacked"


def test_a_watcher_that_is_not_embodied_carries_since():
    eng, gm, you, mara = two()
    b = gm.wait(timeout=0, until="heard('ale')", **NOW)
    assert b["timed_out"] is True and isinstance(b["since"], int)
    mara.say("Ale's off tonight.")
    assert gm.wait(timeout=0, until="heard('ale')", since=b["since"], **NOW)["fired"] is True
    assert gm.wait(timeout=0, until="state('Mara').get('plan') is None", **NOW)["fired"] is True
    nobody = eng.session("nobody")
    nobody.use("ferry-at-dusk")
    with pytest.raises(Rejected, match="not embodied"):
        nobody.wait(timeout=0, until="True", **NOW)


@pytest.mark.parametrize("bad", ["import os", "().__class__", "nope + 1", "x = 1", "def f(): pass"])
def test_a_bad_condition_is_refused_with_the_grammar(bad):
    eng, gm, you, mara = two()
    with pytest.raises(Rejected) as r:
        you.wait(timeout=0, until=bad, **NOW)
    assert "heard(" in (r.value.hint or "")


def test_cli_watch_prints_fired(tmp_path, capsys):
    db = tmp_path / "w.db"
    ferry(str(db))
    cli_main(["--db", str(db), "--as", "mara", "join", "ferry-at-dusk", "Mara"])
    cli_main(["--db", str(db), "--as", "you", "join", "ferry-at-dusk", "Traveler"])
    capsys.readouterr()
    cli_main(["--db", str(db), "--as", "you", "watch", "--until", "came('Mara')", "--for", "2s"])
    out = capsys.readouterr().out
    assert out.startswith("FIRED: came('Mara')") and "Ashford Square" in out


def test_the_door_file_is_a_mcp_json_or_a_paste(tmp_path):
    j = tmp_path / ".mcp.json"
    j.write_text(json.dumps({"mcpServers": {"reach": {"type": "http", "url": "https://h.example/mcp",
                                                      "headers": {"Authorization": "Bearer abc_DEF-1"}}}}))
    assert read_door(str(j)) == ("https://h.example/mcp", "Bearer abc_DEF-1")
    p = tmp_path / "paste.txt"
    p.write_text("claude mcp add --transport http reach https://h.example/mcp --header \"Authorization: Bearer xyz\"")
    assert read_door(str(p)) == ("https://h.example/mcp", "Bearer xyz")
    with pytest.raises(SystemExit):
        read_door(str(j), server="other")


def test_watch_over_a_hosted_door_rejoins_fires_and_times_out(tmp_path, capsys):
    uvicorn = pytest.importorskip("uvicorn")
    import threading
    import time
    from embody.mcp_server import build_server, http_app
    from tests.test_grants import _free_port, owner
    from tests.test_ops import engine_with_two_rooms
    eng, w, i = engine_with_two_rooms()
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    srv = build_server(gm, None, eng, http_only=True)
    server = uvicorn.Server(uvicorn.Config(http_app(srv), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    door = tmp_path / ".mcp.json"
    door.write_text(json.dumps({"mcpServers": {"w": {"type": "http", "url": eng.public_url,
                                                     "headers": {"Authorization": f"Bearer {inv['token']}"}}}}))
    try:
        assert cli_main(["watch", "--door", str(door), "--until", "t >= 0", "--for", "5s", "--rejoin"]) == 0
        out = capsys.readouterr()
        assert out.out.startswith("FIRED: t >= 0") and "lapsed" in out.err and inv["token"] not in out.out + out.err
        assert w.embodied(i["Prisoner"])["id"] == inv["principal"]
        assert cli_main(["watch", "--door", str(door), "--until", "False", "--for", "1s"]) == 0
        assert capsys.readouterr().out.startswith("TIME UP")
        assert cli_main(["watch", "--door", str(door), "--until", "import os", "--for", "5s"]) == 2
        assert "REFUSED: until" in capsys.readouterr().out
    finally:
        server.should_exit = True
        t.join(timeout=5)


def test_a_watch_that_loses_the_door_says_why_and_wakes_its_runner(tmp_path, capsys, monkeypatch):
    import embody.watch_door as wd
    from tests.test_grants import _free_port
    monkeypatch.setattr(wd, "LOST_LIMIT", 0.0)  # nothing is listening: give up at the first loss
    door = tmp_path / ".mcp.json"
    door.write_text(json.dumps({"mcpServers": {"w": {"type": "http", "url": f"http://127.0.0.1:{_free_port()}/mcp",
                                                     "headers": {"Authorization": "Bearer not-a-real-token"}}}}))
    assert cli_main(["watch", "--door", str(door), "--until", "t >= 0", "--for", "1h"]) == 3
    out = capsys.readouterr().out
    assert out.startswith("LOST THE DOOR") and "ExceptionGroup" not in out and "not-a-real-token" not in out
