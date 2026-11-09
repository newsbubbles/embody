def words(text):
    # whole words, lower case, no punctuation
    t = str(text).lower()
    for ch in [",", ".", "?", "!", ";", ":", "'", "\""]:
        t = t.replace(ch, " ")
    return t.split()

# -- the verb: leave word with someone here for someone who is not

def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "leave word with someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.asleep:
        return "they are asleep; wake them first"
    word = ""
    if ctx.params:
        word = str(ctx.params.get("word", "")).strip()
    if not word:
        return "say what to tell them: params {'for': who, 'word': the message}"
    return True

def apply(ctx):
    who = ""
    word = ""
    if ctx.params:
        who = str(ctx.params.get("for", "")).strip()
        word = str(ctx.params.get("word", "")).strip()
    place = ctx.actor.parent
    ctx.emit("word_left", target=ctx.target, reach=0, by=ctx.actor.id, by_name=ctx.actor.name,
             to=who, word=word, where=place.name if place else "")

# -- the listener: keep what was left (always), hand it on when the right one asks (while nobody embodies me)

ANYONE = ["", "anyone", "any", "all", "*", "whoever", "everyone"]
SMALL = ["the", "a", "an", "of", "for", "to", "who", "one", "man", "men", "new", "next", "comes", "whoever", "from"]

def keep(ctx, event):
    if event.target != ctx.self.id:
        return
    p = event.payload
    kept = list(ctx.self.state.word_left or [])
    kept.append({"from": p.get("by"), "from_name": p.get("by_name") or "someone", "for": str(p.get("to") or ""),
                 "word": str(p.get("word") or ""), "t": event.t, "where": p.get("where") or "", "given": []})
    if len(kept) > 20:
        kept = kept[-20:]
    ctx.patch(ctx.self, {"word_left": kept})

def is_for(ctx, entry, asker):
    # who the word is for: anyone; a name ("Harl"); a kind of person ("the new guard", "a Keth"); the asker's faction
    f = str(entry.get("for") or "").strip().lower()
    if f in ANYONE:
        return True
    want = [w for w in words(f) if w not in SMALL and len(w) > 1]
    if not want:
        return True
    a = ctx.get(asker)
    if a is None:
        return False
    have = words(a.name) + words(a.type) + words(a.state.template or "") + words(a.state.faction or "")
    for w in want:
        if w in have:
            return True
    return False

def mentions(topic, entry):
    # does the asker's topic name the one who left the word? ("the reeve", "Varrick", "Ansel")
    for w in words(entry.get("from_name") or ""):
        if len(w) > 3 and w in topic:
            return True
    return False

def on(ctx, event):
    if event.target != ctx.self.id:
        return
    asker = event.payload.get("by")
    if not asker:
        return
    kept = list(ctx.self.state.word_left or [])
    if not kept:
        return
    topic = words(event.payload.get("about", ""))
    changed = False
    withheld = None
    for entry in kept:
        if entry.get("from") == asker:
            continue
        given = list(entry.get("given") or [])
        if asker in given:
            continue
        if is_for(ctx, entry, asker):
            line = entry["from_name"] + " left word for you"
            if entry.get("where"):
                line = line + ", at " + entry["where"]
            ctx.say(line + ": '" + entry["word"] + "'", reach=0, to=asker)
            entry["given"] = given + [asker]
            changed = True
        elif mentions(topic, entry):
            withheld = entry
    if withheld is not None and not changed:
        ctx.say(withheld["from_name"] + " left word here. Not for you.", reach=0, to=asker)
    if changed:
        ctx.patch(ctx.self, {"word_left": kept})
