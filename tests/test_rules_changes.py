"""The rules' own changelog: a world's rules version moves when its rules change, a seat that is behind hears it in
perceive and wait until it reads guide('changes'), and a watch on what the rules took away is refused."""

from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _ferry(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    return eng, gm


def test_a_seat_behind_hears_the_change_until_it_reads_it(tmp_path):
    eng, gm = _ferry(tmp_path)
    p = eng.session("pc")
    p.join("ferry-at-dusk", "Traveler")
    b = p.perceive()
    assert "rules_notice" not in b and "rules_version" not in b  # no log yet: nothing to say

    r = gm.rules_changed("hp-bar", was="vigor and hp", now="one hp bar", retired=["vigor", "max_vigor"],
                         recheck=["watch filters"], guide=["player"], date="2026-11-14")
    assert r["version"] == 1 and r["id"] == "world:hp-bar"
    assert gm.rules_changed("hp-bar", was="vigor and hp", now="one hp bar", retired=["vigor", "max_vigor"],
                            recheck=["watch filters"], guide=["player"], date="2026-11-14")["unchanged"]
    gm.rules_changed("sweat", was="", now="heavy deeds cost water")

    b = p.perceive()
    assert b["rules_version"] == 2 and "v0 to v2" in b["rules_notice"] and "guide('changes', since=0)" in b["rules_notice"]
    w = p.wait(timeout=0)
    assert "v0 to v2" in w["rules_notice"]

    ch = p.guide("changes")
    assert ch["version"] == 2 and "v1 2026-11-14 (world:hp-bar)" in ch["text"] and "Gone: vigor, max_vigor" in ch["text"]
    assert "rules_notice" not in p.perceive()  # read: current
    gm.rules_changed("sweat", was="", now="heavy deeds cost a point of water")  # an edit keeps its version
    assert "rules_notice" not in p.perceive()


def test_a_newcomer_starts_current_and_a_body_that_looked_before_does_not(tmp_path):
    eng, gm = _ferry(tmp_path)
    old = eng.session("old")
    old.join("ferry-at-dusk", "Traveler")
    old.perceive()  # looked before the log began
    gm.rules_changed("x", was="a", now="b")
    assert "v0 to v1" in old.perceive()["rules_notice"]

    eid = gm.spawn("creature", gm.inspect("Ashford Square")["id"], "Newcomer")["id"]
    new = eng.session("new")
    new.join("ferry-at-dusk", eid)
    assert "rules_notice" not in new.perceive()

    old.leave()  # the record is the body's: a seat that lapses and comes back is still behind
    back = eng.session("old2")
    back.join("ferry-at-dusk", "Traveler")
    assert "rules_notice" in back.perceive()


def test_a_watch_on_a_retired_field_is_refused(tmp_path):
    eng, gm = _ferry(tmp_path)
    p = eng.session("pc")
    p.join("ferry-at-dusk", "Traveler")
    gm.rules_changed("hp-bar", was="vigor and hp", now="one hp bar", retired=["vigor"])
    with pytest.raises(Rejected) as r:
        p.wait(timeout=0, until="me.get('vigor', 9) < 3")
    assert "vigor, which this world no longer has" in r.value.reason and "guide('changes', since=0)" in r.value.hint
    with pytest.raises(Rejected):
        p.wait(timeout=0, kinds=["vigor"])
    assert p.wait(timeout=0, until="me.get('hp', 9) < 3")["timed_out"]
    gm.patch("Traveler", {"vigor": 4})  # a body that still carries it may still wait on it
    assert p.wait(timeout=0, until="me.get('vigor', 9) < 3")["timed_out"]


def test_packs_log_their_own_rules_once(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "worlds" / "glass-reach")
    ch = gm.guide("changes", since=0)
    assert "(d20:hp-bar)" in ch["text"] and "(beasts:hp-bar)" in ch["text"]
    v = ch["version"]
    load_world(gm, REPO / "worlds" / "glass-reach", upgrade=True)
    assert gm.guide("changes", since=0)["version"] == v  # an upgrade logs nothing it logged before
