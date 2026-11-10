"""Stage a deploy: the committed tree (git archive HEAD, so nothing uncommitted ships) plus a world's site folder,
which stays out of git (its films are large and are the site's own). Prints the one command that deploys the stage.

    uv run python tools/stage_deploy.py --world glass-reach --site D:/path/to/site
    railway up <stage> --path-as-root --no-gitignore --ci

The site's own working files stay behind: dot-files, and the names in SKIP (notes, sources, local tools).
"""

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"BRIEF.md", "README.md", "dev", "media-src", "node_modules"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--world", required=True, help="the world folder the site belongs to (worlds/<world>/site)")
    ap.add_argument("--site", required=True, help="the site folder to ship")
    ap.add_argument("--out", help="where to stage (default: a fresh temporary folder)")
    a = ap.parse_args()
    site = Path(a.site).resolve()
    if not (site / "index.html").is_file():
        print(f"no index.html in {site}", file=sys.stderr)
        return 2
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
    if dirty:
        print("note: uncommitted changes stay behind; the stage is HEAD:\n" + dirty, file=sys.stderr)
    out = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="embody-stage-"))
    if out.exists() and any(out.iterdir()):
        print(f"{out} is not empty", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(out, filter="data")
    dest = out / "worlds" / a.world / "site"
    shutil.copytree(site, dest, ignore=lambda d, names: [n for n in names if n.startswith(".") or n in SKIP])
    files = [p for p in dest.rglob("*") if p.is_file()]
    print(f"staged {out}: HEAD plus {len(files)} site files ({sum(p.stat().st_size for p in files) / 2**20:.1f} MiB)")
    print(f"deploy: railway up \"{out}\" --path-as-root --no-gitignore --ci")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
