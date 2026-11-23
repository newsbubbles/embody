"""A rule or a timer makes an act (asked by a world builder, 2026-11-22): ctx.act(body, verb, target, params) drives a
body nobody holds through the same door its own act takes, so a keeper on a weekly timer reaches an oracle verb, the
oracle's limits and before_act rules still hold, the act names the rule as its cause, and a chain of them stays short."""

from tests.test_oracle import lab

WEEKLY = """
def on(ctx, ev):
    keeper = ctx.find(name="Keeper")[0]
    r = ctx.act(keeper, "search", ctx.find(name="Terminal")[0], {"q": "top 3"})
    ctx.patch(keeper, {"tries": (keeper.state.tries or 0) + 1, "refused": None if r["ok"] else r["reason"]})
"""

DRIVE_ADA = """
def on(ctx, ev):
    r = ctx.act(ctx.find(name="Prisoner")[0], "search", ctx.find(name="Terminal")[0], {"q": "puppet"})
    ctx.patch(ctx.find(name="Keeper")[0], {"refused": r["reason"]})
"""

NO_SEARCH = """
def on(ctx, ev):
    if ev.payload.get("verb") == "search":
        ctx.reject("the Terminal is shut tonight")
"""

RING = """
def apply(ctx):
    ctx.patch(ctx.target, {"rings": (ctx.target.state.rings or 0) + 1})
"""

ECHO = """
def on(ctx, ev):
    ctx.act(ctx.find(name="Keeper")[0], "ring", ctx.find(name="Bell")[0])
"""


def keeper_lab(**kw):
    eng, gm, o, ada, bo, inv, now = lab(**kw)
    gm.spawn("person", "Cell", "Keeper")
    gm.define_script("weekly_keeper", WEEKLY)
    gm.set_rule("Keeper", "weekly_keeper", kinds=["weekly"])
    return eng, gm, o, ada, gm.world


def test_a_keeper_on_a_timer_calls_the_oracle_and_hears_its_answer():
    eng, gm, o, ada, w = keeper_lab()
    keeper = w.find(name="Keeper")[0]["id"]
    gm.schedule(5, "weekly", entity="Keeper")
    w.step(6)
    calls = o.wait(timeout=0)["calls"]
    assert [(c["verb"], c["args"]) for c in calls] == [("search", {"q": "top 3"})]
    act = w.events(kinds=["act"], touching=keeper, newest=True, limit=1)[0]
    assert act["actor_id"] == keeper and act["payload"]["by"] == "weekly_keeper" and act["caused_by"]
    o.answer(calls[0]["request"], "1. Ada 2. Bo 3. Mara")
    got = w.events(kinds=["oracle_answer"], newest=True, limit=1)[0]
    assert got["payload"]["seen_by"] == [keeper] and got["payload"]["text"].startswith("1. Ada")  # to its caller alone


def test_the_oracle_limits_and_before_act_rules_still_hold():
    eng, gm, o, ada, w = keeper_lab()
    gm.schedule(5, "weekly", entity="Keeper", every=5)
    w.step(6)
    w.step(5)  # the second week: its first call is still open
    st = w.find(name="Keeper")[0]["state"]
    assert st["tries"] == 2 and "still working on your last call" in st["refused"]
    o.answer(o.wait(timeout=0)["calls"][0]["request"], "done")
    gm.define_script("shut_terminal", NO_SEARCH)
    gm.set_rule("Cell", "shut_terminal", kinds=["before_act"])
    w.step(5)
    assert w.find(name="Keeper")[0]["state"]["refused"] == "the Terminal is shut tonight"


def test_a_held_body_acts_only_for_itself():
    eng, gm, o, ada, w = keeper_lab()
    gm.define_script("drive_ada", DRIVE_ADA)
    gm.set_rule("Keeper", "drive_ada", kinds=["nudge"])
    gm.schedule(1, "nudge", entity="Keeper")
    w.step(2)
    assert "acts for itself" in w.find(name="Keeper")[0]["state"]["refused"]
    assert not o.wait(timeout=0)["calls"]


def test_a_chain_of_rule_acts_stays_short():
    eng, gm, o, ada, w = keeper_lab()
    gm.spawn("thing", "Cell", "Bell")
    gm.program("Bell", "ring", RING)
    gm.define_script("echo_ring", ECHO)
    gm.set_rule("Cell", "echo_ring", kinds=["act"])
    ada.act("ring", "Bell")
    assert w.find(name="Bell")[0]["state"]["rings"] == 3  # Ada's ring, the echo, the echo's echo, then no more
