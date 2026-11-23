"""Table-top rules as embody actions. A world imports this and gets a d20 layer: checks against a
difficulty, opposed attacks with weapons and wards, brace, yield, kill, threaten, parley, duels whose ring
holds, water that runs out, and factions with a standing.

Nothing here is a world. It is a pack: a world names it in its manifest (`"requires": ["d20"]`) and the loader
defines the scripts in scripts/ (every rules script starts with `use("common")`, the helpers in scripts/_common.py)
and runs `define(s)` for the base schemas (`combatant`, `faction`, `waterskin`, `medicine`). The world's
build.py imports `install_rules` from here and puts the four world rules on its root. It then extends `combatant`
with its own verbs (go, take, talk) and spawns the people. `tests/fixtures/worlds/outpost` is the worked example.

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
- A grudge ends. A blow or a shot makes the striker its target's foe (`attacked_by`, and `attacked_at` the world t).
  A fighter keeps that foe only while they stand where it can reach them (here, or in its bow's sight), have not
  yielded to it, and struck it within the root's `grudge_for` (world seconds, default 3600). Walk away and it is
  over: coming back starts nothing. A challenge to a beast is refused (a beast keeps no ring).
- Strikes take their time. `attack`, `shoot` and `kill` are strikes (`strikes: true`): after one, the striker
  waits the engine's cooldown before striking that foe again, and half of it before anyone (docs/SCRIPTING.md,
  Strikes; a minute of real time when a player or a mind holds either side, 15 s when neither does, nothing on a
  paused clock). Blows and shots, a player's or a fighter's, wait times the weapon's `cooldown_x` (2 for a maul).
  A world's own strike verbs say `strikes: true` and their `cooldown_x` and `cost`.
- One bar, `hp`. At half hp you are `wounded`; at 0 you are `down` and can only yield, drink or crawl; `kill`
  finishes someone down, and only a deliberate `kill` or a thirst left too long ends a life; striking someone who yielded to you is `dishonor` and every faction hears of it. A fighter without a mind never strikes one who yielded to it or to anyone of its faction.
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
  full body refuses, so no draw is poured away), `fill` one at a source, and `pour` what one holds into a store here
  (a thing with `water_source` and a `left`: a cask, a jar, a cistern), a skin, or someone here (their first skin with
  room): all of it by default or `amount` draws, never past the store's `capacity` (none: no cap); the rest stays in
  the skin, and `poured` says by, item, store, amount, left and kept. An endless source takes nothing. A body
  nobody embodies looks after itself (the `quench` behavior): thirsty, it drinks from a skin in hand, else from a source here; with nothing
  here it walks toward the nearest water it knows the way to (up to six steps, one step a look; hidden places
  only for their own faction) and walks back to its `post` the same way. No walk steps into or through a place
  where someone of a side that has outlawed the body stands on their feet: it goes around, or waits. A held seat
  gone idle (a mind on a watcher) looks after itself the same way. Stepping out of a vehicle (its way out is
  alight) or of any place with `way_out: true` counts as a step, into the place that holds it, so a body aboard a
  dry hauler climbs down for water; `way_out: false` keeps a sealed place's own. The walks arrive `quiet`. At an endless
  source (a place with `water_source`, or a source thing with no `left`) it drinks its fill (a draw a look until
  it is within a draw of full) and fills its skin; a store with a count (`left`) gives it one draw, the fullest
  store first, and no skinful, so idle bodies never drink a cask dry. A source with `keep_for` (a faction, an
  entity id, or a list of them) is not drunk or walked to by anyone else's idle care; held seats and deeds are
  not stopped by it. A body that is down drinks what is
  put in its hand. An embodied seat decides for itself while it is in use; quench is an `idle` behavior, so a
  seat that has done nothing for the world's `idle_after` (a mind on a watcher, a player asleep) drinks what is
  in reach, a skin in hand or a source here, and never walks: where a held body stands is its seat's choice. `python packs/d20/soak.py <world> --days N` runs a world that long with nobody playing and says who
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
  carries two levels up: a lock broken) or done to it. It is easy prey: a blow on a sleeper rolls twice
  and keeps the better, against bare hands and no brace; `search` works on a sleeper as on someone down, by stealth
  (d20 + wits + stealth against 10 + their wits): done, the `lifted` event names the thief and the sleeper sleeps on;
  fumbled (`caught`), nothing is taken and they wake. A blow, a word said to them, `wake` by someone here, a noise,
  thirst (water 3) or their own next deed wakes them (`woke`, with `by` and `why`). Sleep where nobody would rob you.
- A feud burns out. A blow on a member costs the striker 2 with the member's faction, but a blow struck back at
  someone who struck you first, while that grudge holds (`grudge_for`), costs nothing: the faction counts who
  started the fight. Standing lost to blows climbs back a point a world day after the last blow, up to -3, just
  above outlaw (`standing` with `why` "blows forgiven"; the faction's secret `bruised` keeps what is left, the
  body's secret `bruised_with` the factions). A fight nobody keeps up ends there; one a mind keeps striking stays
  alive. A kill, a threat and dishonor are not forgiven by time.
- A gift (`given`) is worth 1 with the receiver's faction only if they keep it: something they trade away on
  the spot, or something that was theirs to begin with (`given_by` on the thing names who handed it over),
  moves nothing, and a gift handed back to its giver was a loan: the 1 goes again ("lent, not given").
- Terms (`agreed`) and gifts buy standing once a pair a world day: the same doer and the same member, ten offers or
  ten gifts in a day, count once (the faction's secret `courted`).
- A check is one try a skill, a place, a world hour: the same skill again in the same place before then is refused
  with the time left (`tried` on the body; root `check_again_after` in world seconds, 0 lets a world reroll).
- A deed to someone who keeps `faction` in their `secret` list still counts with that faction, but quietly: the
  faction keeps it in its own secret `unseen`, and the doer gets no `standing` event and no edge that names the
  side. Standing is the readable edge plus `unseen`; at -4 the faction still outlaws them, openly.
"""

