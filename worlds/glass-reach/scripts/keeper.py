# A keeper (Nate 2026-11-12): a body that holds something for one person, or for a rank above them, and passes word
# once to the first of the right people who comes in. The same rule sits on the keeper (for `talked` and `keeper_word`,
# so it speaks in the keeper's voice) and on the keeper's place (for `arrived`, which it turns into a `keeper_word` for
# the keeper a moment later). What the keeper says and holds is all on its state, so a world sets it live:
#   keeps: {"item": a thing the keeper holds, "for": [names], "ids": [ids], "ranks": [ranks], "topics": "key|door|...",
#           "yes": what it says handing it over, "no": what it says to anyone else, "gone": once it is given,
#           "yes_letter": what it says handing it over on a written word, "letters": False to refuse written words}
# A written word counts (2026-11-12, Pell came to Hask with the wright's signed leaf and the key would not move): a
# leaf the asker holds, written in the hand of one the thing is kept for, that names the asker, is that one asking.
#   passes_word: {"to": [names], "line": what it says to the first of them to come in, "memory": what that one
#                 remembers of it (default the line), "done": False}
# The keeper's dialog should carry the same topics with an empty line, so the table stays quiet and this speaks.

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

def may(k, who):
    if who.name in (k.get("for") or []) or who.id in (k.get("ids") or []):
        return True
    rank = who.state.rank or who.state.guild_rank
    return rank is not None and rank in (k.get("ranks") or [])

def by_letter(ctx, k, who):
    if k.get("letters") is False:
        return None
    for p in who.children():
        if who.name.lower() not in str(p.state.text or "").lower():
            continue
        for h in (p.state.hands or []):
            h = str(h)
            if h in (k.get("ids") or []):
                return p
            w = ctx.get(h) if h[:1] == "e" and h[1:].isdigit() else None
            if w is not None and may(k, w):
                return p
    return None

def held(ctx, keeper, name):
    for it in keeper.children():
        if (it.name or "").lower() == str(name or "").lower():
            return it
    return None

def talked(ctx, event, keeper):
    who = ctx.get((event.payload or {}).get("by"))
    if event.target != keeper.id or who is None:
        return
    k = keeper.state.keeps
    if not k or ctx.embodied(keeper) or not matches(k.get("topics"), (event.payload or {}).get("about")):
        return
    it = held(ctx, keeper, k.get("item"))
    if it is None:
        if k.get("gone"):
            ctx.say(k["gone"], to=who.id)
        return
    leaf = None if may(k, who) else by_letter(ctx, k, who)
    if leaf is None and not may(k, who):
        ctx.say(k.get("no") or "That is not for you.", to=who.id)
        return
    ctx.move(it, who)
    ctx.emit("given", target=who, reach=1, item=it.id, by=keeper.id)
    ctx.say((k.get("yes_letter") if leaf is not None else None) or k.get("yes") or "Here.", to=who.id)

def arrived(ctx, event, place):
    who = ctx.get((event.payload or {}).get("who"))
    if who is None or (event.payload or {}).get("place") != place.id:
        return
    for keeper in ctx.children(place, "creature"):
        w = keeper.state.passes_word
        if w and not w.get("done") and keeper.id != who.id and who.name in (w.get("to") or []):
            ctx.schedule(1, "keeper_word", keeper, {"who": who.id})

def word(ctx, event, keeper):
    w = keeper.state.passes_word
    who = ctx.get((event.payload or {}).get("who"))
    if not w or w.get("done") or who is None or ctx.embodied(keeper):
        return
    if who.parent is None or keeper.parent is None or who.parent.id != keeper.parent.id:
        return  # gone on before the word came out; the next of them will hear it
    ctx.say(w.get("line") or "", to=who.id)
    ctx.remember(who, w.get("memory") or w.get("line") or "")
    nw = dict(w)
    nw["done"] = True
    nw["told"] = who.id
    ctx.patch(keeper, {"passes_word": nw})

def on(ctx, event):
    me = ctx.self
    if event.kind == "talked":
        talked(ctx, event, me)
    elif event.kind == "keeper_word":
        word(ctx, event, me)
    elif event.kind == "arrived":
        arrived(ctx, event, me)
