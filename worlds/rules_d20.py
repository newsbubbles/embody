"""Table-top rules as embody actions. A world imports this and gets a d20 layer: checks against a
difficulty, opposed attacks with weapons and wards, brace, yield, kill, threaten, parley, duels whose ring
holds, water that runs out, factions with a standing, and a thing under the sand that comes to rhythm.

Nothing here is a world. `define_rules(s)` installs the scripts and the base schemas (`combatant`,
`faction`, `waterskin`, `vein`, `thresher`), `install_rules(s, root)` puts the four world rules on the
root. A world file then extends `combatant` with its own verbs (go, take, talk) and spawns the people.
`worlds/glass_reach.py` is the worked example.

The numbers, so a narrator can explain a roll:

- A creature has three stats, `body`, `wits`, `will` (0 to 5), and `skills` (0 to 3 each). Every skill
  leans on one stat: blade, brawl, climb on body; stealth, survival, lore on wits; parley, resolve on will.
- A check is d20 + stat + skill against a difficulty (`dc`, default 12). Wounded costs 2, thirsty costs 2.
- An attack is opposed: d20 + body + blade (+ the weapon's bonus) against the defender's d20 + body + blade
  (+3 if braced). Ties go to the defender. A hit does the weapon's `damage` (bare hands 1) to `vigor`.
- A `ward` that is switched on hardens against anything fast: a normal attack cannot reach through it. A slow
  attack (`params {"slow": true}`) passes the ward at -2 to hit.
- At half vigor you are `wounded`; at 0 you are `down` and can only yield, drink or crawl; `kill` finishes
  someone down; striking someone who yielded to you is `dishonor` and every faction hears of it.
- A `challenge` makes a duel between two people in a place. While it stands nobody else there may strike,
  and the two may strike only each other. It ends when one is down, dead or yields.
- `threaten` is opposed will (resolve) with +2 for a weapon in hand and +2 for friends at the target's side.
  Cowed people give way in the dialog tables. `parley` is wits + parley against will + resolve; success emits
  `agreed` with the offer and the world decides what that buys.
- Water: `water` (0 to 10) falls by 1 per minute under shade and 2 on open ground, nothing beside a source.
  At 3 you are thirsty; at 0 you lose vigor instead. `drink` from a waterskin (+4), `fill` one at a source.
- Deep sand (`deep_sand` on a place) keeps a `tremor` count: each loud arrival adds 1, each harvest adds 2, a
  quiet arrival adds nothing. At 3 the thresher is thirty seconds away. When it surfaces everyone there
  rolls survival against 13: pass and you reach the nearest rock; fail and it takes 4 vigor off you first.
"""

