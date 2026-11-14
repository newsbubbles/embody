use("common")
QUIET = 120  # seconds of quiet before the tremor count drops by one

def bump(ctx, place, n, why):
    tremor = int(place.state.tremor or 0) + n
    ctx.patch(place, {"tremor": tremor, "tremor_t": ctx.t})
    if not place.state.settling:
        ctx.patch(place, {"settling": True})
        ctx.schedule(QUIET, "tremor_settles", target=place)
    if tremor >= 3 and not place.state.thresher_coming:
        ctx.patch(place, {"thresher_coming": True})
        ctx.emit("tremor", target=place, reach=1, tremor=tremor, why=why,
                 text="The sand under your feet hums. Something far down has turned toward the sound.")
        ctx.schedule(30, "thresher_surfaces", target=place)
    elif tremor == 2:
        ctx.emit("tremor", target=place, reach=1, tremor=tremor, why=why,
                 text="A grain-slide runs off the dune face for no reason you can see.")

def settle_tremor(ctx, place):
    # two minutes of quiet and the sand forgets one footfall; while the thresher is coming nothing settles
    since = ctx.t - float(place.state.tremor_t or 0)
    if place.state.thresher_coming:
        ctx.patch(place, {"settling": False})
        return
    if since < QUIET:
        ctx.schedule(QUIET - since, "tremor_settles", target=place)
        return
    tremor = max(0, int(place.state.tremor or 0) - 1)
    ctx.patch(place, {"tremor": tremor, "tremor_t": ctx.t})
    if tremor > 0:
        ctx.schedule(QUIET, "tremor_settles", target=place)
    else:
        ctx.patch(place, {"settling": False})
        ctx.emit("tremor", target=place, reach=1, tremor=0, why="quiet", text="The dune is still. Whatever listened has lost the thread.")

def safe_exit(ctx, place):
    for e in ctx.edges(place, "connects_to", "out"):
        x = ctx.get(e["target"])
        if x is not None and not x.state.deep_sand and not x.state.hidden:
            return x
    return None

def surface(ctx, place):
    worms = ctx.find(type="thresher", limit=1)
    if not worms:
        return
    worm = worms[0]
    ctx.move(worm, place)
    ctx.emit("scene", target=place, reach=1, text="The dune splits. The Thresher comes up through the glass like a ship surfacing, mouth first.")
    safe = safe_exit(ctx, place)
    for c in ctx.children(place, "creature"):
        if c.type == "thresher" or c.state.dead:
            continue
        roll = ctx.rand.roll("1d20")
        mod = bonus(c, "survival")
        total = roll + mod
        ok = total >= 13
        ctx.emit("checked", target=c, reach=1, by=c.id, skill="survival", roll=roll, mod=mod, total=total, dc=13, success=ok, margin=total - 13)
        if not ok:
            hp = int(c.state.hp or 0) - 4
            ctx.patch(c, {"hp": hp, "braced": False})
            ctx.emit("hit", target=c, reach=1, by=worm.id, dmg=4, weapon="the Thresher", attack=0, defence=0, hp=hp)
            settle(ctx, c, worm.id)
        if safe is not None:
            ctx.move(c, safe)
            ctx.emit("arrived", target=safe, reach=1, who=c.id, place=safe.id, quiet=True, fled=place.id)
            ctx.emit("scene", target=safe, reach=0, text=(c.name + " scrambles onto the rock, " + ("untouched." if ok else "bleeding, thrown clear by the first pass.")))
    ctx.patch(place, {"tremor": 0, "thresher_coming": False, "settling": False, "tremor_t": ctx.t})
    ctx.schedule(10, "thresher_sinks", target=place)

def on(ctx, event):
    k = event.kind
    if k == "arrived":
        place = ctx.get(event.payload.get("place"))
        if place is None or not place.state.deep_sand or event.payload.get("quiet"):
            return
        who = ctx.get(event.payload.get("who"))
        if who is not None and who.type == "thresher":
            return
        bump(ctx, place, 1, "footfall")
    elif k == "harvested":
        vein = ctx.get(event.target)
        if vein is not None and vein.parent is not None and vein.parent.state.deep_sand:
            bump(ctx, vein.parent, 2, "harvest")
    elif k == "tremor_settles":
        place = ctx.get(event.target)
        if place is not None:
            settle_tremor(ctx, place)
    elif k == "thresher_surfaces":
        place = ctx.get(event.target)
        if place is not None:
            surface(ctx, place)
    elif k == "thresher_sinks":
        worms = ctx.find(type="thresher", limit=1)
        if worms and worms[0].state.home:
            ctx.move(worms[0], worms[0].state.home)
            ctx.emit("scene", target=event.target, reach=1, text="The sand closes over the Thresher. The dune is a dune again.")
