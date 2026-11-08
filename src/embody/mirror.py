"""Markdown mirror: a read-only directory projection of a world.

Containment becomes directories, entities become markdown files, so an agent
can `ls` and `cat` a world the way it reads a codebase. The engine writes it;
nothing reads it back. Edits belong in ops.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .world import World, _INTERNAL_KINDS

MANIFEST = ".manifest.json"


def slug(name: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or fallback


def _fm(d: dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in d.items():
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v}")
    lines.append("---")
    return "\n".join(lines)


class Mirror:
    def __init__(self, world: World, root: str | Path):
        self.w = world
        self.root = Path(root)

    def write(self, events: int = 200) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        previous = self._read_manifest()
        written: set[str] = set()

        def put(rel: str, text: str) -> None:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                p.write_text(text, encoding="utf-8")
            written.add(rel)

        put("WORLD.md", self._world_md())
        for s in self.w.schemas():
            put(f"schemas/{s['id']}.md", self._schema_md(s))
        for s in self.w.scripts():
            put(f"scripts/{s['id']}.py", f'"""{s["doc"]}"""\n\n{s["source"].strip()}\n' if s["doc"] else s["source"].strip() + "\n")
        self._walk(self.w.root_id, "", put)
        put("events.md", self._events_md(events))
        # files from the last mirror that no longer exist in the world: this directory is ours to prune
        stale = set(previous) - written
        for rel in stale:
            p = self.root / rel
            if p.is_file():
                p.unlink()
        for d in sorted({str(Path(r).parent) for r in stale}, key=len, reverse=True):
            dp = self.root / d
            if d not in ("", ".") and dp.is_dir() and not any(dp.iterdir()):
                dp.rmdir()
        (self.root / MANIFEST).write_text(json.dumps(sorted(written), indent=0), encoding="utf-8")
        return {"root": str(self.root), "files": len(written), "removed": len(stale)}

    def _read_manifest(self) -> list[str]:
        p = self.root / MANIFEST
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
        return []

    # ---- pieces -------------------------------------------------------------------

    def _walk(self, eid: str, prefix: str, put) -> None:
        e = self.w.need(eid)
        kids = self.w.children(eid)
        base = f"{slug(e['name'], e['type'])}.{eid}"
        if kids:
            d = f"{prefix}{base}/"
            put(f"{d}index.md", self._entity_md(e, kids))
            for k in kids:
                self._walk(k["id"], d, put)
        else:
            put(f"{prefix}{base}.md", self._entity_md(e, []))

    def _entity_md(self, e: dict[str, Any], kids: list[dict[str, Any]]) -> str:
        w = self.w
        state = {k: v for k, v in e["state"].items() if k not in ("rules", "description")}
        fm: dict[str, Any] = {"id": e["id"], "type": e["type"], "parent": e["parent_id"]}
        if e["pos"] is not None:
            fm["pos"] = e["pos"]
        emb = w.embodied(e["id"])
        if emb:
            fm["embodied_by"] = emb["id"]
        out = [_fm(fm), "", f"# {e['name'] or e['type']}", ""]
        if e["state"].get("description"):
            out += [e["state"]["description"], ""]
        if state:
            out += ["## State", "", "```json", json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), "```", ""]
        if kids:
            out += ["## Contents", ""]
            for k in kids:
                tag = f" ({k['type']})" if k["type"] != "thing" else ""
                flags = []
                if k["state"].get("hidden"):
                    flags.append("hidden")
                if w.embodied(k["id"]):
                    flags.append("embodied")
                out.append(f"- {k['name'] or k['type']}{tag} `{k['id']}`" + (f" [{', '.join(flags)}]" if flags else ""))
            out.append("")
        exits = w.edges(e["id"], "connects_to", "out")
        if exits:
            out += ["## Exits", ""]
            for x in exits:
                to = w.get(x["target"])
                via = w.get(x["data"].get("via")) if x["data"].get("via") else None
                line = f"- to {to['name'] if to else x['target']} `{x['target']}`"
                if via:
                    st = "open" if via["state"].get("open") else "closed"
                    if via["state"].get("locked"):
                        st += ", locked"
                    line += f" via {via['name']} `{via['id']}` ({st})"
                out.append(line)
            out.append("")
        rels = [r for r in w.edges(e["id"], None, "both") if r["relation"] != "connects_to"]
        hyper = w.hyperedges(e["id"])
        if rels or hyper:
            out += ["## Relations", ""]
            for r in rels:
                other = r["target"] if r["source"] == e["id"] else r["source"]
                o = w.get(other)
                arrow = "->" if r["source"] == e["id"] else "<-"
                out.append(f"- {r['relation']} {arrow} {o['name'] if o else other} `{other}`"
                           + (f" {json.dumps(r['data'])}" if r["data"] else ""))
            for h in hyper:
                out.append(f"- {h['relation']} among {', '.join(f'`{p}`' for p in h['participants'])}"
                           + (f" {json.dumps(h['data'])}" if h["data"] else ""))
            out.append("")
        acts = w.schema_actions(e["type"])
        if acts:
            out += ["## Actions", ""]
            for v, a in acts.items():
                if a.get("hidden"):
                    continue
                tt = f" (targets a {a['targets']})" if a.get("targets") else ""
                out.append(f"- `{v}`{tt}: {a.get('doc', '')}".rstrip(": "))
            out.append("")
        rules = e["state"].get("rules", [])
        comps = w.schema_components(e["type"], "listeners") + w.schema_components(e["type"], "behaviors")
        if rules or comps:
            out += ["## Code", ""]
            for c in comps:
                kind = "behavior" if "every" in c else "listener"
                out.append(f"- {kind} `{c['script']}`" + (f" every {c['every']}" if "every" in c else f" on {c.get('kinds') or 'all events'}"))
            for r in rules:
                out.append(f"- rule `{r['script']}` on {r.get('kinds')}")
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def _world_md(self) -> str:
        s = self.w.summary()
        root = self.w.need(self.w.root_id)
        out = [_fm({"id": s["id"], "t": s["t"], "entities": s["entities"], "events": s["events"]}), "",
               f"# {s['name']}", ""]
        if s["description"]:
            out += [s["description"], ""]
        out += ["Read-only mirror. Change the world through embody ops, not by editing these files.", "",
                "## Top level", ""]
        for k in self.w.children(root["id"]):
            out.append(f"- {k['name'] or k['type']} ({k['type']}) `{k['id']}`")
        out += ["", "## Principals", ""]
        for p in s["principals"]:
            ent = self.w.get(p["entity"]) if p["entity"] else None
            out.append(f"- {p['id']} ({p['kind']}) as {ent['name'] if ent else '-'} `{p['entity']}`")
        if not s["principals"]:
            out.append("- none")
        out += ["", "## Clock", "", f"t = {s['t']}, running = {s['clock']['running']}, rate = {s['clock']['rate']}, "
                f"pending = {s['clock']['pending']}", ""]
        return "\n".join(out)

    def _schema_md(self, s: dict[str, Any]) -> str:
        out = [_fm({"id": s["id"], "extends": s["extends"], "version": s["version"]}), "", f"# {s['id']}", ""]
        if s["doc"]:
            out += [s["doc"], ""]
        if s["state"]:
            out += ["## Default state", "", "```json", json.dumps(s["state"], indent=2, sort_keys=True), "```", ""]
        if s["space"]:
            out += ["## Space", "", "```json", json.dumps(s["space"]), "```", ""]
        if s["actions"]:
            out += ["## Actions", ""]
            for v, a in s["actions"].items():
                out.append(f"- `{v}` -> script `{a['script']}`" + (f", targets {a['targets']}" if a.get("targets") else "")
                           + (f": {a['doc']}" if a.get("doc") else ""))
            out.append("")
        for kind in ("listeners", "behaviors"):
            if s[kind]:
                out += [f"## {kind.title()}", ""]
                for c in s[kind]:
                    out.append(f"- `{c['script']}` " + json.dumps({k: v for k, v in c.items() if k != 'script'}))
                out.append("")
        return "\n".join(out).rstrip() + "\n"

    def _events_md(self, n: int) -> str:
        w = self.w
        last = w.store.next_seq(w.id) - 1
        rows = [e for e in w.events(since=max(0, last - n * 3), limit=n * 3) if e["kind"] not in _INTERNAL_KINDS][-n:]
        out = ["# Recent events", "", f"Last {len(rows)} of {last}.", "", "| seq | t | kind | actor | target | payload |",
               "|---|---|---|---|---|---|"]
        for e in rows:
            p = json.dumps(e["payload"], ensure_ascii=False)
            if len(p) > 120:
                p = p[:117] + "..."
            out.append(f"| {e['seq']} | {e['t']:g} | {e['kind']} | {e['actor_id'] or ''} | {e['target_id'] or ''} | {p} |")
        return "\n".join(out) + "\n"
