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
    with pytest.raises(Rejected) as r:
        p.guide("bard")
    assert "narrator" in r.value.hint


def test_the_briefing_teaches_a_condition_and_names_the_guide():
    eng, w, i = engine_with_two_rooms()
    p = eng.session("p")
    how = " ".join(p.join("two-rooms", "Prisoner")["briefing"]["how"])
    assert "wait(until=" in how and "never loop on a bare wait()" in how and "guide(" in how


def test_to_me_wakes_on_words_to_you_or_your_name():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    p = eng.session("p")
    p.join("two-rooms", "Prisoner")
    i["Cellmate"] = w.spawn("person", i["Cell"], "Cellmate")
    since = w.store.next_seq(w.id) - 1
    gm.say_as("Cellmate", "the bread is stale")
    assert not p.wait(until="to_me()", timeout=0, since=since).get("fired")
    gm.say_as("Cellmate", "you there, prisoner, wake up")
    assert p.wait(until="to_me()", timeout=0, since=since).get("fired")
    since = w.store.next_seq(w.id) - 1
    gm.say_as("Cellmate", "psst", to="Prisoner")
    assert p.wait(until="to_me()", timeout=0, since=since).get("fired")
    since = w.store.next_seq(w.id) - 1
    p.say("I am the prisoner here")  # your own words never wake you
    assert not p.wait(until="to_me()", timeout=0, since=since).get("fired")


def test_a_url_door_reads_the_token_from_the_environment(monkeypatch):
    monkeypatch.setenv("EMBODY_TOKEN", "abc123")
    assert read_door("https://host.example/mcp") == ("https://host.example/mcp", "Bearer abc123")
    monkeypatch.delenv("EMBODY_TOKEN")
    with pytest.raises(SystemExit):
        read_door("https://host.example/mcp")
