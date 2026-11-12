# Corin's file (Nate 2026-11-11): the Reach has more sides and more people in it than when the Hold took the gate,
# and Captain Ruhl wants a second hand who can take men out past the wall and bring them back. He has settled on
# Corin Vass. The first time Corin talks to him (or speaks to him by name), Ruhl gives him a file of three: Brannoc
# Hale and Lute Callow with bows off the pegs at the wall stair, Osk Barran with the Hold's one boar spear. Their
# blades go up on the practice rack in the yard. Made once: the story keeps `corin_file` with the three ids.
LEADER = "Corin Vass"
CAPTAIN = "Captain Ruhl"
FILE = [("Brannoc Hale", "bow"), ("Lute Callow", "bow"), ("Osk Barran", "spear")]
BOW = {"weapon": True, "damage": 2, "bonus": 1, "portable": True, "issued_by": "Captain Ruhl",
       "description": "One of the Hold's six short bows, taken down off its peg at the wall stair, with a quiver of a dozen "
                      "arrows. The Varrick boar is burned small into the grip."}
SPEAR = {"weapon": True, "damage": 2, "bonus": 1, "portable": True, "issued_by": "Captain Ruhl",
         "description": "The Hold's one boar spear, from before the writ: an ash shaft dark with hands, a broad head with a "
                        "crossbar under it so whatever is on it cannot climb the shaft to you."}
PEGS = ("Four short bows on pegs at the foot of the wall stair, strung, arrows standing in a jar beside them, and two "
        "empty pegs: Corin's file carries those. What the Hold has for anything past the gate.")

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def by_name(ctx, name):
    for e in ctx.find(name=name, limit=10):
        if e.name == name:
            return e
    return None

def held_blade(who):
    for it in who.children():
        if it.state.weapon:
            return it
    return None

def on(ctx, event):
    k = event.kind
    if k != "talked" and k != "say":
        return
    story = story_of(ctx)
    if story.state.corin_file:
        return
    captain = by_name(ctx, CAPTAIN)
    leader = by_name(ctx, LEADER)
    if captain is None or leader is None or event.target != captain.id:
        return
    p = event.payload or {}
    speaker = p.get("by") or event.actor
    if speaker != leader.id or leader.state.dead or captain.state.dead:
        return
    if leader.parent is None or captain.parent is None or leader.parent.id != captain.parent.id:
        return
    rack = by_name(ctx, "Rack of practice blades")
    pegs = by_name(ctx, "Bows on the wall")
    ids = []
    names = []
    for name, arm in FILE:
        man = by_name(ctx, name)
        if man is None or man.state.dead:
            continue
        blade = held_blade(man)
        if blade is not None and rack is not None:
            ctx.move(blade, rack)
        if arm == "bow":
            ctx.spawn("thing", man, "Varrick bow", state=dict(BOW))
        else:
            ctx.spawn("thing", man, "The Hold's boar spear", state=dict(SPEAR))
        # a file of men nobody plays goes where its leader goes (village go moves whoever follows the walker), and
        # off the Hold's post, or the walk back from water would take them home from wherever he led them
        ctx.patch(man, {"file_of": leader.id, "follows": leader.id, "post": None})
        others = []
        for pair in FILE:
            if pair[0] != name:
                others.append(pair[0])
        ctx.remember(man, "Captain Ruhl put me in Corin Vass's file, with " + " and ".join(others)
                     + ". Corin says where we go and when; the captain is still over all of us. I carry a "
                     + ("bow off the pegs" if arm == "bow" else "the Hold's boar spear") + " now, my blade is on the rack.")
        ids.append(man.id)
        names.append(name)
    if not ids:
        return
    if pegs is not None:
        ctx.patch(pegs, {"description": PEGS})
    ctx.patch(leader, {"file": ids, "rank": "file leader"})
    ctx.patch(story, {"corin_file": ids})
    ctx.remember(leader, "Captain Ruhl gave me a file of my own: " + ", ".join(names) + ". Two bows and a spear. I say "
                 "where they go and when, and bring them back; he is still over all of us.")
    ctx.remember(captain, "I gave Corin Vass his file: " + ", ".join(names) + ". Two bows off the pegs and the boar spear.")
    ctx.emit("scene", target=captain.parent, reach=1,
             text=CAPTAIN + " hears Corin out, then turns and calls three names down the yard: " + ", ".join(names)
             + ". Two bows come down off the pegs at the wall stair and the old boar spear out from behind the cistern "
             "steps; three blades go up on the practice rack. 'Corin Vass has a file,' Ruhl says. 'You three are it. "
             "He says where, I say whether. Bring each other back.'")
    ctx.emit("file_given", target=leader, reach=1, by=captain.id, men=ids)
