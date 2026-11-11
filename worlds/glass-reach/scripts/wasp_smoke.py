# Smoking the wasps (Weeping Rock, 2026-11-11): burn one glassthorn smudge (a thing whose kind is smudge, one of a
# stack) under the nest and the swarm goes sleepy and still for a day. The Keth keep smudge at the Deepwell.
CALM = 86400

def smudge(ctx):
    for it in ctx.actor.children():
        if it.state.kind == "smudge":
            return it
    return None

def check(ctx):
    if not ctx.target.state.swarm:
        return "there is nothing here to smoke"
    if ctx.target.state.calm_until is not None and ctx.t < ctx.target.state.calm_until:
        return "they are already sleepy with smoke"
    if smudge(ctx) is None:
        return "you need something that smokes: a glassthorn smudge (the Keth keep them at the Deepwell)"
    return True

def apply(ctx):
    it = smudge(ctx)
    n = ctx.count(it)
    if n > 1:
        ctx.patch(it, {"count": n - 1})
    else:
        ctx.destroy(it)
    nest = ctx.target
    ctx.patch(nest, {"calm_until": ctx.t + CALM, "description": nest.state.description_calm or nest.state.description})
    ctx.emit("smoked", target=nest, reach=1, by=ctx.actor.id)
    ctx.emit("scene", target=nest.parent, reach=1, text=ctx.actor.name + " lights a glassthorn smudge and holds it up "
             "under the nest. Thick grey smoke rolls up the cleft, and the hum drops to a drowse. The wasps settle on "
             "the rock like spilled glass and stay there.")
