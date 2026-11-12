# The Guild comes down after the moon (Nate 2026-11-11: the speakers come after the moon, and Dreyer's scheme lines
# up with the arrival). A day after the moon turns, the crawler from up the road brings Factor Ivo Senn and Reckoner
# Aurel Quist to the Landing with five Guild speakers: the Landing's for Ossa, the post's for Sergeant Marr, the yard's
# for the wright set over it (or Mira Ost on its door), the factor's own, and the gate's, which the factor carries
# until the Guild names who holds Scar Gate. Two days on, he names them: the house the moon left at the gate, unless
# the other house put more glass in his hand, and ten shards at least. The gate's slab goes to that house's head.
# The story keeps guild_due, guild_down and guild_recognizes; the factor keeps the glass each house paid in `bids`.
DESCENT = 86400
RECOGNIZE = 172800
BRIBE = 10
FACTOR = "Factor Ivo Senn"
RECKONER = "Reckoner Aurel Quist"
SLAB = ("A palm-sized slab of dark glass, cool and heavier than it looks, with the Guild's wheel-and-scale seal cut in its "
        "back. A Guild speaker: woken with ember, it stands up a small hologram that talks to its sister slabs anywhere "
        "in the Reach (call, send, read, contacts, charge).")
LINES = [("The Landing's speaker", "the Landing"), ("The post's speaker", "the wardens' post"),
         ("The yard's speaker", "the Guild Yard"), ("The factor's speaker", "the factor"), ("The gate's speaker", "Scar Gate")]
SPEAK = ("'A speaker,' the factor says, turning the slab so the seal catches the light. 'Cut from the mother crystal "
         "aboard the High Landing, the slow star you see cross before dawn. Every slab is a sister of every other; wake one "
         "with a shard and your picture and your words stand up out of its sister, wherever that is. The Guild keeps the "
         "lines and does not lend them. The slab tells true which slab is calling. The face on it is whatever you say it "
         "is, so learn your callers' questions.'")
QUIST_TALK = {
    "reckon|reckoner|consult|question|answer|mentat": "'Ask, and pay a shard. Water, the moon's count, the convoy, the "
        "Guild's glass. I answer the house that pays and the house that pays next, the same.'",
    "high landing|platform|slow star|station|ship|orbit|sky": "'Fifty kilometres keel to tip, twenty across the wide "
        "deck. I was trained on its third ring, in the reckoning halls, where the windows face the planet. Your Reach is "
        "a brown thumbprint from there.'",
    "speaker|slab|hologram|call": "'The slabs are sisters, cut from one crystal on the High Landing. The ember is what "
        "makes them speak; the crystal is why they can hear each other.'",
    "ear|seam|metal|wrist|inlaid|implant|chrome": "She touches the seam behind her ear, once. 'The reckoning halls cut "
        "deeper than ink.' She says no more about it.",
}
SENN_TALK = {
    "speaker|slab|hologram|call|message": "'A Guild speaker. Wake it with a shard and it puts your face and your words "
        "into its sister, anywhere. The source is always true; the face is not. The Guild owns every slab.'",
    "gate|recognize|recognise|holder|charter|house": "'The Master's letter says the Guild recognizes whoever holds Scar "
        "Gate, and sets a speaker there. Whoever holds it in two days' time. Holding has more than one meaning on a tally.'",
    "glass|shards|gift|offer|pay": "'The Guild is grateful for glass. Gratitude is entered on the tally, by house.'",
    "high landing|platform|slow star|station|ship|orbit|sky": "'The High Landing. The Guild's own ground, above "
        "everyone's. You will see it cross before dawn if you look east. One day the Reach may be asked up.'",
}
SENN = {"faction": "the Carriers", "factor": True, "body": 2, "wits": 4, "will": 4, "vigor": 7, "max_vigor": 7,
        "water": 10, "max_water": 10, "carry": 24, "bids": {},
        "description": "A narrow grey man in a Guild coat cut close, the sleeves whole, a ledger-case on a strap and a dark "
                       "glass slab in his left hand that he never quite puts down.",
        "default_line": "Factor Senn looks at you as if you were a column of figures. 'Yes?'",
        "secret": ["dialog", "gives", "gave", "word_left", "brief", "bids"],
        "brief": "You are Ivo Senn, factor of the Carriers' Guild, down from the Master of the Reach leg after the moon. "
                 "Your letter: recognize whoever holds Scar Gate and set the gate's speaker with them, in two days. You "
                 "carry the gate's slab until then. You are not a cruel man and not an honest one: the Guild's tally is "
                 "what matters, and a house that adds glass to it is easier to recognize. Explain the speakers to anyone "
                 "who is given one: what they are, how they work, what they cost. Never take a side aloud."}
