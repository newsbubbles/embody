# The Guild's speakers (notes/the-guild-speakers.md, Nate 2026-11-11): a palm slab of dark glass cut from the one
# mother crystal aboard the High Landing, so what one sister is made to show, the others can be made to show. Ember
# burned in its heart wakes it. Verbs, on the slab in your hand:
#   call (to, words, seen): a live line; the far slab stands up a hologram of `seen` saying `words`, and its room sees it
#   send (to, words, seen; or forward: a message's number here): stored on the far slab until someone reads it
#   read (clear: true to empty it after): what waits on this slab, picture and all, oldest first
#   contacts (add: a line's name): the lines this slab knows; a line that reaches it is learned
#   charge (count): burn emberglass you hold into the slab, a shard a call, a shard for three messages
# The network tells the truth about one thing: which slab a call came from. The face and the words are the caller's.
# A slab that comes into new hands wakes once for them with the Guild's primer: what it is, how it works, what it is for.
WORDS_MAX = 400
SEEN_MAX = 300
PER_SHARD = 3  # stored messages a shard pays for
PRIMER = ("The slab wakes in your hand the first time and a small ember-coloured figure stands up out of it, a Guild "
          "clerk's face, and recites: 'This is a speaker of the Carriers' Guild. Its glass was cut from the mother "
          "crystal aboard the High Landing, the slow star, and every speaker is a sister of every other: what one is made "
          "to show, the rest can be made to show, across any distance. Ember in its heart wakes it; a call burns a shard, "
          "three stored messages burn one. Call a line and your words and your picture stand up out of the far slab, "
          "live; send, and they wait there until read. The line you call from is always told true. The face is "
          "whatever you give it. The Guild keeps the lines; the slab is the Guild's, wherever it is carried.'")


def held(ctx):
    me = ctx.self
    return me.parent is not None and me.parent.id == ctx.actor.id

def lines(ctx):
    out = []
    for e in ctx.find(type="speaker", limit=50):
        if e.state.line and not e.state.broken:
            out.append(e)
    return out

def find_line(ctx, want):
    want = str(want or "").strip().lower()
    if not want:
        return None
    for e in lines(ctx):
        if e.id != ctx.self.id and (str(e.state.line).lower() == want or e.name.lower() == want):
            return e
    for e in lines(ctx):
        n = str(e.state.line).lower()
        if e.id != ctx.self.id and len(want) >= 4 and (want in n or want in e.name.lower()):
            return e
    return None

def known(ctx):
    return list(ctx.self.state.contacts or [])

def learn(ctx, slab, line):
    have = list(slab.state.contacts or [])
    if line and line not in have and line != slab.state.line:
        have.append(line)
        ctx.patch(slab, {"contacts": have})

def clip(s, n):
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + "..."

def bodied(e):
    return e is not None and e.type != "place" and e.state.vigor is not None

def where_of(slab):
    # who holds it, and the place its picture stands up in; a slab shut in a box or a pack shows to nobody
    p = slab.parent
    if p is None:
        return None, None
    if p.type == "place":
        return None, p
    if bodied(p):
        return p, p.parent
    return None, None

def dark():
    return "the slab is dark: no ember in it. Charge it with emberglass you carry (charge, params {\"count\": n})"

def check(ctx):
    v = ctx.verb
    if not held(ctx):
        return "take the speaker in hand first: its verbs work for whoever holds it"
    if ctx.actor.state.down:
        return "you are down"
    me = ctx.self
    if me.state.broken:
        return "the slab is cracked through and stays dark"
    pr = ctx.params or {}
    if v == "charge":
        n = int(pr.get("count") or 1)
        have = ctx.count(ctx.actor, "ember")
        if n < 1:
            return "charge it with one shard or more: params {\"count\": n}"
        if have < n:
            return "you hold " + str(have) + " emberglass; the slab burns shards you carry"
        return True
    if v == "read":
        return True
    if v == "contacts":
        if pr.get("add") and find_line(ctx, pr.get("add")) is None:
            return "no speaker answers to that name. The lines this one knows: " + (", ".join(known(ctx)) or "none yet")
        return True
    if v == "send" and pr.get("forward") is not None:
        n = len(me.state.inbox or [])
        i = int(pr.get("forward") or 0)
        if i < 1 or i > n:
            return "forward which? params {\"forward\": the number read shows, \"to\": a line}; " + str(n) + " wait here"
    elif not pr.get("words") and not pr.get("seen"):
        return "say something: params {\"to\": a line, \"words\": what you say, \"seen\": what your picture shows}"
    if not pr.get("to"):
        return "which line? params {\"to\": ...}; this one knows " + (", ".join(known(ctx)) or "no lines yet")
    if find_line(ctx, pr.get("to")) is None:
        return "no speaker answers to " + str(pr.get("to")) + ". This one knows: " + (", ".join(known(ctx)) or "none yet")
    if v == "call" and int(me.state.charge or 0) < 1:
        return dark()
    if v == "send" and int(me.state.charge or 0) < 1 and int(me.state.sent or 0) % PER_SHARD == 0:
        return dark()
    return True

