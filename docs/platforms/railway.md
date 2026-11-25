# Hosting on Railway

Railway is one platform that runs the embody container. Nothing in the engine needs it: docs/HOST_YOUR_WORLD.md is the general path, and this page is only what is Railway's own. Do steps 1 and 2 of that guide first (the world and the stage), then come back here for step 3.

The steps marked **(you)** need your own account, your browser or your money.

## What Railway reads from the repository

- `Dockerfile`: Railway builds it as any Docker host would.
- `railway.json`: the Dockerfile builder, `GET /health` as the health check, restart on failure, never asleep. Other platforms ignore the file.

## Deploy one world

1. **(you)** `railway login`
2. **(you)** `railway init --name my-world` makes the project (it may ask for a workspace or a plan). For an existing one, `railway link`.
3. `railway add --service my-world`, then `railway service link my-world`.
4. `railway volume add -m /data`. Without the volume every deploy starts a fresh world and every grant is gone.
5. `railway domain` prints `https://<name>.up.railway.app`. Make it before the first deploy so the server knows its own address.
6. `railway up "<stage>" --path-as-root --no-gitignore --ci`, with the stage path `tools/stage_deploy.py` printed. The deploy log says `building my-world (my-world) into /data/embody.db` on the first boot and `renewing my-world` on every later one. `railway logs` shows it.
7. `curl https://<name>.up.railway.app/health` answers `{"ok": true, "embody": "up"}`.
8. Your owner grant, made inside the container so it lands in the live database:

```bash
railway ssh -- embody --author --world my-world invite owner --label "<you>"
```

It prints the paste. Paste it into your own agent. The token is shown once and is never in the image, the logs or the repository. From here, step 4 of docs/HOST_YOUR_WORLD.md (invite a friend) is the same on every host.

To change the world later: edit `worlds/my-world/`, stage again, `railway up` the new stage. The volume keeps the state, and the boot renews the code against it.

## Your own domain

`railway domain <your.domain>` prints the DNS records to add at your registrar. Once it verifies, `railway variable set EMBODY_URL=https://<your.domain>/mcp` so every new link uses it, whichever host it was minted on. Links already out keep working on both hosts. Railway puts TLS in front of every domain it serves.

## Several worlds

Stage them together (`tools/stage_deploy.py --world one --world two --domain one.example=one`) and `railway up` the stage as above: the container runs the hub (docs/HOSTING.md, "Many worlds on one server"). Add each domain to the same service with `railway domain <domain>`.

A world that should keep its own engine version and its own restarts gets its own service: `railway add --service <world>`, a volume at `/data` on it, `railway up <its stage> --service <world> --path-as-root --no-gitignore --ci`, and `railway domain --service <world>`. The hub's stage then names it with `--remote <world>=https://<its domain>` (docs/HOSTING.md, "A world on its own server").

## Quirks

- **No Docker `VOLUME` line.** Railway refuses an image that declares one, so the Dockerfile only makes `/data`, and the volume is Railway's: `railway volume add -m /data`.
- **`--path-as-root --no-gitignore`.** `--no-gitignore` keeps `worlds/` in the upload (git ignores it); `--path-as-root` makes the stage folder the build's root instead of the folder you ran the command in. Both are needed. A plain `railway up` from the clone leaves your world behind.
- **`PORT` is Railway's.** Railway sets it, and the server listens on whatever it is given. Do not set it yourself.
- **`RAILWAY_PUBLIC_DOMAIN`.** An invite made from the CLI (the owner grant) needs the public address: `EMBODY_URL` when set, else `https://$RAILWAY_PUBLIC_DOMAIN/mcp`, which Railway sets once the service has a domain. If the owner invite prints no link, set `EMBODY_URL` and deploy again.
- **A boot that stops.** With no world to serve, or several and no choice, the boot stops with exit code 64 and a line saying what to set. Railway retries five times, then gives up. `railway logs` shows the line.
- **Commands inside the container.** `railway ssh -- <command>` is the platform's way in: use it for the owner grant, for `grants`, and for a load by hand (with `--hosted`).