QUIST = {"faction": "the Carriers", "reckoner": True, "body": 2, "wits": 5, "will": 5, "vigor": 6, "max_vigor": 6,
         "water": 10, "max_water": 10, "carry": 6,
         "description": "A small woman with a shaved head, a seam of dull metal behind her left ear, and Guild tally "
                        "marks inlaid in a ring around one wrist, sitting "
                        "very still, as if listening to numbers nobody else can hear.",
         "default_line": "Reckoner Quist opens her eyes. 'A shard, and a question.'",
         "secret": ["dialog", "gives", "gave", "word_left", "brief"],
         "brief": "You are Aurel Quist, a reckoner of the Carriers' Guild: a mentat, trained in the reckoning halls of the "
                  "High Landing. You answer what is paid for (consult: water, moon, convoy, glass), exactly and for "
                  "anyone, both houses alike. Off the clock you speak little, and mostly of the High Landing."}


def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def scene(ctx, place, text):
    if place is not None:
        ctx.emit("scene", target=place, reach=1, text=text)

def by_name(ctx, name):
    for e in ctx.find(name=name, limit=10):
        if e.name == name:
            return e
    return None

def alive(e):
    return e is not None and not e.state.dead

def descend(ctx, story):
    st = story.state
    landing = ctx.get(st.landing) if st.landing else by_name(ctx, "The Carriers' Landing")
    if landing is None:
        return
    senn = ctx.spawn("person", landing, FACTOR, state=dict(SENN, dialog=dict(SENN_TALK)))
    quist = ctx.spawn("person", landing, RECKONER, state=dict(QUIST, dialog=dict(QUIST_TALK)))
    ctx.remember(senn, "I came down from the Master's station with the reckoner and five speakers. The Landing's goes to "
                 "Ossa, the post's to Sergeant Marr, the yard's to the wright, the factor's I keep, and the gate's I carry "
                 "until I name the gate's holder on the Guild's tally, two days after I came. Glass given me is entered on "
                 "the tally by house. Whoever I hand a slab to, I tell what it is and how it works.")
    ctx.remember(quist, "I was trained in the reckoning halls on the High Landing's third ring, where the windows face the "
                 "planet: fifty kilometres keel to tip, twenty across the wide deck, the Guild's ground above everyone's. "
                 "Mira Ost at the yard is my sister's sister; she will want a word. The Master sent me down to sell true "
                 "counts to whoever pays, and I will.")
    names = []
    for pair in LINES:
        names.append(pair[1])
    slabs = {}
    for pair in LINES:
        others = []
        for n in names:
            if n != pair[1]:
                others.append(n)
        slabs[pair[1]] = ctx.spawn("speaker", senn, pair[0], state={"line": pair[1], "contacts": others, "charge": 3,
                                                                      "description": SLAB, "portable": True})
    ossa = by_name(ctx, "Ossa the Carrier")
    marr = by_name(ctx, "Sergeant Edda Marr")
    wright = ctx.get(st.guild_wright) if st.guild_wright else None
    if not alive(wright):
        wright = by_name(ctx, "Mira Ost")
    for who, line in [(ossa, "the Landing"), (marr, "the wardens' post"), (wright, "the Guild Yard")]:
        if alive(who):
            ctx.move(slabs[line], who)
            ctx.emit("slab_handed", target=slabs[line], reach=0, to=who.id)  # it wakes for them with the primer
            ctx.remember(who, "Factor Ivo Senn came down on the crawler after the moon and gave me " + slabs[line].name
                         + ". He showed me how it works: ember in its heart, a shard a call, sisters cut from one crystal on "
                         "the High Landing. If I hand it on, I tell them the same.")
    ctx.patch(story, {"guild_down": senn.id, "guild_speakers": [slabs[n].id for n in names]})
    ctx.schedule(RECOGNIZE, "guild_recognizes", target=ctx.root())
    scene(ctx, landing, "The crawler from up the road comes in with two in Guild grey riding the roof: a narrow factor with "
                        "a ledger-case and a still, shaved-headed woman with ink round her wrist. The factor hands Ossa a "
                        "slab of dark glass and wakes it with a shard: a hologram of a Guild clerk stands up out of it, "
                        "ember-coloured, no taller than a cup. " + SPEAK + " The woman sits down by the tally post and "
                        "closes her eyes. 'Reckoner Quist,' Ossa says quietly. 'She answers for a shard. Anything that is "
                        "counted.'")
    road = by_name(ctx, "The Salt Road")
    scene(ctx, road, "A Guild runner comes down from the Landing with a slab of dark glass for the sergeant, and shows her how "
                     "it wakes.")
    ctx.emit("guild_descended", target=ctx.root(), reach=-1, factor=senn.id)

