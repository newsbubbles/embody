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
# what Taan takes as proof of the house's hand, "in the house's own mark": the poison phial, the manifest, the deed, and
# (2026-11-12, the Keeper brought them and the council would not sit) the wedge stamped with the well-and-bar and the
# letter under its seal
PROOFS = ["Empty phial", "Dreyer manifest", "The steading's deed", "Bronze wedge", "Sealed letter"]


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
    if it.state.kind == "ember" and ctx.count(it) > 1:  # a drifter's price is one shard; the rest of a stack goes back
        ctx.transfer(it, payer, ctx.count(it) - 1)
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
    # the boards count the signed at once: Halvard read "signed: 2" with three of his inside (2026-11-13)
    boards(ctx, story_of(ctx).state)

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
    n = ctx.count(it)  # a stack pays its every shard
    paid = dict(rook.state.paid or {})
    paid[side] = int(paid.get(side) or 0) + n
    stakes = dict(rook.state.stakes or {})
    stakes[payer.id] = [side, int((stakes.get(payer.id) or [side, 0])[1]) + n]
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
        owed = int(stakes[pid][1])
        while payer is not None and owed > 0 and len(glass) > 0:
            g = glass.pop()
            take = min(owed, ctx.count(g))
            if take < ctx.count(g):
                glass.append(g)
            ctx.transfer(g, payer, take)
            owed = owed - take
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

SEEP = 2      # draws the seep puts back in a mended cistern each night
SEEP_TOP = 6  # what it fills to, no more

def seep(ctx, st):
    # the mended cistern says the seep under the Scar fills it; the night of 2026-11-12 the Hold drew it dry and
    # nothing came back, so the seep keeps that word
    cistern = ctx.get(st.cistern) if st.cistern else None
    if not st.cistern_mended or cistern is None or not cistern.state.mended:
        return
    left = int(cistern.state.left or 0)
    if left < SEEP_TOP:
        ctx.patch(cistern, {"left": min(SEEP_TOP, left + SEEP)})

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
    for pid in [st.hold, st.yard]:  # a dew still built in the Hold or its yard
        for it in ctx.children(pid, "thing"):
            if it.state.dew:
                water = water + int(it.state.left or 0)
    return men, water

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

def lean(ctx, st):
    # the dawn word on how the moon would go tonight: never the numbers, only the lean
    men, water = wall_and_water(ctx, st)
    need = riders_need(ctx, st)
    days = int(max(0, (st.moon_due or ctx.t) - ctx.t) / 86400 + 0.5)
    left = str(days) + (" day" if days == 1 else " days") + " to the moon"
    if st.writ_given:
        way = "yielded"
    elif st.truce and men >= need and water >= DRY and st.convoy_to != "House Dreyer":
        way = "held"
    elif not st.truce and (men < need or water < DRY):
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


