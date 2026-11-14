"""Table-top rules as embody actions. A world imports this and gets a d20 layer: checks against a
difficulty, opposed attacks with weapons and wards, brace, yield, kill, threaten, parley, duels whose ring
holds, water that runs out, factions with a standing, and a thing under the sand that comes to rhythm.

Nothing here is a world. It is a pack: a world names it in its manifest (`"requires": ["d20"]`) and the loader
defines the scripts in scripts/ (every rules script starts with `use("common")`, the helpers in scripts/_common.py)
and runs `define(s)` for the base schemas (`combatant`, `faction`, `waterskin`, `vein`, `thresher`). The world's
build.py imports `install_rules` from here and puts the four world rules on its root. It then extends `combatant`
with its own verbs (go, take, talk) and spawns the people. `worlds/glass-reach` is the worked example.

The numbers, so a narrator can explain a roll:

- A creature has three stats, `body`, `wits`, `will` (0 to 5), and `skills` (0 to 3 each). Every skill
  leans on one stat: blade, brawl, climb on body; stealth, survival, lore, lockpick, aim on wits; parley, resolve on will.
  lockpick is the locks pack's: `pick` adds the best of lockpick, stealth or craft.
- Every roll's bonus comes from one place, `bonus(who, skill, ctx)` in scripts/_common.py. A body with a `sheet`
  (the sheet pack) rolls its attributes and ranks there instead, adds its `grants`, and learns from difficulties the
  world sets (`learn`); a body without one rolls exactly as below.
- A check is d20 + stat + skill against a difficulty (`dc`, default 12). Wounded costs 2, thirsty costs 2.
  A skill neither the pack nor the body knows is an untrained roll on wits, and the result says so (`untrained`,
  `note` with the skills there are). A hand from someone is `aid` on the body, a list of {bonus, skill, place, by, why,
  until}: the next check of that skill (no skill: any) in that place (no place: anywhere), before `until` (world t),
  adds the bonus and uses it up; the result and the `checked` event carry it. A familiar's `point` writes one.
- An attack is opposed: d20 + body + blade (+ the weapon's bonus) against the defender's d20 + body + blade
  (+3 if braced). Ties go to the defender. A hit does the weapon's `damage` (bare hands 1) to `hp`.
- A `ward` that is switched on hardens against anything fast: a normal attack cannot reach through it. A slow
  attack (`params {"slow": true}`) passes the ward at -2 to hit.
- `shoot` fires what you hold that fires (a weapon with `ranged`; `ammo` names the kind it takes, matched to a
  held thing's `ammo` or `kind`; a weapon with `loaded` false must be loaded first) at someone here or one way
  over that you can see: a way you know with no shut door on it (the verb's scope is `sight`). d20 + wits + aim +
  the weapon's bonus, -2 one way over, against d20 + wits + the `cover` of the place they stand in (true is +2, a
  number that much). Ties go to the defender. A ward that is on stops every shot: a shot is fast. The hit does the
  weapon's `damage` plus the ammo's own. Each shot spends one unit of ammo, which lands where the target stands,
  hit or miss, in a pile anyone there can `take`. The shooter's place sees `shot`, the target's `hit` or
  `missed` with `ranged`. A world's own fire verbs (a crossbow to `load`, a sling) call `shot(ctx, me, t, weapon)`
  from common, after `in_sight`, `can_fire` and `ring_blocks`. Blows use the first weapon held that does not fire.
- A fighter (a body with the `fighter_tick` behavior) with a bow that will fire shoots its foes one way over as
  well as here: whoever struck it last, and anyone its faction has outlawed. So wardens cover a road.
- Strikes take their time. `attack`, `shoot` and `kill` are strikes (`strikes: true`): after one, the striker
  waits the engine's cooldown before striking that foe again, and half of it before anyone (docs/SCRIPTING.md,
  Strikes; a minute of real time when a player or a mind holds either side, 15 s when neither does, nothing on a
  paused clock). Blows and shots, a player's or a fighter's, wait times the weapon's `cooldown_x` (2 for a maul).
  A world's own strike verbs say `strikes: true` and their `cooldown_x` and `cost`.
- One bar, `hp`. At half hp you are `wounded`; at 0 you are `down` and can only yield, drink or crawl; `kill`
  finishes someone down, and only a deliberate `kill` or a thirst left too long ends a life; striking someone who yielded to you is `dishonor` and every faction hears of it.
- A `challenge` makes a duel between two people in a place. While it stands nobody else there may strike,
  and the two may strike only each other. It ends when one is down, dead or yields, when one agrees to the
  other's `parley` (that is a yield on terms), or when one walks out of the ring: that one lost, and their own
  faction marks them down 2 for stepping back.
- `threaten` is opposed will (resolve) with +2 for a weapon in hand and +2 for friends at the target's side.
  Cowed people give way in the dialog tables. `parley` is wits + parley against will + resolve; success emits
  `agreed` with the offer and the world decides what that buys.
- Water: `water` (0 to 10) falls by 1 a beat under shade and 2 on open ground, nothing beside a source (a
  place with `water_source`, or a cask or cistern here with something `left`). The beat is a minute in a
  turn-based story; a hosted world sets its own with `set_pace` (the Reach: one point every 2.4 world hours).
  At 3 you are thirsty; at 0 you lose hp instead, down to 0 and no further: thirst puts a body down
  (`downed_by: thirst`) and a drink brings it back up (`rose`). Left down and dry it dies: `fading` each world
  day it lasts (with `day` and `of`), `died` (`why: thirst`) when its days are spent, counted from when it went
  down. The days go by `body`: 1 for a body of 2 or less, 2 for 3, 3 for 4 and up. A world sets
  `thirst_death_days` on its root in the same shape (`{"0": 1, "3": 2, "4": 3}`: the days for a body of at least
  that much), or false for a thirst that never kills. `drink` from a waterskin (+4; a
  full body refuses, so no draw is poured away), `fill` one at a source. A body nobody embodies looks after
  itself (the `quench` behavior): thirsty, it drinks from a skin in hand, else from a source here; with nothing
  here it walks toward the nearest water it knows the way to (up to six steps, one step a look; hidden places
  only for their own faction) and walks back to its `post` the same way. The walks arrive `quiet`. At an endless
  source (a place with `water_source`, or a source thing with no `left`) it drinks its fill (a draw a look until
  it is within a draw of full) and fills its skin; a store with a count (`left`) gives it one draw, the fullest
  store first, and no skinful, so idle bodies never drink a cask dry. A source with `keep_for` (a faction, an
  entity id, or a list of them) is not drunk or walked to by anyone else's idle care; held seats and deeds are
  not stopped by it. A body that is down drinks what is
  put in its hand. An embodied seat decides for itself while it is in use; quench is an `idle` behavior, so a
  seat that has done nothing for the world's `idle_after` (a mind on a watcher, a player asleep) drinks the same
  way. `python packs/d20/soak.py <world> --days N` runs a world that long with nobody playing and says who
  went dry and which sources ran out.
- Sweat: heavy work costs water on top of the beat. A blow in a fight (`attack`, or a fighter's own), `harvest`,
  `dig`, `dress`, `break` (a lock forced) and a walk (`go`, `crawl`) to or from open ground under more than half
  your `carry` each cost a point (`sweated`, reach 0, with `by` and `cost`). Talk, look, wait, `pick` and `drink`
  are free; works labour pays in its own tick. A world sets `sweat` on its root to tune it: a table by key (a verb,
  or `fight` and `heavy_walk`) laid over the default `{fight: 1, harvest: 1, dig: 1, dress: 1, break: 1,
  heavy_walk: 1}`, or `false` for none.
- Mending: rest heals. A body with water in it (more than 3) mends a point of `hp` a beat (`mended`): the
  `mend` behavior, a beat of ten minutes in a turn-based story, the world's own with `set_pace` (the Reach: one point
  every six world hours). Above half hp the wound closes (`wounded` off). A body a wound put down gets up on its
  own at 2 (`rose`, by rest); thirst's down is water's to undo, and a dry body does not mend. Mending is thirsty
  work: every second point mended costs a point of water. `tend` someone down here: a draw of water washes the
  wound (from a skin in hand, else a cask or source here; spent whether the binding holds or not) and survival
  against 12 binds them so they stand at 1. With `medicine` in hand (a thing with `doses` left) a
  dose heals its `heals` (default 3) at once, no roll, on anyone hurt, the down included; that is what a medic
  carries. Bare hands do nothing for someone already on their feet.
- Sleep: `sleep` lies a body down (`asleep`, a `slept` event; a seat going away can do it with `away(sleep=true)`). Asleep it
  mends two points a beat for the water of one, dries at half the pace (a half carried to the next beat in
  `thirst_owed`), and hears only what is loud (an event that says `loud`, or that
  carries two levels up: a lock broken, the thresher) or done to it. It is easy prey: a blow on a sleeper rolls twice
  and keeps the better, against bare hands and no brace; `search` works on a sleeper as on someone down, by stealth
  (d20 + wits + stealth against 10 + their wits): done, the `lifted` event names the thief and the sleeper sleeps on;
  fumbled (`caught`), nothing is taken and they wake. A blow, a word said to them, `wake` by someone here, a noise,
  thirst (water 3) or their own next deed wakes them (`woke`, with `by` and `why`). Sleep where nobody would rob you.
- A gift (`given`) is worth 1 with the receiver's faction only if they keep it: something they trade away on
  the spot, or something that was theirs to begin with (`given_by` on the thing names who handed it over),
  moves nothing, and a gift handed back to its giver was a loan: the 1 goes again ("lent, not given").
- A deed to someone who keeps `faction` in their `secret` list still counts with that faction, but quietly: the
  faction keeps it in its own secret `unseen`, and the doer gets no `standing` event and no edge that names the
  side. Standing is the readable edge plus `unseen`; at -4 the faction still outlaws them, openly.
- Deep sand (`deep_sand` on a place) keeps a `tremor` count: each loud arrival adds 1, each harvest adds 2, a
  quiet arrival adds nothing. Two minutes of quiet and the count drops by one, down to zero, when a `tremor`
  event says the dune is still. At 3 the thresher is thirty seconds away. When it surfaces everyone there
  rolls survival against 13: pass and you reach the nearest rock; fail and it takes 4 hp off you first.
"""

