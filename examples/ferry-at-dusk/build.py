"""The Ferry at Dusk: five places, four NPCs, one storyline that watches facts.

    uv run embody --as gm --author load ferry-at-dusk
    uv run embody --as you join ferry-at-dusk Traveler
    uv run embody --as you perceive

The ferryman is missing and the river must be crossed before the fog. Everything that
moves the story is deterministic code in this folder: the storyline waits for events, the
innkeeper answers to topics, the miller wanders, the dog follows whoever feeds it, the fog
rolls in on a timer, night falls and dawn comes. Whoever embodies the Traveler (a person,
or Claude) does the playing; whoever runs the GM session narrates and can nudge any NPC
with act_as and say_as, or hand an NPC to a mind.

The story checks facts, not a stage: ring the bell and Tam comes, however you got there;
find him asleep in the Reeds and wake him and he walks down to the raft by himself.
  arrive at the Landing  ->  learn from Mara (or Hob) where Tam is and how to call him
  ->  tie the rope, ring the bell  |  or walk to the Reeds and wake him
  ->  Old Tam steps onto the raft  ->  cross (12 s, needs a lit lantern once the fog is in)

Ambient facts live on the root (`ambient`: time_of_day, weather, light) and on the Landing
(`ambient.weather` once the fog is in). Every perceive shows them merged.

The folder is split so a running world can take new code without losing its state:
  scripts/     one file per script: verbs, listeners, behaviors, the storyline (go, take, drop, give, talk, read and
               person_on come from packs/village, the rest is this world's)
  define(s)    schemas (what things can do)
  populate(s)  places, people, things, rules, the clock (what there is)
  upgrade(s)   idempotent additions for a world built from an older build (the Reeds, the tinderbox, ambient, timers)
`uv run embody load ferry-at-dusk --upgrade` runs the pack, the scripts, define() and upgrade() against the current world.

Play is turn-based: the clock is paused and every act of an embodied player moves the world
three seconds (longer for a slow verb). Fog at t=90, night at t=150, dawn at t=400.
"""

WORLD = {
    "id": "ferry-at-dusk",
    "name": "The Ferry at Dusk",
    "seed": 11,
    "description": "A river village at dusk. The ferryman is missing. Cross before the fog closes in.",
    "requires": ["village"],
}

# ---- what things can do ----------------------------------------------------------------

