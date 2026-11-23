"""A world's handbook (Nate, 2026-11-23): the guides its agents read for their part come from the world itself.
handbook() lists the pages a seat may read and reads one; the engine's defaults lie under the world's own folder;
each page's `for` names the roles and parts that may read it, and a page a seat may not read answers as one that
does not exist; the owner names a seat's parts on its grant; every briefing and invite page points at it."""

import pytest

from embody.ops import AUTHOR, Engine, Rejected


def hosted(tmp_path, manifest_extra=""):
    tmp_path.mkdir(parents=True, exist_ok=True)
    eng = Engine(tmp_path / "embody.db", workspace=tmp_path)
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.create_world("The Pit", id="the-pit")
    gm.spawn("creature", gm.world.root_id, "Mara", state={"playable": True})
    home = tmp_path / "worlds" / "the-pit"
    if manifest_extra:
        b = home / "build.py"
        b.write_text(b.read_text(encoding="utf-8").replace('"id": "the-pit",', '"id": "the-pit", ' + manifest_extra, 1),
                     encoding="utf-8")
    return eng, gm, home


def page(home, rel, text, folder="handbook"):
    f = home / folder / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def seat(eng, gm, role="mind", parts=None, label="Sam"):
    inv = gm.invite(role, entity="Mara" if role == "mind" else None, label=label, parts=parts)
    return inv, eng.session_for_token(inv["token"])


def paths(s):
    return {p["path"] for p in s.handbook()["pages"]}


def test_a_seat_reads_the_index_and_only_the_pages_for_its_part(tmp_path):
    eng, gm, home = hosted(tmp_path)
    inv, sam = seat(eng, gm)
    hb = sam.handbook()
    assert hb["path"] == "SKILL.md" and hb["text"] and hb["role"] == "mind"
    assert "SEATS.md" in paths(sam) and not any(p.startswith("parts/") for p in paths(sam))
    assert "angel" not in str(hb).lower()  # the index never names a part nobody gave you
    with pytest.raises(Rejected) as hidden:
        sam.handbook("parts/angel.md")
    with pytest.raises(Rejected) as missing:
        sam.handbook("parts/no-such.md")
    assert hidden.value.reason.replace("angel", "X") == missing.value.reason.replace("no-such", "X")
    for bad in ("../build.py", "parts/../SKILL.md", "/etc/passwd", "SKILL.txt"):
        with pytest.raises(Rejected):
            sam.handbook(bad)


def test_the_owner_names_parts_and_they_open_their_pages(tmp_path):
    eng, gm, home = hosted(tmp_path)
    inv, angel = seat(eng, gm, role="author", parts=["angel"], label="Wings")
    assert inv["parts"] == ["angel"] and angel.who()["parts"] == ["angel"]
    assert "parts/angel.md" in paths(angel) and "parts/demon.md" not in paths(angel)
    assert angel.handbook("parts/angel.md")["text"]
    r = gm.set_parts(inv["id"], add=["demon"], remove=["angel"])
    assert r["parts"] == ["demon"]
    again = eng.session_for_token(inv["token"])
    assert "parts/demon.md" in paths(again) and "parts/angel.md" not in paths(again)
    assert {"parts/angel.md", "parts/demon.md"} <= paths(gm)  # the owner reads every page
    for bad in (["owner"], ["everyone"], ["Big Boss!"], ["a"] * 0 + [f"p{k}" for k in range(9)]):
        with pytest.raises(Rejected):
            gm.invite("player", label="X" + str(len(bad)), parts=bad)
    with pytest.raises(Rejected):
        again.set_parts(inv["id"], add=["angel"])  # an author does not hand out parts


def test_the_worlds_own_pages_lie_over_the_engines(tmp_path):
    eng, gm, home = hosted(tmp_path)
    page(home, "SKILL.md", "---\nname: handbook\n---\nThe Pit's own front page.\n")
    page(home, "parts/angel.md", "---\nname: angel\ndescription: The Pit's angel.\nfor: [angel]\n---\nPit angels.\n")
    page(home, "parts/demon.md", "---\nname: demon\nfor: []\n---\nnobody\n")  # this world has no demons
    page(home, "lore/keepers.md", "---\nname: keepers\ndescription: the keepers\n---\nstaff only\n")  # no for: staff
    page(home, "ways.md", "---\nname: ways\ndescription: how we play\nfor:\n  - mind\n  - player\n---\nwalk\n")
    inv, sam = seat(eng, gm)
    assert sam.handbook()["text"].startswith("The Pit's own front page") and sam.handbook()["from"] == "world"
    assert "ways.md" in paths(sam) and "lore/keepers.md" not in paths(sam)
    inv2, angel = seat(eng, gm, role="author", parts=["angel"], label="Wings")
    got = angel.handbook("parts/angel.md")
    assert got["text"].startswith("Pit angels") and got["from"] == "world"
    assert "lore/keepers.md" in paths(angel)  # an author reads the staff pages
    assert "parts/demon.md" not in paths(gm)  # hidden from everyone, the owner too
    big = "line\n" * 6000
    page(home, "long.md", "---\nname: long\nfor: [everyone]\n---\n" + big)
    two = sam.handbook("long.md", page=2)
    assert two["pages"] >= 2 and two["page"] == 2


def test_a_world_moves_or_turns_off_its_folder(tmp_path):
    eng, gm, home = hosted(tmp_path, manifest_extra='"handbook": "docs/agents",')
    page(home, "ways.md", "---\nname: ways\nfor: [everyone]\n---\nhere\n", folder="docs/agents")
    page(home, "ways2.md", "---\nname: ways2\nfor: [everyone]\n---\nnot here\n")
    inv, sam = seat(eng, gm)
    assert "ways.md" in paths(sam) and "ways2.md" not in paths(sam)
    eng2, gm2, home2 = hosted(tmp_path / "off", manifest_extra='"handbook": False,')
    page(home2, "ways.md", "---\nname: ways\nfor: [everyone]\n---\nhere\n")
    inv2, sam2 = seat(eng2, gm2)
    assert "ways.md" not in paths(sam2) and "SEATS.md" in paths(sam2)  # the engine's defaults stay
    eng3, gm3, home3 = hosted(tmp_path / "out", manifest_extra='"handbook": "../../",')
    inv3, sam3 = seat(eng3, gm3)
    assert all(p["from"] == "engine" for p in sam3.handbook()["pages"])  # never outside the world's folder


def test_every_briefing_and_invite_page_points_at_the_handbook(tmp_path):
    eng, gm, home = hosted(tmp_path)
    inv, sam = seat(eng, gm, parts=["guide"])
    assert "handbook()" in inv["page"] and "guide" in inv["page"]
    b = sam.join()["briefing"]
    assert b["parts"] == ["guide"] and any("handbook()" in h and "your parts here: guide" in h for h in b["how"])
    assert "handbook()" in gm.guide()["world_guides"]