def charge(ctx, me, n):
    left = n
    for it in ctx.actor.children():
        if left > 0 and it.state.kind == "ember":
            k = min(left, ctx.count(it))
            ctx.destroy(ctx.split(it, k))
            left = left - k
    total = int(me.state.charge or 0) + n
    ctx.patch(me, {"charge": total})
    ctx.emit("scene", target=ctx.actor.parent, reach=1, text=ctx.actor.name + " presses emberglass to the back of a dark "
             "glass slab; the shard dulls to grey and the slab's seal glows the colour the shard was.")
    return "The slab drinks " + str(n) + (" shard" if n == 1 else " shards") + ". Charge: " + str(total) + "."

def read(ctx, me, clear):
    box = list(me.state.inbox or [])
    if not box:
        return "Nothing waits on " + str(me.state.line) + "."
    out = []
    i = 0
    for m in box:
        i = i + 1
        head = str(i) + ". from " + str(m.get("from"))
        if m.get("fwd"):
            head = head + " (forwarded; first sent from " + str(m.get("fwd")) + ")"
        out.append(head + ": the picture shows " + (m.get("seen") or "nothing, a blank flicker") + "; it says: '"
                   + (m.get("words") or "") + "'")
    if clear:
        ctx.patch(me, {"inbox": []})
    ctx.emit("scene", target=ctx.actor.parent, reach=1, text="Small ember-coloured figures stand up one after another out "
             "of the slab in " + ctx.actor.name + "'s hand, speak, and fold away.")
    return " | ".join(out)

def apply(ctx):
    v = ctx.verb
    me = ctx.self
    pr = ctx.params or {}
    if v == "charge":
        return charge(ctx, me, int(pr.get("count") or 1))
    if v == "read":
        return read(ctx, me, pr.get("clear"))
    if v == "contacts":
        if pr.get("add"):
            learn(ctx, me, find_line(ctx, pr.get("add")).state.line)
        have = list(ctx.get(me.id).state.contacts or [])
        return ("This slab is " + str(me.state.line) + ". It knows: " + (", ".join(have) or "no lines yet") +
                ". Charge: " + str(int(me.state.charge or 0)) + ".")
    far = find_line(ctx, pr.get("to"))
    src = str(me.state.line)
    learn(ctx, me, far.state.line)
    learn(ctx, far, src)
    if v == "send" and pr.get("forward") is not None:
        m = dict(list(me.state.inbox or [])[int(pr.get("forward")) - 1])
        msg = {"from": src, "words": m.get("words"), "seen": m.get("seen"), "t": ctx.t, "fwd": m.get("fwd") or m.get("from")}
    else:
        msg = {"from": src, "words": clip(pr.get("words"), WORDS_MAX), "seen": clip(pr.get("seen"), SEEN_MAX), "t": ctx.t}
    holder, room = where_of(far)
    if v == "call":
        ctx.patch(me, {"charge": int(me.state.charge or 0) - 1})
        ctx.emit("scene", target=ctx.actor.parent, reach=1, text=ctx.actor.name + " holds up a dark glass slab and talks "
                 "into it; a thread of ember light stands up off it toward the sky.")
        if room is None:
            return ("The line to " + str(far.state.line) + " rings in the dark: nobody there to see it, or the slab is "
                    "shut away. Send instead and it waits.")
        at = ("the slab in " + holder.name + "'s hand") if holder is not None else far.name
        ctx.emit("scene", target=room, reach=1, text="A hologram stands up out of " + at + ", small and ember-coloured, "
                 "flickering at its edges: " + (msg["seen"] or "a blank flicker") + ". It speaks: '" + (msg["words"] or "")
                 + "' The slab names its line: " + src + ".")
        ctx.emit("speaker_call", target=holder if holder is not None else far, reach=0, line=src, words=msg["words"],
                 seen=msg["seen"], slab=far.id)
        return ("Your picture stands up at " + str(far.state.line) + (" in " + holder.name + "'s hand" if holder is not None
                else "") + ". Charge left: " + str(int(me.state.charge or 0) - 1) + ". They answer by calling you back.")
    sent = int(me.state.sent or 0)
    left = int(me.state.charge or 0)
    if sent % PER_SHARD == 0:
        left = left - 1
    ctx.patch(me, {"sent": sent + 1, "charge": left})
    box = list(far.state.inbox or [])
    box.append(msg)
    ctx.patch(far, {"inbox": box[-20:]})
    if holder is not None:
        ctx.emit("scene", target=holder, reach=0, text="The slab you carry warms once against you: a message waits on "
                 + str(far.state.line) + ", from " + src + ". The speaker's read shows it.")
    ctx.emit("speaker_message", target=holder if holder is not None else far, reach=0, line=src, slab=far.id)
    return "Stored on " + str(far.state.line) + ". Charge left: " + str(left) + "."

def on(ctx, event):
    # taken off a table, or handed on (reach_speakers.py turns a give or the Guild's hand-over into slab_handed)
    me = ctx.self
    holder = me.parent
    if not bodied(holder):
        return
    seen = list(me.state.primed or [])
    if holder.id in seen:
        return
    seen.append(holder.id)
    ctx.patch(me, {"primed": seen})
    ctx.emit("scene", target=holder, reach=0, text=PRIMER + " This one is " + str(me.state.line) + "; it knows "
             + (", ".join(me.state.contacts or []) or "no lines yet") + ". Charge: " + str(int(me.state.charge or 0)) + ".")
    ctx.remember(holder, "I carry " + me.name + ", a Guild speaker (" + str(me.state.line) + "). " + PRIMER)