def define(s):
    """Schemas. The scripts are the files in scripts/ and packs/village/scripts. Safe to run again on a live world:
    entities keep their state and pick up the new code."""
    # scope keeps impossible pairs out of a player's affordances: go only to exits, drop only what you hold.
    # The dialog table is secret: a player hears a line when they ask, not the whole table in perceive.
    # person_on is skipped while an agent embodies the person: the table is the floor, a mind sits on top.
    s.define_schema("person", extends="creature", doc="Someone who can walk, carry, talk, sleep and fight.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": {}, "asleep": False,
                           "secret": ["dialog", "gives", "gave"]},
                    actions={
                        "go": {"script": "go", "doc": "Walk to a connected place", "targets": "place",
                               "scope": "exits", "duration": 5},
                        "take": {"script": "take", "doc": "Pick something up", "targets": "thing", "scope": "here"},
                        "drop": {"script": "drop", "doc": "Put down something you hold", "targets": "thing", "scope": "held"},
                        "give": {"script": "give", "doc": "Hand something you hold to someone here",
                                 "targets": "creature", "scope": "here", "params": {"item": "id or name of a thing you hold"}},
                        "talk": {"script": "talk", "doc": "Talk to someone about something",
                                 "targets": "creature", "scope": "here", "duration": 2,
                                 "params": {"about": "the topic, in your words"}},
                        "touch": {"script": "touch", "doc": "Touch, pet or pat something or someone here",
                                  "targets": "entity", "scope": "here"},
                        "check": {"script": "check", "doc": "Try your luck or skill at something: a d20 everyone sees",
                                  "targets": "entity", "reach": "self", "params": {"skill": "what you are trying"}},
                        "sleep": {"script": "sleep", "doc": "Sleep where you are until dawn or until woken", "duration": 10},
                        "wake": {"script": "wake", "doc": "Wake a sleeper here (or yourself)", "targets": "creature",
                                 "scope": "here", "self": True},
                        "attack": {"script": "attack", "doc": "Strike someone", "targets": "creature", "scope": "here"},
                        "work": {"script": "work", "doc": "Do a chore here: grease the wheel, stack the sacks",
                                 "targets": "thing", "scope": "here", "duration": 20},
                    },
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])
    s.define_schema("dog", extends="creature", doc="Follows whoever feeds it.", state={"hp": 6, "max_hp": 6, "friend": None},
                    behaviors=[{"script": "dog_follow", "every": 6}],
                    listeners=[{"script": "dog_on", "kinds": ["given", "touched"]}])
    s.define_schema("miller", extends="person", doc="Walks between the mill and the square.",
                    behaviors=[{"script": "hob_walk", "every": 45}],
                    listeners=[{"script": "hob_on", "kinds": ["noticed"]}])
    s.define_schema("sign", extends="thing", doc="Something with writing on it.", state={"text": "", "portable": False},
                    actions={"read": {"script": "read", "doc": "Read what is written"}})
    s.define_schema("drinkable", extends="thing", doc="A drink. Two pulls to a mug.", state={"left": 2, "portable": True},
                    actions={"drink": {"script": "drink", "doc": "Drink from it (you must hold it)", "duration": 3}})
    s.define_schema("bell", extends="thing", doc="A landing bell. Needs its rope.", state={"rope": False, "portable": False},
                    actions={"tie": {"script": "tie", "doc": "Tie a rope you hold onto it"},
                             "ring": {"script": "ring", "doc": "Pull the rope"}})
    s.define_schema("lantern", extends="thing", state={"lit": False, "portable": True},
                    actions={"light": {"script": "light", "doc": "Light it (you need fire)"}})
    s.define_schema("raft", extends="thing", doc="The ferry. Crossing takes a while; it goes both ways.",
                    state={"portable": False, "banks": [], "far_bank": None},
                    actions={"cross": {"script": "cross", "doc": "Cross the river on it", "duration": 12}})
    s.define_schema("landing", extends="place", listeners=[{"script": "landing_on", "kinds": ["fog", "dawn"]}])
    s.define_schema("story", extends="entity", doc="The rails. Hidden; holds the facts the story has seen.",
                    state={"hidden": True, "stage": "start", "seen_landing": False, "mara_told": False, "crossed": False})

# ---- what there is ---------------------------------------------------------------------

# What a narrator may and may not change while running this world. Read by agents, not by the engine.
POLICY = {
    "fixed": [
        "the rails: Mara and Hob know where Tam is, the bell calls Tam, waking him in the Reeds works too, Tam rows, "
        "fog comes with the dark and blinds the crossing without a lit lantern; timers() says when",
        "there is no money in Ashford; favors and debts instead",
        "nobody raises a hand in the square",
        "the four NPCs and the five places",
    ],
    "fill": True,    # small things a village would have (a bench, a second mug, a stray cat) may be spawned with state {"improvised": true}
    "voice": True,   # NPCs may say free lines through say_as when their table has no answer, in their own voice
}

AMBIENT = {"time_of_day": "dusk", "weather": "still, clear, cold coming on", "light": "failing; the inn lamps are lit"}

