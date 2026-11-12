# The lime kiln (Nate 2026-11-12: lime from the Reach's own stone, not only the Guild's three sacks). Jory Flint chalks
# it beside the wall line and the works build it; then anyone standing at it may:
#   fire: lay a dressed stone and two bundles of glassthorn you carry into it and light it (ten minutes); it burns
#         six hours, smoking over the yard, one burn at a time
#   draw: rake out the sack of lime once the burn is done
# Glassthorn is cut in the Thornbrake (cut_thorn.py), through the postern in the yard's south wall.
BURN = 21600
FUEL = 2
LIME = {"portable": True, "kind": "lime", "bulk": 2,
        "description": "A sack of quicklime burned in the Hold's own kiln, tied with cord. It burns wet hands."}
LIT = ("A squat round kiln of dressed Scar stone beside the wall line, its stoke-hole glowing and a column of white "
       "glassthorn smoke standing up off it.")
COLD = ("A squat round kiln of dressed Scar stone beside the wall line, a stoke-hole at its foot and its throat black with "
        "old burning. Scar stone and glassthorn go in; lime comes out.")


def check(ctx):
    me = ctx.self
    a = ctx.actor
    if me.parent is None or a.parent is None or me.parent.id != a.parent.id:
        return "the kiln is not here"
    if a.state.down:
        return "you are down"
    if ctx.verb == "fire":
        if me.state.burning_until is not None:
            return "the kiln is already burning; draw the lime when the burn is done"
        if ctx.count(a, "dressed stone") < 1:
            return "the kiln burns Scar stone: carry a dressed stone to it (dress one from the rubble)"
        if ctx.count(a, "glassthorn") < FUEL:
            return ("it wants two bundles of glassthorn to burn hot enough; cut them in the Thornbrake, through the "
                    "postern in the yard's south wall, and by day")
        return True
    if me.state.burning_until is None:
        return "nothing is burning in the kiln: fire it with a dressed stone and two bundles of glassthorn"
    left = float(me.state.burning_until) - ctx.t
    if left > 0:
        return "the stone is still burning: about " + str(max(1, int(left // 3600 + 1))) + " hours more"
    if a.state.carry and ctx.load(a) + 2 > float(a.state.carry):
        return "your hands are full: a sack of lime is a two-hand load; drop or put something first"
    return True


def use(ctx, kind, n):
    left = n
    for it in ctx.actor.children():
        if left > 0 and it.state.kind == kind:
            k = min(left, ctx.count(it))
            ctx.destroy(ctx.split(it, k))
            left = left - k
    return left == 0


def apply(ctx):
    me = ctx.self
    a = ctx.actor
    if ctx.verb == "fire":
        ctx.emit("scene", target=a.parent, reach=1, text=a.name + " packs a block of Scar stone into the kiln's throat "
                 "and stuffs glassthorn under it.")
        return None
    ctx.patch(me, {"burning_until": None, "description": COLD})
    ctx.spawn("thing", a, name="Sack of lime", state=dict(LIME))
    ctx.emit("scene", target=a.parent, reach=1, text=a.name + " rakes the burned stone out of the kiln's foot, white and "
             "crumbling, and sacks it: lime.")
    return "A sack of lime, from the Hold's own stone. One sack lays one course."


def finish(ctx):
    me = ctx.self
    if ctx.verb != "fire":
        return
    if ctx.count(ctx.actor, "dressed stone") < 1 or ctx.count(ctx.actor, "glassthorn") < FUEL:
        ctx.log("the stone or the thorn left your hands before the kiln was lit")
        return
    use(ctx, "dressed stone", 1)
    use(ctx, "glassthorn", FUEL)
    ctx.patch(me, {"burning_until": ctx.t + BURN, "description": LIT})
    ctx.emit("scene", target=ctx.actor.parent, reach=1, text="The glassthorn catches with a crackle like breaking glass and "
             "the kiln roars. White smoke stands up over the yard, and it will burn six hours.")
    ctx.log("the kiln is lit: draw the lime in six hours")