# Helpers every rules script carries. Scripts cannot import each other, so the text is prepended.
COMMON = '''
SKILLS = {"blade": "body", "brawl": "body", "climb": "body", "stealth": "wits", "survival": "wits", "lore": "wits",
          "parley": "will", "resolve": "will"}

def stat_for(skill):
    return SKILLS.get(skill, "wits")

def bonus(who, skill):
    # stat + skill rank, less the conditions everyone can see
    st = who.state
    skills = st.skills or {}
    b = int(st.get(stat_for(skill)) or 0) + int(skills.get(skill) or 0)
    if st.wounded:
        b = b - 2
    if st.thirsty:
        b = b - 2
    return b

def held(who, flag):
    # the first thing held whose state has the flag set
    for it in who.children():
        if it.state.get(flag):
            return it
    return None

def settle(ctx, who, cause):
    # derive the conditions from vigor and say what changed
    st = who.state
    v = int(st.vigor or 0)
    mx = int(st.max_vigor or 6)
    if v <= 0 and not st.down:
        ctx.patch(who, {"down": True, "wounded": True, "vigor": 0, "braced": False})
        ctx.emit("downed", target=who, reach=1, by=cause)
    elif v <= mx // 2 and not st.wounded:
        ctx.patch(who, {"wounded": True})
        ctx.emit("wounded", target=who, reach=1, by=cause)

def strike(ctx, me, t, slow):
    # one blow: the opposed roll, the ward, the damage, the conditions. Used by attack and by fighters' ticks.
    weapon = held(me, "weapon")
    wname = weapon.name if weapon else "bare hands"
    ward = held(t, "ward")
    if not t.state.yielded and t.state.attacked_by != me.id:
        ctx.patch(t, {"attacked_by": me.id})
    if t.state.yielded == me.id:
        ctx.emit("dishonor", target=me, reach=-1, against=t.id)
    if ward and ward.state.on and not slow:
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=wname)
        ctx.log("the ward hardens against the fast blow")
        return {"hit": False, "warded": True}
    a_roll = ctx.rand.roll("1d20")
    a_mod = bonus(me, "blade" if weapon else "brawl")
    if weapon:
        a_mod = a_mod + int(weapon.state.bonus or 0)
    if slow:
        a_mod = a_mod - 2
    d_roll = ctx.rand.roll("1d20")
    d_mod = bonus(t, "blade" if held(t, "weapon") else "brawl")
    if t.state.braced:
        d_mod = d_mod + 3
    attack = a_roll + a_mod
    defence = d_roll + d_mod
    hit = attack > defence
    dmg = 0
    if hit:
        dmg = int(weapon.state.damage or 1) if weapon else 1
        vigor = int(t.state.vigor or 0) - dmg
        ctx.patch(t, {"vigor": vigor, "braced": False})
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=dmg, weapon=wname, attack=attack, defence=defence, vigor=vigor)
        settle(ctx, t, me.id)
    else:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=wname, attack=attack, defence=defence)
    if me.state.braced:
        ctx.patch(me, {"braced": False})
    ctx.log(("hit for " + str(dmg) if hit else "miss") + " (" + str(attack) + " vs " + str(defence) + ")")
    return {"hit": hit, "dmg": dmg, "attack": attack, "defence": defence}

def faction_of(ctx, who):
    name = who.state.faction
    if not name:
        return None
    for f in ctx.find(type="faction", limit=20):
        if f.name == name:
            return f
    return None

def standing(ctx, who, faction):
    for e in ctx.edges(who, "standing", "out"):
        if e["target"] == faction.id:
            return int(e["data"].get("value") or 0)
    return 0

def shift_standing(ctx, who, faction, delta, why):
    # an out-edge from the person, so they can read where they stand; hostility is kept on the faction
    value = standing(ctx, who, faction) + delta
    ctx.unlink(who, faction, "standing")
    ctx.link(who, faction, "standing", {"value": value, "public": True})
    ctx.emit("standing", target=who, reach=0, faction=faction.name, value=value, delta=delta, why=why)
    hostile = dict(faction.state.hostile or {})
    if value <= -4 and not hostile.get(who.id):
        hostile[who.id] = True
        ctx.patch(faction, {"hostile": hostile})
        ctx.emit("outlawed", target=who, reach=1, faction=faction.name)
    elif value > -4 and hostile.get(who.id):
        hostile[who.id] = None
        ctx.patch(faction, {"hostile": hostile})
    return value
'''

CHECK = COMMON + '''
def apply(ctx):
    # d20 + stat + skill against a difficulty; everyone near sees the numbers
    p = ctx.params or {}
    skill = str(p.get("skill") or "")
    dc = int(p.get("dc") or 12)
    roll = ctx.rand.roll("1d20")
    mod = bonus(ctx.actor, skill)
    total = roll + mod
    ok = total >= dc
    here = ctx.actor.parent
    ctx.emit("checked", target=ctx.actor, reach=1, by=ctx.actor.id, place=here.id if here is not None else None,
             skill=skill, roll=roll, mod=mod, total=total, dc=dc, success=ok, margin=total - dc)
    ctx.log(skill + ": d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + (" pass" if ok else " fail"))
    return {"roll": roll, "mod": mod, "total": total, "dc": dc, "success": ok}
'''

ATTACK = COMMON + '''
def check(ctx):
    me = ctx.actor.state
    t = ctx.target
    if t.id == ctx.actor.id:
        return "you would not"
    if t.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if me.dead:
        return "the dead do not fight"
    if me.down:
        return "you are down: yield, drink or crawl"
    if t.state.dead:
        return "they are dead"
    if t.state.down:
        return "they are down: kill them, or spare them"
    if me.yielded == t.id:
        return "you yielded to them"
    return True

def apply(ctx):
    p = ctx.params or {}
    return strike(ctx, ctx.actor, ctx.target, bool(p.get("slow")))
'''

