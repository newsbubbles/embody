# A Guild reckoner (a mentat: notes/the-guild-speakers.md): ask a question and pay a shard, and the answer is the
# world's own numbers, exactly. A reckoner answers anyone who pays, both houses alike; the Guild sells to everyone.
# Questions: water (what the Hold holds and how many drink from it), moon (what the reckoning counted), convoy (where
# the convoy's water went), glass (the Guild's own glass on the Reach leg).
PRICE = 1
TOPICS = ["water", "moon", "convoy", "glass"]


def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def topic(ctx):
    q = str((ctx.params or {}).get("question") or "").lower()
    for t in TOPICS:
        if t in q:
            return t
    if "cistern" in q or "drink" in q:
        return "water"
    if "wall" in q or "rider" in q or "reckon" in q:
        return "moon"
    if "shard" in q or "ember" in q or "strongbox" in q:
        return "glass"
    return None

def check(ctx):
    r = ctx.target
    if not r.state.reckoner:
        return "only a Guild reckoner answers that way; talk to them instead"
    if r.state.dead or r.state.down or r.state.asleep:
        return r.name + " cannot reckon now"
    if topic(ctx) is None:
        return ("ask one of what a reckoner sells: params {\"question\": \"water\" | \"moon\" | \"convoy\" | \"glass\"}, "
                "a shard of emberglass the answer")
    if ctx.count(ctx.actor, "ember") < PRICE:
        return "a reckoner's answer costs a shard of emberglass, and you carry none"
    return True

def hold_water(ctx, st):
    water = 0
    wids = [st.keth_jars, st.hold_ration]
    if st.cistern_mended:
        wids.append(st.cistern)
    for wid in wids:
        w = ctx.get(wid) if wid else None
        if w is not None:
            water = water + int(w.state.left or 0)
    souls = 0
    for pid in [st.hold, st.yard]:
        for it in ctx.children(pid) if pid else []:
            if it.state.dew:
                water = water + int(it.state.left or 0)
            if it.state.vigor is not None and not it.state.dead and not it.state.beast:
                souls = souls + 1
    return water, souls

def answer(ctx, t):
    st = story_of(ctx).state
    if t == "water":
        water, souls = hold_water(ctx, st)
        return ("The Hold's water, now: " + str(water) + " draws in its jars, its ration and its cistern" +
                ("" if st.cistern_mended else " (the cistern still cracked, so not counted)") + ", and " + str(souls) +
                " souls under its roof and in its yard who drink from them.")
    if t == "moon":
        r = st.reckoning
        if not st.moon_turned or not r:
            return "The moon has not turned. A reckoner counts what was, not what will be."
        return ("What the moon counted: " + str(r.get("wall")) + " on the wall against " + str(r.get("riders")) +
                " the riders needed; " + str(r.get("water")) + " draws of water; the Keth truce " +
                ("holding" if r.get("truce") else "broken") + "; the convoy's water to " + str(r.get("convoy") or "nobody")
                + "; " + str(r.get("bought") or 0) + " bought men on the wall. Outcome: " + str(st.outcome) + ".")
    if t == "convoy":
        if st.convoy_to:
            return "The convoy's water was sold to " + str(st.convoy_to) + ", and the Guild carried it there."
        return "The convoy's water was sold to nobody. The Guild carried it north."
    glass = 0
    for box in ctx.find(name="The Guild strongbox", limit=2):
        for it in box.children():
            if it.state.kind == "ember":
                glass = glass + int(it.state.count or 1)
    return "The Guild's glass in its strongbox at the yard: " + str(glass) + " shards."

def apply(ctx):
    t = topic(ctx)
    r = ctx.target
    left = PRICE
    for it in ctx.actor.children():
        if left > 0 and it.state.kind == "ember":
            k = min(left, ctx.count(it))
            ctx.transfer(it, r, k)
            left = left - k
    text = answer(ctx, t)
    ctx.emit("scene", target=r.parent, reach=1, text=r.name + " takes the shard, closes their eyes for the space of three "
             "breaths, lips moving, and answers " + ctx.actor.name + " in a flat clear voice.")
    ctx.emit("consulted", target=ctx.actor, reach=0, by=r.id, topic=t, text=text)
    ctx.remember(r, "I reckoned for " + ctx.actor.name + " on " + t + ": " + text)
    return text
