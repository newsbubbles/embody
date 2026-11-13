use("beasts")
# Cut a meal of meat (or carrion, once it has turned) from a carcass here, to carry and feed by hand: the way to keep
# a tamed hunter fed.

def check(ctx):
    b = ctx.target
    me = ctx.actor
    if b.parent is None or me.parent is None or b.parent.id != me.parent.id:
        return b.name + " is not here"
    if not b.state.dead:
        return b.name + " is alive"
    if int(b.state.meals or 0) <= 0 or not b.state.food:
        return "there is nothing left on " + b.name + " worth cutting"
    return True

def apply(ctx):
    b = ctx.target
    meat = "meat" in tags(b.state.food)
    ctx.patch(b, {"meals": int(b.state.meals) - 1})
    it = ctx.spawn("thing", ctx.actor, name="Meat" if meat else "Carrion",
                   state={"portable": True, "bulk": 0.5, "food": ["meat", "carrion"] if meat else ["carrion"], "feeds": 1,
                          "description": ("A cut of raw meat from " if meat else "A cut of turning meat from ") + b.name.lower() + "."})
    ctx.emit("butchered", target=b, reach=1, by=ctx.actor.id, item=it.id, left=int(b.state.meals))
