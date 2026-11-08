"""The Ferry at Dusk: three places, four NPCs, one storyline on rails.

    uv run embody --as gm --author load worlds/ferry_at_dusk.py
    uv run embody --as you join ferry-at-dusk Traveler
    uv run embody --as you perceive

The ferryman is missing and the river must be crossed before the fog. Everything that
moves the story is deterministic code in this file: the storyline waits for events, the
innkeeper answers to topics, the miller wanders, the dog follows whoever feeds it, the fog
rolls in on a timer. Whoever embodies the Traveler (a person, or Claude) does the playing;
whoever runs the GM session narrates and can nudge any NPC with act_as and say_as.

Rails (a rule on the root watches for these, the hidden Story entity keeps the stage):
  arrive at the Landing  ->  ask Mara about the ferry  ->  tie the rope, ring the bell
  ->  Old Tam comes down to the Landing  ->  cross (12 s, needs the lantern lit once the fog is in)

The file is split in two so a running world can take new code without losing its state:
  define(s)    scripts and schemas (what things can do)
  populate(s)  places, people, things, rules, the clock (what there is)
  build(s)     a new world: create, define, populate
`uv run embody load worlds/ferry_at_dusk.py --upgrade` runs define() against the current world.

Play is turn-based: the clock is paused and every act of an embodied player moves the world
three seconds (longer for a slow verb). The fog comes at t=90 world seconds, about thirty turns in.
"""

# ---- scripts --------------------------------------------------------------------------

GO = '''
def check(ctx):
    here = ctx.actor.parent
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            via = e["data"].get("via")
            if via and not ctx.get(via).state.open:
                return "the way is shut"
            return True
    return "there is no way there from here"

def apply(ctx):
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id)
'''

TAKE = '''
def check(ctx):
    if ctx.target.parent.id == ctx.actor.id:
        return "you already hold it"
    if not ctx.target.state.portable:
        return "it will not budge"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    return True

def apply(ctx):
    ctx.move(ctx.target, ctx.actor)
    ctx.emit("taken", target=ctx.target, reach=1, by=ctx.actor.id)
'''

DROP = '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    return True

def apply(ctx):
    ctx.move(ctx.target, ctx.actor.parent)
    ctx.emit("dropped", target=ctx.target, reach=1, by=ctx.actor.id)
'''

GIVE = '''
def find_item(ctx):
    want = str(ctx.params.get("item", "")).lower()
    for it in ctx.actor.children():
        if it.id == want or (it.name or "").lower() == want:
            return it
    return None

def check(ctx):
    if not ctx.params or "item" not in ctx.params:
        return "say what to give: params {\\"item\\": <id or name of something you hold>}"
    if find_item(ctx) is None:
        return "you hold no such thing"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    it = find_item(ctx)
    ctx.move(it, ctx.target)
    ctx.emit("given", target=ctx.target, reach=1, item=it.id, by=ctx.actor.id)
'''

TALK = '''
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "talking to yourself helps nobody"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    about = ""
    if ctx.params:
        about = str(ctx.params.get("about", ""))
    ctx.emit("talked", target=ctx.target, reach=-1, by=ctx.actor.id, about=about)