import json

PACK = {"name": "d20", "description": "Table-top rules as verbs: d20 checks, opposed attacks, wards, duels, thirst, factions, the thresher."}

# This pack's rules changelog, oldest first: what changed for a body in play. A world that requires the pack logs
# these at its build or upgrade, and seats behind hear of them in perceive (guide('changes')).
RULES = [
    {"id": "rest-mends", "date": "2026-11-10",
     "was": "A wound stayed until someone healed it.",
     "now": "Rest mends: a body with water in it gets a point of hp back each beat, and one a wound put down gets up on "
            "its own at 2. tend (survival vs 12) gets someone down up at 1; medicine heals at once. Mending costs "
            "water: a point for every second point given back, and a bare-hands tend spends a draw.",
     "recheck": ["notes on healing", "plans that wait for a wound to close"], "guide": ["player", "mind"]},
    {"id": "sweat", "date": "2026-11-11",
     "was": "Only time made a body thirsty.",
     "now": "Heavy deeds cost a point of water each (sweated): a blow, harvest, dig, dress, break, and walking to or "
            "from open ground under more than half your carry. Talk, look, wait, pick and drink are free. A sleeper "
            "dries at half the pace.",
     "recheck": ["water plans", "watch filters on water"], "guide": ["player", "mind"]},
    {"id": "strike-cooldowns", "date": "2026-11-13",
     "was": "A fighter could strike again as fast as the calls came.",
     "now": "attack, shoot and kill are strikes: after one, you wait before striking that target again (half as long "
            "for anyone else). A strike too soon is refused with the wait, and perceive's affordances show it. A heavy "
            "weapon waits longer, a light one less.",
     "recheck": ["fight plans and scripts that strike in a loop"], "guide": ["player", "mind"]},
    {"id": "hp-bar", "date": "2026-11-14",
     "was": "Two health numbers, vigor and hp.",
     "now": "One: hp and max_hp. Every creature's card carries condition (fine, hurt, down (wounds), down (thirst), "
            "dead) and way_out, what gets it out of that.",
     "retired": ["vigor", "max_vigor"],
     "recheck": ["memories and notes that count vigor", "watch filters on vigor", "scripts that read vigor"],
     "guide": ["player", "mind"]},
    {"id": "death-stays", "date": "2026-11-14",
     "was": "A body could be put down, and someone could always get it up again.",
     "now": "Dead is dead: a dead body hears 'you are dead' before any other refusal, for every verb and for say. It "
            "keeps its seat and its perceive, and nothing brings it back. Down is not dead: tend or rest still gets a "
            "downed body up.",
     "recheck": ["plans that count on getting back up", "watch filters on condition"], "guide": ["player", "mind"]},
    {"id": "thirst-kills", "date": "2026-11-14",
     "was": "Thirst put a body down and never killed it.",
     "now": "Thirst kills, slowly: a body thirst put down that stays dry gets fading each world day and dies (died, "
            "why: thirst) after 1, 2 or 3 days by its body. Water or a tend clears the count.",
     "recheck": ["water plans", "watch filters: wake on fading"], "guide": ["player", "mind"]},
]

