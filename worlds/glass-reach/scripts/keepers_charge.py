# A charge laid before the Hold (the Hold's Keeper of the Count, 2026-11-12): the holder of the Keeper's book names who
# did a thing, aloud, where the Hold hears it. What follows is on the book's state, so a world sets it live:
#   charge_at: [place ids where a charge is heard]
#   charges: {"<person id>": {"needs": {"holds": [...], "marks": [...], "story": {...}}, "proved": effects,
#                              "unproved": effects}}
#   bought: effects for a man the house bought (turncoat, bought_by); otherwise: effects for anyone else
#   effects: {"scene": text ({who} and {by} filled in), "patch": {...} on the accused, "story": {...},
#             "mark": story key to put the accused on, "reveal": a hidden place the accuser now knows the way to
#             ("reveal_from": the place its way opens from, made when first shown),
#             "whisper": what the accuser alone hears, "remember_by": what the accuser keeps}

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def accused(ctx):
    ref = str((ctx.params or {}).get("who") or "").strip()
    if not ref:
        return None
    for x in ctx.find(name=ref, limit=20):
        if (x.name or "").lower() == ref.lower() or x.id == ref:
            return x
    if ref[:1] == "e" and ref[1:].isdigit():
        return ctx.get(ref)
    return None

def holds(who, name):
    for it in who.children():
        if (it.name or "").lower() == str(name).lower():
            return True
    return False

def met(ctx, who, needs):
    st = story_of(ctx).state
    for n in needs.get("holds") or []:
        if not holds(who, n):
            return False
    for k in needs.get("marks") or []:
        if who.id not in list(st.get(k) or []):
            return False
    want = needs.get("story") or {}
    for k in want:
        if st.get(k) != want[k]:
            return False
    return True

def check(ctx):
    book = ctx.target
    me = ctx.actor
    if book.parent is None or book.parent.id != me.id:
        return "a charge is laid with the book in your hands: take it first"
    at = list(book.state.charge_at or [])
    if at and (me.parent is None or me.parent.id not in at):
        names = []
        for pid in at:
            p = ctx.get(pid)
            if p is not None:
                names.append(p.name)
        return "a charge is heard only before the Hold: lay it at " + " or ".join(names)
    who = accused(ctx)
    if who is None:
        return "name who you charge: params {\"who\": their name}"
    if who.id == me.id:
        return "you cannot charge yourself: tell someone instead"
    return True

def way(ctx, a, b):
    for e in ctx.edges(a, "connects_to", "out"):
        if e["target"] == b.id:
            return True
    return False

def effects(ctx, me, who, fx):
    if not fx:
        return ""
    story = story_of(ctx)
    text = str(fx.get("scene") or "").replace("{who}", who.name).replace("{by}", me.name)
    if text and me.parent is not None:
        ctx.emit("scene", target=me.parent, reach=1, text=text)
    if fx.get("patch"):
        ctx.patch(who, dict(fx["patch"]))
    if fx.get("story"):
        ctx.patch(story, dict(fx["story"]))
    if fx.get("mark"):
        on_list = list(story.state.get(fx["mark"]) or [])
        if who.id not in on_list:
            ctx.patch(story, {fx["mark"]: on_list + [who.id]})
    if fx.get("reveal"):
        place = ctx.get(fx["reveal"])
        if place is not None:
            kt = place.state.known_to
            known = list(kt) if isinstance(kt, list) else ([] if kt is None else [kt])
            if me.id not in known:
                ctx.patch(place, {"known_to": known + [me.id]})
            frm = ctx.get(fx.get("reveal_from")) if fx.get("reveal_from") else None
            if frm is not None and not way(ctx, frm, place):
                ctx.link(frm, place, "connects_to")  # the way is made when it is first shown: until then no exit names it
                ctx.link(place, frm, "connects_to")
    if fx.get("whisper"):
        ctx.emit("scene", target=me, reach=0, text=str(fx["whisper"]).replace("{who}", who.name).replace("{by}", me.name))
    if fx.get("remember_by"):
        ctx.remember(me, fx["remember_by"])
    return text

def apply(ctx):
    book = ctx.target
    me = ctx.actor
    who = accused(ctx)
    rule = (book.state.charges or {}).get(who.id)
    if rule:
        way = "proved" if met(ctx, me, rule.get("needs") or {}) else "unproved"
        fx = rule.get(way)
    elif who.state.turncoat and who.state.bought_by:
        way = "bought"
        fx = book.state.bought
    else:
        way = "otherwise"
        fx = book.state.otherwise
    text = effects(ctx, me, who, fx)
    ctx.emit("charged", target=who, reach=1, by=me.id, way=way)
    return {"charged": who.name, "way": way, "heard": text}
