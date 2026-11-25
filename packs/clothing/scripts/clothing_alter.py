use("clothing")

# alter: let a garment out or take it in one size (params {"to": "l"}), with a sewing tool in hand (a thing whose
# state says tool "sewing"). Half an hour; done if you still have both when the time is out. A needle does not refit
# armour.

def tool_of(me):
    for c in me.children():
        if c.state.tool == "sewing":
            return c
    return None

def why_not(ctx):
    me = ctx.actor
    it = ctx.get(ctx.target.id)
    if it is None or it.parent is None or it.parent.id != me.id:
        return "you do not have " + ctx.target.name
    if on_me(me, it) and (it.state.worn or it.state.donning):
        return "you are wearing " + it.name + ": take it off first"
    if tool_of(me) is None:
        return "you need a sewing tool in hand (needle and thread, a sewing kit)"
    sp = spec(it)
    if sp["fit"] == "exact":
        return "a needle does not refit armour: that is a smith's work"
    if it.state.adjustable:
        return it.name + " adjusts itself: it fits anyone"
    to = lower((ctx.params or {}).get("to"))
    if to not in SIZES:
        return "say the size: params {\"to\": " + " or ".join(SIZES) + "}"
    have = lower(it.state.size) or "m"
    if have not in SIZES:
        have = "m"
    d = SIZES.index(to) - SIZES.index(have)
    if d == 0:
        return it.name + " is already " + to.upper()
    if d > 1 or d < -1:
        return "one size at a time: " + it.name + " is " + have.upper()
    return ""

def check(ctx):
    why = why_not(ctx)
    return why if why else True

def apply(ctx):
    ctx.log("you unpick the seams of " + ctx.target.name + ": half an hour, keep it and the needle with you")

def finish(ctx):
    why = why_not(ctx)
    if why:
        ctx.log("the alteration stopped: " + why)
        return
    it = ctx.get(ctx.target.id)
    to = lower(ctx.params.get("to"))
    ctx.patch(it, {"size": to})
    ctx.emit("altered", target=ctx.actor, reach=1, by=ctx.actor.id, item=it.id, name=it.name, size=to)
    ctx.log(it.name + " is " + to.upper() + " now")
