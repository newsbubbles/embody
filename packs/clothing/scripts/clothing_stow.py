use("clothing")

# stow: hang a thing you have at a position (params {"at": "hip_left"}), from a worn carrier there (a belt, a baldric)
# or by its own strap; {"at": "away"} puts it back in your pack or pocket, out of sight.

AWAY = ["away", "pack", "loose", "pocket"]

def at_of(ctx):
    return lower((ctx.params or {}).get("at")).replace(" ", "_").replace("-", "_")

def carriers_for(pos):
    return [k.replace("_", " ") for k, v in GARMENTS.items() if pos in (v.get("mounts") or [])]

def check(ctx):
    me = ctx.actor
    it = ctx.target
    if it.parent is None or it.parent.id != me.id:
        return "you do not have " + it.name
    if is_worn(me, it) or (it.state.donning and on_me(me, it)):
        return "you are wearing " + it.name + ": remove it first"
    at = at_of(ctx)
    where = stows_of(it)
    if at in AWAY:
        if not on_me(me, it):
            return it.name + " is already put away"
        return True
    if not at:
        return "say where: params {\"at\": " + " or ".join(where + ["away"]) + "}"
    if at not in POSITIONS:
        return "there is no " + at.replace("_", " ") + " to hang it at: one of " + ", ".join(POSITIONS) + ", or away"
    if POSITION_NEEDS[at] not in plan_of(me):
        return "a " + species_of(me) + " has no " + POSITION_NEEDS[at] + " to hang it at"
    if at not in where:
        if not where:
            return it.name + " does not hang anywhere: carry it loose (away) or in your hands (hold)"
        return it.name + " does not hang at the " + LABELS[at] + ": it goes at the " + join_and([LABELS[p] for p in where])
    others = [c for c in at_position(me, at) if c.id != it.id]
    if len(others) >= POSITION_ROOM.get(at, 1):
        return "your " + LABELS[at] + " already carries " + join_and([c.name for c in others])
    if not mount_for(me, it, at):
        ks = carriers_for(at)
        what = join_or(["a " + k for k in ks]) if ks else "something that holds it there"
        return "nothing to hang it from at the " + LABELS[at] + ": wear " + what + (", or give it a strap" if at in STRAP_POSITIONS else "")
    return True

def apply(ctx):
    me = ctx.actor
    it = ctx.target
    at = at_of(ctx)
    if at in AWAY:
        ctx.patch(it, {"on": None, "stowed_at": None, "stowed_on": None, "in_hand": None})
        at = "away"
    else:
        ctx.patch(it, {"on": me.id, "stowed_at": at, "stowed_on": mount_for(me, it, at), "in_hand": None})
    refresh(ctx, me)
    ctx.emit("stowed", target=me, reach=1, by=me.id, item=it.id, name=it.name, at=at)
    ctx.log(it.name + (" put away" if at == "away" else " now hangs at your " + LABELS[at]))
    return {"item": it.name, "at": at}
