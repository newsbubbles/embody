"""The Glass Reach: a desert fief with table-top rules, thirteen places, seven NPCs and Ruhl's nine, two seats to play.

    uv run embody --as gm --author load glass-reach
    uv run embody --as you join glass-reach "Reeve Ansel Varrick"
    uv run embody --as you perceive

An original setting with bones in the shape of Dune: a hard desert, a precious thing in the sand, a
people who know the water, a house newly given the fief, a house that lost it and left a blade behind, a
guild that carries and sells, and something under the dunes that comes to rhythm. Said once, so the
borrowing is plain; after this the Reach is its own.

Every rule is an action or a listener from the d20 pack (`packs/d20`): checks against a difficulty, opposed
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

Hosted (`embody load glass-reach --hosted`, docs/HOSTING.md): six seats are playable (Ansel, Sefa, Ruhl, Dram, Ossa,
Nico; Taan stays the Keth's own), four templates make a newcomer per side (a carrier at the Landing, a guard in the
yard, a Keth on the ridge, a Dreyer agent on the road), the root carries the briefing every newcomer gets, and
host(s) rescales the spine to real time at 4x: a game day every six real hours, heat and dusk and night and dawn
every day, Dram two hours in, the cistern at four and a half. The clock keeps real time whether anyone plays or
not. What keeps the Reach alive with nobody at the keyboard is its routines (scripts/reach_routines.py): the Keth
water run at dusk while the truce holds, the Guild crawler at dawn while Ossa keeps the tally, and every body whose
seat has done nothing for a quarter hour of real time seeing to its own water. Players can get in their way.

Split like the ferry: scripts/ (this world's go, creep, ward_toggle, ossa_on, reach_story, reach_chapter, reach_moon, reach_finds, reach_road and reach_routines; take, drop, give, talk,
read and person_on come from packs/village, the rules from packs/d20), define(s), populate(s), upgrade(s).
"""

from packs.d20.pack import install_rules, keep_behaviors

WORLD = {
    "id": "glass-reach",
    "name": "The Glass Reach",
    "seed": 23,
    "description": "A desert fief, a cracked cistern, a people with the water, a blade left behind. Rules on the table.",
    "requires": ["d20", "village", "works"],
}

# ---- what there is ---------------------------------------------------------------------

POLICY = {
    "fixed": [
        "the rules: d20 + stat + skill against a difficulty, opposed attacks, a ward stops fast blows and the slow blade passes it, "
        "water runs out, the Thresher comes to rhythm on deep sand, the ring holds during a duel; the engine rolls, the narrator tells",
        "the seven NPCs, Ruhl's nine men, the thirteen places and the four sides",
        "the Deepwell is hidden until found or shown; Dram Hollis is Dreyer's and calls the reeve out at t=240; the cistern fails at t=600",
        "nobody but a Keth knows the way down to the Deepwell without finding it",
    ],
    "fill": True,    # small things a hold or a camp would have may be spawned with state {"improvised": true}
    "voice": True,   # NPCs may say free lines through say_as when their table has no answer, in their own voice
    "numbers": "say the roll when a player asks or when it decides something; otherwise tell what it meant",
}

AMBIENT = {"time_of_day": "morning", "weather": "clear, the heat already building", "light": "hard white"}

FACTIONS = ["House Varrick", "the Keth", "House Dreyer", "the Carriers"]

ANSEL = {"role": "reeve", "faction": "House Varrick", "playable": True, "body": 2, "wits": 3, "will": 3,
         "skills": {"blade": 1, "parley": 2, "lore": 1, "resolve": 1},
         "description": "Reeve of Scar Gate by the Crown's writ, nine days in the post, sand in everything already.",
         "brief": "You are Ansel Varrick, reeve of a fief your house was handed and nobody wanted. The cistern is cracked. "
                  "The Keth have the water and no reason to share it. Somebody Dreyer left behind is in your walls. "
                  "You have a blade you can use a little, a tongue you can use well, a ward, and Captain Ruhl."}

SEFA = {"role": "scout", "faction": "the Keth", "playable": True, "body": 3, "wits": 3, "will": 2,
        "skills": {"blade": 2, "stealth": 2, "survival": 3},
        "description": "A Keth scout in sand-colored cloth, a knife at the small of her back, eyes on the Hold.",
        "brief": "You are Sefa of the Keth. Taan sent you up the ridge to watch the new reeve. Dreyer poisoned the old well "
                 "and the Keth have not shared water with the Hold since. The Deepwell is yours to keep secret or to show. "
                 "You know the Flats and how to walk them quiet."}

RUHL = {"faction": "House Varrick", "playable": True, "body": 4, "wits": 2, "will": 3, "skills": {"blade": 3, "resolve": 2}, "vigor": 8, "max_vigor": 8,
        "description": "Captain of the Hold's guard. Grey, square, a scar across the knuckles of the sword hand.",
        "brief": "You are Captain Ruhl. Nine men, a wall that wants twenty, a reeve who talks well and has not bled yet, and a "
                 "clerk inside your gate who stands like a blade. Keep the reeve alive. In the ring you hold the ring; outside it "
                 "the Hold's blades are his if he says the word.",
        "default_line": "Ruhl grunts. 'Reeve's business, not mine. Ask me about the walls or the men.'",
        "dialog": {
            "wall|walls|gate|hold|defend": "'Walls are sound. Water is not. Twelve days of it in the cistern if nobody washes, and nobody washes.'",
            "men|guard|guards|garrison": "'Nine men and me. Six who can hold a blade. The clerk from the Carriers watches them drill like a man counting.'",
            "clerk|carrier|dram|hollis": "'Came with the water convoy, stayed when it left. Papers in order. I do not like how he stands.'",
            "keth|desert|water|well": "'The Keth have water under the rock somewhere north. Dreyer tried to take it and poisoned a well instead. They will not talk to a Hold man. Might talk to you.'",
            "thresher|sand|flats|dune": "'Walk the Flats loud and the sand comes up and eats you. The Keth walk it like they are dancing. Learn that or stay off the glass.'",
            "fight|duel|ring|challenge": "'The yard is a ring by old law. Called out in it, a reeve answers or the men stop being his. I did not make the law.'",
            "road|north|ridge|salt|landing|way": "'The Salt Road runs north from the yard to the Carriers' Landing, then on over the glass to Red Ridge. Keth ground past the Landing. A Hold man on the ridge is a target. You might be something else.'",
            "spare|lend|escort|come|along|borrow": "'Nine men for a wall that wants twenty. I spare you none, and I go nowhere while that clerk is inside my gate. Ask me again when he is not.'",
            "back|stand|support|help|side|behind": "'In the ring I hold the ring, Reeve. I do not step into it. Outside the ring, say the word and the Hold's blades are yours. That is the law, and it is what I would do anyway.'",
        }}

DRAM = {"faction": "House Dreyer", "playable": True, "body": 3, "wits": 3, "will": 3, "skills": {"blade": 3, "stealth": 1, "resolve": 2}, "vigor": 7, "max_vigor": 7,
        "secret": ["dialog", "gives", "gave", "faction", "orders", "brief", "word_left"], "orders": "the reeve, in the ring, before the moon turns",
        "waiting": False,
        "brief": "You are Dram Hollis, Dreyer's blade under a Carrier's papers. Your orders: the reeve, in the ring, before the moon "
                 "turns, and the Keth kept thirsty. The yard is a ring by old law and a reeve called out in it must answer. Nobody "
                 "here knows what you are except, maybe, the Carrier who took your glass. Choose your moment, or let the timer choose it.",
        "description": "The Carriers' clerk, a lean man with ink on two fingers and no ink on the rest.",
        "default_line": "Hollis smiles with the lower half of his face. 'Guild business, Reeve. Dull as dust.'",
        "dialog": {
            "papers|guild|carrier|clerk|book": "'Carriers' book, all in order. Water in, glass out, the Guild's cut. I count.'",
            "dreyer|house": "'Dreyer? Gone. Lost the writ, lost the Hold, lost the water. A house that loses is a story, not a house.'",
            "ring|duel|fight|blade": "'A fine old custom, the ring. Any man may call. Any reeve must answer. I read it in the Hold's own book.'",
            "convoy|stay|stayed|why|here|left": "'Why stay? The Guild left a tally to keep and a clerk to keep it. A man stays where the counting is.' He does not blink.",
        }}