'''

PERSON_ON = '''
def words(text):
    # the topic as whole words: "ale" matches "an ale, please" and not "a tale"
    t = str(text).lower()
    for ch in [",", ".", "?", "!", ";", ":", "'", "\\""]:
        t = t.replace(ch, " ")
    return t.split()

def matches(key, topic):
    # a dialog key is one word or several joined with |: "ale|drink|beer"
    for alias in key.split("|"):
        if alias.strip() in topic:
            return True
    return False

def pick(ctx, entry, key, gave):
    # an entry is a line, or a dict: {"line", "after_gift", "if_state": {k: v}, "else"}
    if not isinstance(entry, dict):
        return entry
    me = ctx.self.state
    cond = entry.get("if_state")
    if cond:
        for k in cond:
            if me.get(k) != cond[k]:
                return entry.get("else", entry.get("line"))
    if key in gave and entry.get("after_gift"):
        return entry["after_gift"]
    return entry.get("line")

def on(ctx, event):
    # Someone talked to me. Answer from my dialog table; hand over anything I give for that topic.
    # Skipped while an agent embodies me (unless_embodied on the listener): then the agent answers.
    if event.target != ctx.self.id:
        return
    topic = words(event.payload.get("about", ""))
    asker = event.payload.get("by")
    me = ctx.self.state
    dialog = me.dialog or {}
    gives = me.gives or {}
    gave = me.gave or []
    for key in dialog:
        if not matches(key, topic):
            continue
        line = pick(ctx, dialog[key], key, gave)
        if line:
            ctx.say(line, to=asker)
        if key in gives and key not in gave:
            g = gives[key]
            ctx.spawn(g["type"], asker, name=g["name"], state=g.get("state"))
            ctx.say(g.get("line") or f"Here, take the {g['name'].lower()}.", to=asker)
            ctx.patch(ctx.self, {"gave": gave + [key]})
        return
    ctx.say(me.default_line or "Hm.", to=asker)
'''

READ = '''
def apply(ctx):
    text = ctx.target.state.text or "nothing is written on it"
    ctx.emit("read", target=ctx.target, reach=0, text=text)
    ctx.log(text)
    return text
'''

DRINK = '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    if (ctx.target.state.left or 0) <= 0:
        return "it is empty"
    return True

def apply(ctx):
    left = (ctx.target.state.left or 0) - 1
    ctx.target.state.left = left
    ctx.actor.state.drinks = (ctx.actor.state.drinks or 0) + 1
    ctx.emit("drank", target=ctx.target, reach=1, by=ctx.actor.id, left=left)
    if left <= 0:
        ctx.log("Empty. The mug is just a mug now.")
        ctx.destroy(ctx.target)
    else:
        ctx.log("A long pull. Some left.")
'''

TIE = '''
def check(ctx):
    if ctx.target.state.rope:
        return "the rope is already on it"
    ropes = [k for k in ctx.actor.children() if k.state.kind == "rope"]
    if not ropes:
        return "you need a rope to tie on"
    return True

def apply(ctx):
    rope = [k for k in ctx.actor.children() if k.state.kind == "rope"][0]
    ctx.destroy(rope)
    ctx.target.state.rope = True
    ctx.emit("tied", target=ctx.target, reach=1)
'''

RING = '''
def check(ctx):
    if not ctx.target.state.rope:
        return "the bell rope has been cut; nothing to pull"
    return True

def apply(ctx):
    ctx.emit("rang", target=ctx.target, reach=-1, by=ctx.actor.id)
    ctx.say("The bell rings out over the river.")
'''

LIGHT = '''
def check(ctx):
    if ctx.target.state.lit:
        return "it is already lit"
    fire = [k for k in ctx.actor.children() if k.state.kind == "fire"]
    if not fire:
        return "you have nothing to light it with"
    return True

def apply(ctx):
    ctx.target.state.lit = True
    ctx.emit("lit", target=ctx.target, reach=1)
'''

CROSS = '''
def ferryman_here(ctx):
    for p in ctx.actor.peers():
        if p.state.role == "ferryman":
            return p
    return None

def check(ctx):
    if ctx.actor.parent.id != ctx.target.parent.id:
        return "the raft is not here"
    if ferryman_here(ctx) is None:
        return "nobody here knows the current; the raft stays moored"
    here = ctx.actor.parent
    if here.state.fog:
        lanterns = [l for l in ctx.children(here) if l.state.lit]
        lanterns = lanterns + [l for l in ctx.actor.children() if l.state.lit]
        if not lanterns:
            return "the fog hides the far bank"
    return True

def apply(ctx):
    ctx.emit("casting_off", target=ctx.actor.parent, reach=1, who=ctx.actor.id)
    ctx.log("Tam pushes off. The crossing takes a while.")

def finish(ctx):
    far = ctx.self.state.far_bank
    tam = ferryman_here(ctx)
    ctx.move(ctx.actor, far)
    if tam:
        ctx.move(tam, far)
    ctx.emit("crossed", target=far, reach=-1, who=ctx.actor.id)
'''

PEACE = '''
def on(ctx, event):
    if event.payload["verb"] == "attack":
        ctx.reject("nobody raises a hand in the square; Mara would never forgive it", "talk instead")
'''

ATTACK = '''
def apply(ctx):
    dmg = ctx.rand.roll("1d6")
    ctx.target.state.hp = ctx.target.state.hp - dmg
    ctx.emit("hit", target=ctx.target, reach=1, dmg=dmg)
    return dmg
'''

HOB_WALK = '''
def tick(ctx):
    me = ctx.self
    st = me.state
    dest = st.haunt if me.parent.id == st.home else st.home
    ctx.move(me, dest)
    ctx.emit("arrived", target=dest, reach=-1, who=me.id, place=dest)
    ctx.say(ctx.rand.choice(st.lines))
'''

DOG_FOLLOW = '''
def tick(ctx):
    me = ctx.self
    friend = me.state.friend
    if not friend:
        return
    f = ctx.get(friend)
    if f is None or f.parent is None:
        return
    if f.parent.id != me.parent.id:
        ctx.move(me, f.parent)
        ctx.say("pads in after you, tail going")
'''

DOG_ON = '''
def on(ctx, event):
    if event.target != ctx.self.id:
        return
    item = ctx.get(event.payload["item"])
    if item is not None and item.state.kind == "food":
        ctx.destroy(item)
        ctx.patch(ctx.self, {"friend": event.payload["by"]})
        ctx.say("wolfs it down and looks up at you. You have a dog now.")
    else:
        ctx.say("sniffs it and loses interest")
'''

LANDING_ON = '''
def on(ctx, event):
    if event.kind == "fog":
        ctx.self.state.fog = True
'''

STORY = '''
def on(ctx, event):
    # installed on the world root with set_rule, so it hears every event; the stage lives on the Story entity
    story = ctx.find(type="story", limit=1)[0]
    st = story.state
    stage = st.stage
    k = event.kind
    if stage == "start" and k == "arrived" and event.payload.get("place") == st.landing:
        ctx.emit("scene", target=st.landing, reach=1,
                 text="Cold mist lifts off the river. The raft is moored and the bell rope on the post hangs cut. No ferryman.")
        ctx.patch(story, {"stage": "ask"})
    elif stage == "ask" and k == "talked" and event.target == st.mara:
        about = str(event.payload.get("about", "")).lower()
        if "ferry" in about or "tam" in about or "cross" in about or "river" in about:
            # patch merges: this adds one topic to Mara's table without touching the rest
            ctx.patch(ctx.get(st.mara), {"dialog": {
                "bell": "The landing bell calls him down from wherever he is sleeping it off. Rope was cut by the Pell boys. Hob at the mill keeps rope."}})
            ctx.patch(story, {"stage": "bell"})
    elif stage in ("ask", "bell") and k == "rang":
        tam = ctx.get(st.tam)
        ctx.patch(tam, {"hidden": False})
        ctx.move(tam, st.landing)
        ctx.emit("scene", target=st.square, reach=1, text="Far off, a hoarse voice answers the bell.")
        ctx.emit("scene", target=st.landing, reach=1, text="Old Tam comes down the reed path, rubbing his eyes, and steps onto the raft.")
        ctx.patch(story, {"stage": "cross"})
    elif stage == "cross" and k == "crossed":
        ctx.emit("scene", target=st.far_bank, reach=1, text="The raft grinds onto the far shingle. Behind you Ashford is a handful of lights in the fog.")
        ctx.patch(ctx.root(), {"story": "complete"})
        ctx.patch(story, {"stage": "done"})
'''


# ---- what things can do ----------------------------------------------------------------


def define(s):
    """Scripts and schemas. Safe to run again on a live world: entities keep their state and pick up the new code."""
    for sid, src in [("go", GO), ("take", TAKE), ("drop", DROP), ("give", GIVE), ("talk", TALK), ("read", READ),
                     ("drink", DRINK), ("tie", TIE), ("ring", RING), ("light", LIGHT), ("cross", CROSS),
                     ("attack", ATTACK), ("peace", PEACE), ("person_on", PERSON_ON), ("hob_walk", HOB_WALK),
                     ("dog_follow", DOG_FOLLOW), ("dog_on", DOG_ON), ("landing_on", LANDING_ON), ("story", STORY)]:
        s.define_script(sid, src)

    # scope keeps impossible pairs out of a player's affordances: go only to exits, drop only what you hold.
    # The dialog table is secret: a player hears a line when they ask, not the whole table in perceive.
    # person_on is skipped while an agent embodies the person: the table is the floor, a mind sits on top.
    s.define_schema("person", extends="creature", doc="Someone who can walk, carry, talk and fight.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": [],
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
                        "attack": {"script": "attack", "doc": "Strike someone", "targets": "creature", "scope": "here"},
                    },
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])
    s.define_schema("dog", extends="creature", doc="Follows whoever feeds it.", state={"hp": 6, "max_hp": 6, "friend": None},
                    behaviors=[{"script": "dog_follow", "every": 6}],
                    listeners=[{"script": "dog_on", "kinds": ["given"]}])
    s.define_schema("miller", extends="person", doc="Walks between the mill and the square.",
                    behaviors=[{"script": "hob_walk", "every": 45}])
    s.define_schema("sign", extends="thing", doc="Something with writing on it.", state={"text": "", "portable": False},
                    actions={"read": {"script": "read", "doc": "Read what is written"}})
    s.define_schema("drinkable", extends="thing", doc="A drink. Two pulls to a mug.", state={"left": 2, "portable": True},
                    actions={"drink": {"script": "drink", "doc": "Drink from it (you must hold it)", "duration": 3}})
    s.define_schema("bell", extends="thing", doc="A landing bell. Needs its rope.", state={"rope": False, "portable": False},
                    actions={"tie": {"script": "tie", "doc": "Tie a rope you hold onto it"},
                             "ring": {"script": "ring", "doc": "Pull the rope"}})
    s.define_schema("lantern", extends="thing", state={"lit": False, "portable": True},
                    actions={"light": {"script": "light", "doc": "Light it (you need fire)"}})
    s.define_schema("raft", extends="thing", doc="The ferry. Crossing takes a while.", state={"portable": False, "far_bank": None},
                    actions={"cross": {"script": "cross", "doc": "Cross the river on it", "duration": 12}})
    s.define_schema("landing", extends="place", listeners=[{"script": "landing_on", "kinds": ["fog"]}])
    s.define_schema("story", extends="entity", doc="The rails. Hidden; holds the stage.", state={"hidden": True, "stage": "start"})


