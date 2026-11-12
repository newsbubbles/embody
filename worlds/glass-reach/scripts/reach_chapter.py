# Chapter two: the moon turns. It begins at the first dawn after chapter one is done and both a Dreyer newcomer and a
# Guild newcomer are in the world (a template body is only ever made by someone joining), or when the host schedules
# `chapter_two_begins`; the crawler brings the news, and the moon turns twelve days later (three real days at 4x). Until then the truce can strain and break, Hollis's letter can reach Taan, Wick's note can reach Hollis,
# and the Thresher can die. When the moon turns the world reckons from facts, not from a stage: the truce, the men on
# the Hold's wall, the Hold's water, and where Hollis is.
MOON_AFTER = 1036800  # twelve world days: three real days at the hosted rate, time for the Reach to fill and choose
WALL = 9  # men on their feet in the Hold and the yard that the riders count as a held wall
KETH_BOWS = 3  # Keth on the wall at the moon, when Taan has proof and the truce still stands
BEATS = [(259200, "convoy_word"), (518400, "rook_arrives"), (777600, "riders_fires"), (950400, "herald_comes")]  # the herald: the day before the moon
DRY = 4  # draws in the Keth jars and the ration cask together, below which the Hold is called thirsty

def scene(ctx, place, text):
    if place is not None:
        ctx.emit("scene", target=place, reach=1, text=text)

def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def by_name(ctx, name):
    got = ctx.find(name=name, limit=5)
    for e in got:
        if e.name == name:
            return e
    return None

def begin(ctx, story):
    st = story.state
    ctx.patch(story, {"chapter": 2, "moon_due": ctx.t + MOON_AFTER, "strain": 0})
    ctx.patch(ctx.root(), {"story": "chapter two: the moon turns", "chapter": 2})
    ctx.schedule(MOON_AFTER, "moon_turns", target=ctx.root())
    for b in BEATS:  # the middle of the chapter, in scripts/reach_moon.py
        ctx.schedule(b[0], b[1], target=ctx.root())
    scene(ctx, st.landing, "The dawn crawler comes in with its dust and its driver talking before the engine stops. Riders on the "
                           "south road, twelve days out, under a pennant with a well and a bar across it. Dreyer. 'And the "
                           "convoy goes north at the moon's turn, same as the tally says. Whoever wants carrying had better "
                           "say so before.'")
    scene(ctx, st.hold, "The crawler's driver says it twice at the gate, so nobody can say they did not hear: Dreyer riders on "
                        "the south road. The moon turns in twelve nights.")
    scene(ctx, st.deepwell, "Word comes down the broken step with the morning: riders under Dreyer's pennant in the south dunes. "
                            "The cups on their cords go still while the camp listens.")
    scene(ctx, st.dry_camp, "A rider comes in off the south road at first light and kneels to Halvard Dreyer. The house's riders "
                            "are twelve nights out. The moon turns, and they come up.")
    notice = by_name(ctx, "Notice by the cistern")
    if notice is not None:
        ctx.patch(notice, {"text": "BY ORDER OF THE REEVE. Dreyer riders are on the south road and will be at the Reach when "
                                   "the moon turns, in twelve nights. Every man to the wall at the moon. Water is drawn by "
                                   "the captain's count. The truce with the Keth holds: no man of the Hold digs glass or "
                                   "draws steel on a Keth. Anyone who knows Dreyer's business in the Reach brings it to the "
                                   "reeve."})
    ctx.emit("chapter_two", target=ctx.root(), reach=-1, moon_due=ctx.t + MOON_AFTER)

def break_truce(ctx, story, why):
    st = story.state
    ctx.patch(story, {"truce": False, "truce_broken": why, "truce_broken_t": ctx.t})
    keth = ctx.get(st.keth)
    if keth is not None:
        for r in ctx.relations(keth, "truce"):
            ctx.unrelate(r["id"])
    taan = ctx.get(st.taan)
    if taan is not None:
        ctx.patch(taan, {"dialog": {"water|well|truce": "'There were terms. The Hold broke them. Go home and drink sand.'"}})
    scene(ctx, st.deepwell, "Taan takes the Hold's cup off its cord and pours it out on the stone. 'The terms are broken. No "
                            "water goes up the road at dusk.'")
    ctx.emit("truce_broken", target=ctx.root(), reach=-1, why=why)