COMBATANT_STATE = {"body": 1, "wits": 1, "will": 1, "skills": {}, "hp": 6, "max_hp": 6, "water": 10, "max_water": 10,
                   "wounded": False, "down": False, "dead": False, "braced": False, "yielded": None, "thirsty": False,
                   "cowed_by": None, "attacked_by": None, "faction": None, "asleep": False}

COMBATANT_ACTIONS = {
    "check": {"script": "check", "doc": "Try something against a difficulty: d20 + stat + skill vs dc (default 12)",
              "params": {"skill": "blade, brawl, climb, stealth, survival, lore, lockpick, aim, parley, resolve", "dc": "difficulty, default 12"}},
    "attack": {"script": "attack", "strikes": True, "doc": "Strike someone here: opposed roll, a ward stops fast blows, slow passes it at -2",
               "targets": "creature", "scope": "here", "duration": 3, "params": {"slow": "true for the slow blade"}},
    "shoot": {"script": "shoot", "strikes": True, "doc": "Shoot someone here or one way over with what you hold that fires: a ward stops it, cover helps them, the shot lands where they stand",
              "targets": "creature", "scope": "sight", "reach": "sight", "duration": 3},
    "brace": {"script": "brace", "doc": "Guard yourself: +3 to defence until your next deed", "duration": 3},
    "yield": {"script": "yield", "doc": "Give up to someone here; striking you after that is dishonor", "targets": "creature", "scope": "here"},
    "kill": {"script": "kill", "strikes": True, "doc": "Finish someone who is down", "targets": "creature", "scope": "here"},
    "crawl": {"script": "crawl", "doc": "Drag yourself to a connected place, even when down", "targets": "place", "scope": "exits", "duration": 15},
    "threaten": {"script": "threaten", "doc": "Opposed will; a weapon in hand helps you, friends at their side help them",
                 "targets": "creature", "scope": "here", "duration": 2},
    "parley": {"script": "parley", "doc": "Talk terms: wits + parley against their will; success emits agreed with your offer",
               "targets": "creature", "scope": "here", "duration": 5, "params": {"offer": "what you put on the table"}},
    "challenge": {"script": "challenge", "doc": "Call someone out: a duel nobody else may enter", "targets": "creature", "scope": "here"},
    "drink": {"script": "drink", "doc": "Drink from a skin or a vessel within reach (+4 water)", "targets": "thing", "scope": "any", "duration": 2},
    "fill": {"script": "fill", "doc": "Fill a skin you hold at a source here", "targets": "thing", "scope": "held", "duration": 5},
    "search": {"script": "search", "doc": "Take what you can carry off someone who is down, dead or asleep (a sleeper by stealth: "
                                          "fumble and they wake); the rest stays on them", "targets": "creature", "scope": "here", "duration": 5},
    "sleep": {"script": "sleep", "doc": "Lie down and sleep: you mend twice as fast, hear only what is loud or done to you, and are "
                                        "easy prey. Your next deed wakes you; so do a blow, a word to you, a noise and thirst", "duration": 2},
    "wake": {"script": "wake", "doc": "Wake someone asleep here with a shake and a word", "targets": "creature", "scope": "here",
             "duration": 1},
    "tend": {"script": "tend", "doc": "See to someone hurt here (or yourself): medicine in hand heals a dose's worth, bare hands "
                                      "(survival vs 12) get a downed body up at 1", "targets": "creature", "scope": "here", "duration": 10},
}

