# Spoiling water (the Riders' Hollow, 2026-11-11): cut the seams of a tank or foul it with salt and sand. Two minutes,
# quiet if the hand is steady: d20 + wits + stealth against the water's `spoil_dc`, rolled when the time is out and only
# if you are still there. Spoiled water stays spoiled: it is empty, and nothing fills it again. A fail is heard.

def check(ctx):
    w = ctx.target
    if not w.state.spoil_dc:
        return "that water cannot be spoiled by hand"
    if w.state.spoiled:
        return "it is already spoiled"
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    ctx.patch(ctx.target, {"spoiling": {"who": ctx.actor.id, "at": ctx.actor.parent.id}})
    ctx.log("you set to work on " + ctx.target.name + "; stay here until it is done")

def finish(ctx):
    w = ctx.get(ctx.target.id)
    me = ctx.actor
    if w is None:
        return
    at = (w.state.spoiling or {}).get("at") if (w.state.spoiling or {}).get("who") == me.id else None
    ctx.patch(w, {"spoiling": None})
    if at is None or me.parent is None or me.parent.id != at:
        ctx.log("you left " + w.name + " before it was done")
        return
    roll = ctx.rand.roll("1d20")
    mod = int(me.state.wits or 0) + int((me.state.skills or {}).get("stealth") or 0)
    total = roll + mod
    dc = int(w.state.spoil_dc)
    if total >= dc:
        ctx.patch(w, {"spoiled": True, "left": 0, "water_source": False,
                      "description": w.state.description_spoiled or ("Spoiled. " + str(w.state.description or ""))})
        ctx.emit("spoiled", target=w, reach=0, by=me.id, roll=roll, mod=mod, total=total, dc=dc)
        ctx.emit("scene", target=me, reach=0, text="It is done before anyone looks your way. What was water is not, now.")
        ctx.log("spoil: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": spoiled")
        return
    ctx.emit("spoil_failed", target=w.parent, reach=1, by=me.id, thing=w.id, roll=roll, mod=mod, total=total, dc=dc)
    ctx.emit("scene", target=w.parent, reach=1, text="Something scrapes at " + w.name.lower() + ": " + me.name + " is at it.")
    ctx.log("spoil: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": heard")
