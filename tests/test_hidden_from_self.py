"""A key a body may not read on itself (asked by a world builder, 2026-11-23): `hidden_from_self` on a body names state
a world keeps about it (a law's tally) that stays off its own perceive card, out of the patched diffs it sees and away
from its seat's filters, while the world's rules and the host read it as ever."""

from tests.test_patched_and_until import patches, seated

TALLY = """
def on(ctx, ev):
    p = ctx.find(name="Prisoner")[0]
    ctx.patch(p, {"marks": (p.state.marks or 0) + 1, "checked": p.state.marks})
"""


def marked():
    eng, w, i, gm, sam = seated()
    gm.patch("Prisoner", {"marks": 2, "secret": ["marks"], "hidden_from_self": ["marks"]})
    return eng, w, i, gm, sam


def test_the_body_never_reads_it_on_its_own_card():
    eng, w, i, gm, sam = marked()
    me = sam.perceive()["you"]["state"]
    assert "marks" not in me and "hidden_from_self" not in me
    assert "marks" not in sam.inspect("Prisoner")["state"]
    assert not any("marks" in p["changes"] or "hidden_from_self" in p["changes"] for p in patches(sam.wait(timeout=0)))


def test_a_rule_reads_and_writes_it_and_the_diff_the_body_sees_leaves_it_out():
    eng, w, i, gm, sam = marked()
    sam.wait(timeout=0)
    gm.define_script("tally", TALLY)
    gm.set_rule("Prisoner", "tally", kinds=["tally"])
    gm.schedule(5, "tally", entity="Prisoner")
    w.step(6)
    seen = patches(sam.wait(timeout=0))
    assert any(p["changes"].get("checked") == 2 for p in seen)  # the rule read the old tally
    assert not any("marks" in p["changes"] or "marks" in p["before"] for p in seen)
    assert gm.inspect("Prisoner")["state"]["marks"] == 3  # the host reads it
    assert w.events(kinds=["patched"], newest=True, limit=1)[0]["payload"]["changes"]["marks"] == 3  # the log keeps it


def test_a_wait_filter_reads_it_as_missing():
    eng, w, i, gm, sam = marked()
    b = sam.wait(until="me.get('marks') == 2", timeout=0)
    assert b["timed_out"]
