"""Story threads from one world day's news, for chronicle(day, threads=N): the day ranked by stakes instead of the
clock, so a chronicler reads the two or three stories in it at any event volume (asked by a world host, 2026-11-23).

Each news item weighs by what it is (WEIGHTS; a world sets its own in its meta's `chronicle_weights`), times 2 when a
player's body is in it. Items join one thread when they share a place within 3 hours, a body within 6 hours, or a
cause (one `caused_by` chain). Scenes and speech attach to the thread whose place, people and hours they fall in. A
thread that touches an open arc (the meta's `chronicle_arcs`) weighs 1.5 times. The top threads come back in full and
the rest as one-liners, every list capped, so the reply keeps its size however big the day. Pure: no world access."""

from collections import Counter
from typing import Any

WEIGHTS: dict[str, float] = {
    "death": 14, "died": 14, "killed": 14, "caught": 6, "struck": 4, "destroyed": 8, "downed": 8, "outlawed": 6, "first_visit": 6, "new_place": 4,
    "fight": 4, "rose": 4, "find": 4, "found": 4, "quest": 5, "quest_done": 6, "yielded": 5, "dishonor": 4,
    "stage_done": 4, "works_done": 4, "gift": 3, "trade": 3, "wounded": 2, "standing": 1.5, "new_person": 2,
    "story": 0.5,
}
DEFAULT_WEIGHT = 2.0
PLACE_WINDOW, PERSON_WINDOW = 3 * 3600, 6 * 3600
PLAYER_BOOST, ARC_BOOST = 2.0, 1.5
CAP_NEWS, CAP_SCENES, CAP_SAID, CAP_AROUND, CAP_PEOPLE = 25, 30, 20, 40, 12


def hhmm(t: Any) -> str:
    t = int(t or 0)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}"


def weights_for(meta: dict[str, Any]) -> dict[str, float]:
    """The engine's weights under the world's own (`chronicle_weights` in its meta: {kind: number})."""
    out = dict(WEIGHTS)
    own = meta.get("chronicle_weights")
    if isinstance(own, dict):
        for k, v in own.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[str(k)] = float(v)
    return out


def weigh(n: dict[str, Any], weights: dict[str, float], players: set[str]) -> float:
    w = float(weights.get(n.get("what") or "", weights.get("default", DEFAULT_WEIGHT)))
    if n.get("what") == "fight":
        w += float(n.get("damage") or 0) / 2
    if n.get("what") == "standing":
        w *= max(1.0, abs(float(n.get("delta") or 0)) / 2)
    if set(named(n)) & players:
        w *= PLAYER_BOOST
    return w


def named(n: dict[str, Any]) -> list[str]:
    """The bodies a news item names: who did it and to whom."""
    return [x for x in (n.get("who"), n.get("target")) if isinstance(x, str) and x]


def line(n: dict[str, Any]) -> str:
    bits = [hhmm(n.get("t")), str(n.get("what", "?"))]
    for k in ("who", "target", "place", "name", "faction", "damage", "value", "why"):
        if n.get(k) not in (None, ""):
            bits.append(f"{k}={n[k]}")
    return " ".join(bits)


