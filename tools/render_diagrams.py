"""Render the explainer diagrams: every docs/diagrams/src/<name>.html to docs/diagrams/<name>.png at 2x (3200x1800),
with headless Edge or Chrome. The pages load their fonts from Google Fonts, so this needs the network.

    uv run python tools/render_diagrams.py            # all of them
    uv run python tools/render_diagrams.py acts seats # some
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "diagrams" / "src"
OUT = ROOT / "docs" / "diagrams"
BROWSERS = [
    os.environ.get("EMBODY_BROWSER", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def browser() -> str:
    for b in BROWSERS:
        if b and (Path(b).exists() or shutil.which(b)):
            return b
    sys.exit("no Edge or Chrome found: set EMBODY_BROWSER to one")


def render(name: str, exe: str) -> Path:
    page = SRC / f"{name}.html"
    out = OUT / f"{name}.png"
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    "--window-size=1600,900", "--virtual-time-budget=8000", f"--screenshot={out}", page.as_uri()],
                   check=True, capture_output=True, timeout=120)
    return out


def main(names: list[str]) -> None:
    exe = browser()
    for n in names or sorted(p.stem for p in SRC.glob("*.html")):
        print(render(n, exe))


if __name__ == "__main__":
    main(sys.argv[1:])
