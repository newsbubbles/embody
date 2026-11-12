# Testimony (Nate 2026-11-12, an inquiry for the Hold's Keeper of the Count): a witness with no mind in its seat says
# what it saw, and says more to whoever brings the proof. The rule sits on the witness; what it knows is its state:
#   testimony: [{"topics": "cistern|night|lamp", "line": what it says, "private": true to tell the asker alone,
#                "needs": {"holds": [names the asker carries], "marks": [story keys whose list holds the asker],
#                          "story": {key: value the story has now}},
#                "then": {"patch": {...} on the witness, "story": {...}, "mark": story key to put the asker on,
#                         "reveal": a hidden place the asker now knows the way to, "reveal_from": the place the way
#                         opens from (made the first time it is shown, so no exit names it before), "remember": ...}}]
# The first entry whose topics match and whose needs are met is said. The witness's dialog carries the same topics
# with an empty line, so the table stays quiet and this speaks.

def words(text):
    t = str(text or "").lower()
    for ch in [",", ".", "?", "!", ";", ":", "'", "\""]:
        t = t.replace(ch, " ")
    return t.split()

def matches(topics, about):
    said = words(about)
    for a in str(topics or "").split("|"):
        a = a.strip().lower()
        if a and a in said:
            return True
    return False

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

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

def way(ctx, a, b):
    for e in ctx.edges(a, "connects_to", "out"):
        if e["target"] == b.id:
            return True
    return False

def then(ctx, me, who, t):
    story = story_of(ctx)
    if t.get("patch"):
        ctx.patch(me, dict(t["patch"]))
    if t.get("story"):
        ctx.patch(story, dict(t["story"]))
    if t.get("mark"):
        on_list = list(story.state.get(t["mark"]) or [])
        if who.id not in on_list:
            ctx.patch(story, {t["mark"]: on_list + [who.id]})
    if t.get("reveal"):
        place = ctx.get(t["reveal"])
        if place is not None:
            kt = place.state.known_to
            known = list(kt) if isinstance(kt, list) else ([] if kt is None else [kt])
            if who.id not in known:
                ctx.patch(place, {"known_to": known + [who.id]})
            frm = ctx.get(t.get("reveal_from")) if t.get("reveal_from") else None
            if frm is not None and not way(ctx, frm, place):
                ctx.link(frm, place, "connects_to")  # the way is made when it is first shown: until then no exit names it
                ctx.link(place, frm, "connects_to")
    if t.get("remember"):
        ctx.remember(who, t["remember"])

def on(ctx, event):
    me = ctx.self
    if event.kind != "talked" or event.target != me.id or ctx.embodied(me):
        return
    who = ctx.get((event.payload or {}).get("by"))
    if who is None:
        return
    about = (event.payload or {}).get("about")
    for t in me.state.testimony or []:
        if not matches(t.get("topics"), about) or not met(ctx, who, t.get("needs") or {}):
            continue
        if t.get("private"):
            ctx.emit("scene", target=who, reach=0, text=t.get("line") or "")
        else:
            ctx.say(t.get("line") or "", to=who.id)
        if t.get("then"):
            then(ctx, me, who, t["then"])
        return
