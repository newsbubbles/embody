"""Access: owners, groups and modes on things (docs/ACCESS.md), and a limited grant that reads only its own plot."""

import pytest

from embody import access as acl
from embody.ops import Rejected, call
from tests.test_grants import owner
from tests.test_limits import builder
from tests.test_ops import engine_with_two_rooms

PEEK = """
def apply(ctx):
    p = ctx.find(name="Prisoner")[0]
    g = ctx.find(name="Guard")[0]
    ctx.patch(ctx.target, {"saw": [p.state.brief, p.state.get("plan"), "plan" in p.state.keys(), g.state.brief,
                                   len(ctx.find(state={"plan": "dig"}))]})
"""

SEAL = """
def apply(ctx):
    if ctx.params.get("how") == "hand":
        ctx.target.state.access = {"mode": "rwx------"}
    elif ctx.params.get("how") == "name":
        ctx.rename(ctx.target, "Pressed seal")
    elif ctx.params.get("how") == "far":
        ctx.rename(ctx.find(name="Prisoner")[0], "Nobody")
    else:
        ctx.chmod(ctx.target, "rwx------")
"""

CHARTER = """
def apply(ctx):
    root = ctx.root()
    table = dict(root.state.get("access_groups") or {})
    table["cellmates"] = list(table.get("cellmates") or []) + [ctx.actor.id]
    ctx.patch(root, {"access_groups": table})
    door = ctx.find(name="Iron door")[0]
    return [ctx.member(ctx.actor, "cellmates"), ctx.may(ctx.actor, "unlock", door), ctx.may(ctx.actor, "w", door)]
"""


def test_modes_read_like_a_file_system():
    assert acl.parse_mode("750") == "rwxr-x---"
    assert acl.parse_mode("rw-r--r--") == "rw-r--r--"
    assert acl.parse_mode("g+w,o-rwx", "rwxr-xr-x") == "rwxrwx---"
    assert acl.parse_mode("a=r") == "r--r--r--"
    with pytest.raises(acl.AccessError):
        acl.parse_mode("g*w")
    assert acl.parse_classes("a") == "ugo" and acl.parse_classes("gu") == "ug"
    acc = {"owner": "e1", "group": "masons", "mode": "rwxr-x---"}
    root = {"state": {"access_groups": {"masons": ["e2", "e1"]}}}
    assert [acl.class_of(acc, {x}, root) for x in ("e1", "e2", "e3")] == ["u", "g", "o"]
    assert acl.allows(acc, {"e2"}, root, "x") and not acl.allows(acc, {"e2"}, root, "w")
    assert not acl.allows({**acc, "mode": "---rwxrwx"}, {"e1"}, root, "r")  # the first class that matches counts
    assert acl.who_may(acc, "open", True) == "its owner and the masons"
    assert acl.may_verb(acc, {"e3"}, root, "take", own=False)  # an actor's verb with no rule is not the thing's to refuse
    assert not acl.may_verb({**acc, "verbs": {"take": "u"}}, {"e2"}, root, "take", own=False)


def test_a_builder_reads_the_secrets_of_its_own_plot_only():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Prisoner", {"brief": "knows the tunnel", "plan": "dig", "secret": ["plan"]})
    gm.patch("Guard", {"brief": "takes bribes"})
    gm.remember("hid a spoon", entity="Prisoner")
    gm.remember("owes the cook", entity="Guard")
    gm.spawn("thing", "Cell", name="Tunnel", state={"hidden": True})
    b, inv = builder(eng, gm)
    pre = inv["limits"]["scripts"]
    b.use("two-rooms")
    pris = b.inspect("Prisoner")["state"]
    assert "brief" not in pris and "plan" not in pris and "memory" not in pris
    assert b.inspect("Guard")["state"]["brief"] == "takes bribes"
    for op, kw in (("perceive", {"from_entity": "Prisoner"}), ("recall", {"entity": "Prisoner"})):
        assert call(b, op, **kw)["ok"] is False, op
    assert call(b, "recall", entity="Guard").get("ok") is not False
    assert not b.find(name="Tunnel") and gm.find(name="Tunnel")
    # its scripts read the same way, whoever runs them
    b.define_script(f"{pre}peek", PEEK)
    b.define_schema(f"{pre}glass", extends="thing", actions={"look": {"script": f"{pre}peek", "reach": "near"}})
    b.spawn(f"{pre}glass", "Hall", name="Glass")
    guard = eng.session("sam")
    guard.join("two-rooms", "Guard")
    guard.act("look", "Glass")
    assert w.find(name="Glass")[0]["state"]["saw"] == [None, None, False, "takes bribes", 0]
    gm.define_script(f"{pre}peek", PEEK)  # the owner's script reads everything
    guard.act("look", "Glass")
    assert w.find(name="Glass")[0]["state"]["saw"] == ["knows the tunnel", "dig", True, "takes bribes", 1]


