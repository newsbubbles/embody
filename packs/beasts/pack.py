"""Beasts: animals that grow up, eat what the land gives, can be tamed and kept, and breed as far as the land carries.

A world names it after d20 in its manifest (`"requires": ["d20", "beasts"]`): the pack's scripts use d20's rolls and
blows. It defines the `species` and `beast` schemas and one rule, which a world installs on its root with
`install_rules(s, root, day="dawn", night="dusk")`, naming the event kind that turns its day and the one that is its
night (when predators hunt) (a world with no dawn schedules a repeating one on its root: `s.schedule(86400,
"beast_day", entity=root, every=86400)` and `day="beast_day"`; an event with no target reaches no rule). The day walks
every beast and place, so the rule asks for `fuel` (default `FUEL`, 400,000 operations; twelve beasts in the Glass
Reach used about 15,500, against a rule's default of 20,000). Everything
happens on that event, once a day, in this order: forage regrows, carcasses rot, predators hunt (with no night),
beasts age and grow, they eat or go hungry, kept ones gain or lose loyalty, the young due are born, pairs conceive,
and kept beasts give what they give.

A species is a hidden `species` entity named by its id ("thornback"); a beast's `species` names it. Every value below
may also sit on a beast itself, which wins over its species:

- `stages`: [{"name": "young", "from": 0, "state": {...}}, {"name": "adult", "from": 6, ...}, {"name": "old", "from":
  60, ...}], `from` in days of age. On the day a beast's `age` reaches a stage it takes that stage's `state` (body,
  vigor and max_vigor, skills, carry, description: a wound it has stays, vigor moves by what max_vigor gains) and its
  `parts` (things spawned on it once, such as tusks with `weapon`). A born beast (`stage_names`) also takes the stage's
  name: `names` {"m": "Thornback boar", "f": "Thornback sow"}; an authored name stays.
- `lifespan` (days): past it, each day a chance `old_death` (default 0.2) that it dies in its sleep.
- `eats`: diet tags ["root", "pulp", "carrion", "graze"]. `fed_max` (default 3).
- `tame_dc` and `tame_at`: a number, or a table by stage ({"young": 11, "adult": 14}); a stage the table leaves out is
  never tamed, nor is a beast with `leader`. `tame_skill` (default survival).
- `breeds` (a mother's stages, default ["adult"]), `sires` (a father's, default ["adult", "old"]), `breed_chance`
  (default 0.25), `season` (true: only while the species has `in_season`, which a world rule sets), `gestation` (days,
  default 6), `litter` [min, max], `young_name`.
- `starve_days` (default 2): a wild beast that many days hungry dies.
- `guards`: a kept one growls (`growled`) at a stranger arriving where it is (not its owner's faction) and takes up
  its owner's fight. `yields`: {"name": "Goat's milk", "state": {...}, "max": 2, "stages": ["adult"], "sex": "f"}: a
  kept beast fed 2 or more puts one by it each day, up to `max` lying there.

A beast's own state: `species`, `sex` ("m"/"f"), `age` (days), `stage`, `fed`, `hungry` and `hungry_days`, `owner`
(a body), `herd` (a faction or place it belongs to, kept without an owner), `loyalty` (0 to 5), `follows`, `staying`,
`home` (where it goes feral to), `pack`, `leader`, `riled` (a world sets it, at night in its ground: not calm),
`carrying` {due, sire}, `trust`, `gentled` and `fed_by` (by body id: the day of each). `beast_day` on the root counts
the days.

Diet and hunger. A place's `forage` is {tag: {"left": n, "max": m, "regrow": r}}: each day `regrow` comes back up to
`max`, and that is what the land carries. Each day every beast is a meal shorter; then the beasts in a place eat its
forage of their diet, a meal each first so it is shared (the grown, then the young, the old last), then what else they
are short. At 0 a beast is `hungry` (`beast_hungry`): a wild one walks one way over toward the most it eats (with
nothing near, a way toward its `home`) and dies at `starve_days`. A wild grazer that is not hungry and stands away from
home walks back a way a day when home has more of what it eats than where it stands; hunters keep to where they hunt. A food item has `food` (a tag or a list) and `feeds` (meals); `portions` uses it more than once, a
stack goes one at a time. `feed` from your hand gives the meals, up to full (a full beast still takes it from a hand,
as a treat), and refuses food it does not eat ("sniffs the grain and turns away").

Taming. `gentle` needs the beast calm (not riled, not hungry, its foe not standing there) and fed from your hand today,
once a day per beast per person: d20 + your tame skill against its tame_dc. A success is a point of `trust` toward
you (`beast_trust`); fail by 5 or more and it bites (`beast_bit`, then a d20 blow) and you lose a point. At `tame_at`
it is yours (`beast_tamed`): owner, follows you, loyalty 3, out of its pack. A young beast at tame_at 3 takes three
days of visits at least.

Kept beasts follow their owner where the village `go` takes them (`follows`). `stay` leaves it, `come` calls it (one
way over, if the way is open), `release` lets it go. Loyalty each day: +1 if its owner fed it the day before, else -1
if it was not full all day; -1 more if hungry; -1 more when it has been two days away from its owner. A blow from its
owner costs 1. At 0 it goes feral (`beast_feral`): no owner, no herd, back to its `home`. A herd beast (no owner)
gains loyalty when anyone feeds it and loses it only to hunger. A dead owner leaves it feral at the next day.

Breeding. At the day, an adult female and an adult male of one species in one place, both fed 2 or more, she not
carrying: `breed_chance` that she is (`beast_carrying`), only in season if the species has one, and only if there are
fewer of her species there (the old not counted: they eat last and go first; the young on the way counted, each
carrying female's least `litter`) than the place's forage of their diet regrows a day, unless someone fed her by hand. So a wild herd grows to what the land carries and stops, and kept herds
grow as fast as their keepers feed them. `gestation` days later `litter` young are born where she is (`beast_born`),
age 0, wild or kept as she is, following her owner.

Carnivores and hunting. A species with `preys_on` (species ids) hunts; it eats `meat` and `carrion`, which only the
dead give. A dead beast is a carcass where it lies: `meals` (its species' `carcass`, default its max_vigor) of meat
and carrion, carrion only after a day, bones after three; beasts whose diet matches eat it at the day, and people cut
a meal off with `butcher` to carry (the way to keep a tamed hunter fed: the dearest beast to keep). A `killed` beast
becomes a carcass too. Once a night (the kinds `install_rules` names as `night`; with none, at the start of the day),
each wild pack (its species in one place) with a member at fed below `hunts_below` (default 1: the hungry) hunts the
weakest prey within reach: its place, its home and the places next to its home, one place further after `range_after`
(default 2) days hungry, which is when it comes for the herds by the houses. Weakest is young or old, hurt, alone and
nobody's. The pack walks to it (`beast_hunts`); the prey may flee (d20 + survival against 10 + 2 a hunter:
`beast_fled`), else up to six rounds of d20 blows, its herd and its owner's guard beasts striking back, until it is
down (`killed`, a carcass) or half the pack is (`beast_hunt_failed`). A person is hunted only by a species with
`attacks_people` or a ranging pack, only alone, and is fought for real: the hunters take them as their foe and their
fighter ticks fight at the world's pace, so they can run or fight; a person they down is left down, not eaten. Two
guards against an empty map: a prey species keeps its last `refuge` (default 2) within a pack's reach, and its last
grown male and female, out of reach; and a hunter species with `wanders_in` {"at": place, "prey": n, "count": [a, b]}
comes back from beyond the map once none of it is left and its prey number n. A hunter breeds only with `prey_per`
(default 3) prey within reach for each of its kind there, one more (`room`: "prey"; grazers have "forage"). A pack of
three jackals and four goats on a ridge regrowing 5 keep both alive for ninety days in the pack's test, the herd
between 3 and 8.

Events: `beast_grew`, `beast_hungry`, `beast_tamed`, `beast_trust`, `beast_bit`, `beast_shied`, `beast_feral`,
`beast_carrying`, `beast_born`, `beast_died` {why: hunger, age}, `beast_yielded`, `beast_stays`, `beast_comes`,
`beast_released`, `growled`, `fed`, `beast_hunts`, `beast_fled`, `beast_hunt_failed`, `killed` {by, why: hunt},
`beast_wandered_in`, `butchered`. Walks arrive `quiet`.

What a world does not need: no ticks of its own for hunger or growth (the day does it), no follow code (village `go`
moves whoever `follows` the walker), and no fight code (beasts run d20's `fighter_tick`, so a struck beast or a kept
guard whose owner is struck fights back).
"""

