"""The Ferry at Dusk: three places, four NPCs, one storyline on rails.

    uv run embody --as gm --author load worlds/ferry_at_dusk.py
    uv run embody --as you join ferry-at-dusk Traveler
    uv run embody --as you perceive

The ferryman is missing and the river must be crossed before the fog. Everything that
moves the story is deterministic code in this file: the storyline waits for events, the
innkeeper answers to topics, the miller wanders, the dog follows whoever feeds it, the fog
rolls in on a timer. Whoever embodies the Traveler (a person, or Claude) does the playing;
whoever runs the GM session narrates and can nudge any NPC with act_as.

Rails (a rule on the root watches for these, the hidden Story entity keeps the stage):
  arrive at the Landing  ->  ask Mara about the ferry  ->  tie the rope, ring the bell
  ->  Old Tam comes down to the Landing  ->  cross (12 s, needs the lantern lit once the fog is in)
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
def on(ctx, event):
    # Someone talked to me. Answer from my dialog table; hand over anything I give for that topic.
    if event.target != ctx.self.id:
        return
    topic = str(event.payload.get("about", "")).lower()
    me = ctx.self.state
    dialog = me.dialog or {}
    for key in dialog:
        if key in topic:
            ctx.say(dialog[key])
            gives = me.gives or {}
            gave = me.gave or []
            if key in gives and key not in gave:
                g = gives[key]
                ctx.spawn(g["type"], event.payload["by"], name=g["name"], state=g.get("state"))
                ctx.say(f"Here, take the {g['name'].lower()}.")
                ctx.patch(ctx.self, {"gave": gave + [key]})
            return
    ctx.say(me.default_line or "Hm.")
'''

READ = '''
def apply(ctx):
    text = ctx.target.state.text or "nothing is written on it"
    ctx.emit("read", target=ctx.target, reach=0, text=text)
    ctx.log(text)
    return text
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
            mara = ctx.get(st.mara)
            d = dict(mara.state.dialog)
            d["bell"] = "The landing bell calls him down from wherever he is sleeping it off. Rope was cut by the Pell boys. Hob at the mill keeps rope."
            ctx.patch(mara, {"dialog": d})
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


# ---- the world -------------------------------------------------------------------------


def build(s):
    s.create_world("The Ferry at Dusk", seed=11, id="ferry-at-dusk",
                   description="A river village at dusk. The ferryman is missing. Cross before the fog closes in.")

    for sid, src in [("go", GO), ("take", TAKE), ("drop", DROP), ("give", GIVE), ("talk", TALK), ("read", READ),
                     ("tie", TIE), ("ring", RING), ("light", LIGHT), ("cross", CROSS), ("attack", ATTACK),
                     ("peace", PEACE), ("person_on", PERSON_ON), ("hob_walk", HOB_WALK), ("dog_follow", DOG_FOLLOW),
                     ("dog_on", DOG_ON), ("landing_on", LANDING_ON), ("story", STORY)]:
        s.define_script(sid, src)

    s.define_schema("person", extends="creature", doc="Someone who can walk, carry, talk and fight.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": [], "secret": ["gives", "gave"]},
                    actions={
                        "go": {"script": "go", "doc": "Walk to a connected place", "targets": "place"},
                        "take": {"script": "take", "doc": "Pick something up", "targets": "thing"},
                        "drop": {"script": "drop", "doc": "Put down something you hold", "targets": "thing"},
                        "give": {"script": "give", "doc": "Hand something you hold to someone here",
                                 "targets": "creature", "params": {"item": "id or name of a thing you hold"}},
                        "talk": {"script": "talk", "doc": "Talk to someone about something",
                                 "targets": "creature", "params": {"about": "the topic"}},
                        "attack": {"script": "attack", "doc": "Strike someone", "targets": "creature"},
                    },
                    listeners=[{"script": "person_on", "kinds": ["talked"]}])
    s.define_schema("dog", extends="creature", doc="Follows whoever feeds it.", state={"hp": 6, "max_hp": 6, "friend": None},
                    behaviors=[{"script": "dog_follow", "every": 6}],
                    listeners=[{"script": "dog_on", "kinds": ["given"]}])
    s.define_schema("miller", extends="person", doc="Walks between the mill and the square.",
                    behaviors=[{"script": "hob_walk", "every": 45}])
    s.define_schema("sign", extends="thing", doc="Something with writing on it.", state={"text": "", "portable": False},
                    actions={"read": {"script": "read", "doc": "Read what is written"}})
    s.define_schema("bell", extends="thing", doc="A landing bell. Needs its rope.", state={"rope": False, "portable": False},
                    actions={"tie": {"script": "tie", "doc": "Tie a rope you hold onto it"},
                             "ring": {"script": "ring", "doc": "Pull the rope"}})
    s.define_schema("lantern", extends="thing", state={"lit": False, "portable": True},
                    actions={"light": {"script": "light", "doc": "Light it (you need fire)"}})
    s.define_schema("raft", extends="thing", doc="The ferry. Crossing takes a while.", state={"portable": False, "far_bank": None},
                    actions={"cross": {"script": "cross", "doc": "Cross the river on it", "duration": 12}})
    s.define_schema("landing", extends="place", listeners=[{"script": "landing_on", "kinds": ["fog"]}])
    s.define_schema("story", extends="entity", doc="The rails. Hidden; holds the stage.", state={"hidden": True, "stage": "start"})

    root = s.summary()["root"]
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
            "ferry": "Tam's not been back since noon. Went up to the mill to drink with Hob and that was that. If you need across you need him, and the bell is the way to call him.",
            "tam": "Old Tam rows the ferry. Drinks at the mill. Sleeps where he falls.",
            "hob": "Hob Pell runs the mill. Decent man, terrible sons.",
            "fog": "River fog comes in with the dark. Nobody crosses blind. Take a light.",
            "lantern": "There's a lantern on the post at the landing. You'll want something to light it with.",
            "light": "You'll want a tinderbox for that. Here, I keep a spare.",
            "dog": "That's Biscuit. He'll follow anyone with a bone.",
            "bone": "Something for the dog? Look under the bench by the well.",
        },
        "default_line": "Mara wipes a mug. 'Ask me something I know about: the ferry, Tam, Hob, the fog, the light.'",
        "gives": {"light": {"type": "thing", "name": "Tinderbox", "state": {"kind": "fire", "portable": True}}},
    })["id"]
    s.spawn("sign", square, "Notice board", state={
        "text": "FERRY: dawn to dusk, ring for Tam. NO CROSSINGS IN FOG. Pell's Mill buying barley. Lost: one grey dog, answers to Biscuit, does not come when called."})
    s.spawn("thing", square, "Bone", state={"kind": "food", "portable": True, "description": "A soup bone, mostly gnawed. Under the bench."})
    s.set_rule(square, "peace")

    # the mill
    hob = s.spawn("miller", mill, "Hob", state={
        "description": "The miller. Big, floury, tired.",
        "home": mill, "haunt": square,
        "lines": ["'Wheel wants greasing.'", "'If you see my boys, send them home.'", "'Tam owes me for three jugs.'"],
        "dialog": {
            "rope": "Rope? Take a coil, there's plenty. It's my boys cut the bell rope and I'll not have the village think ill of the mill.",
            "tam": "Tam was here till the second jug. Went off to sleep it off in the reeds behind the mill, I'd guess.",
            "boys": "My boys cut the bell rope for a lark. They'll hear about it.",
        },
        "default_line": "Hob shrugs flour off his shoulders. 'Rope, Tam, my boys. That's all I've got for you.'",
    })["id"]
    s.spawn("thing", mill, "Coil of rope", state={"kind": "rope", "portable": True})
    s.spawn("thing", mill, "Sack of flour", state={"portable": True, "description": "Heavy. Why would you."})
    s.spawn("dog", mill, "Biscuit", state={"description": "A grey dog with flour in his coat."})
    tam = s.spawn("person", mill, "Old Tam", state={
        "description": "The ferryman. Hoarse, damp, cheerful enough.",
        "role": "ferryman", "hidden": True,
        "dialog": {"ferry": "Aye, aye. On the raft with you. I'll take you over.", "cross": "Say 'cross' on the raft and hold on."},
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
    s.clock(run=True)
    return s.summary()
