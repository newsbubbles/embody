use("clothing")

# adjust: one of the garment's ways (its `modes`): hood_up, open, visor_down, sleeves_rolled... params {"how": name,
# "on": true or false}; without "on" it toggles.

def how_of(ctx):
    return lower((ctx.params or {}).get("how")).replace(" ", "_")

def check(ctx):
    it = ctx.target
    if not is_worn(ctx.actor, it):
        return "you are not wearing " + it.name
    sp = spec(it)
    if not sp["modes"]:
        return it.name + " has nothing to adjust"
    if how_of(ctx) not in sp["modes"]:
        return "say how: params {\"how\": " + " or ".join(list(sp["modes"].keys())) + "}"
    return True

def apply(ctx):
    it = ctx.target
    sp = spec(it)
    how = how_of(ctx)
    now = modes_on(it, sp)
    p = ctx.params or {}
    want = (how not in now) if p.get("on") is None else bool(p.get("on"))
    if want and how not in now:
        now.append(how)
    if not want:
        now = [m for m in now if m != how]
    ctx.patch(it, {"modes_on": now if now else None})
    refresh(ctx, ctx.actor)
    ctx.emit("adjusted", target=ctx.actor, reach=1, by=ctx.actor.id, item=it.id, name=it.name, how=how, on=want)
    ctx.log(it.name + ": " + how.replace("_", " ") + (" now" if want else " no longer"))
    return {"item": it.name, "how": how, "on": want}
