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
