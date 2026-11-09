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
  leans on one stat: blade, brawl, climb on body; stealth, survival, lore on wits; parley, resolve on will.
- A check is d20 + stat + skill against a difficulty (`dc`, default 12). Wounded costs 2, thirsty costs 2.
- An attack is opposed: d20 + body + blade (+ the weapon's bonus) against the defender's d20 + body + blade
  (+3 if braced). Ties go to the defender. A hit does the weapon's `damage` (bare hands 1) to `vigor`.
- A `ward` that is switched on hardens against anything fast: a normal attack cannot reach through it. A slow
  attack (`params {"slow": true}`) passes the ward at -2 to hit.
- At half vigor you are `wounded`; at 0 you are `down` and can only yield, drink or crawl; `kill` finishes
  someone down; striking someone who yielded to you is `dishonor` and every faction hears of it.
- A `challenge` makes a duel between two people in a place. While it stands nobody else there may strike,
  and the two may strike only each other. It ends when one is down, dead or yields, when one agrees to the
  other's `parley` (that is a yield on terms), or when one walks out of the ring: that one lost, and their own
  faction marks them down 2 for stepping back.
- `threaten` is opposed will (resolve) with +2 for a weapon in hand and +2 for friends at the target's side.
  Cowed people give way in the dialog tables. `parley` is wits + parley against will + resolve; success emits
  `agreed` with the offer and the world decides what that buys.
- Water: `water` (0 to 10) falls by 1 per minute under shade and 2 on open ground, nothing beside a source (a
  place with `water_source`, or a cask or cistern here with something `left`). At 3 you are thirsty; at 0 you
  lose vigor instead. `drink` from a waterskin (+4), `fill` one at a source. A body nobody embodies drinks on
  its own when it is thirsty and water is in reach (the `quench` behavior): a skin in hand first, then a source
  here, filling its skin while it is there. An embodied seat decides for itself.
- A gift (`given`) is worth 1 with the receiver's faction only if they keep it: something they trade away on
  the spot, or something that was theirs to begin with (`given_by` on the thing names who handed it over),
  moves nothing.
- Deep sand (`deep_sand` on a place) keeps a `tremor` count: each loud arrival adds 1, each harvest adds 2, a
  quiet arrival adds nothing. Two minutes of quiet and the count drops by one, down to zero, when a `tremor`
  event says the dune is still. At 3 the thresher is thirty seconds away. When it surfaces everyone there
  rolls survival against 13: pass and you reach the nearest rock; fail and it takes 4 vigor off you first.
"""

PACK = {"name": "d20", "description": "Table-top rules as verbs: d20 checks, opposed attacks, wards, duels, thirst, factions, the thresher."}

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

def define(s):
    """Scripts and the base schemas. Idempotent: run it again and entities pick up the new code."""
    s.define_schema("combatant", extends="creature",
                    doc="Someone the d20 rules apply to: three stats, skills, vigor, water, and the verbs of a fight.",
                    state=COMBATANT_STATE, actions=COMBATANT_ACTIONS,
                    behaviors=[{"script": "thirst", "every": 60, "always": True},
                               {"script": "quench", "every": 60}])
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


define_rules = define  # the old name


def install_rules(s, root):
    """The four world rules on the root. set_rule is idempotent."""
    s.set_rule(root, "rules_guard", kinds=["before_act", "act"])
    s.set_rule(root, "duel_rule", kinds=["before_act", "downed", "killed", "yielded", "arrived", "agreed"])
    s.set_rule(root, "factions_rule", kinds=["hit", "killed", "cowed", "agreed", "given", "dishonor"])
    s.set_rule(root, "thresher_rule", kinds=["arrived", "harvested", "tremor_settles", "thresher_surfaces", "thresher_sinks"])
