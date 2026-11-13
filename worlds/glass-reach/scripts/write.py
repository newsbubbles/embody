# Writing (the spoken-vs-real audit, 2026-11-12): over four days the Reach's people tried to write, sign or copy a
# paper more than a hundred times, and the world had no pen. A leaf you hold takes what you write, a line at a time,
# up to what fits; a signature is your name written on it. Nobody reading it sees whose hand wrote it unless the
# writer signed it: the hands are kept on the paper's state, for whoever later learns to compare them.
ROOM = 1200  # letters a leaf holds; a book says its own (`room`)
WRITTEN = "A written leaf"  # what a blank leaf is called once written on; names are one to a world, so (2), (3)...

def free_name(ctx, base):
    for n in range(1, 200):
        name = base if n == 1 else base + " (" + str(n) + ")"
        taken = False
        for e in ctx.find(name=name, limit=20):
            if (e.name or "").lower() == name.lower():
                taken = True
        if not taken:
            return name
    return None

def words_of(ctx):
    return str((ctx.params or {}).get("text") or "").strip()

def check(ctx):
    it = ctx.target
    if it.parent is None or it.parent.id != ctx.actor.id:
        return "you can only write on a paper in your own hands: take it first"
    words = words_of(ctx)
    if not words:
        return "say what you write: params {\"text\": the words}"
    left = int(it.state.room or ROOM) - len(it.state.text or "")
    if len(words) > left:
        return "there is room for " + str(max(0, left)) + " more letters on it: write less, or find fresh paper"
    return True

def apply(ctx):
    it = ctx.target
    words = words_of(ctx)
    text = it.state.text or ""
    hands = list(it.state.hands or [])
    if ctx.actor.id not in hands:
        hands.append(ctx.actor.id)
    changes = {"text": words if not text else text + "\n" + words, "hands": hands, "blank": False}
    if ", blank," in (it.state.description or ""):
        changes["description"] = it.state.description.replace(", blank,", ", inked in a hand,")
    ctx.patch(it, changes)
    if it.name == "A blank leaf":
        name = free_name(ctx, WRITTEN)
        if name:
            ctx.rename(it, name)
    ctx.emit("wrote", target=it, reach=0, by=ctx.actor.id, text=words)
    if ctx.actor.parent is not None:
        # a book (it says its own room) is written in, a leaf on; only the article drops its capital
        parts = it.name.split(" ", 1)
        shown = parts[0].lower() + " " + parts[1] if len(parts) == 2 and parts[0] in ("A", "An", "The") else it.name
        ctx.emit("scene", target=ctx.actor.parent, reach=1, text=ctx.actor.name + (" writes in " if it.state.room else
                 " writes on ") + shown + ".")
    return "written: " + words
