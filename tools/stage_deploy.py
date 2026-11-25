"""Stage a deploy: the engine's committed tree (git archive HEAD, so nothing uncommitted ships), each world from its own
repository's committed tree when it has one (worlds/<id> linked to a private repo), else from its folder under worlds/
as it is on disk (git ignores worlds/, so a build or upload that follows .gitignore leaves it behind), each world's
site folder (which stays out of git: its films are large and are the site's own), and the list of worlds the container
hosts. Prints how to build the stage on any Docker host, and the upload line for each platform in docs/platforms/.

    uv run python tools/stage_deploy.py --world my-world
    uv run python tools/stage_deploy.py --world examples/ferry-at-dusk
    uv run python tools/stage_deploy.py --world my-world=/path/to/site
    uv run python tools/stage_deploy.py --world my-world=/path/to/site --world other-world \\
        --domain world.example.com=my-world
    docker build -t my-world <stage>

One world ships with deploy/world naming it, and deploy/start.sh serves it alone; a path in the engine's tree
(examples/ferry-at-dusk) ships a sample the same way. Two or more ship with deploy/worlds, and start.sh runs
`embody hub`: one server per world, each on its own database file. A world's `private/` folder (git-ignored: codes
and lock words its build reads) ships beside it. The site's own working files stay behind: dot-files, and the names
in SKIP (notes, sources, local tools). A world shipped from disk leaves its dot-files, mirror and databases behind.
`--world W --site S` (the older form) still works for one world.
"""

import argparse
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"BRIEF.md", "README.md", "dev", "media-src", "node_modules"}
# what stays behind when a world ships from its folder on disk: the working files a run leaves there
LOCAL_SKIP = {"mirror", "__pycache__"}
LOCAL_SKIP_SUFFIXES = (".db", ".db-shm", ".db-wal", ".db-journal", ".pyc")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def _untar(tar: bytes, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dest, filter="data")


def _local(d: str, names: list[str]) -> list[str]:
    return [n for n in names if n.startswith(".") or n in LOCAL_SKIP or n.endswith(LOCAL_SKIP_SUFFIXES)]


def stage_world(out: Path, wid: str, site: Path | None) -> str:
    """worlds/<wid> into the stage: from its own repository when it has one, else from the engine's tree when it is
    committed there, else from its folder on disk. A path (examples/ferry-at-dusk) must be in the engine's tree.
    Returns a line on what it shipped."""
    if "/" in wid:
        if not (out / wid / "build.py").is_file():
            raise SystemExit(f"no world at {wid}: a path names a folder in the engine's committed tree "
                             "(examples/ferry-at-dusk); a world of your own goes in worlds/<id>/, staged by its id")
        return f"{wid}: from the engine's tree"
    src = ROOT / "worlds" / wid
    dest = out / "worlds" / wid
    top = _git(src, "rev-parse", "--show-toplevel") if src.is_dir() else ""
    own = bool(top) and Path(top).resolve() != ROOT.resolve()
    if own:
        if not _git(src, "rev-parse", "--verify", "-q", "HEAD"):
            raise SystemExit(f"{wid}: its repository ({top}) has no commits yet; commit the world, then stage")
        dirty = _git(src, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            print(f"note: {wid}: uncommitted changes stay behind; the stage is its HEAD:\n{dirty}", file=sys.stderr)
        sub = Path(src.resolve()).relative_to(Path(top).resolve()).as_posix()
        tree = f"HEAD:{sub}" if sub != "." else "HEAD"
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True)
        _untar(subprocess.run(["git", "archive", "--format=tar", tree], cwd=top, capture_output=True, check=True).stdout,
               dest)
        what = f"{wid}: {_git(Path(top), 'rev-parse', '--short', 'HEAD')} from its own repository"
    elif (dest / "build.py").is_file():
        what = f"{wid}: from the engine's tree"
    elif (src / "build.py").is_file():
        shutil.copytree(src, dest, dirs_exist_ok=True, ignore=_local)
        files = [p for p in dest.rglob("*") if p.is_file()]
        what = f"{wid}: {len(files)} files from worlds/{wid} as it is on disk"
    else:
        raise SystemExit(f"no world {wid}: worlds/{wid}/build.py is not here (a world folder holds build.py and scripts/)")
    private = src / "private"
    if private.is_dir():
        shutil.copytree(private, dest / "private", dirs_exist_ok=True)
        what += ", with its private/ folder"
    if site is not None:
        if not (site / "index.html").is_file():
            raise SystemExit(f"no index.html in {site}")
        shutil.copytree(site, dest / "site", dirs_exist_ok=True,
                        ignore=lambda d, names: [n for n in names if n.startswith(".") or n in SKIP])
        files = [p for p in (dest / "site").rglob("*") if p.is_file()]
        what += f", {len(files)} site files ({sum(p.stat().st_size for p in files) / 2**20:.1f} MiB)"
    return what


