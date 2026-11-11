"""Locks: a lock is a thing attached to what it keeps shut, and the thing does not open without it.

A world names it in its manifest (`"requires": ["locks"]`, beside village); the pack defines the `lock` schema and its
verbs, so a world binds nothing on its people. Spawn a lock inside what it locks:

- a box, a chest, a rack (a thing whose state has `holds`): while the lock is locked, nothing in it is within reach of
  anyone (take, read, burn, any verb: the engine refuses, with the way to open it), `put` refuses, and its card shows
  `locked` and the lock, never what is inside.
- a door (the `via` of a connects_to edge): village `go` through it refuses while it is locked. Leave the door's own
  `open: True`; the lock is what shuts it.
- a place: village `go` into it refuses while it is locked (the way in is shut; the way out is a bolt turned from
  inside). Exits to it show `locked`.

A lock's state: `locked` (default True), `key` (the name or id of the thing that fits it; it can be stolen, given or
lost, and nobody copies it), `code` (a string, secret: never on a card), `pick_dc` (absent: it cannot be picked),
`break_dc` (absent: it will not break), `broken` (written by play). A lock with neither a key nor a code is a bolt:
anyone in reach turns it. The lock is `attached`: it is in reach wherever what it locks is (from both sides of a door,
from outside a place), and it never comes away (`portable: False`).

Verbs, done to the lock:
- `unlock`, `lock`: with its key in your hand, or `params {"code": ...}`. A wrong code is refused before anything
  happens and spends nothing. A broken lock never locks again.
- `pick` (ten world minutes): d20 + wits + the better of stealth or craft (skills), against `pick_dc`, rolled when the
  time is out and only if you are still there. Quiet while it works; a fail is heard (`pick_failed` and a scene).
- `break` (two world minutes): d20 + body against `break_dc`, loud from the first blow (heard two levels up). It
  leaves the lock open and broken for good.

Events, on what the lock keeps shut (the box, the door, the place), reach 1 unless said: `unlocked`, `locked`,
`lock_picked`, `pick_failed`, `lock_broken` and `break_failed` (reach 2), each with `by`, `lock` and `holder`, so rules
and minds can react: guards come running. Scripts ask `ctx.locked(x)` for what keeps x shut, or None.
"""

PACK = {"name": "locks", "description": "Locks on boxes, doors and places: a key, a code, picking or force, and nothing opens without them."}


def define(s):
    """The lock schema. Idempotent."""
    s.define_schema("lock", extends="thing",
                    doc="A lock attached to a box, a door or a place: nothing opens without it.",
                    state={"portable": False, "attached": True, "locked": True, "key": None, "code": None,
                           "pick_dc": None, "break_dc": None, "broken": False, "picking": None,
                           "secret": ["code", "picking"], "description": "A lock."},
                    actions={"unlock": {"script": "locks_unlock", "doc": "Unlock it, with its key in hand or its code",
                                        "duration": 2, "params": {"code": "the code, if it takes one"}},
                             "lock": {"script": "locks_lock", "doc": "Lock it, with its key in hand or its code",
                                      "duration": 2, "params": {"code": "the code, if it takes one"}},
                             "pick": {"script": "locks_pick", "doc": "Pick it: ten minutes, quiet unless you fail",
                                      "duration": 600},
                             "break": {"script": "locks_break", "doc": "Break it open by force: loud, and it never locks again",
                                       "duration": 120}})
