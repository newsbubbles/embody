def tam_to_landing(ctx, st, how):
    tam = ctx.get(st.tam)
    if tam is None or tam.parent.id == st.landing:
        return
    ctx.patch(tam, {"hidden": False, "asleep": False})
    ctx.move(tam, st.landing)
    if how == "bell":
        ctx.emit("scene", target=st.square, reach=1, text="Far off, a hoarse voice answers the bell.")
        ctx.emit("scene", target=st.landing, reach=1, text="Old Tam comes down the reed path, rubbing his eyes, and steps onto the raft.")
    else:
        ctx.emit("scene", target=st.reeds, reach=1, text="Tam gets up, brushes off the reeds and sets off down the bank. 'Raft is this way.'")
        ctx.emit("scene", target=st.landing, reach=1, text="Old Tam comes along the bank from the reeds and steps onto the raft.")
    ctx.emit("arrived", target=st.landing, reach=-1, who=tam.id, place=st.landing)
    ctx.patch(ctx.find(type="story", limit=1)[0], {"stage": "cross", "tam_came_by": how})

def on(ctx, event):
    # installed on the world root with set_rule, so it hears every event; the Story entity keeps the facts.
    # Every branch checks a fact, not the stage, so play off the rails still finds the river.
    story = ctx.find(type="story", limit=1)[0]
    st = story.state
    k = event.kind
    if k == "arrived" and event.payload.get("place") == st.landing and not st.seen_landing:
        ctx.emit("scene", target=st.landing, reach=1,
                 text="Cold mist lifts off the river. The raft is moored and the bell rope on the post hangs cut. No ferryman.")
        ctx.patch(story, {"seen_landing": True, "stage": "ask"})
    elif k == "talked" and event.target == st.mara and not st.mara_told:
        about = str(event.payload.get("about", "")).lower()
        if "ferry" in about or "tam" in about or "cross" in about or "river" in about:
            # patch merges: this adds one topic to Mara's table without touching the rest
            ctx.patch(ctx.get(st.mara), {"dialog": {
                "bell": "The landing bell calls him down from wherever he is sleeping it off. Rope was cut by the Pell boys. Hob at the mill keeps rope."}})
            ctx.patch(story, {"mara_told": True, "stage": "bell"})
    elif k == "rang":
        tam_to_landing(ctx, st, "bell")
    elif k == "woken" and event.target == st.tam:
        tam_to_landing(ctx, st, "woken")
    elif k == "crossed" and not st.crossed and event.target == st.far_bank:
        ctx.emit("scene", target=st.far_bank, reach=1, text="The raft grinds onto the far shingle. Behind you Ashford is a handful of lights in the fog.")
        ctx.patch(ctx.root(), {"story": "complete"})
        ctx.patch(story, {"crossed": True, "stage": "done"})
