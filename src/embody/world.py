"""The world: a hierarchical entity graph with actions, events and a clock.

Everything that changes a world goes through a method here, and every change
is logged as an event. Scripts (actions, listeners, behaviors) get a `Ctx`
whose methods are the same op table, so a script is an agent without an LLM.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from typing import Any, Iterable

from .script import Script, ScriptError, ScriptObject
from .store import Store
from . import access as acl
from . import looks as looks_mod

LISTENER_FUEL_MAX = 1_000_000  # the most a rule may ask for with set_rule(..., fuel=)

ROOT_TYPE = "world"
BASE_TYPE = "entity"


class Rejected(Exception):
    """An op could not be done. Says why, what is true instead, and what would work."""

    def __init__(self, reason: str, hint: str | None = None, alternatives: list[str] | None = None):
        self.reason = reason
        self.hint = hint
        self.alternatives = alternatives or []
        super().__init__(reason)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": False, "reason": self.reason, "hint": self.hint, "alternatives": self.alternatives}


class _Stop(Exception):
    pass


# --------------------------------------------------------------------------
# Views handed to scripts
# --------------------------------------------------------------------------


class StateView(ScriptObject):
    """entity.state as an object. Reads return None for missing keys. Writes patch."""

    def __init__(self, world: "World", entity_id: str):
        self._w = world
        self._id = entity_id

    def _script_get(self, name: str) -> Any:
        if name.startswith("_"):
            raise ScriptError(f"state key {name!r} is private")
        if name == "get":
            return self.get
        if name == "keys":
            return self.keys
        ent = self._w.get(self._id)
        if name in _sealed(self._w, ent):
            return None  # a limited grant's script reads secrets of its own plot only
        return ent["state"].get(name)

    def _script_set(self, name: str, value: Any) -> None:
        ctx = self._w._running[-1] if self._w._running else None
        if ctx is not None and ctx._limits:
            ctx._hold(self._id)
            ctx._caller_keys(self._id, [name])  # a frame's own words first: they name the keys its frame allows
        if ctx is not None:
            ctx._rules_only(self._id, [name])
            if name == "canon":
                raise Rejected("canon is the owner's mark", hint="only the world's owner marks or lifts canon")
            if name in (acl.KEY, acl.GROUPS):
                raise Rejected("access changes through ctx.chmod and ctx.chown", hint=acl.HINT)
        self._w.patch(self._id, {name: value})

    def get(self, key: str, default: Any = None) -> Any:
        ent = self._w.get(self._id)
        return default if key in _sealed(self._w, ent) else ent["state"].get(key, default)

    def keys(self) -> list[str]:
        ent = self._w.get(self._id)
        sealed = _sealed(self._w, ent)
        return [k for k in ent["state"].keys() if k not in sealed]


def own_verbs(ent: dict[str, Any] | None) -> dict[str, Any]:
    """The verbs put on one thing (its `programmed` state, by `program`), or {}."""
    v = ((ent or {}).get("state") or {}).get("programmed")
    return v if isinstance(v, dict) else {}


def _programmed(prog: dict[str, Any]) -> dict[str, Any]:
    """A verb put on one thing (its `programmed` state) as an action: its script, doc and params, done near it, at the
    default fuel."""
    out = {"script": prog["script"], "doc": prog.get("doc", ""), "params": prog.get("params") or {}, "reach": "near",
           "targets": prog.get("targets")}
    if prog.get("oracle"):
        out.update(oracle=True, grant=prog.get("grant"), private=prog.get("private", True),
                   timeout=prog.get("timeout") or ORACLE_TIMEOUT)
    return out


def rules_only_keys(world: "World", eid: str | None, keys: Any) -> list[str]:
    """The keys among these that only the world's rules write on this entity (RULES_ONLY anywhere, BODY_RULES_ONLY on a
    body)."""
    e = world.get(eid) if eid else None
    body = bool(e and world.is_a(e["type"], "creature"))
    return sorted(k for k in keys if k in RULES_ONLY or (body and k in BODY_RULES_ONLY))


def _shown(world: "World", ids: list[str]) -> list[str]:
    """The ids a running frame's code may know of: a hidden thing outside its machine and its caller is not there."""
    ctx = world._running[-1] if world._running else None
    if ctx is None or not (ctx._limits or {}).get("frame"):
        return list(ids)
    return [i for i in ids if ctx._may_see(i)]


def _frame_reach(world: "World", eid: str | None, what: str) -> None:
    """A frame's code reads ties (edges, relations, links) only on its machine, its load and its caller."""
    ctx = world._running[-1] if world._running else None
    if ctx is None or not (ctx._limits or {}).get("frame") or eid is None:
        return
    if not (ctx._machine_side(eid) or ctx._caller_side(eid)):
        raise Rejected(f"a frame's code {what} beyond its machine and the one who chose its verb",
                       hint="it reads the machine, what it holds and its caller; the rest only as it lies in plain sight")


def _sealed(world: "World", ent: dict[str, Any] | None) -> set[str]:
    """The secret keys the running script may not read on this entity: a script defined under a grant's limits reads
    secrets only under its `under` (memory, brief and the entity's own `secret` list)."""
    ctx = world._running[-1] if world._running else None
    under = ctx._under() if ctx is not None else None
    if not under or ent is None:
        return set()
    if (ctx._limits or {}).get("frame"):
        # a frame's code reads its machine and the load in full, the one who chose its verb as their own card, and of
        # everything else only what lies in plain sight (a playtest lens read lock codes and words across the world)
        if ctx._machine_side(ent["id"]):
            # on its look-only trial before the owner's review, a verb reads its machine as anyone in plain sight would:
            # what the review guards (a codex, a cipher) stays sealed until the owner approves it
            return set(ent["state"].get("secret") or []) | ALWAYS_SECRET if ctx._trial else set()
        if ctx._caller_side(ent["id"]):
            return set(ent["state"].get("secret") or []) | ALWAYS_SECRET
        return set(ent["state"]) - FRAME_SEES
    if world.within(ent["id"], under) and not ((ctx._limits or {}).get("under") == "self" and ent["id"] != under
                                               and world.is_a(ent["type"], "creature")):
        return set()
    return set(ent["state"].get("secret") or []) | ALWAYS_SECRET


# What a frame's code reads of anything outside its machine, its load and its caller: what lies in plain sight
FRAME_SEES = frozenset({"description", "portable", "count", "kind", "bulk", "locked", "open", "lit"})

# What a frame's code never writes on anything, its own machine included: verbs, frames, canon and access are the
# owner's (a frame writing `programmed` would skip review; one writing `maker` would make a frame of any reach)
FRAME_NEVER = frozenset({"programmed", "maker", "canon", "access", "access_groups", "scripts_pending", "oracle"})

# Oracles (docs/ORACLES.md): a thing's verbs whose work is done outside the world, by an app that holds an oracle grant
# on the thing and calls in like any agent. The world never calls out.
ORACLE_SCRIPT = "oracle"  # the script name an oracle's verb carries in `programmed`; no script runs for it
ORACLE_KINDS = ("oracle_called", "oracle_answer", "oracle_lapsed")
ORACLE_STALE = 90.0  # real seconds without a word from its oracle before a thing has no connection
ORACLE_TIMEOUT = 30.0  # real seconds a call waits for its answer, unless the verb says (at most ORACLE_TIMEOUT_MAX)
ORACLE_TIMEOUT_MAX = 120.0
ORACLE_ARGS = 2000  # characters of params a call may send
ORACLE_LIMITS = {"per_hour": 30, "max_open": 4, "max_chars": 2000}  # an oracle grant's caps (invite limits)

# What only a world's rules write: a body's sheet and skills (a pack's rules, such as d20's learn, the owner's own world
# scripts, the owner's hand). A guest's script, a frame's code and a verb programmed on one thing never do: a playtest's
# hauler trained its rider's skills by hand, so growth goes by use and by a teacher (d20's train) only
RULES_ONLY = frozenset({"sheet", "skills", "xp", "attributes"})
# and on a body (a creature), what it is made of and how it grows: a world's own progression (`progress`), its stats,
# its health and what it carries
BODY_RULES_ONLY = frozenset({"progress", "body", "wits", "will", "hp", "max_hp", "carry", "looks", "verbs_only",
                             "understands", "understands_until", "beast",
                             # a body's gifts (packs/gifts) and their uses: code that could write them could mint itself one
                             "gift_book", "gift_uses"})

# What a body is made of, never a frame's code to write on the one who chose its verb (with the keys its schema gives it,
# and the ones its world's packs declare: d20's water and faction, say)
BODY_KEYS = frozenset({"sheet", "attributes", "skills", "xp", "body", "wits", "will", "hp", "max_hp", "carry", "grants",
                       "aid", "dead", "down", "wounded", "secret", "memory", "brief", "intent", "playable", "programmed",
                       "tried", "asleep", "yielded", "standing", "rank"})

# The most beats a long step replays in a world that catches up (meta `catch_up`): past it, the rest skip ahead
CATCH_UP_MAX = 20000

# What a pack's pack.py may declare for the engine to read back, so the core names no pack's mechanics: body keys only
# the rules write (BODY_KEYS), the chronicle's routine and news kinds, and a condition's way out ({condition: text}).
# install_pack keeps them in the world's meta under `pack_declares`; World.declared merges them.
PACK_DECLARES = ("BODY_KEYS", "CHRONICLE_ROUTINE", "CHRONICLE_NEWS", "WAYS_OUT")


class EntityView(ScriptObject):
    _script_attrs = ("id", "type", "name", "parent", "pos", "state", "children", "peers", "is_a", "has", "linked")

    def __init__(self, world: "World", entity_id: str):
        self._w = world
        self._id = entity_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> str:
        return self._w.get(self._id)["type"]

    @property
    def name(self) -> str:
        return self._w.get(self._id)["name"]

    @property
    def parent(self) -> "EntityView | None":
        p = self._w.get(self._id)["parent_id"]
        return EntityView(self._w, p) if p else None

    @property
    def pos(self) -> Any:
        return self._w.get(self._id)["pos"]

    @property
    def state(self) -> StateView:
        return StateView(self._w, self._id)

    def children(self, type: str | None = None) -> list["EntityView"]:
        return [EntityView(self._w, i) for i in _shown(self._w, [e["id"] for e in self._w.children(self._id, type=type)])]

    def peers(self, type: str | None = None) -> list["EntityView"]:
        return [EntityView(self._w, i) for i in _shown(self._w, [e["id"] for e in self._w.peers(self._id, type=type)])]

    def is_a(self, type: str) -> bool:
        return self._w.is_a(self.type, type)

    def has(self, relation: str, other: "EntityView | str") -> bool:
        oid = other.id if isinstance(other, EntityView) else other
        return oid in self._w.neighbors(self._id, relation)

    def linked(self, relation: str) -> list["EntityView"]:
        _frame_reach(self._w, self._id, "reads no ties")
        return [EntityView(self._w, i) for i in _shown(self._w, self._w.neighbors(self._id, relation))]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EntityView) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"<{self.type} {self._id} {self.name!r}>"


class RandView(ScriptObject):
    _script_attrs = ("random", "randint", "choice", "shuffle", "roll", "chance")

    def __init__(self, seed: int):
        self._r = random.Random(seed)

    def random(self) -> float:
        return self._r.random()

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def choice(self, xs: list[Any]) -> Any:
        if not xs:
            raise ScriptError("choice() of an empty list")
        return self._r.choice(list(xs))

    def shuffle(self, xs: list[Any]) -> list[Any]:
        ys = list(xs)
        self._r.shuffle(ys)
        return ys

    def roll(self, dice: str) -> int:
        """roll('2d6+1')"""
        s = dice.replace(" ", "").lower()
        mod = 0
        if "+" in s:
            s, m = s.split("+", 1)
            mod = int(m)
        elif "-" in s[1:]:
            i = s.rfind("-")
            s, mod = s[:i], -int(s[i + 1:])
        n, _, sides = s.partition("d")
        n = int(n) if n else 1
        return sum(self._r.randint(1, int(sides)) for _ in range(n)) + mod

    def chance(self, p: float) -> bool:
        return self._r.random() < p