def manifest(out: Path, engine: str, worlds: list[tuple[str, Path | None]], domains: list[str],
             remotes: list[str]) -> dict:
    """deploy/manifest.json: what the stage holds, for tools/deploy_check.py to compare one stage with the last."""
    shipped = {}
    for wid, _ in worlds:
        src = ROOT / "worlds" / wid
        top = _git(src, "rev-parse", "--show-toplevel") if "/" not in wid and src.is_dir() else ""
        own = bool(top) and Path(top).resolve() != ROOT.resolve()
        site = out / wid / "site" if "/" in wid else out / "worlds" / wid / "site"
        files = [p for p in site.rglob("*") if p.is_file()] if site.is_dir() else []
        shipped[wid] = {"commit": _git(Path(top), "rev-parse", "--short", "HEAD") if own else None,
                        "from": "its own repository" if own else "the engine's tree or disk",
                        "site_files": len(files), "site_bytes": sum(p.stat().st_size for p in files)}
    return {"engine": _git(ROOT, "rev-parse", "--short", engine), "staged_at": int(time.time()), "worlds": shipped,
            "domains": dict(d.partition("=")[::2] for d in domains),
            "remotes": dict(r.partition("=")[::2] for r in remotes)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--world", action="append", required=True,
                    help="a world to host, as ID or ID=SITE_FOLDER, or a sample's path (examples/ferry-at-dusk); "
                         "repeat for more (the first is the default)")
    ap.add_argument("--site", help="the site folder, for a single --world given without one")
    ap.add_argument("--domain", action="append", default=[], help="HOST=WORLD for the hub's domain map; repeat")
    ap.add_argument("--remote", action="append", default=[],
                    help="WORLD=URL: a world on its own server that the hub forwards its domains to; repeat")
    ap.add_argument("--engine", default="HEAD",
                    help="the engine's commit or tag to ship (default HEAD): a world pins its engine version here")
    ap.add_argument("--out", help="where to stage (default: a fresh temporary folder)")
    a = ap.parse_args(argv)
    worlds: list[tuple[str, Path | None]] = []
    for w in a.world:
        wid, _, site = w.partition("=")
        worlds.append((wid.strip().replace("\\", "/").strip("/"), Path(site).resolve() if site else None))
    hub = len(worlds) > 1 or bool(a.domain) or bool(a.remote)
    if hub and any("/" in w for w, _ in worlds):
        print("a path (examples/...) ships one world alone; for the hub, put each world in worlds/<id>/", file=sys.stderr)
        return 2
    if a.site:
        if len(worlds) != 1 or worlds[0][1] is not None:
            print("--site goes with one --world given without a site (or write --world ID=SITE)", file=sys.stderr)
            return 2
        worlds[0] = (worlds[0][0], Path(a.site).resolve())
    if not _git(ROOT, "rev-parse", "--verify", "-q", f"{a.engine}^{{commit}}"):
        print(f"no engine version {a.engine}: name a commit or tag of this repository", file=sys.stderr)
        return 2
    dirty = _git(ROOT, "status", "--porcelain", "--untracked-files=no")
    if dirty and a.engine == "HEAD":
        print("note: uncommitted changes stay behind; the stage is HEAD:\n" + dirty, file=sys.stderr)
    out = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="embody-stage-"))
    if out.exists() and any(out.iterdir()):
        print(f"{out} is not empty", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    _untar(subprocess.run(["git", "archive", "--format=tar", a.engine], cwd=ROOT, capture_output=True, check=True).stdout,
           out)
    lines = [stage_world(out, wid, site) for wid, site in worlds]
    if hub:
        (out / "deploy" / "worlds").write_text(",".join(w for w, _ in worlds) + "\n", encoding="utf-8", newline="\n")
        (out / "deploy" / "domains").write_text(",".join(a.domain) + "\n", encoding="utf-8", newline="\n")
        if a.remote:
            (out / "deploy" / "remotes").write_text(",".join(a.remote) + "\n", encoding="utf-8", newline="\n")
    else:
        (out / "deploy" / "world").write_text(worlds[0][0] + "\n", encoding="utf-8", newline="\n")
    (out / "deploy" / "manifest.json").write_text(json.dumps(manifest(out, a.engine, worlds, a.domain, a.remote),
                                                             indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"staged {out}: the engine's {a.engine} ({_git(ROOT, 'rev-parse', '--short', a.engine)})")
    for line in lines:
        print("  " + line)
    if hub:
        print(f"  hub: {', '.join(w for w, _ in worlds)}; domains {', '.join(a.domain) or '(none)'}"
              + (f"; remote {', '.join(a.remote)}" if a.remote else ""))
    print(f"build: docker build -t <name> \"{out}\"  (any Docker host: docs/HOST_YOUR_WORLD.md; a VPS or home box: docs/platforms/vps.md)")
    print(f"railway: railway up \"{out}\" --path-as-root --no-gitignore --ci  (docs/platforms/railway.md)")
    print(f"check: tools/deploy_check.py pre \"{out}\" before it goes up, and post after (docs/HOSTING.md, \"Deploy checks\")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