PACK = {"name": "beasts", "description": "Animals that grow up, eat what the land gives, can be tamed and kept, and breed as far as the land carries."}

BEAST_STATE = {"beast": True, "species": None, "sex": None, "age": 0, "stage": None, "fed": 3, "hungry": False,
               "hungry_days": 0, "owner": None, "herd": None, "loyalty": None, "follows": None, "staying": False,
               "home": None, "pack": False, "leader": False, "carrying": None, "trust": {}, "gentled": {}, "fed_by": {},
               "body": 2, "wits": 1, "will": 1, "skills": {}, "vigor": 6, "max_vigor": 6, "down": False, "dead": False,
               "wounded": False, "attacked_by": None, "asleep": False}

BEAST_ACTIONS = {
    "feed": {"script": "beast_feed", "doc": "Feed it from your hand: something you hold that it eats",
             "params": {"item": "what you feed it"}, "duration": 5},
    "gentle": {"script": "beast_gentle", "duration": 10,
               "doc": "Win its trust: calm, and fed from your hand today; once a day. Enough trust and it is yours"},
    "stay": {"script": "beast_stay", "doc": "Tell your beast to stay here"},
    "come": {"script": "beast_come", "reach": "sight", "doc": "Call your beast to you: here it follows again, one way over it comes"},
    "release": {"script": "beast_release", "doc": "Let your beast go wild"},
    "butcher": {"script": "beast_butcher", "duration": 30,
                "doc": "Cut a meal of meat from a dead beast here, to carry and feed by hand"},
}