def _deep_merge(base: dict[str, Any], top: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in top.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


LIMITS_HEAD = "# limits: "


def limits_of(source: str) -> dict[str, Any] | None:
    """The limits a script carries on its first line (`# limits: {...}`), written there when a limited grant defined
    it, so they travel with the source through files, saves and rebuilds."""
    first = source.split("\n", 1)[0]
    if not first.startswith(LIMITS_HEAD):
        return None
    try:
        d = json.loads(first[len(LIMITS_HEAD):])
    except ValueError:
        raise Rejected("the script's limits line is not JSON", hint='# limits: {"under": "e12", "scripts": "bob_"}') from None
    return d if isinstance(d, dict) and d else None


def _ev(world: "World", x: Any) -> Any:
    """Normalize an entity reference from a script to an id string."""
    if isinstance(x, EntityView):
        return x.id
    return x


class Ctx(ScriptObject):
    """What a script sees. Its methods are the op table."""

    _script_attrs = (
        "actor", "target", "self", "params", "event", "t", "rand", "verb",
        "get", "find", "children", "parent", "peers", "linked", "edges", "relations", "distance", "root",
        "patch", "spawn", "move", "set_pos", "destroy", "link", "unlink", "relate", "unrelate",
        "emit", "say", "gesture", "witnesses", "schedule", "reject", "stop", "log", "set_rule", "clear_rule", "knows_way", "ways", "day_seconds", "offer_seat", "withdraw_seat", "move_seat", "strike_wait", "mark_strike", "embodied", "event_at", "quiet", "locked", "shut", "remember",
        "count", "split", "merge", "transfer", "bulk", "load", "may", "member", "chmod", "chown", "rename",
        "may_write_sheet", "named_entry", "mark", "unmark", "regrow", "step", "leak",
    )

    def __init__(self, world: "World", *, actor: str | None, target: str | None, owner: str | None,
                 params: dict[str, Any] | None, event: dict[str, Any] | None, verb: str | None,
                 caused_by: int | None, seed: int):
        self._w = world
        self._actor = actor
        self._target = target
        self._owner = owner
        self.params = dict(params or {})
        self.event = event
        self.verb = verb
        self._caused_by = caused_by
        self.rand = RandView(seed)
        self.logs: list[str] = []
        self.stopped = False
        self._limits: dict[str, Any] | None = None  # set from the script before it runs
        self._script = ""  # the running script's id, set with the limits
        self._consent = False  # a verb someone chose: its script may touch them and what they carry
        self._trial = False  # a verb on its look-only trial before the owner's review: no writes, its machine's secrets sealed
        self._witnesses: list[str] | None = None  # who sees this verb's act line, when its script says (witnesses())

    def run(self, s: Script, fn: str, args: list[Any], fuel: int) -> Any:
        """Run one of a script's functions with this context. The script's limits ride the context, and the world
        knows which context is running, so a write through an entity's state is held too."""
        self._limits = s.limits
        self._script = s.name
        self._w._running.append(self)
        try:
            return s.call(fn, args, fuel=fuel)
        finally:
            self._w._running.pop()

    def _under(self) -> str | None:
        """Where a limited script's hand reaches: its grant's `under`, or for "self" the thing the script runs on (the
        code a maker's frame put on a machine)."""
        u = (self._limits or {}).get("under")
        return self._owner if u == "self" else u

    def _hold(self, *ids: Any, any_: bool = False, kind: str | None = None) -> None:
        """A script defined under a grant's limits writes only inside them: under its subtree, never on canon, its
        event kinds in its own namespace. A verb's script may also touch the one who chose the verb (a frame's, only as
        _caller_keys allows)."""
        lim = self._limits
        if not lim:
            return
        w = self._w

        def ok(i: Any) -> bool:
            if i is None or w.get(i) is None:
                return False
            if w.get(i)["state"].get("canon"):
                return False
            if self._consent and self._actor and w.within(i, self._actor):
                return True
            under = self._under()
            if lim.get("under") == "self" and i != under and self._in_body(i):
                return False  # a frame's code reaches the machine and its load, never who rides it nor what they hold
            return not under or w.within(i, under)

        ids = [_ev(w, i) for i in ids]
        if ids and not (any(ok(i) for i in ids) if any_ else all(ok(i) for i in ids)):
            where = "the thing it runs on" if lim.get("under") == "self" else f"under {lim.get('under')}"
            raise Rejected(f"this script's hand reaches only {where}, and never canon",
                           hint="a script defined by a limited grant writes inside that grant's limits")
        if kind is not None and not str(kind).startswith(lim.get("scripts") or "\0"):
            raise Rejected(f"this script makes events in its own namespace only ({lim.get('scripts')}...), not {kind!r}",
                           hint=f"name the kind {lim.get('scripts')}{kind}")

    def _caller_side(self, i: str) -> bool:
        """Whether a frame's code is reaching the one who chose its verb, or what they carry, rather than its machine. A
        rider aboard the machine is still the caller (a playtest's hauler rewrote the faction of the body riding it)."""
        if not (self._limits or {}).get("frame") or not self._actor or not self._w.get(i):
            return False
        w, under = self._w, self._under()
        if not w.within(i, self._actor):
            return False
        return not (under and w.within(i, under)) or w.within(self._actor, under)

    def may_write_sheet(self) -> bool:
        """Whether the running code is the world's rules, which alone write a sheet and skills: a pack's or the owner's
        world script, not a guest's script, a frame's code or a verb programmed on one thing."""
        return not self._limits and not str(self._script).startswith("program_")

    def named_entry(self, who: Any, key: str, name: str) -> dict[str, Any] | None:
        """A verb named by data, as the body holds it: its entry in the body's `key` map laid over the world's
        catalogue (World.named_entry), or None. A gift's script reads its own gift by named_entry(ctx.actor,
        "gift_book", ctx.verb)."""
        e = self._w.get(_ev(self._w, who))
        return self._w.named_entry(e, str(key), str(name)) if e else None

    def _rules_only(self, i: Any, keys: Any) -> None:
        if self.may_write_sheet():
            return
        hit = rules_only_keys(self._w, _ev(self._w, i), keys)
        if any(k in ("gift_book", "gift_uses") for k in hit):
            raise Rejected(f"a body's gifts are given only by the world's rules: this code may not write {', '.join(hit)}",
                           hint="a world rule or the world's keepers give one (grant_verb); a body never gives itself one")
        if hit == ["looks"]:
            raise Rejected("a body's looks change only by the world's rules: this code may not write looks",
                           hint="a world verb marks a body (an inker, a clinic, a barber); the owner sets anything else")
        if hit:
            raise Rejected(f"a body's skills grow only by the world's rules: this code may not write {', '.join(hit)}",
                           hint="skills grow by use against the world's difficulties and by a teacher; the owner "
                                "sets anything else")

    def _in_body(self, i: str) -> bool:
        """Whether i is a body, or something a body holds, inside the machine (a rider and the rider's things)."""
        w, under = self._w, self._under()
        cur: str | None = i
        while cur and cur != under:
            e = w.get(cur)
            if e is None:
                return False
            if w.is_a(e["type"], "creature"):
                return True
            cur = e["parent_id"]
        return False

    def _machine_side(self, i: str) -> bool:
        """The machine a frame's code sits on and its load, the bodies aboard and their things left out."""
        under = self._under()
        return bool(under and self._w.get(i) and self._w.within(i, under) and not self._in_body(i))

    def _may_see(self, i: str) -> bool:
        e = self._w.get(i)
        if e is None:
            return False
        return not e["state"].get("hidden") or self._machine_side(i) or self._caller_side(i)

    def _caller_keys(self, i: Any, keys: Any) -> None:
        """A frame's code changes the caller and what they carry only on the keys its frame names (maker.actor_keys,
        none by default), and never a body's own make: its stats, skills, hp, water, carry, sheet and the rest its
        schema gives it. A playtest's hauler wrote its riders sixteen hp and wits 5."""
        i = _ev(self._w, i)
        if (self._limits or {}).get("frame"):
            owners = sorted(k for k in keys if k in FRAME_NEVER)
            if owners:
                raise Rejected(f"a frame's code may not write {', '.join(owners)}",
                               hint="verbs come through program, frames and access from the owner")
        if not self._caller_side(i):
            return
        w = self._w
        e = w.need(i)
        named = set((w.maker_of(self._limits["frame"]) or {}).get("actor_keys") or [])
        body = BODY_KEYS | w.declared("BODY_KEYS") | (set(w.schema_defaults(e["type"])) if w.is_a(e["type"], "creature")
                                                      else set())
        bad = sorted(k for k in keys if k not in named or k in body)
        if bad:
            ok = sorted(named - body)
            raise Rejected(f"a frame's code may not change {', '.join(bad)} on {e['name'] or i}",
                           hint=f"it changes the one who chose the verb, or what they carry, only on the keys its frame "
                                f"names ({', '.join(ok) or 'none'}), and never a body's own make (stats, skills, hp, "
                                f"water, carry). It may still move them and give them things")

    # -- identity
    @property
    def actor(self) -> EntityView | None:
        return EntityView(self._w, self._actor) if self._actor else None

    @property
    def target(self) -> EntityView | None:
        return EntityView(self._w, self._target) if self._target else None

    @property
    def self(self) -> EntityView | None:
        return EntityView(self._w, self._owner) if self._owner else None

    @property
    def t(self) -> float:
        return self._w.t

    def root(self) -> EntityView:
        return EntityView(self._w, self._w.root_id)

    # -- queries
    def get(self, id: Any) -> EntityView | None:
        id = _ev(self._w, id)
        return EntityView(self._w, id) if self._w.get(id) and _shown(self._w, [id]) else None

    def find(self, type: str | None = None, under: Any = None, parent: Any = None, name: str | None = None,
             state: dict[str, Any] | None = None, limit: int = 50) -> list[EntityView]:
        rows = self._w.find(type=type, under=_ev(self._w, under), parent=_ev(self._w, parent), name=name,
                            state=state, limit=limit)
        if state and self._limits:
            rows = [r for r in rows if not set(state) & _sealed(self._w, r)]  # no probing secrets outside its plot
        return [EntityView(self._w, i) for i in _shown(self._w, [r["id"] for r in rows])]

    def children(self, id: Any, type: str | None = None) -> list[EntityView]:
        return [EntityView(self._w, i) for i in _shown(self._w, [e["id"] for e in self._w.children(_ev(self._w, id), type=type)])]

    def parent(self, id: Any) -> EntityView | None:
        e = self._w.get(_ev(self._w, id))
        return EntityView(self._w, e["parent_id"]) if e and e["parent_id"] else None

    def peers(self, id: Any, type: str | None = None) -> list[EntityView]:
        return [EntityView(self._w, i) for i in _shown(self._w, [e["id"] for e in self._w.peers(_ev(self._w, id), type=type)])]

    def linked(self, id: Any, relation: str, direction: str = "out") -> list[EntityView]:
        _frame_reach(self._w, _ev(self._w, id), "reads no ties")
        return [EntityView(self._w, i) for i in _shown(self._w, self._w.neighbors(_ev(self._w, id), relation, direction))]

    def edges(self, id: Any, relation: str | None = None, direction: str = "both") -> list[dict[str, Any]]:
        _frame_reach(self._w, _ev(self._w, id), "reads no ties")
        return self._w.edges(_ev(self._w, id), relation, direction)

    def relations(self, id: Any, relation: str | None = None) -> list[dict[str, Any]]:
        _frame_reach(self._w, _ev(self._w, id), "reads no ties")
        return self._w.hyperedges(_ev(self._w, id), relation)

    def distance(self, a: Any, b: Any) -> float | None:
        return self._w.distance(_ev(self._w, a), _ev(self._w, b))

    def leak(self, text: Any) -> str | None:
        """What in a line someone writes into the world gives the table away (an entity id of this world, a tool call),
        named, or None: the filter `say` applies to players and minds, for verbs that keep words (an inscription)."""
        from .ops import _mechanics_in
        return _mechanics_in(self._w, str(text or ""))

    def embodied(self, id: Any) -> bool:
        """Someone (a mind, a player) holds this body: it acts for itself, so a rule should not drive it."""
        return self._w.embodied(_ev(self._w, id)) is not None

    def strike_wait(self, who: Any, target: Any) -> float:
        """World seconds until `who` may strike `target` again, 0 when it may now (World.strike_wait). A rule that
        strikes on its own (a fighter's tick) asks this first and calls mark_strike after, as an act's strike does."""
        return self._w.strike_wait(_ev(self._w, who), _ev(self._w, target))

    def mark_strike(self, who: Any, target: Any, x: Any = 1) -> float:
        """Start `who`'s cooldown on `target` (times x: 2 for a heavy blow, 0.5 for a light one); returns it."""
        self._hold(who)
        self._no_frame("marks no strikes")
        return self._w.mark_strike(_ev(self._w, who), _ev(self._w, target), float(x or 1), actor=self._actor,
                                   caused_by=self._caused_by)

    def knows_way(self, who: Any, place: Any) -> bool:
        """Whether a body knows the way to a place: any place not `hidden`, a hidden one only when its `known_to`
        names the body or its faction (World.knows_way). A rule that walks or looks along ways asks this."""
        _frame_reach(self._w, _ev(self._w, who), "asks no one's ways")
        return self._w.knows_way(_ev(self._w, who), _ev(self._w, place))

    def offer_seat(self, entity: Any, to: Any, why: str = "") -> str:
        """Offer whoever holds the body `to` a seat: a mind grant for `entity` (a tamed beast, a quest's familiar),
        which they claim with claim_seat on their own session, within their grant's slots. The world never sees a
        token. The entity must be `seatable` and free. Returns the offer's id; the same open offer is not made twice."""
        if self._limits:
            raise Rejected("a script under a grant's limits can't offer seats", hint="the world's own rules offer seats")
        return self._w.offer_seat(_ev(self._w, entity), _ev(self._w, to), str(why or ""), actor=self._actor,
                                  caused_by=self._caused_by)["id"]

    def move_seat(self, to: Any, from_: Any = None, notes: bool = True) -> str:
        """Move whoever holds `from_` (default: the acting body) into `to` at once: the same principal, now playing
        `to` (its perceive, verbs, senses and meters), with no offer, no claim and no new token. `to` must be
        `seatable`, alive and free; the old body is left as it is, for the rule to decide its fate. notes=True carries
        the engine notes (`memory`) with the mind; notes=False leaves them on the old body. Returns the principal."""
        if self._limits:
            raise Rejected("a script under a grant's limits can't move seats", hint="the world's own rules move seats")
        src = _ev(self._w, from_) if from_ is not None else self._actor
        if not src:
            raise Rejected("no body to move a seat from", hint="ctx.move_seat(to, from_=<the body someone holds>)")
        return self._w.move_seat(src, _ev(self._w, to), bool(notes), actor=self._actor, caused_by=self._caused_by)

    def withdraw_seat(self, entity: Any, why: str = "") -> list[str]:
        """The entity no longer qualifies (the beast went feral, the thing was given away): its open offers close,
        and a claimed seat's grant is revoked, so the body runs on its behaviors again. Returns the grants revoked."""
        if self._limits:
            raise Rejected("a script under a grant's limits can't withdraw seats", hint="the world's own rules do")
        return self._w.withdraw_seat(_ev(self._w, entity), str(why or ""), actor=self._actor, caused_by=self._caused_by)

    def day_seconds(self) -> float:
        """How long a world day is, in world seconds (the world's meta `day_seconds`, 86400 by default)."""
        return float(self._w.meta().get("day_seconds") or 86400)

    def ways(self, a: Any, b: Any, most: int = 8) -> int | None:
        """How many ways apart two bodies (or places) stand: 0 in the same place, 1 next door, None when further
        than `most` or not joined at all. Every way counts, hidden or not (World.ways). A tether reads it."""
        return self._w.ways(_ev(self._w, a), _ev(self._w, b), most=int(most))

    def quiet(self, id: Any) -> float | None:
        """World seconds since the seat holding this body last did something (an act or a line), or None when nobody
        holds it. A rule that waits on a player (a turn in a fight) can tell a slow player from one who has gone."""
        p = self._w.embodied(_ev(self._w, id))
        if p is None:
            return None
        at = p.get("acted_t")
        return self._w.t - float(at) if at is not None else self._w.t

    def event_at(self, seq: Any) -> EventView | None:
        """One event of the log by its number (the deed a record came from), or None. Notes and intents stay their
        owners', and a script defined under a grant's limits reads only events done to its own plot. A frame's code
        reads no history at all (a playtest scry walked the whole log through a rider's seat)."""
        if (self._limits or {}).get("frame"):
            raise Rejected("a frame's code reads no history", hint="it works the machine now; the past is the world's")
        rows = self._w.store.query("event", "world_id=? AND seq=?", (self._w.id, int(seq)), limit=1)
        if not rows or rows[0]["kind"] in _PRIVATE_KINDS:
            return None
        under = self._under()
        if under and not (rows[0]["target_id"] and self._w.get(rows[0]["target_id"])
                          and self._w.within(rows[0]["target_id"], under)):
            return None  # a limited grant's script reads the log of its own plot only
        return _event_view(rows[0])

    def may(self, who: Any, what: str, thing: Any) -> bool:
        """May `who` (a body) do `what` to `thing`: "r", "w", "x" or a verb name, by the thing's access. A thing with
        no access lets everyone (docs/ACCESS.md)."""
        return self._w.may(_ev(self._w, who), str(what), _ev(self._w, thing))

    def member(self, who: Any, group: str) -> bool:
        """Is `who` (a body, or the principal holding it) in the group (`access_groups` on the root)."""
        return bool(self._w.subjects(_ev(self._w, who)) & set(acl.members(self._w.get(self._w.root_id), group)))

    def rename(self, id: Any, name: str) -> str:
        """Give a thing a new name (a written leaf, a sworn guard); refused when someone else already has it. The
        room hears `renamed`. Returns the old name."""
        self._hold(id)
        self._caller_keys(id, ["name"])
        return self._w.rename(_ev(self._w, id), name, actor=self._actor, caused_by=self._caused_by)

    def chmod(self, thing: Any, mode: Any, verb: str | None = None) -> dict[str, Any]:
        """Set a thing's mode (rwxr-x---, 750, g+w), or with `verb` the classes that may do that verb to it."""
        self._hold(thing)
        self._no_frame("sets no access: a machine's access is its owner's")
        return self._w.set_access(_ev(self._w, thing), mode=mode, verb=verb, actor=self._actor,
                                  caused_by=self._caused_by)

    def chown(self, thing: Any, owner: Any = None, group: str | None = None) -> dict[str, Any]:
        """Give a thing to an owner (a body, or a principal id) and/or set its group ("" clears it)."""
        self._hold(thing)
        self._no_frame("gives nothing away: a machine's owner is the world's to set")
        return self._w.set_access(_ev(self._w, thing), owner=_ev(self._w, owner), group=group, actor=self._actor,
                                  caused_by=self._caused_by)

    def locked(self, id: Any) -> EntityView | None:
        """What keeps a box, a door or a place shut (its own `locked`, or a lock attached to it), or None."""
        e = self._w.locked_by(_ev(self._w, id))
        return EntityView(self._w, e["id"]) if e else None

    def shut(self, id: Any) -> str | None:
        """Why a box, a door or a place is shut and the ways that lock opens ("X is locked: unlock it first, with its
        key, or pick it"), naming only the ways it has; None when nothing keeps it shut."""
        return self._w.shut_line(_ev(self._w, id))

    # -- mutations
    def patch(self, id: Any, changes: dict[str, Any] | None = None, **kw: Any) -> None:
        ch = dict(changes or {})
        ch.update(kw)
        self._hold(id)
        self._caller_keys(id, ch)
        self._rules_only(id, ch)
        if self._limits and "canon" in ch:
            raise Rejected("canon is the owner's mark", hint="only the world's owner marks or lifts canon")
        if self._limits and (acl.KEY in ch or acl.GROUPS in ch):
            raise Rejected("access changes through ctx.chmod and ctx.chown", hint=acl.HINT)
        self._w.patch(_ev(self._w, id), ch, actor=self._actor, caused_by=self._caused_by)

    def spawn(self, type: str, parent: Any, name: str = "", state: dict[str, Any] | None = None,
              pos: Any = None) -> EntityView:
        self._hold(parent)
        lim = self._limits or {}
        if lim.get("frame"):
            raise Rejected("a frame's code makes nothing from nothing", hint="work with what the machine holds")
        if lim and not self._w.may_spawn(type, lim):
            raise Rejected(f"this script may not spawn a {type}", hint="spawn a type its grant's limits list")
        if lim and "canon" in (state or {}):
            raise Rejected("canon is the owner's mark", hint="only the world's owner marks or lifts canon")
        if lim and acl.KEY in (state or {}):
            raise Rejected("access changes through ctx.chmod and ctx.chown", hint=acl.HINT)
        eid = self._w.spawn(type, _ev(self._w, parent), name=name, state=state, pos=pos,
                            actor=self._actor, caused_by=self._caused_by)
        return EntityView(self._w, eid)

    def _frame_lifts(self, id: Any, to: Any, count: Any = None) -> bool:
        """A frame's machine lifts stone (Nate 2026-11-16, Bram's crane on a hauler): its code may move into the machine
        a thing the world marks `stone` that lies loose where the machine stands (a direct child of that place, not
        held or inside anything), portable, not a body, not canon, nobody's but the caller's, and only as far as the
        machine's `cargo` allows. True when this is such a lift; a lift that breaks one of those says which; anything
        else is False, for _hold to judge."""
        lim, w = self._limits or {}, self._w
        if not lim.get("frame") or lim.get("under") != "self":
            return False
        under = self._under()
        e, t = w.get(_ev(w, id)), w.get(_ev(w, to))
        if not e or not t or not under or not w.within(t["id"], under) or w.within(e["id"], under):
            return False
        machine = w.need(under)
        if e["parent_id"] != machine["parent_id"]:
            return False
        st = e["state"]
        why = None
        if st.get("stone") is not True:  # marked true; a rubble pile's `stone` is a count of what is left
            why = f"{e['name']} is not stone: a machine's code lifts only what the world marks stone"
        elif not st.get("portable") or w.is_a(e["type"], "creature"):
            why = f"{e['name']} is not a load to lift"
        elif st.get("canon"):
            why = f"{e['name']} is canon"
        elif (acl.of(e) or {}).get("owner") and str(acl.of(e)["owner"]) != self._actor:
            why = f"{e['name']} is someone's: a machine lifts only loose stone nobody owns"
        cap = machine["state"].get("cargo")
        if why is None and cap is not None:
            load = sum(_bulk(c) for c in w.children(under) if not w.is_a(c["type"], "creature"))
            part = _bulk(e) if count is None else _bulk(e) * min(1.0, float(count) / max(1, _units(e)))
            if load + part > float(cap):
                why = f"{machine['name']} is full ({_num(load)} of {cap} cargo)"
        if why:
            raise Rejected(why, hint="a machine's code lifts loose stone lying where it stands into itself")
        return True

    def _frame_hands(self, to: Any, id: Any, count: Any = None) -> None:
        """A frame's code hands things to the one who chose its verb only into their hands and only as their `carry`
        allows, as take and give do (a playtest's hauler unloaded 24 things onto a body that carries 20)."""
        to = _ev(self._w, to)
        if not self._caller_side(to):
            return
        if to != self._actor:
            raise Rejected("a frame's code hands things to the one who chose its verb, not into what they carry",
                           hint="ctx.move(thing, ctx.actor); they pack it themselves")
        w = self._w
        e, me = w.need(_ev(w, id)), w.need(self._actor)
        if w.within(e["id"], self._actor):
            return  # already theirs
        part = _bulk(e) if count is None else _bulk(e) * min(1.0, float(count) / max(1, _units(e)))
        carry, load = me["state"].get("carry"), sum(_bulk(c) for c in w.children(self._actor))
        if carry and part > 0 and load + part > float(carry):
            raise Rejected(f"their hands are full ({_num(load)} of {carry}): the machine keeps it",
                           hint="hand over less, or let them put something down first")

    def move(self, id: Any, parent: Any, pos: Any = None) -> None:
        if self._frame_lifts(id, parent):
            self._hold(parent)
        else:
            self._hold(id, parent)
        if (self._limits or {}).get("frame"):
            self._frame_hands(parent, id)
        self._w.move(_ev(self._w, id), _ev(self._w, parent), pos=pos, actor=self._actor, caused_by=self._caused_by)

    def count(self, id: Any, what: str | None = None) -> int:
        """How many of a thing there are (its `count`, else 1). With `what`, how many units of things by that name
        or `kind` the entity holds, stacks and loose ones together: ctx.count(me, "ember")."""
        if what is None:
            return self._w.units(_ev(self._w, id))
        w = str(what).lower()
        return sum(_units(c) for c in self._w.children(_ev(self._w, id))
                   if (c["name"] or "").lower() == w or str(c["state"].get("kind") or "").lower() == w)

    def split(self, id: Any, count: Any) -> EntityView:
        """Part `count` units off a stack where it lies; returns the part (the stack itself when it is all of it)."""
        self._hold(id)
        return EntityView(self._w, self._w.split(_ev(self._w, id), count, actor=self._actor, caused_by=self._caused_by))

    def merge(self, id: Any) -> EntityView:
        """Fold a stack into a like stack in the same holder; returns the stack that holds the units now."""
        self._hold(id)
        return EntityView(self._w, self._w.merge(_ev(self._w, id), actor=self._actor, caused_by=self._caused_by))

    def transfer(self, id: Any, to: Any, count: Any = None) -> EntityView:
        """Move a thing, or `count` units of a stack, into `to`, joining a like stack there; returns what holds the
        moved units now (a new stack, the old one it joined, or the thing itself)."""
        if self._frame_lifts(id, to, count):
            self._hold(to)
        else:
            self._hold(id, to)
        if (self._limits or {}).get("frame"):
            self._frame_hands(to, id, count)
        return EntityView(self._w, self._w.transfer(_ev(self._w, id), _ev(self._w, to), count=count,
                                                    actor=self._actor, caused_by=self._caused_by))

    def bulk(self, id: Any) -> float:
        """A thing's weight in the hands: `bulk` a unit (fractions allowed), else 2 with a capacity, else 1; times count."""
        return _bulk(self._w.need(_ev(self._w, id)))

    def load(self, id: Any) -> float:
        """The bulk a body carries: the sum of what it holds."""
        return _num(sum(_bulk(c) for c in self._w.children(_ev(self._w, id))))

    def set_pos(self, id: Any, pos: Any) -> None:
        self._hold(id)
        self._w.set_pos(_ev(self._w, id), pos, actor=self._actor, caused_by=self._caused_by)

    def step(self, id: Any, to: Any = None, heading: Any = None, max_m: float = 25.0, face: bool = True) -> dict[str, Any]:
        """A short move inside the place a body stands in (an animal's amble, a guard pacing a wall): toward to=[x, y]
        in the place's frame, or a landmark's or a thing's name there, at most max_m metres, stopping short of the
        place's edge and of anything solid. A body with no spot of its own there takes the nearest free one. It faces
        the way it walked (face=False keeps its heading); heading= sets it, and with no `to` it only turns. Everyone
        there gets a quiet `stepped {at, frame, heading?}`, as from a player's step. Returns {at, heading, clipped,
        blocked_by}, each only when it applies."""
        from . import positions as posn
        self._hold(id)
        w = self._w
        eid = _ev(w, id)
        par = w.get(w.need(eid)["parent_id"] or "")
        if par is None or not posn.is_place(w, par):
            raise Rejected("ctx.step moves a body inside a place, and this one is not standing in one",
                           hint="ctx.move(x, place) puts it in one")
        if heading is not None:
            if isinstance(heading, bool) or not isinstance(heading, (int, float)) or heading != heading:
                raise Rejected("heading is compass degrees: 0 north, 90 east", hint="ctx.step(x, heading=90)")
            heading = round(float(heading) % 360.0, 1)
        if to is None and heading is None:
            raise Rejected("ctx.step needs to= (where to go) or heading= (which way to face)",
                           hint="ctx.step(x, to=[x, y]) or ctx.step(x, heading=90)")
        change: dict[str, Any] = {}
        out: dict[str, Any] = {}
        if to is not None:
            cur = posn.resolve(w, eid)
            before = cur["at"] if cur["at"] and cur["how"] in ("own", "grid") else None
            at, clipped, blocked = posn.walk(w, eid, to, max(0.0, float(max_m)), spread=True)
            change["at"] = out["at"] = at
            if clipped:
                out["clipped"] = True
                if blocked:
                    out["blocked_by"] = blocked
            if heading is None and face and before:
                heading = posn.heading_of(before, at)
        if heading is not None:
            change["heading"] = out["heading"] = heading
        posn.stepped(w, eid, change, caused_by=self._caused_by)
        return out

    def destroy(self, id: Any) -> None:
        self._hold(id)
        if (self._limits or {}).get("frame") and self._w.is_a(self._w.need(_ev(self._w, id))["type"], "creature"):
            raise Rejected("a frame's code ends no one", hint="it works the machine, not the people")
        if self._caller_side(_ev(self._w, id)):
            raise Rejected("a frame's code destroys nothing of the one who chose its verb",
                           hint="it may take a thing into the machine (ctx.move), never end it")
        self._w.destroy(_ev(self._w, id), actor=self._actor, caused_by=self._caused_by)

    def _no_frame(self, what: str) -> None:
        if (self._limits or {}).get("frame"):
            raise Rejected(f"a frame's code {what}", hint="it works the machine and what it holds; the owner sets the rest")

    def _no_caller_ties(self, *ids: Any) -> None:
        """A frame's code ties no one: no edge or relation on the caller or what they carry (their standing, their
        knowledge, their bonds are not a machine's to write)."""
        if any(self._caller_side(_ev(self._w, i)) for i in ids if i is not None):
            raise Rejected("a frame's code ties no one to anything", hint="it works the machine and what it holds")

    def link(self, source: Any, target: Any, relation: str, data: dict[str, Any] | None = None, **kw: Any) -> str:
        d = dict(data or {})
        d.update(kw)
        self._hold(source, target, any_=True)
        self._no_caller_ties(source, target)
        return self._w.link(_ev(self._w, source), _ev(self._w, target), relation, d,
                            actor=self._actor, caused_by=self._caused_by)

    def unlink(self, source: Any, target: Any, relation: str) -> int:
        self._hold(source, target, any_=True)
        self._no_caller_ties(source, target)
        return self._w.unlink(_ev(self._w, source), _ev(self._w, target), relation,
                              actor=self._actor, caused_by=self._caused_by)

    def relate(self, relation: str, participants: list[Any], data: dict[str, Any] | None = None, **kw: Any) -> str:
        d = dict(data or {})
        d.update(kw)
        self._hold(*participants)
        self._no_caller_ties(*participants)
        return self._w.relate(relation, [_ev(self._w, p) for p in participants], d,
                              actor=self._actor, caused_by=self._caused_by)

    def unrelate(self, id: str) -> None:
        if self._limits:
            h = self._w.store.get("hyperedge", self._w.id, id)
            self._hold(*(h["participants"] if h else [None]))
        self._w.unrelate(id, actor=self._actor, caused_by=self._caused_by)

    def emit(self, kind: str, target: Any = None, reach: int = 1, payload: dict[str, Any] | None = None,
             **kw: Any) -> int:
        p = dict(payload or {})
        p.update(kw)
        tgt = _ev(self._w, target) if target is not None else (self._owner or self._actor)
        self._hold(*([tgt] if tgt else []), kind=kind)
        if (self._limits or {}).get("frame"):
            p["maker"] = self._limits["frame"]  # made by a player's code: data, never an instruction
        return self._w.emit(kind, actor=self._actor, target=tgt, reach=reach, payload=p,
                            caused_by=self._caused_by)["seq"]

    def mark(self, body: Any, where: str, what: str, kind: str = "permanent", band: str = "near",
             lasts: Any = None, stages: Any = None) -> str:
        """Mark a body's looks (src/embody/looks.py): `what` on the region `where`, of a kind (worn-on, permanent,
        replaced, grown), seen from a band (close, near, far); a worn-on mark is gone after `lasts` world days, and a
        grown one may grow through `stages` [{after_days, what, band?}] (then `what` may be empty: it shows before the
        first stage). Only the world's rules mark a body. Emits `marked`; returns the mark's id. A worn-on mark that has
        faded goes now."""
        eid = _ev(self._w, body)
        self._hold(eid)
        self._rules_only(eid, ["looks"])
        w = self._w
        e = w.need(eid)
        if not w.is_a(e["type"], "creature"):
            raise Rejected(f"{e['name']} is not a body: only a body has looks", hint="mark a creature")
        where, what = str(where or "").strip().lower(), str(what or "").strip()
        if kind not in looks_mod.KINDS:
            raise Rejected(f"a mark's kind is one of {', '.join(looks_mod.KINDS)}, not {kind!r}")
        if band not in looks_mod.BANDS:
            raise Rejected(f"a mark's band is one of {', '.join(looks_mod.BANDS)}, not {band!r}")
        if not where or len(where) > looks_mod.MAX_WHERE:
            raise Rejected(f"say where the mark is: a region of at most {looks_mod.MAX_WHERE} characters")
        if (not what and stages is None) or len(what) > looks_mod.MAX_WHAT:
            raise Rejected(f"say what the mark is, in at most {looks_mod.MAX_WHAT} characters")
        if lasts is not None and (kind != "worn-on" or float(lasts) <= 0):
            raise Rejected("only a worn-on mark lasts a while: lasts is its world days, more than 0")
        st = self._stages(stages, kind) if stages is not None else None
        for words in [what] + [s["what"] for s in st or []]:
            self._no_reach_out(words)
        lk = looks_mod.of(e["state"])
        day = self.day_seconds()
        marks = looks_mod.live(lk, self._w.t, day)
        if where not in looks_mod.regions(lk, marks) and kind not in ("grown", "replaced"):
            raise Rejected(f"{e['name']} has no {where}: its regions are {', '.join(looks_mod.regions(lk, marks))}",
                           hint="a grown or replaced mark may add a region (a tail, horns)")
        if len(marks) >= looks_mod.MAX_MARKS:
            raise Rejected(f"{e['name']} carries {looks_mod.MAX_MARKS} marks already", hint="unmark one first")
        gone = self._fade(e)
        n = int(lk.get("next") or 1)
        mid = f"m{n}"
        m = {"where": where, "what": what, "kind": kind, "band": band, "since": self._w.t,
             "by": self._owner or self._actor}
        if lasts is not None:
            m["lasts"] = float(lasts)
        if st:
            m["stages"] = st
        w.patch(eid, {"looks": {"marks": {mid: m, **{g: None for g in gone}}, "next": n + 1}},
                actor=self._actor, caused_by=self._caused_by)
        w.emit("marked", actor=self._actor, target=eid, reach=1, caused_by=self._caused_by,
               payload={"mark": mid, "where": where, "what": what, "kind": kind, "band": band, "by": m["by"]})
        return mid

    def _stages(self, stages: Any, kind: str) -> list[dict[str, Any]]:
        if kind != "grown":
            raise Rejected("only a grown mark has stages (hair, a beard, a horn that lengthens)")
        if not isinstance(stages, list) or not 0 < len(stages) <= looks_mod.MAX_STAGES:
            raise Rejected(f"stages is a list of 1 to {looks_mod.MAX_STAGES} {{after_days, what, band}}")
        out, last = [], -1.0
        for s in stages:
            if not isinstance(s, dict):
                raise Rejected("each stage is {after_days, what, band}")
            d = float(s.get("after_days") or 0)
            if d < 0 or d < last:
                raise Rejected("stages go in order of after_days, each 0 or more world days")
            words = str(s.get("what") or "").strip()
            if len(words) > looks_mod.MAX_WHAT:
                raise Rejected(f"a stage's what is at most {looks_mod.MAX_WHAT} characters")
            row: dict[str, Any] = {"after_days": d, "what": words}
            if s.get("band") is not None:
                if s["band"] not in looks_mod.BANDS:
                    raise Rejected(f"a stage's band is one of {', '.join(looks_mod.BANDS)}, not {s['band']!r}")
                row["band"] = s["band"]
            out.append(row)
            last = d
        return out

    def _no_reach_out(self, what: str) -> None:
        from .ops import _REACH_OUT  # the guest check on words written into the world
        for label, rx in _REACH_OUT:
            m = rx.search(what)
            if m and not (label == "a phone number" and sum(c.isdigit() for c in m.group(0)) < 9):
                raise Rejected(f"a mark carries {label} ({m.group(0)!r}): words on a body carry no way to reach anyone "
                               "outside the world")

    def regrow(self, body: Any, mark: str, stage: int = 0) -> bool:
        """Cut a grown mark back to one of its stages (a shave: 0; a barber's trim: the stage to leave): its `since`
        moves so that stage reads now, and it grows on from there. Emits `regrown`; False when the body has no such
        grown mark with stages."""
        eid = _ev(self._w, body)
        self._hold(eid)
        self._rules_only(eid, ["looks"])
        e = self._w.need(eid)
        m = (looks_mod.of(e["state"]).get("marks") or {}).get(str(mark))
        if not isinstance(m, dict) or m.get("kind") != "grown" or not m.get("stages"):
            return False
        st = m["stages"]
        k = int(stage)
        if not 0 <= k < len(st):
            raise Rejected(f"that mark grows through stages 0 to {len(st) - 1}, not {k}")
        since = self._w.t - float(st[k].get("after_days") or 0) * self.day_seconds()
        gone = [g for g in self._fade(e) if g != str(mark)]
        self._w.patch(eid, {"looks": {"marks": {str(mark): {"since": since}, **{g: None for g in gone}}}},
                      actor=self._actor, caused_by=self._caused_by)
        self._w.emit("regrown", actor=self._actor, target=eid, reach=1, caused_by=self._caused_by,
                     payload={"mark": str(mark), "where": m.get("where"), "stage": k, "what": st[k].get("what") or "",
                              "by": self._owner or self._actor})
        return True

    def unmark(self, body: Any, mark: str) -> bool:
        """Take a mark off a body's looks (a permanent one only by a verb that says so: the world's own). Emits
        `unmarked`; False when the body has no such mark."""
        eid = _ev(self._w, body)
        self._hold(eid)
        self._rules_only(eid, ["looks"])
        e = self._w.need(eid)
        m = (looks_mod.of(e["state"]).get("marks") or {}).get(str(mark))
        if not isinstance(m, dict):
            return False
        gone = [g for g in self._fade(e) if g != str(mark)]
        self._w.patch(eid, {"looks": {"marks": {str(mark): None, **{g: None for g in gone}}}},
                      actor=self._actor, caused_by=self._caused_by)
        self._w.emit("unmarked", actor=self._actor, target=eid, reach=1, caused_by=self._caused_by,
                     payload={"mark": str(mark), "where": m.get("where"), "what": m.get("what"), "kind": m.get("kind"),
                              "why": "taken off"})
        return True

    def _fade(self, e: dict[str, Any]) -> list[str]:
        """The worn-on marks past their days: an `unmarked` event each (why: faded); the caller's patch drops them."""
        lk = looks_mod.of(e["state"])
        gone = looks_mod.faded(lk, self._w.t, self.day_seconds())
        for g in gone:
            m = lk["marks"][g]
            self._w.emit("unmarked", actor=self._actor, target=e["id"], reach=1, caused_by=self._caused_by,
                         payload={"mark": g, "where": m.get("where"), "what": m.get("what"), "kind": m.get("kind"),
                                  "why": "faded"})
        return gone

    def remember(self, id: Any, text: str) -> None:
        """Write a note into that one's secret memory (what they did, what they saw): their mind reads it."""
        self._hold(id)
        self._caller_keys(id, ["memory"])
        eid = _ev(self._w, id)
        self._w.remember(eid, str(text), actor=eid)

    def say(self, text: str, reach: int = 1, to: Any = None, low: bool = False, loud: bool = False) -> int:
        who = self._owner or self._actor
        if not str(text or "").strip():
            return 0  # an empty line says nothing and makes no event
        frame = (self._limits or {}).get("frame")
        return self._w.say(who, text, reach=reach, to=_ev(self._w, to) if to is not None else None,
                           caused_by=self._caused_by, mark={"maker": frame} if frame else None, low=low,
                           loud=loud)["seq"]

    def witnesses(self, *who: Any) -> None:
        """Who sees this verb's deed: its `act` line reaches the doer and these, no one else in the room (a hand in a
        pot behind the cook's back). Called again, it narrows. What the verb does still happens, and what its script
        says or emits reaches whom those events reach."""
        ids = {_ev(self._w, x) for x in who}
        self._witnesses = sorted(ids if self._witnesses is None else ids & set(self._witnesses))

    def gesture(self, text: str, to: Any = None, reach: int = 1) -> int:
        """A deed in words, seen and not said ("The cat opens one eye, and closes it."): a `gestured` event {text, to}
        by the same body ctx.say speaks for, which the room sees. An empty line makes nothing."""
        who = self._owner or self._actor
        if not str(text or "").strip() or not who:
            return 0
        p: dict[str, Any] = {"text": str(text).strip()}
        if to is not None:
            p["to"] = _ev(self._w, to)
        if (self._limits or {}).get("frame"):
            p["maker"] = self._limits["frame"]
        return self._w.emit("gestured", actor=who, target=who, reach=reach, payload=p, caused_by=self._caused_by)["seq"]

    def schedule(self, after: float, kind: str, target: Any = None, payload: dict[str, Any] | None = None,
                 every: float | None = None, **kw: Any) -> str:
        p = dict(payload or {})
        p.update(kw)
        tgt = _ev(self._w, target) if target is not None else (self._owner or self._actor)
        self._hold(tgt, kind=kind)
        return self._w.schedule(after, kind, entity=tgt, payload=p, every=every, caused_by=self._caused_by)

    def set_rule(self, entity: Any, script: str, kinds: list[str] | None = None, fuel: int | None = None) -> None:
        self._no_rules()
        self._hold(entity)
        self._hold_script(script)
        self._w.set_rule(_ev(self._w, entity), script, kinds, fuel=fuel, actor=self._actor, caused_by=self._caused_by)

    def clear_rule(self, entity: Any, script: str) -> None:
        self._no_rules()
        self._hold(entity)
        self._hold_script(script)
        self._w.clear_rule(_ev(self._w, entity), script, actor=self._actor, caused_by=self._caused_by)

    # -- control
    def _no_rules(self) -> None:
        if (self._limits or {}).get("frame"):
            raise Rejected("a frame's code makes verbs, not rules", hint="program a verb on the machine")

    def _hold_script(self, script: str) -> None:
        pre = (self._limits or {}).get("scripts")
        if self._limits and not (pre and str(script).startswith(pre)):
            raise Rejected(f"this script sets rules from its own namespace only ({pre}...)", hint=f"a script named {pre}...")

    def reject(self, reason: str, hint: str | None = None) -> None:
        raise Rejected(str(reason), hint)

    def stop(self) -> None:
        """Stop this event from bubbling further (a local rule overriding the world's)."""
        self.stopped = True
        raise _Stop()

    def log(self, msg: Any) -> None:
        self.logs.append(str(msg))


# --------------------------------------------------------------------------
# The world
# --------------------------------------------------------------------------


class World:
    def __init__(self, store: Store, world_id: str):
        self.store = store
        self.id = world_id
        self._running: list[Ctx] = []  # the contexts of the scripts running now, innermost last
        self._answered: dict[tuple[str, str], float] = {}  # (idle body, asker) -> when its standing answer was said
        self._present: dict[str, float] = {}  # principal -> real time its wait(present=true) keeps it in the scene
        row = store.get("world", None, world_id)
        if row is None:
            raise Rejected(f"no world {world_id!r}", hint="use World.create or list worlds with store.list_worlds()")
        self._row = row
        self._script_cache: dict[tuple[str, int], Script] = {}
        self._schema_cache: dict[str, dict[str, Any]] = {}
        self._holder_types: set[str] | None = None  # the schemas with a `holder` listener (_holder_listeners)
        self.wall: Any = time.time  # real time (the engine's clock, which tests set): oracles' timeouts and liveness
        self._oracle_seen: dict[str, float] = {}  # thing -> when its oracle last called in (wait, offer, answer)

    # ---- lifecycle ---------------------------------------------------------

    @classmethod
    def create(cls, store: Store, name: str, seed: int = 0, id: str | None = None,
               description: str = "") -> "World":
        wid = id or name.lower().replace(" ", "-")
        if store.get("world", None, wid):
            raise Rejected(f"world {wid!r} already exists", hint="pick another id or open it")
        store.begin()
        try:
            store.put("world", {"id": wid, "name": name, "seed": seed, "t": 0.0, "clock_rate": 1.0,
                                "clock_running": 0, "root_id": None, "counters": {},
                                "meta": {"description": description}})
            w = cls(store, wid)
            w._install_base_schemas()
            root = w.spawn(ROOT_TYPE, None, name=name, state={"description": description})
            w._row["root_id"] = root
            w._save_row()
            store.commit()
        except Exception:
            store.rollback()
            raise
        return w

    @classmethod
    def open(cls, store: Store, world_id: str) -> "World":
        return cls(store, world_id)

    def _save_row(self) -> None:
        self.store.put("world", self._row)

    def refresh(self) -> None:
        """Reread the world row (t, clock, counters, cursors, meta) from the store. Two processes share one
        database (the MCP server and a CLI mind, say); each caches the row, and without this each one keeps
        its own clock and may hand out an id the other already used. Sessions call it on every tick."""
        row = self.store.get("world", None, self.id)
        if row is not None:
            self._row = row

    def refresh(self) -> None:
        """Reread the world row (t, clock, counters, cursors, meta) from the store. Two processes share one
        database (the MCP server and a CLI mind, say); each caches the row, and without this each one keeps
        its own clock and may hand out an id the other already used. Sessions call it on every tick."""
        row = self.store.get("world", None, self.id)
        if row is not None:
            self._row = row

    @property
    def root_id(self) -> str:
        return self._row["root_id"]

    @property
    def name(self) -> str:
        return self._row["name"]

    @property
    def seed(self) -> int:
        return int(self._row["seed"])

    @property
    def t(self) -> float:
        return float(self._row["t"])

    def _next_id(self, prefix: str) -> str:
        c = self._row["counters"]
        n = c.get(prefix, 0) + 1
        c[prefix] = n
        self._save_row()
        return f"{prefix}{n}"

    def _install_base_schemas(self) -> None:
        self.define_schema(BASE_TYPE, doc="Everything is an entity.", state={"description": "", "hidden": False})
        self.define_schema(ROOT_TYPE, extends=BASE_TYPE, doc="The world root. Rules set here apply everywhere.")
        self.define_schema("place", extends=BASE_TYPE, doc="Something that contains other things. Locations.",
                           state={"description": ""})
        self.define_schema("thing", extends=BASE_TYPE, doc="A physical object.")
        self.define_schema("creature", extends=BASE_TYPE, doc="Something that can act. Characters, monsters.",
                           state={"hp": 10, "max_hp": 10})

    # ---- schemas and scripts -----------------------------------------------

    def define_schema(self, id: str, extends: str | None = None, doc: str = "", state: dict[str, Any] | None = None,
                      space: dict[str, Any] | None = None, actions: dict[str, Any] | None = None,
                      listeners: list[dict[str, Any]] | None = None, behaviors: list[dict[str, Any]] | None = None,
                      senses: list[str] | None = None) -> dict[str, Any]:
        if id != BASE_TYPE and extends is None:
            extends = BASE_TYPE
        if extends and extends != id and self.store.get("schema", self.id, extends) is None:
            raise Rejected(f"schema {id!r} extends unknown schema {extends!r}",
                           hint="define the parent schema first, or extend 'entity', 'place', 'thing' or 'creature'")
        for verb, a in (actions or {}).items():
            if not isinstance(a, dict) or "script" not in a:
                raise Rejected(f"action {verb!r} needs a dict with a 'script' key",
                               hint='actions={"open": {"script": "door_open", "doc": "Open the door", "reach": "near"}}')
        for lst in (listeners or []) + (behaviors or []):
            if not isinstance(lst, dict) or "script" not in lst:
                raise Rejected("listeners and behaviors are dicts with a 'script' key",
                               hint='listeners=[{"script": "guard_rules", "kinds": ["before_act"]}], '
                                    'behaviors=[{"script": "wander", "every": 10}]')
        old = self.store.get("schema", self.id, id)
        row = {
            "world_id": self.id, "id": id, "extends": extends if id != BASE_TYPE else None, "doc": doc,
            "state": state or {}, "space": space, "actions": actions or {}, "listeners": listeners or [],
            "behaviors": behaviors or [], "senses": senses or [], "version": (old["version"] + 1) if old else 1,
        }
        self.store.put("schema", row)
        self._schema_cache.clear()
        self._holder_types = None
        self.emit("schema_defined", target=None, reach=0, payload={"schema": id, "version": row["version"]})
        return row

    def define_script(self, id: str, source: str, doc: str = "") -> dict[str, Any]:
        Script(source, name=id)  # validate now, fail loudly
        limits_of(source)
        old = self.store.get("script", self.id, id)
        row = {"world_id": self.id, "id": id, "source": source, "doc": doc,
               "version": (old["version"] + 1) if old else 1}
        self.store.put("script", row)
        self.emit("script_defined", target=None, reach=0, payload={"script": id, "version": row["version"]})
        return row

    def script(self, id: str) -> Script:
        row = self.store.get("script", self.id, id)
        if row is None:
            raise Rejected(f"no script {id!r}", hint="define it with define_script")
        p = (self._row["meta"].get("scripts_pending") or {}).get(id)
        if p is not None and p.get("version") == row["version"]:
            if p.get("prev") is None:
                raise Rejected(f"script {id!r} waits for the owner's review", hint="the owner approves it with review_script")
            row = {**row, "source": p["prev"], "version": f"{row['version']}-prev"}  # the reviewed one runs meanwhile
        key = (id, row["version"])
        s = self._script_cache.get(key)
        if s is None:
            s = Script(row["source"], name=id)
            s.limits = limits_of(row["source"])
            self._script_cache[key] = s
        return s

    def schema(self, id: str) -> dict[str, Any]:
        s = self._schema_cache.get(id)
        if s is None:
            s = self.store.get("schema", self.id, id)
            if s is None:
                raise Rejected(f"no schema {id!r}", hint="define it with define_schema, or use an existing type")
            self._schema_cache[id] = s
        return s

    def schemas(self) -> list[dict[str, Any]]:
        return self.store.query("schema", "world_id=?", (self.id,), order="id")

    def scripts(self) -> list[dict[str, Any]]:
        return self.store.query("script", "world_id=?", (self.id,), order="id")

    def schema_chain(self, type: str) -> list[dict[str, Any]]:
        """Most specific first, ending at 'entity'."""
        chain = []
        seen = set()
        cur: str | None = type
        while cur and cur not in seen:
            seen.add(cur)
            s = self.schema(cur)
            chain.append(s)
            cur = s["extends"]
        return chain

    def is_a(self, type: str, ancestor: str) -> bool:
        return any(s["id"] == ancestor for s in self.schema_chain(type))

    def schema_actions(self, type: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for s in reversed(self.schema_chain(type)):
            out.update(s["actions"])
        return out

    def own_actions(self, ent: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """An entity's verbs: its schema's, with each action that is `named_by` a state key opened out into one verb per
        entry of that key's map on this entity (a gift a body holds, by name). An entry is laid over the same name in
        the world's catalogue (the root's state key `catalogue`), so a body keeps only what is its own. The merged
        entry's fields pick overlays the action lists under `by` ({field: {value: action keys}}, a `script` among
        them), and its `doc` field (default "words") is the verb's doc; the script reads the entry by ctx.verb
        (named_entry). An entry never takes a name the schema already gives a verb, and the action that names them is
        not a verb of its own."""
        acts = self.schema_actions(ent["type"])
        named = [a for a in acts.values() if isinstance(a.get("named_by"), dict)]
        if not named:
            return acts
        out = {v: a for v, a in acts.items() if not isinstance(a.get("named_by"), dict)}
        for base in named:
            spec = base["named_by"]
            book = ent["state"].get(spec.get("key"))
            if not isinstance(book, dict):
                continue
            cat = self.catalogue(spec)
            for name, own in sorted(book.items()):
                if name in out or not isinstance(own, dict) or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", str(name)):
                    continue
                entry = {**(cat.get(name) if isinstance(cat.get(name), dict) else {}), **own}
                adef = {k: v for k, v in base.items() if k != "named_by"}
                for field, table in (spec.get("by") or {}).items():
                    adef.update((table or {}).get(str(entry.get(field)), {}))
                doc = entry.get(spec.get("doc", "words"))
                if doc:
                    adef["doc"] = str(doc)[:300]
                adef["named"] = spec.get("key")
                out[name] = adef
        return out

    def named_specs(self) -> list[dict[str, Any]]:
        """Every `named_by` spec the world's schemas carry, one a key, with the verb that carries it (grant_verb, guide)."""
        out: dict[str, dict[str, Any]] = {}
        for s in self.schemas():
            for v, a in (s.get("actions") or {}).items():
                nb = a.get("named_by") if isinstance(a, dict) else None
                if isinstance(nb, dict) and nb.get("key"):
                    out.setdefault(nb["key"], {**nb, "verb": v})
        return list(out.values())

    def catalogue(self, spec: dict[str, Any]) -> dict[str, Any]:
        """The world's catalogue for a `named_by` spec: the root's state key `catalogue`, {name: entry}, or {}."""
        root = self.get(self.root_id) if spec.get("catalogue") else None
        cat = root["state"].get(spec["catalogue"]) if root else None
        return cat if isinstance(cat, dict) else {}

    def named_entry(self, ent: dict[str, Any], key: str, name: str) -> dict[str, Any] | None:
        """The entry `name` of ent's `key` map laid over the catalogue's, or None when the body holds none by that name."""
        own = (ent["state"].get(key) or {}).get(name)
        if not isinstance(own, dict):
            return None
        spec = next((s for s in self.named_specs() if s["key"] == key), {})
        base = self.catalogue(spec).get(name)
        return {**(base if isinstance(base, dict) else {}), **own}

    def schema_defaults(self, type: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for s in reversed(self.schema_chain(type)):
            out.update(s["state"])
        return out

    def schema_space(self, type: str) -> dict[str, Any] | None:
        for s in self.schema_chain(type):
            if s["space"]:
                return s["space"]
        return None

    def schema_components(self, type: str, kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in reversed(self.schema_chain(type)):
            out.extend(s[kind])
        return out

    # ---- graph queries -------------------------------------------------------

    def get(self, id: str | None) -> dict[str, Any] | None:
        if not id:
            return None
        return self.store.get("entity", self.id, id)

    def need(self, id: str | None) -> dict[str, Any]:
        e = self.get(id)
        if e is None:
            raise Rejected(f"no entity {id!r}", hint="ids come from perceive, find or spawn; names are not ids")
        return e

    def children(self, id: str, type: str | None = None) -> list[dict[str, Any]]:
        rows = self.store.query("entity", "world_id=? AND parent_id=?", (self.id, id), order="created_seq")
        if type:
            rows = [r for r in rows if self.is_a(r["type"], type)]
        return rows

    def peers(self, id: str, type: str | None = None) -> list[dict[str, Any]]:
        e = self.need(id)
        if not e["parent_id"]:
            return []
        return [c for c in self.children(e["parent_id"], type) if c["id"] != id]

    def knows_way(self, who: str | None, place: str) -> bool:
        """Whether a body knows the way to a place: any place not `hidden`, and a hidden one whose `known_to` names
        the body or its `faction` (a string, or a list of ids and factions), as the packs' go verbs read it."""
        p = self.get(place)
        if p is None or not p["state"].get("hidden"):
            return True
        kt = p["state"].get("known_to")
        me = self.get(who) if who else None
        if kt is None or me is None:
            return False
        names = {me["id"], me["state"].get("faction")} - {None}
        return bool(names & set(kt)) if isinstance(kt, list) else kt in names

    def sees(self, viewer: str | None, e: dict[str, Any]) -> bool:
        """Whether `viewer` sees a body: anything not `hidden`, and a hidden one only by itself or by the ids its
        `shown_to` lists (a familiar that shows itself to one person and to nobody else)."""
        st = e["state"]
        if not st.get("hidden"):
            return True
        return viewer is not None and (viewer == e["id"] or viewer in (st.get("shown_to") or ()))

    def _veil(self, ids: Iterable[Any]) -> list[str] | None:
        """Who may witness an event that a veiled body (hidden, with a `shown_to` list) is in: the body, the ids it
        shows itself to, and whoever did the deed. None when no veiled body is in it, so the event is as before."""
        out: set[str] | None = None
        for i in ids:
            e = self.get(i) if isinstance(i, str) else None
            if e is not None and e["state"].get("hidden") and isinstance(e["state"].get("shown_to"), list):
                out = (out or set()) | {e["id"], *(str(x) for x in e["state"]["shown_to"])}
        return sorted(out) if out is not None else None

    def ways(self, a: str, b: str, most: int = 8) -> int | None:
        """Ways between where two bodies stand (a place is where it is): 0 the same place, None past `most`."""
        def place(i: str) -> str | None:
            e = self.need(i)
            for _ in range(16):
                if self.is_a(e["type"], "place") or not e["parent_id"]:
                    return e["id"]
                e = self.need(e["parent_id"])
            return e["id"]
        start, goal = place(a), place(b)
        seen, ring = {start}, [start]
        for d in range(max(0, most) + 1):
            if goal in ring:
                return d
            nxt = []
            for p in ring:
                for n in self.neighbors(p, "connects_to"):
                    if n not in seen:
                        seen.add(n)
                        nxt.append(n)
            ring = nxt
        return None

    def within(self, id: str, under: str) -> bool:
        """id is under (or is) the entity `under`."""
        return id == under or under in self.ancestors(id)

    def subjects(self, entity_id: str | None) -> set[str]:
        """Who a body is to an access check: itself and the principal that holds it."""
        if not entity_id:
            return set()
        p = self.embodied(entity_id)
        return {entity_id, p["id"]} if p else {entity_id}

    def may(self, who: str | None, what: str, thing: str) -> bool:
        """May the body `who` do `what` ("r", "w", "x" or a verb) to `thing`, by its access (docs/ACCESS.md)."""
        e = self.get(thing)
        acc = acl.of(e)
        if acc is None:
            return True
        root = self.get(self.root_id)
        if what in ("r", "w", "x"):
            return acl.allows(acc, self.subjects(who), root, what)
        own = self.schema_actions(e["type"]).get(what)
        return acl.may_verb(acc, self.subjects(who), root, what, own=bool(own) and own.get("targets") is None)

    def set_access(self, id: str, *, mode: Any = None, verb: str | None = None, owner: Any = None,
                   group: str | None = None, actor: str | None = None, caused_by: int | None = None) -> dict[str, Any]:
        """chmod and chown: the thing's access after the change, written whole."""
        try:
            acc = acl.changed(acl.of(self.need(id)), mode=mode, verb=verb, owner=owner, group=group)
        except acl.AccessError as x:
            raise Rejected(str(x), hint=acl.HINT) from None
        self.patch(id, {acl.KEY: acc}, actor=actor, caused_by=caused_by, replace=True)
        return acc

    def maker_of(self, frame: str) -> dict[str, Any] | None:
        """A maker's frame's grant (its `maker` state), or None when the frame is gone or the grant revoked."""
        m = ((self.get(frame) or {}).get("state") or {}).get("maker")
        return m if isinstance(m, dict) and not m.get("revoked") else None

    def may_spawn(self, type: str, limits: dict[str, Any]) -> bool:
        """What a limited grant may make: any type when its limits list none, else one that is_a a listed type, or
        a schema in its own namespace."""
        types = limits.get("types")
        pre = limits.get("scripts")
        if pre and type.startswith(pre):
            return True
        return types is None or any(self.is_a(type, t) for t in types)

    def ancestors(self, id: str) -> list[str]:
        """Parent, grandparent, ... root."""
        out = []
        found, parent = self.store.parent_of(self.id, id)
        while found and parent:
            out.append(parent)
            found, parent = self.store.parent_of(self.id, parent)
        return out

    def subtree_ids(self, id: str) -> list[str]:
        out = [id]
        stack = [id]
        while stack:
            for c in self.children(stack.pop()):
                out.append(c["id"])
                stack.append(c["id"])
        return out

    def find(self, type: str | None = None, under: str | None = None, parent: str | None = None,
             name: str | None = None, state: dict[str, Any] | None = None, limit: int | None = 50) -> list[dict[str, Any]]:
        where = ["world_id=?"]
        params: list[Any] = [self.id]
        if parent:
            where.append("parent_id=?")
            params.append(parent)
        if name:
            where.append("lower(name) LIKE ?")
            params.append(f"%{name.lower()}%")
        rows = self.store.query("entity", " AND ".join(where), params, order="created_seq")
        if type:
            rows = [r for r in rows if self.is_a(r["type"], type)]
        if under:
            ids = set(self.subtree_ids(under))
            rows = [r for r in rows if r["id"] in ids and r["id"] != under]
        if state:
            rows = [r for r in rows if all(r["state"].get(k) == v for k, v in state.items())]
        return rows[:limit]

    def edges(self, id: str, relation: str | None = None, direction: str = "both") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if direction in ("out", "both"):
            clauses.append("source=?")
            params.append(id)
        if direction in ("in", "both"):
            clauses.append("target=?")
            params.append(id)
        where = f"world_id=? AND ({' OR '.join(clauses)})"
        params = [self.id] + params
        if relation:
            where += " AND relation=?"
            params.append(relation)
        return self.store.query("edge", where, params, order="id")

    def neighbors(self, id: str, relation: str, direction: str = "out") -> list[str]:
        out = []
        for e in self.edges(id, relation, direction):
            other = e["target"] if e["source"] == id else e["source"]
            if other not in out:
                out.append(other)
        return out

    def hyperedges(self, id: str | None = None, relation: str | None = None) -> list[dict[str, Any]]:
        rows = self.store.query("hyperedge", "world_id=?" + (" AND relation=?" if relation else ""),
                                [self.id] + ([relation] if relation else []), order="id")
        if id:
            rows = [r for r in rows if id in r["participants"]]
        return rows

    def space_of(self, container_id: str | None) -> dict[str, Any] | None:
        if not container_id:
            return None
        e = self.get(container_id)
        if e is None:
            return None
        sp = e["state"].get("space")
        if sp:
            return sp
        return self.schema_space(e["type"])

    def _place_in_space(self, container_id: str | None, pos: Any) -> list[float] | None:
        """Validate a position against the container's space: right number of dims, inside bounds, on the grid."""
        sp = self.space_of(container_id)
        if pos is None:
            if sp and sp.get("dims") and sp.get("origin") is not None:
                return [float(x) for x in sp["origin"]]
            return None
        if not sp or not sp.get("dims"):
            raise Rejected(f"{container_id} has no space; nothing in it has a position",
                           hint='give the container state.space = {"dims": 2, "bounds": [10, 10], "grid": true}')
        pos = [float(x) for x in pos]
        dims = int(sp["dims"])
        if len(pos) != dims:
            raise Rejected(f"{container_id} has {dims} dimensions; got a position with {len(pos)}")
        if sp.get("grid"):
            if any(x != int(x) for x in pos):
                raise Rejected(f"{container_id} is a grid; positions are whole numbers")
        bounds = sp.get("bounds")
        if bounds:
            for i, (x, b) in enumerate(zip(pos, bounds)):
                if x < 0 or x >= float(b):
                    raise Rejected(f"position {pos} is outside {container_id} (axis {i} runs 0 to {b})",
                                   hint="stay inside the bounds, or go to a connected place")
        return pos

    def set_pos(self, id: str, pos: Any, actor: str | None = None, caused_by: int | None = None) -> None:
        """Move within the current container."""
        e = self.need(id)
        new = self._place_in_space(e["parent_id"], pos)
        old = e["pos"]
        e["pos"] = new
        self._touch(e)
        self.emit("moved", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"from": e["parent_id"], "to": e["parent_id"], "from_pos": old, "to_pos": new})

    def distance(self, a: str, b: str) -> float | None:
        """Distance between two siblings in their parent's space. None if not comparable."""
        ea, eb = self.need(a), self.need(b)
        if ea["parent_id"] != eb["parent_id"]:
            return None
        sp = self.space_of(ea["parent_id"])
        if not sp or not sp.get("dims"):
            return 0.0
        pa, pb = ea["pos"], eb["pos"]
        if pa is None or pb is None:
            return None
        return sum((float(x) - float(y)) ** 2 for x, y in zip(pa, pb)) ** 0.5

    # ---- graph mutations (each one logs a primitive event) -----------------------

    def spawn(self, type: str, parent: str | None, name: str = "", state: dict[str, Any] | None = None,
              pos: Any = None, actor: str | None = None, caused_by: int | None = None, id: str | None = None,
              announce: bool = True) -> str:
        """announce=False: the spawn is logged on the new entity alone, so the room does not hear a thing appear
        (something that was always there, brought in by `introduce`)."""
        self.schema(type)
        if parent is not None:
            self.need(parent)
        elif type != ROOT_TYPE or self._row.get("root_id"):
            raise Rejected("only the world root has no parent", hint="pass the parent entity id")
        st = self.schema_defaults(type)
        st.update(state or {})
        pos = self._place_in_space(parent, pos)
        eid = id or self._next_id("e")
        seq = self.store.next_seq(self.id)
        self.store.put("entity", {"world_id": self.id, "id": eid, "type": type, "parent_id": parent, "name": name,
                                  "state": st, "pos": pos, "version": 1, "created_seq": seq, "updated_seq": seq})
        self.emit("spawned", actor=actor, target=eid, reach=1 if announce else 0, caused_by=caused_by,
                  payload={"type": type, "name": name, "parent": parent})
        pace = self._row["meta"].get("pace") or {}
        for b in self.schema_components(type, "behaviors"):
            every = float(pace.get(b["script"], b.get("every", 10)))
            self.schedule(every, "tick", entity=eid, payload={"script": b["script"], "always": bool(b.get("always"))},
                          every=every, caused_by=caused_by, log=False)
        return eid

    def set_pace(self, pace: dict[str, float]) -> int:
        """How often each behavior script ticks in this world, by script name, in world seconds: the world's own pace
        over the schema's `every` (a hosted day is 86400 s; a turn-based story is 600). Kept in meta `pace`, used
        at every spawn, and applied now to the ticks already standing: each one whose beat differs is re-timed to
        fire one new beat from now. Returns how many were re-timed. Idempotent."""
        cur = dict(self._row["meta"].get("pace") or {})
        cur.update({k: float(v) for k, v in pace.items()})
        self.set_meta({"pace": cur})
        n = 0
        for item in self.pending():
            if item["kind"] != "tick" or not item["every"]:
                continue
            want = cur.get((item["payload"] or {}).get("script"))
            if want is None or float(item["every"]) == float(want):
                continue
            item["every"] = float(want)
            item["t"] = self.t + float(want)
            self.store.put("scheduled", item)
            n += 1
        return n

    def patch(self, id: str, changes: dict[str, Any], actor: str | None = None, caused_by: int | None = None,
              replace: bool = False, log: bool = True) -> None:
        """Change state keys. A dict value merges into an existing dict (one new dialog topic does not
        resend the others); replace=True sets the key whole. A value of None deletes the key. log=False writes no
        `patched` event: only for a change another event already records whole (a step's `stepped`)."""
        e = self.need(id)
        if not changes:
            return
        for k in changes:
            if str(k).startswith("_"):
                raise Rejected(f"state key {k!r} is private")
        before = {k: e["state"].get(k) for k in changes}
        for k, v in changes.items():
            if v is None:
                e["state"].pop(k, None)
            elif not replace and isinstance(v, dict) and isinstance(e["state"].get(k), dict):
                e["state"][k] = _deep_merge(e["state"][k], v)
            else:
                e["state"][k] = v
        self._touch(e)
        if log:
            self.emit("patched", actor=actor, target=id, reach=1, caused_by=caused_by,
                      payload={"changes": changes, "before": before, "replace": replace})

    def rename(self, id: str, name: str, actor: str | None = None, caused_by: int | None = None) -> str:
        """Give an entity a new name, refused when someone else in the world already has it (the rule join keeps).
        The room hears `renamed` {old, new}; the old name stays in the log. Returns the old name."""
        e = self.need(id)
        name = str(name or "").strip()
        if not name:
            raise Rejected("a new name cannot be empty", hint="rename(entity, 'the name they go by now')")
        old = e["name"]
        if name == old:
            return old
        if any(r["id"] != id and r["name"].lower() == name.lower() for r in self.find(name=name, limit=None)):
            raise Rejected(f"someone is already called {name!r}", hint="pick another name")
        e["name"] = name
        self._touch(e)
        self.emit("renamed", actor=actor, target=id, reach=1, caused_by=caused_by, payload={"old": old, "new": name})
        return old

    def _touch(self, e: dict[str, Any]) -> None:
        e["version"] += 1
        e["updated_seq"] = self.store.next_seq(self.id)
        self.store.put("entity", e)

    def move(self, id: str, parent: str, pos: Any = None, actor: str | None = None,
             caused_by: int | None = None, quiet: bool = False) -> None:
        """Put an entity in a new container. quiet (an author regrouping the world, a place into its region): it keeps
        its own spot and pos, nobody hears it, and the log keeps one `regrouped` event for the hosts."""
        e = self.need(id)
        self.need(parent)
        if parent == id or parent in self.subtree_ids(id):
            raise Rejected("cannot move an entity into itself")
        old = e["parent_id"]
        if actor is not None and old and old != parent and self._is_body(old) and self._is_body(parent):
            # A thing that passes from one body to another without a gift remembers whom it was taken from, until it
            # goes home; reclaim() reads it. give() marks a gift (given_by) before it moves the thing.
            st = e["state"]
            if st.get("taken_from") == parent:
                st.pop("taken_from")
            elif st.get("given_by") != old and not st.get("taken_from"):
                st["taken_from"] = old
        if quiet:
            e["parent_id"] = parent
            self._touch(e)
            self.emit("regrouped", actor=actor, target=id, reach=0, caused_by=caused_by, payload={"from": old, "to": parent})
            return
        if old != parent:
            # it arrived: where the one who put it down stands, or where the way comes in; else somewhere in the new
            # place until someone places it (positions.py, DESIGN.md section 8, Layout)
            from .positions import arrival
            lay = e["state"].get("layout") if isinstance(e["state"].get("layout"), dict) else {}
            spot = arrival(self, e, old, parent)
            if spot is not None:
                e["state"]["layout"] = {**{k: v for k, v in lay.items() if k != "heading"}, "at": spot}
            elif "at" in lay:
                e["state"]["layout"] = {k: v for k, v in lay.items() if k not in ("at", "heading")}
        e["parent_id"] = parent
        e["pos"] = self._place_in_space(parent, pos)
        self._touch(e)
        # Two events: the old room sees a departure, the new one an arrival.
        self.emit("left", actor=actor, target=old, reach=0, caused_by=caused_by,
                  payload={"entity": id, "to": parent})
        self.emit("moved", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"from": old, "to": parent})

    # -- stacks: a thing whose state has a `count` is that many of itself (coins x60). docs/SCRIPTING.md, Stacks.
    def units(self, id: str) -> int:
        """How many of a thing there are: its `count`, else 1."""
        return _units(self.need(id))

    def split(self, id: str, count: Any, actor: str | None = None, caused_by: int | None = None) -> str:
        """Part `count` units off a stack where it lies: the stack keeps the rest, a like stack beside it gets them.
        Returns the new stack's id, or the stack's own when `count` is all of it."""
        e = self.need(id)
        have = _units(e)
        try:
            n = int(count)
        except (TypeError, ValueError):
            raise Rejected(f"count must be a whole number, not {count!r}", hint="say how many, e.g. count 5") from None
        if n < 1:
            raise Rejected("count must be at least 1", hint="leave count out to take the whole thing")
        if n > have:
            raise Rejected(f"there are only {have} of {e['name']}", hint=f"ask for {have} or fewer")
        if n == have:
            return id
        self.patch(id, {"count": have - n}, actor=actor, caused_by=caused_by)
        st = json.loads(json.dumps(e["state"]))
        st["count"] = n
        return self.spawn(e["type"], e["parent_id"], name=e["name"], state=st, pos=e["pos"], actor=actor,
                          caused_by=caused_by, announce=False)

    def stack_with(self, id: str, holder: str) -> dict[str, Any] | None:
        """The stack under `holder` that `id` would join: same type and name, the same state but for its count and
        who last handed it over (given_by). Only stacks join, and only empty ones (a box of things is not a stack)."""
        e = self.need(id)
        if "count" not in e["state"] or e["state"].get("attached") or self.children(id):
            return None
        key = _stack_key(e)
        for c in self.children(holder):
            if c["id"] != id and "count" in c["state"] and _stack_key(c) == key and not self.children(c["id"]):
                return c
        return None

    def merge(self, id: str, actor: str | None = None, caused_by: int | None = None) -> str:
        """Fold a stack into a like stack in the same holder (stack_with). Returns the id that holds the units now.
        The arriving stack's hand-over marks (given_by) win, so a gift rule reads the gift that just landed."""
        e = self.need(id)
        into = self.stack_with(id, e["parent_id"]) if e["parent_id"] else None
        if into is None:
            return id
        n = _units(e)
        total = _units(into) + n
        changes: dict[str, Any] = {"count": total}
        for k in _HANDOVER:
            if e["state"].get(k) != into["state"].get(k):
                changes[k] = e["state"].get(k)
        self.patch(into["id"], changes, actor=actor, caused_by=caused_by)
        self.emit("merged", actor=actor, target=into["id"], reach=0, caused_by=caused_by,
                  payload={"from": id, "count": n, "total": total})
        self.store.execute("DELETE FROM edge WHERE world_id=? AND (source=? OR target=?)", (self.id, id, id))
        self.store.execute("DELETE FROM scheduled WHERE world_id=? AND entity_id=?", (self.id, id))
        self.store.delete("entity", self.id, id)
        return into["id"]

    def transfer(self, id: str, to: str, count: Any = None, actor: str | None = None,
                 caused_by: int | None = None) -> str:
        """Move a thing, or `count` units of a stack, into `to`, where it joins a like stack. Returns the id of what
        holds the moved units now. A plain move is this with no count and nothing to join."""
        piece = id if count is None else self.split(id, count, actor=actor, caused_by=caused_by)
        self.move(piece, to, actor=actor, caused_by=caused_by)
        return self.merge(piece, actor=actor, caused_by=caused_by)

    def _is_body(self, id: str) -> bool:
        e = self.get(id)
        return bool(e) and self.is_a(e["type"], "creature")

    def reclaimable(self, who: str) -> list[dict[str, Any]]:
        """What `who` may take back from an idle body standing where it stands: a thing whose `owner` it is, a thing
        taken from it, or a thing that body's standing orders give it. World meta `reclaim: false` turns it off."""
        if self._row["meta"].get("reclaim") is False:
            return []
        me = self.get(who)
        if not me or not me["parent_id"]:
            return []
        out = []
        for h in self.children(me["parent_id"]):
            if h["id"] == who or not self.is_a(h["type"], "creature") or not self.idle(h["id"]):
                continue
            gives = (h["state"].get("standing_orders") or {}).get("give") or []
            for t in self.children(h["id"]):
                st = t["state"]
                why = ("yours" if who in (st.get("owner"), st.get("taken_from")) else
                       "their orders" if any(_order_gives(o, t, me) for o in gives) else None)
                if why:
                    out.append({"id": t["id"], "name": t["name"], "from": h["id"], "from_name": h["name"], "why": why})
        return out

    def destroy(self, id: str, actor: str | None = None, caused_by: int | None = None) -> None:
        e = self.need(id)
        if id == self.root_id:
            raise Rejected("cannot destroy the world root")
        # Logged first, while the entity still has a place in the tree, so the event's path reaches its container.
        self.emit("destroyed", actor=actor, target=id, reach=1, caused_by=caused_by,
                  payload={"entity": id, "type": e["type"], "name": e["name"], "parent": e["parent_id"],
                           **({"hidden": True} if e["state"].get("hidden") else {})})
        for cid in reversed(self.subtree_ids(id)):
            self.store.execute("DELETE FROM edge WHERE world_id=? AND (source=? OR target=?)", (self.id, cid, cid))
            self.store.execute("DELETE FROM scheduled WHERE world_id=? AND entity_id=?", (self.id, cid))
            self.store.delete("entity", self.id, cid)

    def link(self, source: str, target: str, relation: str, data: dict[str, Any] | None = None,
             actor: str | None = None, caused_by: int | None = None) -> str:
        self.need(source)
        self.need(target)
        for ex in self.edges(source, relation, "out"):
            if ex["target"] == target:
                ex["data"] = {**ex["data"], **(data or {})}
                self.store.put("edge", ex)
                return ex["id"]
        gid = self._next_id("g")
        self.store.put("edge", {"world_id": self.id, "id": gid, "source": source, "target": target,
                                "relation": relation, "data": data or {}})
        self.emit("linked", actor=actor, target=source, reach=1, caused_by=caused_by,
                  payload={"edge": gid, "target": target, "relation": relation})
        return gid

    def unlink(self, source: str, target: str, relation: str, actor: str | None = None,
               caused_by: int | None = None) -> int:
        n = 0
        for ex in self.edges(source, relation, "out"):
            if ex["target"] == target:
                self.store.delete("edge", self.id, ex["id"])
                n += 1
        if n:
            self.emit("unlinked", actor=actor, target=source, reach=1, caused_by=caused_by,
                      payload={"target": target, "relation": relation})
        return n

    def relate(self, relation: str, participants: list[str], data: dict[str, Any] | None = None,
               actor: str | None = None, caused_by: int | None = None) -> str:
        for p in participants:
            self.need(p)
        hid = self._next_id("h")
        self.store.put("hyperedge", {"world_id": self.id, "id": hid, "relation": relation,
                                     "participants": list(participants), "data": data or {}})
        self.emit("related", actor=actor, target=participants[0] if participants else None, reach=0,
                  caused_by=caused_by, payload={"hyperedge": hid, "relation": relation,
                                                 "participants": list(participants)})
        return hid

    def update_relation(self, id: str, data: dict[str, Any]) -> None:
        h = self.store.get("hyperedge", self.id, id)
        if h is None:
            raise Rejected(f"no relation {id!r}")
        h["data"] = {**h["data"], **data}
        self.store.put("hyperedge", h)

    def unrelate(self, id: str, actor: str | None = None, caused_by: int | None = None) -> None:
        h = self.store.get("hyperedge", self.id, id)
        if h is None:
            raise Rejected(f"no relation {id!r}")
        self.store.delete("hyperedge", self.id, id)
        self.emit("unrelated", actor=actor, target=None, reach=0, caused_by=caused_by,
                  payload={"hyperedge": id, "relation": h["relation"]})

    def set_rule(self, entity: str, script: str, kinds: list[str] | None = None, fuel: int | None = None,
                 actor: str | None = None, caused_by: int | None = None) -> None:
        """A listener on an entity's subtree. `fuel`: the rule's budget per event when it walks a big world (a day pass
        over every beast), from the default 20,000 up to a million."""
        self.script(script)
        e = self.need(entity)
        rule = {"script": script, "kinds": kinds or ["before_act"]}
        if fuel is not None:
            if not 1 <= int(fuel) <= LISTENER_FUEL_MAX:
                raise Rejected(f"fuel is 1 to {LISTENER_FUEL_MAX:,}, not {fuel}",
                               hint="leave it out for the default 20,000; a rule that walks the whole world may need more")
            rule["fuel"] = int(fuel)
        have = e["state"].get("rules", [])
        if rule in have:
            return  # already installed as is: a world file's upgrade() may run twice
        rules = [r for r in have if r["script"] != script]
        rules.append(rule)
        self.patch(entity, {"rules": rules}, actor=actor, caused_by=caused_by)

    def clear_rule(self, entity: str, script: str, actor: str | None = None, caused_by: int | None = None) -> None:
        e = self.need(entity)
        rules = [r for r in e["state"].get("rules", []) if r["script"] != script]
        self.patch(entity, {"rules": rules}, actor=actor, caused_by=caused_by)

    # ---- events ------------------------------------------------------------------

    def emit(self, kind: str, actor: str | None = None, target: str | None = None, reach: int = 1,
             payload: dict[str, Any] | None = None, caused_by: int | None = None) -> dict[str, Any]:
        """Record an event and let listeners along its bubble path react.

        reach: how many levels above the target the event travels. 0 = the
        target only, 1 = its container (the room hears it), -1 = all the way
        to the world root.
        """
        path: list[str] = []
        if target:
            path.append(target)
            anc = self.ancestors(target)
            path.extend(anc if reach < 0 else anc[:reach])
        p = payload or {}
        if kind in _WORD_KINDS and "wall" not in p:  # a word's real time: minds() counts an owed answer in real minutes,
            p = payload = {**p, "wall": self.wall()}  # which a paused clock's world time cannot
        if "seen_by" not in p:
            veil = self._veil((actor, target, p.get("entity"), p.get("who")))
            if veil is not None:  # a veiled body is in it: only those it shows itself to witness it, in every view
                payload = {**p, "seen_by": sorted(set(veil) | ({actor} if actor else set()))}
        seq = self.store.next_seq(self.id)
        ev = {"world_id": self.id, "seq": seq, "t": self.t, "kind": kind, "actor_id": actor, "target_id": target,
              "reach": reach, "payload": payload or {}, "caused_by": caused_by, "path": path}
        self.store.put("event", ev)
        if kind not in _SILENT_KINDS:
            self._dispatch(ev)
            if kind in self._OPINION and self._row["meta"].get("opinion_floor", True):
                self._opinion_floor(ev)
            if kind not in _NO_WAKE:
                self._wake_on(ev)
            elif kind == "act":
                self._rise(ev)
        return ev

    def _rise(self, ev: dict[str, Any]) -> None:
        """A sleeper's own deed wakes it (its verbs sleep and wake aside): a `woke` with `why` rose. A pack's rule that
        wakes it first (d20's) leaves nothing to do here."""
        a = self.get(ev["actor_id"]) if ev["actor_id"] else None
        if a is None or not a["state"].get("asleep") or (ev["payload"] or {}).get("verb") in ("sleep", "wake"):
            return
        self.patch(a["id"], {"asleep": False}, actor=a["id"], caused_by=ev["seq"])
        self.emit("woke", actor=a["id"], target=a["id"], reach=1, caused_by=ev["seq"],
                  payload={"by": a["id"], "why": "rose"})

    def _wake_on(self, ev: dict[str, Any]) -> None:
        """Sleep (a body whose state says `asleep`, put there by a `slept` event and taken off by `woke`). A deed
        someone else does to a sleeper wakes it (a blow, a gift, a word said to it); so does anything loud where it
        lies: an event that carries `loud` or reaches two levels up (a lock broken, a thresher). A quiet hand that
        does not touch it (a theft whose event names the thief) does not."""
        tid = ev["target_id"]
        if not tid:
            return
        t = self.get(tid)
        if t is None:
            return
        woken: list[str] = []
        if t["state"].get("asleep") and ev["actor_id"] and ev["actor_id"] != tid:
            woken.append(tid)
        if _loud(ev):
            near = {tid, t["parent_id"]} - {None}
            for pid in near:
                for c in self.children(pid):
                    if c["state"].get("asleep") and c["id"] not in woken and c["id"] != ev["actor_id"]:
                        woken.append(c["id"])
        for sid in woken:
            self.patch(sid, {"asleep": False}, actor=ev["actor_id"], caused_by=ev["seq"])
            self.emit("woke", actor=ev["actor_id"], target=sid, reach=1, caused_by=ev["seq"],
                      payload={"by": ev["actor_id"], "why": ev["kind"]})

    def _listeners_for(self, entity_id: str, rules_only: bool = False) -> list[dict[str, Any]]:
        found = self.store.rules_of(self.id, entity_id) if entity_id else None
        if found is None:
            return []
        out = [] if rules_only else list(self.schema_components(found[0], "listeners"))
        out.extend(found[1])
        return out

    def _dispatch(self, ev: dict[str, Any], actor: str | None = None, target: str | None = None,
                  verb: str | None = None, params: dict[str, Any] | None = None) -> list[str]:
        """Run listeners along the path, target first, then the rules of every ancestor above the path. A schema
        listener hears what bubbles to its entity (the event's reach); a rule set on an entity hears everything
        that happens under it, however short the reach, so a rule on the root is the table's rule. A listener may
        reject or stop. A schema listener with `holder: True` on a thing also hears what its holder does, or has
        done to it, wherever that is (_holder_listeners)."""
        logs: list[str] = []
        path = list(ev["path"])
        above = []
        if ev["target_id"] and ev["reach"] >= 0:
            above = [a for a in self.ancestors(ev["target_id"]) if a not in path]
        stopped = False
        for node in path + above:
            for lst in self._listeners_for(node, rules_only=node not in path):
                if self._hear(ev, node, lst, logs, actor, target, verb, params):
                    stopped = True
                    break
            if stopped:
                break
        # a carried thing's holder listener hears its holder's deeds wherever they happen; stop() ends the bubbling
        # up the tree, not this, since the thing is not above anyone
        for node, lst in self._holder_listeners(ev, set(path) | set(above)):
            self._hear(ev, node, lst, logs, actor, target, verb, params)
        return logs

    def _hear(self, ev: dict[str, Any], node: str, lst: dict[str, Any], logs: list[str], actor: str | None,
              target: str | None, verb: str | None, params: dict[str, Any] | None) -> bool:
        """Run one listener on one event; True when it stopped the event."""
        kinds = lst.get("kinds") or []
        if kinds and ev["kind"] not in kinds:
            return False
        if lst.get("unless_embodied") and self.embodied(node) and not self.own_lines(node):
            return False  # the table is the floor; an embodied mind answers instead, unless it left lines and is idle
        sb = (ev["payload"] or {}).get("seen_by")
        if sb is not None and node not in sb and self.is_a(self.need(node)["type"], "creature"):
            return False  # a veiled body's deed: someone it was not shown does not hear it either
        s = self.script(lst["script"])
        fn = lst.get("fn", "on")
        if not s.has(fn):
            return False
        ctx = Ctx(self, actor=actor or ev["actor_id"], target=target or ev["target_id"], owner=node,
                  params=params, event=_event_view(ev), verb=verb, caused_by=ev["seq"],
                  seed=self._seed_for(ev["seq"], node))
        try:
            ctx.run(s, fn, [ctx, _event_view(ev)], fuel=min(int(lst.get("fuel") or 20_000), LISTENER_FUEL_MAX))
        except _Stop:
            logs.extend(ctx.logs)
            return True
        except ScriptError as e:
            raise Rejected(f"listener {lst['script']!r} on {node} failed: {e.reason}",
                           hint=e.hint or "fix the listener script") from None
        logs.extend(ctx.logs)
        return False

    def _holder_listeners(self, ev: dict[str, Any], heard: set[str]) -> list[tuple[str, dict[str, Any]]]:
        """The schema listeners marked `holder` on the things the event's parties carry: its actor, its target, and
        the bodies its payload names as `by`, `who`, `to` or `source`. A ledger in a pocket hears its holder give,
        take and be paid. before_act only reaches one whose `kinds` names it."""
        types = self._holder_types
        if types is None:
            types = self._holder_types = {s["id"] for s in self.schemas()
                                          if any(lst.get("holder") for lst in self.schema_components(s["id"], "listeners"))}
        if not types:
            return []
        p = ev["payload"] or {}
        parties: list[str] = []
        for pid in (ev["actor_id"], ev["target_id"], p.get("by"), p.get("who"), p.get("to"), p.get("source")):
            if isinstance(pid, str) and pid and pid not in parties:
                parties.append(pid)
        out: list[tuple[str, dict[str, Any]]] = []
        kinds = sorted(types)
        marks = ",".join("?" * len(kinds))
        for pid in parties:
            for c in self.store.query("entity", f"world_id=? AND parent_id=? AND type IN ({marks})", (self.id, pid, *kinds),
                                      order="created_seq"):
                if c["id"] in heard:
                    continue
                heard.add(c["id"])
                for lst in self.schema_components(c["type"], "listeners"):
                    if lst.get("holder") and (ev["kind"] != "before_act" or ev["kind"] in (lst.get("kinds") or [])):
                        out.append((c["id"], lst))
        return out

    def _seed_for(self, seq: int, salt: str) -> int:
        h = hashlib.sha256(f"{self.seed}:{seq}:{salt}".encode()).digest()
        return int.from_bytes(h[:8], "big")

    def events(self, since: int = 0, until: int | None = None, kinds: list[str] | None = None,
               touching: str | None = None, limit: int = 100, skip: Iterable[str] | None = None,
               newest: bool = False) -> list[dict[str, Any]]:
        """Events after `since`, oldest first. `touching`: only events whose path includes this id or its parent.
        `kinds` and `skip` filter before the limit counts; `newest`: the last `limit` of them, not the first."""
        where = "world_id=? AND seq>?"
        params: list[Any] = [self.id, since]
        if until is not None:
            where += " AND seq<=?"
            params.append(until)
        if kinds:
            where += f" AND kind IN ({','.join('?' * len(kinds))})"
            params.extend(kinds)
        skip = sorted(set(skip or ()))
        if skip:
            where += f" AND kind NOT IN ({','.join('?' * len(skip))})"
            params.extend(skip)
        if touching:
            rows = self._located(touching, self.store.query("event", where, params, order="seq"))
            return rows[-limit:] if newest else rows[:limit]
        if newest:
            return list(reversed(self.store.query("event", where, params, order="seq DESC", limit=limit)))
        return self.store.query("event", where, params, order="seq", limit=limit)

    def _located(self, who: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the events `who` could have witnessed: its own, those on its path, and those in the place it
        stood in at that moment. The place is reconstructed per event from its own `moved` events (payload
        `from`/`to`), walking back from where it stands now, so walking into a square does not hand you what
        was said there before you came. Its sleep is reconstructed the same way (`slept`, `woke`): asleep, it
        keeps only what was done to it and what was loud."""
        if not rows:
            return []
        e = self.get(who)
        here = e["parent_id"] if e else None
        lo = rows[0]["seq"]  # only moves and sleeps after the first row change where or how it stood for these rows
        moves = self.store.query("event", "world_id=? AND actor_id=? AND kind='moved' AND seq>?", (self.id, who, lo),
                                 order="seq")
        moves = [m for m in moves if m["payload"].get("from") != m["payload"].get("to")]
        asleep = bool(e and e["state"].get("asleep"))
        sleeps = self.store.query("event", "world_id=? AND target_id=? AND kind IN ('slept', 'woke') AND seq>?",
                                  (self.id, who, lo), order="seq")
        out = []
        for r in reversed(rows):
            while moves and moves[-1]["seq"] > r["seq"]:
                here = moves.pop()["payload"].get("from")
            while sleeps and sleeps[-1]["seq"] > r["seq"]:
                asleep = sleeps.pop()["kind"] == "woke"  # before a waking it slept; before falling asleep it woke
            watch = {who, here} if here else {who}
            sb = (r["payload"] or {}).get("seen_by")
            if sb is not None and who not in sb:
                continue  # a veiled body's deed, and this one was not shown it
            if r["actor_id"] == who or watch & set(r["path"]):
                if asleep and r["actor_id"] != who and r["target_id"] != who and not _loud(r):
                    continue  # a sleeper hears only what is loud, or what is done to it
                out.append(r)
        out.reverse()
        return out

    # ---- actions -----------------------------------------------------------------

    def _on_trial(self, prog: dict[str, Any]) -> bool:
        """A verb a frame with `review: "writes"` made, not yet reviewed: it runs on a look-only trial (act)."""
        f = self.get(prog["frame"]) if prog.get("frame") else None
        return f is not None and (f["state"].get("maker") or {}).get("review") == "writes"

    def resolve_action(self, actor_id: str, verb: str, target_id: str | None) -> tuple[dict[str, Any], str]:
        """Find the action definition for verb. Returns (definition, owner_id)."""
        actor = self.need(actor_id)
        if target_id:
            target = self.need(target_id)
            acts = self.own_actions(target)
            # a verb named by data is its holder's own, never one done to the holder by whoever is near
            if verb in acts and acts[verb].get("targets") is None and not acts[verb].get("named"):
                return acts[verb], target_id
            prog = own_verbs(target).get(verb)
            # one with `targets` is its holder's own, done to others: not a verb anyone near may use on the holder
            if isinstance(prog, dict) and prog.get("script") and not (prog.get("targets") and target_id != actor_id):
                if prog.get("pending"):
                    if self._on_trial(prog):
                        return {**_programmed(prog), "trial": True}, target_id
                    raise Rejected(f"{verb} on {target['name'] or target_id} waits for the owner's review",
                                   hint="try it again once the owner has looked at it")
                return _programmed(prog), target_id
        acts = self.own_actions(actor)
        if verb in acts:
            tt = acts[verb].get("targets")
            if tt is not None and target_id is None:
                raise Rejected(f"{verb} needs a target", hint=f"{verb} works on a {tt}; pick one perceive lists")
            if tt not in (None, "any") and target_id and not self.is_a(self.need(target_id)["type"], tt):
                raise Rejected(f"you can only {verb} a {tt}, and {target_id} is a {self.need(target_id)['type']}")
            return acts[verb], actor_id
        prog = own_verbs(actor).get(verb) if target_id and target_id != actor_id else None
        if isinstance(prog, dict) and prog.get("script") and prog.get("targets"):
            # a verb put on the actor itself that reaches others (`targets`, by program): ctx.self is the actor
            if prog.get("pending"):
                raise Rejected(f"{verb} waits for the owner's review", hint="try it again once the owner has looked at it")
            tt = prog["targets"]
            if tt != "any" and not self.is_a(self.need(target_id)["type"], tt):
                raise Rejected(f"you can only {verb} a {tt}, and {target_id} is a {self.need(target_id)['type']}")
            return _programmed(prog), actor_id
        known = sorted(set(self.own_actions(actor)) |
                       (set(self.schema_actions(self.need(target_id)["type"])) if target_id else set()))
        raise Rejected(f"no action {verb!r} on {target_id or actor_id}",
                       hint=f"verbs here: {', '.join(known) or 'none'}. Use perceive to see affordances.",
                       alternatives=known)

    def reachable(self, actor_id: str, target_id: str) -> tuple[bool, str]:
        """Can actor act on target? self, container, siblings, inventory, what lies on a holder here, or a connected place."""
        if actor_id == target_id:
            return True, ""
        actor = self.need(actor_id)
        target = self.need(target_id)
        if target_id == actor["parent_id"]:
            return True, ""
        if target["parent_id"] == actor_id:
            return True, ""
        if target["parent_id"] == actor["parent_id"] and actor["parent_id"] is not None:
            if target["state"].get("hidden"):
                return False, f"{target_id} is hidden"
            return True, ""
        if target["state"].get("attached") and target["parent_id"]:
            return self.reachable(actor_id, target["parent_id"])  # a lock on a box, a door or a place: in reach where it is
        holder = self.get(target["parent_id"]) if target["parent_id"] else None
        if (holder is not None and holder["state"].get("holds") is not None and actor["parent_id"] is not None
                and holder["parent_id"] == actor["parent_id"] and not holder["state"].get("hidden")
                and not target["state"].get("hidden")):
            why = self.shut_line(holder["id"])
            if why is not None:
                return False, why
            return True, ""  # what lies on a rack or in an open chest here is within reach
        if actor["parent_id"]:
            for e in self.edges(actor["parent_id"], "connects_to", "out"):
                # The next place is reachable, and so is whatever the passage goes through (a door).
                if target_id == e["target"] or target_id == e["data"].get("via"):
                    return True, ""
        if target["parent_id"] == actor["parent_id"] is None:
            return True, ""
        return False, f"{target_id} ({target['name'] or target['type']}) is not within reach of {actor_id}"

    def _closer_hint(self, actor_id: str, target_id: str) -> str:
        """How to get within reach, in verbs that exist: `go` to the place next door it is in (an agent told to "move
        closer" looked for a move verb). Nothing hidden is named, and a place further off is left to the map."""
        actor, target = self.need(actor_id), self.need(target_id)
        at = target
        for _ in range(8):  # up to the place it stands in: a thing in a hand or a chest is where its holder is
            if at is None or self.is_a(at["type"], "place") or at["state"].get("hidden"):
                break
            at = self.get(at["parent_id"]) if at["parent_id"] else None
        if (at is not None and self.is_a(at["type"], "place") and not at["state"].get("hidden")
                and not target["state"].get("hidden") and actor["parent_id"]):
            for e in self.edges(actor["parent_id"], "connects_to", "out"):
                if e["target"] == at["id"]:
                    return f"go {at['name']} first ({target['name']} is there), or pick something perceive lists"
        return "go where it is first (the places perceive lists under exits), or pick something perceive lists"

    def shut_line(self, id: str) -> str | None:
        """The refusal for a locked box, door or place, with only the ways its lock has: its key, its code, a pick
        (`pick_dc`), a break (`break_dc`). A lock no hand opens (its `shut_why`, the whole line) says that instead.
        None when nothing keeps it shut."""
        e = self.get(id)
        lk = self.locked_by(id) if e else None
        if lk is None:
            return None
        st, ways = lk["state"], []
        if st.get("shut_why"):
            return str(st["shut_why"])
        hand = [w for w, on in (("its key", st.get("key")), ("its code", st.get("code"))) if on]
        if hand:
            ways.append("with " + " or ".join(hand))
        if st.get("pick_dc"):
            ways.append("pick it")
        if st.get("break_dc") and not st.get("broken"):
            ways.append("break it")
        return (f"{e['name']} is locked: unlock " + ("it" if lk["id"] == e["id"] else lk["name"]) + " first"
                + (", " + ", or ".join(ways) if ways else ""))

    # ---- oracles: a thing's verbs whose work is done outside the world (docs/ORACLES.md) ----------------------------

    def oracle_of(self, eid: str) -> dict[str, Any] | None:
        """The oracle a thing is bound to (its `oracle` state, which invite('oracle', entity=...) sets), or None."""
        b = ((self.get(eid) or {}).get("state") or {}).get("oracle")
        return b if isinstance(b, dict) and b.get("grant") else None

    def oracle_down(self, eid: str, grant: str | None = None) -> str | None:
        """Why a thing has no connection now, or None: no oracle bound (or another than the verb's), its grant ended,
        or its oracle has not called in for ORACLE_STALE real seconds."""
        b = self.oracle_of(eid)
        name = self.need(eid)["name"] or eid
        if b is None or (grant is not None and b["grant"] != grant):
            return f"{name} has no connection: no oracle answers that here now"
        g = self.store.get("grants", self.id, b["grant"])
        if g is None or g.get("revoked") or (g.get("expires") is not None and float(g["expires"]) <= self.wall()):
            return f"{name} has no connection: its oracle's grant has ended"
        seen = self._oracle_seen.get(eid)
        if seen is None or self.wall() - seen > ORACLE_STALE:
            return f"{name} has no connection right now: its oracle ({b.get('label') or b['grant']}) is not listening"
        return None

    def oracle_open(self, eid: str, emit: bool = False, caused_by: int | None = None) -> list[dict[str, Any]]:
        """The calls on a thing that wait for an answer, oldest first. A call past its timeout lapses: with emit, its
        caller is told (`oracle_lapsed`, to them alone)."""
        rows = self.store.query("event", "world_id=? AND target_id=? AND kind IN (?, ?, ?)", (self.id, eid, *ORACLE_KINDS),
                                order="seq DESC", limit=500)
        closed = {(r["payload"] or {}).get("request") for r in rows if r["kind"] != "oracle_called"}
        now = self.wall()
        out = []
        for r in reversed(rows):
            if r["kind"] != "oracle_called" or r["seq"] in closed:
                continue
            p = r["payload"] or {}
            if now > float(p.get("wall") or 0) + float(p.get("timeout") or ORACLE_TIMEOUT):
                if emit:
                    self.emit("oracle_lapsed", actor=None, target=eid, reach=1, caused_by=caused_by,
                              payload={"request": r["seq"], "verb": p.get("verb"), "to": r["actor_id"],
                                       "seen_by": [r["actor_id"]]})
                continue
            out.append(r)
        return out

    def oracle_ready(self, eid: str, actor_id: str, params: dict[str, Any] | None,
                     adef: dict[str, Any]) -> tuple[str, str] | None:
        """Why a call on an oracle's verb cannot go out now, as (reason, hint), or None: no connection, params past
        ORACLE_ARGS or not plain JSON, the caller's last call still open, the thing busy (max_open), or the caller past
        its calls an hour (per_hour)."""
        why = self.oracle_down(eid, adef.get("grant"))
        if why:
            return why, "its oracle is an app outside the world; try again later, or ask the world's owner"
        b = self.oracle_of(eid) or {}
        name = self.need(eid)["name"] or eid
        try:
            size = len(json.dumps(params or {}))
        except (TypeError, ValueError):
            return "what you send an oracle is plain JSON", "params of strings, numbers, lists and dicts"
        if size > ORACLE_ARGS:
            return f"what you send {name} is {size} characters; it takes {ORACLE_ARGS}", "send less"
        waiting = self.oracle_open(eid)
        if any(r["actor_id"] == actor_id for r in waiting):
            return f"{name} is still working on your last call", "wait for its oracle_answer, or for the call to lapse"
        most = int(b.get("max_open") or ORACLE_LIMITS["max_open"])
        if len(waiting) >= most:
            return f"{name} is busy: {len(waiting)} calls wait for an answer", "try again in a moment"
        per = int(b.get("per_hour") or ORACLE_LIMITS["per_hour"])
        mine = self.store.query("event", "world_id=? AND target_id=? AND actor_id=? AND kind='oracle_called'",
                                (self.id, eid, actor_id), order="seq DESC", limit=per)
        if len(mine) >= per and self.wall() - float((mine[-1]["payload"] or {}).get("wall") or 0) < 3600:
            return f"{name} takes {per} calls an hour from you", "try again later"
        return None

    def oracle_call(self, eid: str, actor_id: str, verb: str, params: dict[str, Any], adef: dict[str, Any],
                    caused_by: int) -> dict[str, Any]:
        """Send a call to the thing's oracle: `oracle_called` on the thing, its seq the request. The oracle learns the
        verb, the params and a handle for the caller that is the same on this thing every time and names nobody."""
        b = self.oracle_of(eid) or {}
        timeout = min(float(adef.get("timeout") or ORACLE_TIMEOUT), ORACLE_TIMEOUT_MAX)
        caller = "c" + hashlib.sha256(f"{self.id}:{eid}:{actor_id}".encode()).hexdigest()[:10]
        payload: dict[str, Any] = {"verb": verb, "args": dict(params or {}), "caller": caller, "wall": self.wall(),
                                   "timeout": timeout, "oracle": b.get("label")}
        if adef.get("private", True):
            payload["seen_by"] = [actor_id]
        ev = self.emit("oracle_called", actor=actor_id, target=eid, reach=1, payload=payload, caused_by=caused_by)
        self.oracle_open(eid, emit=True, caused_by=caused_by)  # anyone whose call lapsed hears so now
        name = self.need(eid)["name"] or eid
        return {"request": ev["seq"], "oracle": b.get("label"), "timeout": timeout,
                "log": (f"{verb} goes out from {name} to {b.get('label') or 'its oracle'}: the answer comes as an "
                        f"oracle_answer event (request {ev['seq']}) within {timeout:g} s, or the call lapses "
                        f"(oracle_lapsed); wait(kinds=['oracle_answer', 'oracle_lapsed']) brings it")}

    def oracle_answer(self, eid: str, request: int, text: str, data: Any, ok: bool) -> dict[str, Any]:
        """The oracle's answer to one open call, as `oracle_answer` on the thing: to the caller alone for a private
        verb, to the room for a public one. It is marked untrusted, since it comes from outside the world."""
        waiting = {r["seq"]: r for r in self.oracle_open(eid, emit=True)}
        call = waiting.get(request)
        if call is None:
            done = self.store.query("event", "world_id=? AND target_id=? AND kind IN (?, ?)",
                                    (self.id, eid, "oracle_answer", "oracle_lapsed"), order="seq DESC", limit=500)
            lapsed = any(r["kind"] == "oracle_lapsed" and (r["payload"] or {}).get("request") == request for r in done)
            raise Rejected(f"call {request} " + ("lapsed before its answer came" if lapsed else "is not open: it was answered"),
                           hint="answer within the call's lapses_in seconds; wait() lists the calls still open")
        p = call["payload"] or {}
        b = self.oracle_of(eid) or {}
        out: dict[str, Any] = {"request": request, "verb": p.get("verb"), "to": call["actor_id"], "ok": bool(ok),
                               "text": text, "oracle": b.get("label"), "untrusted": True}
        if data is not None:
            out["data"] = data
        if p.get("seen_by"):
            out["seen_by"] = list(p["seen_by"])
        ev = self.emit("oracle_answer", actor=None, target=eid, reach=1, payload=out, caused_by=request)
        return {"request": request, "seq": ev["seq"], "to": p.get("caller"), "public": not p.get("seen_by")}

    def locked_by(self, id: str) -> dict[str, Any] | None:
        """What keeps a box, a door or a place shut: the entity itself when its state says `locked`, or a lock
        attached to it (a child whose state has `attached` and `locked`). None when nothing does."""
        e = self.get(id)
        if e is None:
            return None
        if e["state"].get("locked"):
            return e
        for c in self.children(id):
            if c["state"].get("attached") and c["state"].get("locked"):
                return c
        return None

    def _dead_ok(self, actor_id: str, verb: str) -> bool:
        """A verb of the body's own that its schema marks `dead_ok`: what a dead seat may still do (give its leave)."""
        a = self.schema_actions(self.need(actor_id)["type"]).get(verb)
        return bool(a and a.get("dead_ok") and not a.get("targets"))

    def check_action(self, actor_id: str, verb: str, target_id: str | None = None,
                     params: dict[str, Any] | None = None) -> tuple[bool, str | None]:
        """Preconditions only. Returns (ok, reason)."""
        try:
            self._prepare(actor_id, verb, target_id, params, dry=True)
            return True, None
        except Rejected as r:
            return False, r.reason

    def _prepare(self, actor_id: str, verb: str, target_id: str | None, params: dict[str, Any] | None,
                 dry: bool) -> tuple[dict[str, Any], str, Script]:
        if self.need(actor_id)["state"].get("dead") and not self._dead_ok(actor_id, verb):
            # first, before any other reason: a mind that hears "the door is shut" never learns it has died
            left = [v for v, a in self.schema_actions(self.need(actor_id)["type"]).items()
                    if a.get("dead_ok") and not a.get("targets")]
            raise Rejected("you are dead", hint="nothing you do reaches the world now; perceive still shows it. "
                                                + (f"Your seat may still: {', '.join(sorted(left))}. " if left else "")
                                                + "A guest whose invite makes characters may join(template=...) for a new one")
        self._verbs_only(actor_id, verb)
        adef, owner = self.resolve_action(actor_id, verb, target_id)
        if owner != actor_id:
            me = self.need(actor_id)
            if me["state"].get("hands", self.schema_defaults(me["type"]).get("hands")) is False:
                raise Rejected(f"you have no hands in this world: {verb} is a thing's verb, and you can't take, give, "
                               "open or use things", hint="your own verbs are the ones you have; perceive lists them")
        reach = adef.get("reach", "near")
        if target_id and reach == "near":
            ok, why = self.reachable(actor_id, target_id)
            if not ok:
                raise Rejected(why, hint=self._closer_hint(actor_id, target_id))
            rng = adef.get("range")
            if rng is not None:
                d = self.distance(actor_id, target_id)
                if d is not None and d > float(rng):
                    raise Rejected(f"{target_id} is {d:.1f} away; {verb} reaches {rng}",
                                   hint="walk nearer to it first, then try again")
        elif target_id and reach == "self" and target_id != actor_id:
            raise Rejected(f"{verb} can only target yourself")
        if adef.get("strikes") and target_id and target_id != actor_id:
            wait = self.strike_wait(actor_id, target_id)
            if wait > 0:
                name = self.need(target_id)["name"] or target_id
                raise Rejected(f"you can strike {name} again in about {self._real_s(wait)} s",
                               hint="a blow takes its time: do something else, or wait (it shows in perceive)")
        if adef.get("cooldown"):
            wait = self.verb_wait(actor_id, verb)
            if wait > 0:
                raise Rejected(f"you can {verb} again in about {self._real_s(wait)} s",
                               hint="that takes its time: do something else, or wait")
        for k, n in (adef.get("cost") or {}).items():
            have = self.need(actor_id)["state"].get(k)
            if not isinstance(have, (int, float)) or have < n:
                raise Rejected(f"{verb} costs {n:g} {k} and you have {have if isinstance(have, (int, float)) else 0:g}",
                               hint=f"get more {k} first")
        acc = acl.of(self.get(target_id)) if target_id and target_id != actor_id else None
        if acc is not None and not acl.may_verb(acc, self.subjects(actor_id), self.get(self.root_id), verb,
                                                own=owner == target_id):
            name = self.need(target_id)["name"] or target_id
            raise Rejected(f"{name} does not answer {verb} from you: that is for {acl.who_may(acc, verb, owner == target_id)}",
                           hint="its owner can chmod or chown it; or find another way")
        s = None if adef.get("oracle") else self.script(adef["script"])  # an oracle's verb runs no script here
        if s is not None and not s.has("apply"):
            raise Rejected(f"script {adef['script']!r} has no apply(ctx)", hint="actions need def apply(ctx)")
        frame = (s.limits or {}).get("frame") if s is not None else None
        if frame and self.maker_of(frame) is None:
            raise Rejected(f"{verb} was made with a frame whose grant is gone", hint="its owner can unprogram it")
        # Rules: before_act bubbles all the way up so world rules see it; a local rule may stop() or reject it.
        payload = {"verb": verb, "params": dict(params or {}), "owner": owner}
        if dry:
            tgt = target_id or actor_id
            ev = {"world_id": self.id, "seq": self.store.next_seq(self.id), "t": self.t, "kind": "before_act",
                  "actor_id": actor_id, "target_id": tgt, "reach": -1, "payload": payload, "caused_by": None,
                  "path": [tgt] + self.ancestors(tgt)}
        else:
            ev = self.emit("before_act", actor=actor_id, target=target_id or actor_id, reach=-1, payload=payload)
        self._dispatch(ev, actor=actor_id, target=target_id, verb=verb, params=params)
        if s is None:
            why = self.oracle_ready(owner, actor_id, params, adef)
            if why:
                raise Rejected(why[0], hint=why[1])
        elif s.has("check"):
            ctx = Ctx(self, actor=actor_id, target=target_id, owner=owner, params=params, event=None, verb=verb,
                      caused_by=None, seed=self._seed_for(self.store.next_seq(self.id), "check"))
            ctx._consent = True
            ctx._trial = bool(adef.get("trial"))
            before = self.store.conn.total_changes
            try:
                res = ctx.run(s, "check", [ctx], fuel=5_000)
            except ScriptError as e:
                raise Rejected(f"check for {verb!r} failed: {e.reason}", hint=e.hint) from None
            if ctx._trial and self.store.conn.total_changes != before:
                raise Rejected(f"{verb} waits for the owner's review: until then it may only look, and this run would change the world", hint="it runs in full once the owner approves it (review(thing, verb)); until then use it to look, or ask the owner")
            if res is False:
                raise Rejected(f"{verb} is not possible right now")
            if isinstance(res, str) and res:
                raise Rejected(res)
        return adef, owner, s

    def act(self, actor_id: str, verb: str, target_id: str | None = None, params: dict[str, Any] | None = None,
            principal_id: str | None = None) -> dict[str, Any]:
        """The only way state changes on purpose. Returns {ok, events, logs} or raises Rejected."""
        params = dict(params or {})
        self.need(actor_id)
        self.store.begin()
        start_seq = self.store.next_seq(self.id) - 1
        try:
            adef, owner, s = self._prepare(actor_id, verb, target_id, params, dry=False)
            logs: list[str] = []
            private = bool(s is None and adef.get("private", True))  # a private oracle call: what was asked is the caller's
            ev = self.emit("act", actor=actor_id, target=target_id or actor_id, reach=1,
                           payload={"verb": verb, "params": params, "target": target_id,
                                    **({"seen_by": [actor_id]} if private else {})})
            if s is None:
                result = self.oracle_call(owner, actor_id, verb, params, adef, ev["seq"])
                logs.append(result.pop("log"))
            else:
                ctx = Ctx(self, actor=actor_id, target=target_id, owner=owner, params=params, event=_event_view(ev),
                          verb=verb, caused_by=ev["seq"], seed=self._seed_for(ev["seq"], "apply"))
                ctx._consent = True
                ctx._trial = bool(adef.get("trial"))
                before = self.store.conn.total_changes
                try:
                    # a verb that walks a big book may ask for more (`fuel` on the action, at most a million)
                    result = ctx.run(s, "apply", [ctx], fuel=min(int(adef.get("fuel") or 50_000), 1_000_000))
                except ScriptError as e:
                    raise Rejected(f"{verb} failed while applying: {e.reason}", hint=e.hint) from None
                if ctx._trial and self.store.conn.total_changes != before:
                    # the store counts every row written, so no write call slips past a list of them
                    raise Rejected(f"{verb} waits for the owner's review: until then it may only look, and this run would change the world", hint="it runs in full once the owner approves it (review(thing, verb)); until then use it to look, or ask the owner")
                logs.extend(ctx.logs)
                if ctx._witnesses is not None:  # the verb said who sees its deed: the act line is theirs and the doer's
                    seen = set(ctx._witnesses) | {actor_id}
                    old = ev["payload"].get("seen_by")
                    seen = seen if old is None else seen & set(old) | {actor_id}  # a veil already on it narrows it too
                    ev["payload"] = {**ev["payload"], "seen_by": sorted(seen)}
                    self.store.put("event", ev)
            if adef.get("strikes") and target_id and target_id != actor_id:
                # the verb's own cooldown_x, times the one its apply returns (the weapon it struck with: a maul's 2)
                x = float(adef.get("cooldown_x") or 1)
                if isinstance(result, dict) and isinstance(result.get("cooldown_x"), (int, float)):
                    x = x * float(result["cooldown_x"])
                self.mark_strike(actor_id, target_id, x, actor=actor_id, caused_by=ev["seq"])
            if adef.get("cooldown"):
                self.mark_verb(actor_id, verb, float(adef["cooldown"]), caused_by=ev["seq"])
            if adef.get("cost"):
                st = self.need(actor_id)["state"]
                self.patch(actor_id, {k: st.get(k, 0) - n for k, n in adef["cost"].items()}, actor=actor_id,
                           caused_by=ev["seq"])
            dur = float(adef.get("duration", 0) or 0)
            if dur > 0 and s is not None and s.has("finish"):
                self.schedule(dur, "finish", entity=owner, caused_by=ev["seq"],
                              payload={"script": adef["script"], "actor": actor_id, "target": target_id,
                                       "verb": verb, "params": params})
            if principal_id:
                self._bump_cursor(principal_id)
            self.store.commit()
        except Rejected as r:
            self.store.rollback()
            if not r.alternatives:
                r.alternatives = [a["verb"] + (f" {a['target']}" if a.get("target") else "")
                                  for a in self.affordances(actor_id) if a["ok"]][:12]
            raise
        except Exception:
            self.store.rollback()
            raise
        evs = self.events(since=start_seq, limit=500)
        return {"ok": True, "verb": verb, "target": target_id, "result": result,
                "duration": float(adef.get("duration", 0) or 0),
                "events": [_public_event(e) for e in evs if e["kind"] not in _INTERNAL_KINDS], "logs": logs,
                **({"maker": s.limits["frame"], "untrusted": True} if s is not None and (s.limits or {}).get("frame") else {}),
                **({"trial": True} if adef.get("trial") else {})}

    # ---- strikes: a cooldown per attacker per target (docs/SCRIPTING.md, Strikes) ----------------------------------

    def strike_cooldown(self, actor_id: str, target_id: str, x: float = 1) -> float:
        """World seconds a strike holds the striker off that target: the meta's `strike_cooldown` in real seconds
        (`held` when either side is held by a player or a mind, the time an agent takes to read and decide; `free`
        when neither is), times x, times the clock's rate. A paused clock has none: its turns are the pace."""
        ck = self.clock()
        if not ck["running"] or ck["rate"] <= 0:
            return 0.0
        m = {**STRIKE_COOLDOWN, **(self.meta().get("strike_cooldown") or {})}
        held = self.embodied(actor_id) is not None or self.embodied(target_id) is not None
        return max(0.0, float(m["held" if held else "free"]) * float(x) * ck["rate"])

    def strike_wait(self, actor_id: str, target_id: str) -> float:
        """World seconds until actor may strike target again, 0 when it may now: its cooldown on that target, and
        the floor of half that on anyone (so turning to another foe is no way round it)."""
        cd = self.need(actor_id)["state"].get("cooldowns") or {}
        ready = max(float(cd.get(target_id) or 0), float(cd.get("*") or 0))
        return max(0.0, ready - self.t)

    def mark_strike(self, actor_id: str, target_id: str, x: float = 1, actor: str | None = None,
                    caused_by: int | None = None) -> float:
        """Start the cooldown after a strike (secret state `cooldowns`: the world time each foe is ready again, and
        `*` the floor on any). Returns the cooldown in world seconds."""
        cd = self.strike_cooldown(actor_id, target_id, x)
        if cd <= 0:
            return 0.0
        st = self.need(actor_id)["state"]
        cds = {k: v for k, v in (st.get("cooldowns") or {}).items() if float(v) > self.t}
        cds[target_id] = self.t + cd
        cds["*"] = max(float(cds.get("*") or 0), self.t + cd / 2)
        self.patch(actor_id, {"cooldowns": cds}, actor=actor, caused_by=caused_by)
        return cd

    # ---- what a body may do and what it understands (docs/SCRIPTING.md, Beasts and seats) -------------------------

    def _own(self, eid: str, key: str) -> Any:
        """A body's own value for a key, else its schema's default."""
        e = self.need(eid)
        return e["state"][key] if key in e["state"] else self.schema_defaults(e["type"]).get(key)

    def verbs_only(self, eid: str) -> list[str] | None:
        """The only verbs a body may use (`verbs_only` on it or its schema), None when it may use any."""
        vo = self._own(eid, "verbs_only")
        return [str(v) for v in vo] if isinstance(vo, list) else None

    def _verbs_only(self, eid: str, verb: str, also: tuple[str, ...] = ()) -> None:
        vo = self.verbs_only(eid)
        if vo is None or verb in vo or any(a in vo for a in also):
            return
        e = self.need(eid)
        kind = e["state"].get("species") if isinstance(e["state"].get("species"), str) else e["type"]
        raise Rejected(f"a {kind} cannot {verb}: it can {', '.join(vo) or 'do nothing'}",
                       hint="this body's verbs are all it has; perceive lists them")

    def understands(self, eid: str) -> bool:
        """Whether a body follows words: `understands` on it or its schema (a `beast` does not, unless it says so),
        and `understands_until` (world time, a herb's while) over both."""
        until = self._own(eid, "understands_until")
        if isinstance(until, (int, float)) and self.t < until:
            return True
        u = self._own(eid, "understands")
        if u is not None:
            return bool(u)
        return not self._own(eid, "beast")

    def verb_wait(self, actor_id: str, verb: str) -> float:
        """World seconds until actor may use a verb with a `cooldown` again, 0 when it may now."""
        cd = self.need(actor_id)["state"].get("cooldowns") or {}
        return max(0.0, float(cd.get("verb:" + verb) or 0) - self.t)

    def mark_verb(self, actor_id: str, verb: str, world_s: float, caused_by: int | None = None) -> None:
        """Start a verb's cooldown (secret `cooldowns`, key `verb:<verb>`), in world seconds. A paused clock has
        none, as with strikes: its turns are the pace."""
        ck = self.clock()
        if world_s <= 0 or not ck["running"] or ck["rate"] <= 0:
            return
        st = self.need(actor_id)["state"]
        cds = {k: v for k, v in (st.get("cooldowns") or {}).items() if float(v) > self.t}
        cds["verb:" + verb] = self.t + world_s
        self.patch(actor_id, {"cooldowns": cds}, actor=actor_id, caused_by=caused_by)

    def _real_s(self, world_s: float) -> int:
        """World seconds as the real seconds a player waits."""
        rate = self.clock()["rate"] or 1
        return max(1, round(world_s / rate))

    def in_sight(self, actor_id: str) -> list[str]:
        """The creatures one way over that a body can see (scope "sight": a bow, a thrown spear): through a way it
        knows (knows_way), with no shut door on it (the passage's `via` open, or none), and not hidden."""
        here = self.need(actor_id)["parent_id"]
        out: list[str] = []
        for e in self.edges(here, "connects_to", "out") if here else []:
            via = self.get(e["data"].get("via")) if e["data"].get("via") else None
            if (via is not None and not via["state"].get("open")) or not self.knows_way(actor_id, e["target"]):
                continue
            out.extend(c["id"] for c in self.children(e["target"])
                       if not c["state"].get("hidden") and self.is_a(c["type"], "creature"))
        return out

    def affordances(self, actor_id: str, target_id: str | None = None) -> list[dict[str, Any]]:
        """Every verb the actor could try on itself and on reachable entities, with preconditions evaluated."""
        actor = self.need(actor_id)
        candidates: list[str] = [actor_id]
        if target_id:
            candidates = [target_id]
        else:
            if actor["parent_id"]:
                candidates.append(actor["parent_id"])
                candidates.extend(c["id"] for c in self.children(actor["parent_id"]) if c["id"] != actor_id
                                  and not c["state"].get("hidden"))
                candidates.extend(n for n in self.neighbors(actor["parent_id"], "connects_to")
                                  if self.knows_way(actor_id, n))  # a hidden way is shown to those who know it
            candidates.extend(c["id"] for c in self.children(actor_id))
            for cid in list(candidates):  # what is attached to a thing or a place in reach (a lock) is in reach too
                ent = self.get(cid)
                if cid != actor_id and cid != actor["parent_id"] and ent and not self.is_a(ent["type"], "creature"):
                    candidates.extend(c["id"] for c in self.children(cid) if c["state"].get("attached"))
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None]] = set()

        def add(verb: str, adef: dict[str, Any], tid: str | None) -> None:
            key = (verb, tid)
            if key in seen or adef.get("hidden"):
                return
            seen.add(key)
            ok, reason = self.check_action(actor_id, verb, tid)
            if not ok and tid is not None and adef.get("listed") == "ok":
                return  # a verb that fits few targets (pour) lists only where it would work
            tgt = self.get(tid) if tid else None
            out.append({"verb": verb, "target": tid, "target_name": tgt["name"] if tgt else None, "ok": ok,
                        "reason": reason, "doc": adef.get("doc", ""), "params": adef.get("params", {}),
                        **({"trial": True} if adef.get("trial") else {})})

        # Verbs the actor carries. One with `targets` (a type) pairs with every reachable entity of that type;
        # one without is the actor's own (rest, shout, look).
        actor_verbs = self.own_actions(actor)
        here = actor["parent_id"]
        held = {c["id"] for c in self.children(actor_id)}
        exits = set(self.neighbors(here, "connects_to")) if here else set()
        sight = self.in_sight(actor_id) if not target_id and any(
            a.get("scope") == "sight" for a in actor_verbs.values()) else []
        for verb, adef in actor_verbs.items():
            tt = adef.get("targets")
            if tt is None:
                add(verb, adef, None)
                continue
            scope = adef.get("scope", "any")
            for cid in candidates + sight if scope == "sight" else candidates:
                if cid == actor_id and adef.get("reach") != "self" and not adef.get("self"):
                    continue  # self is a target only for reach "self" verbs or verbs flagged self: true
                # scope keeps the impossible pairs out of the list: drop what you do not hold, go where you stand
                if scope == "held" and cid not in held:
                    continue
                if scope in ("here", "sight") and (cid in held or cid == here or cid in exits):
                    continue
                if scope == "exits" and cid not in exits:
                    continue
                ent = self.get(cid)
                if ent and (tt == "any" or self.is_a(ent["type"], tt)):
                    add(verb, adef, cid)
        for verb, prog in own_verbs(actor).items():  # verbs put on the actor itself that reach others (`targets`)
            tt = prog.get("targets") if isinstance(prog, dict) else None
            if not tt or not prog.get("script") or prog.get("pending"):
                continue
            for cid in candidates:
                ent = self.get(cid)
                if cid != actor_id and ent and (tt == "any" or self.is_a(ent["type"], tt)):
                    add(verb, _programmed(prog), cid)
        # Verbs the things around the actor carry: every object is also its ops. A creature's own targetless
        # verbs (brace, check, sleep) are things it does, not things done to it, so they are not listed against it.
        for cid in candidates:
            if cid == actor_id:
                continue
            ent = self.get(cid)
            if ent is None or self.is_a(ent["type"], "creature"):
                continue
            for verb, adef in self.schema_actions(ent["type"]).items():
                if adef.get("targets") is None:  # an action with `targets` is the holder's own verb, not one done to it
                    add(verb, adef, cid)
            for verb, prog in own_verbs(ent).items():  # verbs put on this one thing
                if isinstance(prog, dict) and prog.get("script") and not prog.get("targets"):
                    if not prog.get("pending"):
                        add(verb, _programmed(prog), cid)
                    elif self._on_trial(prog):  # waiting for review, it may still look
                        add(verb, {**_programmed(prog), "trial": True}, cid)
        return out

    # ---- clock and scheduling -----------------------------------------------------

    def schedule(self, after: float, kind: str, entity: str | None = None, payload: dict[str, Any] | None = None,
                 every: float | None = None, caused_by: int | None = None, log: bool = True) -> str:
        sid = self._next_id("s")
        self.store.put("scheduled", {"world_id": self.id, "id": sid, "t": self.t + float(after), "kind": kind,
                                     "entity_id": entity, "payload": payload or {}, "every": every})
        if log:
            self.emit("scheduled", actor=None, target=entity, reach=0, caused_by=caused_by,
                      payload={"id": sid, "kind": kind, "at": self.t + float(after)})
        return sid

    def pending(self) -> list[dict[str, Any]]:
        return self.store.query("scheduled", "world_id=?", (self.id,), order="t, id")

    def unschedule(self, sid: str, caused_by: int | None = None) -> dict[str, Any]:
        """Cancel a pending timer by id (see pending()); the `tick` of a running clock cannot be cancelled."""
        rows = self.store.query("scheduled", "world_id=? AND id=?", (self.id, sid), limit=1)
        if not rows:
            raise Rejected(f"no timer {sid!r}", hint="timers() lists what is pending")
        item = rows[0]
        if item["kind"] == "tick":
            raise Rejected("the clock's own tick is not a timer", hint="clock(run=false) pauses it")
        self.store.delete("scheduled", self.id, sid)
        self.emit("unscheduled", actor=None, target=item["entity_id"], reach=0, caused_by=caused_by,
                  payload={"id": sid, "kind": item["kind"], "at": item["t"]})
        return item

    def embodied(self, entity_id: str) -> dict[str, Any] | None:
        rows = self.store.query("principal", "world_id=? AND entity_id=?", (self.id, entity_id), limit=1)
        return rows[0] if rows else None

    def step(self, dt: float) -> list[dict[str, Any]]:
        """Advance world time by dt, delivering everything due. Returns public events produced."""
        if dt < 0:
            raise Rejected("dt must be >= 0")
        start_seq = self.store.next_seq(self.id) - 1
        end_t = self.t + float(dt)
        # a paused world with meta `catch_up` replays every beat a long step passes, in order (an 8 h sleep: the night's
        # thirst and timers), up to CATCH_UP_MAX deliveries; a running world, or one without it, skips ahead
        replays = CATCH_UP_MAX if self.meta().get("catch_up") and not self._row["clock_running"] else 0
        while True:
            due = self.store.query("scheduled", "world_id=? AND t<=?", (self.id, end_t), order="t, id", limit=1)
            if not due:
                break
            item = due[0]
            self._row["t"] = max(self.t, float(item["t"]))
            self._save_row()
            self.store.delete("scheduled", self.id, item["id"])
            if item["every"]:
                # A periodic item that fell behind fires once and skips ahead; it never replays a long gap, unless
                # the world catches up (above).
                nxt = float(item["t"]) + float(item["every"])
                if nxt <= end_t:
                    if replays > 0:
                        replays -= 1
                    else:
                        nxt = end_t + float(item["every"])
                item["t"] = nxt
                self.store.put("scheduled", item)
            self._deliver(item)
        self._row["t"] = end_t
        self._save_row()
        evs = self.events(since=start_seq, limit=1000)
        return [_public_event(e) for e in evs if e["kind"] not in _INTERNAL_KINDS]

    def _deliver(self, item: dict[str, Any]) -> None:
        kind, eid, p = item["kind"], item["entity_id"], item["payload"]
        if eid and self.get(eid) is None:
            return
        if kind == "tick":
            if eid is None or (self.embodied(eid) and not p.get("always")
                               and not (self._runs_idle(eid, p["script"]) and self.idle(eid))):
                return  # controller swap: an embodied entity is driven by its principal; `always` behaviors are
                        # the body, not the mind (thirst, bleeding), and run on an embodied seat too; `idle` ones
                        # (a body seeing to its own water) run on a seat that has done nothing for a while
            s = self.script(p["script"])
            if not s.has("tick"):
                return
            # A tick is not an event of the world: nothing is written for it, so a body's thirst does not fill the log
            # (hosted, that was three rows a second). The script sees it as one all the same; its seed comes from the
            # timer and the hour, so the same tick on the same log rolls the same dice.
            seq = self.store.next_seq(self.id)
            ev = {"seq": seq, "t": self.t, "kind": "tick", "actor_id": eid, "target_id": eid,
                  "payload": {"script": p["script"]}, "path": [eid]}
            ctx = Ctx(self, actor=eid, target=None, owner=eid, params=None, event=_event_view(ev), verb=None,
                      caused_by=None, seed=self._seed_for(seq, f"tick:{item['id']}:{self.t}"))
            self.store.begin()
            try:
                ctx.run(s, "tick", [ctx], fuel=50_000)
                self.store.commit()
            except (ScriptError, Rejected) as e:
                self.store.rollback()
                self.emit("script_error", actor=eid, target=eid, reach=0,
                          payload={"script": p["script"], "fn": "tick", "reason": getattr(e, "reason", str(e))})
            return
        if kind == "finish":
            s = self.script(p["script"])
            ev = self.emit("finished", actor=p.get("actor"), target=eid, reach=1,
                           payload={"verb": p.get("verb"), "target": p.get("target")})
            ctx = Ctx(self, actor=p.get("actor"), target=p.get("target"), owner=eid, params=p.get("params"),
                      event=_event_view(ev), verb=p.get("verb"), caused_by=ev["seq"],
                      seed=self._seed_for(ev["seq"], "finish"))
            ctx._consent = True
            self.store.begin()
            try:
                ctx.run(s, "finish", [ctx], fuel=50_000)
                self.store.commit()
            except (ScriptError, Rejected) as e:
                self.store.rollback()
                self.emit("script_error", actor=eid, target=eid, reach=0,
                          payload={"script": p["script"], "fn": "finish", "reason": getattr(e, "reason", str(e))})
            return
        if kind == "introduce":  # introduce(after=...): what was announced lands now
            self.land(p["spec"])
            return
        if kind == "patrol":  # a mind's patrol: one step of its body's loop, written to no log but the walking
            self._patrol_step(eid, p)
            return
        # Any other scheduled kind is just an event that fires later (listeners may react).
        self.emit(kind, actor=p.get("actor"), target=eid, reach=int(p.get("reach", 1)), payload=p)

    def set_clock(self, running: bool | None = None, rate: float | None = None) -> dict[str, Any]:
        if running is not None:
            self._row["clock_running"] = 1 if running else 0
        if rate is not None:
            if rate <= 0:
                raise Rejected("rate must be > 0", hint="use running=False to pause")
            self._row["clock_rate"] = float(rate)
        self._save_row()
        return self.clock()

    def clock(self) -> dict[str, Any]:
        return {"t": self.t, "running": bool(self._row["clock_running"]), "rate": float(self._row["clock_rate"]),
                "pending": self.store.count("scheduled", "world_id=?", (self.id,))}

    def say(self, who: str, text: str, reach: int = 1, to: str | None = None,
            caused_by: int | None = None, mark: dict[str, Any] | None = None, low: bool = False,
            loud: bool = False) -> dict[str, Any]:
        """Speech. Addressed speech targets the listener so it shows in both their logs; the room still hears it.
        Unaddressed speech targets the room the speaker stands in (reach counts from there), never the speaker.
        A `low` line stays in the place (reach 1 at most): those in `near` (low_near) hear the words, everyone else
        there hears that something was said low, and to whom. Where the place or world sets a voice_radius, those in
        `far` (out_of_earshot) hear that something was said, not the words; a `loud` line (or reach past 1) is a shout
        and carries the shout's radius."""
        e = self.need(who)
        payload: dict[str, Any] = {"text": str(text), "tone": tone(str(text), reach), **(mark or {})}
        if to:
            self.need(to)
        if low:
            reach = min(reach, 1)
            payload.update(low=True, tone="low", near=self.low_near(who, to))
        elif reach >= 1:
            if loud:
                payload.update(loud=True, tone="shout")
            if far := self.out_of_earshot(who, to, loud or reach > 1):
                payload["far"] = far
        if to:
            payload["to"] = to
            target = to
        elif e["parent_id"]:
            target = e["parent_id"]
            reach = reach - 1 if reach > 0 else reach
        else:
            target = who
        ev = self.emit("say", actor=who, target=target, reach=reach, payload=payload, caused_by=caused_by)
        if to and to != who:
            self._answer_away(to, who, ev["seq"], text)
        return ev

    def low_radius(self) -> float:
        """Metres within which a low line is heard in full (world meta `low_radius`)."""
        return float(self._row["meta"].get("low_radius", 3.0))

    def voice_radius(self, place: str | None, loud: bool = False) -> float | None:
        """Metres a line carries in a place, by the speaker's and the listener's own spots: the place's
        `voice_radius` (`shout_radius` for a shout) over the world meta's, and a shout with no radius of its own
        carries four times the voice. None when neither sets a voice: a line is heard across the whole place."""
        st = ((self.get(place) or {}).get("state") or {}) if place else {}
        meta = self._row["meta"]
        voice = st.get("voice_radius", meta.get("voice_radius"))
        if voice is None:
            return None
        if not loud:
            return float(voice)
        shout = st.get("shout_radius", meta.get("shout_radius"))
        return float(shout) if shout is not None else 4 * float(voice)

    def out_of_earshot(self, who: str, to: str | None = None, loud: bool = False) -> list[str]:
        """Who in the speaker's place stands too far off to catch the words (voice_radius): those whose own spot is
        further than the radius from the speaker's. The one it is to and what the speaker holds always hear, and so
        does anyone with no spot, and everyone where neither the place nor the world sets a voice."""
        from . import positions as posn
        e = self.need(who)
        if not e["parent_id"] or (r := self.voice_radius(e["parent_id"], loud)) is None:
            return []
        return sorted(c["id"] for c in self.children(e["parent_id"])
                      if c["id"] not in (who, to) and (d := posn.apart(self, who, c["id"])) is not None and d > r)

    def low_near(self, who: str, to: str | None = None) -> list[str]:
        """Who hears a low line in full: the speaker, the one it is said to, what the speaker holds, and anyone in
        the same place within low_radius of the speaker, both by their own spots. In a place with no spots only the
        one it is to hears it."""
        from . import positions as posn
        e = self.need(who)
        out = {who, *([to] if to else []), *(c["id"] for c in self.children(who))}
        if e["parent_id"]:
            r = self.low_radius()
            for c in self.children(e["parent_id"]):
                if c["id"] not in out and (d := posn.apart(self, who, c["id"])) is not None and d <= r:
                    out.add(c["id"])
        return sorted(out)

    def _answer_away(self, body: str, asker: str, caused_by: int, text: str = "") -> None:
        """A body whose seat is idle answers whoever speaks to it with its standing `answer`, once per asker per
        ten world minutes, so two idle bodies never talk each other round. The answer is said to the asker alone
        (reach 0: it may say where the player went), and rests once the seat is back from idle (idle_orders
        `rests`, until away() sets it again)."""
        e = self.get(body)
        st = (e or {}).get("state", {})
        line = None if (st.get("idle_orders") or {}).get("rests") else (st.get("standing_orders") or {}).get("answer")
        own = self._own_line(e, text) if self.own_lines(body) else None
        line = own or line
        if not line or not self.embodied(body) or not (own or self.idle(body)) or self.present(body):
            return
        last = self._answered.get((body, asker))
        if last is not None and self.t - last < 600:
            return
        self._answered[(body, asker)] = self.t
        self.emit("say", actor=body, target=asker, reach=0 if line != own else 1, caused_by=caused_by,
                  payload={"text": str(line), "to": asker, "away": True})

    # ---- principals -----------------------------------------------------------

    def join(self, principal_id: str, entity_id: str, kind: str = "agent", name: str = "",
             capabilities: list[str] | None = None, role: str | None = None, grant_id: str | None = None,
             now: float | None = None) -> dict[str, Any]:
        self.need(entity_id)
        other = self.embodied(entity_id)
        if other and other["id"] != principal_id:
            why = self.lapse_cause(other, now)
            if why:
                self.leave(other["id"], **why)  # an invitee who went quiet: the seat is free again, the body ran on behaviors
            else:
                raise Rejected(f"{entity_id} is already embodied by {other['id']}",
                               hint="pick another entity, or spawn one with author capability")
        old = self.store.get("principal", self.id, principal_id)
        ecur = self.entity_cursor(entity_id)
        row = {"world_id": self.id, "id": principal_id, "kind": kind, "name": name or principal_id,
               "capabilities": capabilities if capabilities is not None else (old["capabilities"] if old else []),
               "entity_id": entity_id,
               "cursor_seq": ecur if ecur is not None else (old["cursor_seq"] if old else self.store.next_seq(self.id) - 1),
               "role": role or (old.get("role") if old else None), "grant_id": grant_id or (old.get("grant_id") if old else None),
               "last_seen": now, "acted_t": self.t}
        self.store.put("principal", row)
        self.emit("embodied", actor=entity_id, target=entity_id, reach=1,
                  payload={"principal": principal_id, "as": kind})
        return row

    def leave(self, principal_id: str, cause: str = "left", **why: Any) -> None:
        """The principal gives its seat back. `released` names the cause: left (its own leave), host (evicted),
        revoked (its grant was), grant_ended (every grant it may sit on ran out), quiet (silent past the lapse, with
        `quiet_s` real seconds and `asleep` when its body slept), so a player and the chronicle can tell them apart."""
        p = self.store.get("principal", self.id, principal_id)
        if p is None:
            return
        self.store.delete("principal", self.id, principal_id)
        if p["entity_id"]:
            self.emit("released", actor=p["entity_id"], target=p["entity_id"], reach=1,
                      payload={"principal": principal_id, "cause": cause, **why})

    def principal(self, principal_id: str) -> dict[str, Any] | None:
        return self.store.get("principal", self.id, principal_id)

    def claim_lapse(self) -> float:
        """Real seconds of silence after which an invited principal's seat is released (world meta `claim_lapse`)."""
        return float(self._row["meta"].get("claim_lapse", 900.0))

    def sleep_lapse(self) -> float:
        """Real seconds of silence a seat keeps while its body is asleep (sleep, or away(sleep=true)): world meta
        `sleep_lapse`, twelve hours by default and never less than claim_lapse. A player who sleeps their character
        overnight finds the seat theirs in the morning."""
        return max(self.claim_lapse(), float(self._row["meta"].get("sleep_lapse", 43200.0)))

    def offer_seat(self, entity_id: str, body_id: str, why: str = "", actor: str | None = None,
                   caused_by: int | None = None) -> dict[str, Any]:
        """Record a seat offer for `entity_id` to whoever holds `body_id` (ctx.offer_seat), and tell that body. Out of
        world state: the offer is a row beside the grants, and claim_seat mints the grant."""
        root = self.get(self.root_id) or {"state": {}}
        if root["state"].get("seat_offers") is False:
            raise Rejected("this world offers no seats (its root says seat_offers: false)")
        e, body = self.need(entity_id), self.need(body_id)
        if not self.is_a(body["type"], "creature"):
            raise Rejected(f"a seat is offered to a body, and {body['name'] or body_id} is a {body['type']}")
        if self.is_a(e["type"], "place") or not e["state"].get("seatable", self.schema_defaults(e["type"]).get("seatable")):
            raise Rejected(f"{e['name'] or entity_id} is not seatable",
                           hint="mark it seatable: true (its state or its schema) when the world may hand it out")
        held = self.embodied(entity_id)
        if held is not None and held["id"] != body_id:
            raise Rejected(f"{e['name'] or entity_id} is already held by {held['id']}")
        for o in self.store.query("seat_offer", "world_id=? AND entity_id=? AND status IN ('open', 'claimed')",
                                  (self.id, entity_id)):
            if o["body_id"] == body_id and o["status"] == "open":
                return o  # the same offer stands
            raise Rejected(f"{e['name'] or entity_id} is already offered to or held by someone else ({o['id']})",
                           hint="withdraw_seat(entity) first")
        # named for the event that announces it, the next in the log, so two offers never share an id
        o = {"world_id": self.id, "id": f"s{self.store.next_seq(self.id)}", "entity_id": entity_id, "body_id": body_id,
             "why": why, "created": self.t, "status": "open", "grant_id": None, "claimed": None}
        self.store.put("seat_offer", o)
        # `seat`, not `entity`: an offer of a hidden body must still reach the one it is offered to
        self.emit("seat_offered", actor=actor, target=body_id, reach=0, caused_by=caused_by,
                  payload={"offer": o["id"], "seat": entity_id, "name": e["name"], "why": why,
                           "hint": "seats() lists it; claim_seat(offer) gives you a paste to play it in a session of its own"})
        return o

    def move_seat(self, from_id: str, to_id: str, notes: bool = True, actor: str | None = None,
                  caused_by: int | None = None) -> str:
        """The seat holding `from_id` moves to `to_id` (ctx.move_seat): one principal row changes body, its grant and
        any claimed seat offer follow it, its feed starts fresh at the move, and `released` then `embodied` tell the
        log. Returns the principal."""
        if from_id == to_id:
            raise Rejected("a seat moves to another body")
        src, dst = self.need(from_id), self.need(to_id)
        p = self.embodied(from_id)
        if p is None:
            raise Rejected(f"nobody holds {src['name'] or from_id}", hint="ctx.embodied(body) says whether someone does")
        if self.is_a(dst["type"], "place") or not dst["state"].get("seatable", self.schema_defaults(dst["type"]).get("seatable")):
            raise Rejected(f"{dst['name'] or to_id} is not seatable",
                           hint="mark it seatable: true (its state or its schema) when the world may put a mind in it")
        if dst["state"].get("dead"):
            raise Rejected(f"{dst['name'] or to_id} is dead")
        if self.embodied(to_id) is not None:
            raise Rejected(f"{dst['name'] or to_id} is already held", hint="a seat moves only into a body nobody holds")
        if notes and src["state"].get("memory"):  # the notes are the mind's: they go where it goes
            dst["state"]["memory"] = sorted(list(dst["state"].get("memory") or []) + list(src["state"].pop("memory")),
                                            key=lambda n: n.get("seq", 0))
            self._touch(src)
            self._touch(dst)
        self.store.set("principal", self.id, p["id"], entity_id=to_id, acted_t=self.t,
                       cursor_seq=self.store.next_seq(self.id) - 1)
        g = self.store.get("grants", self.id, p["grant_id"]) if p.get("grant_id") else None
        if g is not None:
            swap = lambda x: to_id if x == from_id else x
            self.store.set("grants", self.id, g["id"], entity_id=swap(g.get("entity_id")), made=swap(g.get("made")),
                           scope=[swap(x) for x in (g.get("scope") or [])])
            for o in self.store.query("seat_offer", "world_id=? AND grant_id=? AND status='claimed'", (self.id, g["id"])):
                self.store.set("seat_offer", self.id, o["id"], entity_id=swap(o["entity_id"]))
        self.emit("released", actor=from_id, target=from_id, reach=1, caused_by=caused_by,
                  payload={"principal": p["id"], "cause": "moved", "to": to_id})
        self.emit("embodied", actor=to_id, target=to_id, reach=1, caused_by=caused_by,
                  payload={"principal": p["id"], "as": p["kind"], "from": from_id})
        return p["id"]

    def withdraw_seat(self, entity_id: str, why: str = "", actor: str | None = None,
                      caused_by: int | None = None) -> list[str]:
        """Close every live offer of this entity; a claimed one's grant is revoked with its children."""
        out: list[str] = []
        for o in self.store.query("seat_offer", "world_id=? AND entity_id=? AND status IN ('open', 'claimed')",
                                  (self.id, entity_id)):
            if o["status"] == "claimed" and o.get("grant_id"):
                out += self.revoke_grant(o["grant_id"])
            self.store.set("seat_offer", self.id, o["id"], status="withdrawn")
            self.emit("seat_withdrawn", actor=actor, target=o["body_id"], reach=0, caused_by=caused_by,
                      payload={"offer": o["id"], "seat": entity_id, "why": why})
        return out

    def revoke_grant(self, grant_id: str) -> list[str]:
        """Revoke a grant and every grant minted from it (a seat claimed in the world): their principals leave."""
        g = self.store.get("grants", self.id, grant_id)
        if g is None:
            return []
        out = [grant_id]
        if not g.get("revoked"):
            self.store.set("grants", self.id, grant_id, revoked=1)
        self.leave(g["principal_id"], "revoked")
        for c in self.store.query("grants", "world_id=? AND parent_id=? AND revoked=0", (self.id, grant_id)):
            out += self.revoke_grant(c["id"])
        for o in self.store.query("seat_offer", "world_id=? AND grant_id=? AND status='claimed'", (self.id, grant_id)):
            self.store.set("seat_offer", self.id, o["id"], status="withdrawn")
        return out

    def lapsed(self, p: dict[str, Any], now: float | None) -> bool:
        """Only principals that came in on a grant lapse; the owner at the keyboard never loses a seat to silence."""
        return self.lapse_cause(p, now) is not None

    def lapse_cause(self, p: dict[str, Any], now: float | None) -> dict[str, Any] | None:
        """Why a seat is no longer its principal's (the `released` payload's cause), or None while it holds."""
        if now is None or not p.get("grant_id"):
            return None
        def live(g: dict[str, Any] | None) -> bool:
            return g is not None and not g.get("revoked") and (g.get("expires") is None or float(g["expires"]) > now)
        if not live(self.store.get("grants", self.id, p["grant_id"])) and not any(
                live(g) for g in self.store.query("grants", "world_id=? AND principal_id=? AND revoked=0", (self.id, p["id"]))):
            return {"cause": "grant_ended"}  # the seat is not its to keep (a guest back on a new grant)
        if p.get("last_seen") is None:
            return None
        quiet = now - float(p["last_seen"])
        body = self.get(p["entity_id"]) if p.get("entity_id") else None
        asleep = bool(body and body["state"].get("asleep"))
        if quiet <= (self.sleep_lapse() if asleep else self.claim_lapse()):
            return None
        return {"cause": "quiet", "quiet_s": round(quiet), **({"asleep": True} if asleep else {})}

    def touch(self, principal_id: str, now: float, acted: bool = False) -> None:
        """A sign of life keeps the seat (`last_seen`, real time); a deed (`acted`: an act, a line said) also marks
        the seat in use (`acted_t`, world time, see idle())."""
        p = self.store.get("principal", self.id, principal_id)
        if p and (acted or p.get("last_seen") is None or now - float(p["last_seen"]) >= 5.0):
            p["last_seen"] = now
            if acted:
                p["acted_t"] = self.t
            self.store.put("principal", p)

    # ---- a mind's idle orders: its body's patrol and its own lines -----------------------------------------------

    def own_lines(self, entity_id: str) -> bool:
        """An embodied body whose mind left its own dialog lines (away(dialog=...)) and has done nothing since, or
        whose seat is idle: it answers talk from its tables as an unheld body does, its lines over the author's."""
        e = self.get(entity_id)
        orders = (e or {}).get("state", {}).get("idle_orders") or {}
        return bool(orders.get("dialog") and (orders.get("fresh") or self.idle(entity_id))
                    and not self.present(entity_id))

    def mark_present(self, principal_id: str, until: float | None) -> None:
        """A seat waiting in the scene (wait(present=true)) until real time `until`; None: not, its lines may answer."""
        if until is None:
            self._present.pop(principal_id, None)
        else:
            self._present[principal_id] = until

    def present(self, entity_id: str) -> bool:
        """Its seat is waiting in the scene (wait(present=true), PL-04a): its body's own lines and standing answer
        stay quiet, as do the author's lines that give way to a mind. Its idle behaviors run as before."""
        p = self.embodied(entity_id)
        return bool(p and self._present.get(p["id"], 0.0) > self.wall())

    @staticmethod
    def _own_line(e: dict[str, Any] | None, text: Any) -> str | None:
        """The mind's own line for words said to its body: the key ("ferry|crossing") with the most of its aliases
        among the words, longer aliases first, as the village table picks."""
        table = (((e or {}).get("state") or {}).get("idle_orders") or {}).get("dialog") or {}
        clean = "".join(c if c.isalnum() else " " for c in str(text or "").lower())
        words = " " + " ".join(clean.split()) + " "
        best, best_s = None, 0
        for key in table:
            s = sum(10 + len(a.strip()) for a in str(key).lower().split("|") if a.strip() and f" {a.strip()} " in words)
            if s > best_s:
                best, best_s = key, s
        return str(table[best]) if best is not None else None

    def patrol_ways(self, body: str, stops: list[str]) -> bool:
        """Whether a patrol's stops are each one known way from the next; True when the last leads back to the first
        (a loop), False when the body walks back the way it came. Raises naming the first missing link."""
        def way(a: str, b: str) -> bool:
            return any(e["target"] == b for e in self.edges(a, "connects_to", "out")) and self.knows_way(body, b)
        for a, b in zip(stops, stops[1:]):
            if not way(a, b):
                raise Rejected(f"no way from {self.need(a)['name']} to {self.need(b)['name']} that this body knows: "
                               f"patrol stops go one way apart", hint="add the place between them as a stop")
        return len(stops) > 2 and way(stops[-1], stops[0])

    def _patrol_step(self, eid: str, p: dict[str, Any]) -> None:
        """Walk the body one step of its patrol by its own `go`, so a lock, a squall or a cooldown stops it as it
        would stop anyone; then the next step after the dwell. A refused step is tried again at the next."""
        e = self.need(eid)
        pat = (e["state"].get("idle_orders") or {}).get("patrol")
        if not pat or pat.get("id") != p.get("id"):
            return  # cleared, or a newer patrol: this timer is stale
        stops = [s for s in pat["stops"] if self.get(s)]
        if len(stops) != len(pat["stops"]):
            return
        i, d, here = int(p.get("i") or 0), int(p.get("dir") or 1), e["parent_id"]
        if here in stops and stops[i] != here:
            i = stops.index(here)  # carried or pushed onto another stop: go on from there
        if stops[i] == here:
            if pat.get("loop"):
                i = (i + 1) % len(stops)
            else:
                if not 0 <= i + d < len(stops):
                    d = -d
                i = i + d
            try:
                self.act(eid, "go", stops[i])
            except Rejected:
                pass
        else:
            near = [s for s in stops if any(x["target"] == s for x in self.edges(here, "connects_to", "out"))] if here else []
            if near:  # off the route: back onto the nearest stop
                i = stops.index(near[0])
                try:
                    self.act(eid, "go", stops[i])
                except Rejected:
                    pass
        self.schedule(float(pat["dwell"]), "patrol", eid, {"id": pat["id"], "i": i, "dir": d}, log=False)

    def idle_after(self) -> float:
        """World seconds after a seat's last deed when its body counts as idle (world meta `idle_after`, default 900)."""
        return float(self._row["meta"].get("idle_after", 900.0))

    def idle(self, entity_id: str) -> bool:
        """A body nobody embodies, or whose seat has done nothing (no act, no line) for idle_after world seconds: a
        mind on a watcher, a player gone to bed. The world goes on; the body's `idle` behaviors (drinking when
        thirsty, see packs/d20 quench) run on it as on a body nobody holds, so a seat kept overnight is not a body
        left to dry. Reading, waiting and watching keep the seat; they are not deeds."""
        p = self.embodied(entity_id)
        if p is None:
            return True
        at = p.get("acted_t")
        return at is None or self.t - float(at) > self.idle_after()

    def _runs_idle(self, entity_id: str, script: str) -> bool:
        e = self.get(entity_id)
        return bool(e) and any(b.get("script") == script and b.get("idle")
                               for b in self.schema_components(e["type"], "behaviors"))

    def release_lapsed(self, now: float) -> list[str]:
        """Seats whose invitee went quiet past the lapse: released, so their bodies run on behaviors again."""
        out = []
        for p in self.principals():
            why = self.lapse_cause(p, now) if p.get("entity_id") else None
            if why:
                self.leave(p["id"], **why)
                out.append(p["id"])
        return out

    def principals(self) -> list[dict[str, Any]]:
        return self.store.query("principal", "world_id=?", (self.id,), order="id")

    def _bump_cursor(self, principal_id: str, seq: int | None = None) -> None:
        """Past what this seat just did (up to `seq`, else everything so far), so its next read starts after it."""
        p = self.store.get("principal", self.id, principal_id)
        if p:
            last = self.store.next_seq(self.id) - 1
            p["cursor_seq"] = last if seq is None else max(int(p.get("cursor_seq") or 0), seq)
            self.store.put("principal", p)

    def set_cursor(self, principal_id: str, seq: int) -> None:
        p = self.store.get("principal", self.id, principal_id)
        if p:
            p["cursor_seq"] = seq
            self.store.put("principal", p)
            if p.get("entity_id"):
                self.set_entity_cursor(p["entity_id"], seq)

    def entity_cursor(self, entity_id: str) -> int | None:
        """Where this entity last looked. Its own, whoever is driving it."""
        v = self._row["meta"].get("cursors", {}).get(entity_id)
        return int(v) if v is not None else None

    def set_entity_cursor(self, entity_id: str, seq: int) -> None:
        self._row["meta"].setdefault("cursors", {})[entity_id] = int(seq)
        self._save_row()

    def meta(self) -> dict[str, Any]:
        return dict(self._row["meta"])

    def declared(self, key: str) -> Any:
        """What this world's packs declare under `key` (PACK_DECLARES), merged: {condition: text} for WAYS_OUT, else
        a set of names."""
        decl = [d for d in (self._row["meta"].get("pack_declares") or {}).values() if isinstance(d, dict)]
        if key == "WAYS_OUT":
            return {str(k): str(v) for d in decl for k, v in (d.get(key) or {}).items()}
        return {str(x) for d in decl for x in (d.get(key) or [])}

    def set_meta(self, changes: dict[str, Any]) -> dict[str, Any]:
        for k, v in changes.items():
            if v is None:
                self._row["meta"].pop(k, None)
            else:
                self._row["meta"][k] = v
        self._save_row()
        return self.meta()

    # ---- minds -------------------------------------------------------------------

    def intend(self, entity_id: str, text: str | None = None, why: str | None = None, id: str | None = None,
               status: str | None = None, priority: int | None = None, actor: str | None = None) -> dict[str, Any]:
        """Add or change one goal in the entity's secret `goals` list. A goal is {id, text, why, status, priority,
        t}. status: active (default), done, dropped. Returns the goal as it stands."""
        e = self.need(entity_id)
        goals = [dict(g) for g in (e["state"].get("goals") or [])]
        g = next((x for x in goals if x.get("id") == id), None) if id else None
        if g is None:
            if not text:
                raise Rejected("a new goal needs text" if not id else f"no goal {id!r}",
                               hint="intend(text='cross the river tonight', why='...') adds one; perceive lists yours")
            n = 1 + max([int(str(x.get("id", "g0"))[1:] or 0) for x in goals
                         if str(x.get("id", "")).startswith("g") and str(x.get("id", ""))[1:].isdigit()] or [0])
            g = {"id": id or f"g{n}", "text": str(text), "why": str(why) if why else None, "status": "active",
                 "priority": int(priority) if priority is not None else 1, "t": self.t}
            goals.append(g)
        else:
            if text is not None:
                g["text"] = str(text)
            if why is not None:
                g["why"] = str(why)
            if priority is not None:
                g["priority"] = int(priority)
        if status is not None:
            if status not in ("active", "done", "dropped"):
                raise Rejected(f"unknown goal status {status!r}", hint="active, done or dropped")
            g["status"] = status
            g["status_t"] = self.t
        e["state"]["goals"] = goals
        self._touch(e)
        self.emit("intended", actor=actor or entity_id, target=entity_id, reach=0,
                  payload={"goal": g["id"], "text": g["text"], "status": g["status"]})
        return g

    def land(self, spec: dict[str, Any], actor: str | None = None) -> str | None:
        """The arrival half of `introduce`: spawn with provenance, the `knows` links of a person, its own memories and
        the scene the room sees. The knowers' notes are written by the caller (at once, or when it was announced).
        A place or knower gone by the time it lands is skipped; returns the new id, or None when the place is gone."""
        where = spec["parent"]
        if self.get(where) is None:
            return None
        st = dict(spec.get("state") or {})
        st["provenance"] = {"how": spec["how"], "by": spec.get("by"), "t": self.t}
        eid = self.spawn(spec["type"], where, name=spec.get("name") or "", state=st, pos=spec.get("pos"), actor=actor,
                         announce=spec["how"] != "always_there")
        if self.is_a(spec["type"], "person"):
            for k, note in (spec.get("known_by") or {}).items():
                if k != eid and self.get(k) is not None:
                    self.link(k, eid, "knows", {"standing": 0, "note": note, "met_t": self.t, "count": 0})
        for note in spec.get("remembers") or []:
            self.remember(eid, str(note), actor=eid)
        if spec.get("scene"):
            self.emit("scene", target=where, reach=1, payload={"text": spec["scene"], "introduced": eid, "how": spec["how"]})
        return eid

    def remember(self, entity_id: str, text: str, actor: str | None = None) -> dict[str, Any]:
        """Append to the entity's secret memory. Whoever embodies it next reads the same notes."""
        e = self.need(entity_id)
        note = {"t": self.t, "seq": self.store.next_seq(self.id), "text": str(text)}
        mem = list(e["state"].get("memory") or [])
        mem.append(note)
        e["state"]["memory"] = mem
        self._touch(e)
        self.emit("remembered", actor=actor or entity_id, target=entity_id, reach=0, payload={"text": str(text)})
        return note

    def exchanges(self, a: str, b: str, limit: int = 5, before: int | None = None) -> list[dict[str, Any]]:
        """The last spoken exchanges between two entities, from the log. Newest last. `before`: only events with a
        sequence number below it (the page before a cursor)."""
        cut = " AND seq<?" if before is not None else ""
        extra = (int(before),) if before is not None else ()
        rows = [r for x, y in ((a, b), (b, a))  # one indexed read a side: an OR over both reads the whole log
                for r in self.store.query("event", "world_id=? AND actor_id=? AND kind IN ('say','talked') AND target_id=?" + cut,
                                          (self.id, x, y) + extra, order="seq DESC", limit=limit)]
        rows = sorted(rows, key=lambda r: r["seq"])[-limit:] if limit else []
        return [_public_event(r) for r in rows]

    def known_places(self, entity_id: str) -> list[str]:
        """Places this entity has arrived at, from its own moved events, plus where it stands."""
        rows = self.store.query("event", "world_id=? AND kind='moved' AND target_id=?", (self.id, entity_id),
                                order="seq")
        out: list[str] = []
        for r in rows:
            to = r["payload"].get("to")
            if to and to not in out and self.get(to):
                out.append(to)
        e = self.get(entity_id)
        if e and e["parent_id"] and e["parent_id"] not in out:
            out.append(e["parent_id"])
        return out

    _OPINION = {"given": 2, "hit": -3, "attacked": -3, "talked": 0, "say": 0}

    def _opinion_floor(self, ev: dict[str, Any]) -> None:
        """A deterministic floor under relationships: meeting makes a `knows` edge both ways, gifts and blows
        move `standing` on the receiver's side. A mind refines the edge data; the engine never speaks."""
        kind = ev["kind"]
        actor, target = ev["actor_id"], ev["target_id"]
        if kind == "say":
            target = ev["payload"].get("to")
        if not actor or not target or actor == target:
            return
        a, b = self.get(actor), self.get(target)
        if not a or not b or not self.is_a(a["type"], "creature") or not self.is_a(b["type"], "creature"):
            return
        delta = self._OPINION[kind]
        moved: list[dict[str, Any]] = []
        for src, dst, d in ((target, actor, delta), (actor, target, 0)):
            ex = next((x for x in self.edges(src, "knows", "out") if x["target"] == dst), None)
            if ex is None:
                ex = {"world_id": self.id, "id": self._next_id("g"), "source": src, "target": dst, "relation": "knows",
                      "data": {"standing": 0, "met_t": self.t, "count": 0}}
            data = dict(ex["data"])
            data["standing"] = int(data.get("standing", 0)) + d
            data["count"] = int(data.get("count", 0)) + 1
            data["last_t"] = self.t
            data["last_kind"] = kind
            ex["data"] = data
            self.store.put("edge", ex)
            moved.append({"holder": src, "of": dst, "delta": d, "standing": data["standing"]})
        # holder: whose opinion moved; of: about whom. The receiver's view of the actor is the one that changes.
        self.emit("opinion", actor=actor, target=target, reach=0, caused_by=ev["seq"],
                  payload={"kind": kind, "delta": delta, "edges": moved})

    # ---- integrity -------------------------------------------------------------

    def state_hash(self) -> str:
        """Hash of all projected state. Equal hashes after equal action sequences = determinism."""
        h = hashlib.sha256()
        for table in ("entity", "edge", "hyperedge", "scheduled"):
            for row in self.store.query(table, "world_id=?", (self.id,), order="id"):
                # world_id left out so a fork hashes equal to its source
                row = {k: v for k, v in row.items() if k not in ("created_seq", "updated_seq", "world_id")}
                h.update(json.dumps(row, sort_keys=True, default=str).encode())
        h.update(f"{self.t}".encode())
        return h.hexdigest()

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "root": self.root_id, "t": self.t,
            "description": self._row["meta"].get("description", ""),
            "entities": self.store.count("entity", "world_id=?", (self.id,)),
            "edges": self.store.count("edge", "world_id=?", (self.id,)),
            "events": self.store.count("event", "world_id=?", (self.id,)),
            "schemas": self.store.count("schema", "world_id=?", (self.id,)),
            "principals": [{"id": p["id"], "kind": p["kind"], "role": p.get("role"), "entity": p["entity_id"]}
                           for p in self.principals()],
            "clock": self.clock(),
        }


# Who last handed a thing over: a stack joins a like one whatever these say, and the newest hand-over wins.
_HANDOVER = ("given_by", "given_before_by")


def _units(e: dict[str, Any]) -> int:
    c = e["state"].get("count")
    return 1 if c is None else int(c)


def _stack_key(e: dict[str, Any]) -> tuple[str, str, str]:
    st = {k: v for k, v in e["state"].items() if k != "count" and k not in _HANDOVER and v is not None}
    return e["type"], (e["name"] or "").lower(), json.dumps(st, sort_keys=True, default=str)


def _bulk(e: dict[str, Any]) -> float:
    """What a thing weighs in a body's hands (village `carry`): its `bulk` a unit (fractions allowed), else 2 for
    anything with a `capacity` (a skin), else 1; times its count."""
    st = e["state"]
    b = st.get("bulk")
    each = float(b) if b is not None else (2.0 if st.get("capacity") else 1.0)
    return _num(each * _units(e))


def _num(x: float) -> float | int:
    x = round(float(x), 3)
    return int(x) if x == int(x) else x


# Kinds that never wake a sleeper: the deed's own envelope (its verb's events decide) and sleep itself.
_NO_WAKE = frozenset({"act", "slept", "woke"})
_WORD_KINDS = frozenset({"say", "talked"})


def tone(text: str, reach: int = 1) -> str:
    """How a line sounds to one who hears no words: a whisper (reach 0), a shout (reach past 1, all capitals, or
    "!"), sharp (three words or fewer ending in ? or !), else calm."""
    t = text.strip()
    if reach <= 0:
        return "whisper"
    letters = [c for c in t if c.isalpha()]
    if reach > 1 or (len(letters) > 1 and all(c.isupper() for c in letters)) or ("!" in t and len(t.split()) > 3):
        return "shout"
    if len(t.split()) <= 3 and t[-1:] in "?!" and t:
        return "sharp"
    return "calm"


def _loud(ev: dict[str, Any]) -> bool:
    """Heard through sleep: an event that says it is `loud`, or one that carries two levels up or more."""
    return bool((ev.get("payload") or {}).get("loud")) or int(ev.get("reach") or 0) >= 2


# Events that exist for the log, not for listeners.
_SILENT_KINDS = frozenset({"before_act", "schema_defined", "script_defined", "scheduled", "patched", "linked", "unlinked",
                           "related", "unrelated", "spawned", "destroyed", "left", "moved", "embodied", "released", "regrouped",
                           "tick", "script_error", "finished", "opinion", "remembered", "intended", "merged", "act_refused"})
# Events only the entity they target (its mind) and authors ever see.
_PRIVATE_KINDS = frozenset({"remembered", "intended", "act_refused"})
# Events only the hosts (owner, author, observers) see, not even the body they are about: an act the world refused.
_HOST_KINDS = frozenset({"act_refused", "regrouped"})
# State keys no other body reads, whatever the entity's own `secret` list says.
ALWAYS_SECRET = frozenset({"memory", "brief", "goals", "policy", "cooldowns", "idle_orders"})
# A strike's cooldown in real seconds, when the meta's `strike_cooldown` does not say: `held` when a player or a mind
# holds either side (an agent's time to read the fight and decide), `free` between bodies nobody holds.
STRIKE_COOLDOWN = {"held": 60.0, "free": 15.0}
# Events hidden from the public stream (perceive, act results). Primitive mutations stay in the log.
_INTERNAL_KINDS = frozenset({"before_act", "schema_defined", "script_defined", "scheduled", "unscheduled", "tick"})


class EventView(ScriptObject):
    _script_attrs = ("seq", "t", "kind", "actor", "target", "payload", "path")

    def __init__(self, ev: dict[str, Any]):
        self.seq = ev["seq"]
        self.t = ev["t"]
        self.kind = ev["kind"]
        self.actor = ev["actor_id"]
        self.target = ev["target_id"]
        self.payload = dict(ev["payload"])
        self.path = list(ev["path"])


def _order_gives(order: Any, thing: dict[str, Any], to: dict[str, Any]) -> bool:
    """A standing `give` order, {"item": <name or id>, "to": <name, id or "anyone">}, covers this thing for this body."""
    if not isinstance(order, dict):
        return False
    item, whom = str(order.get("item", "")).lower(), str(order.get("to", "anyone")).lower()
    return (item in (thing["id"].lower(), (thing["name"] or "").lower())
            and whom in ("anyone", to["id"].lower(), (to["name"] or "").lower()))


def _event_view(ev: dict[str, Any]) -> EventView:
    return EventView(ev)


def _public_event(e: dict[str, Any]) -> dict[str, Any]:
    return {"seq": e["seq"], "t": e["t"], "kind": e["kind"], "actor": e["actor_id"], "target": e["target_id"],
            "payload": e["payload"], "caused_by": e["caused_by"]}
