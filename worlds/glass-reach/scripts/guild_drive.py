# Driving a Guild hauler: the hauler is a place with one way in and out, and driving it moves that way to another
# stop on the road. Whoever is aboard rides along. A quarter hour of the clock on the road between stops, loud the
# whole way; never onto the glass, where the Thresher hears a crawler a league off.

def hauler_of(ctx):
    h = ctx.target.parent
    if h is None or not h.state.hauler:
        return None
    return h

def stop_named(ctx, h, want):
    want = str(want or "").lower()
    for name in h.state.stops or []:
        if name.lower() == want or (len(want) >= 4 and want in name.lower()):
            for e in ctx.find(name=name, limit=5):
                if e.name == name:
                    return e
    return None

def check(ctx):
    if not ctx.target.state.wheel:
        return "that is not a hauler's wheel: stand in a hauler and drive its wheel"
    h = hauler_of(ctx)
    if h is None or ctx.actor.parent is None or ctx.actor.parent.id != h.id:
        return "climb into the hauler first: the wheel is in its cab"
    if ctx.actor.state.down:
        return "you are down"
    if not ctx.params or not ctx.params.get("to"):
        return "say where: params {\"to\": one of " + ", ".join(h.state.stops or []) + "}"
    dest = stop_named(ctx, h, ctx.params.get("to"))
    if dest is None:
        return "the hauler keeps to the road: drive it to one of " + ", ".join(h.state.stops or [])
    if dest.id == h.state.at:
        return "the hauler already stands at " + dest.name
    return True

def apply(ctx):
    h = hauler_of(ctx)
    here = ctx.get(h.state.at)
    if here is not None:
        ctx.emit("scene", target=here, reach=1, text=h.name + " coughs awake, its eight woven wheels bite, and it grinds "
                 "out onto the road with " + ctx.actor.name + " at the wheel.")
    ctx.emit("driving", target=h, reach=1, by=ctx.actor.id, to=ctx.params.get("to"))

def finish(ctx):
    h = hauler_of(ctx)
    if h is None:
        return
    dest = stop_named(ctx, h, ctx.params.get("to"))
    if dest is None:
        return
    was = ctx.get(h.state.at)
    if was is not None:
        ctx.unlink(h, was, "connects_to")
        ctx.unlink(was, h, "connects_to")
    ctx.link(h, dest, "connects_to")
    ctx.link(dest, h, "connects_to")
    ctx.patch(h, {"at": dest.id})
    if dest.pos is not None:
        ctx.set_pos(h, dest.pos)
    ctx.emit("scene", target=dest, reach=1, text=h.name + " grinds in off the road in a cloud of salt dust and stands "
             "ticking, its engine cooling, " + ctx.actor.name + " at the wheel.")
    ctx.emit("hauled", target=h, reach=1, by=ctx.actor.id, to=dest.id, frm=was.id if was is not None else None)
    ctx.log(h.name + " stands at " + dest.name)
