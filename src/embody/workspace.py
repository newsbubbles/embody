"""The workspace: folders of worlds and packs around one database.

    <workspace>/
      embody.db              the running state: a build of the folders below, plus every game played in them
      worlds/<id>/           one world, one folder; the folder name is the world id
        build.py             WORLD manifest, define(s) for schemas, populate(s) for entities, upgrade(s) for additions
        scripts/*.py         the world's scripts, one file each; the file stem is the script id
        changes.jsonl        live authoring since the build (an author's spawn, patch, define_schema...), replayed
                             after populate on a fresh build; the author folds lines into build.py or deletes them
        saves/*.json         state files written by save(); restore() makes a world from one
        notes/ tests/ assets/ and anything else the world owns: the engine never looks at those
      packs/<name>/          define-only code more than one world uses
        pack.py              PACK manifest, define(s) for schemas, helpers a build.py may import
        scripts/*.py         the pack's scripts

The folder is canonical and the database is derived from it. Git in the world folder gives versions, forks,
backups and sharing; `create_world` starts one when the folder is not inside a repository already.

A script file may include another script's text with a line `use("common")`: the loader replaces the line with
the source of the script of that name (from the same folder, a pack loaded before it, or the world's stored
scripts). The interpreter never sees `use`.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .world import Rejected

if TYPE_CHECKING:
    from .ops import Engine, Session

USE_LINE = re.compile(r'^\s*use\(\s*["\']([\w./-]+)["\']\s*\)\s*(#.*)?$')
RECORDED_OPS = ["define_schema", "spawn", "patch", "move", "destroy", "link", "connect", "unlink", "relate",
                "unrelate", "set_rule", "clear_rule", "schedule", "unschedule"]

BUILD_SKELETON = '''"""{name}: a world for embody. Edit this file and the scripts beside it; load it with
`load_world("{id}")`, renew a live game with `load_world("{id}", upgrade=True)`."""

WORLD = {{
    "id": "{id}",
    "name": {name!r},
    "seed": {seed},
    "description": {description!r},
    "requires": [],  # packs from <workspace>/packs, installed before this world's own scripts and schemas
}}


def define(s):
    """Schemas. Scripts come from scripts/*.py (the file stem is the script id). Safe to run again on a live world."""


def populate(s):
    """Places, people, things, connections, rules and timers. Runs once, on build."""


def upgrade(s):
    """What an older build of this world lacks. Every step checks before it acts, so it runs twice without change."""
'''

WORLD_GITIGNORE = "mirror/\n__pycache__/\n"


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    @classmethod
    def from_db(cls, db: str | Path) -> "Workspace":
        """The workspace around a database: its folder, or the folder above a legacy `worlds/embody.db`."""
        p = Path(db).resolve().parent
        if p.name == "worlds":
            p = p.parent
        return cls(p)

    @property
    def worlds_dir(self) -> Path:
        return self.root / "worlds"

    @property
    def packs_dir(self) -> Path:
        return self.root / "packs"

    def world_dir(self, world_id: str) -> Path:
        return self.worlds_dir / world_id

    def pack_dir(self, name: str) -> Path:
        return self.packs_dir / name

    def list_worlds(self) -> list[dict[str, Any]]:
        """World folders with a build.py, with the manifest when it parses."""
        out = []
        if not self.worlds_dir.exists():
            return out
        for d in sorted(self.worlds_dir.iterdir()):
            if (d / "build.py").exists():
                out.append({"id": d.name, "folder": str(d), "manifest": _manifest(d / "build.py")})
        return out

    def list_packs(self) -> list[str]:
        if not self.packs_dir.exists():
            return []
        return sorted(d.name for d in self.packs_dir.iterdir() if (d / "pack.py").exists())

    def resolve(self, ref: str | Path) -> Path:
        """A world id, a world folder, a build.py, or a legacy single-file world."""
        p = Path(ref)
        if p.exists():
            if p.is_dir():
                if not (p / "build.py").exists():
                    raise Rejected(f"{p} has no build.py", hint="a world folder holds build.py and scripts/")
                return p.resolve()
            return p.resolve()
        d = self.world_dir(str(ref))
        if (d / "build.py").exists():
            return d
        legacy = self.worlds_dir / f"{ref}.py"
        if legacy.exists():
            return legacy
        known = [w["id"] for w in self.list_worlds()]
        raise Rejected(f"no world {str(ref)!r} in {self.worlds_dir}",
                       hint=("worlds here: " + ", ".join(known)) if known else "create one with create_world, or load a folder by path")

    # ---- folders -------------------------------------------------------------------------

    def scaffold_world(self, world_id: str, name: str, seed: int = 0, description: str = "") -> dict[str, Any]:
        """Make the world's folder with a build.py skeleton. Touches nothing that exists."""
        d = self.world_dir(world_id)
        made = []
        for sub in ("", "scripts", "notes"):
            p = d / sub if sub else d
            if not p.exists():
                p.mkdir(parents=True)
                made.append(str(p))
        if not (d / "build.py").exists():
            (d / "build.py").write_text(BUILD_SKELETON.format(id=world_id, name=name, seed=seed, description=description),
                                        encoding="utf-8")
            made.append(str(d / "build.py"))
        if not (d / ".gitignore").exists():
            (d / ".gitignore").write_text(WORLD_GITIGNORE, encoding="utf-8")
        if not (d / "README.md").exists():
            (d / "README.md").write_text(f"# {name}\n\n{description}\n\nA world for embody. `build.py` builds it, "
                                         f"`scripts/` holds its verbs and rules, `notes/` what play taught us.\n", encoding="utf-8")
        return {"folder": str(d), "made": made}

    def git_init(self, folder: Path) -> str:
        """Start a repository in the folder unless it already sits inside one. Returns what happened."""
        for p in [folder] + list(folder.parents):
            if (p / ".git").exists():
                return f"inside {p}"
        try:
            r = subprocess.run(["git", "init", "-q"], cwd=str(folder), capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"git not run: {e}"
        return "initialized" if r.returncode == 0 else f"git init failed: {r.stderr.strip()}"

    def write_script(self, world_id: str, script_id: str, source: str) -> Path | None:
        """A live define_script lands in the world's scripts/ first. None when the world has no folder."""
        d = self.world_dir(world_id)
        if not (d / "build.py").exists():
            return None
        (d / "scripts").mkdir(exist_ok=True)
        p = d / "scripts" / f"{script_id}.py"
        p.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
        return p

    def record(self, world_id: str, op: str, args: dict[str, Any], by: str) -> bool:
        """Append one line of live authoring to the world's changes.jsonl. False when the world has no folder."""
        d = self.world_dir(world_id)
        if not (d / "build.py").exists():
            return False
        line = {"op": op, "args": args, "by": by, "at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}
        with (d / "changes.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str) + "\n")
        return True

    def changes(self, world_id: str) -> list[dict[str, Any]]:
        p = self.world_dir(world_id) / "changes.jsonl"
        if not p.exists():
            return []
        out = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    # ---- saves ---------------------------------------------------------------------------

    def home(self, world_id: str, meta_of: Callable[[str], dict[str, Any] | None]) -> str:
        """The world whose folder a game belongs to: itself, or up the forked_from / restored_from chain to the
        first world that has a folder here. A fork runs its source's code, so its saves live with the source."""
        seen: set[str] = set()
        wid = world_id
        while wid not in seen:
            seen.add(wid)
            if (self.world_dir(wid) / "build.py").exists():
                return wid
            meta = meta_of(wid) or {}
            src = (meta.get("forked_from") or meta.get("restored_from") or {}).get("world")
            if not src:
                break
            wid = src
        return world_id

    def save_path(self, world_id: str, name: str | None = None, home: str | None = None) -> Path:
        """worlds/<home>/saves/<name>.json; home is the world whose folder this game belongs to (see home()).
        A game with no folder anywhere saves under saves/<id>/ at the root. The default name is the time; a game
        saving into another world's folder gets its own id in front of the name."""
        home = home or world_id
        d = self.world_dir(home) if (self.world_dir(home) / "build.py").exists() else self.root / "saves" / world_id
        (d / "saves").mkdir(parents=True, exist_ok=True)
        name = name or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        if home != world_id:
            name = f"{world_id}-{name}"
        return d / "saves" / f"{name}.json"


# ---- scripts as files -----------------------------------------------------------------------


def read_scripts(folder: Path) -> dict[str, str]:
    """scripts/*.py of a world or pack folder, raw, keyed by file stem."""
    d = folder / "scripts"
    if not d.exists():
        return {}
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.py"))}


def resolve_uses(sid: str, raw: dict[str, str], known: dict[str, str], stack: tuple[str, ...] = ()) -> str:
    """Replace every `use("x")` line with x's source: from this folder first, then from what was loaded before."""
    if sid in stack:
        raise Rejected(f"script {sid!r} includes itself through {' > '.join(stack)}", hint="drop the cycle in use()")
    out = []
    for line in raw[sid].splitlines():
        m = USE_LINE.match(line)
        if not m:
            out.append(line)
            continue
        name = m.group(1)
        if name not in raw and "_" + name in raw:
            name = "_" + name  # an include-only file: scripts/_common.py is used as use("common")
        if name in raw:
            out.append(resolve_uses(name, raw, known, stack + (sid,)))
        elif name in known:
            out.append(known[name])
        elif "_" + name in known:
            out.append(known["_" + name])
        else:
            raise Rejected(f"script {sid!r} uses {name!r}, which is not in this folder, a pack loaded before it, or the world",
                           hint="name a script file beside it, add the pack to requires, or define the script first")
    return "\n".join(out) + "\n"


def define_scripts(session: "Session", folder: Path, known: dict[str, str], shadowed: set[str] = frozenset()) -> list[str]:
    """Define every scripts/*.py of the folder. A file whose name starts with `_` is an include for use(), not a script.
    `shadowed` names the scripts the world has its own file for: a pack's version of those is never defined, so the
    world's replaces it outright (the Glass Reach has its own `go` over the village pack's)."""
    raw = read_scripts(folder)
    done = []
    for sid in raw:
        src = resolve_uses(sid, raw, known)
        if sid.startswith("_"):
            known[sid] = src
            continue
        if sid in shadowed:
            continue
        known[sid] = src
        session.define_script(sid, src)
        done.append(sid)
    return done


def _import(path: Path, name: str, roots: list[Path]) -> Any:
    for r in roots:
        if str(r) not in sys.path:
            sys.path.insert(0, str(r))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Rejected(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest(build_py: Path) -> dict[str, Any] | None:
    """The WORLD dict of a build.py without importing it: a literal, read with ast."""
    import ast
    try:
        tree = ast.parse(build_py.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WORLD" for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                return None
    return None


# ---- the loader --------------------------------------------------------------------------------


def install_pack(session: "Session", ws: Workspace, name: str, known: dict[str, str],
                 shadowed: set[str] = frozenset()) -> dict[str, Any]:
    d = ws.pack_dir(name)
    if not (d / "pack.py").exists():
        raise Rejected(f"no pack {name!r} in {ws.packs_dir}",
                       hint=("packs here: " + ", ".join(ws.list_packs())) if ws.list_packs() else "a pack is packs/<name>/pack.py plus scripts/")
    mod = _import(d / "pack.py", f"embody_pack_{name}", [ws.root])
    scripts = define_scripts(session, d, known, shadowed)
    if hasattr(mod, "define"):
        mod.define(session)
    return {"pack": name, "scripts": scripts}


def load_world(session: "Session", ref: str | Path, upgrade: bool = False, workspace: Workspace | None = None,
               hosted: bool = False) -> dict[str, Any]:
    """Build a world from its folder (or renew a live one with upgrade=True).

    A folder's build.py carries a WORLD manifest (id, name, seed, description, requires), `define(s)` for schemas,
    `populate(s)` for entities and `upgrade(s)` for additions. Scripts are the files in scripts/. Packs named in
    `requires` are installed first. A build replays changes.jsonl after populate. Upgrade runs the packs' define,
    the scripts, define and upgrade against the world the session points at: new code, same state and history.

    hosted=True also runs the folder's `host(s)` after populate or upgrade: how this world differs as a hosted
    place (its pace, its seats' lapse, timers scaled to real time). A build without one hosts as it is.

    A legacy single file with `build(session)` (or define/populate/upgrade) still loads as before."""
    ws = workspace or session.engine.workspace or Workspace(Path.cwd())
    target = ws.resolve(ref)
    if target.is_file() and target.name != "build.py":
        return _load_legacy(session, target, upgrade)
    folder = target if target.is_dir() else target.parent
    mod = _import(folder / "build.py", f"embody_world_{folder.name}", [folder, ws.root])
    manifest = getattr(mod, "WORLD", None)
    known: dict[str, str] = {}
    own = {sid for sid in read_scripts(folder) if not sid.startswith("_")}
    with session.building():
        if upgrade:
            if not session.world_id:
                raise Rejected("point the session at the world to upgrade first", hint="use(world_id)")
            packs = [install_pack(session, ws, p, known, own) for p in (manifest or {}).get("requires", [])]
            scripts = define_scripts(session, folder, known)
            if hasattr(mod, "define"):
                mod.define(session)
            if hasattr(mod, "upgrade"):
                mod.upgrade(session)
            if hosted and hasattr(mod, "host"):
                mod.host(session)
            r = session.summary()
            r.update(upgraded=True, hosted=hosted, folder=str(folder), packs=[p["pack"] for p in packs], scripts=scripts)
            return r
        if manifest is None:
            if not hasattr(mod, "build"):
                raise Rejected(f"{folder / 'build.py'} has neither a WORLD manifest nor build(session)",
                               hint="WORLD = {'id': ..., 'name': ..., 'seed': 0, 'requires': []} plus define(s) and populate(s)")
            r = mod.build(session) or session.summary()
            r["folder"] = str(folder)
            return r
        wid = manifest.get("id") or folder.name
        if session.engine.store.get("world", None, wid):
            raise Rejected(f"world {wid!r} already exists", hint=f"load_world({wid!r}, upgrade=True) renews its code; fork_world or restore for a new game")
        session.create_world(manifest.get("name") or wid, seed=int(manifest.get("seed", 0)), id=wid,
                             description=manifest.get("description", ""))
        packs = [install_pack(session, ws, p, known, own) for p in manifest.get("requires", [])]
        scripts = define_scripts(session, folder, known)
        if hasattr(mod, "define"):
            mod.define(session)
        if hasattr(mod, "populate"):
            mod.populate(session)
        replayed, errors = replay_changes(session, ws, wid)
        if hosted and hasattr(mod, "host"):
            mod.host(session)
    git = ws.git_init(folder)
    r = session.summary()
    r.update(folder=str(folder), hosted=hosted, packs=[p["pack"] for p in packs], scripts=scripts, replayed=replayed, git=git)
    if errors:
        r["replay_errors"] = errors
    return r


def replay_changes(session: "Session", ws: Workspace, world_id: str) -> tuple[int, list[str]]:
    n, errors = 0, []
    for line in ws.changes(world_id):
        op = line.get("op")
        if op not in RECORDED_OPS:
            errors.append(f"line {n + 1}: unknown op {op!r}")
            continue
        try:
            getattr(session, op)(**line.get("args", {}))
            n += 1
        except Rejected as e:
            errors.append(f"{op}: {e}")
        except Exception as e:  # a bad line never stops the build
            errors.append(f"{op}: {type(e).__name__}: {e}")
    return n, errors


def _load_legacy(session: "Session", path: Path, upgrade: bool) -> dict[str, Any]:
    mod = _import(path, f"embody_world_{path.stem}", [path.parent])
    with session.building():
        if upgrade:
            if not hasattr(mod, "define"):
                raise Rejected(f"{path} has no define(session) function to upgrade with",
                               hint="split build into define(s) for scripts and schemas and populate(s) for entities")
            if not session.world_id:
                raise Rejected("point the session at the world to upgrade first", hint="use(world_id)")
            mod.define(session)
            if hasattr(mod, "upgrade"):
                mod.upgrade(session)
            r = session.summary()
            r["upgraded"] = True
            return r
        if not hasattr(mod, "build"):
            raise Rejected(f"{path} has no build(session) function",
                           hint="def build(s): s.create_world(...); s.define_schema(...); s.spawn(...)")
        return mod.build(session) or session.summary()


# ---- saves ---------------------------------------------------------------------------------------

SAVE_TABLES = ("schema", "script", "entity", "edge", "hyperedge", "event", "scheduled", "principal")


def save_world(engine: "Engine", world_id: str, path: Path) -> dict[str, Any]:
    """Everything the database holds about one world, as one JSON file."""
    st = engine.store
    row = st.get("world", None, world_id)
    if row is None:
        raise Rejected(f"no world {world_id!r}")
    data: dict[str, Any] = {"embody_save": 1, "world": dict(row), "tables": {}}
    for t in SAVE_TABLES:
        try:
            data["tables"][t] = [dict(r) for r in st.query(t, "world_id=?", (world_id,))]
        except Exception:
            data["tables"][t] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, default=str), encoding="utf-8")
    return {"ok": True, "path": str(path), "world": world_id, "entities": len(data["tables"]["entity"]),
            "events": len(data["tables"]["event"])}


def restore_world(engine: "Engine", path: Path, id: str | None = None) -> dict[str, Any]:
    """A world from a save file, under its own id or a new one. Principals are not restored: nobody is in it."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("embody_save") != 1:
        raise Rejected(f"{path} is not an embody save")
    row = dict(data["world"])
    wid = id or row["id"]
    st = engine.store
    if st.get("world", None, wid):
        raise Rejected(f"world {wid!r} already exists", hint="restore(path, id=<new id>)")
    source = row["id"]
    row["id"] = wid
    meta = dict(row.get("meta") or {})
    meta["restored_from"] = {"path": str(path), "world": source}
    row["meta"] = meta
    st.begin()
    try:
        st.put("world", row)
        for t in SAVE_TABLES:
            if t == "principal":
                continue
            for r in data["tables"].get(t, []):
                r = dict(r)
                r["world_id"] = wid
                st.put(t, r)
        st.commit()
    except Exception:
        st.rollback()
        raise
    engine._worlds.pop(wid, None)
    return engine.world(wid).summary()
