"""A hidden place's way out shows only to the ones it is known to: by id, or by faction (string or list)."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_a_hidden_way_shows_only_to_those_who_know_it():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.spawn("place", "Two Rooms", name="Tunnel", state={"hidden": True, "known_to": [i["Guard"]]})
    gm.connect("Hall", "Tunnel")
    gm.move("Prisoner", "Hall")
    sam, nate = eng.session("sam"), eng.session("nate")
    sam.join("two-rooms", "Guard")
    nate.join("two-rooms", "Prisoner")

    def sees(s):
        b = s.perceive()
        return ("Tunnel" in {x["name"] for x in b["exits"]},
                any(a["target_name"] == "Tunnel" for a in b["affordances"]))

    assert sees(sam) == (True, True) and sees(nate) == (False, False)
    gm.patch("Prisoner", {"faction": "keth"})
    gm.patch("Tunnel", {"known_to": "keth"})
    assert sees(nate) == (True, True) and sees(sam) == (False, False)
    gm.patch("Tunnel", {"known_to": ["keth", i["Guard"]]})
    assert sees(nate) == (True, True) and sees(sam) == (True, True)
    gm.patch("Tunnel", {"hidden": False, "known_to": None})
    gm.patch("Prisoner", {"faction": None})
    assert sees(nate) == (True, True)
