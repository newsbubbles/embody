# The road wardens: five Guild spears and bows at a post on the Salt Road, where every road in the Reach meets. They
# keep the road for the Carriers against Dreyer's men and look over strangers. A Dreyer man who walks onto the road is
# turned back to the Flats, unless a shard buys him a day's road or he creeps past the bows (stealth against the
# watch). A newcomer who is neither the Guild's nor the Hold's is held at the post once, until they talk to the
# sergeant or the hold runs out. Anyone not of the Guild who comes onto the road with two shards or more leaves one
# with the wardens. With every warden down or gone the post is empty and the road is open. The Guild waters its
# wardens at dawn and dusk (a ration up with the crawler, another with the night runner): there is no well at the
# post, so the road stays as dry for everyone else as it ever was.
WATCH_DC = 15  # a creep past the bows: d20 + wits + stealth
HOLD_AT_POST = 1800  # world seconds a stranger waits at the post if they say nothing
ROAD_DAY = 86400  # what a shard buys
SERGEANT = "Sergeant Edda Marr"

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def scene(ctx, place, text):
    if place is not None:
        ctx.emit("scene", target=place, reach=1, text=text)

def sergeant(ctx):
    for e in ctx.find(name=SERGEANT, limit=5):
        if e.name == SERGEANT:
            return e
    return None

def standing_wardens(ctx, road):
    n = 0
    for c in ctx.children(road, "creature"):
        if c.state.warden and not c.state.down and not c.state.dead:
            n = n + 1
    return n

def shards(who):
    out = []
    for c in who.children():
        if c.state.kind == "ember":
            out.append(c)
    return out

def paid(ctx, who):
    return bool(who.state.road_paid_until) and ctx.t < who.state.road_paid_until

def toll(ctx, who, glass, sgt, road):
    ctx.move(glass, sgt if sgt is not None else road)
    ctx.emit("road_toll", target=who, reach=1, by=who.id)

def arrive(ctx, st, who, quiet):
    road = ctx.get(st.road)
    if road is None or standing_wardens(ctx, road) == 0:
        return
    f = who.state.faction
    if f == "the Carriers" or paid(ctx, who):
        return
    sgt = sergeant(ctx)
    if f == "House Dreyer":
        if quiet:
            roll = ctx.rand.roll("1d20") + int(who.state.wits or 0) + int((who.state.skills or {}).get("stealth") or 0)
            if roll >= WATCH_DC:
                ctx.emit("scene", target=who, reach=0, text="You come up onto the road in the dune shadow with the broken "
                         "step. Up at the wardens' post a bow turns your way, holds, and turns back. Nobody calls out.")
                ctx.emit("slipped_past", target=who, reach=0, by=who.id)
                return
        glass = shards(who)
        if len(glass) > 0:
            toll(ctx, who, glass[0], sgt, road)
            ctx.patch(who, {"road_paid_until": ctx.t + ROAD_DAY})
            scene(ctx, road, "Spears come across the road at the wardens' post. " + SERGEANT + " looks " + who.name +
                  " up and down: no convoy coat, no Hold blade, sand of the south glass to the knee. She holds out a hand, "
                  "weighs the shard she is given, and nods. 'The road is the Guild's, and the Guild sells passage like "
                  "anything else. One day. Keep to it.'")
            return
        flats = ctx.get(st.flats)
        scene(ctx, road, "Spears come across the road at the wardens' post and two bows come up. " + SERGEANT + " looks " +
              who.name + " up and down: no convoy coat, no Hold blade, sand of the south glass to the knee. 'Nobody honest "
              "comes up off the south glass. The road is shut that way. Back you go. A shard buys a day, if you find one.'")
        if flats is not None:
            ctx.move(who, flats)
            scene(ctx, flats, who.name + " comes back down off the Salt Road onto the glass with two warden bows watching "
                  "every step.")
        ctx.emit("turned_back", target=who, reach=1, by=who.id)
        return
    if who.state.template and not who.state.road_known and f != "House Varrick":
        ctx.patch(who, {"road_known": True, "pinned_until": ctx.t + HOLD_AT_POST, "pinned_by": "the road wardens",
                        "pinned_why": "the road wardens hold you at their post until you give your name and business: "
                                      "talk to " + SERGEANT + ", or wait"})
        scene(ctx, road, "A spear comes across the road in front of " + who.name + ". The Guild's road wardens keep a post "
              "here where every road in the Reach meets: three spears, two bows and a sergeant with a ledger. " + SERGEANT +
              " does not get up. 'New face. Name, and your business on the Guild's road. Then you can go where you like.'")
    glass = shards(who)
    if len(glass) >= 2:
        toll(ctx, who, glass[0], sgt, road)
        scene(ctx, road, SERGEANT + " holds out a hand to " + who.name + ". 'Two shards and more off the glass. The Guild "
              "takes one at the post. Glass that leaves the Flats pays the road.'")

def on(ctx, event):
    st = story_of(ctx).state
    if not st.road:
        return
    k = event.kind
    p = event.payload
    if k in ["dawn", "dusk"]:
        for w in ctx.children(st.road, "creature"):
            if w.state.warden and not w.state.dead:
                ctx.patch(w, {"water": int(w.state.max_water or 10), "thirsty": None})
        return
    if k == "arrived":
        who = ctx.get(p.get("who"))
        if p.get("place") != st.road or who is None or who.state.warden or who.state.dead or who.parent is None:
            return
        if who.parent.id != st.road or not (who.state.faction or who.state.template):
            return
        arrive(ctx, st, who, bool(p.get("quiet")))
    elif k == "talked":
        sgt = sergeant(ctx)
        who = ctx.get(p.get("by"))
        if sgt is None or who is None or event.target != sgt.id:
            return
        if who.state.pinned_by == "the road wardens":
            ctx.patch(who, {"pinned_until": None, "pinned_by": None, "pinned_why": None})
            scene(ctx, sgt.parent, SERGEANT + " writes a line in the ledger and lifts the spear. 'Go on, then. Keep to the "
                  "road and keep your water close.'")
    elif k == "given":
        sgt = sergeant(ctx)
        it = ctx.get(p.get("item"))
        who = ctx.get(p.get("by"))
        if sgt is None or it is None or who is None or event.target != sgt.id or it.state.kind != "ember":
            return
        ctx.patch(who, {"road_paid_until": ctx.t + ROAD_DAY})
        scene(ctx, sgt.parent, SERGEANT + " weighs the shard and writes a line. 'A day's road. Nobody at the post stops you "
              "till this hour tomorrow.'")
