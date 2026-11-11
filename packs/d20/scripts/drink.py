use("common")
def check(ctx):
    if ctx.target.parent.id != ctx.actor.id and ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not within reach"
    if not endless(ctx.target) and int(ctx.target.state.left or 0) <= 0:
        return "it is empty"
    if ctx.actor.state.dead:
        return "the dead do not thirst"
    return True

def apply(ctx):
    me = ctx.actor
    if endless(ctx.target):
        water = min(int(me.state.max_water or 10), int(me.state.water if me.state.water is not None else 10) + 4)
        changes = {"water": water}
        if water > 3 and me.state.thirsty:
            changes["thirsty"] = False
        ctx.patch(me, changes)
        ctx.emit("drank", target=ctx.target, reach=1, by=me.id, water=water)
        revive(ctx, me, water)
        ctx.log("water " + str(water) + "; it does not run dry")
        return
    left = int(ctx.target.state.left or 0) - 1
    water = min(int(me.state.max_water or 10), int(me.state.water if me.state.water is not None else 10) + 4)
    changes = {"water": water}
    if water > 3 and me.state.thirsty:
        changes["thirsty"] = False
    ctx.patch(me, changes)
    ctx.patch(ctx.target, {"left": left, "description": (ctx.target.state.description_empty or "Empty.") if left <= 0 else ctx.target.state.description})
    ctx.emit("drank", target=ctx.target, reach=1, by=me.id, left=left, water=water)
    revive(ctx, me, water)
    ctx.log("water " + str(water) + ", " + str(left) + " left in it")