DUG_BY = {"House Dreyer": "Sand wraps and a long glass, the Keth watchers say. Dreyer's. 'The house that poisoned the "
                          "Low Well digs our glass now,' Taan says. 'The Hold's terms stand. Dreyer has none.'",
          "the Carriers": "A Guild coat on the Flats with a spade, the Keth watchers say. Taan says nothing for a while. "
                          "'The Guild takes its cut of everything. Now it takes the ground.'"}

def outsider_dig(ctx, story, digger):
    side = str(digger.state.faction or "a stranger")
    grudges = dict(story.state.keth_grudges or {})
    grudges[side] = int(grudges.get(side) or 0) + 1
    ctx.patch(story, {"keth_grudges": grudges})
    scene(ctx, story.state.deepwell, DUG_BY.get(side, "Someone dug the Flats, the Keth watchers say, and not in a Hold "
                                                     "coat. 'Not the Hold's doing,' Taan says. 'Find out whose.'"))
    ctx.emit("keth_grudge", target=ctx.root(), reach=-1, side=side, n=grudges[side])

def mend_truce(ctx, story):
    # the host's mend (2026-11-12): the truce broke on two digs by Dreyer men under the old rule, which blamed the Hold
    st = story.state
    if st.truce:
        return
    keth = ctx.get(st.keth)
    side = ctx.find(type="faction", name="House Varrick", limit=1)
    if keth is not None and side:
        ctx.relate("truce", [keth.id, side[0].id], {"terms": "water at dusk, the Flats quiet", "since": ctx.t, "public": True})
    ctx.patch(story, {"truce": True, "strain": 0, "truce_broken": None, "truce_broken_t": None})
    taan = ctx.get(st.taan)
    if taan is not None:
        ctx.patch(taan, {"dialog": {"water|well|truce": "We have terms. Keth water goes up the road at dusk and the Flats stay "
                                                        "quiet. Keep it so."}})
    scene(ctx, st.deepwell, "Sefa comes down the broken step and speaks to Taan a long time: the digger on the Flats wore "
                            "sand wraps and carried a long glass, no Hold coat. Taan hangs the Hold's cup back on its cord. "
                            "'The Hold did not break the terms. Dreyer wants us to think it did. The water goes up at dusk.'")
    scene(ctx, st.hold, "A Keth runner comes to the gate in the dark and says it once: the terms stand. It was Dreyer on the "
                        "Flats, not the Hold. The water comes.")
    ctx.emit("truce_restored", target=ctx.root(), reach=-1)

def strain(ctx, story, why):
    st = story.state
    if not st.truce:
        return
    n = int(st.strain or 0) + 1
    ctx.patch(story, {"strain": n})
    if n >= 2:
        break_truce(ctx, story, why)
    else:
        scene(ctx, st.deepwell, "Taan hears what was done on the Flats and says nothing for a long time. 'Once,' she says.")
        ctx.emit("truce_strained", target=ctx.root(), reach=-1, why=why, strain=n)

def courses(b):
    # the wall works (packs/works): every course laid and set stands as a man; one still setting does not yet
    bs = b.state
    if bs.wall_men:
        return int(bs.wall_men)
    want = ((bs.becomes or {}).get("state") or {}).get("wall_men")
    if b.type != "project" or not want:
        return 0
    n = len(bs.built_stages or [])
    if bs.settling_until is not None:
        n = n - 1
    return max(0, n)

