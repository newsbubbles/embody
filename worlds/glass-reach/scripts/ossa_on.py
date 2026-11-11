def on(ctx, event):
    # emberglass handed to Ossa buys a full skin a shard (a stack of five buys five); anything else she keeps and says so
    if event.target != ctx.self.id:
        return
    item = ctx.get(event.payload.get("item"))
    buyer = ctx.get(event.payload.get("by"))
    if item is None or buyer is None:
        return
    if item.state.kind == "ember":
        n = ctx.count(item)
        ctx.destroy(item)
        for _ in range(n):
            ctx.spawn("waterskin", buyer, name="Guild waterskin", state={"left": 3, "given_by": ctx.self.id,
                      "description": "A Guild skin, tallied and stamped, heavy and cool.",
                      "description_full": "A Guild skin, tallied and stamped, heavy and cool.",
                      "description_empty": "A Guild skin, tallied and stamped, slack and dry."})
        ctx.patch(ctx.self, {"ember_bought": int(ctx.self.state.ember_bought or 0) + n})
        ctx.say(("Fair glass. A full skin, and no questions where you dug it." if n == 1 else
                 "Fair glass. " + str(n) + " full skins, a shard each, and no questions where you dug it."), to=buyer.id)
        ctx.emit("traded", target=buyer, reach=1, by=ctx.self.id, got="Guild waterskin", gave="Emberglass")
    else:
        ctx.say("I take glass, friend. Keep your trinkets.", to=buyer.id)
