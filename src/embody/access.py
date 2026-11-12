"""Access: who may read a thing, change it and use its verbs, the way a file has an owner, a group and a mode.

A thing's `access` state is {owner, group, mode, verbs}. The owner is a principal id or an entity id; the group's
members are listed on the root under `access_groups`; the mode is nine characters, rwx for the owner (u), the group
(g) and everyone else (o), and only the first class that matches counts. `verbs` maps a verb to the classes that may
do it to the thing. A thing with no access works as it always did (docs/ACCESS.md).
"""

from __future__ import annotations

import re
from typing import Any

KEY = "access"
GROUPS = "access_groups"
DEFAULT_MODE = "rwxr-xr-x"
_CLASSES = "ugo"
_BITS = "rwx"
_SYMBOLIC = re.compile(r"([ugoa]*)([+\-=])([rwx]*)")


class AccessError(ValueError):
    pass


def of(ent: dict[str, Any] | None) -> dict[str, Any] | None:
    """The thing's access, or None when it has none."""
    acc = (ent or {}).get("state", {}).get(KEY)
    return acc if isinstance(acc, dict) else None


def members(root: dict[str, Any] | None, group: str | None) -> list[str]:
    if not group:
        return []
    table = (root or {}).get("state", {}).get(GROUPS) or {}
    m = table.get(group) if isinstance(table, dict) else None
    return [str(x) for x in m] if isinstance(m, list) else []


def class_of(acc: dict[str, Any], subjects: set[str], root: dict[str, Any] | None) -> str:
    """u, g or o: the first class the subjects fall in."""
    if acc.get("owner") and str(acc["owner"]) in subjects:
        return "u"
    if subjects & set(members(root, acc.get("group"))):
        return "g"
    return "o"


def mode_of(acc: dict[str, Any]) -> str:
    m = acc.get("mode")
    return m if isinstance(m, str) and len(m) == 9 else DEFAULT_MODE


def allows(acc: dict[str, Any], subjects: set[str], root: dict[str, Any] | None, bit: str) -> bool:
    cls = class_of(acc, subjects, root)
    return mode_of(acc)[_CLASSES.index(cls) * 3 + _BITS.index(bit)] != "-"


def verb_rule(acc: dict[str, Any], verb: str) -> str | None:
    """The classes that may do this verb to the thing, or None when the verb has no rule of its own."""
    v = (acc.get("verbs") or {}).get(verb)
    return v if isinstance(v, str) else None


def may_verb(acc: dict[str, Any], subjects: set[str], root: dict[str, Any] | None, verb: str, own: bool) -> bool:
    """A verb done to the thing: its own rule when it has one, else `x` for the thing's own verbs. A verb from the
    actor (take, attack) with no rule of its own is not the thing's to refuse."""
    rule = verb_rule(acc, verb)
    if rule is not None:
        return class_of(acc, subjects, root) in rule
    return allows(acc, subjects, root, "x") if own else True


def parse_mode(spec: Any, current: str = DEFAULT_MODE) -> str:
    """rwxr-x---, octal 750, or symbolic (g+w, o-rwx, a+x, u=rwx, comma separated) applied to the current mode."""
    s = str(spec).strip()
    if re.fullmatch(r"[0-7]{3}", s):
        return "".join("".join(b if int(d) & (4 >> i) else "-" for i, b in enumerate(_BITS)) for d in s)
    if re.fullmatch(r"([r-][w-][x-]){3}", s):
        return s
    bits = [list(current[i:i + 3]) for i in (0, 3, 6)]
    parts = [p.strip() for p in s.split(",")]
    if not parts or not all(_SYMBOLIC.fullmatch(p) for p in parts):
        raise AccessError(f"no mode {spec!r}")
    for p in parts:
        who, op, what = _SYMBOLIC.fullmatch(p).groups()
        for c in (who or "a").replace("a", "ugo"):
            row = bits[_CLASSES.index(c)]
            for i, b in enumerate(_BITS):
                if op == "=":
                    row[i] = b if b in what else "-"
                elif b in what:
                    row[i] = b if op == "+" else "-"
    return "".join("".join(r) for r in bits)


def parse_classes(spec: Any) -> str:
    """The classes a verb rule names: u, g, o in any mix, a for all three, "" for nobody."""
    s = str(spec).strip().replace("a", "ugo")
    if not re.fullmatch(r"[ugo]*", s):
        raise AccessError(f"a verb rule names classes (u, g, o, a), not {spec!r}")
    return "".join(c for c in _CLASSES if c in s)


def changed(acc: dict[str, Any] | None, *, mode: Any = None, verb: str | None = None, owner: Any = None,
            group: Any = None) -> dict[str, Any]:
    """The access after a chmod or chown."""
    out = dict(acc or {})
    out.setdefault("mode", DEFAULT_MODE)
    if verb is not None:
        verbs = dict(out.get("verbs") or {})
        if mode is None or str(mode).strip() == "default":
            verbs.pop(verb, None)
        else:
            verbs[verb] = parse_classes(mode)
        if verbs:
            out["verbs"] = verbs
        else:
            out.pop("verbs", None)
    elif mode is not None:
        out["mode"] = parse_mode(mode, mode_of(out))
    if owner is not None:
        out["owner"] = str(owner)
    if group == "":
        out.pop("group", None)
    elif group is not None:
        out["group"] = str(group)
    return out


def who_may(acc: dict[str, Any], verb: str, own: bool) -> str:
    """Who a verb is kept for, in words: its owner, the masons, anyone."""
    rule = verb_rule(acc, verb)
    if rule is None:
        m = mode_of(acc)
        rule = "".join(c for i, c in enumerate(_CLASSES) if m[i * 3 + 2] != "-") if own else _CLASSES
    names = {"u": "its owner", "g": f"the {acc.get('group')}" if acc.get("group") else "its group", "o": "anyone"}
    return " and ".join(names[c] for c in rule) or "nobody"


HINT = ("access is {owner, group, mode, verbs}: chmod(entity, 'rwxr-x---' or '750' or 'g+w'), chmod(entity, 'u', "
        "verb='drive'), chown(entity, owner=..., group=...)")
