# Works: things people build, in time, where others can stop them

Design note, settled with Nate 2026-11-11.

## Why

Most of what enters a running world today enters by storytelling: the author introduces a place or a thing, says
how it came (`introduce`), and seeds who knows it. That is right for what was always there. It is wrong for what
people make. A new floor, a raised wall or a covered cistern should take days, cost real materials and real hands,
and stand half-done where anyone can see it, help it or wreck it. The Reach already has a small one: the pitch
mend, six hours to set, undone by a Dreyer knife. Works makes that a pattern any world can use.

## The pieces

### Blueprint (a thing in the world)

A blueprint is a real thing: a rolled plan, a mason's tally, a Keth knotted cord. It is written by the author, so
the world's shape stays the author's, but once it is in the world it is play's. It can be read, carried, given,
stolen, hidden or burned. It comes in two kinds:

1. **Site-bound**: fixed to a place, and to a position in it, and not portable. "The stairhead, marked out in
   chalk" is a blueprint for the second floor that can only be built there. Whoever its `patrons` name may start it.
2. **Portable**: an item. Whoever holds it may `build` it where they stand, if the place fits what the plan asks
   (`where`: open ground, inside walls, beside water, not hidden). A stolen plan builds for the thief. That is the
   point.

```python
"Plan for a watch platform": {           # a portable blueprint, a letter-like thing you can read
    "where": {"types": ["place"], "open": True, "not": ["hidden"]},
    "stages": [
        {"name": "footings", "labour": 8, "needs": {"Dressed stone": 4}, "roles": {"mason": 1, "hand": 2},
         "scene": "Four squared stones sit in the sand, levelled by eye and then by string."},
        {"name": "frame and deck", "labour": 16, "needs": {"Timber": 4}, "roles": {"carpenter": 1, "hand": 2},
         "settles": 6, "scene": "A deck stands on the footings, high enough to see over a dune."},
    ],
    "becomes": {"type": "thing", "name": "Watch platform", "state": {"sightline": 2}},
}
```

`build` on a blueprint starts the work: the plan goes into the scaffold, and the foreman works from it. Take the
plan out of the scaffold and the work stops at the end of the stage it is on, until someone puts it back. That is
one more way to stop a build without a fight.

### Project (a thing in the world)

Building a blueprint puts a real thing at the site: "Scaffold at the stairhead". Its state says the stage, the
labour done and owed, what materials it holds, the roles and who fills them, and who started it (the patron).
`inspect` on it answers everything a mind needs to plan: what the next stage needs, which roles are open, and
what is stopping it. A stalled project is just a project nobody is working, standing there half-done.

### Stages

Each stage needs its materials in the project before work counts (handed in with `supply`). It needs its roles
present at the site, and its labour in world hours. When the labour is done the stage's scene plays to the room
and the next stage opens. A stage may `settle` (hours after it is done, like curing pitch) during which it can
be undone. That is the window where sabotage lives.

### Roles and the crew

A role is a slot: `mason`, `carpenter`, `hand`, `foreman`, `guard`. A role may want a skill (`craft` 1 for a
mason). There are three ways a slot gets filled:

1. **Hired hands**: workers who come for the work. They are introduced (`how="arrived"`, or `after=` so they are
   expected) with their own small story: a name, a look, a `default_line`, `dialog`, a wage, where they came from
   and who sent them, and who already knows them. They have the standard NPC affordances (talk, give, be hurt,
   be bribed), and they leave if the wage stops. A wage is water or shards a day, so a crew costs the Hold
   something real.
2. **Assigned**: someone with standing over a person puts them in a role. Ruhl can put his nine to work, Taan her
   Keth, Halvard his men. The assignment is a fact on the worker, and a person can only be in one place doing one
   thing, so a guard on the stair is not a guard on the wall.
3. **Volunteered**: anyone, player or mind, takes an open role (`work` at the site in that role). A mind decides
   this the way it decides anything: by its brief and what it wants.

A body with no mind in a role runs a **labour routine**, an idle behaviour like `quench`: in working hours it
walks to the site, works, and walks back to its post at dusk, and it drinks more than a resting body. A mind or a
player works by acting. Either way the progress is the engine's arithmetic, never anyone's say-so.

### Verbs

| verb | who | what it does |
|---|---|---|
| `build` | a patron of a site-bound plan; whoever holds a portable one | starts the blueprint here: the scaffold appears, the plan goes into it |
| `supply` | anyone | hands a material in; the project holds it from then on |
| `work` | anyone in a role, or taking an open one | spends time at the site and adds labour; loud, heard next door |
| `assign` | someone with standing over the worker | puts a mindless person in a role, or takes them out |
| `hire` | the patron | offers a hired hand a wage; they come, or say why not |

Errors point forward, as with every op: "no mason: assign one, hire one, or work as one yourself".

### Interruption

Nothing new is needed, because everything a project uses is real:

- materials can be taken from the site or ambushed on the road before they arrive;
- workers can be thirsty, hurt, bribed, frightened off, or simply not paid;
- a stage that is settling can be undone by a check, the way a knife undoes soft pitch;
- a `guard` role on the site gives the undoing a harder roll.

Each of these is an event with a scene, so the minds see it and the chronicle tells it.

### Completion

The last stage calls `introduce` with `how="built"`, `by` the crew, and `known_by` the crew, the patron and
everyone at the site, each with a note of what they did. The scaffold comes down. The new place or thing is born
with a history nobody had to make up afterwards.

## The small step before it: `introduce(after=...)`

Something announced now that arrives later. The people in `known_by` learn of it now ("a Guild mason comes on
Rook's crawler in three days"), and the scene plays when it lands. This is how sending for timber, a mason or
furniture works, and it is about an hour of work on top of `introduce`. It goes first.

## First use in the Reach: the wall

The moon counts the wall as men: nine wanted, fewer on hand. A blueprint "Raise the wall" with courses of dressed
stone and lime turns that into play. Each finished course counts as a man on the wall at the moon. The stone is
dressed from the Scar by Ruhl's men at dusk. The lime is bought from the Guild at Ossa's price. Keth hands can
come if the truce holds. Dreyer has every reason to stop it: steal the lime, bribe a hand, knock down a course
while it settles. Building becomes part of chapter two's contest, the same as the water.

The second floor (the stair that goes nowhere) is the natural second blueprint: a lookout over the Flats that
lets the Hold see riders from the Bone Field coming.

## Settled with Nate

1. **Who may `build`?** Settled: a site-bound plan names its patrons; a portable plan builds for whoever holds
   it, where its `where` allows. Anyone can then supply or work.
2. **Who has standing to `assign`?** Settled: a faction's named leader over that faction's mindless members, and
   the owner over anyone. A mind is never assigned: it chooses.
3. **Wages**: settled: either, named by the blueprint, paid at dusk.

## Order of work

1. `introduce(after=...)`, with tests.
2. The works pack (`packs/works`): blueprint, project, stages, roles, the five verbs, the labour routine, settle
   and undo, completion through `introduce`. Tests and a soak.
3. The Reach's wall blueprint, wired into the moon's count, and a hired mason who comes on Rook's crawler.
