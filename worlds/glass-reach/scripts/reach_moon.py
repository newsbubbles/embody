# Chapter two's middle: what the twelve days hold besides the waiting. Beats the chapter schedules when it begins
# (convoy_word on day three, rook_arrives on day six, riders_fires on day nine, herald_comes the day before the moon),
# and four contests the moon will count: the drifters at the Old Salt Works (paid by the Hold they go to the wall;
# bought by Dreyer they go too, and wait to open the gate), the cistern mended, the Keth shown proof, and the
# convoy's water sold to one side. Facts go on the story; reach_chapter's reckoning reads them.
CRAWLER_LOAD = 8  # draws the convoy crawler rolls into the Hold's cask when the Hold buys it
PRICE = 3  # shards of emberglass for the load
MEND_DC = 13


def story_of(ctx):
    return ctx.find(type="story", limit=1)[0]

def scene(ctx, place, text):
    if place is not None:
        ctx.emit("scene", target=place, reach=1, text=text)

def by_name(ctx, name):
    for e in ctx.find(name=name, limit=10):
        if e.name == name:
            return e
    return None

def is_pay(it):
    # what a drifter takes: a shard of emberglass, or a skin with water in it
    if it is None:
        return False
    if it.state.kind == "ember":
        return True
    return it.state.capacity is not None and int(it.state.left or 0) > 0

ROOK = {"faction": "the Carriers", "body": 3, "wits": 4, "will": 3, "skills": {"parley": 3, "lore": 1},
        "description": "A long sun-cured man in a convoy coat gone white at the seams, a ledger chained to his belt, and "
                       "a voice that carries over an engine.",
        "default_line": "Bellan Rook taps the ledger. 'Eight draws on the crawler. Three shards of glass and it rolls "
                        "where you say. Who are you buying for?'",
        "dialog": {"water|load|crawler|price|buy": "'Eight draws, sweet, from the Guild's own wells. Three shards of "
                                                   "emberglass, and it goes where the buyer says. First to pay.'",
                   "hold|varrick|reeve|gate|wall": "'For the Hold, then. Bring the glass and say so, and it rolls into "
                                                   "their cask.'",
                   "dreyer|house|south|dunes": "'Dreyer pays in glass like anyone. The Guild carries for whoever "
                                               "holds the gate, and the gate is not settled yet.'",
                   "ossa|guild|cut|tally": "'Ossa takes her cut either way. That is what a tally is for.'"}}
HERALD = {"faction": "House Dreyer", "body": 3, "wits": 3, "will": 4, "skills": {"parley": 3, "resolve": 2},
          "description": "A rider in a clean grey coat under a pennant with a well and a bar across it, unarmed, which "
                         "is its own kind of threat.",
          "default_line": "The herald does not raise his voice. 'Put the Crown's writ in my hand before the moon, and "
                          "every man in the Hold walks out with his water and his life.'",
          "dialog": {"terms|writ|yield|surrender": "'The writ, in my hand, before the moon. The house takes the gate "
                                                   "and the Flats. Every man walks north with a full skin. Refuse, and "
                                                   "we count your wall at the moon.'",
                     "riders|moon|how many": "'Enough. You will count them yourself at the moon if you make us.'",
                     "hollis|dram": "'I do not know the name.'"}}

