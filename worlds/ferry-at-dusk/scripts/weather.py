def on(ctx, event):
    # the ambient facts every perceive carries: on the root, laid under each place's own
    root = ctx.root()
    if event.kind == "fog":
        ctx.patch(root, {"ambient": {"weather": "fog coming up off the river"}})
        ctx.emit("scene", target=ctx.get(event.target).parent if ctx.get(event.target) else root, reach=0,
                 text=event.payload.get("text", "Fog."))
    elif event.kind == "nightfall":
        ctx.patch(root, {"ambient": {"time_of_day": "night", "light": "dark; lamps and stars"}})
        for place in ctx.find(type="place"):
            ctx.emit("scene", target=place, reach=0, text="The last light goes out of the sky. Night, proper.")
    elif event.kind == "dawn":
        ctx.patch(root, {"ambient": {"time_of_day": "dawn", "weather": "clear and cold", "light": "grey, growing"}})
        for place in ctx.find(type="place"):
            ctx.emit("scene", target=place, reach=0, text="Grey light. Birds in the reeds. Dawn.")
        for p in ctx.find(type="person"):
            if p.state.asleep:
                ctx.patch(p, {"asleep": False})
                ctx.emit("woken", target=p, reach=-1, by=None, dawn=True)
