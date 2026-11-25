use("clothing")

# wear: put on a garment you have. It takes its time (don_s, else by layer), and alone a needs_help garment takes
# three times as long: someone can dress you in it instead.

def check(ctx):
    why = wear_check(ctx.actor, ctx.target)
    if why.startswith("no:"):
        return why[3:]
    return True

def apply(ctx):
    it = ctx.target
    dur = start(ctx, ctx.actor, it, "wear")
    if dur:
        tip = ": with help it goes faster (someone can dress you in it)" if spec(it)["needs_help"] else ""
        ctx.log("you start putting on " + it.name + ", about " + str(int(dur)) + " s" + tip)
    else:
        ctx.log("you put on " + it.name)
    return {"item": it.name, "seconds": dur}
