use("common")
def on(ctx, event):
    # installed on the root: the dead do nothing, the down do little, a brace lasts until your next deed and so does sleep
    a = ctx.get(event.actor) if event.actor else None
    if a is None:
        return
    verb = event.payload.get("verb")
    if event.kind == "before_act":
        if a.state.dead:
            ctx.reject("the dead do nothing", "this seat is over; join another or watch")
        if a.state.down and verb not in ["yield", "drink", "crawl"]:
            ctx.reject("you are down: you can yield, drink or crawl", "act('yield', <who>), act('drink', <skin>) or act('crawl', <place>)")
    elif event.kind == "act":
        if a.state.braced and verb != "brace":
            ctx.patch(a, {"braced": False})
        if a.state.asleep and verb not in ["sleep", "wake"]:
            # a deed wakes the one who does it
            ctx.patch(a, {"asleep": False})
            ctx.emit("woke", target=a, reach=1, by=a.id, why="rose")
        # heavy deeds cost water (the table in common); a fight's blows pay in strike, works labour in its own tick
        if verb in ["go", "crawl"]:
            here = a.parent
            to = ctx.get(event.payload.get("target")) if event.payload.get("target") else None
            carry = a.state.carry
            if carry and ctx.load(a) > float(carry) / 2 and ((here and here.state.open) or (to and to.state.open)):
                sweat(ctx, a, "heavy_walk")
        elif verb not in ["fight", "heavy_walk"]:
            sweat(ctx, a, verb)