def define(s):
    """The two schemas. Idempotent."""
    s.define_schema("species", extends="entity",
                    doc="What a kind of beast is: stages, diet, taming, breeding. Hidden; beasts name it in `species`.",
                    state={"hidden": True, "stages": [], "eats": [], "fed_max": 3})
    s.define_schema("beast", extends="creature",
                    doc="An animal: grows, eats, can be tamed and kept, breeds. d20 blows land on it and it fights back.",
                    state=BEAST_STATE, actions=BEAST_ACTIONS,
                    behaviors=[{"script": "fighter_tick", "every": 6}])


FUEL = 400_000  # one day's walk: the ninety-day hunters test peaks near 21,000, the Reach at twelve beasts 15,500

def install_rules(s, root, day="dawn", night=None, fuel=FUEL):
    """The beasts' rule on the root: `day` (an event kind, or a list) turns their day; `night` (a kind or a list, or
    None) is when predators hunt, else they hunt at the start of the day. `fuel`: the rule's budget for one day's
    walk over every beast and place (the default holds a few hundred beasts). Idempotent."""
    days = [day] if isinstance(day, str) else list(day)
    nights = [] if night is None else ([night] if isinstance(night, str) else list(night))
    s.patch(root, {"beast_night": nights or None})
    s.set_rule(root, "beasts_rule", kinds=days + nights + ["arrived", "hit", "missed", "killed"], fuel=fuel)
