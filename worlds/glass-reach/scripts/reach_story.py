def scene(ctx, place, text):
    ctx.emit("scene", target=place, reach=1, text=text)

def keth_standing(ctx, who, keth):
    for e in ctx.edges(who, "standing", "out"):
        if e["target"] == keth.id:
            return int(e["data"].get("value") or 0)
    return 0

def reveal_well(ctx, st, how):
    well = ctx.get(st.deepwell)
    if well is None or not well.state.hidden:
        return
    ctx.patch(well, {"hidden": False})
    ctx.patch(ctx.find(type="story", limit=1)[0], {"found_well": True, "well_found_by": how})
    if how == "nico":
        scene(ctx, st.ridge, "Nico looks at you a long moment, then points down the back of the ridge, to a shadow in the rock you had taken for nothing. A way down.")
    else:
        scene(ctx, st.ridge, "Goat sign, then a worn lip of stone, then cool air coming up out of the rock. There is a way down the back of the ridge.")

def finish_if_done(ctx, story):
    st = story.state
    if st.truce and st.dram_done and not st.done:
        ctx.patch(story, {"done": True})
        ctx.patch(ctx.root(), {"story": "complete"})
        scene(ctx, st.hold, "Water comes up the Salt Road under a Keth flag, and the Carrier's clerk is gone from the yard. Scar Gate stands. For now, it stands.")

