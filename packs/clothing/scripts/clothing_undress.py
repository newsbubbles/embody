use("clothing")

# undress: take a garment off someone here, who has let you (let_dress) or is asleep, down or dead. It ends in your
# hands.

def item_of(ctx):
    return find_held(ctx.target, (ctx.params or {}).get("item"))

def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.id == me.id:
        return "to take off your own, remove it"
    if not (ctx.params or {}).get("item"):
        return "say what: params {\"item\": a garment they wear}"
    it = item_of(ctx)
    if it is None or not is_worn(t, it):
        return t.name + " wears no such thing"
    if not lets(t, me):
        return t.name + " has not let you undress them (they can: let_dress)"
    why = remove_check(t, it, me)
    return why if why else True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    it = item_of(ctx)
    dur = start(ctx, t, it, "remove", me)
    if dur:
        ctx.log("you start taking " + it.name + " off " + t.name + ", about " + str(int(dur)) + " s: stay beside them")
    else:
        ctx.log("you take " + it.name + " off " + t.name)
    return {"item": it.name, "who": t.name, "seconds": dur}
