# The wild ground (Nate 2026-11-11; notes/the-reach-grows.md, B and C): the Thornbrake south of the Hold, where the
# thornbacks come out at night, and Weeping Rock in the Scar wall north of it, the child's well under the glass wasps.
# The story keeps day and night (`wild_night`, set at dusk, cleared at dawn). At dawn the rock's basin gains two
# draws, every dew still gains its dew, a barrel cactus tapped dry is full again a week after, and a pack that fled
# comes back once its day is out. Walk into the brake at night and the pack goes for you; down the big boar and the
# rest run for a day. The wasps are their own (scripts/wasp_tick.py, wasp_smoke.py).
use("common")
PACK_FLEES = 86400

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def by_name(ctx, name):
    for e in ctx.find(name=name, limit=10):
        if e.name == name:
            return e
    return None

def scene(ctx, place, text):
    if place is not None:
        ctx.emit("scene", target=place, reach=1, text=text)

def fill(ctx, it, n):
    mx = int(it.state.max_left or 0)
    if mx and int(it.state.left or 0) < mx:
        ctx.patch(it, {"left": min(mx, int(it.state.left or 0) + n)})

def pack(ctx, brake):
    out = []
    for c in ctx.children(brake, "creature"):
        if c.state.beast and c.state.pack and not c.state.dead and not c.state.down and not c.state.hidden:
            out.append(c)
    return out

def dawn(ctx, st):
    for name in ["Weeping Rock", "The Thornbrake", "Tessel's Steading"]:
        place = by_name(ctx, name)
        if place is None:
            continue
        for it in ctx.children(place, "thing"):
            if it.state.basin:
                fill(ctx, it, int(it.state.per_dawn or 2))
            if it.state.cactus and int(it.state.left or 0) == 0:
                if it.state.full_at is None:
                    ctx.patch(it, {"full_at": ctx.t + 6 * 86400})
                elif ctx.t >= it.state.full_at:
                    ctx.patch(it, {"left": int(it.state.max_left or 1), "full_at": None})
        for c in ctx.children(place, "creature"):
            if c.state.beast and c.state.hidden and c.state.fled_until and ctx.t >= c.state.fled_until:
                ctx.patch(c, {"hidden": False, "fled_until": None})
    for pid in [st.hold, st.yard, st.thornbrake, st.steading]:
        place = ctx.get(pid) if pid else None
        if place is None:
            continue
        for it in ctx.children(place, "thing"):
            if it.state.dew:
                fill(ctx, it, int(it.state.per_dawn or 2))

def on(ctx, event):
    story = story_of(ctx)
    st = story.state
    k = event.kind
    p = event.payload or {}
    if k == "dusk":
        ctx.patch(story, {"wild_night": True})
        return
    if k == "dawn":
        ctx.patch(story, {"wild_night": False})
        dawn(ctx, st)
        return
    brake = ctx.get(st.thornbrake) if st.thornbrake else None
    if brake is None:
        return
    if k == "arrived":
        who = ctx.get(p.get("who"))
        if p.get("place") != brake.id or who is None or who.state.beast or not st.wild_night:
            return
        beasts = pack(ctx, brake)
        if len(beasts) == 0:
            return
        scene(ctx, brake, "Something heavy moves in the thorn, then three of them, low and fast and glittering: "
              "thornbacks, out for the night, and " + who.name + " is in their ground.")
        for b in beasts:
            if not who.state.down:
                strike(ctx, b, who, False)
        return
    if k == "downed" or k == "killed":
        hit = ctx.get(event.target)
        if hit is None or not hit.state.beast or not hit.state.leader:
            return
        for c in ctx.children(hit.parent, "creature"):
            if c.state.beast and c.id != hit.id and not c.state.dead and not c.state.down:
                ctx.patch(c, {"hidden": True, "fled_until": ctx.t + PACK_FLEES})
        scene(ctx, hit.parent, "The big boar goes down in the thorn, and the others break and crash away south. "
              "The brake goes quiet for the first time.")