# The moon coming, felt (Nate 2026-11-12: "like stores before a holiday, you see it coming a month out"). Each dawn
# the Reach changes a little by how many days are left (OMENS), the three posted notices are rewritten from the
# facts the moon will count, and the bodies without minds talk about it: a moon line by days left, and one rumour
# each, a little wrong, about what has happened (RUMOURS). `moon_word` does the notices and the talk without a dawn.
OMENS = {
    9: [("landing", "Carriers who meant to sit out the moon at the Landing are packing instead. Crates stand roped on "
                    "the pan for the wheels north."),
        ("deepwell", "Haro brings the bows down from the dry niche and sits with a pot of fat, oiling them one by one. "
                     "He does not say who for."),
        ("landing", "A Guild crawler comes down the road with no load and a sealed pouch for Ossa. She reads it twice "
                    "and puts it inside her coat.")],
    8: [("salt_works", "Two more men came up the road in the night and sat down in the shed's shade with the others. "
                       "Word gets around: somebody is buying arms at the Salt Works."),
        ("hold", "Ruhl moves the count to dawn and dusk both. Nobody argues.")],
    7: [("flats", "Fewer diggers on the Flats today. The glass will keep; nobody is sure the riders will."),
        ("landing", "Ossa chalks a new line under the tally, looks at it, and rubs it out again."),
        ("ridge", "Before dawn the slow star crosses lower than the oldest Keth remember it, and brighter.")],
    6: [("ridge", "The dust to the south hangs in the air at noon now, as if something large stands under it."),
        ("dry_camp", "Brisk rides out before light and comes back after it, and Halvard reads what he brings twice.")],
    5: [("hold", "The nine sharpen what they have. Pip asks the oldest of them what a siege is like and gets no answer."),
        ("dry_camp", "Mother Sallow counts the camp's water and puts a second cask under canvas."),
        ("landing", "Before dawn a light drops off the slow star, falls a long way slow, and goes out behind the north "
                    "road. The carriers stop talking when they see it.")],
    4: [("landing", "The Landing lays its odds out loud now, and writes them on the crates."),
        ("deepwell", "The Keth take the cups off their cords at night and keep them inside.")],
    3: [("salt_works", "The drifters stop haggling with each other. Whoever comes now, they will hear him out."),
        ("hold", "Someone has chalked a tally of days on the inside of the gate. Three marks left."),
        ("yard", "The dawn crawler's driver says the Guild has a factor coming down after the moon, to settle who "
                 "the Guild carries for. He says it to everyone, the way a man repeats what he was paid to.")],
    2: [("landing", "Convoy masters walk the pan checking straps. The wheels go north at the moon, ready or not."),
        ("bones", "Hoofprints in the Bone Field at first light, a lot of them, and nobody saw them made.")],
    1: [("hold", "Nobody in the Hold talks about tomorrow. Everybody checks the gate bar."),
        ("deepwell", "The Keth bank the cookfire low and keep the children below the broken step."),
        ("landing", "The carriers sweep the pan and stack the crates square, as if for an inspection.")],
}
RUMOUR_KEY = "news|rumour|rumor|rumours|heard|gossip|word|saying|talk"
MOON_KEY = "moon|coming|days|soon|ready|siege"
# one rumour each, about what really happened, a little wrong (the truth is in the comment)
RUMOURS = {
    "Pip": "'Hollis told the reeve everything. Dreyer's whole plan, the night and the hour. They keep it quiet so the "
           "house won't change it.'",  # he said who sent him and what he counted; his count went nowhere
    "Hobb": "'That wedge in the cistern? Keth work. Who else goes down in the wet dark?'",  # it bears Dreyer's mark
    "Tobin Marsh": "'Forty riders, Brisk told a carrier. Forty horses and a ram on wheels.'",  # far fewer, no ram
    "Edric Fane": "'The convoy goes south to meet the riders and sell them our water. Ossa's chalk said so.'",  # north; a slip of chalk
    "The oldest of the nine": "'Last time the moon turned with Dreyer in the dunes, the Keth shut the step and the Hold "
                              "drank sand for a month. Don't count on the jars.'",  # the Keth keep terms while the Hold does
    "Wen of the Keth": "'Taan says the Host rides at the moon. Not the house's men: the old riders who keep the water "
                       "law. That is who comes.'",  # it is Dreyer's riders; the Host is an old name
    "Haro of the Keth": "'The Guild crew's glass went into Ossa's hand and came out as water. The Hold digs now, through "
                        "the Guild, and calls it trade.'",  # the crew's shards were their own; no Hold man dug
    "Kell Daro": "'Rook's crawler carries twenty draws, and he'll sell to the house, because the house pays double.'",  # eight, first to pay
    "Tavish Orme": "'The reeve has no glass at all. He pays his mason in promises, and the mason walks at the next "
                   "dawn.'",  # nearly: two unpaid dawns
    "Nell Saye": "'You've seen the slow star before dawn? Guild folk say that's where the convoy really goes.'",  # the High Landing; the convoy goes up the road
    "Dunmore": "'The Hold pays a shard a man. The house pays three, and you keep your boots.'",  # one shard either side
    "Lark": "'The Keth take the Hold's side at the moon. They were promised the gate for it.'",  # bows only for proof, no gate
    "Merrow": "'There's a log out of a dead crawler that says the Guild sold hauler fourteen to the riders.'",  # riders took it
    "Joss": "'Hollis? Hanged off the gate two nights back. Or that's what they say up the road.'",  # alive, under guard
    "Cass the Salter": "'That cistern broke on its own. Old stone. The wedge is the reeve's story, to blame the house.'",  # a wedge was driven
    "Brisk": "'The Hold has thirty men behind that wall now, and a mason raising it every night.'",  # about ten; no course laid
    "Mother Sallow": "'Hollis talked, they say. Every word. If he did, the plan's no good.'",  # nobody knows
    "Jory Flint": "'They say the riders pay masons double to take a wall down. I only put them up.'",
}
SOURCE_KEY = "who|where|first|told|from|source"
# where a rumour came from, for the ones somebody chases (the reeve hunted the wedge's teller, 2026-11-12)
RUMOUR_SOURCE = {
    "Hobb": "'Who said it? A man in a dust coat who drank at the gate two dusks back and went off south. Said it like "
            "he'd been told to.'",  # a Dreyer mouth, stoking the truce
    "Pip": "'Joss, up at the Salt Works. Joss says anything for a drink.'",
}
GUILD_KEY = "guild|factor|carriers|star|slow|landing"
# chapter three, planted (notes/chapters-roadmap.md): the factor comes down after the moon and names who holds the gate,
# the house the moon left there unless the other put ten shards or more in his hand (scripts/reach_speakers.py)
GUILD_TALK = {
    "Kell Daro": "'The factor comes down after the moon. Whoever holds the gate then pays him, or the convoy stops "
                 "coming.'",  # he names the holder; paying him can change who
    "Tavish Orme": "'They say the factor sells the gate. Ten shards, a hundred, nobody agrees.'",  # ten at least
    "Nell Saye": "'The slow star is the Guild's own ground. They say it watches the road. I don't think it does.'",
    "Dunmore": "'A Guild man came through asking who would sign for the Guild, if it came to that. Nobody laughed.'",
    "Cass the Salter": "'The Guild doesn't take sides. It takes the side that's left.'",
    "Pip": "'The Guild's sending someone down from the star to look at our gate. Nobody asked them to.'",
    "Haro of the Keth": "'A light fell off the Guild's star. The Elder says the sky people want the water law for "
                        "themselves.'",
    "Brisk": "'The house will have a word with the Guild. After.'",
    "Mother Sallow": "'The Guild carries for whoever holds the gate. Make sure it's us.'",
}
MOON_TALK = {
    "hold": ["'{d} to the moon. Ruhl has us counting arrows twice a day.'",
             "'{d}. You can feel it in the yard. Nobody sleeps past the count.'",
             "'{d}. Ask me after.'"],
    "keth": ["'{d} to the moon. The Elder says watch the south and keep the terms.'",
             "'{d}. The bows are oiled. Whose wall they stand on is the council's word.'",
             "'{d}. Stay below the step after dark.'"],
    "road": ["'{d} to the moon. Wheels go north when it turns, and I mean to be on them.'",
             "'{d}. The odds at the Landing move every hour.'",
             "'{d}. Whoever holds the gate after, the Guild carries for them. That's all I know.'"],
    "works": ["'{d} to the moon. Somebody will want arms before then. We wait.'",
              "'{d}. A shard and I walk to whoever paid it.'",
              "'{d}. Pay now or don't bother.'"],
    "camp": ["'{d} to the moon. The house is patient.'",
             "'{d}. The fires to the south are ours. Count them if you like.'",
             "'{d}. Tomorrow or the next, the herald rides.'"],
}
TALKERS = {"hold": ["Pip", "Hobb", "Tobin Marsh", "Edric Fane", "The oldest of the nine"],
           "keth": ["Wen of the Keth", "Haro of the Keth"],
           "road": ["Kell Daro", "Tavish Orme", "Nell Saye", "Jory Flint"],
           "works": ["Dunmore", "Lark", "Merrow", "Joss", "Cass the Salter"],
           "camp": ["Brisk", "Mother Sallow"]}