def wall_and_water(ctx, st):
    # a bought man on the wall is worse than none: he counts against it. Keth bows stand on it with proof and the truce.
    men = 0
    bought = 0
    for pid in [st.hold, st.yard]:
        for b in ctx.children(pid):
            bs = b.state
            if bs.faction == "House Varrick" and not bs.dead and not bs.down:
                if bs.turncoat:
                    bought = bought + 1
                else:
                    men = men + 1
    men = men - bought
    for b in ctx.children(st.yard):
        men = men + courses(b)
    if st.keth_proof and st.truce:
        men = men + KETH_BOWS
    water = 0
    wids = [st.keth_jars, st.hold_ration]
    if st.cistern_mended:
        wids.append(st.cistern)
    for wid in wids:
        w = ctx.get(wid) if wid else None
        if w is not None:
            water = water + int(w.state.left or 0)
    for pid in [st.hold, st.yard]:  # a dew still built in the Hold or its yard
        for it in ctx.children(pid, "thing"):
            if it.state.dew:
                water = water + int(it.state.left or 0)
    return men, water, bought

def riders_need(ctx, st):
    # men on the wall that turn the riders back (scripts/reach_riders.py): the riders on their feet in the Hollow and
    # two for the caltrops while the gate plan is still the house's. Fewer with no captain, dry with their cart
    # spoiled or run low, unpaid with the paychest empty of glass. Before the muster, the wall the riders were told of.
    if not st.riders_mustered or not st.riders_hollow:
        return WALL
    hollow = ctx.get(st.riders_hollow)
    if hollow is None:
        return WALL
    n = 0
    captain = False
    for c in ctx.children(hollow, "creature"):
        if c.state.rider and not c.state.dead and not c.state.down:
            n = n + 1
            if c.state.captain:
                captain = True
    if not captain:
        n = n - 2
    cart = ctx.get(st.riders_cart) if st.riders_cart else None
    if cart is None or cart.state.spoiled or int(cart.state.left or 0) < 3:
        n = n - 3
    chest = ctx.get(st.riders_chest) if st.riders_chest else None
    glass = 0
    if chest is not None:
        for it in ctx.children(chest):
            if it.state.kind == "ember":
                glass = glass + int(it.state.count or 1)
    if glass == 0:
        n = n - 2
    plan = ctx.get(st.riders_plan) if st.riders_plan else None
    if plan is not None and not plan.state.built:
        holder = plan.parent
        if holder is not None and (holder.id == hollow.id or holder.state.faction == "House Dreyer"):
            n = n + 2
    return max(3, n)

def reckon(ctx, story):
    st = story.state
    men, water, bought = wall_and_water(ctx, st)
    need = riders_need(ctx, st)
    dram = ctx.get(st.dram)
    where = "gone"
    if dram is not None and dram.state.dead:
        where = "dead"
    elif dram is not None and dram.parent is not None and dram.parent.id in [st.hold, st.yard]:
        where = "held"
    if st.writ_given:
        outcome = "yielded"
    elif st.truce and men >= need and water >= DRY and st.convoy_to != "House Dreyer":
        outcome = "held"
    elif not st.truce and (men < need or water < DRY):
        outcome = "fallen"
    else:
        outcome = "siege"
    ctx.patch(story, {"moon_turned": True, "outcome": outcome,
                      "reckoning": {"truce": bool(st.truce), "wall": men, "water": water, "hollis": where, "bought": bought,
                                    "keth_bows": bool(st.keth_proof and st.truce), "cistern": bool(st.cistern_mended),
                                    "convoy": st.convoy_to, "writ": bool(st.writ_given), "riders": need}})
    ctx.patch(ctx.root(), {"story": "chapter two: " + outcome})
    if outcome == "yielded":
        scene(ctx, st.hold, "The moon turns. The gate stands open, as the writ's new holder asked. Dreyer's riders come "
                            "up out of the south dunes at a walk, and the men of the Hold go north on the Salt Road with "
                            "full skins and nothing else.")
        scene(ctx, st.dry_camp, "Halvard Dreyer rides north with the writ in his coat. 'No blood,' he says. 'The Crown "
                                "likes a clean seal.'")
    elif outcome == "held":
        scene(ctx, st.hold, "The moon turns. Dreyer's riders come up out of the south dunes in the last light and stop at the "
                            "edge of the Flats. They count the men on the wall, and the Keth fires on Red Ridge, and they "
                            "count again. Then they turn back into the dark.")
        scene(ctx, st.dry_camp, "Halvard Dreyer watches the riders turn and says only, 'Not this moon.'")
    elif outcome == "fallen":
        scene(ctx, st.hold, "The moon turns. Dreyer's riders come up the south dunes in the dark, and there are not men enough "
                            "on the wall, nor water enough behind it. By morning a pennant with a well and a bar across it "
                            "hangs from Scar Gate.")
        scene(ctx, st.deepwell, "Taan hears the riders go by above and puts out the cookfire. 'Dreyer again. We drink in the dark.'")
    else:
        scene(ctx, st.hold, "The moon turns. Dreyer's riders come up out of the south dunes and do not charge the gate: they make "
                            "camp in the Bone Field, in plain sight, and light their fires. A siege, then.")
        scene(ctx, st.dry_camp, "Halvard Dreyer rides out to meet the house's riders at the Bone Field. 'We wait,' he says. "
                                "'They are thirstier than we are.'")
    ctx.emit("moon_turned", target=ctx.root(), reach=-1, outcome=outcome, wall=men, water=water, hollis=where, bought=bought, riders=need)

