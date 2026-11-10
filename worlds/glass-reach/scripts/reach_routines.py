# The Reach's own routines: what keeps it alive when nobody is playing, and what a player can get in the way of.
#
#   keth_run   at dusk, while the truce holds: a Keth bearer carries water from the Deepwell up the ridge, across the
#              Flats (the broken step, quiet), down the Salt Road and through the yard to the Hold, tips it into the
#              Keth jars by the dry cistern, and walks home. A leg every LEG world seconds. A bearer who is down, dead,
#              yielded or cowed stops where they stand; what they carried is set down there, for whoever is there.
#   crawler    at dawn: a Guild crawler comes up the Salt Road. It leaves the Hold's ration at the gate while somebody
#              holds the Hold for the Crown, and tops up the Landing's casks while Ossa is there on her feet to tally.
#              No Ossa at the tally post, no crawler.
#
# Each run is one event with a `leg`, scheduled by the one before it, so a run in progress is a timer anyone with
# the owner's eye can see, and the run itself is in the log, arrival by arrival.

KETH_WATER = 8      # draws a bearer carries
KETH_JARS = 12      # what the Keth jars in the Hold hold
HOLD_RATION = 8     # the Guild's ration cask at the gate is topped up to this
GUILD_CASKS = 6     # the Landing's casks are topped up to this
LEG = 1800          # world seconds a leg takes (half an hour of the world's day)
OUT = ["ridge", "flats", "road", "yard", "hold"]   # from the Deepwell; home is the same road back

def scene(ctx, place, text):
    ctx.emit("scene", target=place, reach=1, text=text)

def stopped(who):
    st = who.state
    return st.dead or st.down or st.yielded or st.cowed_by

def put_down(ctx, who, left):
    # the yoke comes off where the run stopped: water for whoever is standing there
    here = who.parent
    ctx.spawn("thing", here, "Keth jars, set down", state={"portable": False, "water_source": True, "left": left,
              "description": "A bearer's yoke and two sealed jars, set down in a hurry. Keth water."})
    ctx.patch(who, {"carrying": 0, "run": None})
    scene(ctx, here, "The Keth bearer's yoke comes down where they stand. The jars are full, and nobody is carrying them now.")

def walk(ctx, who, place):
    ctx.move(who, place)
    ctx.emit("arrived", target=place, reach=-1, who=who.id, place=place.id, quiet=bool(place.state.deep_sand))

def keth_run(ctx, st, leg, back):
    who = ctx.get(st.bearer) if st.bearer else None
    if who is None or who.state.dead:
        return
    if leg == 0:
        if not st.truce or ctx.root().state.story == "lost" or who.state.run or stopped(who):
            return
        if who.parent is None or who.parent.id != st.deepwell:
            return
        ctx.patch(who, {"carrying": KETH_WATER, "run": "out"})
        scene(ctx, st.ridge, "A Keth bearer comes up out of the rock with two jars on a yoke and starts down toward the Flats. Water for the Hold, by the terms.")
        ctx.schedule(LEG, "keth_run", target=ctx.root(), leg=1)
        return
    if stopped(who):
        if int(who.state.carrying or 0) > 0:
            put_down(ctx, who, int(who.state.carrying))
        else:
            ctx.patch(who, {"run": None})
        return
    route = list(reversed(OUT[:-1])) + ["deepwell"] if back else OUT
    place = ctx.get(st.get(route[leg - 1]))
    walk(ctx, who, place)
    if not back and leg == len(OUT):
        jars = ctx.get(st.keth_jars)
        if jars is not None:
            ctx.patch(jars, {"left": min(KETH_JARS, int(jars.state.left or 0) + int(who.state.carrying or 0))})
        ctx.patch(who, {"carrying": 0, "run": "home"})
        scene(ctx, st.hold, "The Keth bearer sets the yoke down by the dry cistern and pours both jars into the Keth's own. Nobody thanks them. They do not wait to be thanked.")
        ctx.schedule(LEG, "keth_run", target=ctx.root(), leg=1, back=True)
    elif back and leg == len(route):
        ctx.patch(who, {"run": None})
    else:
        ctx.schedule(LEG, "keth_run", target=ctx.root(), leg=leg + 1, back=back)

def crawler(ctx, st):
    ossa = ctx.get(st.ossa)
    landing = ctx.get(st.landing)
    if ossa is None or ossa.state.dead or ossa.state.down or ossa.parent is None or ossa.parent.id != st.landing:
        scene(ctx, st.road, "A Guild crawler grinds up the Salt Road at first light, finds nobody at the tally post, and grinds back the way it came.")
        return
    lost = ctx.root().state.story == "lost"
    ration = ctx.get(st.hold_ration)
    if ration is not None and not lost and int(ration.state.left or 0) < HOLD_RATION:
        ctx.patch(ration, {"left": HOLD_RATION})
        scene(ctx, st.hold, "A Guild crawler stops at the gate long enough to roll the Hold's ration cask off its bed. The writ pays for it; the Guild carries for whoever holds the gate.")
    for c in ctx.children(landing, "thing"):
        if c.state.water_source and c.state.left is not None and int(c.state.left) < GUILD_CASKS:
            ctx.patch(c, {"left": GUILD_CASKS})
    scene(ctx, st.landing, "A Guild crawler puts down on the pan at first light. Ossa walks its length with the ledger and chalks the casks full.")

def on(ctx, event):
    story = ctx.find(type="story", limit=1)
    if not story:
        return
    st = story[0].state
    p = event.payload or {}
    if event.kind == "keth_run":
        keth_run(ctx, st, int(p.get("leg") or 0), bool(p.get("back")))
    elif event.kind == "crawler":
        crawler(ctx, st)
