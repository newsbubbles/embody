# What the road does to a newcomer: the first time one is out on the Glass Flats a squall comes off the south dunes and
# pins them where they stand for two world hours (go refuses while `pinned_until` is ahead). The host can also send one
# at anyone by scheduling `squall` at them. When it passes, the dunes have moved and something red shows past the veins.
SQUALL = 7200

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def hit(ctx, who):
    here = who.parent
    if here is None or who.state.dead:
        return
    ctx.patch(who, {"squalled": True, "pinned_until": ctx.t + SQUALL, "pinned_by": "the squall"})
    ctx.emit("scene", target=here, reach=1, text="The sky to the south goes the colour of rust, and then there is no sky. "
             "A squall comes off the dunes, sand thrown like gravel, and the world ends an arm's length out. Nobody walks "
             "in this. Get low, cover your face, keep your water close, and wait it out.")
    ctx.schedule(SQUALL, "squall_passes", target=who)

def on(ctx, event):
    k = event.kind
    if k == "arrived":
        st = story_of(ctx).state
        who = ctx.get(event.payload.get("who"))
        if who is None or event.payload.get("place") != st.flats:
            return
        if who.state.template and not who.state.squalled:
            hit(ctx, who)
    elif k == "squall":
        who = ctx.get(event.target)
        if who is not None:
            hit(ctx, who)
    elif k == "squall_passes":
        who = ctx.get(event.target)
        if who is None:
            return
        ctx.patch(who, {"pinned_until": None, "pinned_by": None})
        if who.parent is not None:
            ctx.emit("scene", target=who.parent, reach=1, text="The squall blows itself out to the north as fast as it "
                     "came. The dunes are not where they were. Out past the worked veins the sand has pulled back from "
                     "something that shows faintly red, and the way is open again.")
