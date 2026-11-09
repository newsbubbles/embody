"""The Glass Reach: a desert fief with table-top rules, nine places, seven NPCs, two seats to play.

    uv run embody --as gm --author load worlds/glass_reach.py
    uv run embody --as you join glass-reach "Reeve Ansel Varrick"
    uv run embody --as you perceive

An original setting with bones in the shape of Dune: a hard desert, a precious thing in the sand, a
people who know the water, a house newly given the fief, a house that lost it and left a blade behind, a
guild that carries and sells, and something under the dunes that comes to rhythm. Said once, so the
borrowing is plain; after this the Reach is its own.

Every rule is an action or a listener from `worlds/rules_d20.py`: checks against a difficulty, opposed
attacks, wards that stop fast blades, brace, yield, kill, threaten, parley, duels whose ring holds, water
that runs out, factions that remember, the Thresher that comes when the sand is walked loud. The narrator
reads the numbers off the events and tells them; the engine decides them.

The situation. House Varrick has held Scar Gate for nine days by the Crown's writ. The Hold's cistern is
cracked and holds a week of water. The Keth, the desert people, keep the Deepwell under Red Ridge and
have had no truce with the Hold since House Dreyer poisoned a well. A Dreyer blade, Dram Hollis, stands in
the Hold's own yard under a Carrier's papers, with orders to kill the reeve in a duel the Hold's honor
cannot refuse. Ossa the Carrier sells water at a thief's price and buys emberglass. Emberglass lies in
veins on the Glass Flats, and harvesting it wakes the Thresher.

Two seats with goals: Reeve Ansel Varrick (water, terms with the Keth, find who Dreyer left behind) and
Sefa of the Keth (learn what the reeve wants, keep the Deepwell secret unless they earn it, bring water
back to Taan). The story checks facts, not a stage:
  find the Deepwell (a survival or lore check on Red Ridge against 15, or Nico shows a friend of the Keth)
  -> terms with Elder Taan (parley, with standing not below -1)  ->  truce
  Dram walks into the ring at t=240 and calls the reeve out; down him, kill him or make him yield  ->  his letter
  truce + Dram dealt with  ->  the Hold stands. The reeve dead  ->  Scar Gate falls to Dreyer within the month.

Timers: heat at 200, Dram at 240, dusk at 500, the cistern fails at 600. Play is turn-based, three seconds a turn.

Split like the ferry: define(s), populate(s), upgrade(s), build(s).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ferry_at_dusk import DROP, GIVE, PERSON_ON, READ, TAKE, TALK  # noqa: E402
from rules_d20 import define_rules, install_rules  # noqa: E402

# ---- scripts of this world -------------------------------------------------------------

GO = '''
def check(ctx):
    here = ctx.actor.parent
    if ctx.actor.state.down:
        return "you are down: crawl"
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            if ctx.target.state.hidden and ctx.target.state.known_to != ctx.actor.state.faction:
                return "you do not know the way"
            return True
    return "there is no way there from here"

def apply(ctx):
    here = ctx.actor.parent
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id, quiet=False)
    for p in ctx.children(here, "creature"):
        if p.state.follows == ctx.actor.id and not p.state.down and not p.state.dead:
            ctx.move(p, ctx.target)
            ctx.emit("arrived", target=ctx.target, reach=1, who=p.id, place=ctx.target.id, following=ctx.actor.id, quiet=False)
'''

CREEP = '''
def check(ctx):
    here = ctx.actor.parent
    if ctx.actor.state.down:
        return "you are down: crawl"
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            if ctx.target.state.hidden and ctx.target.state.known_to != ctx.actor.state.faction:
                return "you do not know the way"
            return True
    return "there is no way there from here"

def apply(ctx):
    # the broken step: twice as long, and the sand does not count it
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id, quiet=True)
'''

WARD_TOGGLE = '''
def check(ctx):
    if ctx.self.parent.id != ctx.actor.id:
        return "you must hold it"
    return True

def apply(ctx):
    on = not ctx.self.state.on
    ctx.patch(ctx.self, {"on": on, "description": ctx.self.state.description_on if on else ctx.self.state.description_off})
    ctx.emit("ward_" + ("on" if on else "off"), target=ctx.actor, reach=1)
'''

OSSA_ON = '''
def on(ctx, event):
    # emberglass handed to Ossa buys a full skin; anything else she keeps and says so
    if event.target != ctx.self.id:
        return
    item = ctx.get(event.payload.get("item"))
    buyer = ctx.get(event.payload.get("by"))
    if item is None or buyer is None:
        return
    if item.state.kind == "ember":
        ctx.destroy(item)
        ctx.spawn("waterskin", buyer, name="Full waterskin", state={"left": 3})
        ctx.patch(ctx.self, {"ember_bought": int(ctx.self.state.ember_bought or 0) + 1})
        ctx.say("Fair glass. A full skin, and no questions where you dug it.", to=buyer.id)
        ctx.emit("traded", target=buyer, reach=1, by=ctx.self.id, got="Full waterskin", gave="Emberglass")
    else:
        ctx.say("I take glass, friend. Keep your trinkets.", to=buyer.id)
'''

STORY = '''
def scene(ctx, place, text):
    ctx.emit("scene", target=place, reach=1, text=text)

def keth_standing(ctx, who, keth):
    for e in ctx.edges(who, "standing", "out"):
        if e["target"] == keth.id:
            return int(e["data"].get("value") or 0)
    return 0

def reveal_well(ctx, st, how):
    well = ctx.get(st.deepwell)
    if well is None or not well.state.hidden:
        return
    ctx.patch(well, {"hidden": False})
    ctx.patch(ctx.find(type="story", limit=1)[0], {"found_well": True, "well_found_by": how})
    if how == "nico":
        scene(ctx, st.ridge, "Nico looks at you a long moment, then points down the back of the ridge, to a shadow in the rock you had taken for nothing. A way down.")
    else:
        scene(ctx, st.ridge, "Goat sign, then a worn lip of stone, then cool air coming up out of the rock. There is a way down the back of the ridge.")

def finish_if_done(ctx, story):
    st = story.state
    if st.truce and st.dram_done and not st.done:
        ctx.patch(story, {"done": True})
        ctx.patch(ctx.root(), {"story": "complete"})
        scene(ctx, st.hold, "Water comes up the Salt Road under a Keth flag, and the Carrier's clerk is gone from the yard. Scar Gate stands. For now, it stands.")

def on(ctx, event):
    story = ctx.find(type="story", limit=1)[0]
    st = story.state
    k = event.kind
    p = event.payload
    if k == "arrived":
        dram = ctx.get(st.dram)
        if dram is not None and dram.state.waiting and dram.parent is not None and p.get("place") == dram.parent.id and p.get("who") == st.ansel:
            reeve = ctx.get(st.ansel)
            if not reeve.state.down and not ctx.relations(reeve, "duel") and not ctx.relations(dram, "duel"):
                ctx.relate("duel", [dram.id, reeve.id], {"place": dram.parent.id, "since": ctx.t, "public": True})
                ctx.patch(dram, {"waiting": False})
                ctx.emit("challenged", target=reeve, reach=1, by=dram.id, place=dram.parent.id, ring=True)
                scene(ctx, dram.parent, "Dram Hollis turns in the ring and draws. 'Reeve Varrick. Dram Hollis, of the Carriers' book, lately of other books. Step in, or be known for stepping back.'")
        if p.get("place") == st.ridge and not st.seen_ridge:
            ctx.patch(story, {"seen_ridge": True})
            scene(ctx, st.ridge, "From up here the Reach is a sheet of black glass with red dunes walking across it. The Hold is a thumbprint to the south. Nothing moves, except one thin line of smoke from somewhere under the rock.")
        elif p.get("place") == st.flats and not st.seen_flats:
            ctx.patch(story, {"seen_flats": True})
            scene(ctx, st.flats, "Glass underfoot, warm already. Veins of dull red show where the dunes have pulled back. Every step rings.")
    elif k == "checked":
        if p.get("place") == st.ridge and p.get("success") and str(p.get("skill")) in ["survival", "lore", "track", "search"] and int(p.get("dc") or 0) >= 15:
            reveal_well(ctx, st, "found")
    elif k == "talked":
        if event.target == st.nico:
            about = str(p.get("about", "")).lower()
            asker = ctx.get(p.get("by"))
            keth = ctx.get(st.keth)
            if asker is not None and ("water" in about or "well" in about or "cistern" in about or "keth" in about):
                if asker.state.faction == "the Keth" or keth_standing(ctx, asker, keth) >= 1:
                    reveal_well(ctx, st, "nico")
    elif k == "agreed":
        if event.target == st.taan and not st.truce:
            offer = str(p.get("offer", "")).lower()
            who = ctx.get(p.get("by"))
            keth = ctx.get(st.keth)
            if who is not None and keth_standing(ctx, who, keth) >= -1 and ("water" in offer or "truce" in offer or "well" in offer or "ember" in offer or "glass" in offer or "share" in offer or "peace" in offer):
                side = ctx.find(type="faction", name=who.state.faction, limit=1)
                parts = [keth.id] + ([side[0].id] if side else [who.id])
                ctx.relate("truce", parts, {"terms": str(p.get("offer")), "since": ctx.t, "public": True})
                ctx.patch(story, {"truce": True})
                ctx.patch(ctx.get(st.taan), {"dialog": {"water|well|truce": "We have terms. Keth water goes up the road at dusk and the Flats stay quiet. Keep it so."}})
                scene(ctx, st.deepwell, "Taan puts both palms flat on the wet stone. 'Then it is water between us. Say it at the Hold the way I say it here.'")
                finish_if_done(ctx, story)
            else:
                scene(ctx, st.deepwell, "Taan hears you out and shakes her head once. 'That is not terms. That is a man asking.'")
    elif k == "dram_moves":
        dram = ctx.get(st.dram)
        if dram is None or dram.state.down or dram.state.dead or st.dram_done:
            return
        ctx.move(dram, st.yard)
        ctx.emit("arrived", target=st.yard, reach=-1, who=dram.id, place=st.yard, quiet=False)
        ctx.patch(dram, {"waiting": True, "description": "The Carrier's clerk, except that the clerk's coat is off and the blade on his hip is not a clerk's."})
        reeve = ctx.get(st.ansel)
        if reeve is not None and reeve.parent.id == st.yard and not reeve.state.down and not ctx.relations(reeve, "duel"):
            ctx.relate("duel", [dram.id, reeve.id], {"place": st.yard, "since": ctx.t, "public": True})
            ctx.patch(dram, {"waiting": False})
            ctx.emit("challenged", target=reeve, reach=1, by=dram.id, place=st.yard, ring=True)
            scene(ctx, st.yard, "Dram Hollis steps into the ring and draws. 'Reeve Varrick. Dram Hollis, of the Carriers' book, lately of other books. Step in, or be known for stepping back.'")
        else:
            scene(ctx, st.yard, "Dram Hollis walks into the ring, shrugs off the clerk's coat, draws, and asks the yard for the reeve by name.")
            scene(ctx, st.hold, "Word comes in from the yard: the Carrier's clerk is in the ring with a blade out, asking for the reeve.")
    elif k in ["downed", "killed", "yielded"]:
        who = event.target
        if who == st.dram and not st.dram_done:
            ctx.patch(story, {"dram_done": True, "dram_how": k})
            scene(ctx, ctx.get(who).parent, "Something falls out of Dram's coat as he goes down: a folded letter under a seal the color of old blood.")
            ctx.spawn("letter", ctx.get(who).parent, name="Sealed letter", state={
                "text": "H. The reeve in the ring, before the moon turns. Keep the Keth thirsty: no truce, whatever it costs. The Flats are ours when the Hold is empty. Burn this. D.",
                "description": "Folded twice, sealed in dark red wax with a sigil of a well and a bar across it."})
            finish_if_done(ctx, story)
        elif who == st.ansel and k == "killed" and not st.reeve_dead:
            ctx.patch(story, {"reeve_dead": True, "done": True})
            ctx.patch(ctx.root(), {"story": "lost"})
            scene(ctx, ctx.get(who).parent, "The reeve of Scar Gate is dead on the Hold's own sand. Within the month a Dreyer banner will hang from the gate, and the Keth will go on drinking in the dark.")
    elif k == "heat":
        ctx.patch(ctx.root(), {"ambient": {"time_of_day": "noon", "weather": "white glare, heat shimmer off the glass", "light": "blinding"}})
        scene(ctx, st.flats, "The glare comes up off the glass until there is no ground, only light.")
    elif k == "dusk":
        ctx.patch(ctx.root(), {"ambient": {"time_of_day": "dusk", "weather": "the heat going out of the air fast", "light": "red, long shadows"}})
        scene(ctx, st.hold, "The sun drops behind Red Ridge and the Hold's walls start to tick as they cool.")
    elif k == "cistern_cracks":
        cistern = ctx.get(st.cistern)
        if cistern is not None and int(cistern.state.left or 0) > 0:
            ctx.patch(cistern, {"left": 0, "description": "A stone tank with a crack you could put your hand in. Dry. The floor of it is already warm."})
            scene(ctx, st.hold, "A sound like a shot from under the floor. The cistern's crack has run, and what water was left is going into the sand.")
'''

# ---- what there is ---------------------------------------------------------------------

POLICY = {
    "fixed": [
        "the rules: d20 + stat + skill against a difficulty, opposed attacks, a ward stops fast blows and the slow blade passes it, "
        "water runs out, the Thresher comes to rhythm on deep sand, the ring holds during a duel; the engine rolls, the narrator tells",
        "the seven NPCs, the nine places and the four sides",
        "the Deepwell is hidden until found or shown; Dram Hollis is Dreyer's and calls the reeve out at t=240; the cistern fails at t=600",
        "nobody but a Keth knows the way down to the Deepwell without finding it",
    ],
    "fill": True,    # small things a hold or a camp would have may be spawned with state {"improvised": true}
    "voice": True,   # NPCs may say free lines through say_as when their table has no answer, in their own voice
    "numbers": "say the roll when a player asks or when it decides something; otherwise tell what it meant",
}

AMBIENT = {"time_of_day": "morning", "weather": "clear, the heat already building", "light": "hard white"}

FACTIONS = ["House Varrick", "the Keth", "House Dreyer", "the Carriers"]

ANSEL = {"role": "reeve", "faction": "House Varrick", "body": 2, "wits": 3, "will": 3,
         "skills": {"blade": 1, "parley": 2, "lore": 1, "resolve": 1},
         "description": "Reeve of Scar Gate by the Crown's writ, nine days in the post, sand in everything already.",
         "brief": "You are Ansel Varrick, reeve of a fief your house was handed and nobody wanted. The cistern is cracked. "
                  "The Keth have the water and no reason to share it. Somebody Dreyer left behind is in your walls. "
                  "You have a blade you can use a little, a tongue you can use well, a ward, and Captain Ruhl."}

SEFA = {"role": "scout", "faction": "the Keth", "body": 3, "wits": 3, "will": 2,
        "skills": {"blade": 2, "stealth": 2, "survival": 3},
        "description": "A Keth scout in sand-colored cloth, a knife at the small of her back, eyes on the Hold.",
        "brief": "You are Sefa of the Keth. Taan sent you up the ridge to watch the new reeve. Dreyer poisoned the old well "
                 "and the Keth have not shared water with the Hold since. The Deepwell is yours to keep secret or to show. "
                 "You know the Flats and how to walk them quiet."}

RUHL = {"faction": "House Varrick", "body": 4, "wits": 2, "will": 3, "skills": {"blade": 3, "resolve": 2}, "vigor": 8, "max_vigor": 8,
        "description": "Captain of the Hold's guard. Grey, square, a scar across the knuckles of the sword hand.",
        "default_line": "Ruhl grunts. 'Reeve's business, not mine. Ask me about the walls or the men.'",
        "dialog": {
            "wall|walls|gate|hold|defend": "'Walls are sound. Water is not. Twelve days of it in the cistern if nobody washes, and nobody washes.'",
            "men|guard|guards|garrison": "'Nine men and me. Six who can hold a blade. The clerk from the Carriers watches them drill like a man counting.'",
            "clerk|carrier|dram|hollis": "'Came with the water convoy, stayed when it left. Papers in order. I do not like how he stands.'",
            "keth|desert|water|well": "'The Keth have water under the rock somewhere north. Dreyer tried to take it and poisoned a well instead. They will not talk to a Hold man. Might talk to you.'",
            "thresher|sand|flats|dune": "'Walk the Flats loud and the sand comes up and eats you. The Keth walk it like they are dancing. Learn that or stay off the glass.'",
            "fight|duel|ring|challenge": "'The yard is a ring by old law. Called out in it, a reeve answers or the men stop being his. I did not make the law.'",
        }}

DRAM = {"faction": "House Dreyer", "body": 3, "wits": 3, "will": 3, "skills": {"blade": 3, "stealth": 1, "resolve": 2}, "vigor": 7, "max_vigor": 7,
        "secret": ["dialog", "gives", "gave", "faction", "orders"], "orders": "the reeve, in the ring, before the moon turns",
        "waiting": False,
        "description": "The Carriers' clerk, a lean man with ink on two fingers and no ink on the rest.",
        "default_line": "Hollis smiles with the lower half of his face. 'Guild business, Reeve. Dull as dust.'",
        "dialog": {
            "papers|guild|carrier|clerk|book": "'Carriers' book, all in order. Water in, glass out, the Guild's cut. I count.'",
            "dreyer|house": "'Dreyer? Gone. Lost the writ, lost the Hold, lost the water. A house that loses is a story, not a house.'",
            "ring|duel|fight|blade": "'A fine old custom, the ring. Any man may call. Any reeve must answer. I read it in the Hold's own book.'",
        }}

OSSA = {"faction": "the Carriers", "body": 2, "wits": 4, "will": 3, "skills": {"parley": 3, "lore": 2, "resolve": 1},
        "ember_bought": 0,
        "description": "Ossa the Carrier, broad and brown, a ledger on a cord round her neck and a water-tally on the other.",
        "default_line": "Ossa taps the ledger. 'Water in, glass out. Talk to me in those two words and we understand each other.'",
        "dialog": {
            "water|skin|drink|buy|price": "'Water is a full skin for one shard of glass. Hand me the glass and the skin is yours. No glass, no water; the Guild does not run a well.'",
            "glass|ember|emberglass|flats": "'Veins on the Flats, dull red, you cannot miss them. Dig quiet. The last fool who dug loud I never had to pay.'",
            "keth|desert|deepwell": "'The Keth have water the Guild would give a year's cut to carry. They do not sell. Whoever gets terms with them owns this road.'",
            "dram|hollis|clerk": {"line": "'My clerk? He came with my convoy on good paper.' She does not look at you. 'Good paper is cheap in the Reach.'",
                                  "if_state": {"ember_bought": 0}, "else": "'Hollis is no clerk of mine. The paper was Dreyer's. I took the glass and said nothing, and now I have said it.'"},
            "dreyer": "'Dreyer had this Hold eleven years and the Guild carried for them. Then the well. Then the writ went to Varrick. The Guild carries for whoever holds the gate.'",
        }}

TAAN = {"faction": "the Keth", "body": 1, "wits": 4, "will": 5, "skills": {"lore": 3, "resolve": 3, "parley": 2},
        "description": "Elder Taan, small and very old, sitting where the drip from the roof lands in a stone cup.",
        "default_line": "Taan lets the drip fall three times before she answers. 'You came a long way down to ask me nothing.'",
        "dialog": {
            "water|well|deepwell|cistern|share": "'This water was here before the Hold and will be here after. Dreyer wanted it and put poison in the Low Well. You want it too. Tell me why you are not Dreyer, in terms I can carry.'",
            "truce|terms|peace|treaty": "'Terms are not a wish. Say what the Hold gives and what it stays away from, and we will see if it weighs anything.'",
            "dreyer|poison": "'Four of mine died at the Low Well, two of them children. The Hold did that, whatever name it wore. I do not forget it. I may set it down.'",
            "thresher|sand|flats": "'The Thresher is the Reach's own. Walk the broken step and it does not hear you. Dig the glass and it does. Your people do not know that yet.'",
            "sefa|scout|nico": "'My scouts watch you from the ridge. If you are here, one of them let you be here. Remember that.'",
        }}

NICO = {"faction": "the Keth", "body": 2, "wits": 3, "will": 2, "skills": {"stealth": 3, "survival": 3, "blade": 1},
        "description": "A Keth scout, young, cross-legged on the rock with a long glass in one hand, watching the Hold.",
        "default_line": "Nico does not take the glass from his eye. 'Hm.'",
        "dialog": {
            "water|well|deepwell|cistern|keth": "'Water is for the Keth and the Keth's friends.' He lowers the glass. 'Are you a friend? Friends bring something.'",
            "hold|reeve|varrick": "'Nine days you have been in there. Nine days and no patrol on the Flats. Either you are careful or you are afraid. Taan wants to know which.'",
            "thresher|flats|sand|glass": "'Loud step, two, three, and it turns. Broken step and you are wind. You hear the hum, you run for rock and you do not look back.'",
            "dram|clerk|carrier": "'The one in the yard who watches the drill? He walks like a blade. He is nobody's clerk.'",
        }}

GOALS = {
    "Reeve Ansel Varrick": [
        ("Water for the Hold before the cistern fails", "nine men and the Keth between you and the dry"),
        ("Terms with the Keth", "no truce has held since Dreyer poisoned the Low Well"),
        ("Find who Dreyer left behind in the Hold", "a house does not lose a fief and leave nothing in the walls"),
    ],
    "Sefa of the Keth": [
        ("Learn what the new reeve wants with the Flats", "Taan needs to know careful or afraid"),
        ("Keep the Deepwell secret unless they earn it", "the Low Well is a grave"),
        ("Bring a skin of water back to Taan", "you left with one and she counts"),
    ],
    "Captain Ruhl": [("Keep the reeve alive", "the men follow a live reeve")],
    "Dram Hollis": [("The reeve, in the ring, before the moon turns", "Dreyer pays on the body")],
    "Ossa the Carrier": [("Glass in, water out, the Guild's cut on both", "the Guild carries for whoever holds the gate")],
    "Elder Taan": [("Keep the Deepwell", "the Low Well is a grave"), ("Terms that weigh something, if the Hold brings any", "children should not drink in the dark")],
    "Nico": [("Watch the Hold, report to Taan", "careful or afraid")],
}

STANDINGS = {
    "Reeve Ansel Varrick": {"House Varrick": 5, "the Keth": -1, "House Dreyer": -3, "the Carriers": 0},
    "Sefa of the Keth": {"the Keth": 5, "House Varrick": -2, "House Dreyer": -5, "the Carriers": 0},
}

KNOWS = [
    ("Reeve Ansel Varrick", "Captain Ruhl", 2, "Hold's captain; came with the writ; not warm, not false"),
    ("Captain Ruhl", "Reeve Ansel Varrick", 1, "the new reeve; talks well; has not bled for the Hold yet"),
    ("Captain Ruhl", "Dram Hollis", -1, "the Carriers' clerk; watches the drill like a man counting"),
    ("Dram Hollis", "Reeve Ansel Varrick", -2, "the mark"),
    ("Dram Hollis", "Captain Ruhl", -1, "the one who would be trouble"),
    ("Ossa the Carrier", "Dram Hollis", -1, "came on Dreyer's paper; I took the glass"),
    ("Elder Taan", "Nico", 3, "my eyes on the ridge"),
    ("Elder Taan", "Sefa of the Keth", 3, "my best scout; too quick to like people"),
    ("Nico", "Sefa of the Keth", 2, "the better walker"),
    ("Sefa of the Keth", "Elder Taan", 4, "she counts the skins"),
    ("Sefa of the Keth", "Nico", 2, "watches with me"),
]


def seed_reach(s, by_name):
    """Goals, standings and acquaintances for every seat. Idempotent: checks before it writes."""
    for who, goals in GOALS.items():
        eid = by_name[who]
        have = {g.get("text") for g in (s.recall(entity=eid).get("goals") or [])}
        for text, why in goals:
            if text not in have:
                s.intend(text, why=why, entity=eid)
    factions = {f["name"]: f["id"] for f in s.find(type="faction", limit=20)}
    for who, table in STANDINGS.items():
        eid = by_name[who]
        existing = {e["target"] for e in s.world.edges(eid, "standing", "out")}
        for fname, value in table.items():
            if factions[fname] not in existing:
                s.link(eid, factions[fname], "standing", {"value": value, "public": True})
    for a, b, standing, note in KNOWS:
        ea, eb = by_name[a], by_name[b]
        if not any(e["target"] == eb for e in s.world.edges(ea, "knows", "out")):
            s.link(ea, eb, "knows", {"standing": standing, "note": note, "met_t": 0, "count": 0})


def define(s):
    """Scripts and schemas. Safe to run again on a live world."""
    define_rules(s)
    for sid, src in [("go", GO), ("creep", CREEP), ("take", TAKE), ("drop", DROP), ("give", GIVE), ("talk", TALK),
                     ("read", READ), ("person_on", PERSON_ON), ("ward_toggle", WARD_TOGGLE), ("ossa_on", OSSA_ON),
                     ("reach_story", STORY)]:
        s.define_script(sid, src)
    s.define_schema("person", extends="combatant", doc="Someone of the Reach: walks, carries, talks, and fights by the rules.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": {}, "asleep": False, "follows": None,
                           "secret": ["dialog", "gives", "gave"]},
                    actions={
                        "go": {"script": "go", "doc": "Walk to a connected place (loud on deep sand)", "targets": "place", "scope": "exits", "duration": 10},
                        "creep": {"script": "creep", "doc": "Walk with the broken step: twice as long, the sand does not hear you",
                                  "targets": "place", "scope": "exits", "duration": 20},
                        "take": {"script": "take", "doc": "Pick something up", "targets": "thing", "scope": "here"},
                        "drop": {"script": "drop", "doc": "Put down something you hold", "targets": "thing", "scope": "held"},
                        "give": {"script": "give", "doc": "Hand something you hold to someone here", "targets": "creature", "scope": "here",
                                 "params": {"item": "id or name of a thing you hold"}},
                        "talk": {"script": "talk", "doc": "Talk to someone about something", "targets": "creature", "scope": "here", "duration": 2,
                                 "params": {"about": "the topic, in your words"}},
                    },
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])
    s.define_schema("fighter", extends="person", doc="A person who fights without a mind: in a duel, or against the outlawed.",
                    behaviors=[{"script": "fighter_tick", "every": 6}])
    s.define_schema("carrier", extends="person", doc="Trades glass for water.",
                    listeners=[{"script": "ossa_on", "kinds": ["given"]}])
    s.define_schema("letter", extends="thing", doc="Something with writing on it.", state={"text": "", "portable": True},
                    actions={"read": {"script": "read", "doc": "Read what is written"}})
    s.define_schema("ward", extends="thing", doc="A belt ward. On, it hardens against anything fast.",
                    state={"portable": True, "ward": True, "on": True,
                           "description": "A belt plate with a thumb-switch. A faint hum when it is on.",
                           "description_on": "A belt plate with a thumb-switch. A faint hum when it is on.",
                           "description_off": "A belt plate with a thumb-switch. Silent."},
                    actions={"toggle": {"script": "ward_toggle", "doc": "Switch it on or off"}})
    s.define_schema("story", extends="entity", doc="The rails. Hidden; holds the facts the story has seen.",
                    state={"hidden": True, "seen_ridge": False, "seen_flats": False, "found_well": False, "truce": False,
                           "dram_done": False, "reeve_dead": False, "done": False})


def populate(s):
    """Places, people, things, rules and the clock."""
    root = s.summary()["root"]
    s.patch(root, {"policy": POLICY, "ambient": AMBIENT})

    hold = s.spawn("place", root, "Scar Gate, the Hold", state={
        "description": "A squat stone hold wedged into the only gap in the Scar. A cracked cistern under the floor, a hall "
                       "with a map nobody trusts, and the gate yard beyond the inner door."})["id"]
    yard = s.spawn("place", root, "The Gate Yard", state={"ring": True,
        "description": "Packed sand inside the gate, a ring scratched in it by old law. Guards drill in the shade of the wall."})["id"]
    road = s.spawn("place", root, "The Salt Road", state={"open": True,
        "description": "The one road out, white with salt, running north between the Scar and the glass. Convoy ruts, a dead crawler, wind."})["id"]
    flats = s.spawn("place", root, "The Glass Flats", state={"open": True, "deep_sand": True, "tremor": 0,
        "description": "Black glass underfoot, red dunes walking across it. Veins of dull red where the dunes have pulled back. Every step rings."})["id"]
    ridge = s.spawn("place", root, "Red Ridge", state={
        "description": "A spine of red rock standing out of the glass. Shade, a view of everything, goat sign on the stone."})["id"]
    deepwell = s.spawn("place", root, "The Deepwell", state={"hidden": True, "known_to": "the Keth", "water_source": True,
        "ambient": {"weather": "cool, a steady drip", "light": "dim, from one shaft"},
        "description": "A cavern under the ridge where the rock sweats water into a black pool. Cups on cords, a cookfire, the smell of wet stone."})["id"]
    landing = s.spawn("place", root, "The Carriers' Landing", state={"open": True,
        "description": "A flat of hard pan where the Guild's crawlers put down. Water casks under tarps, a tally post, one broad woman with a ledger."})["id"]
    bones = s.spawn("place", root, "The Bone Field", state={"open": True, "deep_sand": True, "tremor": 2,
        "description": "A Dreyer crawler on its side, half sunk, ribs of it showing. Things glint in the wreck. The sand here is soft and deep."})["id"]
    deep = s.spawn("place", root, "The Deep", state={"hidden": True,
        "description": "Under the dunes. Nothing lives here but the one thing that does."})["id"]
    s.connect(hold, yard)
    s.connect(yard, road)
    s.connect(road, flats)
    s.connect(road, landing)
    s.connect(flats, ridge)
    s.connect(flats, bones)
    s.connect(ridge, deepwell)

    factions = {name: s.spawn("faction", root, name)["id"] for name in FACTIONS}

    # the Hold
    ansel = s.spawn("person", hold, "Reeve Ansel Varrick", state=ANSEL)["id"]
    s.spawn("thing", ansel, "Reeve's blade", state={"weapon": True, "damage": 2, "bonus": 0, "portable": True,
                                                   "description": "A straight court blade, better made than its owner can use."})
    s.spawn("ward", ansel, "Belt ward")
    s.spawn("waterskin", ansel, "Waterskin", state={"left": 2})
    cistern = s.spawn("thing", hold, "The cistern", state={"portable": False, "water_source": True, "left": 12,
        "description": "A stone tank under the floor with a crack you can put two fingers in. Twelve draws left, Ruhl says."})["id"]
    s.spawn("letter", hold, "The Crown's writ", state={"portable": False,
        "text": "By the Crown: the fief of Scar Gate and the Glass Flats to House Varrick, with the water, the road and the glass, and the duty of the gate. Dreyer to quit the Reach within the season."})
    dram = s.spawn("fighter", hold, "Dram Hollis", state=DRAM)["id"]
    s.spawn("thing", dram, "Thin blade", state={"weapon": True, "damage": 2, "bonus": 1, "portable": True,
                                               "description": "Narrow, dark, no ornament. A blade for the slow stroke through a ward."})

    # the yard
    ruhl = s.spawn("fighter", yard, "Captain Ruhl", state=RUHL)["id"]
    s.spawn("thing", ruhl, "Guard's blade", state={"weapon": True, "damage": 2, "bonus": 0, "portable": True})
    s.spawn("thing", yard, "Rack of practice blades", state={"portable": False,
        "description": "Wooden blades, weighted. Nobody dies in the ring on these. Nobody wins on them either."})

    # the landing
    ossa = s.spawn("carrier", landing, "Ossa the Carrier", state=OSSA)["id"]
    s.spawn("thing", landing, "Water casks", state={"portable": False, "water_source": True, "left": 6,
        "description": "Guild casks under a tarp, each one tallied. Ossa's eye is on them."})
    s.spawn("letter", landing, "Tally post", state={"portable": False,
        "text": "GUILD TALLY. Water: one skin per shard. Glass: by weight, Guild's cut a third. Convoy south at the moon's turn. The Guild carries for whoever holds the gate."})

    # the flats and the bones
    s.spawn("vein", flats, "Red vein", state={"ember": 3, "description": "A seam of dull red in the black glass, warm to the hand."})
    s.spawn("vein", flats, "Second vein", state={"ember": 2, "description": "A thinner seam, half under the dune's edge."})
    s.spawn("thing", bones, "Maul", state={"weapon": True, "damage": 3, "bonus": -1, "portable": True,
                                           "description": "A crawler's breaker bar. Slow, and heavy enough that slow is enough."})
    s.spawn("ward", bones, "Dead man's ward", state={"on": False, "description": "A belt plate with a thumb-switch. Silent.",
                                                   "description_off": "A belt plate with a thumb-switch. Silent."})
    s.spawn("waterskin", bones, "Cracked waterskin", state={"left": 1, "capacity": 2})

    # the ridge and the well
    sefa = s.spawn("person", ridge, "Sefa of the Keth", state=SEFA)["id"]
    s.spawn("thing", sefa, "Keth knife", state={"weapon": True, "damage": 1, "bonus": 1, "portable": True,
                                               "description": "Short, curved, kept sharper than it needs to be."})
    s.spawn("waterskin", sefa, "Sefa's skin", state={"left": 3})
    nico = s.spawn("person", ridge, "Nico", state=NICO)["id"]
    s.spawn("thing", nico, "Long glass", state={"portable": True, "description": "A brass spyglass, Carrier make, the lens scratched."})
    taan = s.spawn("person", deepwell, "Elder Taan", state=TAAN)["id"]
    s.spawn("thing", deepwell, "Stone cups on cords", state={"portable": False, "description": "Cups worn smooth, one for each Keth who has ever drunk here."})
    worm = s.spawn("thresher", deep, "The Thresher", state={"home": deep})["id"]

    # the rails and the clock
    s.spawn("story", root, "Story", state={"hold": hold, "yard": yard, "road": road, "flats": flats, "ridge": ridge, "deepwell": deepwell,
                                           "landing": landing, "bones": bones, "deep": deep, "cistern": cistern,
                                           "ansel": ansel, "sefa": sefa, "ruhl": ruhl, "dram": dram, "ossa": ossa, "taan": taan,
                                           "nico": nico, "worm": worm, "keth": factions["the Keth"], "varrick": factions["House Varrick"]})
    install_rules(s, root)
    s.set_rule(root, "reach_story", kinds=["arrived", "checked", "talked", "agreed", "dram_moves", "downed", "killed", "yielded",
                                            "heat", "dusk", "cistern_cracks"])
    by_name = {"Reeve Ansel Varrick": ansel, "Sefa of the Keth": sefa, "Captain Ruhl": ruhl, "Dram Hollis": dram,
               "Ossa the Carrier": ossa, "Elder Taan": taan, "Nico": nico}
    seed_reach(s, by_name)
    s.schedule(200, "heat", entity=root)
    s.schedule(240, "dram_moves", entity=root)
    s.schedule(500, "dusk", entity=root)
    s.schedule(600, "cistern_cracks", entity=root)
    s.clock(run=False, turn=3)
    return s.summary()


def upgrade(s):
    """Bring a world built from an older version of this file up to this one. Checks before every write."""
    names = {e["name"]: e["id"] for e in s.find(limit=500)}
    need = ["Reeve Ansel Varrick", "Sefa of the Keth", "Captain Ruhl", "Dram Hollis", "Ossa the Carrier", "Elder Taan", "Nico"]
    if all(n in names for n in need):
        seed_reach(s, {n: names[n] for n in need})
    root = s.summary()["root"]
    install_rules(s, root)
    s.set_rule(root, "reach_story", kinds=["arrived", "checked", "talked", "agreed", "dram_moves", "downed", "killed", "yielded",
                                            "heat", "dusk", "cistern_cracks"])
    s.patch(root, {"policy": POLICY})


def build(s):
    s.create_world("The Glass Reach", seed=23, id="glass-reach",
                   description="A desert fief, a cracked cistern, a people with the water, a blade left behind. Rules on the table.")
    define(s)
    return populate(s)
