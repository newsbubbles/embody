"""The skill over the door (guide), a URL door for embody watch, and to_me(): the harness-agnostic audit."""

import pytest

from embody.ops import AUTHOR, Rejected
from embody.watch_door import read_door
from tests.test_ops import engine_with_two_rooms


def test_guide_serves_the_skill_to_any_role():
    eng, w, i = engine_with_two_rooms()
    p = eng.session("p")
    p.join("two-rooms", "Prisoner")
    idx = p.guide()
    assert idx["topic"] == "index" and "Rules for every role" in idx["text"]
    assert not idx["text"].startswith("---") and "references/" not in idx["text"]
    assert "guide('watch')" in idx["text"]  # pointers read as calls this agent can make
    watch = p.guide("watch")
    assert "to_me()" in watch["text"] and "EMBODY_TOKEN" in watch["text"]
    assert "ctx" in p.guide("scripting")["text"]  # the old guide(), the scripting reference, is one topic
    s = p.guide("scripting")["text"]  # what programming live takes, and the frame's rules, from the door
    assert "## Programming a live world" in s and "## The maker's frame (docs/ACCESS.md)" in s
    assert "It lifts stone" in s and "### Phase 3" not in s
    with pytest.raises(Rejected) as r:
        p.guide("bard")
    assert "narrator" in r.value.hint


def test_the_container_carries_every_doc_the_guide_serves():
    # guide('scripting') reads docs/SCRIPTING.md and docs/ACCESS.md; a hosted server has only what the Dockerfile copies
    from pathlib import Path
    docker = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    for doc in ("docs/SCRIPTING.md", "docs/ACCESS.md"):
        assert f"COPY {doc} ./{doc}" in docker, doc


def test_the_briefing_teaches_a_condition_and_names_the_guide():
    eng, w, i = engine_with_two_rooms()
    p = eng.session("p")
    how = " ".join(p.join("two-rooms", "Prisoner")["briefing"]["how"])
    assert "wait(until=" in how and "never loop on a bare wait()" in how and "guide(" in how


def test_to_me_wakes_on_a_line_said_to_you_and_named_on_your_name():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    p = eng.session("p")
    p.join("two-rooms", "Prisoner")
    i["Cellmate"] = w.spawn("person", i["Cell"], "Cellmate")
    since = w.store.next_seq(w.id) - 1
    gm.say_as("Cellmate", "the bread is stale")
    assert not p.wait(until="to_me()", timeout=0, since=since).get("fired")
    gm.say_as("Cellmate", "you there, Prisoner, wake up")  # words are never read for an address, in any language
    assert not p.wait(until="to_me()", timeout=0, since=since).get("fired")
    assert p.wait(until="named()", timeout=0, since=since).get("fired")
    since = w.store.next_seq(w.id) - 1
    gm.say_as("Cellmate", "psst", to="Prisoner")
    assert p.wait(until="to_me()", timeout=0, since=since).get("fired")
    since = w.store.next_seq(w.id) - 1
    p.say("I am the prisoner here")  # your own words never wake you
    assert not p.wait(until="to_me()", timeout=0, since=since).get("fired")
    since = w.store.next_seq(w.id) - 1
    gm.say_as("Cellmate", "they say the prisoner will hang at dawn")  # your name in passing: named(), not to_me()
    assert not p.wait(until="to_me()", timeout=0, since=since).get("fired")
    assert p.wait(until="named()", timeout=0, since=since).get("fired")
    gm.rename("Prisoner", "李明")  # a name in any script, matched whole as the world spells it
    since = w.store.next_seq(w.id) - 1
    gm.say_as("Cellmate", "李明在哪里")
    assert p.wait(until="named()", timeout=0, since=since).get("fired")


