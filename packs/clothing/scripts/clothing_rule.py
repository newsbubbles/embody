use("clothing")

# The pack's rule on the root (install_rules): a worn thing is not handed over, put down, laid on a rack or burned
# until it is taken off; a place's dress_code is kept at its door by what the door can see; and when a thing leaves a
# body by any verb (given, taken, lifted from a sleeper, burned), both bodies' attire is set again.

MOVES = ["given", "dropped", "put", "taken", "lifted", "burned"]
GUARDED = ["give", "drop", "put", "burn"]
BARS = {"armor": "armour shows", "weapon": "a weapon shows", "drawn": "a weapon is drawn",
        "masked": "the face is covered", "barefoot": "the feet are bare"}

def on(ctx, event):
    if event.kind == "before_act":
        guard(ctx, event)
        return
    if event.kind not in MOVES:
        return
    p = event.payload or {}
    seen = []
    for i in [event.actor, event.target, p.get("by"), p.get("sleeper"), p.get("source")]:
        if i and i not in seen:
            seen.append(i)
            b = ctx.get(i)
            if b is not None and b.is_a("creature"):
                refresh(ctx, b)

def guard(ctx, event):
    p = event.payload or {}
    verb = p.get("verb")
    if verb not in GUARDED and verb != "go":
        return
    me = ctx.get(event.actor) if event.actor else None
    if me is None:
        return
    if verb == "go":
        place = ctx.get(event.target) if event.target else None
        if place is not None and place.state.dress_code:
            dress_code(ctx, me, place)
        return
    prm = p.get("params") or {}
    it = None
    if verb in ["give", "put"] and prm.get("item"):
        it = find_held(me, prm.get("item"))
    elif event.target:
        t = ctx.get(event.target)
        if t is not None and t.parent is not None and t.parent.id == me.id:
            it = t
    if it is not None and on_me(me, it) and (it.state.worn or it.state.donning):
        ctx.reject("you are wearing " + it.name + ": take it off first", "remove " + it.name + ", then " + verb + " it")

def dress_code(ctx, me, place):
    dc = place.state.dress_code
    tags, dressed = visible_tags(me)
    wrong = []
    for n in dc.get("needs") or []:
        if n.startswith("tag:"):
            if n[4:] not in tags:
                wrong.append("no " + n[4:].replace("_", " ") + " shows")
        elif n not in dressed:
            wrong.append("nothing covers the " + n)
    for b in dc.get("bars") or []:
        if b in tags:
            wrong.append(BARS.get(b) or (b.replace("_", " ") + " shows"))
    if wrong:
        why = dc.get("why") or (place.name + " keeps a dress code")
        ctx.reject(why + ": " + join_and(wrong), "dress for it (wear, remove, adjust, stow) and go again")
