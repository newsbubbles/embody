def norm(text):
    # a topic as written, in any language: case and surrounding spaces aside, nothing is read out of it
    return " ".join(str(text).lower().split())

def names(key):
    # a dialog key is one topic or several names for it joined with |: "ale|drink|beer"
    return [norm(a) for a in str(key).split("|") if norm(a)]

def pick(ctx, entry, given):
    # an entry is a line, or a dict: {"line", "after_gift", "if_state": {k: v}, "else"}
    if not isinstance(entry, dict):
        return entry
    me = ctx.self.state
    cond = entry.get("if_state")
    if cond:
        for k in cond:
            if me.get(k) != cond[k]:
                return entry.get("else", entry.get("line"))
    if given and entry.get("after_gift"):
        return entry["after_gift"]
    return entry.get("line")

def given_to(me, key):
    # gave is {topic key: [who asked and got it]}; one gift per topic per asker, not per lifetime
    gave = me.gave or {}
    if isinstance(gave, list):
        gave = {k: ["*"] for k in gave}
    return list(gave.get(key) or [])

def hand_over(ctx, g, asker):
    # a gift is a held thing named in "item" (handed over for real), or a thing spawned from the table
    item = g.get("item")
    if item:
        for it in ctx.self.children():
            if (it.name or "").lower() == str(item).lower():
                ctx.patch(it, {"given_by": ctx.self.id, "given_before_by": it.state.given_by})
                ctx.move(it, asker)
                ctx.emit("given", target=asker, reach=1, item=it.id, by=ctx.self.id)
                return True
        return False
    ctx.spawn(g["type"], asker, name=g["name"], state=g.get("state"))
    return True

def speak(ctx, line, asker):
    # Text in double quotes is said and the rest is done, in the order written:
    # 'Varn doesn't look up. "Bench is busy, love."' is a gesture, then a line said. A line with no double
    # quotes is said whole, unless the person (or the world's root) keeps lines: "quoted", where it is a gesture.
    # A person whose state has `loud_voice` (a barker, a tout) says every line aloud: it carries as a shout where the
    # world keeps a voice_radius.
    loud = bool(ctx.self.state.loud_voice)
    text = str(line).replace("“", "\"").replace("”", "\"")
    if "\"" not in text:
        if (ctx.self.state.lines or ctx.root().state.lines) == "quoted":
            ctx.gesture(text, to=asker)
        else:
            ctx.say(text, to=asker, loud=loud)
        return
    i = 0
    for part in text.split("\""):  # even pieces lie outside the quotes
        if part.strip():
            if i % 2 == 1:
                ctx.say(part.strip(), to=asker, loud=loud)
            else:
                ctx.gesture(part.strip(), to=asker)
        i = i + 1

def on(ctx, event):
    # Someone talked to me. Answer from my dialog table with the entry the topic names (one of its names, as the
    # world wrote it); hand over anything I give for that topic. Skipped while an agent embodies me
    # (unless_embodied): then the agent answers. Nothing is read out of the asker's words, in any language.
    if event.target != ctx.self.id:
        return
    topic = norm(event.payload.get("about", ""))
    asker = event.payload.get("by")
    me = ctx.self.state
    dialog = dict(me.dialog or {})
    gives = me.gives or {}
    best = None
    for key in dialog:
        if topic and topic in names(key):
            best = key
            break
    if best is None:
        line = me.default_line or (me.standing_orders or {}).get("answer")
        if line:  # the world's own words, or none: the pack says nothing of its own
            speak(ctx, line, asker)
        return
    got = given_to(me, best)
    had = asker in got or "*" in got
    line = pick(ctx, dialog[best], had)
    if line:
        speak(ctx, line, asker)
    if best in gives and not had:
        g = gives[best]
        if hand_over(ctx, g, asker):
            if g.get("line"):
                speak(ctx, g["line"], asker)
            ctx.patch(ctx.self, {"gave": {best: got + [asker]}})
        elif g.get("gone_line"):
            speak(ctx, g["gone_line"], asker)
