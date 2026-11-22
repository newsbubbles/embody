# Host your own world

From a fresh clone of this repository to a friend's agent playing in your world, on any machine or platform that runs a container. One world, one server, one database on a volume. Every step is a command an agent can run; the steps marked **(you)** need your own account, your browser or your money, so do them by hand or approve them.

docs/HOSTING.md is the long reference (invites, roles, seats, minds, the viewer). This page is the path.

## What you need

- `git` and `uv` (https://docs.astral.sh/uv/).
- A host that runs a container from a Dockerfile, keeps a volume, and gives the server a public HTTPS address: a machine with Docker and a domain name, or a platform that does those for you (docs/platforms/ has the ones we have written up).
- A world. Yours goes in `worlds/<id>/`. To try the path first, host a sample: `examples/ferry-at-dusk`.

## 1. Clone and make the world

```bash
git clone https://github.com/newsbubbles/embody
cd embody
uv sync --extra mcp
```

Your world is a folder `worlds/<id>/` with a `build.py` (and `scripts/`). Start from a sample:

```bash
cp -r examples/ferry-at-dusk worlds/my-world
```

Then open `worlds/my-world/build.py` and set `"id": "my-world"` in its `WORLD` manifest. The folder name and the id must be the same. Your agent can also build one from nothing with `create_world`; the `embody` skill in `.claude/skills/embody/` has the author's guide.

Before you host it:

- Mark the bodies a guest may take with `playable: true`, and give the root a `briefing` paragraph (what `join` hands every newcomer).
- Give the build a `host(s)` function if the world should keep real time: it sets the pace, the seats' lapse and the timers (docs/HOSTING.md, "The path"). Without one the world is hosted as it is, with its clock paused.
- Try it on your own machine:

```bash
uv run embody --author load my-world --hosted
uv run embody --author serve --http --port 8900
```

`curl http://127.0.0.1:8900/health` answers `{"ok": true, "embody": "up"}`. Stop the server with Ctrl+C. The local database (`embody.db`) never ships.

## 2. Stage it

```bash
uv run python tools/stage_deploy.py --world my-world
```

It writes a stage folder: the engine as committed (`git archive HEAD`), your world copied from `worlds/my-world/` as it is on disk (without its dot-files, `mirror/` and databases), and `deploy/world` naming the world, so the container needs no variable to find it. It prints the stage's path, the `docker build` line, and the upload line for each platform written up in docs/platforms/. For the sample, `--world examples/ferry-at-dusk`.

Why a stage: git ignores `worlds/` (only `worlds/put_worlds_here.txt` is tracked), and a build or upload that follows `.gitignore` (most platforms' CLIs do) leaves everything git ignores behind, so your world would not ship.

## 3. Run the container

Whatever runs it, the container needs five things from its host:

- **A volume on `/data`.** The database lives there (`EMBODY_DB=/data/embody.db`). Without it every restart starts a fresh world and every grant is gone.
- **A port.** The server listens on `$PORT` (8900 when unset). A platform that sets `PORT` itself routes to it; elsewhere set it and publish the same port.
- **HTTPS in front.** The bearer token travels in a header, so a public host needs TLS. A platform usually gives it; on your own machine a reverse proxy does.
- **Its public address.** `EMBODY_URL=https://<your.domain>/mcp`, so an invite made from the command line (your owner grant) carries a link. An invite made over the door uses the host it was asked on either way.
- **A way to run a command inside it.** Your owner grant is made by the hosting process itself, against the live database.

Point the host's health check at `GET /health`. The image holds nothing secret: tokens are made after the deploy.

### On your own machine (any Docker host)

Build the stage (or the clone itself: the Dockerfile copies `worlds/`, and `.dockerignore` does not drop it), run it with a volume on `/data`, and put TLS in front.

```bash
docker build -t my-world "<stage>"
```

```bash
docker run -d --name my-world --restart unless-stopped -p 127.0.0.1:8900:8900 -e PORT=8900 -e EMBODY_URL=https://world.example.com/mcp -v my-world-data:/data my-world
```

```bash
curl http://127.0.0.1:8900/health
```

It answers `{"ok": true, "embody": "up"}`. The container's log says `building my-world (my-world) into /data/embody.db` on the first boot and `renewing my-world` on every later one. Then your owner grant:

```bash
docker exec my-world embody --author --world my-world invite owner --label "<you>"
```

It prints a link and one line (the paste). Paste it into your own agent. The token is shown once and is never in the image, the logs or the repository.

TLS: with Caddy it is one line, `caddy reverse-proxy --from world.example.com --to 127.0.0.1:8900`, which also gets the certificate. Any reverse proxy works. docs/platforms/vps.md has this on a rented server or a machine at home, with two more fronts that open no ports: Tailscale and Cloudflare Tunnel. To host a sample without staging, add `-e EMBODY_WORLD=examples/ferry-at-dusk`.

To change the world later: edit `worlds/my-world/`, stage again, build and run the new image on the same volume. The volume keeps the state, and the boot renews the code against it (`load --upgrade --hosted`).

### On a platform

A platform that builds a Dockerfile and mounts a volume runs the same container. Give it the five things above in its own terms. Written up so far:

- docs/platforms/railway.md: Railway.

## 4. Invite a friend

Your agent now holds the owner grant. Ask it: "invite Sam as a player" (or as a named character: "invite Sam as the ferryman"). It calls `invite` and hands you the paste. Send that to Sam. Sam drops the link into their agent; the agent reads the page at the link (the server address, the token, who they are), adds the server, calls `join()` and plays. Sam needs no clone, no install and no account.

`grants()` lists who holds what, `revoke(id)` ends a grant, `seats()` shows what is open. docs/HOSTING.md, "Invites", has the rest.

## Quirks we hit

- **Upload the stage, not the clone.** git ignores `worlds/`, and an upload that follows `.gitignore` leaves your world behind. The stage carries it.
- **No Docker `VOLUME` line.** Some platforms refuse an image that declares one, so the Dockerfile only makes `/data`, and the volume is the host's: `-v <name>:/data` on Docker, the platform's own volume elsewhere.
- **`EMBODY_URL`.** With no `EMBODY_URL` (and no platform domain variable the server knows, docs/platforms/), an invite made from the command line has no link and the paste is the whole page. Set it and restart.
- **A world is loaded with `--hosted`.** `deploy/start.sh` always does. The build's `host(s)` (pace, lapse, real-time timers) runs only with it, so a load you run by hand inside the container needs it too.
- **Which world the container serves.** `EMBODY_WORLD` when set (a name under `worlds/`, or a path like `examples/ferry-at-dusk`), else the one in the stage's `deploy/world`, else the only folder under `worlds/` with a `build.py`. With none, or several and no choice, the boot stops with exit code 64 and a line saying what to set.
- **A volume that once ran the hub.** The hub's first boot moved the world into `/data/worlds/<id>.db` and left `/data/embody.db` behind, stale. `start.sh` then renews and serves the hub's file, and says so at boot; a command you run by hand with `--world` picks the same file. A fresh volume has only `/data/embody.db`.
- **The owner grant comes from inside.** Only the hosting process (`docker exec`, or the platform's way in) makes an owner grant. An owner over the door hands on author at most.
- **A link opens once.** The page behind an invite link lives 24 hours and goes away with the token's first use over the door. A second fetch after that answers that it is gone; ask your agent to `relink` or make a new invite.
