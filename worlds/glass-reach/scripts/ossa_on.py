def on(ctx, event):
    # emberglass handed to Ossa buys a full skin; anything else she keeps and says so
    if event.target != ctx.self.id:
        return
    item = ctx.get(event.payload.get("item"))
    buyer = ctx.get(event.payload.get("by"))
    if item is None or buyer is None:
        return
    if item.state.kind == "ember":
        ctx.destroy(item)
        ctx.spawn("waterskin", buyer, name="Full waterskin", state={"left": 3})
        ctx.patch(ctx.self, {"ember_bought": int(ctx.self.state.ember_bought or 0) + 1})
        ctx.say("Fair glass. A full skin, and no questions where you dug it.", to=buyer.id)
        ctx.emit("traded", target=buyer, reach=1, by=ctx.self.id, got="Full waterskin", gave="Emberglass")
    else:
        ctx.say("I take glass, friend. Keep your trinkets.", to=buyer.id)
