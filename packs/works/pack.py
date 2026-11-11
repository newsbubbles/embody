"""Works: things people build, in time, where others can help or stop them (docs/WORKS.md has the design).

A world names it in its manifest (`"requires": ["works"]`); the pack defines two schemas and their verbs, so a world
binds nothing on its people. Every verb is done to the plan or to the works, by whoever stands near them.

- blueprint: a plan that is a thing in the world. Its state says what it makes (`becomes`: type, name, state, and
  the `scene` the room sees when it stands), its `stages`, and who may start it:
  - portable (`portable: True`): whoever holds it builds it where they stand, if the place fits `where`
    ({"types": [...], "places": [names], "has": [state flags], "not": [state flags]}). A stolen plan builds for
    the thief.
  - site-bound (`portable: False`, lying in its place): only its `patrons` (names, ids or factions) start it, there.
  - `hours` [from, to] in world hours of the day when the crew nobody plays works (default: any hour); `pay_every`
    in world seconds (default a day); `begun_scene`; `text` for `study`. `project` and `built` are written by play.
- a stage: {"name", "labour": person-hours, "needs": {material: count}, "roles": {role: count}, "settles": hours,
  "scene", "undone"}. A material is a thing whose name or `kind` is the key, one unit each or `count` in a stack.
  Work counts only while the stage's materials are in the works, every role it wants is on hand at the site, and the
  plan is in the works (or, for a stage already begun, was). When the labour is done the materials are used up,
  the scene plays, and a stage that `settles` can be undone (`undo`) until it has.
- project: the works themselves, a thing at the site that holds the plan, the materials and the pay (`take` and
  `put` from the village pack reach into it: a thief can empty it). Its state: stage, labour, crew {id: {role, how,
  wage, unpaid, home}}, hands (everyone who has worked), patron, settling_until. Its description says how far along
  it is and the first thing stopping it.
- the crew, three ways: hired (`hire` someone whose state has `for_hire` {"wage": {"kind", "count"}, "roles",
  "line"}; paid from the works each pay day, two days unpaid and they walk off), assigned (`assign`: the `leader`
  named on a faction's state, a name or a list of names, puts that side's people with no mind to work; the owner does it by acting as the
  leader), volunteered (anyone takes an open role by working). A mind is never assigned or hired: it works by
  choosing to.
- the labour routine is the project's tick, every ten world minutes: the crew nobody plays walks in from one step
  away in working hours and home after, works while it is there and nothing stops it, and gets thirsty doing it
  (a point of water every two hours worked). Someone a mind or a player holds works by `work`: an hour each, counted
  when the hour is out, nothing if they leave or the materials are gone by then.
- when the last stage stands (and has settled) the thing is spawned at the site with provenance {how: built, by:
  the hands, patron, plan}; the hands, the patron and everyone at the site remember it; the plan is marked `built`
  and the works come down, leaving whatever they still held on the ground.

Verbs: on a plan, `study` (what it makes and asks) and `build`; on the works, `survey` (what is done, what is
next, what stops it), `supply` (params item), `work` (params role, an hour), `assign` (params who, role, or role
"none"), `hire` (params who, role), `undo` (a stage that is still settling: 1d20 + body against 10, 4 more for
each guard at work). Every refusal says what to do instead.
"""

PACK = {"name": "works", "description": "Blueprints as things in the world, and works that take materials, hands and time to build them, where anyone can help or stop them."}


def define(s):
    """The two schemas. Idempotent."""
    s.define_schema("blueprint", extends="thing",
                    doc="A plan that is a thing: study it, build from it. Portable plans build for whoever holds them.",
                    state={"portable": True, "where": {}, "stages": [], "becomes": {}, "patrons": [], "hours": None,
                           "project": None, "built": None, "description": "A plan, drawn and annotated."},
                    actions={"study": {"script": "works_study", "doc": "Read the plan: what it makes, each stage's work, materials and hands"},
                             "build": {"script": "works_build", "doc": "Start the works here from this plan", "duration": 5}})
    s.define_schema("project", extends="thing",
                    doc="Works under way: they hold the plan, the materials and the pay, and go on while the crew is on hand.",
                    state={"portable": False, "holds": ["any"], "stage": 0, "labour": 0, "crew": {}, "hands": [],
                           "settling_until": None},
                    actions={"survey": {"script": "works_survey", "doc": "See what is done, what comes next and what is stopping it"},
                             "supply": {"script": "works_supply", "doc": "Hand a material (or the plan, or pay) into the works",
                                        "params": {"item": "id or name of a thing you hold"}},
                             "work": {"script": "works_work", "doc": "Work an hour on the works, in a role", "duration": 3600,
                                      "params": {"role": "the role you work in (mason, hand...); survey lists them"}},
                             "assign": {"script": "works_assign", "doc": "Put one of your side's people to work in a role, or take someone off (role none)",
                                        "params": {"who": "a name", "role": "a role, or none"}},
                             "hire": {"script": "works_hire", "doc": "Hire someone looking for work, paid from the works each day",
                                      "params": {"who": "a name", "role": "a role"}},
                             "undo": {"script": "works_undo", "doc": "Pull down a stage that is still settling (loud, and guards make it harder)",
                                      "duration": 60}},
                    behaviors=[{"script": "works_tick", "every": 600}])
