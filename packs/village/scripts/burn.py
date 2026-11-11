def fire_near(ctx):
    # a fire to burn it in: the place itself, something burning here, or a lit light in hand
    me = ctx.actor
    here = me.parent
    if here is not None and (here.state.fire or here.state.lit):
        return here
    for it in me.children():
        if it.id != ctx.target.id and it.state.lit:
            return it
    if here is not None:
        for it in ctx.children(here):
            if it.id != ctx.target.id and (it.state.fire or it.state.lit):
                return it
    return None

def check(ctx):
    it = ctx.target
    holder = it.parent
    here = ctx.actor.parent
    if not it.state.burnable:
        return "it will not burn"
    if holder is None or (holder.id != ctx.actor.id and (here is None or holder.id != here.id)):
        return "it is not in your hands or here"
    if fire_near(ctx) is None:
        return "there is no fire here: burn it at a hearth or a fire, or with a lit lamp in your hand"
    return True

def apply(ctx):
    # gone for good: whoever read it keeps what it said, and the room sees only that it burned
    it = ctx.target
    fire = fire_near(ctx)
    here = ctx.actor.parent
    name = it.name
    for c in it.children():
        ctx.move(c, here)
    ctx.emit("burned", target=here, reach=1, by=ctx.actor.id, thing=it.id, name=name, fire=fire.id)
    ctx.emit("scene", target=here, reach=1,
             text=ctx.actor.name + " holds the " + name.lower() + " to the " + (fire.name.lower() if fire.id != here.id else "fire") +
                  " until it is ash.")
    ctx.destroy(it)
    ctx.log("the " + name.lower() + " is ash")