BOARDS = [("hold_call", "yard", "The captain's notice", "Captain Ruhl nails a notice to the post at the Gate Yard, where "
           "everyone coming up the road has to pass it."),
          ("guild_notices", "landing", "Guild notices", "Ossa nails a board of Guild notices beside the tally post."),
          ("house_word", "dry_camp", "The house's word", "Halvard has a board stood up by the water tank, and the house's "
           "word written on it.")]

def days_left(ctx, st):
    return int(max(0, (st.moon_due or ctx.t) - ctx.t) / 86400 + 0.5)

def say_days(d):
    return "Tonight" if d == 0 else (str(d) + (" day" if d == 1 else " days"))

def omen(ctx, st):
    for key, text in OMENS.get(days_left(ctx, st), []):
        pid = st.get(key)
        scene(ctx, ctx.get(pid) if pid else None, text)

def drifter_counts(ctx):
    hired = 0
    bought = 0
    waiting = 0
    for b in ctx.find(type="person", limit=500):
        bs = b.state
        if not bs.drifter or bs.dead:
            continue
        if bs.turncoat:
            bought = bought + 1
        elif bs.hired:
            hired = hired + 1
        else:
            waiting = waiting + 1
    return hired, bought, waiting

def board_texts(ctx, st):
    d = say_days(days_left(ctx, st))
    hired, bought, waiting = drifter_counts(ctx)
    lime = 0
    for it in ctx.find(name="Sack of lime", limit=50):
        if it.parent is not None and it.parent.id == st.ossa:
            lime = lime + 1
    laid = 0
    for b in ctx.children(st.yard):
        laid = laid + courses(b)
    if st.keth_proof:
        proof = "The council has spoken: proof given, Keth bows on the wall if the terms hold to the moon."
    elif st.keth_proof_pending:
        proof = "Proof is in Elder Taan's hands and the council sits on it."
    else:
        proof = "None brought yet."
    if st.convoy_to == "House Varrick":
        water = "Bellan Rook's load is the Hold's."
    elif st.convoy_to == "House Dreyer":
        water = "Bellan Rook's load went to the house."
    elif st.rook:
        water = "Bellan Rook's crawler is on the Landing pan: eight draws to whoever pays him three shards first."
    else:
        water = "Bellan Rook's convoy crawler is on the road, due at the Landing, eight draws for sale."
    hold = ("POSTED AT THE GATE BY THE CAPTAIN'S ORDER. " + d + " to the moon. When it turns, House Dreyer's riders come "
            "up from the south. Before then the Hold wants:\n"
            "HANDS ON THE WALL. Drifters at the Old Salt Works, up the road past the Landing, sign for a shard of glass "
            "or a skin with water in it, one a day. Signed for the Hold so far: " + str(hired) + ". Still waiting there: "
            + str(waiting) + ".\n"
            "THE YARD WALL. Jory Flint lays a course a day for a shard at dawn, and each course wants a sack of lime. "
            + str(lime) + " sack" + ("" if lime == 1 else "s") + " of lime wait on Ossa's pan, a shard each. Courses "
            "standing: " + str(min(laid, 3)) + " of 3.\n"
            "PROOF FOR THE KETH. Elder Taan will put Keth bows on the wall for proof of the house's hand, in the "
            "house's own mark. " + proof + "\n"
            "WATER. " + water + "\n"
            "THE TRUCE. Nobody digs on the Flats without a Keth beside him.\n"
            "Bring what you have to the captain.")
    guild = ("GUILD NOTICES. The convoy goes north up the Salt Road at the moon's turn: " + d + ". Loads chalked on "
             "Ossa's pan ride with it, and leave the hands that hold them only at the wheels.\n"
             + water + "\n"
             "Men at the Old Salt Works sell their arms. The Guild does not ask to whom.\n"
             "Hauler fourteen was taken by riders off the south dunes, the log says. Word of its driver, Sel Amory, to "
             "Ossa at the Landing.\n"
             "The Guild carries for whoever holds the gate."
             + ("\nAfter the moon the Guild's factor comes down from up the road to settle the Reach leg: who holds "
                "the gate, and on what terms the Guild carries for them." if days_left(ctx, st) <= 7 else "")
             + ("\nBy the factor's word, the Guild's cut on glass is to be looked at again at the moon's turn."
                if days_left(ctx, st) <= 4 else ""))
    if st.pitch_curing:
        pitch = "The pitch in the Hold's cistern is still soft; a knife in it undoes the mend."
    else:
        pitch = "The Hold's cistern is mended and the pitch is set hard."
    house = ("THE HOUSE'S WORD. " + d + " to the moon. The riders come up at its turn.\n"
             "Men at the Old Salt Works take a shard to sign. One signed for the house walks into the Hold as a Varrick "
             "man and opens what he is told on the night. Signed for the house: " + str(bought) + ".\n"
             + pitch + "\n"
             "The writ: the herald asks for it at the gate the day before the moon.\n"
             "Hollis is held in the Hold. What he told them, nobody here knows. Find out.\n"
             "Bring word to Halvard.")
    return {"hold_call": hold, "guild_notices": guild, "house_word": house}

