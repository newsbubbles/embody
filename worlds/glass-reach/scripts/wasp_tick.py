# Glass wasps (Weeping Rock, 2026-11-11): a swarm over the child's well. No blade or ward stops a swarm. Every minute
# it is not smoked, everyone standing in its place loses a point of vigor, down to one and no further: the wasps drive
# you off, they do not put you down. Smoke (wasp_smoke) calms it for a day.

def tick(ctx):
    nest = ctx.self
    if nest.parent is None:
        return
    if nest.state.calm_until is not None and ctx.t < nest.state.calm_until:
        return
    if nest.state.calm_until is not None:
        ctx.patch(nest, {"calm_until": None, "description": nest.state.description_angry or nest.state.description})
        ctx.emit("scene", target=nest.parent, reach=1, text="The smoke is long gone. The wasps come back out over the basin, "
                 "a glittering haze, and the hum is back.")
    for c in ctx.children(nest.parent, "creature"):
        if c.state.beast or c.state.dead:
            continue
        v = int(c.state.vigor or 0)
        if v <= 1:
            continue
        ctx.patch(c, {"vigor": v - 1})
        ctx.emit("stung", target=c, reach=0, by=nest.id, vigor=v - 1)
        ctx.emit("scene", target=c, reach=0, text="The wasps find you: glass-bright, hot as sparks, at your neck and "
                 "hands. A point of vigor gone. Smoke drives them; standing here does not.")
