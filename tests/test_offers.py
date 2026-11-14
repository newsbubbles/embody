"""Seats the world hands out: a rule offers a seatable entity to whoever holds a body (ctx.offer_seat), the holder
claims it on their own session within their grant's slots (claim_seat), and the seat ends with the world's word
(ctx.withdraw_seat) or with the grant it was claimed under."""

import re

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

REWARD = "def apply(ctx):\n    return ctx.offer_seat(ctx.find(name=ctx.params.get('what'))[0], ctx.actor, why='for the prayer')\n"
DISMISS = "def apply(ctx):\n    return ctx.withdraw_seat(ctx.find(name=ctx.params.get('what'))[0], why='it wandered off')\n"


def offering_world(slots=1):
    eng, w, i = engine_with_two_rooms()
    w.define_script("reward", REWARD)
    w.define_script("dismiss", DISMISS)
    w.define_schema("shrine", extends="thing", actions={"pray": {"script": "reward", "doc": "Pray here"},
                                                       "dismiss": {"script": "dismiss", "doc": "Let it go"}})
    w.define_schema("hound", extends="creature", state={"seatable": True})
    for name in ("Shrine",):
        i[name] = w.spawn("shrine", i["Cell"], name)
    i["Hound"] = w.spawn("hound", i["Cell"], "Hound")
    i["Pup"] = w.spawn("hound", i["Cell"], "Pup")
    gm = owner(eng)
    gm.patch(w.root_id, {"seat_slots": slots})
    g = gm.invite("player", entity="Prisoner", label="aaron")
    aaron = eng.session_for_token(g["token"])
    aaron.join()
    return eng, w, i, gm, aaron, g


def token_in(paste):
    return re.search(r"Bearer ([A-Za-z0-9_-]{20,})", paste).group(1)


def test_a_rule_offers_a_seat_and_the_holder_claims_it_for_a_new_session():
    eng, w, i, gm, aaron, g = offering_world()
    offer = aaron.act("pray", "Shrine", params={"what": "Hound"})["result"]
    assert [e["kind"] for e in aaron.history(limit=50)].count("seat_offered") == 1  # the holder is told
    assert aaron.seats()["offers"][0]["offer"] == offer and aaron.seats()["offers"][0]["name"] == "Hound"
    assert aaron.act("pray", "Shrine", params={"what": "Hound"})["result"] == offer  # not offered twice
    r = aaron.claim_seat(offer)
    assert r["role"] == "mind" and r["name"] == "Hound" and "paste" in r
    hound = eng.session_for_token(token_in(r["paste"]))
    assert hound.join()["you"]["name"] == "Hound"
    with pytest.raises(Rejected):
        hound.join(entity="Prisoner")  # a mind grant holds that one entity
    row = [x for x in gm.grants() if x["id"] == r["grant"]][0]
    assert row["parent_id"] == g["id"] and row["role"] == "mind" and row["expires"] is None
    assert {o["status"] for o in gm.seats()["offers"]} == {"claimed"}  # the owner sees every offer
    with pytest.raises(Rejected) as e:
        aaron.claim_seat(offer)
    assert "claimed" in e.value.reason


def test_slots_cap_the_seats_and_only_the_holder_claims():
    eng, w, i, gm, aaron, g = offering_world(slots=1)
    first = aaron.act("pray", "Shrine", params={"what": "Hound"})["result"]
    second = aaron.act("pray", "Shrine", params={"what": "Pup"})["result"]
    other = eng.session_for_token(gm.invite("player", entity="Guard", label="b")["token"])
    other.join()
    with pytest.raises(Rejected):
        other.claim_seat(first)
    assert "offers" not in other.seats()
    aaron.claim_seat(first)
    with pytest.raises(Rejected) as e:
        aaron.claim_seat(second)
    assert "slots are full (1 of 1): Hound" in e.value.reason
    # an invite's own slots win over the root's
    g2 = gm.invite("player", label="c", slots=0)
    assert [x for x in gm.grants() if x["id"] == g2["id"]][0]["slots"] == 0


def test_no_slots_no_seats_and_only_seatable_things():
    eng, w, i, gm, aaron, g = offering_world(slots=0)
    offer = aaron.act("pray", "Shrine", params={"what": "Hound"})["result"]
    with pytest.raises(Rejected) as e:
        aaron.claim_seat(offer)
    assert "0 of 0" in e.value.reason and "seat_slots" in e.value.hint
    with pytest.raises(Rejected) as e:
        aaron.act("pray", "Shrine", params={"what": "Rusty key"})
    assert "not seatable" in e.value.reason


def test_withdraw_and_revoke_end_the_seat():
    eng, w, i, gm, aaron, g = offering_world(slots=2)
    r = aaron.claim_seat(aaron.act("pray", "Shrine", params={"what": "Hound"})["result"])
    eng.session_for_token(token_in(r["paste"])).join()
    assert aaron.act("dismiss", "Shrine", params={"what": "Hound"})["result"] == [r["grant"]]  # the world's word
    assert w.embodied(i["Hound"]) is None and eng.session_for_token(token_in(r["paste"])) is None
    assert "offers" not in aaron.seats()
    pup = aaron.claim_seat(aaron.act("pray", "Shrine", params={"what": "Pup"})["result"])
    pup_s = eng.session_for_token(token_in(pup["paste"]))
    pup_s.join()
    gm.revoke(g["id"])  # the grant it was claimed under ends: so does the seat
    assert w.embodied(i["Pup"]) is None
    assert not [x for x in gm.grants() if x["id"] == pup["grant"]][0]["active"]


def test_a_hidden_seat_is_offered_in_the_open_to_its_holder():
    eng, w, i, gm, aaron, g = offering_world()
    gm.patch("Hound", {"hidden": True, "shown_to": []})
    aaron.act("pray", "Shrine", params={"what": "Hound"})
    assert [e["kind"] for e in aaron.history(limit=50)].count("seat_offered") == 1
