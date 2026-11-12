# Comparing hands (the Hold's Keeper of the Count, 2026-11-12): two papers side by side under the Keeper's glass. A
# paper keeps the hands that wrote it (write.py; a world sets them on the papers it lays), and the glass tells its
# holder whether two papers share a hand. Never whose: a name has to come from somewhere else. A book with
# `match_marks` [{"paper": id, "hand": id, "mark": story key}] puts its reader on that story list when that paper is
# matched against one in that hand.

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def paper(ctx, ref):
    ref = str(ref or "").strip().lower()
    if not ref:
        return None
    me = ctx.actor
    places = [me]
    if me.parent is not None:
        places.append(me.parent)
    for p in places:
        for it in p.children():
            if it.state.hidden or (it.state.text is None and it.type != "letter"):
                continue
            if it.id.lower() == ref or (it.name or "").lower() == ref:
                return it
    return None

def check(ctx):
    book = ctx.target
    if book.parent is None or book.parent.id != ctx.actor.id:
        return "the glass works in your own hands: take the book first"
    p = ctx.params or {}
    a = paper(ctx, p.get("a"))
    b = paper(ctx, p.get("b"))
    if a is None or b is None:
        return "name two papers you hold or that lie here: params {\"a\": a paper, \"b\": another}"
    if a.id == b.id:
        return "that is one paper twice: name two"
    return True

def apply(ctx):
    book = ctx.target
    p = ctx.params or {}
    a = paper(ctx, p.get("a"))
    b = paper(ctx, p.get("b"))
    ha = list(a.state.hands or [])
    hb = list(b.state.hands or [])
    same = None
    if not ha or not hb:
        text = "Under the glass one of them shows no hand to read: worn, printed, or never written by a person."
    else:
        same = False
        for h in ha:
            if h in hb:
                same = True
        if same:
            text = ("Under the glass the strokes are the same: the same loops, the same pressure at the turn of each "
                    "letter. " + a.name + " and " + b.name + " were written by one hand.")
        else:
            text = "Under the glass the strokes part ways at every turn. " + a.name + " and " + b.name + " are two hands."
    if same:
        story = story_of(ctx)
        for m in book.state.match_marks or []:
            if (a.id == m.get("paper") and m.get("hand") in hb) or (b.id == m.get("paper") and m.get("hand") in ha):
                on_list = list(story.state.get(m.get("mark")) or [])
                if ctx.actor.id not in on_list:
                    ctx.patch(story, {m.get("mark"): on_list + [ctx.actor.id]})
    ctx.emit("compared", target=book, reach=0, by=ctx.actor.id, a=a.id, b=b.id, same=same)
    return text
