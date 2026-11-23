"""A world can close dead seats (a corpse camera, found by a player, 2026-11-23): a player whose character died and who
took a new one could join the corpse again and watch its place from the dead. Death is the world's call, not the
engine's: with meta `dead_seats: "closed"` the one still in the body keeps it and nobody else gets it back; by default
dead seats stay as they were."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_a_corpse_left_for_a_new_character_is_no_seat():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    gm.patch("Guard", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    sam = eng.session_for_token(inv["token"])
    sam.join()
    gm.world.set_meta({"dead_seats": "closed"})
    gm.patch("Prisoner", {"dead": True})
    assert sam.join(entity="Prisoner")["you"]["id"] == i["Prisoner"]  # still in it: a reconnect keeps the view
    sam.join(entity="Guard")
    with pytest.raises(Rejected) as no:
        sam.join(entity="Prisoner")
    assert "dead" in no.value.reason
    rows = {s["name"]: s for s in sam.seats()["seats"]}
    assert rows["Prisoner"]["open"] is False
    other = eng.session_for_token(gm.invite("player", label="Ann")["token"])
    with pytest.raises(Rejected):
        other.join(entity="Prisoner")
    gm.world.set_meta({"dead_seats": None})  # the engine decides nothing about death: open, as before
    assert any(s["name"] == "Prisoner" and s["open"] for s in sam.seats()["seats"])
    sam.join(entity="Prisoner")
