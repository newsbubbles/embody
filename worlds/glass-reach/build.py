"""The Glass Reach: a desert fief with table-top rules, nine places, seven NPCs, two seats to play.

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
every day, Dram two real hours after the first guest sits down, the cistern at four and a half. The clock runs
while a guest is in the world and waits when none is, so the spine starts with the first player, not the deploy.

Split like the ferry: scripts/ (this world's go, creep, ward_toggle, ossa_on and reach_story; take, drop, give, talk,
read and person_on come from packs/village, the rules from packs/d20), define(s), populate(s), upgrade(s).
"""

from packs.d20.pack import install_rules

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
HOSTED = {"rate": 4, "claim_lapse": 900,
          # a body's water in the hosted day: one point every 2.4 world hours (36 real minutes of play at 4x), a look for
          # water every ten world minutes; the turn-based story keeps the pack's 60 s
          "pace": {"thirst": 8640, "quench": 600},
          "spine": [("heat", 21600, 86400), ("dram_moves", 28800, None), ("dusk", 43200, 86400),
                    ("night", 54000, 86400), ("cistern_cracks", 64800, None), ("dawn", 86400, 86400)]}

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
    s.set_rule(root, "reach_story", kinds=STORY_KINDS)
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


def host(s):
    """The Reach as a hosted place (`embody load glass-reach --hosted`). Seats lapse after fifteen quiet minutes; the clock
    runs at 4x while a guest is in the world and waits when none is; the spine is rescaled to real time and repeats
    daily. Runs once: a second call renews the settings and leaves the timers where the first put them."""
    root = s.summary()["root"]
    s.world.set_meta({"claim_lapse": HOSTED["claim_lapse"], "run_when_occupied": True})
    s.world.set_pace(HOSTED["pace"])
    s.clock(run=False, rate=HOSTED["rate"], turn=0)
    if s.world.meta().get("hosted"):
        return
    spine = {kind for kind, _, _ in HOSTED["spine"]}
    for t in s.timers():
        if t["kind"] in spine:
            s.unschedule(t["id"])
    for kind, at, every in HOSTED["spine"]:
        s.schedule(at, kind, entity=root, every=every)
    s.world.set_meta({"hosted": True})