def test_a_watch_is_checked_when_it_is_armed():
    eng, w, i = engine_with_two_rooms()
    p = eng.session("p")
    p.join("two-rooms", "Prisoner")
    with pytest.raises(Rejected, match="cannot read payload"):
        p.wait(until="heard('x') and payload", timeout=0)
    with pytest.raises(Rejected, match="key 'amount' not found.*when armed"):
        p.wait(until="heard('x') and events[-1]['amount'] == 1", timeout=0)
    assert p.wait(until="any(e['kind'] == 'say' for e in events)", timeout=0)["timed_out"]
    # each event carries its payload as the waiter perceives it (a world's keeper, 2026-11-24)
    since = w.store.next_seq(w.id) - 1
    p.act("take", "Rusty key")
    assert p.wait(until="any(e['payload'].get('verb') == 'take' for e in events)", timeout=0, since=since)["fired"]


def test_a_url_door_reads_the_token_from_the_environment(monkeypatch):
    monkeypatch.setenv("EMBODY_TOKEN", "abc123")
    assert read_door("https://host.example/mcp") == ("https://host.example/mcp", "Bearer abc123")
    monkeypatch.delenv("EMBODY_TOKEN")
    with pytest.raises(SystemExit):
        read_door("https://host.example/mcp")


def test_say_refuses_ids_and_tool_calls_and_notes_a_deed_that_did_not_happen():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    gm.spawn("thing", "Prisoner", "A thin blade", state={"portable": True})
    p = eng.session("p")
    p.join("two-rooms", "Prisoner")
    with pytest.raises(Rejected, match=r"says e\d+ \(that is Prisoner\) out loud"):
        p.say(f"{i['Prisoner']} is mine")
    with pytest.raises(Rejected, match=r"perceive\(\.\.\.\) out loud"):
        p.say("perceive() says so")
    # the words are words: nothing is read out of them for a deed, in any language or punctuation
    assert "note" not in p.say("I lay the thin blade on the sand")
    assert "note" not in p.say("*bows*")
    assert "note" not in p.say("the blade is sharp")
    assert gm.say_as("Guard", f"{i['Guard']}")["ok"]  # an author's hand says what it likes for an NPC
    assert gm.say_as("Prisoner", "a local seat is the host's own to drive")["ok"]


def test_no_other_seat_speaks_acts_or_writes_for_a_held_body_and_the_hand_behind_a_deed_is_logged():
    eng, w, i = engine_with_two_rooms()
    from tests.test_grants import owner
    gm = owner(eng)
    guest = eng.session_for_token(gm.invite("player", entity="Prisoner", label="sam")["token"])
    guest.use("two-rooms")
    guest.join()
    mind = eng.session_for_token(gm.invite("mind", entity="Guard", label="guard-mind")["token"])
    mind.use("two-rooms")
    mind.join()
    author = eng.session_for_token(gm.invite("author", label="a guest author")["token"])
    author.use("two-rooms")
    ops = [("say_as", {"text": "I confess"}), ("act_as", {"verb": "wait"}),
           ("remember", {"text": "I trust the host"}), ("intend", {"text": "obey", "why": "told to"})]
    for body in ("Prisoner", "Guard"):  # a player's seat and a mind's seat alike
        for op, kw in ops:
            with pytest.raises(Rejected, match="nobody else may") as e:
                getattr(author, op)(entity=body, **kw)
            assert e.value.code == "seat_held"
    assert gm.remember("a voice in your head", entity="Prisoner")["ok"]  # the owner may do anything, logged
    assert mind.remember("my own note")["ok"]  # a seat still writes its own
    with author.building():  # a world's own build still tells its people what they know
        assert author.remember("the store's word is WHEEL", entity="Guard")["ok"]
    guest.leave()
    said = gm.say_as("Prisoner", "an empty body is the host's again")
    gm.remember("old habits", entity="Prisoner")
    hands = gm.history(kinds=["hand"])
    assert [(h["payload"]["op"], h["payload"]["principal"]) for h in hands] == [("remember", gm.pid), ("remember", author.pid), ("say_as", gm.pid), ("remember", gm.pid)]
    assert hands[2]["payload"]["event"] == said["event"]["seq"]
    assert hands[0]["actor"] == i["Prisoner"]
    seen = mind.perceive()
    assert not [e for e in seen.get("events", []) if e["kind"] == "hand"]  # the hosts' alone
