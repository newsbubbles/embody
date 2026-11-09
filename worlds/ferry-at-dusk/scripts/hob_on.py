def on(ctx, event):
    # work done at the mill by someone else squares whatever is owed to Hob: the village runs on favors
    if event.payload.get("of") != "chore_done" or event.payload.get("by") == ctx.self.id:
        return
    thing = ctx.get(event.payload.get("thing"))
    if thing is None or thing.parent.id != ctx.self.state.home:
        return
    for r in ctx.relations(ctx.self.id, "debt"):
        if r["data"].get("owed_to") == ctx.self.id:
            who = ctx.get(r["data"].get("owed_by"))
            ctx.unrelate(r["id"])
            ctx.say("That squares " + (who.name if who else "the") + "'s " + str(r["data"].get("what", "debt"))
                    + ", far as I'm concerned. Tell him.", to=event.payload.get("by"))
            ctx.emit("debt_settled", target=ctx.self, reach=1, by=event.payload.get("by"), was=r["data"])