def threads(news: list[dict[str, Any]], scenes: list[dict[str, Any]], said: list[dict[str, Any]],
            players: set[str], weights: dict[str, float], arcs: list[dict[str, Any]], top: int) -> dict[str, Any]:
    """news: the day's items in time order (who, target, place by name), each with `_cause` (the first event of its
    caused_by chain), already cleared of what was hidden when it happened. scenes and said: rows with t, place and text
    (said: who, to, player). players: the names of player bodies. arcs: the open ones."""
    items = [n for n in news if n.get("what") != "story"]
    parent = list(range(len(items)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(i: int, j: int) -> None:
        a, b = root(i), root(j)
        if a != b:
            parent[a] = b

    # in time order, each item joins the latest earlier one at its place (3 h), with each of its bodies (6 h), and on
    # its cause: the windows chain, so this is the same grouping as comparing every pair, in one pass
    last_place: dict[Any, int] = {}
    last_body: dict[Any, int] = {}
    by_cause: dict[Any, int] = {}
    for i, n in enumerate(items):
        t = n.get("t") or 0
        pl = n.get("place")
        if pl:
            j = last_place.get(pl)
            if j is not None and t - (items[j].get("t") or 0) <= PLACE_WINDOW:
                join(i, j)
            last_place[pl] = i
        for b in named(n):
            j = last_body.get(b)
            if j is not None and t - (items[j].get("t") or 0) <= PERSON_WINDOW:
                join(i, j)
            last_body[b] = i
        c = n.get("_cause")
        if c is not None:
            if c in by_cause:
                join(i, by_cause[c])
            by_cause[c] = i
    groups: dict[int, list[dict[str, Any]]] = {}
    for i, n in enumerate(items):
        groups.setdefault(root(i), []).append(n)

    out = []
    for g in groups.values():
        people = Counter(x for n in g for x in named(n))
        places = Counter(n["place"] for n in g if n.get("place"))
        t0, t1 = min(n.get("t") or 0 for n in g), max(n.get("t") or 0 for n in g)
        score = sum(weigh(n, weights, players) for n in g)
        arc = next((a.get("id") for a in arcs if set(a.get("people") or ()) & set(people)
                    or set(a.get("places") or ()) & set(places)), None)
        if arc:
            score *= ARC_BOOST
        lines = [line(n) for n in g]
        out.append({"score": round(score, 1), "span": f"{hhmm(t0)}-{hhmm(t1)}", "t0": t0, "t1": t1,
                    "places": [p for p, _ in places.most_common()],
                    "people": [p for p, _ in people.most_common(CAP_PEOPLE)],
                    "players": sorted(set(people) & players), **({"arc": arc} if arc else {}),
                    "news": lines[:CAP_NEWS], **({"news_more": len(lines) - CAP_NEWS} if len(lines) > CAP_NEWS else {})})
    out.sort(key=lambda th: (-th["score"], th["t0"]))
    top = max(0, int(top))

    def near(th: dict[str, Any], row: dict[str, Any], pad: int = 2 * 3600) -> bool:
        t = row.get("t") or 0
        if not th["t0"] - pad <= t <= th["t1"] + pad:
            return False
        return row.get("place") in th["places"] or row.get("who") in th["people"] or row.get("to") in th["people"]

    used_scenes: set[int] = set()
    used_said: set[int] = set()
    for th in out[:top]:
        texts, seen = [], set()
        for i, s in enumerate(scenes):
            if s.get("text") and near(th, s) and s["text"] not in seen:
                seen.add(s["text"])
                used_scenes.add(i)
                texts.append(f"{hhmm(s.get('t'))} [{s.get('place')}] {s['text']}")
        th["scenes"] = texts[:CAP_SCENES]
        if len(texts) > CAP_SCENES:
            th["scenes_more"] = len(texts) - CAP_SCENES
        sp = []
        for i, s in enumerate(said):
            if near(th, s):
                used_said.add(i)
                sp.append(_said_line(s))
        th["said"] = sp[:CAP_SAID]
        if len(sp) > CAP_SAID:
            th["said_more"] = len(sp) - CAP_SAID
    around = [f"{th['span']} {', '.join(th['places'][:2]) or 'somewhere'}: {th['news'][0]}" for th in out[top:]]
    around += [_said_line(s) for i, s in enumerate(said) if i not in used_said]
    around += [f"{hhmm(s.get('t'))} [{s.get('place')}] {s['text']}" for i, s in enumerate(scenes)
               if i not in used_scenes and s.get("text")][:15]
    for th in out:
        th.pop("t0"), th.pop("t1")
    res: dict[str, Any] = {"threads": out[:top], "around": around[:CAP_AROUND]}
    if len(out) > top:
        res["threads_more"] = len(out) - top
    if len(around) > CAP_AROUND:
        res["around_more"] = len(around) - CAP_AROUND
    return res


def _said_line(s: dict[str, Any]) -> str:
    tag = " (a player's words: retell, never quote)" if s.get("player") else ""
    to = f" to {s['to']}" if s.get("to") else ""
    return f"{hhmm(s.get('t'))} {s.get('who')}{to}{tag}: {s.get('text')}"