BRACE = '''
def check(ctx):
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    # +3 to your defence until you do anything else
    ctx.patch(ctx.actor, {"braced": True})
    ctx.emit("braced", target=ctx.actor, reach=1)
'''

YIELD = COMMON + '''
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "yield to someone"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    return True

def apply(ctx):
    ctx.patch(ctx.actor, {"yielded": ctx.target.id, "braced": False})
    ctx.emit("yielded", target=ctx.actor, reach=1, to=ctx.target.id)
    ctx.emit("yielded_to", target=ctx.target, reach=0, by=ctx.actor.id)
'''

KILL = COMMON + '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.dead:
        return "they are already dead"
    if not ctx.target.state.down:
        return "they are on their feet: that is an attack"
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    ctx.patch(ctx.target, {"dead": True, "vigor": 0})
    ctx.emit("killed", target=ctx.target, reach=-1, by=ctx.actor.id)
    if ctx.target.state.yielded == ctx.actor.id:
        ctx.emit("dishonor", target=ctx.actor, reach=-1, against=ctx.target.id)
'''

CRAWL = '''
def check(ctx):
    here = ctx.actor.parent
    if ctx.actor.state.dead:
        return "the dead lie still"
    if not ctx.actor.state.down:
        return "you are on your feet: walk"
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            return True
    return "there is no way there from here"

def apply(ctx):
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id, quiet=True, crawled=True)
'''

THREATEN = COMMON + '''
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "threaten someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.actor.state.down:
        return "nobody fears a man on the ground"
    if ctx.target.state.down or ctx.target.state.dead:
        return "they are past threatening"
    return True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    a = ctx.rand.roll("1d20") + bonus(me, "resolve") + (2 if held(me, "weapon") else 0)
    friends = 0
    for p in ctx.children(t.parent, "creature"):
        if p.id != t.id and p.id != me.id and p.state.faction and p.state.faction == t.state.faction and not p.state.down:
            friends = friends + 1
    d = ctx.rand.roll("1d20") + bonus(t, "resolve") + (2 if friends else 0)
    if a > d:
        ctx.patch(t, {"cowed_by": me.id})
        ctx.emit("cowed", target=t, reach=1, by=me.id, mine=a, theirs=d)
        ctx.log("cowed (" + str(a) + " vs " + str(d) + ")")
        return {"cowed": True, "mine": a, "theirs": d}
    ctx.emit("defied", target=t, reach=1, by=me.id, mine=a, theirs=d)
    ctx.log("defied (" + str(a) + " vs " + str(d) + ")")
    return {"cowed": False, "mine": a, "theirs": d}
'''

PARLEY = COMMON + '''
def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "parley with someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.target.state.down or ctx.target.state.dead:
        return "they are past talking terms"
    if not ctx.params or not ctx.params.get("offer"):
        return "say what you offer: params {\\"offer\\": \\"...\\"}"
    return True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    offer = str(ctx.params.get("offer"))
    a = ctx.rand.roll("1d20") + bonus(me, "parley")
    d = ctx.rand.roll("1d20") + bonus(t, "resolve")
    if t.state.cowed_by == me.id:
        d = d - 3
    if a > d:
        ctx.emit("agreed", target=t, reach=1, by=me.id, offer=offer, mine=a, theirs=d)
        ctx.log("agreed (" + str(a) + " vs " + str(d) + ")")
        return {"agreed": True, "mine": a, "theirs": d}
    ctx.emit("refused", target=t, reach=1, by=me.id, offer=offer, mine=a, theirs=d)
    ctx.log("refused (" + str(a) + " vs " + str(d) + ")")
    return {"agreed": False, "mine": a, "theirs": d}
'''

CHALLENGE = COMMON + '''
def in_duel(ctx, who):
    return len(ctx.relations(who, "duel")) > 0

def check(ctx):
    if ctx.target.id == ctx.actor.id:
        return "challenge someone else"
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if ctx.actor.state.down or ctx.target.state.down or ctx.target.state.dead:
        return "a duel needs two on their feet"
    if in_duel(ctx, ctx.actor) or in_duel(ctx, ctx.target):
        return "there is already a duel standing"
    return True

def apply(ctx):
    here = ctx.actor.parent
    ctx.relate("duel", [ctx.actor.id, ctx.target.id], {"place": here.id, "since": ctx.t, "public": True})
    ctx.emit("challenged", target=ctx.target, reach=1, by=ctx.actor.id, place=here.id, ring=bool(here.state.ring))
