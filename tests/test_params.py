"""A param nothing reads is refused with the names the verb takes (an agent guessed `topic` for talk's `about`, and the
deed went out empty). A key the verb's script names, or any script reads from params, still passes."""

import pytest

from embody.ops import Rejected
from tests.test_ops import engine_with_two_rooms

TALK = '''
def apply(ctx):
    about = ""
    if ctx.params:
        about = str(ctx.params.get("about", ""))
        if ctx.params.get("loud"):
            about = about.upper()
    ctx.emit("talked", target=ctx.target, reach=-1, by=ctx.actor.id, about=about)
'''

RULE = '''
def on(ctx, event):
    mood = (event.payload.get("params") or {}).get("mood")
'''


def talking_world():
    eng, w, i = engine_with_two_rooms()
    w.define_script("talk", TALK)
    w.define_script("mood_rule", RULE)
    w.define_schema("talker", extends="creature", actions={
        "talk": {"script": "talk", "doc": "Talk to someone", "targets": "creature",
                 "params": {"about": "the topic, in your words"}},
        "hum": {"script": "talk", "doc": "Hum at someone", "targets": "creature"}})
    i["Ada"] = w.spawn("talker", i["Cell"], "Ada")
    i["Bo"] = w.spawn("talker", i["Cell"], "Bo")
    p = eng.session("p")
    p.join("two-rooms", "Ada")
    return w, i, p


def test_a_param_nothing_reads_is_refused_with_the_names_the_verb_takes():
    w, i, p = talking_world()
    with pytest.raises(Rejected) as r:
        p.act("talk", "Bo", {"topic": "pale wax"})
    assert r.value.reason == "talk takes about, not topic"
    assert "about: the topic, in your words" in r.value.hint
    p.act("talk", "Bo", {"about": "pale wax"})
    talked = [e for e in w.events(since=0, limit=500) if e["kind"] == "talked"]
    assert talked[-1]["payload"]["about"] == "pale wax"


def test_keys_a_script_names_or_a_rule_reads_still_pass():
    w, i, p = talking_world()
    p.act("talk", "Bo", {"about": "wax", "loud": True})  # undeclared, but the verb's script reads it
    p.act("talk", "Bo", {"about": "wax", "mood": "glum"})  # undeclared, but a rule reads it off the event
    p.act("hum", "Bo", {"about": "wax"})  # a verb that declares nothing: its script still reads about
    with pytest.raises(Rejected) as r:
        p.act("hum", "Bo", {"tune": "low"})
    assert r.value.reason == "hum takes no params, not tune"