def define(s):
    """Scripts and the base schemas. Idempotent: run it again and entities pick up the new code."""
    s.define_schema("combatant", extends="creature",
                    doc="Someone the d20 rules apply to: three stats, skills, hp, water, and the verbs of a fight.",
                    state=COMBATANT_STATE, actions=COMBATANT_ACTIONS,
                    behaviors=[{"script": "thirst", "every": 60, "always": True},
                               {"script": "quench", "every": 60, "idle": True},
                               {"script": "mend", "every": 600, "always": True}])
    s.define_schema("faction", extends="entity", doc="A side. Hidden; people name it in state.faction, standing edges point at it.",
                    state={"hidden": True, "hostile": {}})
    s.define_schema("waterskin", extends="thing", doc="Holds water. left out of capacity.",
                    state={"portable": True, "capacity": 3, "left": 3, "description": "A goatskin, heavy and cool.",
                           "description_full": "A goatskin, heavy and cool.", "description_empty": "A goatskin, slack and dry."})
    s.define_schema("medicine", extends="thing", doc="Doses that heal: tend someone with it in hand.",
                    state={"portable": True, "medicine": True, "doses": 3, "heals": 3,
                           "description": "A pouch of salve, bitter-smelling.", "description_empty": "An empty pouch, still bitter."})
    s.define_schema("vein", extends="thing", doc="Emberglass in the sand. Harvesting takes time and makes noise; each shard joins the Emberglass stack in hand.",
                    state={"portable": False, "ember": 3},
                    actions={"harvest": {"script": "harvest", "doc": "Dig a shard out (20 s, and the sand hears it)", "duration": 20}})
    s.define_schema("thresher", extends="creature", doc="What lives under the deep sand. It comes to rhythm.",
                    state={"body": 8, "hp": 40, "max_hp": 40, "home": None,
                           "description": "You do not see it. You see the dune move."})


