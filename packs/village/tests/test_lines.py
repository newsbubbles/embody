"""A person's table line, spoken through person_on: text in double quotes is said, the rest is a gesture the room sees
(ctx.gesture), in the order written. A line with no double quotes is said whole, unless the person or the world keeps
lines: "quoted", where it is a gesture."""

import shutil
from pathlib import Path

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "bench", "name": "The bench", "seed": 4, "description": "A workshop.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"talk": {"script": "talk", "doc": "Talk to someone", "targets": "creature", "scope": "here",
                                      "params": {"about": "the topic"}}},
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])

def populate(s):
    root = s.summary()["root"]
    shop = s.spawn("place", root, "Shop")["id"]
    s.spawn("person", shop, "Varn", state={"default_line": 'Varn does not look up from the bench. "Bench is busy, love."',
                                            "dialog": {"cat": "The cat opens one eye, judges you, and closes it."}})
    s.spawn("person", shop, "Aaron")
    s.clock(run=False)
'''


def world(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(REPO / "packs" / "village", ws / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (ws / "worlds" / "bench").mkdir(parents=True)
    (ws / "worlds" / "bench" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(None, workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "bench")
    me = eng.session("aaron")
    me.join("bench", "Aaron")
    return eng, gm, me


def answer(eng, me, about):
    w = eng.world("bench")
    since = w.store.next_seq(w.id)
    me.act("talk", "Varn", params={"about": about})
    return [(e["kind"], e["payload"]["text"]) for e in w.events(since=since - 1, limit=50)
            if e["kind"] in ("say", "gestured") and e["actor_id"] != me._me()]


def test_a_mixed_line_is_a_gesture_then_the_quoted_words(tmp_path):
    eng, gm, me = world(tmp_path)
    assert answer(eng, me, "the weather") == [("gestured", "Varn does not look up from the bench."),
                                              ("say", "Bench is busy, love.")]


def test_a_loud_person_says_its_lines_aloud(tmp_path):
    # a barker's table answers carried only a normal voice where the world keeps a voice_radius (a builder, 2026-11-24)
    eng, gm, me = world(tmp_path)
    w = eng.world("bench")

    def said(about):
        since = w.store.next_seq(w.id)
        me.act("talk", "Varn", params={"about": about})
        return [e["payload"] for e in w.events(since=since - 1, limit=50) if e["kind"] == "say" and e["actor_id"] != me._me()]
    assert not said("the cat")[0].get("loud")
    gm.patch("Varn", {"loud_voice": True})
    assert said("the cat")[0].get("loud") and said("the weather")[0].get("loud")  # whole lines and quoted words


def test_an_unquoted_line_is_said_unless_lines_are_quoted(tmp_path):
    eng, gm, me = world(tmp_path)
    assert answer(eng, me, "the cat") == [("say", "The cat opens one eye, judges you, and closes it.")]
    gm.patch("Varn", {"lines": "quoted"})
    assert answer(eng, me, "the cat") == [("gestured", "The cat opens one eye, judges you, and closes it.")]
    gm.patch("Varn", {"lines": None})
    w = eng.world("bench")
    gm.patch(w.root_id, {"lines": "quoted"})  # the world's word, for every person
    assert answer(eng, me, "the cat")[0][0] == "gestured"