MARA = {
    "description": "The innkeeper. Knows everyone's business and most of their debts.",
    "brief": "You are Mara, innkeeper of Ashford. Dry, quick, kind underneath and not about to show it. You know "
             "Tam went up to the mill at noon to drink with Hob and is sleeping it off in the reeds behind the mill; "
             "the bell at the landing would wake him, but the Pell boys cut its rope and Hob keeps rope. You keep a "
             "spare tinderbox in your apron and will give it to anyone crossing in fog. One ale per traveler who has "
             "a river to cross. Nobody pays coin in Ashford; you take stories. You judge people by whether they "
             "listen. Speak in short lines. Answer what you are asked and no more; let them ask again.",
    "dialog": {
        "ferry|across|crossing": "Tam's not been back since noon. Went up to the mill to drink with Hob and that was that. If you need across you need him, and the bell is the way to call him.",
        "tam|ferryman": "Old Tam rows the ferry. Drinks at the mill. Sleeps where he falls, the reeds behind the mill as often as not.",
        "hob|mill|miller": "Hob Pell runs the mill. Decent man, terrible sons.",
        "reeds": "Behind the mill, down the bank. Tam sleeps there when the jugs get the better of him.",
        "fog|weather|dark|night": "River fog comes in with the dark. Nobody crosses blind. Take a light.",
        "lantern|lamp": "There's a lantern on the post at the landing. You'll want something to light it with.",
        "light|fire|tinderbox": {"line": "You'll want a tinderbox for that. Here, I keep a spare.",
                                 "after_gift": "You've my spare already. Don't drop it in the river."},
        "dog|biscuit": "That's Biscuit. He'll follow anyone with a bone.",
        "bone|food": "Something for the dog? Look under the bench by the well.",
        "ale|drink|beer|pint": {"line": "One, mind. You've a river to cross.",
                                "after_gift": "One was the deal. The river's waiting on you, not the other way round."},
        "pay|coin|money": "Put it away. Nobody pays coin in Ashford; you'll owe me a story when you're back this way.",
        "story|tale|owed|promised": {"line": "Go on then. I'm listening.",
                                    "after_gift": "You've told me yours. It was a fair one; the mugs said so."},
        "work|chore|help|hands": "Hob's wheel wants greasing and his sacks want stacking. Ask him. Work is coin here.",
        "sleep|bed|room": "There's a bench by the fire if you must. But the river won't wait for morning, and the fog won't either.",
    },
    "default_line": "Mara wipes a mug. 'Ask me something I know about: the ferry, Tam, Hob, the fog, the light. Or have a drink.'",
    "gives": {
        # the tinderbox is a real thing in her apron, handed over; a mind embodying her gives it with the give verb
        "light|fire|tinderbox": {"item": "Tinderbox", "line": "She digs the tinderbox out of her apron and puts it in your hand.",
                                 "gone_line": "Gave my spare away already. Try the mill; Hob keeps a fire going."},
        "ale|drink|beer|pint": {"type": "drinkable", "name": "Dark ale", "line": "She sets a dark ale in front of you.",
                                "state": {"description": "A mug of dark ale, head still settling."}},
        "story|tale|owed|promised": {"type": "drinkable", "name": "Three mugs of dark ale",
                                    "line": "She listens to the end, then lines up three mugs without a word about the deal.",
                                    "state": {"left": 6, "description": "Three mugs of dark ale, lined up. A story's worth."}},
    },
}

HOB = {
    "description": "The miller. Big, floury, tired.",
    "brief": "You are Hob Pell, the miller. Slow to speak, honest, ashamed of your sons who cut the bell rope for a "
             "lark. Tam drank two jugs with you at noon and went to sleep it off in the reeds behind the mill. You "
             "give rope freely to anyone who asks because the village should not think ill of the mill. You walk "
             "between the mill and the square. You like the dog but will not feed him; he is nobody's till somebody does.",
    "lines": ["'Wheel wants greasing.'", "'If you see my boys, send them home.'", "'Tam owes me for three jugs.'"],
    "dialog": {
        "rope|cord|line": "Rope? Take a coil, there's plenty. It's my boys cut the bell rope and I'll not have the village think ill of the mill.",
        "tam|ferryman": "Tam was here till the second jug. Went off to sleep it off in the reeds behind the mill. Path's round the back.",
        "reeds": "Round the back of the mill, down the bank. Mind the mud.",
        "boys|sons|bell": "My boys cut the bell rope for a lark. They'll hear about it.",
        "dog|biscuit": "That's Biscuit. Not mine. Nobody's, till somebody feeds him.",
        "work|chore|help|hands|wheel|grease|sacks": "Wheel wants greasing; the pot's by the door. Sacks want stacking. Do either and we'll call Tam's jugs square.",
    },
    "default_line": "Hob shrugs flour off his shoulders. 'Rope, Tam, my boys. That's all I've got for you.'",
}