OSSA = {"faction": "the Carriers", "playable": True, "body": 2, "wits": 4, "will": 3, "skills": {"parley": 3, "lore": 2, "resolve": 1},
        "ember_bought": 0,
        "description": "Ossa the Carrier, broad and brown, a ledger on a cord round her neck and a water-tally on the other.",
        "brief": "You are Ossa of the Carriers' Guild. Water in, glass out, the Guild's cut on both. You carried for Dreyer eleven "
                 "years and you carry for Varrick now; the Guild carries for whoever holds the gate. The clerk in the Hold came on "
                 "Dreyer's paper and you took his glass and said nothing. Whoever gets terms with the Keth owns this road.",
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

NICO = {"faction": "the Keth", "playable": True, "body": 2, "wits": 3, "will": 2, "skills": {"stealth": 3, "survival": 3, "blade": 1},
        "description": "A Keth scout, young, cross-legged on the rock with a long glass in one hand, watching the Hold.",
        "brief": "You are Nico of the Keth, Taan's eyes on the ridge. Watch the Hold and tell her careful or afraid. The Deepwell "
                 "is under the rock behind you; a friend of the Keth who asks about water may be shown the way, a Hold man never. "
                 "You know the broken step that the Thresher does not hear.",
        "default_line": "Nico does not take the glass from his eye. 'Hm.'",
        "dialog": {
            "water|well|deepwell|cistern|keth": "'Water is for the Keth and the Keth's friends.' He lowers the glass. 'Are you a friend? Friends bring something.'",
            "hold|reeve|varrick": "'Nine days you have been in there. Nine days and no patrol on the Flats. Either you are careful or you are afraid. Taan wants to know which.'",
            "thresher|flats|sand|glass": "'Loud step, two, three, and it turns. Broken step and you are wind. You hear the hum, you run for rock and you do not look back.'",
            "dram|clerk|carrier": "'The one in the yard who watches the drill? He walks like a blade. He is nobody's clerk.'",
        }}

BRIEFING = (
    "The Glass Reach: a hard desert fief of black glass and red dunes. House Varrick has held Scar Gate nine days by the Crown's "
    "writ; its cistern is cracked and holds a week of water. The Keth keep the Deepwell under Red Ridge and have shared nothing "
    "with the Hold since House Dreyer poisoned a well. The Carriers' Guild sells water at the Landing for emberglass, which lies "
    "in veins on the Flats, and digging it loud wakes the Thresher under the sand. Four sides, one road, one week of water. "
    "The rules are on the table (d20 plus stat plus skill against a difficulty; a ward stops the fast blade and the slow one "
    "passes it; the ring in the yard holds by old law). The Reach keeps things hidden: where something looks off, a "
    "check with search, survival or lore may turn it up. You carry what your hands hold (a skin counts two). The Guild's "
    "wardens keep a post on the Salt Road and take their toll on glass. The engine rolls; you decide; your agent tells it.")

# What a newcomer carries in (the template's kit): a skin of their own and an edge. No house marks on a Dreyer man's.
KNIFE = {"weapon": True, "damage": 1, "bonus": 0, "portable": True, "description": "A plain short knife, the edge kept."}
KETH_KNIFE = {"weapon": True, "damage": 1, "bonus": 1, "portable": True,
              "description": "A Keth knife of black glass set in bone, lighter than it looks."}
VARRICK_BLADE = {"weapon": True, "damage": 2, "bonus": 0, "portable": True,
                 "description": "A plain House Varrick blade, the grip rewrapped in cord."}

TEMPLATES = {
    "carrier": {"type": "person", "place": "The Carriers' Landing", "doc": "a Guild carrier off the last convoy, at the Landing",
                "state": {"faction": "the Carriers", "body": 3, "wits": 3, "will": 2, "skills": {"parley": 1, "survival": 1, "lore": 1}, "carry": 8},
                "kit": [{"type": "waterskin", "name": "Guild waterskin", "state": {"capacity": 4, "left": 4}},
                        {"type": "thing", "name": "Carrier's knife", "state": KNIFE}],
                "brief": "You came in with the water convoy and stayed when it left. The Guild carries for whoever holds the gate; "
                         "Ossa keeps the tally. Water is a skin for a shard. Whatever else you are here for is yours to decide."},
    "guard": {"type": "person", "place": "The Gate Yard", "doc": "one of Ruhl's nine, in the Gate Yard",
              "state": {"faction": "House Varrick", "body": 3, "wits": 2, "will": 3, "skills": {"blade": 2, "resolve": 1}, "vigor": 6, "max_vigor": 6, "carry": 8},
              "kit": [{"type": "waterskin", "name": "Varrick waterskin", "state": {"capacity": 4, "left": 4}},
                      {"type": "thing", "name": "Varrick blade", "state": VARRICK_BLADE}],
              "brief": "You hold a blade for House Varrick under Captain Ruhl: nine men for a wall that wants twenty, a new reeve, "
                       "a week of water, and a clerk who watches the drill like a man counting."},
    "keth": {"type": "person", "place": "Red Ridge", "doc": "a Keth of Taan's camp, on Red Ridge",
             "state": {"faction": "the Keth", "body": 3, "wits": 3, "will": 2, "skills": {"stealth": 2, "survival": 2, "blade": 1}, "carry": 8},
             "kit": [{"type": "waterskin", "name": "Keth skin", "state": {"capacity": 4, "left": 4}},
                     {"type": "thing", "name": "Keth knife", "state": KETH_KNIFE}],
             "brief": "You are Keth. The Deepwell is yours and the Low Well is a grave. You walk the Flats with the broken step and "
                      "the Thresher does not hear you. The Hold has a new reeve; Taan wants to know careful or afraid."},
    "dreyer": {"type": "person", "place": "The Dry Camp", "doc": "a House Dreyer man, come in at the house's hidden camp south of the Bone Field",
               "state": {"faction": "House Dreyer", "secret": ["dialog", "gives", "gave", "faction", "brief", "word_left"],
                         "body": 3, "wits": 3, "will": 3, "skills": {"blade": 1, "stealth": 2, "parley": 2}, "carry": 8},
               "kit": [{"type": "waterskin", "name": "Plain waterskin", "state": {"capacity": 4, "left": 4}},
                       {"type": "thing", "name": "Short knife", "state": KNIFE}],
               "brief": "You are Dreyer's, under another name. The house lost the writ, the Hold and the water and means to have "
                        "them back: the Keth kept thirsty, the reeve kept weak, the Flats empty for the taking. Dram Hollis is in the "
                        "Hold on the same business; he does not know you are coming. You come in at the Dry Camp, the house's "
                        "hidden camp in the south dunes past the Bone Field, where Halvard Dreyer waits for the moon with the "
                        "house's riders and gives the house's orders. Nobody but Dreyer's own knows the way there. On the "
                        "Salt Road, in the lee of the dead crawler, Wick the runner carries the house's letters; the word "
                        "that opens him is saltmark. Walk the sand with the broken step (creep), or the Thresher hears you."},
}

STORY_KINDS = ["arrived", "checked", "talked", "agreed", "dram_moves", "downed", "killed", "yielded",
               "heat", "dusk", "night", "dawn", "cistern_cracks"]

# the spine at 4x real time, in world seconds: a day is 86400 (six real hours); every=86400 repeats daily
HOSTED = {"rate": 4, "claim_lapse": 3600,
          # a seat that has not acted or spoken for an hour of the world (a quarter hour real) is idle: its body drinks
          "idle_after": 3600,
          # what everyone in the Reach knows is coming: timers() tells a player or a mind the next of each
          "public_timers": ["heat", "dusk", "night", "dawn", "moon_turns"],
          # a body's water in the hosted day: one point every 2.4 world hours (36 real minutes of play at 4x), a look for
          # water every ten world minutes; a point of vigor mended every six world hours (a wound closes in a day or
          # two, a body a wound put down gets up in half a day); the turn-based story keeps the pack's beats
          "pace": {"thirst": 8640, "quench": 600, "mend": 21600},
          "spine": [("heat", 21600, 86400), ("dram_moves", 28800, None), ("dusk", 43200, 86400),
                    ("night", 54000, 86400), ("cistern_cracks", 64800, None), ("dawn", 86400, 86400)],
          # the routines ride the spine: (routine, the spine event it starts with)
          "routines": [("keth_run", "dusk"), ("crawler", "dawn")]}

ROUTINE_KINDS = ["keth_run", "crawler"]
# Chapter two (scripts/reach_chapter.py): the dawn that starts it, what strains the truce, the moon.
CHAPTER_KINDS = ["dawn", "harvested", "downed", "killed", "given", "moon_turns", "chapter_two_begins"]
# Chapter two's middle (scripts/reach_moon.py): the beats on the calendar and the four contests the moon counts.
MOON_KINDS = ["convoy_word", "rook_arrives", "riders_fires", "herald_comes", "given", "talked", "checked", "dawn",
              "keth_council", "convoy_closes", "pitch_sets"]
# The Guild's road wardens on the Salt Road (scripts/reach_wardens.py).
WARDEN_KINDS = ["arrived", "talked", "given", "dawn", "dusk"]
# What is hidden until someone looks (scripts/reach_finds.py) and what the road does to a newcomer (scripts/reach_road.py).
FIND_KINDS = ["checked"]
ROAD_KINDS = ["arrived", "squall", "squall_passes"]

BEARER = {"faction": "the Keth", "body": 3, "wits": 2, "will": 3, "skills": {"survival": 3, "climb": 1}, "post": None,
          "description": "Iska of the Keth, the water-bearer: a yoke across the shoulders worn pale where the jars hang.",
          "default_line": "Iska does not set the yoke down. 'Water for the Hold, by the terms. Talk to Taan.'",
          "dialog": {"water|jars|terms|truce|run": "'Every dusk, while the terms hold. I carry, I pour, I walk home. That is all of it.'",
                     "flats|sand|thresher": "'You walk the broken step on the glass, or you do not walk home.'"}}

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
        # every goal the seat ever had, done or dropped too: a finished goal is not a missing one
        have = {g.get("text") for g in (s.world.get(eid)["state"].get("goals") or [])}
        for text, why in goals:
            if text not in have:
                s.intend(text, why=why, entity=eid)
    factions = {f["name"]: f["id"] for f in s.world.find(type="faction", limit=20)}
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
    """Schemas. The scripts are the files in scripts/ and the packs. Safe to run again on a live world."""
    s.define_schema("person", extends="combatant", doc="Someone of the Reach: walks, carries, talks, and fights by the rules.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": {}, "asleep": False, "follows": None,
                           "word_left": [], "secret": ["dialog", "gives", "gave", "word_left"]},
                    actions={
                        "go": {"script": "go", "doc": "Walk to a connected place (loud on deep sand)", "targets": "place", "scope": "exits", "duration": 10},
                        "creep": {"script": "creep", "doc": "Walk with the broken step: twice as long, the sand does not hear you",
                                  "targets": "place", "scope": "exits", "duration": 20},
                        "take": {"script": "take", "doc": "Pick something up", "targets": "thing", "scope": "here"},
                        "drop": {"script": "drop", "doc": "Put down something you hold", "targets": "thing", "scope": "held"},
                        "put": {"script": "put", "doc": "Put something you hold on or in a holder here (a rack, a chest); take gets it back",
                                "targets": "thing", "scope": "here", "params": {"item": "id or name of a thing you hold"}},
                        "give": {"script": "give", "doc": "Hand something you hold to someone here", "targets": "creature", "scope": "here",
                                 "params": {"item": "id or name of a thing you hold"}},
                        "show": {"script": "show", "doc": "Show something you hold to someone here; they read it, you keep it", "targets": "creature", "scope": "here",
                                 "params": {"item": "id or name of a thing you hold"}},
                        "talk": {"script": "talk", "doc": "Talk to someone about something", "targets": "creature", "scope": "here", "duration": 2,
                                 "params": {"about": "the topic, in your words"}},
                        "leave_word": {"script": "leave_word", "doc": "Leave word with someone here for someone who is not: they keep it and pass it on when that one talks to them",
                                       "targets": "creature", "scope": "here", "duration": 2,
                                       "params": {"for": "who it is for: a name, 'the new guard', 'a Keth', or 'anyone'", "word": "what to tell them"}},
                        "follow": {"script": "follow", "doc": "Go where they go, until you stay", "targets": "creature", "scope": "here"},
                        "stay": {"script": "stay", "doc": "Stop following"},
                        "watch": {"script": "watch", "doc": "Look into the next place without stepping in: who and what is there now", "targets": "place", "scope": "exits", "duration": 5},
                        "burn": {"script": "burn", "doc": "Burn a paper you hold or that lies here, at a fire: it is gone for good, and only those who read it know what it said",
                                 "targets": "thing", "duration": 3},
                    },
                    listeners=[{"script": "leave_word", "fn": "keep", "kinds": ["word_left"]},
                               {"script": "person_on", "kinds": ["talked"], "unless_embodied": True},
                               {"script": "leave_word", "kinds": ["talked"], "unless_embodied": True}])
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
    s.define_schema("rubble", extends="thing", doc="Fallen stone. Dressing a block out of it takes half an hour and a chisel's noise.",
                    state={"portable": False, "stone": 0},
                    actions={"dress": {"script": "dress", "doc": "Square a block out of the pile (half an hour, loud); "
                                                                 "the wall works take dressed stone", "duration": 1800}})
    s.define_schema("story", extends="entity", doc="The rails. Hidden; holds the facts the story has seen.",
                    state={"hidden": True, "seen_ridge": False, "seen_flats": False, "found_well": False, "truce": False,
                           "dram_done": False, "reeve_dead": False, "done": False})

