def on(ctx, event):
    if event.kind == "fog":
        ctx.self.state.fog = True
        ctx.patch(ctx.self, {"ambient": {"weather": "river fog, thick; the far bank is gone"}})
    elif event.kind == "dawn":
        ctx.self.state.fog = False
        ctx.patch(ctx.self, {"ambient": {"weather": "the fog thinning off the water"}})
