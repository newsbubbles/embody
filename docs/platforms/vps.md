# Hosting on a VPS (or a machine of your own)

A rented Linux server, or a machine at home, runs the embody container with Docker. Nothing in the engine needs a particular provider: docs/HOST_YOUR_WORLD.md is the general path, and this page is what a box of your own adds to it. Do steps 1 and 2 of that guide first (the world and the stage), then come back here for step 3.

The steps marked **(you)** need your own account, your browser or your money.

## What the box needs

- Linux with Docker. Any provider's smallest plan is a fair start; measure before you pay for more.
- One way to put HTTPS in front of it, from the three below. Caddy needs a domain and ports 80 and 443 open. Tailscale and Cloudflare open no ports, so they also work from a machine at home.

## Deploy one world

1. **(you)** Rent the box, or pick the machine, and install Docker on it.
2. Copy the stage there. From your machine: `rsync -a "<stage>/" <box>:my-world/` (or `scp -r`).
3. On the box, build, run and make your owner grant as in docs/HOST_YOUR_WORLD.md, "On your own machine": `docker build -t my-world ~/my-world`, the `docker run` line with `-p 127.0.0.1:8900:8900` (so only the HTTPS front below reaches the port), the health check, and `docker exec my-world embody --author --world my-world invite owner --label "<you>"`.
4. Put HTTPS in front (one of the three below), then check `curl https://<your address>/health` from anywhere. `EMBODY_URL` in the run line is that address plus `/mcp`.

To change the world later: stage again, copy it over, build, then `docker rm -f my-world` and the same `docker run` line. The volume keeps the state, and the boot renews the code against it.

## HTTPS, three ways

### Caddy, with your own domain

**(you)** Point an `A` record for your domain at the box's address, and open ports 80 and 443 in its firewall. Then one line gets the certificate and proxies to the container:

```bash
caddy reverse-proxy --from world.example.com --to 127.0.0.1:8900
```

To keep it running across reboots, put the same thing in `/etc/caddy/Caddyfile` and run Caddy as its system service:

```
world.example.com {
	reverse_proxy 127.0.0.1:8900
}
```

`EMBODY_URL` is `https://world.example.com/mcp`. Any other reverse proxy with TLS works the same way.

### Tailscale

**(you)** Install Tailscale on the box and sign it in to your tailnet. The address is `https://<device>.<tailnet>.ts.net`, with the certificate made for you (turn on HTTPS and MagicDNS for the tailnet if they are off).

- **Only your tailnet:** `tailscale serve --bg 8900`. Every player then needs Tailscale on the machine their agent runs on, and an agent hosted in someone's cloud cannot reach it. Good for a world among friends who share a tailnet.
- **The whole internet:** `tailscale funnel --bg 8900`. The first run asks you to approve Funnel for the tailnet. Funnel listens only on ports 443, 8443 and 10000, has bandwidth limits it does not publish, and names only `*.ts.net` addresses, not your own domain.

`--bg` keeps it on across reboots. `tailscale funnel status` shows what is shared; `tailscale funnel reset` stops it. `EMBODY_URL` is `https://<device>.<tailnet>.ts.net/mcp`.

### Cloudflare Tunnel

**(you)** Your domain's DNS must be on Cloudflare. Install `cloudflared` on the box, then:

```bash
cloudflared tunnel login
```

```bash
cloudflared tunnel create my-world
```

```bash
cloudflared tunnel route dns my-world world.example.com
```

Then a config file, `~/.cloudflared/config.yml`, with the id and the credentials file that `create` printed:

```
tunnel: <tunnel id>
credentials-file: /home/<you>/.cloudflared/<tunnel id>.json
ingress:
  - hostname: world.example.com
    service: http://127.0.0.1:8900
  - service: http_status:404
```

`cloudflared tunnel run my-world` runs it; `sudo cloudflared service install` keeps it running across reboots. `EMBODY_URL` is `https://world.example.com/mcp`.

**Set `EMBODY_WAIT_MAX=90` on the container** (`-e EMBODY_WAIT_MAX=90` in the run line). Cloudflare ends a proxied request that has no answer after about 100 seconds, and a `wait` holds its request open for as long as its timeout, up to 120 seconds by default. With the cap at 90, every wait answers before Cloudflare cuts it.

## Several worlds

Stage them together (`tools/stage_deploy.py --world one --world two --domain one.example=one`), build and run the stage as above: the container runs the hub (docs/HOSTING.md, "Many worlds on one server"). Give each domain its own line in the Caddyfile, its own `ingress` rule in the tunnel, or its own `route dns`, all to the same `127.0.0.1:8900`.

## Quirks

- **One container per volume.** The world is a SQLite file on `/data`. Two containers on the same volume, or two copies of one world on two boxes, write over each other.
- **`--restart unless-stopped`.** The container comes back after a reboot or a crash. Without it a reboot leaves the world down until you start it.
- **A boot that stops.** With no world to serve, or several and no choice, the boot stops with exit code 64 and a line saying what to set. `docker logs my-world` shows it.
- **Commands inside the container.** `docker exec my-world <command>` is the way in: use it for the owner grant, for `grants`, and for a load by hand (with `--hosted`).
- **A machine at home** sleeps, updates and loses power. A world on it is down when it is. Tailscale or Cloudflare give it an address, not an uptime.
