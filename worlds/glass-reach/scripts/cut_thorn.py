# Glassthorn in the Thornbrake: cut a bundle from the stand (half an hour; the spines are glass and they bite). It
# burns white-hot, which is what the lime kiln wants (kiln.py): two bundles a burn. The stand does not grow back
# before the moon.
def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    if int(ctx.target.state.bundles or 0) <= 0:
        return "the stand is cut back to the stumps; nothing left worth the cutting"
    if ctx.actor.state.down:
        return "you are down"
    if ctx.actor.state.carry and ctx.load(ctx.actor) + 1 > float(ctx.actor.state.carry):
        return "your hands are full: drop or put something first"
    return True

def apply(ctx):
    ctx.emit("scene", target=ctx.actor.parent, reach=1, text=ctx.actor.name + " starts cutting glassthorn, carefully, "
             "the glazed spines ringing as they fall.")

def finish(ctx):
    left = int(ctx.target.state.bundles or 0) - 1
    ctx.patch(ctx.target, {"bundles": left})
    ctx.spawn("thing", ctx.actor, name="Glassthorn bundle", state={"kind": "glassthorn", "portable": True, "bulk": 1,
              "description": "An armful of cut glassthorn bound with its own runners, the spines glazed to glass. It "
                             "burns white-hot."})
    ctx.log("a bundle of glassthorn, " + str(left) + " more on the stand")
