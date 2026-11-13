"""Following through go: whoever follows the walker comes along, and whoever follows them in turn, each body once;
a sleeper stays and so do those who follow it; two who follow each other do not walk forever."""

import shutil
from pathlib import Path

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "lane", "name": "The lane", "seed": 4, "description": "A yard and a road.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"go": {"script": "go", "doc": "Walk there", "targets": "place", "scope": "exits"}})

def populate(s):
    root = s.summary()["root"]
    yard = s.spawn("place", root, "Yard")["id"]
    road = s.spawn("place", root, "Road")["id"]
    s.connect(yard, road)
    for name in ["Ruhl", "Reeve", "Aaron", "Vass", "Pell", "Moss"]:
        s.spawn("person", yard, name)
    s.clock(run=False)
'''


def world(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(REPO / "packs" / "village", ws / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (ws / "worlds" / "lane").mkdir(parents=True)
    (ws / "worlds" / "lane" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(None, workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "lane")
    return eng, gm


def where(gm, name):
    return gm.world.get(gm.world.get(gm.inspect(name)["id"])["parent_id"])["name"]


def ident(gm, name):
    return gm.inspect(name)["id"]


def test_followers_of_followers_come_along_and_a_sleeper_breaks_the_chain(tmp_path):
    # the Reach, t 1321428: the reeve followed Ruhl, Aaron and Vass followed the reeve, and were left in the yard
    eng, gm = world(tmp_path)
    gm.patch("Reeve", {"follows": ident(gm, "Ruhl")})
    gm.patch("Aaron", {"follows": ident(gm, "Reeve")})
    gm.patch("Vass", {"friend": ident(gm, "Aaron")})
    gm.patch("Pell", {"follows": ident(gm, "Vass"), "asleep": True})
    gm.patch("Moss", {"follows": ident(gm, "Pell")})
    ruhl = eng.session("ruhl")
    ruhl.join("lane", "Ruhl")
    r = ruhl.act("go", "Road")
    assert [where(gm, n) for n in ["Ruhl", "Reeve", "Aaron", "Vass"]] == ["Road"] * 4
    assert where(gm, "Pell") == "Yard" and where(gm, "Moss") == "Yard"  # asleep, and the one who follows the sleeper
    led = {e["payload"]["who"]: e["payload"].get("following") for e in r["events"] if e["kind"] == "arrived"}
    assert led[ident(gm, "Aaron")] == ident(gm, "Reeve") and led[ident(gm, "Vass")] == ident(gm, "Aaron")


def test_two_who_follow_each_other_walk_once(tmp_path):
    eng, gm = world(tmp_path)
    gm.patch("Reeve", {"follows": ident(gm, "Ruhl")})
    gm.patch("Ruhl", {"follows": ident(gm, "Reeve")})
    ruhl = eng.session("ruhl")
    ruhl.join("lane", "Ruhl")
    ruhl.act("go", "Road")
    assert where(gm, "Ruhl") == "Road" and where(gm, "Reeve") == "Road"
    ruhl.act("go", "Yard")
    assert where(gm, "Ruhl") == "Yard" and where(gm, "Reeve") == "Yard"