def head_of(ctx, house):
    if house == "House Dreyer":
        h = by_name(ctx, "Halvard Dreyer")
        return h if alive(h) else None
    for n in ["Reeve Ansel Varrick", "Captain Ruhl"]:
        h = by_name(ctx, n)
        if alive(h):
            return h
    return None

def recognize(ctx, story):
    st = story.state
    senn = ctx.get(st.guild_down) if st.guild_down else None
    if not alive(senn):
        return
    holder = "House Dreyer" if st.outcome in ["fallen", "yielded"] else "House Varrick"
    other = "House Varrick" if holder == "House Dreyer" else "House Dreyer"
    bids = senn.state.bids or {}
    named = holder
    if int(bids.get(other) or 0) >= BRIBE and int(bids.get(other) or 0) > int(bids.get(holder) or 0):
        named = other
    head = head_of(ctx, named)
    gate = None
    for it in senn.children():
        if it.state.line == "Scar Gate":
            gate = it
    ctx.patch(story, {"guild_recognizes": named, "guild_bought": named != holder})
    ctx.remember(senn, "I named " + named + " the holder of Scar Gate on the Guild's tally. Glass from House Varrick: "
                 + str(int(bids.get("House Varrick") or 0)) + "; from House Dreyer: " + str(int(bids.get("House Dreyer") or 0)) + ".")
    if gate is not None and head is not None:
        ctx.move(gate, head)
        ctx.emit("slab_handed", target=gate, reach=0, to=head.id)
        ctx.remember(head, "Factor Ivo Senn named my house the holder of Scar Gate on the Guild's tally and sent me the "
                     "gate's speaker: a Guild slab that wakes with ember and talks to its sisters anywhere in the Reach.")
    landing = ctx.get(st.landing) if st.landing else None
    scene(ctx, landing, "Factor Senn opens his ledger at the tally post and reads it out flat: by the Guild's tally, Scar Gate "
                        "is held by " + named + ". He shuts the ledger. A runner leaves with the gate's slab wrapped in grey.")
    ctx.emit("guild_named", target=ctx.root(), reach=-1, house=named, bought=named != holder)

def on(ctx, event):
    story = story_of(ctx)
    st = story.state
    k = event.kind
    if k == "moon_turned":
        if not st.guild_due:
            ctx.patch(story, {"guild_due": ctx.t + DESCENT})
            ctx.schedule(DESCENT, "guild_descends", target=ctx.root())
        return
    if k == "guild_descends":
        if not st.guild_down:
            descend(ctx, story)
        return
    if k == "guild_recognizes":
        if st.guild_down and not st.guild_recognizes:
            recognize(ctx, story)
        return
    if k == "given":
        item = ctx.get(event.payload.get("item"))
        if item is not None and item.type == "speaker":
            ctx.emit("slab_handed", target=item, reach=0, to=event.target)  # a slab handed on wakes for its new holder
            return
        # glass in the factor's hand is entered on the tally, by the giver's house
        senn = ctx.get(st.guild_down) if st.guild_down else None
        if senn is None or event.target != senn.id or st.guild_recognizes:
            return
        item = ctx.get(event.payload.get("item"))
        giver = ctx.get(event.payload.get("by"))
        if item is None or giver is None or item.state.kind != "ember":
            return
        house = giver.state.faction
        if house not in ["House Varrick", "House Dreyer"]:
            return
        bids = dict(senn.state.bids or {})
        bids[house] = int(bids.get(house) or 0) + ctx.count(item)
        ctx.patch(senn, {"bids": bids})