TAM = {
    "description": "The ferryman. Hoarse, damp, cheerful enough, and at the moment flat out among the reeds.",
    "role": "ferryman", "asleep": True,
    "brief": "You are Old Tam, the ferryman. Drunk at noon, asleep in the reeds since, cheerful when woken and not "
             "a bit sorry. You know the current and will not cross in fog without a lit lantern. You owe Hob for "
             "three jugs and know it. You call everyone 'friend'.",
    "dialog": {"ferry|across|river": "Aye, aye. On the raft with you. I'll take you over.",
               "cross|crossing": "Say 'cross' on the raft and hold on.",
               "hob|jugs|owe": "Three jugs. I know. He'll have them when the barley's in.",
               "raft|row|current|pole": "Feet apart, hold the rope, and let the current do the arguing.",
               "story|tale": "A story? Ask Mara, friend. She collects them. I just row."},
    "default_line": "Tam scratches his beard. 'The river, the raft, Hob's jugs. That's what I know, friend.'",
}

WHEEL = {"portable": False, "description": "The great wheel, turning slow and squealing at every quarter turn.",
         "chore": {"name": "grease the wheel", "needs": "Pot of grease",
                   "start": "You climb down beside the axle with the pot. It is filthy work.",
                   "after": "The great wheel, turning smooth and quiet. Fresh grease shines on the axle."}}
GREASE = {"portable": True, "description": "A clay pot of wheel grease, a rag over it."}
SACKS = {"portable": False, "description": "Empty flour sacks in a heap by the door.",
         "chore": {"name": "stack the sacks", "start": "You start shaking them out and folding.",
                   "after": "Empty flour sacks folded and stacked against the wall."}}

GOALS = {
    "Mara": [("Hear the Traveler's story", "A story is the fare in Ashford, and I am owed one"),
             ("Keep the square peaceful", "Trouble in the square is trouble at my door")],
    "Hob": [("Get Tam's three jugs squared", "A debt left to sit sours a village"),
            ("Keep the wheel greased and the mill turning", "The mill is the Pells' name, and the boys have spent enough of it")],
    "Old Tam": [("Row whoever needs across before the fog", "That is the job, and the job is all I have"),
                ("Settle with Hob when the barley is in", "Three jugs. I know.")],
}

def seed_village(s, mara, hob, tam):
    """What the villagers want and what they think of each other, so an NPC seat starts with a life, not a blank
    card. Checked step by step: safe to run on a world that has some of it."""
    by_id = {mara: "Mara", hob: "Hob", tam: "Old Tam"}
    for eid, name in by_id.items():
        have = {g["text"] for g in (s.inspect(eid)["state"].get("goals") or [])}
        for text, why in GOALS[name]:
            if text not in have:
                s.intend(text, why=why, entity=eid)
    views = {
        (mara, hob): {"standing": 1, "note": "decent man, terrible sons"},
        (mara, tam): {"standing": 0, "note": "drinks his fare before he earns it"},
        (hob, mara): {"standing": 1, "note": "keeps the square honest"},
        (hob, tam): {"standing": -1, "note": "three jugs"},
        (tam, mara): {"standing": 1, "note": "pours fair"},
        (tam, hob): {"standing": 1, "note": "good company, bad creditor"},
    }
    for (a, b), data in views.items():
        edges = s.recall(about=b, entity=a)["edges"]
        if not any(e["relation"] == "knows" and e["direction"] == "out" for e in edges):
            s.link(a, b, "knows", {**data, "met_t": 0, "count": 0})
    debts = [r for r in s.inspect(hob).get("relations", []) if r["relation"] == "debt"]
    settled = any(e["kind"] == "debt_settled" for e in s.history(kinds=["debt_settled"], limit=10))
    if not debts and not settled:
        s.relate("debt", [tam, hob], {"what": "three jugs of ale", "owed_by": tam, "owed_to": hob})