def on(ctx, event):
    story = ctx.find(type="story", limit=1)[0]
    st = story.state
    k = event.kind
    p = event.payload
    if k == "arrived":
        dram = ctx.get(st.dram)
        if dram is not None and dram.state.waiting and dram.parent is not None and p.get("place") == dram.parent.id and p.get("who") == st.ansel:
            reeve = ctx.get(st.ansel)
            if not reeve.state.down and not ctx.relations(reeve, "duel") and not ctx.relations(dram, "duel"):
                ctx.relate("duel", [dram.id, reeve.id], {"place": dram.parent.id, "since": ctx.t, "public": True})
                ctx.patch(dram, {"waiting": False})
                ctx.emit("challenged", target=reeve, reach=1, by=dram.id, place=dram.parent.id, ring=True)
                scene(ctx, dram.parent, "Dram Hollis turns in the ring and draws. 'Reeve Varrick. Dram Hollis, of the Carriers' book, lately of other books. Step in, or be known for stepping back.'")
        if p.get("place") == st.ridge and not st.seen_ridge:
            ctx.patch(story, {"seen_ridge": True})
            scene(ctx, st.ridge, "From up here the Reach is a sheet of black glass with red dunes walking across it. The Hold is a thumbprint to the south. Nothing moves, except one thin line of smoke from somewhere under the rock.")
        elif p.get("place") == st.flats and not st.seen_flats:
            ctx.patch(story, {"seen_flats": True})
            scene(ctx, st.flats, "Glass underfoot, warm already. Veins of dull red show where the dunes have pulled back. Every step rings.")
    elif k == "checked":
        if p.get("place") == st.ridge and p.get("success") and str(p.get("skill")) in ["survival", "lore", "track", "search"] and int(p.get("dc") or 0) >= 15:
            reveal_well(ctx, st, "found")
    elif k == "talked":
        if event.target == st.nico:
            about = str(p.get("about", "")).lower()
            asker = ctx.get(p.get("by"))
            keth = ctx.get(st.keth)
            if asker is not None and ("water" in about or "well" in about or "cistern" in about or "keth" in about):
                if asker.state.faction == "the Keth" or keth_standing(ctx, asker, keth) >= 1:
                    reveal_well(ctx, st, "nico")
    elif k == "agreed":
        if event.target == st.taan and not st.truce:
            offer = str(p.get("offer", "")).lower()
            who = ctx.get(p.get("by"))
            keth = ctx.get(st.keth)
            if who is not None and keth_standing(ctx, who, keth) >= -1 and ("water" in offer or "truce" in offer or "well" in offer or "ember" in offer or "glass" in offer or "share" in offer or "peace" in offer):
                side = ctx.find(type="faction", name=who.state.faction, limit=1)
                parts = [keth.id] + ([side[0].id] if side else [who.id])
                ctx.relate("truce", parts, {"terms": str(p.get("offer")), "since": ctx.t, "public": True})
                ctx.patch(story, {"truce": True})
                ctx.patch(ctx.get(st.taan), {"dialog": {"water|well|truce": "We have terms. Keth water goes up the road at dusk and the Flats stay quiet. Keep it so."}})
                scene(ctx, st.deepwell, "Taan puts both palms flat on the wet stone. 'Then it is water between us. Say it at the Hold the way I say it here.'")
                finish_if_done(ctx, story)
            else:
                scene(ctx, st.deepwell, "Taan hears you out and shakes her head once. 'That is not terms. That is a man asking.'")
    elif k == "dram_moves":
        dram = ctx.get(st.dram)
        if dram is None or dram.state.down or dram.state.dead or st.dram_done:
            return
        ctx.move(dram, st.yard)
        ctx.emit("arrived", target=st.yard, reach=-1, who=dram.id, place=st.yard, quiet=False)
        ctx.patch(dram, {"waiting": True, "description": "The Carrier's clerk, except that the clerk's coat is off and the blade on his hip is not a clerk's."})
        reeve = ctx.get(st.ansel)
        if reeve is not None and reeve.parent.id == st.yard and not reeve.state.down and not ctx.relations(reeve, "duel"):
            ctx.relate("duel", [dram.id, reeve.id], {"place": st.yard, "since": ctx.t, "public": True})
            ctx.patch(dram, {"waiting": False})
            ctx.emit("challenged", target=reeve, reach=1, by=dram.id, place=st.yard, ring=True)
            scene(ctx, st.yard, "Dram Hollis steps into the ring and draws. 'Reeve Varrick. Dram Hollis, of the Carriers' book, lately of other books. Step in, or be known for stepping back.'")
        else:
            scene(ctx, st.yard, "Dram Hollis walks into the ring, shrugs off the clerk's coat, draws, and asks the yard for the reeve by name.")
            scene(ctx, st.hold, "Word comes in from the yard: the Carrier's clerk is in the ring with a blade out, asking for the reeve.")
    elif k in ["downed", "killed", "yielded"]:
        who = event.target
        if who == st.dram and not st.dram_done:
            ctx.patch(story, {"dram_done": True, "dram_how": k})
            scene(ctx, ctx.get(who).parent, "Something falls out of Dram's coat as he goes down: a folded letter under a seal the color of old blood.")
            ctx.spawn("letter", ctx.get(who).parent, name="Sealed letter", state={
                "text": "H. The reeve in the ring, before the moon turns. Keep the Keth thirsty: no truce, whatever it costs. The Flats are ours when the Hold is empty. Burn this. D.",
                "description": "Folded twice, sealed in dark red wax with a sigil of a well and a bar across it."})
            finish_if_done(ctx, story)
        elif who == st.ansel and k == "killed" and not st.reeve_dead:
            ctx.patch(story, {"reeve_dead": True, "done": True})
            ctx.patch(ctx.root(), {"story": "lost"})
            scene(ctx, ctx.get(who).parent, "The reeve of Scar Gate is dead on the Hold's own sand. Within the month a Dreyer banner will hang from the gate, and the Keth will go on drinking in the dark.")
    elif k == "heat":
        ctx.patch(ctx.root(), {"ambient": {"time_of_day": "noon", "weather": "white glare, heat shimmer off the glass", "light": "blinding"}})
        scene(ctx, st.flats, "The glare comes up off the glass until there is no ground, only light.")
    elif k == "dusk":
        ctx.patch(ctx.root(), {"ambient": {"time_of_day": "dusk", "weather": "the heat going out of the air fast", "light": "red, long shadows"}})
        scene(ctx, st.hold, "The sun drops behind Red Ridge and the Hold's walls start to tick as they cool.")
    elif k == "cistern_cracks":
        cistern = ctx.get(st.cistern)
        if cistern is not None and int(cistern.state.left or 0) > 0:
            ctx.patch(cistern, {"left": 0, "description": "A stone tank with a crack you could put your hand in. Dry. The floor of it is already warm."})
            scene(ctx, st.hold, "A sound like a shot from under the floor. The cistern's crack has run, and what water was left is going into the sand.")