# ---- what there is ---------------------------------------------------------------------

# What a narrator may and may not change while running this world. Read by agents, not by the engine.
POLICY = {
    "fixed": [
        "the rails: Mara knows the way, the bell calls Tam, Tam rows, the fog comes at t=90 and blinds the crossing without a lit lantern",
        "there is no money in Ashford; favors and debts instead",
        "nobody raises a hand in the square",
        "the four NPCs and the four places",
    ],
    "fill": True,    # small things a village would have (a bench, a second mug, a stray cat) may be spawned with state {"improvised": true}
    "voice": True,   # NPCs may say free lines through say_as when their table has no answer, in their own voice
}


def populate(s):
    """Places, people, things, rules and the clock, into the world the session points at."""
    root = s.summary()["root"]
    s.patch(root, {"policy": POLICY})

    square = s.spawn("place", root, "Ashford Square", state={
        "description": "A packed-earth square between the inn, the well and the road down to the river. "
                       "Dusk is coming on; someone has lit the inn lamps."})["id"]
    mill = s.spawn("place", root, "Pell's Mill", state={
        "description": "The wheel turns slow in the mill race. Flour dust on everything. Rope, sacks and a sleeping dog."})["id"]
    landing = s.spawn("landing", root, "The Landing", state={
        "description": "A shingle bank where the road ends at the water. A post with a bell, a moored raft, reeds either side.",
        "fog": False})["id"]
    far = s.spawn("place", root, "The Far Bank", state={
        "description": "Shingle and a path going up into the dark. The village is behind you now.",
        "hidden": True})["id"]
    s.connect(square, mill)
    s.connect(square, landing)

    # the square
    mara = s.spawn("person", square, "Mara", state={
        "description": "The innkeeper. Knows everyone's business and most of their debts.",
        "dialog": {
            "ferry|across|crossing": "Tam's not been back since noon. Went up to the mill to drink with Hob and that was that. If you need across you need him, and the bell is the way to call him.",
            "tam|ferryman": "Old Tam rows the ferry. Drinks at the mill. Sleeps where he falls.",
            "hob|mill|miller": "Hob Pell runs the mill. Decent man, terrible sons.",
            "fog|weather|dark": "River fog comes in with the dark. Nobody crosses blind. Take a light.",
            "lantern|lamp": "There's a lantern on the post at the landing. You'll want something to light it with.",
            "light|fire|tinderbox": {"line": "You'll want a tinderbox for that. Here, I keep a spare.",
                                     "after_gift": "You've my spare already. Don't drop it in the river."},
            "dog|biscuit": "That's Biscuit. He'll follow anyone with a bone.",
            "bone|food": "Something for the dog? Look under the bench by the well.",
            "ale|drink|beer|pint": {"line": "One, mind. You've a river to cross.",
                                    "after_gift": "One was the deal. The river's waiting on you, not the other way round."},
            "pay|coin|money": "Put it away. Nobody pays coin in Ashford; you'll owe me a story when you're back this way.",
        },
        "default_line": "Mara wipes a mug. 'Ask me something I know about: the ferry, Tam, Hob, the fog, the light. Or have a drink.'",
        "gives": {
            "light|fire|tinderbox": {"type": "thing", "name": "Tinderbox", "state": {"kind": "fire", "portable": True}},
            "ale|drink|beer|pint": {"type": "drinkable", "name": "Dark ale", "line": "She sets a dark ale in front of you.",
                                    "state": {"description": "A mug of dark ale, head still settling."}},
        },
    })["id"]
    s.spawn("sign", square, "Notice board", state={
        "text": "FERRY: dawn to dusk, ring for Tam. NO CROSSINGS IN FOG. Pell's Mill buying barley. Lost: one grey dog, answers to Biscuit, does not come when called."})
    s.spawn("thing", square, "Well", state={"portable": False, "description": "Stone well with a wooden lid and a bench beside it, worn pale where people sit."})
    s.spawn("thing", square, "Bench", state={"portable": False, "description": "A plank bench by the well. Something under it."})
    s.spawn("thing", square, "Bone", state={"kind": "food", "portable": True, "description": "A soup bone, mostly gnawed. Under the bench."})
    s.set_rule(square, "peace")

    # the mill
    hob = s.spawn("miller", mill, "Hob", state={
        "description": "The miller. Big, floury, tired.",
        "home": mill, "haunt": square,
        "lines": ["'Wheel wants greasing.'", "'If you see my boys, send them home.'", "'Tam owes me for three jugs.'"],
        "dialog": {
            "rope|cord|line": "Rope? Take a coil, there's plenty. It's my boys cut the bell rope and I'll not have the village think ill of the mill.",
            "tam|ferryman": "Tam was here till the second jug. Went off to sleep it off in the reeds behind the mill, I'd guess.",
            "boys|sons|bell": "My boys cut the bell rope for a lark. They'll hear about it.",
            "dog|biscuit": "That's Biscuit. Not mine. Nobody's, till somebody feeds him.",
        },
        "default_line": "Hob shrugs flour off his shoulders. 'Rope, Tam, my boys. That's all I've got for you.'",
    })["id"]
    s.spawn("thing", mill, "Coil of rope", state={"kind": "rope", "portable": True})
    s.spawn("thing", mill, "Sack of flour", state={"portable": True, "description": "Heavy. Why would you."})
    s.spawn("dog", mill, "Biscuit", state={"description": "A grey dog with flour in his coat."})
    tam = s.spawn("person", mill, "Old Tam", state={
        "description": "The ferryman. Hoarse, damp, cheerful enough.",
        "role": "ferryman", "hidden": True,
        "dialog": {"ferry|across|river": "Aye, aye. On the raft with you. I'll take you over.",
                   "cross|crossing": "Say 'cross' on the raft and hold on."},
        "default_line": "Tam yawns. 'You rang. I came. Let's cross before the fog thickens.'",
    })["id"]

    # the landing
    s.spawn("bell", landing, "Landing bell", state={"description": "Iron bell on a post. The rope ends in a clean cut a foot below the clapper."})
    s.spawn("lantern", landing, "Post lantern", state={"description": "A storm lantern hung from the bell post. Unlit."})
    s.spawn("raft", landing, "Ferry raft", state={"far_bank": far, "description": "Pole-and-rope raft, moored to the post."})

    # the player's seat
    s.spawn("person", square, "Traveler", state={"role": "traveler", "description": "You. Needing to be across the river tonight."})

    # the rails and the weather
    s.spawn("story", root, "Story", state={"square": square, "mill": mill, "landing": landing, "far_bank": far,
                                           "mara": mara, "hob": hob, "tam": tam})
    s.set_rule(root, "story", kinds=["arrived", "talked", "rang", "crossed"])
    s.schedule(90, "fog", entity=landing, payload={"text": "Fog comes up off the water and swallows the far bank."})
    # turn-based: paused, three world seconds per embodied act. clock(run=True) makes it realtime instead.
    s.clock(run=False, turn=3)
    return s.summary()


def build(s):
    s.create_world("The Ferry at Dusk", seed=11, id="ferry-at-dusk",
                   description="A river village at dusk. The ferryman is missing. Cross before the fog closes in.")
    define(s)
    return populate(s)
