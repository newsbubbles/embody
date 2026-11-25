use("clothing")

# dress: put a garment you hold on someone here, who has let you (let_dress) or is asleep, down or dead. A helper
# takes the plain time, never the needs_help one.

def item_of(ctx):
    return find_held(ctx.actor, (ctx.params or {}).get("item"))

def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.id == me.id:
        return "to put something on yourself, wear it"
    if not (ctx.params or {}).get("item"):
        return "say what: params {\"item\": a garment you hold}"
    it = item_of(ctx)
    if it is None:
        return "you hold no such thing"
    if is_worn(me, it):
        return "you are wearing " + it.name + ": remove it first"
    if not lets(t, me):
        return t.name + " has not let you dress them (they can: let_dress)"
    why = wear_check(t, it, me)
    if why.startswith("no:"):
        return why[3:]
    return True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    it = item_of(ctx)
    ctx.patch(it, {"on": None, "stowed_at": None, "stowed_on": None, "in_hand": None})
    got = ctx.transfer(it, t)
    refresh(ctx, me)
    dur = start(ctx, t, got, "wear", me)
    if dur:
        ctx.log("you start dressing " + t.name + " in " + got.name + ", about " + str(int(dur)) + " s: stay beside them")
    else:
        ctx.log("you dress " + t.name + " in " + got.name)
    return {"item": got.name, "who": t.name, "seconds": dur}
