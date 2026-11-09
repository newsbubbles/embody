def on(ctx, event):
    # a sleeper does nothing but wake (or get woken); installed on the root so it hears every before_act
    if ctx.actor is not None and ctx.actor.state.asleep and event.payload["verb"] != "wake":
        ctx.reject("you are asleep", "wake yourself (act wake on yourself) or wait to be woken")