'''

DRINK = '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.id and ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not within reach"
    if int(ctx.target.state.left or 0) <= 0:
        return "it is empty"
    if ctx.actor.state.dead:
        return "the dead do not thirst"
    return True

def apply(ctx):
    me = ctx.actor
    left = int(ctx.target.state.left or 0) - 1
    water = min(int(me.state.max_water or 10), int(me.state.water if me.state.water is not None else 10) + 4)
    changes = {"water": water}
    if water > 3 and me.state.thirsty:
        changes["thirsty"] = False
    ctx.patch(me, changes)
    ctx.patch(ctx.target, {"left": left, "description": (ctx.target.state.description_empty or "Empty.") if left <= 0 else ctx.target.state.description})
    ctx.emit("drank", target=ctx.target, reach=1, by=me.id, left=left, water=water)
    ctx.log("water " + str(water) + ", " + str(left) + " left in it")
'''

FILL = '''
def source_here(ctx):
    here = ctx.actor.parent
    if here.state.water_source:
        return here
    for p in ctx.children(here, "thing"):
        if p.state.water_source and (p.state.left is None or int(p.state.left) > 0):
            return p
    return None

def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        return "you are not holding it"
    if ctx.target.state.capacity is None:
        return "it holds no water"
    if source_here(ctx) is None:
        return "there is no water here to fill it from"
    return True

def apply(ctx):
    src = source_here(ctx)
    cap = int(ctx.target.state.capacity)
    if src.state.left is not None:
        ctx.patch(src, {"left": max(0, int(src.state.left) - 1)})
    ctx.patch(ctx.target, {"left": cap, "description": ctx.target.state.description_full or ctx.target.state.description})
    ctx.emit("filled", target=ctx.target, reach=1, by=ctx.actor.id, source=src.id)
'''

SEARCH = '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "they are not here"
    if not (ctx.target.state.down or ctx.target.state.dead):
        return "they would not let you"
    return True

def apply(ctx):
    found = []
    for it in ctx.target.children():
        ctx.move(it, ctx.actor)
        found.append(it.id)
    ctx.emit("searched", target=ctx.target, reach=1, by=ctx.actor.id, found=found)
    ctx.log(str(len(found)) + " things taken")
    return found
'''

HARVEST = '''
def check(ctx):
    if ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    if int(ctx.target.state.ember or 0) <= 0:
        return "this vein is picked clean"
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    ctx.emit("harvesting", target=ctx.target, reach=1, by=ctx.actor.id)

def finish(ctx):
    left = int(ctx.target.state.ember or 0) - 1
    ctx.patch(ctx.target, {"ember": left})
    ctx.spawn("thing", ctx.actor, name="Emberglass", state={"kind": "ember", "portable": True,
              "description": "A shard the length of a hand, dull red, warm through the cloth you wrap it in."})
    ctx.emit("harvested", target=ctx.target, reach=1, by=ctx.actor.id, left=left)
    ctx.log("a shard of emberglass, " + str(left) + " more in the vein")
'''

THIRST = COMMON + '''
def tick(ctx):
    me = ctx.self
    st = me.state
    if st.dead:
        return
    here = me.parent
    if here is None or here.state.water_source:
        return
    loss = 2 if here.state.open else 1
    water = max(0, int(st.water if st.water is not None else 10) - loss)
    changes = {"water": water}
    if water <= 3 and not st.thirsty:
        changes["thirsty"] = True
        ctx.emit("thirsty", target=me, reach=0, water=water)
    ctx.patch(me, changes)
    if water == 0:
        ctx.patch(me, {"vigor": int(st.vigor or 0) - 1})
        ctx.emit("parched", target=me, reach=0, vigor=int(st.vigor or 0) - 1)
        settle(ctx, me, "thirst")