def beat(ctx, k, st):
    root = ctx.root()
    if k == "convoy_word":
        for pid in [st.landing, st.hold, st.salt_works]:
            scene(ctx, ctx.get(pid) if pid else None, "Word comes up the road with a water-runner: Bellan Rook, the "
                  "convoy master, is three days out with a full crawler and no buyer for it yet. He sells his load to "
                  "whoever pays in glass.")
    elif k == "rook_arrives":
        if by_name(ctx, "Bellan Rook") is None and st.landing:
            landing = ctx.get(st.landing)
            rook = ctx.spawn("person", landing, name="Bellan Rook", state=dict(ROOK, post=st.landing, water=10,
                             max_water=10, secret=["dialog", "brokers", "paid", "word_left"]))
            ctx.spawn("thing", landing, name="The convoy crawler", state={"portable": False, "load": CRAWLER_LOAD,
                      "description": "A Guild crawler squatting on the pan, its tanks sweating in the shade of its own "
                                     "flank. Eight draws aboard, and they go where Bellan Rook says."})
            ctx.patch(story_of(ctx), {"rook": rook.id})
            scene(ctx, landing, "A crawler comes up off the Salt Road in its own dust and settles on the pan. A long man "
                  "in a white-seamed coat climbs down with a ledger on a chain. 'Bellan Rook. Eight draws aboard. Three "
                  "shards of glass and it goes where you say.'")
    elif k == "riders_fires":
        ctx.patch(story_of(ctx), {"riders_seen": True})
        for pid in [st.ridge, st.flats, st.bones]:
            scene(ctx, ctx.get(pid) if pid else None, "After dark the south dunes are lit: cookfires, a line of them, "
                  "more than anyone wants to count. Dreyer's riders are three nights out and not hiding it.")
        scene(ctx, ctx.get(st.dry_camp) if st.dry_camp else None, "Fires to the south, answering yours. The house's "
              "riders are close enough now to see the camp's smoke.")
    elif k == "herald_comes":
        if by_name(ctx, "Dreyer's herald") is None and st.yard:
            yard = ctx.get(st.yard)
            h = ctx.spawn("person", yard, name="Dreyer's herald", state=dict(HERALD, post=st.yard, water=10, max_water=10,
                          secret=["dialog", "word_left"]))
            ctx.patch(story_of(ctx), {"herald": h.id})
            writ = by_name(ctx, "The Crown's writ")
            if writ is not None:
                ctx.patch(writ, {"portable": True})
            scene(ctx, yard, "A rider comes up the road alone under a pennant with a well and a bar across it, unarmed, "
                  "and stops inside the gate. 'Terms from House Dreyer. The Crown's writ, in my hand, before the moon, "
                  "and every man here walks north with his water and his life.'")
            scene(ctx, ctx.get(st.hold), "Out in the yard, a Dreyer herald is speaking terms. The writ is on the wall "
                  "behind the reeve's chair, and for the first time it looks like something a man could carry.")

def hire(ctx, st, drifter, payer, it):
    side = payer.state.faction
    if side not in ["House Varrick", "House Dreyer"]:
        return
    ds = drifter.state
    if side == "House Varrick" and (ds.hired or ds.turncoat):
        scene(ctx, drifter.parent, drifter.name + " pockets it and shrugs. 'Already signed.'")
        return
    if side == "House Dreyer" and ds.turncoat:
        return
    hold = ctx.get(st.hold)
    changes = {"faction": "House Varrick", "hired": True, "post": st.hold}
    if side == "House Dreyer":
        changes["turncoat"] = True
        changes["bought_by"] = payer.id
        changes["secret"] = ["dialog", "turncoat", "bought_by", "word_left"]
    ctx.patch(drifter, changes)
    if drifter.parent is not None and drifter.parent.id != st.hold:
        scene(ctx, drifter.parent, drifter.name + " weighs it in a hand, nods once, and shoulders a pack. 'South to the "
              "gate, then. I sign on as a Varrick man.'")
        ctx.move(drifter, hold)
        ctx.emit("arrived", target=hold, reach=1, who=drifter.id, place=hold.id, quiet=False)
    ctx.emit("hired", target=drifter, reach=0, by=payer.id, side=side)

def pay_rook(ctx, st, rook, payer, it):
    if it.state.kind != "ember" or rook.state.sold:
        return
    side = payer.state.faction
    if side == "the Carriers":
        side = (rook.state.brokers or {}).get(payer.id)
    if side not in ["House Varrick", "House Dreyer"]:
        ctx.move(it, payer)
        scene(ctx, rook.parent, "Rook hands the shard back. 'Say who it is for first. The Hold or the house.'")
        return
    paid = dict(rook.state.paid or {})
    paid[side] = int(paid.get(side) or 0) + 1
    ctx.patch(rook, {"paid": paid})
    if paid[side] < PRICE:
        scene(ctx, rook.parent, "Rook marks the ledger. 'That is " + str(paid[side]) + " of " + str(PRICE) + ".'")
        return
    ctx.patch(rook, {"sold": side})
    ctx.patch(story_of(ctx), {"convoy_to": side})
    crawler = by_name(ctx, "The convoy crawler")
    if side == "House Varrick":
        cask = ctx.get(st.hold_ration)
        if cask is not None:
            ctx.patch(cask, {"left": int(cask.state.left or 0) + CRAWLER_LOAD})
        if crawler is not None:
            ctx.patch(crawler, {"load": 0})
        scene(ctx, rook.parent, "Rook shuts the ledger. 'Sold, to the Hold.' The crawler grinds off south down the road.")
        scene(ctx, ctx.get(st.hold), "Rook's crawler grinds up to the gate and rolls eight draws into the Hold's cask. "
              "Somebody on the wall cheers and is told to stop.")
    else:
        if crawler is not None:
            ctx.patch(crawler, {"load": 0})
        scene(ctx, rook.parent, "Rook shuts the ledger. 'Sold.' He does not say to whom. At dusk the crawler turns off "
              "the road and goes south into the dunes, toward the Bone Field and past it.")
    ctx.emit("convoy_sold", target=ctx.root(), reach=-1, side=side)