def populate(s):
    """Places, people, things, rules and the clock, into the world the session points at."""
    root = s.summary()["root"]
    s.patch(root, {"policy": POLICY, "ambient": AMBIENT})

    square = s.spawn("place", root, "Ashford Square", state={
        "description": "A packed-earth square between the inn, the well and the road down to the river. "
                       "Dusk is coming on; someone has lit the inn lamps."})["id"]
    mill = s.spawn("place", root, "Pell's Mill", state={
        "description": "The wheel turns slow in the mill race. Flour dust on everything. Rope, sacks and a sleeping dog. "
                       "A muddy path goes round the back, down to the reeds."})["id"]
    reeds = s.spawn("place", root, "The Reeds", state={
        "description": "A bank of reeds behind the mill where the race runs back into the river. Soft ground, "
                       "flattened in one place where someone has been lying."})["id"]
    landing = s.spawn("landing", root, "The Landing", state={
        "description": "A shingle bank where the road ends at the water. A post with a bell, a moored raft, reeds either side.",
        "fog": False})["id"]
    far = s.spawn("place", root, "The Far Bank", state={
        "description": "Shingle and a path going up into the dark. The village is behind you now.",
        "hidden": True})["id"]
    s.connect(square, mill)
    s.connect(square, landing)
    s.connect(mill, reeds)

    # the square
    mara = s.spawn("person", square, "Mara", state=MARA)["id"]
    s.spawn("thing", mara, "Tinderbox", state={"kind": "fire", "portable": True, "description": "Flint, steel and char cloth in a tin."})
    s.spawn("sign", square, "Notice board", state={
        "text": "FERRY: dawn to dusk, ring for Tam. NO CROSSINGS IN FOG. Pell's Mill buying barley. Lost: one grey dog, answers to Biscuit, does not come when called."})
    s.spawn("thing", square, "Well", state={"portable": False, "description": "Stone well with a wooden lid and a bench beside it, worn pale where people sit."})
    s.spawn("thing", square, "Bench", state={"portable": False, "description": "A plank bench by the well. Something under it.",
                                             "hides": "Bone", "description_after": "A plank bench by the well, worn pale."})
    s.spawn("thing", square, "Bone", state={"kind": "food", "portable": True, "description": "A soup bone, mostly gnawed. Under the bench."})
    s.set_rule(square, "peace")

    # the mill
    hob = s.spawn("miller", mill, "Hob", state={**HOB, "home": mill, "haunt": square})["id"]
    s.spawn("thing", mill, "Coil of rope", state={"kind": "rope", "portable": True})
    s.spawn("thing", mill, "Sack of flour", state={"portable": True, "description": "Heavy. Why would you."})
    s.spawn("dog", mill, "Biscuit", state={"description": "A grey dog with flour in his coat."})
    s.spawn("thing", mill, "Mill wheel", state=WHEEL)
    s.spawn("thing", mill, "Pot of grease", state=GREASE)
    s.spawn("thing", mill, "Heap of empty sacks", state=SACKS)

    # the reeds
    tam = s.spawn("person", reeds, "Old Tam", state=TAM)["id"]

    # the landing
    s.spawn("bell", landing, "Landing bell", state={"description": "Iron bell on a post. The rope ends in a clean cut a foot below the clapper."})
    s.spawn("lantern", landing, "Post lantern", state={"description": "A storm lantern hung from the bell post. Unlit."})
    s.spawn("raft", landing, "Ferry raft", state={"banks": [landing, far], "far_bank": far,
                                                  "description": "Pole-and-rope raft, moored to the post."})

    # the player's seat
    s.spawn("person", square, "Traveler", state={"role": "traveler", "description": "You. Needing to be across the river tonight."})

    # the rails and the weather
    s.spawn("story", root, "Story", state={"square": square, "mill": mill, "reeds": reeds, "landing": landing, "far_bank": far,
                                           "mara": mara, "hob": hob, "tam": tam})
    s.set_rule(root, "story", kinds=["arrived", "talked", "rang", "woken", "crossed"])
    s.set_rule(root, "weather", kinds=["fog", "nightfall", "dawn"])
    s.set_rule(root, "asleep_guard", kinds=["before_act"])
    seed_village(s, mara, hob, tam)
    s.schedule(90, "fog", entity=landing, payload={"text": "Fog comes up off the water and swallows the far bank."})
    s.schedule(150, "nightfall", entity=root)
    s.schedule(400, "dawn", entity=landing)
    # turn-based: paused, three world seconds per embodied act. clock(run=True) makes it realtime instead.
    s.clock(run=False, turn=3)
    return s.summary()

