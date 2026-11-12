"""Vehicles: things people ride that take time on the road, where others can see them pass, stop them, board them
or strike them.

A world names it in its manifest (`"requires": ["vehicles"]`); the pack defines the `vehicle` and `wheel` schemas
and their verbs, so a world binds nothing on its people.

A vehicle is a place that stands inside another place: those around it see it in their place like any thing (its
card, its state) and act on it; those aboard stand inside it, and what they say and do stays in it unless it is loud.
Its riders and its cargo are its children, so they go wherever it goes. Nobody walks into it through an exit: `board`
it from alongside, `alight` into the place it is in.

A trip has a middle. `drive` (or a timetable) sets it out along its road one leg at a time. Halfway through a leg it
rolls into the next place, so the people there see it come through and can act on it; at the end of the leg it is at
that place, and at the last place it pulls in. Anyone alongside may `board` it as it rolls (unless
`boardable_moving` is False), anyone aboard may `alight` into the road it is on, anyone alongside may `halt` it, and a
thing with `blocks_road` in a place it rolls into stops it there. Each step is an event on the vehicle (reach 1), so
those aboard and those in the place it is in both hear it, and a scene for the narrator goes with each.

A vehicle's state (all optional but `stops`):

- `stops`: the places (names or ids) it serves, in order along its road. `route`: the road itself, every place it
  passes in order, stops included; without one the road is the stops. `direct: True` drives straight to the place
  named, one leg, whatever lies between. `loop: True`: the road goes on from its last place to its first.
  `offroad: True` lets it also be driven to any place connected (connects_to) to where it stands.
- `leg_time`: world seconds a leg (default 300). `legs`: {"<place>|<place>": seconds} for legs that differ, either
  way round.
- `seats`: how many may ride (riders are creatures). `cargo`: the bulk aboard (portable things, by ctx.bulk) it
  drives with; over it, `drive` refuses. `loud: True`: its events carry `loud` (a sleeper there wakes).
- `driver`: the name or id of the body that drives its runs. With one, a run goes only while that body is aboard,
  awake, on its feet and nobody's seat (an embodied driver drives by hand); a driver who is gone or falls halts it
  where it is. Without one the vehicle runs itself.
- `timetable`: {"every": seconds, "offset": seconds} (departures at offset + k * every) or {"at": [seconds into the
  day], "day": seconds} (the day defaults to the root's `day_seconds`, else 86400). Standing at a stop when one is
  due, it sets out for the next stop: back and forth along the stops (`heading` turns at either end), or round them
  with `loop`. `next_departure` says when; at a stop it stands at least `dwell` seconds (default 60) before it sets out
  again, so one that pulled in late does not turn straight round.
- `dispatch`: {"to": a place} (or the place's name): a world rule patches it and the vehicle sets out at its next
  tick, as a run. `hold`: True or a reason: it does not set out, and a trip under way stops where it is.
- `scenes`: {"depart", "pass", "approach", "arrive", "stop", "break"} reword the scenes ({vehicle}, {place}, {to},
  {driver}, {why} are filled in); False silences one.
- Costs, each off until a world sets it: `fuel_per_leg` with `fuel`, `fuel_kind` (the name or kind of what it runs
  on), `fuel_per_unit` (default 1), `fuel_max`: a leg it cannot pay for stops it, and `refuel` feeds it.
  `breakdown`: the chance a leg breaks it (it stops halfway, `broken`). `hull` (and `hull_max`, `armour`): `strike`
  takes 1d6 + body less armour off it, and at 0 it is broken. `repair` mends a broken one in `repair_time`.
  `halt_dc`: someone alongside must make d20 + body against it to halt it.
- `resume_wait`: seconds before a run that was stopped (halted, blocked, held, its driver down) sets out again for
  where it was going, once nothing stops it (default 120).

Written by play: `moving`, `trip` {path, i, to, by, origin, run, half, t0, t1, eta}, `driving`, `stopped` (why it last
stopped short), `resume_to`, `arrived_t`, `broken`, `fuel`, `hull`, `heading`, `next_departure`, and `fault` (secret: the leg under way breaks it).

Verbs, done to the vehicle: `board`, `alight`, `drive` (params to; aboard; also on a `wheel` standing in it),
`halt` (alongside, or the one driving), `repair`, `strike`, `refuel` (params item, count). Each refusal says what to
do instead. A world's rule wraps any of them with a `before_act` listener (a crawler that never goes onto the glass),
and its own scripts read the state above.

Events, on the vehicle (reach 1, `loud` when the vehicle is): `departed` {by, origin, to, path, eta, run}, `passing`
{place, to}, `approaching` {place}, `pulled_in` {place, origin, by, run}, `stopped` {place, why, by, to},
`broke_down` {place, why}, `boarded` and `alighted` {who, moving} (alighting adds the place), `halt_failed`,
`repairing`, `repaired`, `struck` {by, damage, hull}, `refuelled`; and the scene that goes with each step. Boarding
and alighting also emit `arrived` {who, place}, as a walk does, so a world's rules see people come and go.

A vehicle that is a place with `holds` keeps what is aboard within reach of those alongside, as a rack does: an open
cart's riders can be struck from the road and its load taken. A covered one (no `holds`) keeps them out of reach.
"""

PACK = {"name": "vehicles", "description": "Vehicles people ride: they take time on the road, pass through places where they can be seen, stopped, boarded or struck, and run on a timetable with or without a driver."}


def define(s):
    """The two schemas. Idempotent."""
    acts = {"board": {"script": "vehicle_board", "doc": "Climb aboard", "duration": 3},
            "alight": {"script": "vehicle_alight", "doc": "Climb down into the place it is in", "duration": 3},
            "drive": {"script": "vehicle_drive", "doc": "Drive it to a place on its road (from aboard)",
                      "params": {"to": "the place to drive to; the refusal lists them"}},
            "halt": {"script": "vehicle_halt", "doc": "Stop it where it is: step into its road, or pull up if you drive it"},
            "repair": {"script": "vehicle_repair", "doc": "Mend it where it broke down", "duration": 1800},
            "strike": {"script": "vehicle_strike", "doc": "Strike it, to break it", "duration": 6},
            "refuel": {"script": "vehicle_refuel", "doc": "Feed it what it runs on",
                       "params": {"item": "what you feed it", "count": "how many of a stack"}}}
    s.define_schema("vehicle", extends="place",
                    doc="A vehicle: a place people ride in, seen from outside as a thing. Board it, drive it, stop it.",
                    state={"portable": False, "moving": False, "secret": ["fault"],
                           "description": "A vehicle. Board it to ride."},
                    actions=acts,
                    behaviors=[{"script": "vehicle_tick", "every": 15, "always": True}])
    s.define_schema("wheel", extends="thing",
                    doc="The wheel (or the reins) of the vehicle it stands in: drive it from here.",
                    state={"portable": False, "description": "A wheel."},
                    actions={"drive": acts["drive"]})