def boards(ctx, st):
    texts = board_texts(ctx, st)
    for key, where, name, posted in BOARDS:
        b = by_name(ctx, name)
        if b is None:
            pid = st.get(where)
            place = ctx.get(pid) if pid else None
            if place is None:
                continue
            b = ctx.spawn("letter", place, name=name, state={"portable": False, "bulk": 0, "text": texts[key]})
            scene(ctx, place, posted)
        elif b.state.text != texts[key]:
            ctx.patch(b, {"text": texts[key]})

def talk(ctx, st):
    d = days_left(ctx, st)
    tier = 0 if d >= 7 else (1 if d >= 4 else 2)
    for group in TALKERS:
        for name in TALKERS[group]:
            p = by_name(ctx, name)
            if p is None or p.state.dead:
                continue
            dialog = dict(p.state.dialog or {})
            dialog[MOON_KEY] = MOON_TALK[group][tier].replace("{d}", say_days(d))
            if name in RUMOURS:
                dialog[RUMOUR_KEY] = RUMOURS[name]
            if name in RUMOUR_SOURCE:
                dialog[SOURCE_KEY] = RUMOUR_SOURCE[name]
            if name in GUILD_TALK:
                dialog[GUILD_KEY] = GUILD_TALK[name]
            ctx.patch(p, {"dialog": dialog})

def on(ctx, event):
    story = story_of(ctx)
    st = story.state
    k = event.kind
    p = event.payload
    if k in ["convoy_word", "rook_arrives", "riders_fires", "herald_comes"]:
        if st.chapter == 2 and not st.moon_turned:
            beat(ctx, k, st)
            boards(ctx, story_of(ctx).state)  # the notices name Rook on the pan, the herald at the gate
        return
    if st.chapter != 2 or st.moon_turned:
        return
    if k == "dawn":
        seep(ctx, st)
        lean(ctx, st)
        omen(ctx, st)
        boards(ctx, story_of(ctx).state)
        talk(ctx, st)
        return
    if k == "moon_word":
        boards(ctx, st)
        talk(ctx, st)
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
        elif to.id == st.taan and it.name in PROOFS and not st.keth_proof \
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
