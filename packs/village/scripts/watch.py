def check(ctx):
    here = ctx.actor.parent
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            if ctx.target.state.hidden and ctx.target.state.known_to != ctx.actor.state.faction:
                return "you know of no such place"
            return True
    return "you cannot see there from here"

def apply(ctx):
    # look into the next place without stepping into it: who is there and what, this moment; only you hear of it
    who = [c.name for c in ctx.children(ctx.target, "creature") if not c.state.hidden]
    things = [t.name for t in ctx.children(ctx.target, "thing") if not t.state.hidden]
    ctx.emit("watched", target=ctx.actor, reach=0, place=ctx.target.id, who=who, things=things)
    ctx.log(ctx.target.name + ": " + (", ".join(who) if who else "nobody"))
    return {"place": ctx.target.id, "who": who, "things": things}