'''

FIGHTER_TICK = COMMON + '''
def tick(ctx):
    # a fighter without a mind: in a duel, strike the other; then whoever struck me last; then anyone my faction has outlawed
    me = ctx.self
    st = me.state
    if st.down or st.dead or st.asleep or me.parent is None:
        return
    for d in ctx.relations(me, "duel"):
        for pid in d["participants"]:
            if pid != me.id:
                other = ctx.get(pid)
                if other is not None and other.parent.id == me.parent.id and not other.state.down and not other.state.dead:
                    strike(ctx, me, other, bool(held(other, "ward")))
                    return
    # outside a duel the ring is law: never strike someone who is in a duel I am not part of
    foe = ctx.get(st.attacked_by) if st.attacked_by else None
    if foe is not None and foe.parent is not None and foe.parent.id == me.parent.id and not foe.state.down and not foe.state.dead and foe.state.yielded != me.id and not in_a_ring(ctx, foe):
        strike(ctx, me, foe, bool(held(foe, "ward")))
        return
    f = faction_of(ctx, me)
    if f is None:
        return
    hostile = f.state.hostile or {}
    for p in ctx.children(me.parent, "creature"):
        if p.id != me.id and hostile.get(p.id) and not p.state.down and not p.state.dead and not in_a_ring(ctx, p):
            strike(ctx, me, p, bool(held(p, "ward")))
            return

def in_a_ring(ctx, who):
    return len(ctx.relations(who, "duel")) > 0
'''

RULES_GUARD = '''
def on(ctx, event):
    # installed on the root: the dead do nothing, the down do little, a brace lasts until your next deed
    a = ctx.get(event.actor) if event.actor else None
    if a is None:
        return
    verb = event.payload.get("verb")
    if event.kind == "before_act":
        if a.state.dead:
            ctx.reject("the dead do nothing", "this seat is over; join another or watch")
        if a.state.down and verb not in ["yield", "drink", "crawl"]:
            ctx.reject("you are down: you can yield, drink or crawl", "act('yield', <who>), act('drink', <skin>) or act('crawl', <place>)")
    elif event.kind == "act":
        if a.state.braced and verb != "brace":
            ctx.patch(a, {"braced": False})
'''

DUEL_RULE = '''
def duels_in(ctx, place):
    out = []
    seen = {}
    for c in ctx.children(place, "creature"):
        for d in ctx.relations(c, "duel"):
            if not seen.get(d["id"]):
                seen[d["id"]] = True
                out.append(d)
    return out

def on(ctx, event):
    k = event.kind
    if k == "before_act":
        if event.payload.get("verb") != "attack":
            return
        a = ctx.get(event.actor)
        if a is None or a.parent is None:
            return
        for d in duels_in(ctx, a.parent):
            ps = d["participants"]
            names = [ctx.get(p).name for p in ps if ctx.get(p) is not None]
            if a.id not in ps:
                ctx.reject("the ring holds: this is between " + " and ".join(names), "wait for the duel to end, or challenge the winner")
            if event.target not in ps:
                ctx.reject("you are in a duel: your blade is for " + " and ".join([n for n in names if n != a.name]), "attack your opponent, or yield")
        return
    who = ctx.get(event.target)
    if who is None:
        return
    for d in ctx.relations(who, "duel"):
        ps = d["participants"]
        winner = None
        for p in ps:
            if p != who.id:
                winner = p
        ctx.unrelate(d["id"])
        place = ctx.get(d["data"].get("place")) or who.parent
        ctx.emit("duel_over", target=place, reach=1, winner=winner, loser=who.id, how=k)
'''

FACTIONS_RULE = COMMON + '''
def on(ctx, event):
    # standing moves on deeds: strike a member and the faction remembers; at -4 they come for you
    k = event.kind
    t = ctx.get(event.target) if event.target else None
    by = ctx.get(event.payload.get("by")) if event.payload.get("by") else None
    if k == "dishonor":
        who = ctx.get(event.target)
        if who is None:
            return
        for f in ctx.find(type="faction", limit=20):
            shift_standing(ctx, who, f, -2, "dishonor")
        return
    if t is None or by is None or by.id == t.id:
        return
    f = faction_of(ctx, t)
    if f is None or by.state.faction == f.name:
        return
    if k == "hit":
        shift_standing(ctx, by, f, -2, "struck " + t.name)
    elif k == "killed":
        shift_standing(ctx, by, f, -5, "killed " + t.name)
    elif k == "cowed":
        shift_standing(ctx, by, f, -1, "threatened " + t.name)
    elif k == "agreed":
        shift_standing(ctx, by, f, 2, "terms with " + t.name)
    elif k == "given":
        shift_standing(ctx, by, f, 1, "a gift to " + t.name)