def upgrade(s):
    """Bring a world built from an older version of this file up to this one. Every step checks first, so it is
    safe to run twice. Entities keep their state; only what is missing is added."""
    def want(eid, changes):
        # patch only what differs, so a world already at this version keeps its state hash
        have = s.inspect(eid)["state"]
        diff = {}
        for k, v in changes.items():
            cur = have.get(k)
            if isinstance(v, dict) and isinstance(cur, dict):
                v = {kk: vv for kk, vv in v.items() if cur.get(kk) != vv}
                if not v:
                    continue
            elif cur == v:
                continue
            diff[k] = v
        if diff:
            s.patch(eid, diff)

    root = s.summary()["root"]
    rs = s.inspect(root)["state"]
    want(root, {"policy": POLICY})
    if not rs.get("ambient"):
        s.patch(root, {"ambient": AMBIENT})
    by_name = {e["name"]: e for e in s.find(limit=100)}
    mill, square, landing = by_name["Pell's Mill"]["id"], by_name["Ashford Square"]["id"], by_name["The Landing"]["id"]
    reedy = [e for e in s.find(type="place", limit=100) if "reeds" in e["name"].lower()]
    if reedy:
        reeds = reedy[0]["id"]  # round two improvised "The Reeds behind the Mill"; it is the Reeds
    elif "The Reeds" not in by_name:
        reeds = s.spawn("place", root, "The Reeds", state={
            "description": "A bank of reeds behind the mill where the race runs back into the river. Soft ground, "
                           "flattened in one place where someone has been lying."})["id"]
        s.connect(mill, reeds)
    else:
        reeds = by_name["The Reeds"]["id"]
    raft = by_name["Ferry raft"]["id"]
    rst = s.inspect(raft)["state"]
    if not rst.get("banks"):
        s.patch(raft, {"banks": [landing, rst.get("far_bank") or by_name["The Far Bank"]["id"]]})
    mara, hob = by_name["Mara"]["id"], by_name["Hob"]["id"]
    story = by_name["Story"]["id"]
    st = s.inspect(story)["state"]
    if "Old Tam" not in by_name:
        tam = s.spawn("person", reeds, "Old Tam", state=TAM)["id"]
    else:
        tam = by_name["Old Tam"]["id"]
        trow = s.inspect(tam)
        if trow["state"].get("hidden") and st.get("stage") in ("start", "ask", "bell"):
            # round two kept him hidden in the mill; now he sleeps in the open, in the Reeds
            s.move(tam, reeds)
            s.patch(tam, {"hidden": False, "asleep": True})
    # briefs and the new topics; a merge, so lines improvised in play stay
    want(mara, {"brief": MARA["brief"], "dialog": MARA["dialog"], "gives": MARA["gives"]})
    want(hob, {"brief": HOB["brief"], "dialog": HOB["dialog"]})
    want(tam, {"brief": TAM["brief"], "dialog": TAM["dialog"], "role": "ferryman"})
    if not any(c["name"] == "Tinderbox" for c in s.inspect(mara)["contents"]) and \
            "light|fire|tinderbox" not in (s.inspect(mara)["state"].get("gave") or []):
        s.spawn("thing", mara, "Tinderbox", state={"kind": "fire", "portable": True, "description": "Flint, steel and char cloth in a tin."})
    # gifts are per asker now: whatever an older table gave, it gave to the Traveler
    trav = by_name.get("Traveler", {}).get("id")
    for who in (mara, hob, tam):
        gave = s.inspect(who)["state"].get("gave")
        if isinstance(gave, list):
            s.patch(who, {"gave": {k: [trav] for k in gave} if trav else {}}, replace=False)
            if not gave:
                s.patch(who, {"gave": {}})
    # Tam's improvised key from round three caught "mill"; the table has his real lines now
    tdialog = s.inspect(tam)["state"].get("dialog") or {}
    for key in list(tdialog):
        if key.startswith("wake|up|inside"):
            s.patch(tam, {"dialog": {key: None}})
    # the chores: the pot and the sacks were improvised in round three, the wheel is new
    mill_things = {e["name"]: e for e in s.world.find(limit=None) if e["name"] in ("Mill wheel", "Pot of grease", "Heap of empty sacks")}
    if "Mill wheel" not in mill_things:
        s.spawn("thing", mill, "Mill wheel", state=WHEEL)
    if "Pot of grease" not in mill_things:
        s.spawn("thing", mill, "Pot of grease", state=GREASE)
    elif mill_things["Pot of grease"]["state"].get("improvised"):
        s.patch(mill_things["Pot of grease"]["id"], {"improvised": None, "portable": True})
    if "Heap of empty sacks" not in mill_things:
        s.spawn("thing", mill, "Heap of empty sacks", state=SACKS)
    elif not mill_things["Heap of empty sacks"]["state"].get("chore"):
        s.patch(mill_things["Heap of empty sacks"]["id"], {**SACKS, "improvised": None})
    # words that went stale when the world changed under them
    bell = by_name.get("Landing bell")
    if bell and bell["state"].get("rope") and "clean cut" in bell["state"].get("description", ""):
        s.patch(bell["id"], {"description": "Iron bell on a post. A new rope hangs from the clapper, the knot still stiff."})
    bench = by_name.get("Bench")
    if bench and "Bone" not in by_name and "Something under it" in bench["state"].get("description", ""):
        s.patch(bench["id"], {"hides": None, "description": "A plank bench by the well, worn pale."})
    elif bench and "Something under it" in bench["state"].get("description", "") and not bench["state"].get("hides"):
        s.patch(bench["id"], {"hides": "Bone", "description_after": "A plank bench by the well, worn pale."})
    dog, board = by_name.get("Biscuit"), by_name.get("Notice board")
    if dog and board and dog["state"].get("friend") and "Lost: one grey dog" in board["state"].get("text", ""):
        s.patch(board["id"], {"text": board["state"]["text"].split(" Lost: one grey dog")[0] + " FOUND: the grey dog. He picked someone."})
    want(root, {"policy": POLICY})
    want(tam, {"default_line": TAM["default_line"]})
    seed_village(s, mara, hob, tam)
    told = "bell" in (s.inspect(mara)["state"].get("dialog") or {}) or st.get("stage") == "bell"
    want(story, {"reeds": reeds, "tam": tam, "seen_landing": st.get("stage") != "start", "mara_told": told,
                 "crossed": st.get("stage") == "done"})
    s.set_rule(root, "story", kinds=["arrived", "talked", "rang", "woken", "crossed"])  # set_rule is a no-op when already there
    s.set_rule(root, "weather", kinds=["fog", "nightfall", "dawn"])
    s.set_rule(root, "asleep_guard", kinds=["before_act"])
    kinds = {t["kind"] for t in s.timers()}
    t = s.summary()["t"]
    if "nightfall" not in kinds and t < 150:
        s.schedule(150 - t, "nightfall", entity=root)
    if "dawn" not in kinds:
        s.schedule(max(30.0, 400 - t), "dawn", entity=landing)
    return s.summary()

