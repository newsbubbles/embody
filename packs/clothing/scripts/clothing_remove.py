use("clothing")

# remove: take off a garment you wear, once nothing is over it and nothing hangs from it.

def check(ctx):
    why = remove_check(ctx.actor, ctx.target)
    return why if why else True

def apply(ctx):
    it = ctx.target
    dur = start(ctx, ctx.actor, it, "remove")
    ctx.log(("you start taking off " + it.name + ", about " + str(int(dur)) + " s") if dur else ("you take off " + it.name))
    return {"item": it.name, "seconds": dur}
