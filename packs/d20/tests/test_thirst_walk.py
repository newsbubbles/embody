"""A thirst walk keeps clear of danger (d20, asked by the Glass Reach host, 2026-11-21). Ruhl's seat, held by a mind on
a watcher, went idle; its idle care walked the body off for water and through the people who had outlawed it. Every
thirst walk, a held seat's too, now goes around a side that outlawed the body, or waits."""

from packs.d20.tests.test_rules_d20 import outpost, state


def where(gm, name):
    return gm.world.get(gm.inspect(name)["parent"])["name"]


def test_a_held_seat_gone_idle_drinks_what_is_in_reach_then_walks_for_water_and_back():
    eng, gm, you = outpost()
    gm.spawn("person", "The Flats", "Walker", state={"faction": "the Garrison", "playable": True, "water": 10,
                                                     "max_water": 10, "hp": 40, "max_hp": 40})
    gm.world.set_meta({"idle_after": 50})
    eng.session("mind").join("outpost", "Walker")
    gm.clock(step=60)
    gm.clock(step=60)
    assert gm.world.idle(gm.inspect("Walker")["id"])
    gm.spawn("waterskin", "Walker", "Walker's skin", state={"left": 2})
    gm.patch("Walker", {"water": 4})
    gm.clock(step=60)
    assert state(gm, "Walker's skin")["left"] == 1 and where(gm, "Walker") == "The Flats"  # a skin in hand first
    gm.patch("Walker", {"water": 2})
    gm.patch("Walker's skin", {"left": 0})
    trail = []
    for _ in range(8):
        gm.clock(step=60)
        trail.append(where(gm, "Walker"))
    assert trail[0] == "The Road" and "The Flats" in trail[1:], trail  # then to water, and back to its post
    assert not state(gm, "Walker").get("post") and not state(gm, "Walker").get("water_from")


def test_a_held_seat_gone_idle_is_never_walked_back_to_a_post_its_player_left():
    # a player on a watcher was walked back to his template post, then the post was dropped (a report, 2026-11-23)
    eng, gm, you = outpost()
    gm.spawn("person", "The Flats", "Walker", state={"playable": True, "water": 10, "max_water": 10, "hp": 40,
                                                     "max_hp": 40, "post": gm.inspect("The Flats")["id"]})
    gm.world.set_meta({"idle_after": 50})
    me = eng.session("player")
    me.join("outpost", "Walker")
    me.act("go", "The Road")
    for _ in range(4):
        gm.patch("Walker", {"water": 10})  # the open road dries a body: keep it watered for this half
        gm.clock(step=60)
    assert where(gm, "Walker") == "The Road"  # idle and away from the post: it stays where its player left it
    assert state(gm, "Walker")["post"] == gm.inspect("The Flats")["id"]
    gm.patch("Walker", {"water": 2})  # thirsty and idle: to water, and back to the Road it left from
    trail = []
    for _ in range(8):
        gm.clock(step=60)
        trail.append(where(gm, "Walker"))
    went = trail.index("The Oasis")
    assert "The Road" in trail[went:] and "The Flats" not in trail, trail  # back to the Road it left from


def test_a_thirst_walk_goes_around_a_side_that_outlawed_the_body_or_waits():
    eng, gm, you = outpost()
    wid = gm.spawn("person", "The Flats", "Walker", state={"faction": "the Garrison", "water": 2,
                                                           "max_water": 10, "hp": 40, "max_hp": 40})["id"]
    gm.spawn("fighter", "The Road", "Carter", state={"faction": "the Traders"})
    gm.patch("the Traders", {"hostile": {wid: True}})
    for _ in range(3):
        gm.clock(step=60)
    assert where(gm, "Walker") == "The Flats"  # every way to water runs through the Road, where Carter stands: it waits
    gm.move("Carter", "The Oasis")
    trail = []
    for _ in range(8):
        gm.clock(step=60)
        trail.append(where(gm, "Walker"))
    assert trail[:3] == ["The Road", "The Yard", "The Keep"], trail  # the long way round, to the cistern
    assert "The Oasis" not in trail and state(gm, "Walker")["post"] == gm.inspect("The Flats")["id"], trail
    gm.move("Walker", "The Road")
    gm.patch("Walker", {"water": 2, "post": None})
    gm.clock(step=60)
    assert where(gm, "Walker") == "The Yard"  # Carter stands at the seep: around him
    gm.move("Walker", "The Road")
    gm.patch("Carter", {"down": True})
    gm.clock(step=60)
    assert where(gm, "Walker") == "The Oasis"  # a foe who is down guards nothing: the near way is open