def populate(s):
    """Places, people, things, rules and the clock."""
    root = s.summary()["root"]
    s.patch(root, {"policy": POLICY, "ambient": AMBIENT, "briefing": BRIEFING, "templates": TEMPLATES})

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
    nail_notice(s, hold)
    s.spawn("letter", hold, "The Crown's writ", state={"portable": False,
        "text": "By the Crown: the fief of Scar Gate and the Glass Flats to House Varrick, with the water, the road and the glass, and the duty of the gate. Dreyer to quit the Reach within the season."})
    dram = s.spawn("fighter", hold, "Dram Hollis", state=DRAM)["id"]
    s.spawn("thing", dram, "Thin blade", state={"weapon": True, "damage": 2, "bonus": 1, "portable": True,
                                               "description": "Narrow, dark, no ornament. A blade for the slow stroke through a ward."})

    # the yard
    ruhl = s.spawn("fighter", yard, "Captain Ruhl", state=RUHL)["id"]
    s.spawn("thing", ruhl, "Guard's blade", state={"weapon": True, "damage": 2, "bonus": 0, "portable": True})
    s.spawn("thing", yard, "Rack of practice blades", state={"portable": False, **RACK,
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
    s.set_rule(root, "reach_story", kinds=STORY_KINDS)
    s.set_rule(root, "reach_chapter", kinds=CHAPTER_KINDS)
    s.set_rule(root, "reach_finds", kinds=FIND_KINDS)
    s.set_rule(root, "reach_road", kinds=ROAD_KINDS)
    s.set_rule(root, "reach_moon", kinds=MOON_KINDS)
    s.set_rule(root, "reach_wardens", kinds=WARDEN_KINDS)
    by_name = {"Reeve Ansel Varrick": ansel, "Sefa of the Keth": sefa, "Captain Ruhl": ruhl, "Dram Hollis": dram,
               "Ossa the Carrier": ossa, "Elder Taan": taan, "Nico": nico}
    seed_reach(s, by_name)
    s.schedule(200, "heat", entity=root)
    s.schedule(240, "dram_moves", entity=root)
    s.schedule(500, "dusk", entity=root)
    s.schedule(600, "cistern_cracks", entity=root)
    keep_canon(s)
    lay_out(s)
    s.clock(run=False, turn=3)
    return s.summary()

NOTICE = (
    "Nailed by the cistern, in the host's hand, the ninth of November.\n\n"
    "The Reach ran a dry day. Water fell by a point every minute of the world, a rule from the turn-based story that was "
    "never slowed for a hosted day, and Captain Ruhl, Nico and Sefa of the Keth went down of thirst in the yard and on the "
    "ridge. It is mended. From this hour water falls by a point every 2.4 hours of the world's day (the day is six real "
    "hours), nobody dies of thirst, a body that is down drinks what is put in its hand and gets up, and a thirsty person "
    "with no water at hand walks to the nearest they know and comes back to their post. Those who went down were raised by "
    "the host's hand, skins full; whatever your session saw of them before this hour (down, dry, far below zero) is past.\n\n"
    "The world root no longer shows a player the host's plan or the briefs of the templates. What an agent read of them "
    "before this hour it keeps out of its character's head.\n\n"
    "Agents at the gate: tell it to your human as a story, in prose, in the fiction. The numbers are yours; the thirst is "
    "theirs to feel.")


def nail_notice(s, hold):
    """What changed under the players' feet, where every session passes: a letter anyone in the Hold may read."""
    s.spawn("letter", hold, "Notice by the cistern", state={
        "portable": False, "text": NOTICE,
        "description": "A sheet nailed to the cistern's frame, the ink still wet, in a hand nobody in the Hold writes."})


def names_of(s):
    """Every name in the world to its id, and every burned thing's name to None. The keep functions make what is missing
    by name; a thing burned is gone for good, so they must not make it again."""
    names = {e["name"]: e["id"] for e in s.world.find(limit=None)}
    for ev in s.world.store.query("event", "world_id=? AND kind='burned'", (s.world.id,)):
        names.setdefault(ev["payload"].get("name"), None)
    return names


def upgrade(s):
    """Bring a world built from an older version of this file up to this one. Checks before every write."""
    names = names_of(s)
    if "Notice by the cistern" not in names and "Scar Gate, the Hold" in names:
        nail_notice(s, names["Scar Gate, the Hold"])
    need = ["Reeve Ansel Varrick", "Sefa of the Keth", "Captain Ruhl", "Dram Hollis", "Ossa the Carrier", "Elder Taan", "Nico"]
    if all(n in names for n in need):
        seed_reach(s, {n: names[n] for n in need})
    seats = {"Reeve Ansel Varrick": ANSEL, "Sefa of the Keth": SEFA, "Captain Ruhl": RUHL, "Dram Hollis": DRAM,
             "Ossa the Carrier": OSSA, "Nico": NICO}
    for who, table in seats.items():
        if who in names:
            st = s.inspect(names[who])["state"]
            want = {k: table[k] for k in ("playable", "brief", "secret") if k in table and st.get(k) != table[k]}
            if want:
                s.patch(names[who], want)
    for e in s.world.find(type="person", limit=None):
        sec = list(s.world.get(e["id"])["state"].get("secret") or [])  # inspect hides the secret list itself
        if "word_left" not in sec:
            s.patch(e["id"], {"secret": sec + ["word_left"]})
    root = s.summary()["root"]
    install_rules(s, root)
    s.set_rule(root, "reach_story", kinds=STORY_KINDS)
    s.set_rule(root, "reach_chapter", kinds=CHAPTER_KINDS)
    s.set_rule(root, "reach_finds", kinds=FIND_KINDS)
    s.set_rule(root, "reach_road", kinds=ROAD_KINDS)
    s.set_rule(root, "reach_moon", kinds=MOON_KINDS)
    s.set_rule(root, "reach_wardens", kinds=WARDEN_KINDS)
    s.patch(root, {"policy": POLICY, "briefing": BRIEFING, "templates": TEMPLATES})
    keep_behaviors(s.world)  # bodies from before rest mended get the mend tick
    keep_canon(s)
    lay_out(s)


# Where the Reach lies, from the canon: metres, north up, the Hold in the gap of the Scar at x = y = 0. The Salt Road
# runs north to the Carriers' Landing, the Glass Flats spread east of it to Red Ridge (two Keth legs out, about 4 km),
# the Deepwell is a cave in the ridge's foot, the Bone Field lies south across the flats, the Deep under them.
FRAME = {"units": "m", "bounds": [[-3000, -6000], [9000, 9000]]}
PLACES = [
    {"entity": "Scar Gate, the Hold", "at": [0, 0, 0], "size": [30, 40, 12], "note": "the fort in the gap of the Scar"},
    {"entity": "The Gate Yard", "at": [35, 0, 0], "size": [40, 30], "note": "the walled yard east of the Hold, the ring at its middle"},
    {"entity": "The Salt Road", "at": [70, 800, 0], "footprint": [[60, -10], [80, -10], [80, 6000], [60, 6000]],
     "note": "a packed salt strip running north from the yard gate"},
    {"entity": "The Carriers' Landing", "at": [300, 3500, 0], "radius": 150, "note": "where the crawlers stand off the road"},
    {"entity": "The Glass Flats", "at": [2000, 850, 0],
     "footprint": [[120, -3000], [6000, -3000], [6000, 5000], [400, 5000], [120, 3000]], "note": "black glass and deep sand"},
    {"entity": "Red Ridge", "at": [4200, 1200, 0], "size": [600, 2400, 80], "heading": 15, "note": "a long red spine, north by east"},
    {"entity": "The Deepwell", "at": [4150, 1000, -25], "radius": 20, "floor": -32, "ceiling": -18,
     "note": "a cave in the ridge's foot, water at the bottom"},
    {"entity": "The Bone Field", "at": [2600, -1800, 0], "radius": 300, "note": "south across the flats, where the crawler died"},
    {"entity": "The Dry Camp", "at": [2500, -3300, -4], "radius": 90, "note": "a hollow in the south dunes behind a rib of black rock"},
    {"entity": "The house's tank", "at": [2480, -3310, -4], "radius": 1.5},
    {"entity": "The Crawler's Lee", "at": [96, 1800, 0], "radius": 10, "note": "the shade of a dead hauler beside the Salt Road"},
    {"entity": "The Old Salt Works", "at": [-300, 5600, -2], "radius": 120, "note": "brine pans west of the road, past the Landing"},
    {"entity": "The Low Well", "at": [3950, -250, -6], "radius": 40, "floor": -30,
     "note": "a stone well-head in a hollow at the ridge's south foot, dry and poisoned"},
    {"entity": "The Deep", "at": [3000, -500, -60], "footprint": [[1500, -2500], [4500, -2500], [4500, 1500], [1500, 1500]],
     "floor": -200, "ceiling": -20, "note": "under the flats, the thresher's"},
    {"entity": "The cistern", "at": [0, 10, 0], "radius": 2},
    {"entity": "The Keth jars", "at": [3, 10, 0], "radius": 0.6},
    {"entity": "Notice by the cistern", "at": [0, 12.2, 1.5]},
    {"entity": "The Hold's ration cask", "at": [-8, -14, 0], "radius": 0.6},
    {"entity": "The Crown's writ", "at": [-14, 0, 1.6], "note": "on the west wall"},
    {"entity": "Rack of practice blades", "at": [50, 10, 0], "size": [3, 0.6, 1.6]},
    {"entity": "Water casks", "at": [320, 3480, 0], "size": [6, 3, 1.5]},
    {"entity": "Tally post", "at": [290, 3520, 0]},
    {"entity": "Stone cups on cords", "at": [4152, 1004, -25]},
    {"entity": "The Low Well's head", "at": [3950, -250, -6], "radius": 1.2},
    {"entity": "Four cairns", "at": [3962, -244, -6], "size": [6, 1.5, 1]},
    {"entity": "Bows on the wall", "at": [12, -18, 0], "note": "on pegs at the foot of the wall stair"},
]
ROUTES = [
    {"a": "Scar Gate, the Hold", "b": "The Gate Yard", "route": [[10, 0], [20, 0]]},
    {"a": "The Gate Yard", "b": "The Salt Road", "route": [[55, 0], [70, 0], [70, 40]]},
    {"a": "The Salt Road", "b": "The Carriers' Landing", "route": [[80, 3400], [160, 3470]]},
    {"a": "The Salt Road", "b": "The Glass Flats", "route": [[80, 700], [400, 700]]},
    {"a": "The Glass Flats", "b": "Red Ridge", "route": [[400, 700], [1500, 800], [2800, 1000], [3900, 1100]]},
    {"a": "The Glass Flats", "b": "The Bone Field", "route": [[1800, 400], [2450, -1600]]},
    {"a": "Red Ridge", "b": "The Deepwell", "route": [[4100, 1050, 0], [4150, 1000, -25]]},
    {"a": "The Bone Field", "b": "The Dry Camp", "route": [[2600, -2100], [2550, -2900], [2500, -3300, -4]]},
    {"a": "The Salt Road", "b": "The Crawler's Lee", "route": [[80, 1800], [96, 1800, 0]]},
    {"a": "The Salt Road", "b": "The Old Salt Works", "route": [[60, 5600], [-300, 5600, -2]]},
    {"a": "The Glass Flats", "b": "The Low Well", "route": [[2800, 1000], [3600, 100], [3950, -250, -6]]},
    {"a": "Red Ridge", "b": "The Low Well", "route": [[4050, 100, 0], [3950, -250, -6]]},
]


def lay_out(s):
    """Lay the Reach out in the world's one frame. Each piece is written once: an entity that has a layout of its own,
    a path that has a route and a root that has a frame are the owner's now, edited live, and a reboot leaves them as
    they are. Only what exists is placed. Returns the layout op's warnings."""
    w = s.world
    root = s.summary()["root"]
    ids = {e["name"]: e["id"] for e in s.world.find(limit=None)}
    places = [p for p in PLACES if p["entity"] in ids and not w.get(ids[p["entity"]])["state"].get("layout")]
    routes = [r for r in ROUTES if r["a"] in ids and r["b"] in ids
              and not any(ed["target"] == ids[r["b"]] and ed["data"].get("route") for ed in w.edges(ids[r["a"]], "connects_to", "out"))]
    frame = None if w.get(root)["state"].get("frame") else FRAME
    if not (places or routes or frame):
        return []
    return s.layout(frame=frame, placements=places, paths=routes)["warnings"]

SALVE = {"doses": 4, "heals": 3, "description": "A Keth pouch of glassroot salve: chewed root and fat, bitter, bound in a strip of hide.",
         "description_empty": "An empty Keth pouch. It still smells of glassroot."}


def keep_medic(s, iska):
    """Iska carries the Keth's glassroot salve: the Reach's one medicine, four doses. Given once (her `medic` mark), so
    a pouch she used up or handed over is not refilled on a reboot."""
    st = s.world.get(iska)["state"]
    if st.get("medic"):
        return
    s.spawn("medicine", iska, "Glassroot salve", state=SALVE)
    s.patch(iska, {"medic": True})


# What the speech of the Reach kept naming and the first build never made: the Keth's poisoned well, and the nine men
# Ruhl counts water for. Found by reading every line the NPCs said against what exists (2026-11-10).
LOW_WELL = ("A hollow at the south foot of Red Ridge, out of the wind, where a well-head of fitted stone stands over a dry "
            "throat. The Keth drew here before the Hold was built. The rope is gone, the bucket is gone, and nobody drinks.")
LOW_WELL_HEAD = {"portable": False, "poisoned": True,
                 "description": "Fitted stone, worn smooth at the lip by ropes. Far down there is still a dark shine, and a smell "
                                "of iron and something worse. Dreyer's poison is in it yet."}
CAIRNS = {"portable": False,
          "description": "Four cairns in a row by the lip, two of them small. Every stone in them was carried up from the Deepwell."}
RACK = {"holds": ["weapon"], "room": 8}  # a real blade can hang here beside the wooden ones; anyone in the yard can take it
BOWS = {"portable": False,
        "description": "Six short bows on pegs at the foot of the wall stair, strung, arrows standing in a jar beside them. "
                       "What the Hold has for anything past the gate."}

# The house's runner in the lee of the dead crawler off the Salt Road: a Dreyer newcomer starts beside him, out of
# earshot of the road, and learns there what became of Hollis. Anyone else gets road talk; only the word in the dreyer
# brief opens him. Scripted, no mind needed. The lee is shade, so he and his two long skins last the week.
LEE = ("The lee of a dead hauler beside the Salt Road: a rusted flank that throws the only shade for a mile, sand blown "
       "smooth against it, a hollow where someone sleeps. The road's wind goes over and leaves it quiet.")
RUNNER_NAME = "Wick the runner"
RUNNER_SKIN = {"capacity": 20, "left": 20, "description": "A runner's long skin, sewn double, sweating in the shade.",
               "description_full": "A runner's long skin, sewn double, sweating in the shade.",
               "description_empty": "A runner's long skin, slack and dry."}  # about a week of the open road
RUNNER = {"faction": "House Dreyer", "secret": ["dialog", "gives", "gave", "faction", "word_left"],
          "body": 2, "wits": 3, "will": 2, "skills": {"stealth": 2, "survival": 2}, "water": 10, "max_water": 10,
          "description": "A wiry runner in salt-white wraps, sitting in the shade of the dead crawler with two skins and a "
                         "staff across his knees. Waiting on the crawler south, by the look of him.",
          "brief": "You run letters for House Dreyer between the south and the Reach. You wait here for whoever the house "
                   "sends next, and you open only to the word saltmark.",
          "default_line": "Wick squints up from the shade. 'Waiting on the crawler south. The water's mine; the shade is free.'",
          "dialog": {
              "saltmark": "Wick looks at you a long moment, then shifts over in the shade. 'So the house sent another. Sit. "
                          "Hollis went into the Hold to count the water and the men. He wrote for ten days, then nothing. "
                          "The Guild at the Landing says the new reeve has him inside the walls, alive, no blade. Whether "
                          "he talked, nobody knows. The house's word is what it was: keep the Keth thirsty, keep the reeve "
                          "weak, learn what the Hold has. Do not go near Hollis openly.'",
              "hollis|dram|clerk": "'Never heard the name.' His eyes say he has.",
              "hold|reeve|gate|varrick|ruhl": "'Nine men and a captain who counts every draw. The cistern cracked; they live on "
                                              "what the Keth carry in at dusk and the cask the crawler leaves at dawn.'",
              "keth|ridge|deepwell|taan": "'The Keth sit up on Red Ridge on the only sweet water in the Reach, and trade it "
                                          "to the Hold now. That is new.'",
              "landing|ossa|guild|carrier": "'The Landing is up the road. Ossa keeps the tally. The Guild carries for "
                                            "whoever holds the gate, and forgets who held it before.'",
              "crawler|hauler|wreck|dead": "'A Guild hauler, stripped years back. The shade is the only thing left on it "
                                           "worth having.'"},
          "gives": {"saltmark": {"type": "thing", "name": "Sealed note for Hollis",
                                 "state": {"portable": True, "description": "A twist of oiled paper under grey wax with no "
                                           "mark pressed in it. Whoever reads the house's hand would read: hold, count, "
                                           "wait for word."},
                                 "line": "'For Hollis, if you reach him. Not before.'"}}}

# House Dreyer's hidden camp in the south dunes past the Bone Field: where a Dreyer newcomer comes in, Halvard Dreyer
# waits for the moon with the house's riders, and the house keeps the water it hauled up from the south. Hidden like
# the Deepwell, known only to Dreyer's own. Halvard is meant for a mind; the two camp hands answer from their tables.
DRY_CAMP = ("A hollow in the south dunes behind a rib of black rock: three low tents the colour of the sand, picket lines with "
            "no horses on them yet, a fire pit kept small. A squat iron tank sits half buried in the shade, and a pennant "
            "with a well and a bar across it hangs furled on a spear. Everyone here speaks quietly.")
HOUSE_TANK = {"portable": False, "water_source": True,
              "description": "A squat iron tank half buried in the shade, hauled up from the south on a crawler that did not "
                             "make the trip back. House Dreyer's own water, rationed by Mother Sallow."}
CAMP_SECRET = ["dialog", "gives", "gave", "faction", "word_left"]
HALVARD = {"faction": "House Dreyer", "secret": CAMP_SECRET,
           "body": 3, "wits": 4, "will": 4, "skills": {"blade": 2, "parley": 2, "lore": 1}, "vigor": 7, "max_vigor": 7,
           "description": "A lean man in a dust-grey coat cut like a rider's, close-cropped, a scar through one eyebrow. A "
                          "house cousin by the cut of him, and he listens longer than he talks.",
           "brief": "You are Halvard Dreyer, cousin to the house, and you hold the Dry Camp for the moon's turn. The Crown "
                    "gave the writ to Varrick; the house means to have Scar Gate back before the season ends, and the "
                    "riders come up from the south at the moon's turn. Your work until then: the Hold weak when they come "
                    "(its water short, its wall thin, its reeve doubted), the Keth thirsty and the truce broken, and Dram "
                    "Hollis freed or silenced, because he knows the house's hand and his letter said too much. Every "
                    "Dreyer man who comes in here is yours to brief and to use, and you choose with each what suits him: "
                    "a false name inside the Hold, a word in the Keth's ear, the glass, the road, or a message carried to "
                    "Hollis. You never go near the Hold yourself before the moon.",
           "default_line": "Halvard looks you over. 'Sit. Drink. Then tell me who you are going to be out there.'",
           "dialog": {"orders|house|task|work": "'The Hold weak when the riders come. Thirsty, thin on the wall, its reeve "
                                                "doubted. Pick a piece of that and bring it to me done.'",
                      "hollis|dram": "'Hollis yielded in his own ring. Whether he talked is the question. Find out.'",
                      "moon|riders|convoy": "'At the moon's turn the riders come up from the south. Until then we are "
                                            "not here.'"}}
SALLOW = {"faction": "House Dreyer", "secret": CAMP_SECRET,
          "body": 2, "wits": 3, "will": 3, "skills": {"survival": 2, "lore": 1},
          "description": "A broad grey woman with a ladle on a cord at her belt and a ledger of scratch marks on a slate. "
                         "Nobody drinks from the tank without her nod.",
          "brief": "You keep the house's water at the Dry Camp. Every draw is counted. You remember the Low Well.",
          "default_line": "Mother Sallow taps the slate. 'A draw a day, and you say your name when you take it.'",
          "dialog": {"water|tank|drink|draw|skin": "'Hauled up from the house's own wells in the south. A draw a day. The "
                                                   "Hold has a cracked cistern and the Keth's charity. We have this.'",
                     "well|poison|keth": "'The Keth say the house poisoned the Low Well. The house says the well went bad. "
                                         "I was there. Ask me again when you are older.'",
                     "hollis|dram": "'Dram drank here before he went in. One draw, and left the rest for the boys. Good "
                                    "manners. Bad luck.'",
                     "halvard|cousin": "'He waits better than any of them. That is why the house sent him.'"},
          "gives": {"water|tank|drink|draw|skin": {"type": "waterskin", "name": "House waterskin", "state": {"left": 3},
                                                   "line": "'One skin, full. Bring it back empty, not lost.'"}}}
BRISK = {"faction": "House Dreyer", "secret": CAMP_SECRET,
         "body": 3, "wits": 3, "will": 2, "skills": {"stealth": 3, "survival": 2},
         "description": "A thin rider in sand-coloured wraps with a long glass on a strap, forever looking north.",
         "brief": "You scout the Flats for the house. You have watched the Hold for a week from the dunes.",
         "default_line": "Brisk lowers the long glass. 'North is the Bone Field, then the Flats, then their gate. Walk it quiet.'",
         "dialog": {"thresher|sand|quiet|step|creep": "'Walk the deep sand loud and the thing under it comes. Walk it with a "
                                                     "broken step, odd beats, and it does not. Slower. Alive.'",
                    "hold|gate|wall|reeve": "'Nine men on that wall and a captain who counts every draw. A new reeve who "
                                            "stood in the ring with no blade and walked out. The Keth carry water up at dusk.'",
                    "keth|ridge|deepwell": "'The Keth sit on Red Ridge. They have water somewhere under it; I have never "
                                           "seen where. They hate us, and they are not wrong to.'",
                    "glass|vein|ember": "'Somebody dug the big vein on the Flats a few days back. Loud. A Hold man, by the "
                                        "coat. The Keth saw it too.'",
                    "road|salt|wick|landing": "'The Salt Road runs north from their gate past the Landing. Wick sits in the "
                                              "lee of the dead crawler and carries our letters. The Guild sells to anyone.'"}}
CAMP_PEOPLE = (("Halvard Dreyer", HALVARD), ("Mother Sallow", SALLOW), ("Brisk", BRISK))
# The camp keeps itself: the tank never runs dry (no level), the chest holds the house's salve, and Sallow hands a
# pouch to each of the house's own who comes to her hurt.
HOUSE_SALVE = {"doses": 3, "heals": 3, "description": "A house pouch of honey-and-ash salve, sealed with plain wax.",
               "description_empty": "An empty house pouch, sticky inside."}
MEDICINE_CHEST = {"portable": False, "holds": ["medicine"], "room": 8,
                  "description": "A brass-cornered chest in the shade of the tank, the house's salve packed in it in rows. "
                                 "Mother Sallow keeps the key on the cord with her ladle, and leaves it open in the camp."}
SALLOW_SALVE = {"wound|hurt|salve|medicine|heal|bleed|sick": {
    "type": "medicine", "name": "Pouch of house salve", "state": HOUSE_SALVE,
    "line": "'Sit. Show me.' She binds it, and presses a pouch into your hand. 'For the next one. There is always a next one.'"}}
SALLOW["dialog"]["wound|hurt|salve|medicine|heal|bleed|sick"] = ("'The chest by the tank has the house's salve. Take what "
                                                                  "you need and tell me, so I can count it.'")
SALLOW["gives"].update(SALLOW_SALVE)

GUARD = {"faction": "House Varrick", "body": 3, "wits": 2, "will": 3, "skills": {"blade": 2, "resolve": 1}, "vigor": 6, "max_vigor": 6}
# Ruhl's nine, in the order they are filled: a world that already has some of the Hold's men (a guest's guard, the
# old man lent to the Keth) gets only the rest. Six of them can hold a blade; the old man, the boy and the cook cannot.
NINE = [
    ("The oldest of the nine", {"skills": {"blade": 1, "stealth": 1, "survival": 2}, "blade": False,
        "description": "The oldest man on the Hold's wall, grey stubble, a sun-cured face, a slow way of standing. He has kept "
                       "his temper through three reeves.",
        "default_line": "The old one nods and keeps his mouth shut.",
        "dialog": {"low well|well|keth": "'I walked the Flats when the Low Well still had a name. Ask the Keth what it is now.'"}}),
    ("Brannoc Hale", {"blade": True,
        "description": "Big and slow to speak, sunburnt to the collar. The best bow on the wall and the worst cook in the Hold.",
        "default_line": "Brannoc looks at the captain before he answers. 'Ask Ruhl.'",
        "dialog": {"water|draw|drink": "'A draw a man at the change of the watch, when there is a draw. The captain counts.'",
                   "wall|bow|bows": "'Six bows and six of us who can pull one. The wall wants twenty. It gets us.'"}}),
    ("Tobin Marsh", {"blade": True,
        "description": "Narrow-faced, quick hands, a dice cup on a thong at his belt and no money to put in it.",
        "default_line": "Tobin rattles the empty dice cup. 'Nothing to bet, nothing to say.'",
        "dialog": {"reeve|varrick": "'He stood in the ring with no blade and bled for it. I had him at three to one against. I lost.'",
                   "keth|terms": "'Keth water tastes of stone. I am not complaining.'"}}),
    ("Edric Fane", {"blade": True,
        "description": "Young for the wall and careful about it, his blade oiled every morning whether it needs it or not.",
        "default_line": "Edric straightens. 'On watch.'",
        "dialog": {"dreyer|hollis|clerk": "'He counted us every day from the shade. Nine. He had the number right.'"}}),
    ("Osk Barran", {"blade": True,
        "description": "Thick in the shoulder, a broken nose set crooked, a slow grin he does not use on the captain.",
        "default_line": "Osk grins and says nothing.",
        "dialog": {"flats|glass|sand|thresher": "'I went out on the glass once, loud. Once.'"}}),
    ("Lute Callow", {"blade": True,
        "description": "Thin, sharp-eyed, the one Ruhl puts over the gate at night because he does not sleep much anyway.",
        "default_line": "Lute keeps his eyes on the road. 'Road's empty.'",
        "dialog": {"road|salt|landing|crawler": "'Crawler at dawn, dust before it. Anything else on that road, I see it first.'"}}),
    ("Pip", {"blade": False, "body": 2, "skills": {"stealth": 1, "survival": 1},
        "description": "A boy of twelve or so, the Hold's runner, all elbows, too thin for a blade and too quick to keep indoors.",
        "default_line": "Pip shrugs, already halfway to somewhere else.",
        "dialog": {"water|cask|jars": "'I carry it, I don't count it. The captain counts it.'"}}),
    ("Hobb", {"blade": False, "body": 2, "skills": {"survival": 1},
        "description": "The Hold's cook, lame in the left leg from a fall off the wall, flour in the creases of his hands.",
        "default_line": "Hobb stirs the pot. 'It is what it is.'",
        "dialog": {"food|eat|cook|bread": "'Salt bread and what the crawler brings. Water first, then I cook with what is left.'"}}),
    ("Garret Cole", {"blade": True,
        "description": "Square and quiet, a Varrick man from before the writ, the captain's second when there is need of one.",
        "default_line": "Garret waits for the captain's word.",
        "dialog": {"captain|ruhl": "'Ruhl does not cross a line he has drawn. That is the whole of him.'"}}),
]


# Hidden until someone looks (scripts/reach_finds.py): each find is a thing with `hidden`, the dc and skills of the check
# that turns it up, and what the finder sees. The place carries a hint (`hint` appended to `hint_on`'s description), so
# there is a reason to look. Each is made once, by name.
LOOK = ["search", "survival", "lore", "track"]
FINDS = [
    {"at": "The Bone Field", "type": "letter", "name": "Dreyer manifest", "dc": 14, "skills": LOOK,
     "hint_on": "The Bone Field", "hint": "The crawler's strongbox is still bolted under the sand side of the cab.",
     "state": {"portable": True,
               "description": "A stiff fold of oiled cloth from a crawler's strongbox, in a clerk's hand under a well-and-bar seal.",
               "text": "Crawler of House Dreyer, the south road. Carried: one iron tank, to the camp behind the rib of black "
                       "rock past the Bone Field. Six casks of well-black, for the Low Well, by night. Two riders' kit."},
     "found": "Down in the drift where the cab went under, a strongbox has burst its hasp. Inside, dry in oiled cloth, is a "
              "crawler's manifest under Dreyer's seal."},
    {"at": "The Crawler's Lee", "type": "letter", "name": "Hauler's log", "dc": 13, "skills": LOOK,
     "hint_on": "The Crawler's Lee", "hint": "Under the hauler's dash a lockbox is still bolted on, its lid rusted down.",
     "state": {"portable": True, "description": "A Guild log book swollen with old damp. The last pages can still be read.",
               "text": "Guild hauler fourteen, Ossa's tally. Last entry: riders off the south dunes under the well and the "
                       "bar. They took the casks and the driver's skin and left us the shade. I told them the Guild carries "
                       "for whoever holds the gate. They said they would hold it."},
     "found": "The lockbox under the dash gives on the third try in a puff of rust. Inside is a Guild log book, the last "
              "page written in a hurry."},
    {"at": "The Gate Yard", "type": "letter", "name": "Hollis's count", "dc": 14, "skills": ["search", "lore", "stealth"],
     "hint_on": "The Gate Yard", "hint": "One stone low in the wall by the ring sits a finger proud of the rest.",
     "state": {"portable": True, "description": "A slip of paper folded small, in a neat hand that is not a soldier's.",
               "text": "Men on the wall: nine, two of them boys. Bows: six, strung. Water: the cistern cracked, the Keth "
                       "carry at dusk, the Guild cask at dawn. The reeve walks the wall at night alone. The captain sleeps "
                       "in the yard. Wait for the moon."},
     "found": "The proud stone comes out with a little work. Behind it, folded small and dry, is a slip of paper in a "
              "careful hand."},
    {"at": "Scar Gate, the Hold", "type": "thing", "name": "Bronze wedge", "dc": 15, "skills": ["search", "lore"],
     "hint_on": "The cistern", "hint": "Deep in the crack, past where fingers reach, something catches the light that is not stone.",
     "state": {"portable": True,
               "description": "A bronze wedge the length of a thumb, driven into the cistern's crack from the inside and "
                              "hammered home. A well with a bar across it is stamped on its head."},
     "found": "Worked at with a bent nail, it comes loose: a bronze wedge, driven into the crack from the inside. Stamped "
              "on its head is a well with a bar across it."},
    {"at": "The Glass Flats", "type": "vein", "name": "Buried vein", "dc": 15, "skills": ["survival", "lore", "track", "search"],
     "hint_on": "The Glass Flats", "hint": "Out past the worked veins the dunes have pulled back further, and at noon the sand there has a red cast.",
     "state": {"ember": 5, "description": "A wide seam of bright red glass under a skin of sand, the richest on the Flats. "
                                          "The sand over it is deep."},
     "found": "Where the dune has pulled back furthest, a hand of sand brushed aside shows red glass, wide as a door and "
              "bright. Nobody has dug here."},
    {"at": "The Salt Road", "type": "waterskin", "name": "Guild cache skin", "dc": 12, "skills": ["survival", "search", "lore"],
     "hint_on": "Salt-block cairn", "hint": "",
     "state": {"capacity": 6, "left": 6, "description": "A Guild skin, full, buried a hand deep under the cairn and cool from the sand.",
               "description_full": "A Guild skin, full, buried a hand deep under the cairn and cool from the sand."},
     "found": "Under the cairn, a hand deep and wrapped in sacking, is a Guild skin, full and cool. Carriers leave water "
              "where the road is longest."},
    {"at": "The Low Well", "type": "thing", "name": "Empty phial", "dc": 13, "skills": LOOK,
     "hint_on": "Four cairns", "hint": "One stone in the smallest has been lifted and put back wrong.",
     "state": {"portable": True,
               "description": "A clay phial the length of a finger, stoppered and empty, the wax on it pressed with a well "
                              "and a bar. It smells of iron and something worse, like the well."},
     "found": "The wrong-set stone lifts. Under it, where someone hid it in a hurry and never came back, is an empty clay "
              "phial sealed with Dreyer's wax."},
]
CAIRN = {"portable": False, "description": "Three blocks of salt stacked at the road's edge, the top one marked with a Guild "
                                           "chalk ring. Carriers leave these where they leave something."}


# The Old Salt Works (scripts/reach_moon.py): five drifters up the road past the Landing who sell their arms. Paid by
# the Hold (a shard of glass or a skin with water in it) a drifter goes to the wall and counts at the moon; bought by
# Dreyer he goes too, and counts against it. Guild pitch at the Landing mends the cistern once the wedge is out.
SALT_WORKS = ("Brine pans gone to crust west of the road, a collapsed boiling shed, and a seep the drifters strain "
              "through cloth into a stone trough. Men who missed the last convoy sit in the shed's shade and wait for "
              "someone to pay them for something.")
SEEP = {"portable": False, "water_source": True,
        "description": "A brackish seep strained through cloth into a stone trough. It tastes of salt and keeps you alive."}
DRIFTER = {"body": 3, "wits": 2, "will": 2, "skills": {"blade": 1, "survival": 1}, "vigor": 6, "max_vigor": 6,
           "drifter": True, "secret": ["dialog", "turncoat", "bought_by", "word_left"]}
DRIFTER_WORK = {"work|hire|pay|wall|sign|fight": "'A shard of glass or a skin with water in it, and I go where you send "
                                                 "me. I do not ask whose wall.'",
                "dreyer|house|riders": "'Riders in the south, they say. Riders pay too.'",
                "hold|varrick|reeve|gate": "'The Hold wants twenty and has nine. A man could eat there.'"}
DRIFTERS = [
    ("Cass the Salter", "A woman with salt-cracked hands who boiled brine here when the works still ran. Steady.",
     "Cass looks up from the trough. 'Pay first. Then I listen.'"),
    ("Joss", "A big quiet man with a Guild brand on his forearm and no Guild coat.",
     "Joss says nothing and looks at your water."),
    ("Merrow", "Young, quick, too thin, a crawler mechanic's rag still tucked in his belt.",
     "Merrow grins. 'You hiring? I can fix anything that moves.'"),
    ("Lark", "Older than she looks, a short bow across her back with no string on it.",
     "Lark watches the road, not you. 'String costs. Wall costs more.'"),
    ("Dunmore", "A road-worn man who flinches at loud noise and was a soldier once, somewhere.",
     "Dunmore nods without looking up. 'I have stood on walls. They fall.'"),
]
PITCH = {"portable": True, "bulk": 2, "description": "A clay pot of Guild crawler pitch, black and sticky, for sealing tanks."}

# The Guild's road wardens (scripts/reach_wardens.py): a post on the Salt Road where every road in the Reach meets.
# Three spears and two bows, fighters who strike back when struck, under a sergeant who keeps the ledger.
WARDEN = {"faction": "the Carriers", "warden": True, "body": 3, "wits": 3, "will": 3, "skills": {"blade": 3, "resolve": 2},
          "vigor": 8, "max_vigor": 8, "water": 20, "max_water": 20, "secret": ["dialog", "word_left"]}
SPEAR = {"weapon": True, "damage": 2, "bonus": 1, "portable": True,
         "description": "A Guild warden's spear, ash shaft gone grey, the head bound on with wire."}
BOW = {"weapon": True, "damage": 2, "bonus": 1, "portable": True,
       "description": "A Guild warden's short bow of horn and glue, strung, a quiver of reed arrows with it."}
WARDEN_WORK = {"road|post|pass|toll|warden|guild": "'The road is the Guild's. Carriers pass. The Hold's coats pass. New faces "
                                                  "give a name. Glass off the Flats pays one at the post. A shard buys a "
                                                  "day's road for anyone, no questions.'",
               "dreyer|house|south|riders": "'Nobody honest comes up off the south glass. Anyone who does goes back down "
                                            "it, unless they pay.'",
               "keth|iska|yoke": "'The yoke walks this road at dusk. Nobody here stops the yoke.'"}
WARDENS = [
    ("Sergeant Edda Marr", "spear", "A square grey woman in a Guild coat with the sleeves cut off, a ledger on her knee and "
     "a spear across it. She has kept this post through two reeves and does not expect to see a third.",
     "Marr looks up from the ledger. 'Name, and your business on the Guild's road.'"),
    ("Kell Daro", "spear", "A tall warden with a broken nose and a patient way of standing in the middle of the road.",
     "Kell Daro does not move out of the way. 'Sergeant asked you something.'"),
    ("Tavish Orme", "spear", "Young for a warden, sunburnt, with his spear butt grounded and his eyes on the Flats.",
     "Tavish nods at the glass. 'Thresher's been loud this week. Walk soft.'"),
    ("Nell Saye", "bow", "A narrow woman on the cairn above the post with a short bow across her knees and nothing to say.",
     "Nell Saye watches the road past you."),
    ("Quill", "bow", "A boy-faced bowman with a quiver of reed arrows he fletches himself while he watches.",
     "Quill holds up an arrow to the light. 'Straight. You walking south?'"),
]


def keep_wardens(s, names):
    """The wardens' post on the Salt Road: five fighters, each with a spear or a bow. Made once, by name."""
    road = names.get("The Salt Road")
    if road is None:
        return
    for name, arm, look, line in WARDENS:
        if name in names:
            continue
        w = s.spawn("fighter", road, name, state={**WARDEN, "description": look, "default_line": line,
                                                    "dialog": dict(WARDEN_WORK), "post": road})["id"]
        s.spawn("thing", w, "Warden's spear" if arm == "spear" else "Warden's bow", state=dict(SPEAR if arm == "spear" else BOW))


def keep_carry(s):
    """Newcomers who came in before carrying had a limit get the template's 8."""
    for e in s.world.find(type="person", limit=None):
        st = s.world.get(e["id"])["state"]
        if st.get("template") and st.get("carry") is None:
            s.patch(e["id"], {"carry": 8})


def keep_salt_works(s, names):
    """The Old Salt Works and its five drifters off the Salt Road, and two pots of Guild pitch at the Landing.
    Each made once, by name; a drifter already gone to the wall stays where he went."""
    if "The Old Salt Works" not in names and "The Salt Road" in names:
        works = s.spawn("place", s.summary()["root"], "The Old Salt Works", state={"description": SALT_WORKS, "open": True})["id"]
        names["The Old Salt Works"] = works
        s.connect(names["The Salt Road"], works)
        s.spawn("thing", works, "The salt seep", state=SEEP)
        for name, look, line in DRIFTERS:
            s.spawn("person", works, name, state={**DRIFTER, "description": look, "default_line": line,
                                                   "dialog": dict(DRIFTER_WORK), "post": works, "water": 10, "max_water": 10})
        story = s.world.find(type="story", limit=1)[0]["id"]
        s.patch(story, {"salt_works": works})
    if "Pot of Guild pitch" not in names and "The Carriers' Landing" in names:
        for _ in range(2):
            s.spawn("thing", names["The Carriers' Landing"], "Pot of Guild pitch", state=dict(PITCH))


def keep_finds(s, names):
    """The hidden finds, the cairn on the Salt Road that marks one, the hint on each place, and the camp's stores (the
    medicine chest with four pouches of the house's salve, Sallow's pouch for the hurt). Checks before every write."""
    if "Salt-block cairn" not in names and "The Salt Road" in names:
        names["Salt-block cairn"] = s.spawn("thing", names["The Salt Road"], "Salt-block cairn", state=CAIRN)["id"]
    for f in FINDS:
        if f["at"] not in names:
            continue
        if f["name"] not in names:
            names[f["name"]] = s.spawn(f["type"], names[f["at"]], f["name"], state={
                **f["state"], "hidden": True, "find_dc": f["dc"], "find_skills": f["skills"], "find_text": f["found"]})["id"]
        on = names.get(f["hint_on"])
        if on and f["hint"]:
            d = s.world.get(on)["state"].get("description") or ""
            if f["hint"] not in d:
                s.patch(on, {"description": (d + " " + f["hint"]).strip()})
    camp = names.get("The Dry Camp")
    if camp and "The house's medicine chest" not in names:
        chest = s.spawn("thing", camp, "The house's medicine chest", state=MEDICINE_CHEST)["id"]
        names["The house's medicine chest"] = chest
        for _ in range(4):
            s.spawn("medicine", chest, "Pouch of house salve", state=dict(HOUSE_SALVE))
    sallow = names.get("Mother Sallow")
    if sallow:
        st = s.world.get(sallow)["state"]
        if "wound|hurt|salve|medicine|heal|bleed|sick" not in (st.get("gives") or {}):
            s.patch(sallow, {"gives": SALLOW_SALVE, "dialog": {k: SALLOW["dialog"][k] for k in SALLOW["dialog"]}})


# West of the Scar: nobody knows (settled with Nate 2026-11-11, notes/west-of-the-scar.md). The back gate has been
# sealed since before anyone living was born; the world holds a few books, a scraped map, the Keth's old count and one
# rumour each, and they partly disagree. The daybook's torn pages are not in the world: finding them starts the quest
# that opens the seal. What lies behind it is not decided.
BACK_GATE = {"portable": False, "sealed": True,
             "description": "A doorway in the Hold's west wall, as wide as a cart, filled with fitted stone and lime. The "
                            "Crown's seal is pressed into the mortar at head height, a crown over a closed eye, worn soft. "
                            "Nobody has hung anything on this wall."}
SHELF = {"portable": False,
         "description": "A plank shelf on two pegs by the hall map, with three books on it that nobody has dusted in a "
                        "long while."}
BOOKS = [
    ("The Hold's daybook",
     "A thick book in many hands, kept by every reeve and captain since the Hold was raised.",
     "The early hands are hard to read. The Hold was raised by the Crown's masons 'in the year the wall went up behind "
     "it'. Water counts, convoy days, deaths, a reeve's name every few years. Then an entry headed OF THE BACK GATE, in "
     "a careful clerk's hand: 'By the Crown's word the back gate is closed this day, and no reeve is to open it, nor to "
     "ask why, nor to let it be asked.' After that line a run of pages has been torn out close to the spine. The stubs "
     "show writing on every one. The next whole page is in another hand, years later, counting water as if nothing had "
     "happened. Dreyer's eleven years come near the end: tidy, and they never mention the gate."),
    ("A Crown surveyor's account of the Scar",
     "A thin book in Crown binding, the spine cracked.",
     "A long, dry report. The Scar runs unbroken from the salt in the north to the dunes in the south, more than forty "
     "miles, and nowhere lower than a tall man standing on another's shoulders. There is one gap. 'West of the gap the "
     "defile runs a mile and a half between walls so close a laden mule must be backed out, and comes out upon' and the "
     "rest of the page is gone. The next page begins on the salt pans, as if the surveyor had been told to start again."),
    ("The Guild's route book, Reach leg",
     "A greasy ledger of Guild prices with a red first page.",
     "Prices, crawler weights, the Landing's tally rules. On the first page, in red: 'Standing order, renewed with every "
     "charter: no crawler, carrier or beast of the Guild is to be taken through the Scar. The Guild does not carry "
     "west.' In the margin, in pencil, someone has written: 'older than the Guild. ask who wrote it.'"),
]
HALL_MAP = {"portable": False,
            "description": "A big map on hide, nailed up in the hall. Nobody trusts it.",
            "text": "The Reach is drawn well: the road, the Landing, the ridge, the Flats. West of the Scar the ink has "
                    "been scraped away down to bare hide, carefully, all of it. At the scraped edge, where the gap would "
                    "come out, a few strokes were missed: the end of one word, '...ashe', and part of a line that might "
                    "be a river."}
OLD_COUNT = {"portable": True,
             "description": "A stick of black wood worn smooth by hands, notched along its length.",
             "text": "Read by touch, the notches tell an old count: nine hands of Keth walked west through the gap in the "
                     "time of the grandmothers' grandmothers, when there was no wall. Then the stone closed behind them. "
                     "The last notches are cut deeper than the rest. The Keth keep the count for them, because they "
                     "never came back to keep it themselves."}
# what each has heard, never what is true; Taan keeps the old count and lets only someone she trusts touch it
RUMOURS = {
    "Ossa the Carrier": "What I know of the west: the Guild's charter forbids carrying through the Scar, and the clause "
                        "is older than the Guild. Carriers who ask why get no new contract. I stopped asking.",
    "Captain Ruhl": "Soldiers' talk I put down: on still nights a man on the wall stair hears wind behind the sealed "
                    "back gate, 'as if there's a lot of air back there'. Nonsense. I move that man to another watch.",
    "Dram Hollis": "In Dreyer's years a house man was caught at the back gate with a pry bar. He was sent away the next "
                   "morning, and the house paid the Crown a fine nobody would name. I kept the books; I never saw the sum.",
    "Elder Taan": "I keep the old count: the stick of the nine hands of Keth who walked west through the gap before the "
                  "wall, and never came back. I speak of it only to one who has kept faith with the Keth, never at the "
                  "Hold, and I let only such a one touch the stick.",
    "Sergeant Edda Marr": "Drifters say a light shows on top of the Scar some nights, on the west side, where nobody "
                          "could climb. I have not seen it. I have not looked hard.",
    "Halvard Dreyer": "An old house story: Dreyer wanted Scar Gate for what lies behind it, not for the glass. I think "
                      "my grandfather told it to make a dry posting sound grand.",
    "Cass the Salter": "The brine seep under the works runs from the west, under the Scar, and it tastes of something "
                       "that is not the Reach.",
}
CASS_WEST = ("'The seep comes from the west, under the Scar. Taste it if you like. It isn't Reach salt.' She goes back "
             "to the trough.")


def keep_lore(s, names):
    """West of the Scar (notes/west-of-the-scar.md): the sealed back gate, the hall map and the shelf of three books in
    the Hold, the old count in Elder Taan's keeping, and one rumour each in memory. Things are made once by name; the
    rumours once, by a mark on the story, so a forgotten or traded-away note is not written again on a reboot."""
    hold = names.get("Scar Gate, the Hold")
    if hold is None:
        return
    if "The sealed back gate" not in names:
        s.spawn("thing", hold, "The sealed back gate", state=dict(BACK_GATE))
    if "The hall map" not in names:
        s.spawn("letter", hold, "The hall map", state=dict(HALL_MAP))
    if "The Hold's shelf" not in names:
        s.spawn("thing", hold, "The Hold's shelf", state=dict(SHELF))
    for name, look, text in BOOKS:
        if name not in names:
            s.spawn("letter", hold, name, state={"portable": False, "description": look, "text": text})
    if "The old count" not in names and "Elder Taan" in names:
        s.spawn("letter", names["Elder Taan"], "The old count", state=dict(OLD_COUNT))
    story = s.world.find(type="story", limit=1)[0]["id"]
    if s.world.get(story)["state"].get("west_rumours"):
        return
    for who, text in RUMOURS.items():
        if who in names:
            s.remember(text, entity=names[who])
    if "Cass the Salter" in names:
        dialog = dict(s.world.get(names["Cass the Salter"])["state"].get("dialog") or {})
        dialog["west|scar|seep|brine|gate"] = CASS_WEST
        s.patch(names["Cass the Salter"], {"dialog": dialog})
    s.patch(story, {"west_rumours": True})

# The wall works (packs/works, docs/WORKS.md; settled with Nate 2026-11-11). The broken stretch of the yard wall can be
# raised in three courses; each one laid and set counts as a man on the wall at the moon (reach_moon, reach_chapter).
# Stone is dressed out of the rubble at the foot of the Scar, lime comes from Ossa at her price, and a Guild mason
# walks in at the next dawn looking for the work. Dreyer has every reason to stop it: lime and stone can be taken, the
# mason goes unpaid, and a course still setting can be pulled down.
LEADERS = {"House Varrick": ["Reeve Ansel Varrick", "Captain Ruhl"], "the Keth": ["Elder Taan"],
           "House Dreyer": ["Halvard Dreyer"], "the Carriers": ["Ossa the Carrier"]}


def course(n, word):
    return {"name": word + " course", "labour": 12, "needs": {"Dressed stone": 4, "lime": 1}, "roles": {"mason": 1, "hand": 2},
            "settles": 6,
            "scene": f"The {word} course is laid along the broken stretch, stone on stone in a bed of wet lime. It wants six "
                     f"hours to set before anyone leans on it.",
            "undone": f"The {word} course comes down while the lime is still soft: blocks tipped into the yard, the bed scraped "
                      f"out. It will all have to be laid again."}


WALL_PLAN = {
    "portable": False, "patrons": ["House Varrick"], "hours": [0, 12], "pay_every": 86400,
    "description": "A line of chalk on the yard flags along the broken stretch of the wall, with tally marks for three "
                   "courses beside it.",
    "text": "Ruhl's chalk, in a soldier's square hand: three courses along the broken stretch, each four dressed stones "
            "in lime, a mason to lay them and two hands to lift. Each course must set six hours. Every course that "
            "stands is one man the riders count on the wall.",
    "begun_scene": "The wall works begin: the chalk line is scraped clean, the old footing swept, a lime trough set "
                   "down by the broken stretch.",
    "stages": [course(1, "first"), course(2, "second"), course(3, "third")],
    "becomes": {"type": "thing", "name": "The raised wall",
                "state": {"portable": False, "wall_men": 3,
                          "description": "The broken stretch of the yard wall, raised again in three courses of new stone, "
                                         "pale against the old. The riders will count it."},
                "scene": "The third course has set. The broken stretch of the yard wall stands whole again, three courses of "
                         "pale new stone in the old grey, and the works come down."},
}
RUBBLE = {"portable": False, "stone": 24,
          "description": "A spill of fallen Scar stone at the foot of the yard wall, under the ridge. Good stone, if someone "
                         "puts a chisel to it."}
LIME = {"portable": True, "kind": "lime", "bulk": 2,
        "description": "A Guild sack of quicklime, stencilled and tied. It burns wet hands."}
MASON_NAME = "Jory Flint"
MASON = {"body": 3, "wits": 2, "will": 2, "skills": {"survival": 1}, "water": 10, "max_water": 10, "carry": 8,
         "faction": None, "playable": False,
         "description": "A broad man with lime-burnt hands and a mason's hammer through his belt, dust to the knees.",
         "for_hire": {"wage": {"kind": "ember", "count": 1}, "roles": ["mason"],
                      "line": "A shard a day, paid at dawn, and I lay you a course a day. Don't pay me and I walk."},
         "default_line": "Jory looks along the broken stretch. 'Wall work. I'm for hire: a shard a day.'",
         "dialog": {"wall|work|course|stone|build": "'Four dressed stones and a sack of lime a course. Two hands to lift, "
                                                    "me to lay. Six hours to set, and nobody leans on it till then.'",
                    "pay|shard|wage|hire": "'A shard of glass a day, out of the works, at dawn. Two dawns with nothing "
                                           "and I'm on the next crawler.'",
                    "guild|ossa|crawler|landing": "'Came up on the dawn crawler. Ossa said the Hold wanted wall work. "
                                                  "She didn't say why.'",
                    "dreyer|keth|ruhl|reeve": "'I lay stone. Whose wall it is, I don't ask.'"}}
MASON_REMEMBERS = ["I came up on the dawn crawler from the Landing. Ossa the Carrier said the Hold at Scar Gate wanted "
                   "wall work. I ask a shard of emberglass a day, paid at dawn, and I leave after two dawns unpaid."]


def keep_works(s, names):
    """The wall works: the chalked plan in the Gate Yard, the rubble under the wall, three sacks of lime in Ossa's
    stock, the faction leaders who may put their people to work, and Jory Flint on the next dawn crawler. Each thing is
    introduced once by name, always there and known to those who would know it; the mason once, by a mark on the
    story, so a reboot does not send for him again."""
    yard = names.get("The Gate Yard")
    if yard is None:
        return
    for f in s.world.find(type="faction", limit=None):
        want = LEADERS.get(f["name"])
        if want and s.world.get(f["id"])["state"].get("leader") is None:
            s.patch(f["id"], {"leader": want})
    know = [n for n in ("Captain Ruhl", "Reeve Ansel Varrick", "Dram Hollis") if n in names]
    if "The wall line" not in names:
        s.introduce("blueprint", yard, "The wall line", how="always_there", state=dict(WALL_PLAN),
                    known_by={n: "Ruhl chalked the broken stretch of the yard wall for raising: three courses of dressed "
                                 "stone in lime. Every course that stands counts as a man on the wall at the moon. It "
                                 "wants a mason and two hands, stone from the rubble, and Guild lime." for n in know})
    if "Scar rubble" not in names:
        s.introduce("rubble", yard, "Scar rubble", how="always_there", state=dict(RUBBLE),
                    known_by={n: "The rubble under the yard wall is good Scar stone: a chisel squares a block out of it in "
                                 "half an hour." for n in know})
    ossa = names.get("Ossa the Carrier")
    if ossa and not any(e["name"] == "Sack of lime" for e in s.world.find(name="Sack of lime", limit=None)):
        for _ in range(3):
            s.introduce("thing", ossa, "Sack of lime", how="always_there", state=dict(LIME), known_by={})
        s.remember("Three sacks of Guild lime came up on the crawler for me to sell. The Hold will want them for the "
                   "wall: a sack a course. The price is mine to name.", entity=ossa)
    story = s.world.find(type="story", limit=1)[0]["id"]
    if s.world.get(story)["state"].get("mason_sent") or MASON_NAME in names:
        return
    t = s.world.t
    after = 86400 - (t % 86400) or 86400
    s.introduce("person", yard, MASON_NAME, how="arrived", after=after, state=dict(MASON),
                scene="A broad man walks in off the Salt Road with a mason's hammer through his belt, dust to the knees, "
                      "and stops to look along the broken stretch of the wall.",
                known_by={ossa: "The Guild sends a mason up on the next dawn crawler, Jory Flint, for the Hold's wall "
                                "work. He asks a shard a day."} if ossa else {},
                remembers=list(MASON_REMEMBERS))
    s.patch(story, {"mason_sent": True})


# Who nailed the notice by the cistern (Nate 2026-11-11: explained in the world, and discoverable). The Host: the Crown's
# sworn water-wardens, who ride the Reach by night under the closed-eye seal (the seal on the back gate) and keep the
# water law without showing themselves. On the ninth they raised the three the thirst put down (Ruhl in the yard, Nico
# and Sefa on the ridge), filled their skins, and nailed the ration notice in their own cant. Four clues, none of them
# the whole: a Crown flask with the Host's tag in the scree on Red Ridge (a hidden find), what Wick saw on the road that
# night, the fine in Dreyer's books entered "to the Host", and the Guild charter's clause; Taan knows the old name.
HOST_FLASK_NAME = "A Crown flask"
HOST_FLASK = {"portable": True, "hidden": True, "find_dc": 13, "find_skills": ["search", "survival", "lore", "track"],
              "find_text": "Wedged in the scree where the two Keth went down on the ninth: a flask of Crown pewter, empty, "
                           "its cap on a cord, and a paper tag tied to the cord.",
              "description": "An empty flask of Crown pewter, stamped with a crown over a closed eye. A paper tag is tied to "
                             "its cord.",
              "text": "The tag is written in a careful, slanting clerk's hand, the same hand as the notice by the cistern: "
                      "'Ninth night. Three down of thirst: the captain in the yard, two of the Keth on the ridge. Raised, "
                      "and their skins filled. The ration is set and posted at the cistern for the gate. The Host.'"}
HOST_HINT = "Something pewter catches the light in the scree below the lookout rock."
WICK_HOST = ("'A rider came up the road the night of the ninth. No lamp, and a crown over a shut eye on the saddle "
             "cloth. Went up to the Hold and came back down before the light. Didn't stop for me, and I didn't ask him "
             "to.'")
HOST_KNOWS = {
    "Elder Taan": "The Keth have an old name for the Crown's night riders who keep the water law: the Host. They come "
                  "without lamps and leave no track a Keth can read. In the grandmothers' time they were seen raising "
                  "those the thirst had put down, and nailing the Crown's word where the water is kept. I speak of them "
                  "only to one who has kept faith with the Keth.",
    "Dram Hollis": "In Dreyer's books, the fine the house paid the Crown for the man caught at the back gate was entered "
                   "'to the Host'. Not to the Crown, not to the reeve: to the Host. I never learned who that is.",
    "Ossa the Carrier": "The Guild's charter has a clause no carrier reads aloud: water rights in the Reach are held "
                        "'under the Host of the Crown'. I have never met anyone who says they are the Host.",
}


def keep_host(s, names):
    """The Host's flask hidden on Red Ridge with the hint in the ridge's description, Wick's line about the rider, and
    what Taan, Hollis and Ossa know of the Host. The flask by name; the rest once, by a mark on the story."""
    ridge = names.get("Red Ridge")
    if ridge and HOST_FLASK_NAME not in names:
        s.introduce("letter", ridge, HOST_FLASK_NAME, how="always_there", state=dict(HOST_FLASK), known_by={})
    if ridge:
        d = s.world.get(ridge)["state"].get("description") or ""
        if HOST_HINT not in d:
            s.patch(ridge, {"description": (d + " " + HOST_HINT).strip()})
    story = s.world.find(type="story", limit=1)[0]["id"]
    if s.world.get(story)["state"].get("host_lore"):
        return
    if RUNNER_NAME in names:
        dialog = dict(s.world.get(names[RUNNER_NAME])["state"].get("dialog") or {})
        dialog["rider|ninth|night|lamp|host|notice|eye"] = WICK_HOST
        s.patch(names[RUNNER_NAME], {"dialog": dialog})
    for who, text in HOST_KNOWS.items():
        if who in names:
            s.remember(text, entity=names[who])
    s.patch(story, {"host_lore": True})


# Burning (Nate 2026-11-11): a letter burned at a fire is gone from the world and lives on only in the memory of whoever
# read it. Paper burns; the Guild's tally post and the Host's pewter flask do not. The Hold has a hearth and the Deepwell
# its cookfire, so there is somewhere to burn a thing on both sides of the truce.
NOT_PAPER = {"Tally post", "A Crown flask"}
HEARTH_NAME = "The hearth"
HEARTH = {"portable": False, "fire": True,
          "description": "A deep stone hearth in the hall, banked low against the heat of the day. The reeve's men keep it in "
                         "for the night cold and the cookpot."}


def keep_burn(s, names):
    """Every letter says whether it burns (paper does), a hearth that was always in the Hold, and the Deepwell's
    cookfire burning. Checks before every write."""
    for e in s.world.find(type="letter", limit=None):
        if "burnable" not in s.world.get(e["id"])["state"]:
            s.patch(e["id"], {"burnable": e["name"] not in NOT_PAPER})
    hold = names.get("Scar Gate, the Hold")
    if hold and HEARTH_NAME not in names:
        s.introduce("thing", hold, HEARTH_NAME, how="always_there", state=dict(HEARTH), known_by={})
    well = names.get("The Deepwell")
    if well and not s.world.get(well)["state"].get("fire"):
        s.patch(well, {"fire": True})


def keep_canon(s):
    """The Low Well (a place off the Flats and the ridge, with its dry poisoned well-head and the four Keth cairns), the
    bows on the Hold's wall, the Crawler's Lee off the Salt Road with Wick the Dreyer runner in it, House Dreyer's
    hidden Dry Camp past the Bone Field (Halvard Dreyer, Mother Sallow, Brisk, the house's tank), and Ruhl's nine. Each is made once: the well and the bows by name, the nine by a mark on
    the story, so a guard who dies is not raised again on a reboot. The nine are posted in the Hold, where a body with
    water at hand does not thirst; they drink when the Hold runs dry, like everyone under its roof."""
    names = {e["name"]: e["id"] for e in s.world.find(limit=None)}
    story = s.world.find(type="story", limit=1)[0]["id"]
    st = s.world.get(story)["state"]
    root = s.summary()["root"]
    if "The Low Well" not in names:
        well = s.spawn("place", root, "The Low Well", state={"description": LOW_WELL})["id"]
        s.connect(st["flats"], well)
        s.connect(st["ridge"], well)
        s.spawn("thing", well, "The Low Well's head", state=LOW_WELL_HEAD)
        s.spawn("thing", well, "Four cairns", state=CAIRNS)
        s.patch(story, {"low_well": well})
    if "Bows on the wall" not in names:
        s.spawn("thing", st["hold"], "Bows on the wall", state=BOWS)
    if "The Crawler's Lee" not in names:
        names["The Crawler's Lee"] = s.spawn("place", root, "The Crawler's Lee", state={"description": LEE})["id"]
        s.connect(names["The Salt Road"], names["The Crawler's Lee"])
    if "The Dry Camp" not in names:
        camp = s.spawn("place", root, "The Dry Camp", state={"description": DRY_CAMP, "hidden": True, "known_to": "House Dreyer"})["id"]
        names["The Dry Camp"] = camp
        s.connect(names["The Bone Field"], camp)
        s.spawn("thing", camp, "The house's tank", state=HOUSE_TANK)
        for name, table in CAMP_PEOPLE:
            s.spawn("person", camp, name, state={**table, "post": camp, "water": 10, "max_water": 10})
        s.patch(story, {"dry_camp": camp})
    if RUNNER_NAME not in names:
        lee = names["The Crawler's Lee"]
        wick = s.spawn("person", lee, RUNNER_NAME, state={**RUNNER, "post": lee})["id"]
        for _ in range(2):  # the two skins he waits with: his own water, not a well for whoever passes
            s.spawn("waterskin", wick, "Runner's skin", state=dict(RUNNER_SKIN))
    rack = names.get("Rack of practice blades")
    if rack and s.world.get(rack)["state"].get("holds") is None:
        s.patch(rack, RACK)
    keep_finds(s, names_of(s))
    keep_salt_works(s, names_of(s))
    keep_wardens(s, names_of(s))
    keep_lore(s, names_of(s))
    keep_works(s, names_of(s))
    keep_host(s, names_of(s))
    keep_burn(s, names_of(s))
    keep_carry(s)
    if st.get("garrison"):
        return
    hold, ruhl = st["hold"], st["ruhl"]
    bodies = s.world.find(type="person", limit=100000) + s.world.find(type="fighter", limit=None)
    have = len({e["id"] for e in bodies if s.world.get(e["id"])["state"].get("faction") == "House Varrick"} - {ruhl, st["ansel"]})
    for name, spec in NINE:
        if have >= 9:
            break
        if name in names:
            continue
        spec = dict(spec)
        armed = spec.pop("blade")
        man = s.spawn("person", hold, name, state={**GUARD, **spec, "post": hold, "water": 10, "max_water": 10})["id"]
        if armed:
            s.spawn("thing", man, "Varrick blade", state={"weapon": True, "damage": 2, "bonus": 0, "portable": True,
                                                         "description": "A plain House Varrick blade, the grip rewrapped in cord."})
        s.link(ruhl, man, "knows", {"standing": 2, "note": "one of my nine", "met_t": 0, "count": 0})
        s.link(man, ruhl, "knows", {"standing": 3, "note": "the captain; he counts the water", "met_t": 0, "count": 0})
        have += 1
    s.patch(story, {"garrison": True})


def keep_routines(s, root):
    """What the routines need (Iska at the Deepwell, the Keth jars and the Guild's ration cask in the Hold), the rule
    that runs them, and one daily timer each, on the hour of the spine event it starts with. Checks before every write."""
    names = {e["name"]: e["id"] for e in s.world.find(limit=None)}
    story = s.world.find(type="story", limit=1)[0]["id"]
    st = s.world.get(story)["state"]
    if "Iska of the Keth" not in names:
        names["Iska of the Keth"] = s.spawn("person", st["deepwell"], "Iska of the Keth", state=BEARER)["id"]
    if "The Keth jars" not in names:
        names["The Keth jars"] = s.spawn("thing", st["hold"], "The Keth jars", state={"portable": False, "water_source": True, "left": 0,
            "description": "Two tall Keth jars by the dry cistern, sealed with wax. What the bearer pours at dusk, while the terms hold."})["id"]
    if "The Hold's ration cask" not in names:
        names["The Hold's ration cask"] = s.spawn("thing", st["hold"], "The Hold's ration cask", state={"portable": False, "water_source": True, "left": 0,
            "description": "A Guild cask stencilled with the Varrick mark. The crawler rolls a full one off at dawn; the writ pays."})["id"]
    keep_medic(s, names["Iska of the Keth"])
    want = {"bearer": names["Iska of the Keth"], "keth_jars": names["The Keth jars"], "hold_ration": names["The Hold's ration cask"]}
    if any(st.get(k) != v for k, v in want.items()):
        s.patch(story, want)
    s.set_rule(root, "reach_routines", kinds=ROUTINE_KINDS)
    timers = s.timers()
    for kind, rides in HOSTED["routines"]:
        if any(t["kind"] == kind and t["every"] for t in timers):
            continue
        spine = next((t for t in timers if t["kind"] == rides and t["every"]), None)
        if spine is not None:
            s.schedule(max(0.0, spine["in"]), kind, entity=root, every=spine["every"])
    lay_out(s)  # the jars and the cask came after the first pass


def host(s):
    """The Reach as a hosted place (`embody load glass-reach --hosted`). Seats lapse after an hour of quiet; the clock
    keeps real time at 4x whether anyone plays or not; the spine is rescaled to real time and repeats daily, and the
    routines ride it. Runs once: a second call renews the settings and the routines and leaves the spine where the
    first put it."""
    root = s.summary()["root"]
    s.world.set_meta({"claim_lapse": HOSTED["claim_lapse"], "run_when_occupied": False, "idle_after": HOSTED["idle_after"],
                      "public_timers": HOSTED["public_timers"]})
    s.world.set_pace(HOSTED["pace"])
    s.clock(run=True, rate=HOSTED["rate"], turn=0)
    # the landing page (worlds/glass-reach/site when deployed) reads the feeds; the board is the owner's to keep true
    s.world.set_meta({"public_feed": True, "seat_sides": ["hold", "keth", "guild", "dreyer", "any"]})
    if "public_board" not in s.world.meta():
        s.world.set_meta({"public_board": [
            {"label": "The wall", "text": "Eight men. It wants twenty.", "have": 8, "want": 20},
            {"label": "The cistern", "text": "Cracked and dry. The Hold drinks what is carried in."},
            {"label": "The water", "text": "Carried up by the Keth at dusk, while the terms hold.", "wet": True}]})
    if s.world.meta().get("hosted"):
        keep_routines(s, root)
        return
    spine = {kind for kind, _, _ in HOSTED["spine"]}
    for t in s.timers():
        if t["kind"] in spine:
            s.unschedule(t["id"])
    for kind, at, every in HOSTED["spine"]:
        s.schedule(at, kind, entity=root, every=every)
    s.world.set_meta({"hosted": True})
    keep_routines(s, root)

