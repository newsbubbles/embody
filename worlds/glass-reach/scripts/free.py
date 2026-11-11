# Cutting someone loose (the Riders' Hollow, 2026-11-11): a person whose state is `bound` is tied and goes nowhere.
# A minute at the knots, then d20 + wits + stealth against their `free_dc`, rolled when the time is out and only if you
# are still there. Freed, they go home (`home`) on their own a half hour later unless someone ties them again. A fail
# is heard.

def check(ctx):
    who = ctx.target
    if not who.state.bound:
        return who.name + " is not tied"
    if who.id == ctx.actor.id:
        return "you cannot reach your own knots"
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    ctx.patch(ctx.target, {"freeing": {"who": ctx.actor.id, "at": ctx.actor.parent.id}})
    ctx.log("you go to work on " + ctx.target.name + "'s knots; stay here until they give")

def finish(ctx):
    who = ctx.get(ctx.target.id)
    me = ctx.actor
    if who is None:
        return
    at = (who.state.freeing or {}).get("at") if (who.state.freeing or {}).get("who") == me.id else None
    ctx.patch(who, {"freeing": None})
    if at is None or me.parent is None or me.parent.id != at:
        ctx.log("you left " + who.name + " still tied")
        return
    roll = ctx.rand.roll("1d20")
    mod = int(me.state.wits or 0) + int((me.state.skills or {}).get("stealth") or 0)
    total = roll + mod
    dc = int(who.state.free_dc or 10)
    if total >= dc:
        ctx.patch(who, {"bound": False, "description": who.state.description_free or who.state.description})
        ctx.emit("freed", target=who, reach=0, by=me.id, roll=roll, mod=mod, total=total, dc=dc)
        ctx.emit("scene", target=me, reach=0, text="The last knot gives. " + who.name + " rubs both wrists and whispers, "
                 "'North. I know the way. Go.'")
        if who.state.home:
            ctx.schedule(1800, "freed_home", target=ctx.root(), payload={"who": who.id})
        ctx.log("free: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": loose")
        return
    ctx.emit("free_failed", target=who.parent, reach=1, by=me.id, who=who.id, roll=roll, mod=mod, total=total, dc=dc)
    ctx.emit("scene", target=who.parent, reach=1, text=who.name + " grunts as a knot jerks tight: " + me.name + " is at the rope.")
    ctx.log("free: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": heard")