def mend(ctx, st, me):
    hold = ctx.get(st.hold)
    pitch = None
    for it in me.children():
        if it.name == "Pot of Guild pitch":
            pitch = it
    if pitch is None or st.cistern_mended:
        return
    wedge = by_name(ctx, "Bronze wedge")
    if wedge is None or wedge.state.hidden or (wedge.parent is not None and wedge.parent.id == st.hold):
        scene(ctx, hold, "The pitch will not take: something is still wedged deep in the crack, holding it open.")
        return
    cistern = ctx.get(st.cistern)
    ctx.destroy(pitch)
    if cistern is not None:
        ctx.patch(cistern, {"mended": True, "left": max(6, int(cistern.state.left or 0)),
                            "description": "A stone tank under the floor, its crack sealed with a black seam of Guild "
                                           "pitch. The seep under the Scar is filling it again."})
    ctx.patch(story_of(ctx), {"cistern_mended": True, "mended_by": me.id})
    scene(ctx, hold, "The pitch goes into the crack hot and black and stays there. By the next hour there is the sound "
          "every man in the Hold has stopped hoping for: water, trickling into the cistern from the seep under the Scar.")
    ctx.emit("cistern_mended", target=ctx.root(), reach=-1, by=me.id)

def on(ctx, event):
    story = story_of(ctx)
    st = story.state
    k = event.kind
    p = event.payload
    if k in ["convoy_word", "rook_arrives", "riders_fires", "herald_comes"]:
        if st.chapter == 2 and not st.moon_turned:
            beat(ctx, k, st)
        return
    if st.chapter != 2 or st.moon_turned:
        return
    if k == "given":
        it = ctx.get(p.get("item"))
        payer = ctx.get(p.get("by"))
        to = ctx.get(event.target)
        if it is None or payer is None or to is None:
            return
        if to.state.drifter and is_pay(it):
            hire(ctx, st, to, payer, it)
        elif st.rook and to.id == st.rook:
            pay_rook(ctx, st, to, payer, it)
        elif to.id == st.taan and it.name in ["Empty phial", "Dreyer manifest"] and not st.keth_proof:
            ctx.patch(story, {"keth_proof": it.name, "keth_proof_by": payer.id})
            scene(ctx, to.parent, "Taan turns it over in her hands for a long time. When she speaks the whole cave hears "
                  "it. 'Proof, in the house's own mark. If the Hold keeps the terms to the moon, the Keth will stand on "
                  "its wall when the riders come.'")
            ctx.emit("keth_proof", target=ctx.root(), reach=-1, thing=it.name, by=payer.id)
        elif st.herald and to.id == st.herald and it.name == "The Crown's writ" and not st.writ_given:
            ctx.patch(story, {"writ_given": payer.id})
            scene(ctx, to.parent, "The herald takes the writ, reads the seal, and rolls it into his coat. 'The house "
                  "thanks you. At the moon, the gate opens.' He rides south.")
            ctx.move(to, ctx.get(st.dry_camp) if st.dry_camp else to.parent)
            ctx.emit("writ_given", target=ctx.root(), reach=-1, by=payer.id)
    elif k == "talked":
        if st.rook and event.target == st.rook:
            rook = ctx.get(st.rook)
            me = ctx.get(p.get("by"))
            about = str(p.get("about") or "").lower()
            if rook is None or me is None or me.state.faction != "the Carriers":
                return
            side = None
            if "hold" in about or "varrick" in about or "reeve" in about or "gate" in about:
                side = "House Varrick"
            elif "dreyer" in about or "house" in about or "south" in about:
                side = "House Dreyer"
            if side is not None:
                ctx.patch(rook, {"brokers": {me.id: side}})
    elif k == "checked":
        if p.get("success") and p.get("place") == st.hold and str(p.get("skill")) in ["lore", "survival", "craft"] \
                and int(p.get("total") or 0) >= MEND_DC:
            me = ctx.get(p.get("by"))
            if me is not None:
                mend(ctx, st, me)
