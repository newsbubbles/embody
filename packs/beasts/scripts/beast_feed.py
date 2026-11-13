use("beasts")
# Feed a beast here from your hand: an item whose `food` its diet eats gives it `feeds` meals, up to full; a full
# beast still takes it from a hand, as a treat. The day you feed it counts toward taming it (gentle) and, if it is yours, toward its loyalty.

def check(ctx):
    b = ctx.target
    me = ctx.actor
    if b.parent is None or me.parent is None or b.parent.id != me.parent.id:
        return b.name + " is not here"
    if b.state.dead:
        return b.name + " is dead"
    it = item_in_hand(ctx, me, ctx.params.get("item"))
    if it is None:
        held = [c.name for c in me.children() if c.state.food]
        return "feed it what? name something you hold: item=" + (", ".join(held) if held else "(you hold no food)")
    sp = species_of(ctx, b)
    eats = diet(b, sp)
    if not [t for t in tags(it.state.food) if t in eats]:
        return b.name + " sniffs the " + it.name.lower() + " and turns away: it eats " + (", ".join(eats) if eats else "nothing you could give it")
    return True

def apply(ctx):
    b = ctx.target
    me = ctx.actor
    it = item_in_hand(ctx, me, ctx.params.get("item"))
    sp = species_of(ctx, b)
    mx = int(sv(b, sp, "fed_max", 3))
    fed = min(mx, int(b.state.fed or 0) + int(it.state.feeds or 1))
    fed_by = dict(b.state.fed_by or {})
    fed_by[me.id] = today(ctx)
    ctx.patch(b, {"fed": fed, "fed_by": fed_by, "hungry": False, "hungry_days": 0})
    what = it.name
    portions = it.state.portions
    if portions is not None and int(portions) > 1:
        ctx.patch(it, {"portions": int(portions) - 1})
    elif ctx.count(it) > 1:
        ctx.destroy(ctx.split(it, 1))
    else:
        ctx.destroy(it)
    ctx.emit("fed", target=b, reach=1, by=me.id, item=what, fed=fed)
    ctx.log(b.name + " eats: fed " + str(fed) + " of " + str(mx))