def newcomers(ctx, story):
    # who has come in from the templates so far: a Dreyer man, a Guild carrier
    st = story.state
    changes = {}
    for b in ctx.find(type="person", limit=500):
        kind = b.state.template
        if kind == "dreyer" and not st.dreyer_came:
            changes["dreyer_came"] = b.id
        elif kind == "carrier" and not st.guild_came:
            changes["guild_came"] = b.id
    if changes:
        ctx.patch(story, changes)

def on(ctx, event):
    story = story_of(ctx)
    st = story.state
    k = event.kind
    p = event.payload
    if k == "chapter_two_begins":
        # the host's word: begin now, whoever has come in so far
        if not st.chapter and not st.reeve_dead:
            newcomers(ctx, story)
            begin(ctx, story_of(ctx))
        return
    if k == "dawn":
        if st.chapter or not st.done or st.reeve_dead:
            return
        newcomers(ctx, story)
        story = story_of(ctx)
        if story.state.dreyer_came and story.state.guild_came:
            begin(ctx, story)
        return
    if st.chapter != 2 or st.moon_turned:
        return
    if k == "moon_turns":
        reckon(ctx, story)
    elif k == "harvested":
        # the terms are the Hold's: a Hold man digging strains them (a bought man in a Varrick coat too, which is the
        # house's way to break them). Anyone else digging is a grievance the Keth hold against his own side.
        digger = ctx.get(p.get("by"))
        if digger is None or digger.state.faction == "the Keth":
            return
        if digger.state.faction == "House Varrick":
            strain(ctx, story, "glass dug on the Flats")
        else:
            outsider_dig(ctx, story, digger)
    elif k == "truce_mended":
        mend_truce(ctx, story)
    elif k in ["downed", "killed"]:
        hurt = ctx.get(event.target)
        if event.target == st.worm and k == "killed" and not st.thresher_dead:
            ctx.patch(story, {"thresher_dead": True})
            scene(ctx, st.flats, "The sand goes still in a way it has not been still in anyone's life. Somewhere under the "
                                 "Flats, nothing is listening any more.")
            return
        if hurt is None or hurt.state.faction != "the Keth":
            return
        by = ctx.get(p.get("by")) if p.get("by") else None
        if by is None or by.state.faction == "the Keth":
            return
        if k == "killed":
            break_truce(ctx, story, "a Keth killed by " + str(by.state.faction))
        else:
            strain(ctx, story, "a Keth cut down by " + str(by.state.faction))
    elif k == "given":
        it = ctx.get(p.get("item"))
        if it is None:
            return
        if it.name == "Sealed note for Hollis" and event.target == st.dram and not st.note_delivered:
            ctx.patch(story, {"note_delivered": True})
        elif it.name == "Sealed letter" and event.target == st.taan and not st.letter_shown:
            ctx.patch(story, {"letter_shown": True, "strain": 0})
            scene(ctx, st.deepwell, "Taan holds the letter close to the fire and reads the house's hand twice. 'Keep the Keth "
                                    "thirsty,' she says aloud, and the whole cave hears it. 'So. Now we know who wanted us dry.'")
