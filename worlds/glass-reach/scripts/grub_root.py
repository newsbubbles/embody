# Grub a root out of the ground by hand (the beasts in the Reach, Nate 2026-11-13): it comes out of the place's own
# forage, so a tamer's handful is a meal the pack here goes without. Ten minutes on your knees in the thorn.
def check(ctx):
    place = ctx.actor.parent
    if ctx.target.parent is None or place is None or ctx.target.parent.id != place.id:
        return "it is not here"
    if ctx.actor.state.down:
        return "you are down"
    root = (place.state.forage or {}).get("root") or {}
    if int(root.get("left") or 0) <= 0:
        return "the beasts have rooted it bare; it grows back a little each dawn"
    if ctx.actor.state.carry and ctx.load(ctx.actor) + 1 > float(ctx.actor.state.carry):
        return "your hands are full: drop or put something first"
    return True

def apply(ctx):
    ctx.emit("scene", target=ctx.actor.parent, reach=1, text=ctx.actor.name + " kneels in the thorn and digs at the "
             "sand with both hands, after the grey roots.")

def finish(ctx):
    place = ctx.actor.parent
    forage = dict(place.state.forage or {})
    root = dict(forage.get("root") or {})
    if int(root.get("left") or 0) <= 0:
        ctx.log("the roots here are gone; nothing came up")
        return
    root["left"] = int(root.get("left") or 0) - 1
    forage["root"] = root
    ctx.patch(place, {"forage": forage})
    ctx.spawn("thing", ctx.actor, name="Glassthorn root", state={"portable": True, "bulk": 0, "food": "root", "feeds": 1,
              "description": "A fat grey root as long as your forearm, sweet-smelling and gritty with sand: what "
                             "thornbacks eat."})
    ctx.log("a root, " + str(root["left"]) + " more in the ground here today")
