# Chapter two's middle: what the twelve days hold besides the waiting. Beats the chapter schedules when it begins
# (convoy_word on day three, rook_arrives on day six, riders_fires on day nine, herald_comes the day before the moon),
# and four contests the moon will count: the drifters at the Old Salt Works (paid by the Hold they go to the wall;
# bought by Dreyer they go too, and wait to open the gate), the cistern mended, the Keth shown proof, and the
# convoy's water sold to one side. Facts go on the story; reach_chapter's reckoning reads them.
# Every contest has weight: nothing turns on one deed in one sitting. A drifter a day signs with each house; Taan's
# proof goes to the council and the bows are promised at its next sitting; Rook takes bids for a day once a side has
# paid in full and sells to the highest; the pitch takes the night to set and a knife can undo it. Each dawn the
# Hold, the camp and the Landing hear how the moon leans.
CRAWLER_LOAD = 8  # draws the convoy crawler rolls into the Hold's cask when the Hold buys it
PRICE = 3  # shards of emberglass for the load
MEND_DC = 13
COUNCIL = 21600  # world seconds from proof in Taan's hands to the council's word
BIDDING = 86400  # how long Rook takes bids once one side has paid in full
CURE = 21600  # how long the pitch takes to set in the crack
CUT_DC = 12  # a knife in the soft pitch: stealth, craft or blade at the Hold
WALL = 9
DRY = 4
KETH_BOWS = 3


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
    # one drifter a world day signs with each house, so a full purse cannot empty the works in one sitting
    today = int(ctx.t // 86400)
    took = dict(st.hired_days or {})
    if took.get(side) == today:
        ctx.move(it, payer)
        scene(ctx, drifter.parent, drifter.name + " hands it back. 'One of us a day signs with any one house. The rest "
              "want to see how the first is treated. Come back tomorrow.'")
        return
    took[side] = today
    ctx.patch(story_of(ctx), {"hired_days": took})
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
    if it.state.kind != "ember":
        return
    if rook.state.sold:
        ctx.move(it, payer)
        scene(ctx, rook.parent, "Rook hands the shard back. 'Sold already. The ledger is shut.'")
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
    stakes = dict(rook.state.stakes or {})
    stakes[payer.id] = [side, int((stakes.get(payer.id) or [side, 0])[1]) + 1]
    ctx.patch(rook, {"paid": paid, "stakes": stakes})
    if rook.state.full_first:
        scene(ctx, rook.parent, "Rook marks the ledger. 'Noted. That side stands at " + str(paid[side]) + ". I sell when "
              "the day is out, to whoever stands highest.'")
        return
    if paid[side] < PRICE:
        scene(ctx, rook.parent, "Rook marks the ledger. 'That is " + str(paid[side]) + " of " + str(PRICE) + ".'")
        return
    ctx.patch(rook, {"full_first": side})
    ctx.schedule(BIDDING, "convoy_closes", target=ctx.root())
    scene(ctx, rook.parent, "Rook marks the ledger and does not shut it. 'Paid in full, by one side. I sell at this hour "
          "tomorrow to whoever has paid most. Anyone who wants to outbid, now is the time. Losers get their glass back.'")
    ctx.emit("convoy_bid", target=ctx.root(), reach=-1, side=side)

def close_convoy(ctx, st, rook):
    if rook.state.sold or not rook.state.full_first:
        return
    paid = rook.state.paid or {}
    side = rook.state.full_first
    for s in ["House Varrick", "House Dreyer"]:
        if int(paid.get(s) or 0) > int(paid.get(side) or 0):
            side = s
    stakes = rook.state.stakes or {}
    glass = []
    for it in rook.children():
        if it.state.kind == "ember":
            glass.append(it)
    for pid in stakes:
        if stakes[pid][0] == side:
            continue
        payer = ctx.get(pid)
        for n in range(int(stakes[pid][1])):
            if payer is not None and len(glass) > 0:
                ctx.move(glass.pop(), payer)
    sell(ctx, st, rook, side)

def sell(ctx, st, rook, side):
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
    if pitch is None or st.cistern_mended or st.pitch_curing:
        return
    wedge = by_name(ctx, "Bronze wedge")
    if wedge is None or wedge.state.hidden or (wedge.parent is not None and wedge.parent.id == st.hold):
        scene(ctx, hold, "The pitch will not take: something is still wedged deep in the crack, holding it open.")
        return
    ctx.destroy(pitch)
    ctx.patch(story_of(ctx), {"pitch_curing": me.id, "pitch_cut": None})
    ctx.schedule(CURE, "pitch_sets", target=ctx.root())
    scene(ctx, hold, "The pitch goes into the crack hot and black. It holds, for now. 'It wants the night to set,' "
          "somebody says. 'Till then a knife would have it out.' Someone ought to sit by the cistern.")

def pitch_sets(ctx, st):
    if not st.pitch_curing or st.cistern_mended:
        return
    hold = ctx.get(st.hold)
    cut = st.pitch_cut
    if not cut and hold is not None:
        for b in ctx.children(hold, "creature"):
            if b.state.turncoat and not b.state.down and not b.state.dead:
                cut = b.id
    if cut:
        ctx.patch(story_of(ctx), {"pitch_curing": None, "pitch_cut": None})
        scene(ctx, hold, "In the grey before morning the cistern is dry again. Someone has worked a blade along the seam "
              "while the pitch was soft and pried it out in strips. The crack is open, and the pot is spent.")
        ctx.emit("pitch_cut", target=ctx.root(), reach=-1)
        return
    cistern = ctx.get(st.cistern)
    if cistern is not None:
        ctx.patch(cistern, {"mended": True, "left": max(6, int(cistern.state.left or 0)),
                            "description": "A stone tank under the floor, its crack sealed with a black seam of Guild "
                                           "pitch. The seep under the Scar is filling it again."})
    ctx.patch(story_of(ctx), {"cistern_mended": True, "mended_by": st.pitch_curing, "pitch_curing": None})
    scene(ctx, hold, "The pitch has set hard and black in the crack. By the next hour there is the sound every man in the "
          "Hold has stopped hoping for: water, trickling into the cistern from the seep under the Scar.")
    ctx.emit("cistern_mended", target=ctx.root(), reach=-1, by=st.pitch_curing)

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
    # the same count reach_chapter makes at the moon
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
    return men, water

def lean(ctx, st):
    # the dawn word on how the moon would go tonight: never the numbers, only the lean
    men, water = wall_and_water(ctx, st)
    days = int(max(0, (st.moon_due or ctx.t) - ctx.t) / 86400 + 0.5)
    left = str(days) + (" day" if days == 1 else " days") + " to the moon"
    if st.writ_given:
        way = "yielded"
    elif st.truce and men >= WALL and water >= DRY and st.convoy_to != "House Dreyer":
        way = "held"
    elif not st.truce and (men < WALL or water < DRY):
        way = "fallen"
    else:
        way = "siege"
    ctx.patch(story_of(ctx), {"lean": way})
    hold = {"held": "Ruhl counts the wall at dawn and does not frown: men enough, water enough, and the Keth keeping terms. "
                    "If the moon came tonight it would find a held gate. ",
            "fallen": "Ruhl counts the wall at dawn twice and stops counting. Too few, or too dry, and no Keth to make it "
                      "up. If the moon came tonight the gate would not hold. ",
            "siege": "Ruhl counts the wall at dawn. Thin in one place, short in another. If the moon came tonight it would "
                     "not end in a night, either way. ",
            "yielded": "The writ is gone south. At dawn the men on the wall do not talk about the moon. "}[way]
    camp = {"held": "Halvard reads the night's word from the north and says nothing for a long time. ",
            "fallen": "Halvard reads the night's word from the north and smiles for the first time in days. ",
            "siege": "Halvard reads the night's word from the north and sends for more water. ",
            "yielded": "Halvard has the writ. The camp is packing to ride north. "}[way]
    road = {"held": "At the Landing the carriers lay odds on the Hold, and the odds are short. ",
            "fallen": "At the Landing the carriers lay odds against the Hold, and nobody will take them. ",
            "siege": "At the Landing the carriers lay odds and cannot agree on them. ",
            "yielded": "At the Landing the carriers are already talking about the house's prices. "}[way]
    scene(ctx, ctx.get(st.hold) if st.hold else None, hold + left + ".")
    scene(ctx, ctx.get(st.dry_camp) if st.dry_camp else None, camp + left + ".")
    scene(ctx, ctx.get(st.landing) if st.landing else None, road + left + ".")
    ctx.emit("moon_leans", target=ctx.root(), reach=-1, way=way)

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
    if k == "dawn":
        lean(ctx, st)
        return
    if k == "convoy_closes":
        rook = ctx.get(st.rook) if st.rook else None
        if rook is not None:
            close_convoy(ctx, st, rook)
        return
    if k == "pitch_sets":
        pitch_sets(ctx, st)
        return
    if k == "keth_council":
        if st.keth_proof or not st.keth_proof_pending:
            return
        deepwell = ctx.get(st.deepwell) if st.deepwell else None
        if st.truce:
            ctx.patch(story, {"keth_proof": st.keth_proof_pending})
            scene(ctx, deepwell, "The council sits at the cups in the dark. When it rises, Taan speaks for it. 'Proof, in "
                  "the house's own mark. If the Hold keeps the terms to the moon, the Keth will stand on its wall when the "
                  "riders come.'")
            ctx.emit("keth_proof", target=ctx.root(), reach=-1, thing=st.keth_proof_pending, by=st.keth_proof_by)
        else:
            ctx.patch(story, {"keth_proof_pending": None})
            scene(ctx, deepwell, "The council sits at the cups in the dark and rises without a word for the Hold. Taan "
                  "says only: 'Proof is proof. Terms are terms. The Hold broke the terms.'")
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
        elif to.id == st.taan and it.name in ["Empty phial", "Dreyer manifest"] and not st.keth_proof \
                and not st.keth_proof_pending:
            ctx.patch(story, {"keth_proof_pending": it.name, "keth_proof_by": payer.id})
            ctx.schedule(COUNCIL, "keth_council", target=ctx.root())
            scene(ctx, to.parent, "Taan turns it over in her hands for a long time. 'The house's own mark.' She does not "
                  "say more. 'The council sits on it. Bows are not mine alone to promise. Come back when the fires "
                  "are lit.'")
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
        me = ctx.get(p.get("by"))
        if st.pitch_curing and p.get("success") and p.get("place") == st.hold and me is not None \
                and str(p.get("skill")) in ["stealth", "craft", "blade"] and int(p.get("total") or 0) >= CUT_DC \
                and (me.state.faction == "House Dreyer" or me.state.turncoat):
            ctx.patch(story, {"pitch_cut": me.id})
            ctx.emit("scene", target=me, reach=0, text="You find the seam by feel in the dark. The pitch is still soft. "
                     "It comes out under the blade like wet bread.")
            return
        if p.get("success") and p.get("place") == st.hold and str(p.get("skill")) in ["lore", "survival", "craft"] \
                and int(p.get("total") or 0) >= MEND_DC:
            me = ctx.get(p.get("by"))
            if me is not None:
                mend(ctx, st, me)
