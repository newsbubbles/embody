"""The Glass Reach: a desert fief with table-top rules, ten places, seven NPCs and Ruhl's nine, two seats to play.

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

Split like the ferry: scripts/ (this world's go, creep, ward_toggle, ossa_on, reach_story and reach_routines; take, drop, give, talk,
read and person_on come from packs/village, the rules from packs/d20), define(s), populate(s), upgrade(s).
"""

from packs.d20.pack import install_rules, keep_behaviors

WORLD = {
    "id": "glass-reach",
    "name": "The Glass Reach",
    "seed": 23,
    "description": "A desert fief, a cracked cistern, a people with the water, a blade left behind. Rules on the table.",
    "requires": ["d20", "village"],
}

# ---- what there is ---------------------------------------------------------------------

POLICY = {
    "fixed": [
        "the rules: d20 + stat + skill against a difficulty, opposed attacks, a ward stops fast blows and the slow blade passes it, "
        "water runs out, the Thresher comes to rhythm on deep sand, the ring holds during a duel; the engine rolls, the narrator tells",
        "the seven NPCs, Ruhl's nine men, the ten places and the four sides",
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
    "passes it; the ring in the yard holds by old law). The engine rolls; you decide; your agent tells it.")

TEMPLATES = {
    "carrier": {"type": "person", "place": "The Carriers' Landing", "doc": "a Guild carrier off the last convoy, at the Landing",
                "state": {"faction": "the Carriers", "body": 3, "wits": 3, "will": 2, "skills": {"parley": 1, "survival": 1, "lore": 1}},
                "brief": "You came in with the water convoy and stayed when it left. The Guild carries for whoever holds the gate; "
                         "Ossa keeps the tally. Water is a skin for a shard. Whatever else you are here for is yours to decide."},
    "guard": {"type": "person", "place": "The Gate Yard", "doc": "one of Ruhl's nine, in the Gate Yard",
              "state": {"faction": "House Varrick", "body": 3, "wits": 2, "will": 3, "skills": {"blade": 2, "resolve": 1}, "vigor": 6, "max_vigor": 6},
              "brief": "You hold a blade for House Varrick under Captain Ruhl: nine men for a wall that wants twenty, a new reeve, "
                       "a week of water, and a clerk who watches the drill like a man counting."},
    "keth": {"type": "person", "place": "Red Ridge", "doc": "a Keth of Taan's camp, on Red Ridge",
             "state": {"faction": "the Keth", "body": 3, "wits": 3, "will": 2, "skills": {"stealth": 2, "survival": 2, "blade": 1}},
             "brief": "You are Keth. The Deepwell is yours and the Low Well is a grave. You walk the Flats with the broken step and "
                      "the Thresher does not hear you. The Hold has a new reeve; Taan wants to know careful or afraid."},
    "dreyer": {"type": "person", "place": "The Salt Road", "doc": "a House Dreyer agent come up the Salt Road under another name",
               "state": {"faction": "House Dreyer", "secret": ["dialog", "gives", "gave", "faction", "brief", "word_left"],
                         "body": 3, "wits": 3, "will": 3, "skills": {"blade": 1, "stealth": 2, "parley": 2}},
               "brief": "You are Dreyer's, under another name. The house lost the writ, the Hold and the water and means to have "
                        "them back: the Keth kept thirsty, the reeve kept weak, the Flats empty for the taking. Dram Hollis is in the "
                        "Hold on the same business; he does not know you are coming."},
}

STORY_KINDS = ["arrived", "checked", "talked", "agreed", "dram_moves", "downed", "killed", "yielded",
               "heat", "dusk", "night", "dawn", "cistern_cracks"]

# the spine at 4x real time, in world seconds: a day is 86400 (six real hours); every=86400 repeats daily
HOSTED = {"rate": 4, "claim_lapse": 3600,
          # a seat that has not acted or spoken for an hour of the world (a quarter hour real) is idle: its body drinks
          "idle_after": 3600,
          # what everyone in the Reach knows is coming: timers() tells a player or a mind the next of each
          "public_timers": ["heat", "dusk", "night", "dawn"],
          # a body's water in the hosted day: one point every 2.4 world hours (36 real minutes of play at 4x), a look for
          # water every ten world minutes; a point of vigor mended every six world hours (a wound closes in a day or
          # two, a body a wound put down gets up in half a day); the turn-based story keeps the pack's beats
          "pace": {"thirst": 8640, "quench": 600, "mend": 21600},
          "spine": [("heat", 21600, 86400), ("dram_moves", 28800, None), ("dusk", 43200, 86400),
                    ("night", 54000, 86400), ("cistern_cracks", 64800, None), ("dawn", 86400, 86400)],
          # the routines ride the spine: (routine, the spine event it starts with)
          "routines": [("keth_run", "dusk"), ("crawler", "dawn")]}

ROUTINE_KINDS = ["keth_run", "crawler"]

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


def upgrade(s):
    """Bring a world built from an older version of this file up to this one. Checks before every write."""
    names = {e["name"]: e["id"] for e in s.find(limit=500)}
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
    for e in s.find(type="person", limit=500):
        sec = list(s.world.get(e["id"])["state"].get("secret") or [])  # inspect hides the secret list itself
        if "word_left" not in sec:
            s.patch(e["id"], {"secret": sec + ["word_left"]})
    root = s.summary()["root"]
    install_rules(s, root)
    s.set_rule(root, "reach_story", kinds=STORY_KINDS)
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
    {"a": "The Glass Flats", "b": "The Low Well", "route": [[2800, 1000], [3600, 100], [3950, -250, -6]]},
    {"a": "Red Ridge", "b": "The Low Well", "route": [[4050, 100, 0], [3950, -250, -6]]},
]


def lay_out(s):
    """Lay the Reach out in the world's one frame. Each piece is written once: an entity that has a layout of its own,
    a path that has a route and a root that has a frame are the owner's now, edited live, and a reboot leaves them as
    they are. Only what exists is placed. Returns the layout op's warnings."""
    w = s.world
    root = s.summary()["root"]
    ids = {e["name"]: e["id"] for e in s.find(limit=500)}
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


def keep_canon(s):
    """The Low Well (a place off the Flats and the ridge, with its dry poisoned well-head and the four Keth cairns), the
    bows on the Hold's wall, and Ruhl's nine. Each is made once: the well and the bows by name, the nine by a mark on
    the story, so a guard who dies is not raised again on a reboot. The nine are posted in the Hold, where a body with
    water at hand does not thirst; they drink when the Hold runs dry, like everyone under its roof."""
    names = {e["name"]: e["id"] for e in s.find(limit=500)}
    story = s.find(type="story", limit=1)[0]["id"]
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
    rack = names.get("Rack of practice blades")
    if rack and s.world.get(rack)["state"].get("holds") is None:
        s.patch(rack, RACK)
    if st.get("garrison"):
        return
    hold, ruhl = st["hold"], st["ruhl"]
    bodies = s.find(type="person", limit=500) + s.find(type="fighter", limit=500)
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
    names = {e["name"]: e["id"] for e in s.find(limit=500)}
    story = s.find(type="story", limit=1)[0]["id"]
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

