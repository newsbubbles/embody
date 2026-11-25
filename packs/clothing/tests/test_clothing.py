"""packs/clothing in a small yard beside a temple: layers that hide what is under them (marks too), order, sizes,
body plans, time and help, carry positions and hands, a cloak that hides a blade, worn things that do not leave a
body, a dress code, sewing and altering, and looking someone over."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
import importlib.util
from pathlib import Path

WORLD = {"id": "yard", "name": "Yard", "seed": 7, "description": "A yard and a temple.", "requires": ["village", "clothing"]}

def _pack():
    p = Path(__file__).resolve().parents[2] / "packs" / "clothing" / "pack.py"
    spec = importlib.util.spec_from_file_location("clothing_pack_for_test", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def define(s):
    m = _pack()
    acts = {"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
            "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
            "drop": {"script": "drop", "doc": "Put down", "targets": "thing", "scope": "held"},
            "give": {"script": "give", "doc": "Hand over", "targets": "creature", "scope": "here",
                     "params": {"item": "what"}}}
    acts.update(m.BODY_VERBS)
    s.define_schema("person", extends="creature", actions=acts)
    m.install_rules(s, s.summary()["root"])

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    temple = s.spawn("place", root, "Temple", state={"dress_code": {"needs": ["feet"], "bars": ["drawn", "masked"],
                                                                    "why": "The temple wants feet shod and faces bare"}})["id"]
    s.connect(yard, temple)
    marks = {"m1": {"where": "torso", "what": "a ship inked over the heart", "kind": "permanent", "band": "near", "since": 0},
             "m2": {"where": "arms", "what": "a ring of knots round the forearm", "kind": "permanent", "band": "near", "since": 0}}
    ada = s.spawn("person", yard, "Ada", state={"size": "m", "looks": {"marks": marks, "next": 3}})["id"]
    s.spawn("garment", ada, "Linen shirt", state={"garment": "shirt", "color": "white", "material": "linen"})
    s.spawn("garment", ada, "Oxblood coat", state={"garment": "coat", "look": "a long oxblood wool coat with brass buttons",
                                                   "detail": "one button is replaced with bone"})
    s.spawn("garment", ada, "Leather belt", state={"garment": "belt", "color": "brown", "material": "leather"})
    s.spawn("garment", ada, "Mail shirt", state={"garment": "mail", "size": "m", "don_s": 60})
    s.spawn("garment", ada, "Small mail", state={"garment": "mail", "size": "s"})
    s.spawn("garment", ada, "Wide coat", state={"garment": "coat", "size": "xl"})
    s.spawn("garment", ada, "Roomy shirt", state={"garment": "shirt", "size": "l"})
    s.spawn("garment", ada, "Grey cloak", state={"garment": "hooded_cloak", "color": "grey", "material": "wool"})
    s.spawn("garment", ada, "Felt hat", state={"garment": "hat", "color": "black", "material": "felt"})
    s.spawn("garment", ada, "Iron mask", state={"garment": "mask", "material": "iron"})
    s.spawn("garment", ada, "Boots", state={"garment": "boots", "material": "leather"})
    s.spawn("garment", ada, "Gloves", state={"garment": "gloves", "material": "leather"})
    s.spawn("thing", ada, "Short sword", state={"portable": True, "weapon": True, "damage": 3})
    s.spawn("thing", ada, "Greatsword", state={"portable": True, "weapon": True, "hands": 2, "bulk": 3})
    s.spawn("thing", ada, "Lantern", state={"portable": True})
    s.spawn("sewing_kit", ada, "Sewing kit")
    s.spawn("cloth", ada, "Grey wool", state={"count": 8, "color": "grey", "material": "wool"})
    _pack().make_garment(s, ada, "Riding boots", "boots", color="black", material="leather", cut="knee-high",
                         details=["brass buckles"])
    s.spawn("person", yard, "Bel", state={"size": "s"})
    s.spawn("person", yard, "Goat", state={"species": "goat", "looks": {"regions": ["head", "neck", "back", "legs", "tail"]}})
    s.clock(run=False)
'''


@pytest.fixture
def yard(tmp_path):
    for p in ("village", "clothing"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "yard").mkdir(parents=True)
    (tmp_path / "worlds" / "yard" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "yard")
    ada, bel = eng.session("ada"), eng.session("bel")
    ada.join("yard", "Ada")
    bel.join("yard", "Bel")
    return eng, gm, ada, bel


def kinds(eng, kind):
    w = eng.world("yard")
    return [e["payload"] for e in w.store.query("event", "world_id=? AND kind=?", (w.id, kind))]


def wait(gm, seconds):
    gm.clock(step=seconds)


def wear(s, gm, item, seconds=60):
    s.act("wear", item)
    wait(gm, seconds)


def attire(viewer, who="Ada"):
    return viewer.inspect(who)["state"].get("attire") or []


def looks(viewer, who="Ada"):
    return viewer.inspect(who)["state"].get("looks") or []


def test_a_garment_goes_on_with_time_and_shows_to_others(yard):
    eng, gm, ada, bel = yard
    r = ada.act("wear", "Linen shirt")
    assert r["result"]["seconds"] == 20
    assert attire(bel) == ["Getting into a white linen shirt."]  # half on, and the room can see it
    assert not gm.inspect("Linen shirt")["state"]["worn"]
    wait(gm, 30)
    assert attire(bel) == ["Torso, back and arms: a white linen shirt."]
    assert kinds(eng, "dressed")[0]["name"] == "Linen shirt"
    assert not gm.inspect("Ada")["state"].get("description")  # no hand on the description


def test_an_outer_layer_hides_what_is_under_it_and_its_marks(yard):
    eng, gm, ada, bel = yard
    assert any("ship inked" in l for l in looks(bel))
    wear(ada, gm, "Linen shirt")
    assert not any("ship inked" in l for l in looks(bel)) and not any("knots" in l for l in looks(bel))
    wear(ada, gm, "Oxblood coat")
    assert attire(bel) == ["Torso, back, arms and legs: a long oxblood wool coat with brass buttons."]  # the shirt is under it
    assert gm.inspect("Linen shirt")["state"]["concealed"] is True
    ada.act("adjust", "Oxblood coat", params={"how": "open"})
    assert attire(bel) == ["Torso, back, arms and legs: a long oxblood wool coat with brass buttons, open.",
                           "Torso: a white linen shirt."]
    ada.act("remove", "Oxblood coat")
    wait(gm, 10)
    ada.act("adjust", "Linen shirt", params={"how": "sleeves rolled"})
    assert any("knots" in l for l in looks(bel)) and not any("ship inked" in l for l in looks(bel))  # sleeves up, chest covered
    with pytest.raises(Rejected) as r:
        ada.act("adjust", "Linen shirt", params={"how": "hood_up"})
    assert "sleeves_rolled" in r.value.reason


def test_order_conflicts_and_one_garment_a_slot_a_layer(yard):
    eng, gm, ada, bel = yard
    wear(ada, gm, "Oxblood coat")
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Linen shirt")
    assert r.value.reason == "Oxblood coat is over the torso: take it off first, then put Linen shirt on under it"
    ada.act("remove", "Oxblood coat")
    wait(gm, 10)
    wear(ada, gm, "Linen shirt")
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Roomy shirt")
    assert "already wears Linen shirt on the torso at that layer" in r.value.reason
    wear(ada, gm, "Oxblood coat")
    with pytest.raises(Rejected) as r:
        ada.act("remove", "Linen shirt")
    assert r.value.reason == "Oxblood coat is over it: take that off first"


def test_sizes_fit_loose_or_not_at_all_and_armour_fits_exactly(yard):
    eng, gm, ada, bel = yard
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Wide coat")
    assert "cut for a XL frame" in r.value.reason
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Small mail")
    assert "armour must fit" in r.value.reason
    wear(ada, gm, "Roomy shirt")
    assert attire(bel) == ["Torso, back and arms: a shirt, a size too large."]


def test_a_body_plan_decides_what_it_can_wear(yard):
    eng, gm, ada, bel = yard
    gm.move("Gloves", "Goat")
    goat = eng.session("goat")
    goat.join("yard", "Goat")
    with pytest.raises(Rejected) as r:
        goat.act("wear", "Gloves")
    assert r.value.reason == "a goat has no hands for Gloves"


def test_heavy_armour_alone_takes_three_times_as_long_and_a_helper_needs_leave(yard):
    eng, gm, ada, bel = yard
    r = ada.act("wear", "Mail shirt")
    assert r["result"]["seconds"] == 180  # don_s 60, needs_help, alone
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Felt hat")
    assert r.value.reason == "Ada is still getting into Mail shirt"
    wait(gm, 120)
    assert not gm.inspect("Mail shirt")["state"]["worn"]
    wait(gm, 60)
    assert gm.inspect("Mail shirt")["state"]["worn"]
    ada.act("remove", "Mail shirt")
    wait(gm, 120)
    ada.act("give", "Bel", params={"item": "Mail shirt"})
    bel_id = gm.inspect("Bel")["id"]
    with pytest.raises(Rejected) as r:
        bel.act("dress", "Ada", params={"item": "Mail shirt"})
    assert r.value.reason == "Ada has not let you dress them (they can: let_dress)"
    ada.act("let_dress", params={"who": "Bel"})
    r = bel.act("dress", "Ada", params={"item": "Mail shirt"})
    assert r["result"]["seconds"] == 60  # with help, the plain time
    wait(gm, 60)
    assert gm.inspect("Mail shirt")["state"]["worn"] and kinds(eng, "dressed")[-1]["helper"] == bel_id
    bel.act("undress", "Ada", params={"item": "Mail shirt"})
    wait(gm, 60)
    assert gm.inspect("Mail shirt")["parent"] == bel_id  # what a helper takes off is in the helper's hands


def test_a_belt_carries_a_blade_two_hands_hold_a_greatsword_and_a_cloak_hides_the_hip(yard):
    eng, gm, ada, bel = yard
    with pytest.raises(Rejected) as r:
        ada.act("stow", "Short sword", params={"at": "hip_left"})
    assert r.value.reason == "nothing to hang it from at the left hip: wear a belt, a swordbelt or a baldric"
    wear(ada, gm, "Leather belt")
    ada.act("stow", "Short sword", params={"at": "hip_left"})
    with pytest.raises(Rejected) as r:
        ada.act("stow", "Greatsword", params={"at": "hip_right"})
    assert r.value.reason == "Greatsword does not hang at the right hip: it goes at the back"
    ada.act("hold", "Lantern", params={"hand": "left"})
    with pytest.raises(Rejected) as r:
        ada.act("hold", "Greatsword")
    assert "takes both hands: your left hand holds Lantern" in r.value.reason
    assert attire(bel) == ["Waist: a brown leather belt.", "Left hip: Short sword.", "Left hand: Lantern."]
    with pytest.raises(Rejected) as r:
        ada.act("remove", "Leather belt")
    assert r.value.reason == "Short sword hangs from Leather belt: hold or stow it elsewhere first"
    wear(ada, gm, "Grey cloak")
    assert "Left hip: Short sword." not in attire(bel)
    assert gm.inspect("Short sword")["state"]["concealed"] is True
    ada.act("adjust", "Grey cloak", params={"how": "thrown_back"})
    assert "Left hip: Short sword." in attire(bel)
    ada.act("stow", "Lantern", params={"at": "away"})
    ada.act("hold", "Greatsword")
    assert attire(bel)[-1] == "Both hands: Greatsword."
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Felt hat")
    assert r.value.reason.startswith("your hands are full (Greatsword)")


def test_a_worn_thing_does_not_leave_the_body_and_a_given_one_leaves_the_attire(yard):
    eng, gm, ada, bel = yard
    wear(ada, gm, "Felt hat")
    for verb, target, params in (("drop", "Felt hat", None), ("give", "Bel", {"item": "Felt hat"})):
        with pytest.raises(Rejected) as r:
            ada.act(verb, target, params=params)
        assert r.value.reason == "you are wearing Felt hat: take it off first"
    wear(ada, gm, "Leather belt")
    ada.act("stow", "Short sword", params={"at": "hip_right"})
    ada.act("give", "Bel", params={"item": "Short sword"})
    assert not any("Short sword" in l for l in attire(bel))
    sword = gm.inspect("Short sword")["state"]
    assert not sword.get("stowed_at") and not sword.get("on")
    gm.move("Felt hat", "Bel")  # an author's hand, past every verb: the next look at Ada is still true
    ada.act("look_over", "Ada")
    assert attire(bel) == ["Waist: a brown leather belt."]


def test_the_temple_door_reads_what_shows(yard):
    eng, gm, ada, bel = yard
    with pytest.raises(Rejected) as r:
        ada.act("go", "Temple")
    assert r.value.reason == "The temple wants feet shod and faces bare: nothing covers the feet"
    wear(ada, gm, "Boots")
    wear(ada, gm, "Iron mask")
    ada.act("hold", "Short sword")
    with pytest.raises(Rejected) as r:
        ada.act("go", "Temple")
    assert r.value.reason.endswith("a weapon is drawn and the face is covered")
    ada.act("stow", "Short sword", params={"at": "away"})
    ada.act("remove", "Iron mask")
    wait(gm, 30)
    assert ada.act("go", "Temple")["ok"]


def test_sewing_spends_cloth_and_makes_what_was_asked(yard):
    eng, gm, ada, bel = yard
    with pytest.raises(Rejected) as r:
        ada.act("sew", "Sewing kit", params={"name": "Mail coif", "garment": "helm"})
    assert "a needle does not make armour" in r.value.reason
    with pytest.raises(Rejected) as r:
        ada.act("sew", "Sewing kit", params={"name": "Wool belt", "garment": "belt"})
    assert "sewn from leather, not wool" in r.value.reason
    ada.act("sew", "Sewing kit", params={"name": "Grey hood coat", "garment": "coat", "hood": True,
                                         "details": ["horn toggles"], "detail": "the hem is double-stitched"})
    wait(gm, 3600)
    coat = gm.inspect("Grey hood coat")["state"]
    assert coat["material"] == "wool" and coat["color"] == "grey" and coat["size"] == "m"
    assert set(coat["modes"]) == {"open", "hood_up"}
    assert gm.inspect("Grey wool")["count"] == 2  # 6 spent: torso 2, back 1, arms 1, hangs 1, outer 1
    wear(ada, gm, "Grey hood coat")
    assert attire(bel) == ["Torso, back, arms and legs: a grey wool coat with horn toggles."]
    with pytest.raises(Rejected) as r:
        ada.act("sew", "Sewing kit", params={"name": "Second coat", "garment": "coat"})
    assert r.value.reason == "this takes 6 of Grey wool: you have 2"


def test_altering_takes_a_needle_half_an_hour_and_one_size(yard):
    eng, gm, ada, bel = yard
    with pytest.raises(Rejected) as r:
        ada.act("alter", "Wide coat", params={"to": "m"})
    assert r.value.reason == "one size at a time: Wide coat is XL"
    ada.act("alter", "Roomy shirt", params={"to": "m"})
    wait(gm, 1800)
    assert gm.inspect("Roomy shirt")["state"]["size"] == "m"
    gm.move("Sewing kit", "Bel")
    with pytest.raises(Rejected) as r:
        ada.act("alter", "Wide coat", params={"to": "l"})
    assert "you need a sewing tool in hand" in r.value.reason


def test_a_hood_hides_the_hat_and_looking_over_shows_the_close_detail(yard):
    eng, gm, ada, bel = yard
    wear(ada, gm, "Felt hat")
    wear(ada, gm, "Oxblood coat")
    wear(ada, gm, "Grey cloak")
    ada.act("adjust", "Grey cloak", params={"how": "hood_up"})
    assert not any("felt hat" in l for l in attire(bel))
    seen = bel.act("look_over", "Ada")["result"]
    assert any(l.endswith("brass buttons. One button is replaced with bone.") for l in seen["attire"])  # no spots: close enough
    mine = ada.act("look_over", "Ada")["result"]["attire"]
    assert any(l.startswith("Head: a black felt hat") and "(under Grey cloak)" in l for l in mine)


def test_a_beast_wears_on_its_own_plan_and_the_fallen_need_no_leave(yard):
    eng, gm, ada, bel = yard
    gm.spawn("garment", "Ada", "Red ribbon", state={"slots": ["tail"], "look": "a red ribbon", "accessory": True})
    gm.patch("Goat", {"down": True})
    ada.act("dress", "Goat", params={"item": "Red ribbon"})
    wait(gm, 10)
    assert attire(bel, "Goat") == ["Tail: a red ribbon."]  # a region of its own plan is a slot
    with pytest.raises(Rejected) as r:
        ada.act("dress", "Bel", params={"item": "Linen shirt"})
    assert "has not let you" in r.value.reason
    gm.patch("Bel", {"down": True})
    ada.act("dress", "Bel", params={"item": "Linen shirt"})
    wait(gm, 30)
    assert attire(bel, "Bel") == ["Torso, back and arms: a white linen shirt."]


def test_an_author_makes_a_cloak_and_boots_in_one_call_and_a_new_kind_with_define_schema(yard):
    eng, gm, ada, bel = yard
    gm.spawn("hooded_cloak", "Bel", "Travelling cloak", state={"color": "grey", "material": "wool", "size": "s"})
    cloak = gm.inspect("Travelling cloak")
    assert cloak["type"] == "hooded_cloak" and cloak["state"]["layer"] == "outer" and "hood_up" in cloak["state"]["modes"]
    wear(bel, gm, "Travelling cloak")
    bel.act("adjust", "Travelling cloak", params={"how": "hood_up"})
    assert attire(ada, "Bel") == ["Head, shoulders, torso, back and arms: a grey wool hooded cloak, hood up."]
    wear(ada, gm, "Riding boots")  # made in the build with make_garment
    assert attire(bel) == ["Feet: knee-high black leather boots with brass buckles."]
    gm.define_schema("duster", extends="garment", state={"garment": "duster", "slots": ["torso", "back", "arms"],
                                                         "hangs": ["legs"], "layer": "outer", "material": "oilskin"})
    gm.spawn("duster", "Ada", "Long duster", state={"color": "tan"})
    wear(ada, gm, "Long duster")
    assert "Torso, back, arms and legs: a tan oilskin duster." in attire(bel)
    gm.spawn("garment", "Ada", "Odd scarf", state={"slots": ["nek"]})
    with pytest.raises(Rejected) as r:
        ada.act("wear", "Odd scarf")
    assert r.value.reason.startswith("Odd scarf names a slot no body here has (nek)")


def test_garment_state_checks_what_an_author_writes():
    import importlib.util
    spec = importlib.util.spec_from_file_location("clothing_pack_unit", REPO / "packs" / "clothing" / "pack.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.garment_state("boots", color="black") == ("boots", {"color": "black"})
    assert m.garment_state("duster", slots=["torso"], layer="outer")[0] == "garment"
    assert m.garment_state(slots=["tail"], regions=["tail"])[1]["slots"] == ["tail"]
    for kw, words in (({"kind": "duster"}, "no kind the pack knows"), ({"kind": "cloak", "slots": ["sholders"]}, "sholders"),
                      ({"kind": "coat", "layer": "outerwear"}, "layer is one of"), ({"kind": "coat", "size": "huge"}, "size"),
                      ({"kind": "coat", "modes": {"open": {"shows": []}}}, "mode 'open'")):
        with pytest.raises(ValueError) as e:
            m.garment_state(**kw)
        assert words in str(e.value)
    assert len(m.KINDS) == 89
