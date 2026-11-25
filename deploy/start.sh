#!/bin/sh
# The container's entry: make sure the world is in the database on the volume, then serve it.
#
#   EMBODY_DB      the database file (the Dockerfile sets /data/embody.db; mount a volume at /data)
#   EMBODY_WORKSPACE  the folder with worlds/ and packs/ (/app, this repository)
#   EMBODY_WORLD   the world to host: a folder name under worlds/ (my-world) or a path from the workspace
#                  (examples/ferry-at-dusk). Unset: the one in deploy/world (tools/stage_deploy.py writes it), else
#                  the only folder under worlds/ with a build.py; with none or several, it stops and says so.
#   EMBODY_WORLDS  many worlds instead, comma-separated (my-world,other-world): `embody hub`, one database each
#   EMBODY_DOMAINS host=world,... for the hub (or /data/hub.json); a host it does not know goes to the first world
#   EMBODY_URL     the public URL printed into invites; when unset, a platform's own domain variable (docs/platforms/)
#   PORT           the port the platform routes to
#
# A first boot builds the world with `load --hosted` (the build's host(s) sets the hosted pace, seats' lapse and
# real-time timers). Every later boot runs `load --upgrade --hosted`: the current code against the same state, the
# timers left where they are. The clock of a world that runs while occupied starts with its first guest, not here.
set -eu
: "${PORT:=8900}"

# Many worlds (EMBODY_WORLDS=my-world,other-world): `embody hub` runs one server per world, each on its own
# database file under /data/worlds/, behind this one port. It moves the old /data/embody.db into the first world's
# file on its first boot (the old file stays) and builds or renews each world as below; a world that fails stays
# down and the others serve. src/embody/hub.py has the routing; EMBODY_DOMAINS (host=world,...) maps domains, and
# EMBODY_REMOTES (world=https://its-server,...) forwards a world that moved to its own server.
# tools/stage_deploy.py writes deploy/worlds (and deploy/domains) when it stages more than one world.
if [ -z "${EMBODY_WORLDS:-}" ] && [ -s deploy/worlds ]; then
    EMBODY_WORLDS=$(tr -d '\r' < deploy/worlds)
    export EMBODY_WORLDS
fi
if [ -z "${EMBODY_DOMAINS:-}" ] && [ -s deploy/domains ]; then
    EMBODY_DOMAINS=$(tr -d '\r' < deploy/domains)
    export EMBODY_DOMAINS
fi
if [ -z "${EMBODY_REMOTES:-}" ] && [ -s deploy/remotes ]; then
    EMBODY_REMOTES=$(tr -d '\r' < deploy/remotes)
    export EMBODY_REMOTES
fi
if [ -n "${EMBODY_WORLDS:-}" ]; then
    exec embody hub --port "$PORT" --log-level info
fi

if [ -z "${EMBODY_WORLD:-}" ] && [ -s deploy/world ]; then
    EMBODY_WORLD=$(tr -d '\r' < deploy/world)
fi
if [ -z "${EMBODY_WORLD:-}" ]; then
    found=""
    for b in worlds/*/build.py; do
        [ -f "$b" ] && found="$found ${b#worlds/}"
    done
    found=$(echo "$found" | sed 's|/build.py||g; s|^ ||')
    case "$found" in
        "")
            echo "no world to host: worlds/ has no world folder. Put yours in worlds/<id>/ and ship it with" >&2
            echo "tools/stage_deploy.py, or set EMBODY_WORLD=examples/ferry-at-dusk to host a sample." >&2
            exit 64 ;;
        *" "*)
            echo "which world? worlds/ holds: $found. Set EMBODY_WORLD to one of them (or EMBODY_WORLDS for all)." >&2
            exit 64 ;;
        *) EMBODY_WORLD=$found ;;
    esac
fi

# a name is the folder worlds/<name>; a path (examples/ferry-at-dusk) is that folder. Either way the world's id is
# the id in its build.py's WORLD manifest (the folder's name when it has none), as `embody load` makes it.
case "$EMBODY_WORLD" in
    */*) dir=$EMBODY_WORLD ;;
    *) dir=worlds/$EMBODY_WORLD ;;
esac
if [ ! -f "$dir/build.py" ]; then
    echo "no world at $dir: no build.py there. A fresh clone ships only the samples in examples/; your own world" >&2
    echo "goes in worlds/<id>/ and ships with tools/stage_deploy.py (docs/HOST_YOUR_WORLD.md)." >&2
    exit 64
fi
wid=$(python -c 'import ast, pathlib, sys
p = pathlib.Path(sys.argv[1])
m = next((n.value for n in ast.parse((p / "build.py").read_text(encoding="utf-8")).body if isinstance(n, ast.Assign)
          and any(getattr(t, "id", "") == "WORLD" for t in n.targets)), None)
print((ast.literal_eval(m).get("id") if m is not None else None) or p.resolve().name)' "$dir")
ref=$EMBODY_WORLD
: "${EMBODY_DB:=/data/embody.db}"

# One world, one database file, the same for the renew and for serve. A volume that has run `embody hub` keeps the
# world in the hub's own file, <folder of $EMBODY_DB>/worlds/<world>.db: the hub's first boot moved the world there
# and left the old $EMBODY_DB behind as it was, so that old file is stale and the hub's file is the world. The CLI
# picks the hub's file only for a call that names --world, and serve names none: a boot that left it to the CLI
# renewed the hub's file and served the stale one (2026-11-21, the Reach served ten days back). So the file is
# chosen here, once, and named on every call. EMBODY_DB set to the hub's file works the same.
db=$EMBODY_DB
hub_file="$(dirname "$EMBODY_DB")/worlds/$wid.db"
if [ -f "$hub_file" ]; then
    db=$hub_file
    echo "the world is in the hub's file $db; $EMBODY_DB is left as it is"
fi

if embody --db "$db" --json worlds | grep -q "\"id\": \"$wid\""; then
    echo "renewing $wid in $db"
    embody --db "$db" --author --world "$wid" load "$ref" --upgrade --hosted
else
    echo "building $wid ($ref) into $db"
    embody --db "$db" --author load "$ref" --hosted
fi
echo "hosting $wid; the first owner grant: embody --author --world $wid invite owner --label <you>"

# serve reads the world by its id, and its page from the folder's own site/ (where the folder is not worlds/<id>)
EMBODY_WORLD=$wid
export EMBODY_WORLD
if [ -z "${EMBODY_SITE:-}" ] && [ -d "$dir/site" ]; then
    EMBODY_SITE=$dir/site
    export EMBODY_SITE
fi

exec embody --db "$db" --author serve --http --host 0.0.0.0 --port "$PORT" --log-level info ${EMBODY_URL:+--url "$EMBODY_URL"}
