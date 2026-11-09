def ferryman_here(ctx):
    for p in ctx.actor.peers():
        if p.state.role == "ferryman" and not p.state.asleep:
            return p
    return None

def check(ctx):
    if ctx.actor.parent.id != ctx.target.parent.id:
        return "the raft is not here"
    if ferryman_here(ctx) is None:
        return "nobody here knows the current; the raft stays moored"
    here = ctx.actor.parent
    if here.state.fog:
        lanterns = [l for l in ctx.children(here) if l.state.lit]
        lanterns = lanterns + [l for l in ctx.actor.children() if l.state.lit]
        if not lanterns:
            return "the fog hides the far bank"
    return True

def apply(ctx):
    ctx.emit("casting_off", target=ctx.actor.parent, reach=1, who=ctx.actor.id)
    ctx.log("Tam pushes off. The crossing takes a while.")

def other_bank(ctx):
    here = ctx.actor.parent.id
    banks = ctx.self.state.banks or []
    for b in banks:
        if b != here:
            return ctx.get(b)
    return ctx.get(ctx.self.state.far_bank)

def finish(ctx):
    far = other_bank(ctx)
    here = ctx.actor.parent
    tam = ferryman_here(ctx)
    ctx.move(ctx.actor, far)
    if tam:
        ctx.move(tam, far)
    # the dog you fed and anyone following you ride along; the raft itself ends up on that side
    for p in ctx.children(here):
        if p.state.friend == ctx.actor.id or p.state.follows == ctx.actor.id:
            ctx.move(p, far)
    ctx.move(ctx.self, far)
    ctx.emit("crossed", target=far, reach=-1, who=ctx.actor.id, from_bank=here.id)
