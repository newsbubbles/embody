"""A line a player is owed reaches the mind (asked by a world builder, 2026-11-22): a seated mind whose cursor fell
behind (waits that timed out in a busy turn-based world) still hears the line in its wait, and its own perceive shows
the line as `owed` until it answers, as the host's minds() does."""

from tests.test_minds import ferry


def seated():
    eng, gm = ferry()
    gm.clock(turn=10)
    for name in ("Traveler", "Mara"):
        gm.patch(name, {"playable": True})
    p = eng.session_for_token(gm.invite("player", entity="Traveler", label="Sam")["token"])
    m = eng.session_for_token(gm.invite("mind", entity="Mara", label="mara-mind")["token"])
    p.join("ferry-at-dusk", "Traveler")
    m.join("ferry-at-dusk", "Mara")
    m.wait(timeout=0.1)
    return eng, gm, p, m


def test_a_wait_far_behind_still_hears_the_line():
    eng, gm, p, m = seated()
    w = gm.world
    assert m.wait(until="heard('never said')", timeout=0.2)["timed_out"]  # the cursor stays put
    for _ in range(1200):  # thousands of events touching her since, more than one read takes
        p.act("check", "Traveler")
    p.say("Mara, are you there?", to="Mara")
    r = m.wait(until="heard('are you there')", timeout=5)
    assert r["fired"] and any((e.get("payload") or {}).get("text") == "Mara, are you there?" for e in r["events"])
    assert r["cursor"] <= w.store.next_seq(w.id) - 1


def test_perceive_shows_the_owed_line_until_it_is_answered():
    eng, gm, p, m = seated()
    assert "owed" not in m.perceive()
    p.say("Mara, how much for the crossing?", to="Mara")
    owed = m.perceive()["owed"]
    assert owed["by"] == "Traveler" and owed["text"] == "Mara, how much for the crossing?"
    row = next(r for r in gm.minds()["minds"] if r["name"] == "Mara")
    assert row["owed"]["text"] == owed["text"]  # the host's table agrees
    m.say("Two coins, and mind the rail.", to="Traveler")
    assert "owed" not in m.perceive()
    assert "owed" not in next(r for r in gm.minds()["minds"] if r["name"] == "Mara")


def test_perceive_after_a_backlog_shows_the_newest_events():
    eng, gm, p, m = seated()
    for _ in range(100):
        p.act("check", "Traveler")
    p.say("Mara, last call.", to="Mara")
    texts = [(e.get("payload") or {}).get("text") for e in m.perceive(events=10)["events"]]
    assert "Mara, last call." in texts
