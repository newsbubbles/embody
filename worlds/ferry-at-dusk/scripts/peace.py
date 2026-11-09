def on(ctx, event):
    if event.payload["verb"] == "attack":
        ctx.reject("nobody raises a hand in the square; Mara would never forgive it", "talk instead")