define_rules = define  # the old name


def keep_behaviors(w, scripts=("mend",)):
    """Bodies spawned before a behavior joined their schema get its tick now, at the world's pace (a saved or hosted
    world made before `mend` existed). Only the named scripts, so a tick someone stopped on purpose stays stopped.
    Returns how many ticks it added. Idempotent."""
    pace = w.meta().get("pace") or {}
    have = {(i["entity_id"], (i["payload"] or {}).get("script")) for i in w.pending() if i["kind"] == "tick"}
    n = 0
    for e in w.find(limit=100000):
        for b in w.schema_components(e["type"], "behaviors"):
            if b["script"] not in scripts or (e["id"], b["script"]) in have:
                continue
            every = float(pace.get(b["script"], b.get("every", 10)))
            w.schedule(every, "tick", entity=e["id"], payload={"script": b["script"], "always": bool(b.get("always"))},
                       every=every, log=False)
            n += 1
    return n


def _renamed(v):
    """A value with every vigor key in it renamed: vigor to hp, max_vigor to max_hp, at any depth (a species'
    stages, a template's state, a kit). None when nothing in it changes."""
    if isinstance(v, dict):
        out, changed = {}, False
        for k, x in v.items():
            nk = HP_KEYS.get(k, k)
            nx = _renamed(x)
            changed = changed or nk != k or nx is not None
            out[nk] = x if nx is None else nx
        return out if changed else None
    if isinstance(v, list):
        items = [_renamed(x) for x in v]
        return [x if n is None else n for x, n in zip(v, items)] if any(n is not None for n in items) else None
    return None


HP_KEYS = {"vigor": "hp", "max_vigor": "max_hp"}


def hp_from_vigor(w):
    """One health bar (2026-11-14): every body's vigor becomes its hp, and max_vigor its max_hp, the way a creature's
    core hp already reads. Tables that carry them (a species' stages, the root's templates) are renamed too, and the
    old keys go. Returns how many entities changed. Idempotent: a world with no vigor left is untouched."""
    n = 0
    for e in w.find(limit=1000000):
        st = e["state"]
        if not any(k in json.dumps(st) for k in ('"vigor"', '"max_vigor"')):
            continue
        new = _renamed(st)
        if new is None:
            continue
        changes = {k: v for k, v in new.items() if st.get(k) != v}
        changes.update({k: None for k in st if k not in new})  # the old keys, gone
        w.patch(e["id"], changes, replace=True)
        n += 1
    return n


def install_rules(s, root):
    """The four world rules on the root. set_rule is idempotent. A world made when health was `vigor` has it renamed
    to hp on the way (hp_from_vigor)."""
    hp_from_vigor(s.world if hasattr(s, "world") else s)
    s.set_rule(root, "rules_guard", kinds=["before_act", "act"])
    s.set_rule(root, "duel_rule", kinds=["before_act", "downed", "killed", "yielded", "arrived", "agreed"])
    s.set_rule(root, "factions_rule", kinds=["hit", "killed", "cowed", "agreed", "given", "dishonor"])
    s.set_rule(root, "thresher_rule", kinds=["arrived", "harvested", "tremor_settles", "thresher_surfaces", "thresher_sinks"])
