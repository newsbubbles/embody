"""Grant limits, the builder role and canon: a grant that builds one part of a world while it plays, and the marks
only the owner sets."""

import pytest

from embody.ops import Rejected, call
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

LEVER = """
def apply(ctx):
    ctx.patch(ctx.target, {"pulled": True})
    ctx.patch(ctx.actor, {"tired": True})
    if ctx.params.get("reach") == "cell":
        ctx.patch(ctx.find(name="Prisoner")[0], {"freed": True})
    if ctx.params.get("reach") == "state":
        ctx.find(name="Prisoner")[0].state.freed = True
    if ctx.params.get("reach") == "news":
        ctx.emit("agreed", target=ctx.target)
"""


def builder(eng, gm, **limits):
    inv = gm.invite("builder", label="Mara", limits={"under": "Hall", **limits})
    return eng.session_for_token(inv["token"]), inv


def test_a_builder_builds_under_its_plot_and_reads_the_rest():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    with pytest.raises(Rejected) as r:
        gm.invite("builder", label="Nobody")
    assert "under" in r.value.reason
    b, inv = builder(eng, gm)
    pre = inv["limits"]["scripts"]
    assert inv["limits"]["under"] == i["Hall"] and pre.startswith("mara_") and "under Hall" in inv["page"]
    b.use("two-rooms")
    stall = b.spawn("thing", "Hall", name="Stall")
    assert b.patch("Stall", {"sign": "Bread"})["state"]["sign"] == "Bread"
    for op, kw in (("spawn", {"type": "thing", "parent": "Cell", "name": "Crate"}),
                   ("patch", {"entity": "Prisoner", "changes": {"hp": 0}}),
                   ("move", {"entity": "Stall", "parent": "Cell"}),
                   ("destroy", {"entity": "Iron door"}),
                   ("schedule", {"after": 5, "kind": f"{pre}bell"}),
                   ("clock", {"rate": 100}),
                   ("save", {})):
        out = call(b, op, **kw)
        assert out["ok"] is False, op
    assert call(b, "schedule", after=5, kind="bell", entity="Stall")["ok"] is False  # its kinds carry its prefix
    assert b.schedule(5, f"{pre}bell", entity="Stall")["ok"]
    assert any(c["name"] == "Prisoner" for c in b.find(name="Prisoner"))  # the rest it reads
    assert call(b, "define_script", id="lever", source=LEVER)["ok"] is False
    b.define_script(f"{pre}lever", LEVER)
    src = b.script_source(f"{pre}lever")["source"]
    assert src.startswith("# limits: ") and '"under": "' + i["Hall"] in src
    assert w.script(f"{pre}lever").limits["under"] == i["Hall"]
    assert stall["id"] in {e["id"] for e in w.find(under=i["Hall"])}


def test_a_builders_script_keeps_its_limits_when_anyone_runs_it():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    b, inv = builder(eng, gm)
    pre = inv["limits"]["scripts"]
    b.use("two-rooms")
    b.define_script(f"{pre}lever", LEVER)
    assert call(b, "define_schema", id=f"{pre}lever", extends="thing",
                actions={"pull": {"script": "take"}})["ok"] is False  # an owner's script on its schema
    b.define_schema(f"{pre}lever", extends="thing", actions={"pull": {"script": f"{pre}lever", "reach": "near"}})
    b.spawn(f"{pre}lever", "Hall", name="Lever")
    guard = eng.session("sam")
    guard.join("two-rooms", "Guard")
    guard.act("pull", "Lever")  # the one who chose the verb may be touched by it
    assert w.need(i["Guard"])["state"]["tired"] and w.find(name="Lever")[0]["state"]["pulled"]
    for reach in ("cell", "state", "news"):
        with pytest.raises(Rejected):
            guard.act("pull", "Lever", {"reach": reach})
    assert not w.need(i["Prisoner"])["state"].get("freed")
    gm.define_script(f"{pre}lever", LEVER)  # redefined by the owner: the owner's now, unlimited
    guard.act("pull", "Lever", {"reach": "cell"})
    assert w.need(i["Prisoner"])["state"]["freed"]


def test_canon_is_the_owners_mark():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Iron door", {"canon": True})
    nar = eng.session_for_token(gm.invite("narrator", label="Ned")["token"])
    nar.use("two-rooms")
    for op, kw in (("patch", {"entity": "Iron door", "changes": {"locked": False}}),
                   ("move", {"entity": "Iron door", "parent": "Hall"}),
                   ("destroy", {"entity": "Cell"}),  # it holds the door
                   ("patch", {"entity": "Rusty key", "changes": {"canon": True}}),
                   ("spawn", {"type": "thing", "parent": "Cell", "state": {"canon": True}})):
        out = call(nar, op, **kw)
        assert out["ok"] is False and "canon" in out["reason"], op
    assert nar.patch("Rusty key", {"rust": 3})["state"]["rust"] == 3
    gm.patch("Iron door", {"canon": None})
    assert nar.patch("Iron door", {"scratched": True})["state"]["scratched"]


def test_limits_are_checked_when_the_invite_is_made():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    for kw in ({"role": "player", "limits": {"under": "Hall"}},
               {"role": "builder", "limits": {"under": "Hall", "where": "x"}},
               {"role": "builder", "limits": {"under": "Hall", "types": ["dragon"]}},
               {"role": "builder", "limits": {"under": "Hall", "scripts": "Bad-Prefix"}}):
        assert call(gm, "invite", label="x", **kw)["ok"] is False, kw
    gm.invite("builder", label="One", limits={"under": "Hall", "scripts": "one_"})
    assert call(gm, "invite", role="builder", label="Two", limits={"under": "Cell", "scripts": "one_x_"})["ok"] is False
    nar = gm.invite("narrator", label="Kit", limits={"under": "Cell", "types": ["thing"]})
    k = eng.session_for_token(nar["token"])
    k.use("two-rooms")
    assert k.spawn("thing", "Cell", name="Pebble")["name"] == "Pebble"
    assert call(k, "spawn", type="creature", parent="Cell")["ok"] is False


PEEK = """
def apply(ctx):
    ev = ctx.event_at(ctx.params.get("seq"))
    return ev.kind if ev is not None else None
"""


def test_a_builders_script_reads_the_log_of_its_own_plot_only():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    b, inv = builder(eng, gm)
    pre = inv["limits"]["scripts"]
    b.use("two-rooms")
    b.define_script(f"{pre}peek", PEEK)
    b.define_schema(f"{pre}glass", extends="thing", actions={"peek": {"script": f"{pre}peek", "reach": "near",
                                                                       "params": {"seq": "an event"}}})
    b.spawn(f"{pre}glass", "Hall", name="Glass")
    inside = w.emit("rang", target=w.find(name="Glass")[0]["id"])["seq"]
    outside = w.emit("whispered", target=i["Prisoner"])["seq"]  # in the Cell, out of Mara's plot
    guard = eng.session("sam")
    guard.join("two-rooms", "Guard")
    assert guard.act("peek", "Glass", {"seq": inside})["result"] == "rang"
    assert guard.act("peek", "Glass", {"seq": outside})["result"] is None
