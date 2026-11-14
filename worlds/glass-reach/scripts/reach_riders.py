# The Riders' Hollow (Nate 2026-11-11): the end of chapter two was a count with nothing to go to. Dreyer's riders now
# have a place. It lies empty and hidden past the Dry Camp until the fires on the chapter's ninth night, when the
# riders ride in from the muster on the Hollow's own state: Captain Iven Strake with the paychest's key, six riders,
# the paychest (the glass Dreyer buys drifters with), the water cart (hauler fourteen's tank on a wheeled bed), Sel
# Amory tied in the picket line to drive it, and Dreyer's plan for the gate. Anyone not of the house who walks in while
# a rider is awake is ridden back out to the Bone Field; a creep past their watch takes stealth against 15. A failed
# pick, a lock broken, a spoil or a cut rope that is heard puts the doer out the same way. The cart fills at dawn from
# the house's wells unless it was spoiled. reach_chapter counts what is left of them at the moon.
WATCH_DC = 15  # a creep past the riders' watch: d20 + wits + stealth
CAUGHT = ["pick_failed", "lock_broken", "break_failed", "spoil_failed", "free_failed"]
HOME_AFTER = 1800  # a freed prisoner walks home this long after, if nobody ties them again

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

def watchers(ctx, hollow):
    out = []
    for c in ctx.children(hollow, "creature"):
        if c.state.rider and not c.state.down and not c.state.dead and not c.state.asleep:
            out.append(c)
    return out

def muster(ctx, st, hollow):
    m = hollow.state.muster or {}
    if st.riders_mustered or not m:
        return
    ids = {"riders_mustered": True, "riders_hollow": hollow.id}
    for p in m.get("people") or []:
        body = ctx.spawn("person", hollow, name=p["name"], state=dict(p["state"], post=hollow.id, water=10, max_water=10))
        for it in p.get("kit") or []:
            ctx.spawn(it["type"], body, name=it["name"], state=dict(it["state"]))
        if p["state"].get("captain"):
            ids["riders_captain"] = body.id
        if p["state"].get("bound"):
            ids["riders_prisoner"] = body.id
    for t in m.get("things") or []:
        it = ctx.spawn(t["type"], hollow, name=t["name"], state=dict(t["state"]))
        for c in t.get("holds") or []:
            ctx.spawn(c["type"], it, name=c["name"], state=dict(c["state"]))
        if t.get("key"):
            ids[t["key"]] = it.id
    ctx.patch(story_of(ctx), ids)
    ctx.patch(hollow, {"hidden": False, "known_to": None, "muster": None,
                       "description": m.get("description") or hollow.state.description})
    scene(ctx, hollow, m.get("scene") or "Riders come in off the south dunes and make camp.")
    ctx.emit("riders_mustered", target=ctx.root(), reach=-1, hollow=hollow.id)

def put_out(ctx, hollow, who, why):
    st = story_of(ctx).state
    bones = ctx.get(st.bones) if st.bones else None
    eyes = watchers(ctx, hollow)
    if bones is None or len(eyes) == 0 or who.parent is None or who.parent.id != hollow.id:
        return
    ctx.move(who, bones)
    ctx.patch(who, {"hp": max(0, int(who.state.hp or 0) - 1)})
    scene(ctx, hollow, eyes[0].name + " is on " + who.name + " before " + why + " is done: two riders, a horse's "
          "shoulder, and " + who.name + " is run out north into the dark at a stumble.")
    ctx.emit("scene", target=who, reach=0, text="They run you out past the rib with a rope's end across the back and leave "
             "you on the bones. You are not dead. They wanted you to know they could have.")
    ctx.emit("run_out", target=hollow, reach=1, by=eyes[0].id, who=who.id)

def on(ctx, event):
    story = story_of(ctx)
    st = story.state
    k = event.kind
    p = event.payload or {}
    hollow = by_name(ctx, "The Riders' Hollow")
    if hollow is None:
        return
    if k == "riders_fires" or k == "riders_muster":
        muster(ctx, st, hollow)
        return
    if not st.riders_mustered:
        return
    if k == "dawn":
        cart = ctx.get(st.riders_cart) if st.riders_cart else None
        if cart is not None and not cart.state.spoiled and cart.state.max_left:
            ctx.patch(cart, {"left": int(cart.state.max_left)})
        return
    if k == "freed_home":
        who = ctx.get(p.get("who"))
        home = ctx.get(who.state.home) if who is not None and who.state.home else None
        if who is None or home is None or who.state.bound or who.state.dead:
            return
        was = who.parent
        ctx.move(who, home)
        scene(ctx, was, who.name + " goes north at a limping run and does not look back.")
        scene(ctx, home, who.name + " comes in out of the south, rope-burned and thin, and asks for water before anything.")
        return
    if k == "arrived":
        who = ctx.get(p.get("who"))
        if p.get("place") != hollow.id or who is None or who.state.faction == "House Dreyer":
            return
        if len(watchers(ctx, hollow)) == 0:
            return
        if p.get("quiet"):
            roll = ctx.rand.roll("1d20") + int(who.state.wits or 0) + int((who.state.skills or {}).get("stealth") or 0)
            if roll >= WATCH_DC:
                ctx.emit("scene", target=who, reach=0, text="You come down into the Hollow on the broken step, between "
                         "the fires and the picket line. Nobody looks up.")
                ctx.emit("slipped_in", target=hollow, reach=0, by=who.id)
                return
        put_out(ctx, hollow, who, "they are halfway down the slope")
        return
    if k in CAUGHT:
        who = ctx.get(p.get("by"))
        if who is not None and who.state.faction != "House Dreyer":
            put_out(ctx, hollow, who, "it")