def test_a_thing_answers_whom_its_access_names():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    s = eng.session("nate")
    s.join("two-rooms", "Prisoner")
    gm.chown("Rusty key", owner="Guard")
    gm.chmod("Rusty key", "u", verb="take")  # a rule on someone else's verb
    with pytest.raises(Rejected) as r:
        s.act("take", "Rusty key")
    assert "its owner" in r.value.reason
    gm.chmod("Rusty key", "default", verb="take")
    s.act("take", "Rusty key")
    gm.chown("Iron door", owner="Guard")
    gm.chmod("Iron door", "rwxr--r--")  # its own verbs need x
    aff = {(a["verb"], a["target"]): a for a in s.perceive()["affordances"]}
    assert aff[("unlock", i["Iron door"])]["ok"] is False and "its owner" in aff[("unlock", i["Iron door"])]["reason"]
    with pytest.raises(Rejected):
        s.act("unlock", "Iron door")
    # a world script puts the prisoner in a group; the group's bits open the door
    gm.define_script("charter", CHARTER)
    gm.define_schema("charter", extends="thing", actions={"sign": {"script": "charter", "reach": "near"}})
    gm.spawn("charter", "Cell", name="Charter")
    gm.chown("Iron door", group="cellmates")
    gm.chmod("Iron door", "g+x")
    assert s.act("sign", "Charter")["result"] == [True, True, False]
    s.act("unlock", "Iron door")
    # r: without it another body sees what a thing is, not what it holds
    gm.chmod("Iron door", "rwx--x---")
    gm.chown("Iron door", group="")
    door = s.inspect("Iron door")
    assert door["state"] == {} and door["contents"] == []
    assert gm.inspect("Iron door")["state"]["access"]["owner"] == i["Guard"]


def test_builders_own_what_they_make_and_share_it_by_mode():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    a, ia = builder(eng, gm)
    ib = gm.invite("builder", label="Tov", limits={"under": "Hall"})
    b = eng.session_for_token(ib["token"])
    a.use("two-rooms")
    b.use("two-rooms")
    stall = a.spawn("thing", "Hall", name="Stall")
    assert stall["state"]["access"] == {"owner": ia["principal"], "mode": "rwxr-xr-x"}
    assert call(b, "patch", entity="Stall", changes={"sign": "Fish"})["ok"] is False  # Mara's: no w for Tov
    assert call(b, "chmod", entity="Stall", mode="777")["ok"] is False
    assert call(a, "patch", entity="Stall", changes={"access": {"mode": "777"}})["ok"] is False
    assert call(b, "spawn", type="thing", parent="Stall", name="Fish")["ok"] is False  # writing into it is w too
    gm.patch("Two Rooms", {"access_groups": {"masons": [ib["principal"]]}})
    a.chown("Stall", group="masons")
    a.chmod("Stall", "g+w")
    assert b.patch("Stall", {"sign": "Fish"})["state"]["sign"] == "Fish"
    # in its plot, a builder claims what has no owner and keeps the other off it
    a.chmod("Guard", "rwxr-x---")
    assert w.need(i["Guard"])["state"]["access"]["owner"] == ia["principal"]
    assert call(b, "patch", entity="Guard", changes={"hp": 3})["ok"] is False
    assert call(a, "chmod", entity="Prisoner", mode="700")["ok"] is False  # outside its plot, and nobody's
    # the owner lends one thing outside the plot
    assert call(b, "patch", entity="Iron door", changes={"scratched": True})["ok"] is False
    gm.chown("Iron door", owner=ib["principal"])
    assert b.patch("Iron door", {"scratched": True})["state"]["scratched"] is True
    assert call(a, "patch", entity="Iron door", changes={"scratched": False})["ok"] is False
    gm.patch("Stall", {"sign": "Closed"})  # the world's owner passes every check


def test_a_builders_script_changes_access_inside_its_plot_only_by_chmod():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    b, inv = builder(eng, gm)
    pre = inv["limits"]["scripts"]
    b.use("two-rooms")
    b.define_script(f"{pre}seal", SEAL)
    b.define_schema(f"{pre}seal", extends="thing", actions={"press": {"script": f"{pre}seal", "reach": "near"}})
    b.spawn(f"{pre}seal", "Hall", name="Seal")
    guard = eng.session("sam")
    guard.join("two-rooms", "Guard")
    with pytest.raises(Rejected):
        guard.act("press", "Seal", {"how": "hand"})
    guard.act("press", "Seal", {"how": "name"})
    with pytest.raises(Rejected):
        guard.act("press", "Pressed seal", {"how": "far"})
    guard.act("press", "Pressed seal")
    assert w.find(name="Pressed seal")[0]["state"]["access"]["mode"] == "rwx------"
    with pytest.raises(Rejected) as r:
        guard.act("press", "Pressed seal")  # sealed now: its verbs are its owner's
    assert "its owner" in r.value.reason