import json

PACK = {"name": "d20", "description": "Table-top rules as verbs: d20 checks, opposed attacks, wards, duels, thirst, factions."}

# What the engine reads back from this pack (world.PACK_DECLARES): the body keys only these rules write, the chronicle's
# kinds, and the ways out of the conditions these rules put a body in.
BODY_KEYS = ["water", "max_water", "thirsty", "vigor", "max_vigor", "faction", "cowed_by", "oath"]
CHRONICLE_ROUTINE = ["mended", "sweated", "drank", "filled", "thirsty", "parched"]
CHRONICLE_NEWS = ["outlawed", "dishonor", "lifted", "challenged"]
WAYS_OUT = {"hurt": "-2 on every roll until rest mends you past half", "down (wounds)": "rest with water, or someone tends you",
            "down (thirst)": "drink, before the days run out"}

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
    {"id": "grudges-end", "date": "2026-11-15",
     "was": "A fighter or a beast you struck kept you as its foe for good, and you could challenge a beast to a duel.",
     "now": "A grudge ends: when you walk out of its reach, when you yield to it, or a world hour after your last blow "
            "(root grudge_for). Coming back starts nothing unless you strike again. A beast cannot be challenged: "
            "fight it, or walk away.",
     "recheck": ["plans that avoid a place for fear of an old fight", "duels with beasts"], "guide": ["player", "mind"]},
    {"id": "one-try-one-deal", "date": "2026-11-15",
     "was": "A check could be rolled again and again in one place until it landed, and every agreement or gift to "
            "the same member bought standing again.",
     "now": "A check is one try a skill, a place, a world hour (root check_again_after); the refusal says when to "
            "try again. Terms and gifts buy standing once a pair a world day; more that day moves nothing.",
     "recheck": ["plans that roll check until it passes", "plans that farm standing with repeated parley or gifts"],
     "guide": ["player", "mind"]},
    {"id": "feuds-burn-out", "date": "2026-11-21",
     "was": "Every blow on a member cost 2 standing with their faction, a blow struck back as much as the first, and "
            "standing never came back on its own: two sides could outlaw each other for good with no mind in it.",
     "now": "A blow struck back at someone who struck you first, while that grudge holds, costs no standing: the "
            "faction counts who started the fight. Standing lost to blows climbs back a point a world day after the "
            "last blow, up to -3, just above outlaw (standing, why: blows forgiven). Kills, threats and dishonor stay.",
     "recheck": ["plans that avoid a faction for an old fight", "notes on who is outlawed and why"],
     "guide": ["player", "mind"]},
    {"id": "thirst-walks-stay-safe", "date": "2026-11-21",
     "was": "A held seat gone idle (a mind on a watcher) walked its body to the nearest water on its own, and the "
            "walk went through any place, even one where the people who had outlawed it stood.",
     "now": "A held seat drinks what is in reach while idle (a skin in hand, a source here) and never walks; a "
            "thirsty idle seat stays where its mind left it, so carry water. A body nobody holds still walks for "
            "water, but never into or through a place where someone of a side that outlawed it stands.",
     "recheck": ["minds that count on idle care to fetch water", "watchers left far from water"],
     "guide": ["player", "mind"]},
    {"id": "held-seats-fetch-water", "date": "2026-11-21",
     "was": "A held seat gone idle drank only what was in reach and never walked, so a mind on a watcher far from "
            "water went down from thirst.",
     "now": "A held seat gone idle looks after itself again as a body nobody holds does: thirsty, it walks to the "
            "nearest water it knows and back to its post, by the same safe way (never into or through a place where "
            "someone of a side that outlawed it stands).",
     "recheck": ["minds that carry water only because idle care would not fetch it"],
     "guide": ["player", "mind"]},
    {"id": "yield-stops-the-side", "date": "2026-11-23",
     "was": "A yield stopped only the one you yielded to: his comrades and his faction's fighters kept striking.",
     "now": "A fighter without a mind never strikes one who yielded to it or to anyone of its faction. A mind may, "
            "and pays the dishonor as before.",
     "recheck": ["plans that fight on after a yield", "a yield to one guard when the others wear another faction"],
     "guide": ["player", "mind"]},    {"id": "idle-seats-keep-their-place", "date": "2026-11-23",
     "was": "A held seat gone idle (a player or a mind on a watcher) was walked back to its post, a template's or an "
            "old water walk's, even where its player had walked it on purpose.",
     "now": "A held seat gone idle walks only for water, and back only to the place it left for it, while its player "
            "has done nothing since. A post is for a body nobody holds.",
     "recheck": ["watch filters that expect a quiet arrived at the post", "minds that count on idle care to bring them home"],
     "guide": ["player", "mind"]},
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
    "pour": {"script": "pour", "doc": "Pour what a skin you hold carries into a store here (a cask, a jar, a cistern), a skin, or "
                                      "someone here (into their skin), up to what it holds", "targets": "any", "scope": "here", "listed": "ok", "duration": 5,
             "params": {"item": "the skin you pour from (default: the first you hold with water in it)", "amount": "draws to pour (default: all)"}},
    "search": {"script": "search", "doc": "Take what you can carry off someone who is down, dead or asleep (a sleeper by stealth: "
                                          "fumble and they wake); the rest stays on them", "targets": "creature", "scope": "here", "duration": 5},
    "sleep": {"script": "sleep", "doc": "Lie down and sleep: you mend twice as fast, hear only what is loud or done to you, and are "
                                        "easy prey. Your next deed wakes you; so do a blow, a word to you, a noise and thirst", "duration": 2},
    "wake": {"script": "wake", "doc": "Wake someone asleep here with a shake and a word", "targets": "creature", "scope": "here",
             "duration": 1},
    "practice": {"script": "practice", "doc": "Practice a skill alone for an hour against the world's dc for your rank: a little "
                                          "experience, at most a third of each rank from practice (a body with a sheet)",
                 "duration": 3600, "params": {"skill": "the skill to practice (guide('skills') lists them)"}},
    "train": {"script": "train_with", "doc": "Learn from a teacher here, for their price: below what you reach alone a lesson is "
                                            "experience; past it they turn the experience you earned by use into a rank", "targets": "creature",
              "scope": "here", "listed": "ok", "duration": 60, "params": {"skill": "the skill to learn (default: the one they teach)"}},
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