'''

THRESHER_RULE = COMMON + '''
def bump(ctx, place, n, why):
    tremor = int(place.state.tremor or 0) + n
    ctx.patch(place, {"tremor": tremor})
    if tremor >= 3 and not place.state.thresher_coming:
        ctx.patch(place, {"thresher_coming": True})
        ctx.emit("tremor", target=place, reach=1, tremor=tremor, why=why,
                 text="The sand under your feet hums. Something far down has turned toward the sound.")
        ctx.schedule(30, "thresher_surfaces", target=place)
    elif tremor == 2:
        ctx.emit("tremor", target=place, reach=1, tremor=tremor, why=why,
                 text="A grain-slide runs off the dune face for no reason you can see.")

def safe_exit(ctx, place):
    for e in ctx.edges(place, "connects_to", "out"):
        x = ctx.get(e["target"])
        if x is not None and not x.state.deep_sand and not x.state.hidden:
            return x
    return None

def surface(ctx, place):
    worms = ctx.find(type="thresher", limit=1)
    if not worms:
        return
    worm = worms[0]
    ctx.move(worm, place)
    ctx.emit("scene", target=place, reach=1, text="The dune splits. The Thresher comes up through the glass like a ship surfacing, mouth first.")
    safe = safe_exit(ctx, place)
    for c in ctx.children(place, "creature"):
        if c.type == "thresher" or c.state.dead:
            continue
        roll = ctx.rand.roll("1d20")
        mod = bonus(c, "survival")
        total = roll + mod
        ok = total >= 13
        ctx.emit("checked", target=c, reach=1, by=c.id, skill="survival", roll=roll, mod=mod, total=total, dc=13, success=ok, margin=total - 13)
        if not ok:
            vigor = int(c.state.vigor or 0) - 4
            ctx.patch(c, {"vigor": vigor, "braced": False})
            ctx.emit("hit", target=c, reach=1, by=worm.id, dmg=4, weapon="the Thresher", attack=0, defence=0, vigor=vigor)
            settle(ctx, c, worm.id)
        if safe is not None:
            ctx.move(c, safe)
            ctx.emit("arrived", target=safe, reach=1, who=c.id, place=safe.id, quiet=True, fled=place.id)
            ctx.emit("scene", target=safe, reach=0, text=(c.name + " scrambles onto the rock, " + ("untouched." if ok else "bleeding, thrown clear by the first pass.")))
    ctx.patch(place, {"tremor": 0, "thresher_coming": False})
    ctx.schedule(10, "thresher_sinks", target=place)

def on(ctx, event):
    k = event.kind
    if k == "arrived":
        place = ctx.get(event.payload.get("place"))
        if place is None or not place.state.deep_sand or event.payload.get("quiet"):
            return
        who = ctx.get(event.payload.get("who"))
        if who is not None and who.type == "thresher":
            return
        bump(ctx, place, 1, "footfall")
    elif k == "harvested":
        vein = ctx.get(event.target)
        if vein is not None and vein.parent is not None and vein.parent.state.deep_sand:
            bump(ctx, vein.parent, 2, "harvest")
    elif k == "thresher_surfaces":
        place = ctx.get(event.target)
        if place is not None:
            surface(ctx, place)
    elif k == "thresher_sinks":
        worms = ctx.find(type="thresher", limit=1)
        if worms and worms[0].state.home:
            ctx.move(worms[0], worms[0].state.home)
            ctx.emit("scene", target=event.target, reach=1, text="The sand closes over the Thresher. The dune is a dune again.")
