def words(text):
    # the topic as whole words: "ale" matches "an ale, please" and not "a tale"
    t = str(text).lower()
    for ch in [",", ".", "?", "!", ";", ":", "'", "\""]:
        t = t.replace(ch, " ")
    return t.split()

def score(key, topic):
    # a dialog key is one word or several joined with |: "ale|drink|beer". The score is how many aliases
    # the topic contains plus a little for longer aliases, so "ferry crossing" prefers the ferry entry.
    s = 0
    for alias in key.split("|"):
        a = alias.strip()
        if a in topic:
            s = s + 10 + len(a)
    return s

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
    # Someone talked to me. Answer from my dialog table with the best-matching entry; hand over anything I
    # give for that topic. Skipped while an agent embodies me (unless_embodied): then the agent answers.
    if event.target != ctx.self.id:
        return
    topic = words(event.payload.get("about", ""))
    asker = event.payload.get("by")
    me = ctx.self.state
    dialog = dict(me.dialog or {})
    own = (me.idle_orders or {}).get("dialog") or {}
    for k in own:  # a mind's own lines while its seat is idle, over the author's
        dialog[k] = own[k]
    gives = me.gives or {}
    best = None
    best_s = 0
    for key in dialog:
        s = score(key, topic)
        if s > best_s:
            best = key
            best_s = s
    if best is None:
        speak(ctx, me.default_line or (me.standing_orders or {}).get("answer") or "Hm.", asker)
        return
    got = given_to(me, best)
    had = asker in got or "*" in got
    line = pick(ctx, dialog[best], had)
    if line:
        speak(ctx, line, asker)
    if best in gives and not had:
        g = gives[best]
        if hand_over(ctx, g, asker):
            speak(ctx, g.get("line") or "Here, take the " + str(g.get("name") or g.get("item")).lower() + ".", asker)
            ctx.patch(ctx.self, {"gave": {best: got + [asker]}})
        else:
            speak(ctx, g.get("gone_line") or "I had one of those somewhere. Gone now.", asker)
