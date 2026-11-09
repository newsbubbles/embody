#!/bin/sh
# The container's entry: make sure the world is in the database on the volume, then serve it.
#
#   EMBODY_DB      the database file (the Dockerfile sets /data/embody.db; mount a volume at /data)
#   EMBODY_WORKSPACE  the folder with worlds/ and packs/ (/app, this repository)
#   EMBODY_WORLD   the world folder under worlds/ to host (glass-reach)
#   EMBODY_URL     the public URL printed into invites; when unset, https://$RAILWAY_PUBLIC_DOMAIN/mcp
#   PORT           the port the platform routes to
#
# A first boot builds the world with `load --hosted` (the build's host(s) sets the hosted pace, seats' lapse and
# real-time timers). Every later boot runs `load --upgrade --hosted`: the current code against the same state, the
# timers left where they are. The clock of a world that runs while occupied starts with its first guest, not here.
set -eu
: "${EMBODY_WORLD:=glass-reach}"
: "${PORT:=8900}"

if embody --json worlds | grep -q "\"id\": \"$EMBODY_WORLD\""; then
    echo "renewing $EMBODY_WORLD in $EMBODY_DB"
    embody --author --world "$EMBODY_WORLD" load "$EMBODY_WORLD" --upgrade --hosted
else
    echo "building $EMBODY_WORLD into $EMBODY_DB"
    embody --author load "$EMBODY_WORLD" --hosted
fi

exec embody --author serve --http --host 0.0.0.0 --port "$PORT" --log-level info ${EMBODY_URL:+--url "$EMBODY_URL"}
