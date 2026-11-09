def on(ctx, event):
    if event.target != ctx.self.id:
        return
    if event.kind == "touched":
        if ctx.self.state.friend == event.payload.get("by"):
            ctx.say("leans into your hand, tail thumping the floor")
        else:
            ctx.say("sniffs your hand, then your pockets, hopeful")
        return
    item = ctx.get(event.payload["item"])
    if item is not None and item.state.kind == "food":
        ctx.destroy(item)
        ctx.patch(ctx.self, {"friend": event.payload["by"]})
        ctx.say("wolfs it down and looks up at you. You have a dog now.")
        for board in ctx.find(type="sign", name="Notice board"):
            text = str(board.state.text or "")
            if "Lost: one grey dog" in text:
                ctx.patch(board, {"text": text.split(" Lost: one grey dog")[0] + " FOUND: the grey dog. He picked someone."})
    else:
        ctx.say("sniffs it and loses interest")
