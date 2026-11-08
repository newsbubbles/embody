"""The Ferry at Dusk: five places, four NPCs, one storyline that watches facts.

    uv run embody --as gm --author load worlds/ferry_at_dusk.py
    uv run embody --as you join ferry-at-dusk Traveler
    uv run embody --as you perceive

The ferryman is missing and the river must be crossed before the fog. Everything that
moves the story is deterministic code in this file: the storyline waits for events, the
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

The file is split so a running world can take new code without losing its state:
  define(s)    scripts and schemas (what things can do)
  populate(s)  places, people, things, rules, the clock (what there is)
  upgrade(s)   idempotent additions for a world built from an older file (the Reeds, the tinderbox, ambient, timers)
  build(s)     a new world: create, define, populate
`uv run embody load worlds/ferry_at_dusk.py --upgrade` runs define() then upgrade() against the current world.

Play is turn-based: the clock is paused and every act of an embodied player moves the world
three seconds (longer for a slow verb). Fog at t=90, night at t=150, dawn at t=400.
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
    here = ctx.actor.parent
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id)
    # whoever follows you comes along: the dog you fed, anyone told to follow
    for p in ctx.children(here):
        if p.state.friend == ctx.actor.id or p.state.follows == ctx.actor.id:
            if not p.state.asleep:
                ctx.move(p, ctx.target)
                ctx.emit("arrived", target=ctx.target, reach=1, who=p.id, place=ctx.target.id, following=ctx.actor.id)
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
    if ctx.target.state.asleep:
        return "they are asleep; wake them first"
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

def score(key, topic):
    # a dialog key is one word or several joined with |: "ale|drink|beer". The score is how many aliases
    # the topic contains plus a little for longer aliases, so "ferry crossing" prefers the ferry entry.
    s = 0
    for alias in key.split("|"):
        a = alias.strip()
        if a in topic:
            s = s + 10 + len(a)
    return s

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

def hand_over(ctx, g, asker):
    # a gift is a held thing named in "item" (handed over for real), or a thing spawned from the table
    item = g.get("item")
    if item:
        for it in ctx.self.children():
            if (it.name or "").lower() == str(item).lower():
                ctx.move(it, asker)
                ctx.emit("given", target=asker, reach=1, item=it.id, by=ctx.self.id)
                return True
        return False
    ctx.spawn(g["type"], asker, name=g["name"], state=g.get("state"))
    return True

def on(ctx, event):
    # Someone talked to me. Answer from my dialog table with the best-matching entry; hand over anything I
    # give for that topic. Skipped while an agent embodies me (unless_embodied): then the agent answers.
    if event.target != ctx.self.id:
        return
    topic = words(event.payload.get("about", ""))
    asker = event.payload.get("by")
    me = ctx.self.state
    dialog = me.dialog or {}
    gives = me.gives or {}
    gave = me.gave or []
    best = None
    best_s = 0
    for key in dialog:
        s = score(key, topic)
        if s > best_s:
            best = key
            best_s = s
    if best is None:
        ctx.say(me.default_line or "Hm.", to=asker)
        return
    line = pick(ctx, dialog[best], best, gave)
    if line:
        ctx.say(line, to=asker)
    if best in gives and best not in gave:
        g = gives[best]
        if hand_over(ctx, g, asker):
            ctx.say(g.get("line") or "Here, take the " + str(g.get("name") or g.get("item")).lower() + ".", to=asker)
            ctx.patch(ctx.self, {"gave": gave + [best]})
        else:
            ctx.say(g.get("gone_line") or "I had one of those somewhere. Gone now.", to=asker)
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
        if p.state.role == "ferryman" and not p.state.asleep:
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

def other_bank(ctx):
    here = ctx.actor.parent.id
    banks = ctx.self.state.banks or []
    for b in banks:
        if b != here:
            return ctx.get(b)
    return ctx.get(ctx.self.state.far_bank)

def finish(ctx):
    far = other_bank(ctx)
    here = ctx.actor.parent
    tam = ferryman_here(ctx)
    ctx.move(ctx.actor, far)
    if tam:
        ctx.move(tam, far)
    # the dog you fed and anyone following you ride along; the raft itself ends up on that side
    for p in ctx.children(here):
        if p.state.friend == ctx.actor.id or p.state.follows == ctx.actor.id:
            ctx.move(p, far)
    ctx.move(ctx.self, far)
    ctx.emit("crossed", target=far, reach=-1, who=ctx.actor.id, from_bank=here.id)
'''

PEACE = '''
def on(ctx, event):
    if event.payload["verb"] == "attack":
        ctx.reject("nobody raises a hand in the square; Mara would never forgive it", "talk instead")
'''

ASLEEP_GUARD = '''
def on(ctx, event):
    # a sleeper does nothing but wake (or get woken); installed on the root so it hears every before_act
    if ctx.actor is not None and ctx.actor.state.asleep and event.payload["verb"] != "wake":
        ctx.reject("you are asleep", "wake yourself (act wake on yourself) or wait to be woken")
'''

ATTACK = '''
def apply(ctx):
    dmg = ctx.rand.roll("1d6")
    ctx.target.state.hp = ctx.target.state.hp - dmg
    ctx.emit("hit", target=ctx.target, reach=1, dmg=dmg)
    return dmg
'''

TOUCH = '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id and ctx.target.parent.id != ctx.actor.id:
        return "it is not within reach"
    return True

def apply(ctx):
    ctx.emit("touched", target=ctx.target, reach=1, by=ctx.actor.id)
'''

CHECK = '''
def apply(ctx):
    # a plain d20 with the world's seed: deterministic, replayable, and the player sees the number
    skill = ""
    if ctx.params:
        skill = str(ctx.params.get("skill", ""))
    roll = ctx.rand.roll("1d20")
    ctx.emit("checked", target=ctx.target, reach=1, by=ctx.actor.id, skill=skill, roll=roll)
    ctx.log("d20: " + str(roll))
    return roll
'''

SLEEP = '''
def check(ctx):
    if ctx.actor.state.asleep:
        return "you are already asleep"
    return True

def apply(ctx):
    ctx.actor.state.asleep = True
    ctx.emit("slept", target=ctx.actor, reach=1, who=ctx.actor.id)
    ctx.log("You settle down and sleep. Dawn, or a hand on your shoulder, will wake you.")
'''

WAKE = '''
def check(ctx):
    if not ctx.target.state.asleep:
        return "they are awake"
    if ctx.target.id != ctx.actor.id and ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    ctx.target.state.asleep = False
    ctx.emit("woken", target=ctx.target, reach=-1, by=ctx.actor.id)  # to the root: the story listens for Tam
'''

HOB_WALK = '''
def tick(ctx):
    me = ctx.self
    st = me.state
    if st.asleep:
        return
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
    if event.kind == "touched":
        if ctx.self.state.friend == event.payload.get("by"):
            ctx.say("leans into your hand, tail thumping the floor")
        else:
            ctx.say("sniffs your hand, then your pockets, hopeful")
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
        ctx.patch(ctx.self, {"ambient": {"weather": "river fog, thick; the far bank is gone"}})
    elif event.kind == "dawn":
        ctx.self.state.fog = False
        ctx.patch(ctx.self, {"ambient": {"weather": "the fog thinning off the water"}})
'''

WEATHER = '''
def on(ctx, event):
    # the ambient facts every perceive carries: on the root, laid under each place's own
    root = ctx.root()
    if event.kind == "fog":
        ctx.patch(root, {"ambient": {"weather": "fog coming up off the river"}})
        ctx.emit("scene", target=ctx.get(event.target).parent if ctx.get(event.target) else root, reach=0,
                 text=event.payload.get("text", "Fog."))
    elif event.kind == "nightfall":
        ctx.patch(root, {"ambient": {"time_of_day": "night", "light": "dark; lamps and stars"}})
        for place in ctx.find(type="place"):
            ctx.emit("scene", target=place, reach=0, text="The last light goes out of the sky. Night, proper.")
    elif event.kind == "dawn":
        ctx.patch(root, {"ambient": {"time_of_day": "dawn", "weather": "clear and cold", "light": "grey, growing"}})
        for place in ctx.find(type="place"):
            ctx.emit("scene", target=place, reach=0, text="Grey light. Birds in the reeds. Dawn.")
        for p in ctx.find(type="person"):
            if p.state.asleep:
                ctx.patch(p, {"asleep": False})
                ctx.emit("woken", target=p, reach=-1, by=None, dawn=True)
'''

STORY = '''
def tam_to_landing(ctx, st, how):
    tam = ctx.get(st.tam)
    if tam is None or tam.parent.id == st.landing:
        return
    ctx.patch(tam, {"hidden": False, "asleep": False})
    ctx.move(tam, st.landing)
    if how == "bell":
        ctx.emit("scene", target=st.square, reach=1, text="Far off, a hoarse voice answers the bell.")
        ctx.emit("scene", target=st.landing, reach=1, text="Old Tam comes down the reed path, rubbing his eyes, and steps onto the raft.")
    else:
        ctx.emit("scene", target=st.reeds, reach=1, text="Tam gets up, brushes off the reeds and sets off down the bank. 'Raft is this way.'")
        ctx.emit("scene", target=st.landing, reach=1, text="Old Tam comes along the bank from the reeds and steps onto the raft.")
    ctx.emit("arrived", target=st.landing, reach=-1, who=tam.id, place=st.landing)
    ctx.patch(ctx.find(type="story", limit=1)[0], {"stage": "cross", "tam_came_by": how})

def on(ctx, event):
    # installed on the world root with set_rule, so it hears every event; the Story entity keeps the facts.
    # Every branch checks a fact, not the stage, so play off the rails still finds the river.
    story = ctx.find(type="story", limit=1)[0]
    st = story.state
    k = event.kind
    if k == "arrived" and event.payload.get("place") == st.landing and not st.seen_landing:
        ctx.emit("scene", target=st.landing, reach=1,
                 text="Cold mist lifts off the river. The raft is moored and the bell rope on the post hangs cut. No ferryman.")
        ctx.patch(story, {"seen_landing": True, "stage": "ask"})
    elif k == "talked" and event.target == st.mara and not st.mara_told:
        about = str(event.payload.get("about", "")).lower()
        if "ferry" in about or "tam" in about or "cross" in about or "river" in about:
            # patch merges: this adds one topic to Mara's table without touching the rest
            ctx.patch(ctx.get(st.mara), {"dialog": {
                "bell": "The landing bell calls him down from wherever he is sleeping it off. Rope was cut by the Pell boys. Hob at the mill keeps rope."}})
            ctx.patch(story, {"mara_told": True, "stage": "bell"})
    elif k == "rang":
        tam_to_landing(ctx, st, "bell")
    elif k == "woken" and event.target == st.tam:
        tam_to_landing(ctx, st, "woken")
    elif k == "crossed" and not st.crossed and event.target == st.far_bank:
        ctx.emit("scene", target=st.far_bank, reach=1, text="The raft grinds onto the far shingle. Behind you Ashford is a handful of lights in the fog.")
        ctx.patch(ctx.root(), {"story": "complete"})
        ctx.patch(story, {"crossed": True, "stage": "done"})
'''


# ---- what things can do ----------------------------------------------------------------


def define(s):
    """Scripts and schemas. Safe to run again on a live world: entities keep their state and pick up the new code."""
    for sid, src in [("go", GO), ("take", TAKE), ("drop", DROP), ("give", GIVE), ("talk", TALK), ("read", READ),
                     ("drink", DRINK), ("tie", TIE), ("ring", RING), ("light", LIGHT), ("cross", CROSS),
                     ("attack", ATTACK), ("touch", TOUCH), ("check", CHECK), ("sleep", SLEEP), ("wake", WAKE),
                     ("peace", PEACE), ("asleep_guard", ASLEEP_GUARD), ("person_on", PERSON_ON),
                     ("hob_walk", HOB_WALK), ("dog_follow", DOG_FOLLOW), ("dog_on", DOG_ON),
                     ("landing_on", LANDING_ON), ("weather", WEATHER), ("story", STORY)]:
        s.define_script(sid, src)

    # scope keeps impossible pairs out of a player's affordances: go only to exits, drop only what you hold.
    # The dialog table is secret: a player hears a line when they ask, not the whole table in perceive.
    # person_on is skipped while an agent embodies the person: the table is the floor, a mind sits on top.
    s.define_schema("person", extends="creature", doc="Someone who can walk, carry, talk, sleep and fight.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": [], "asleep": False,
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
                    },
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])
    s.define_schema("dog", extends="creature", doc="Follows whoever feeds it.", state={"hp": 6, "max_hp": 6, "friend": None},
                    behaviors=[{"script": "dog_follow", "every": 6}],
                    listeners=[{"script": "dog_on", "kinds": ["given", "touched"]}])
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
        "the fog comes at t=90 and blinds the crossing without a lit lantern, night at t=150, dawn at t=400",
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
        "sleep|bed|room": "There's a bench by the fire if you must. But the river won't wait for morning, and the fog won't either.",
    },
    "default_line": "Mara wipes a mug. 'Ask me something I know about: the ferry, Tam, Hob, the fog, the light. Or have a drink.'",
    "gives": {
        # the tinderbox is a real thing in her apron, handed over; a mind embodying her gives it with the give verb
        "light|fire|tinderbox": {"item": "Tinderbox", "line": "She digs the tinderbox out of her apron and puts it in your hand.",
                                 "gone_line": "Gave my spare away already. Try the mill; Hob keeps a fire going."},
        "ale|drink|beer|pint": {"type": "drinkable", "name": "Dark ale", "line": "She sets a dark ale in front of you.",
                                "state": {"description": "A mug of dark ale, head still settling."}},
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
               "hob|jugs|owe": "Three jugs. I know. He'll have them when the barley's in."},
    "default_line": "Tam yawns. 'You found me. Let's cross before the fog thickens.'",
}


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
    s.spawn("thing", square, "Bench", state={"portable": False, "description": "A plank bench by the well. Something under it."})
    s.spawn("thing", square, "Bone", state={"kind": "food", "portable": True, "description": "A soup bone, mostly gnawed. Under the bench."})
    s.set_rule(square, "peace")

    # the mill
    hob = s.spawn("miller", mill, "Hob", state={**HOB, "home": mill, "haunt": square})["id"]
    s.spawn("thing", mill, "Coil of rope", state={"kind": "rope", "portable": True})
    s.spawn("thing", mill, "Sack of flour", state={"portable": True, "description": "Heavy. Why would you."})
    s.spawn("dog", mill, "Biscuit", state={"description": "A grey dog with flour in his coat."})

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


def build(s):
    s.create_world("The Ferry at Dusk", seed=11, id="ferry-at-dusk",
                   description="A river village at dusk. The ferryman is missing. Cross before the fog closes in.")
    define(s)
    return populate(s)