'''

SCRIPTS = [("check", CHECK), ("attack", ATTACK), ("brace", BRACE), ("yield", YIELD), ("kill", KILL), ("crawl", CRAWL),
           ("threaten", THREATEN), ("parley", PARLEY), ("challenge", CHALLENGE), ("drink", DRINK), ("fill", FILL),
           ("search", SEARCH), ("harvest", HARVEST), ("thirst", THIRST), ("fighter_tick", FIGHTER_TICK),
           ("rules_guard", RULES_GUARD), ("duel_rule", DUEL_RULE), ("factions_rule", FACTIONS_RULE),
           ("thresher_rule", THRESHER_RULE)]

COMBATANT_STATE = {"body": 1, "wits": 1, "will": 1, "skills": {}, "vigor": 6, "max_vigor": 6, "water": 10, "max_water": 10,
                   "wounded": False, "down": False, "dead": False, "braced": False, "yielded": None, "thirsty": False,
                   "cowed_by": None, "attacked_by": None, "faction": None}

COMBATANT_ACTIONS = {
    "check": {"script": "check", "doc": "Try something against a difficulty: d20 + stat + skill vs dc (default 12)",
              "params": {"skill": "blade, brawl, climb, stealth, survival, lore, parley, resolve", "dc": "difficulty, default 12"}},
    "attack": {"script": "attack", "doc": "Strike someone here: opposed roll, a ward stops fast blows, slow passes it at -2",
               "targets": "creature", "scope": "here", "duration": 3, "params": {"slow": "true for the slow blade"}},
    "brace": {"script": "brace", "doc": "Guard yourself: +3 to defence until your next deed", "duration": 3},
    "yield": {"script": "yield", "doc": "Give up to someone here; striking you after that is dishonor", "targets": "creature", "scope": "here"},
    "kill": {"script": "kill", "doc": "Finish someone who is down", "targets": "creature", "scope": "here"},
    "crawl": {"script": "crawl", "doc": "Drag yourself to a connected place, even when down", "targets": "place", "scope": "exits", "duration": 15},
    "threaten": {"script": "threaten", "doc": "Opposed will; a weapon in hand helps you, friends at their side help them",
                 "targets": "creature", "scope": "here", "duration": 2},
    "parley": {"script": "parley", "doc": "Talk terms: wits + parley against their will; success emits agreed with your offer",
               "targets": "creature", "scope": "here", "duration": 5, "params": {"offer": "what you put on the table"}},
    "challenge": {"script": "challenge", "doc": "Call someone out: a duel nobody else may enter", "targets": "creature", "scope": "here"},
    "drink": {"script": "drink", "doc": "Drink from a skin or a vessel within reach (+4 water)", "targets": "thing", "scope": "any", "duration": 2},
    "fill": {"script": "fill", "doc": "Fill a skin you hold at a source here", "targets": "thing", "scope": "held", "duration": 5},
    "search": {"script": "search", "doc": "Take everything off someone who is down or dead", "targets": "creature", "scope": "here", "duration": 5},
}


def define_rules(s):
    """Scripts and the base schemas. Idempotent: run it again and entities pick up the new code."""
    for sid, src in SCRIPTS:
        s.define_script(sid, src)
    s.define_schema("combatant", extends="creature",
                    doc="Someone the d20 rules apply to: three stats, skills, vigor, water, and the verbs of a fight.",
                    state=COMBATANT_STATE, actions=COMBATANT_ACTIONS,
                    behaviors=[{"script": "thirst", "every": 60, "always": True}])
    s.define_schema("faction", extends="entity", doc="A side. Hidden; people name it in state.faction, standing edges point at it.",
                    state={"hidden": True, "hostile": {}})
    s.define_schema("waterskin", extends="thing", doc="Holds water. left out of capacity.",
                    state={"portable": True, "capacity": 3, "left": 3, "description": "A goatskin, heavy and cool.",
                           "description_full": "A goatskin, heavy and cool.", "description_empty": "A goatskin, slack and dry."})
    s.define_schema("vein", extends="thing", doc="Emberglass in the sand. Harvesting takes time and makes noise.",
                    state={"portable": False, "ember": 3},
                    actions={"harvest": {"script": "harvest", "doc": "Dig a shard out (20 s, and the sand hears it)", "duration": 20}})
    s.define_schema("thresher", extends="creature", doc="What lives under the deep sand. It comes to rhythm.",
                    state={"body": 8, "vigor": 40, "max_vigor": 40, "home": None,
                           "description": "You do not see it. You see the dune move."})


def install_rules(s, root):
    """The four world rules on the root. set_rule is idempotent."""
    s.set_rule(root, "rules_guard", kinds=["before_act", "act"])
    s.set_rule(root, "duel_rule", kinds=["before_act", "downed", "killed", "yielded"])
    s.set_rule(root, "factions_rule", kinds=["hit", "killed", "cowed", "agreed", "given", "dishonor"])
    s.set_rule(root, "thresher_rule", kinds=["arrived", "harvested", "thresher_surfaces", "thresher_sinks"])
