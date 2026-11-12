def check(ctx):
    chore = ctx.target.state.chore
    if not chore:
        return "nothing to be done with that"
    if chore.get("done"):
        return "that is done already"
    need = chore.get("needs")
    if need:
        held = False
        for k in ctx.actor.children():
            if (k.name or "").lower() == str(need).lower():
                held = True
        if not held:
            return "you need the " + str(need).lower() + " for that"
    return True

def apply(ctx):
    chore = ctx.target.state.chore
    ctx.emit("worked", target=ctx.target, reach=1, by=ctx.actor.id, chore=chore.get("name"))
    ctx.log(chore.get("start") or "You set to it.")

def finish(ctx):
    chore = dict(ctx.target.state.chore or {})
    chore["done"] = True
    chore["by"] = ctx.actor.id
    ctx.patch(ctx.target, {"chore": chore, "description": chore.get("after") or ctx.target.state.description})
    ctx.emit("chore_done", target=ctx.target, reach=1, by=ctx.actor.id, chore=chore.get("name"))
    # listeners hear only what bubbles through them; the people in the room get told
    for p in ctx.peers(ctx.target.id, "creature"):
        if p.id != ctx.actor.id:
            ctx.emit("noticed", target=p, reach=0, of="chore_done", by=ctx.actor.id, thing=ctx.target.id, chore=chore.get("name"))
    ctx.log(chore.get("after") or "Done.")
