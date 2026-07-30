---
name: project-n8n-route-pending
description: "n8n container is stopped and has no Cloudflare Tunnel route; user wants it re-enabled later, not now"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7b227a90-cdda-4912-9e1e-71c6d8dc8ef4
  modified: 2026-07-22T02:24:41.193Z
---

n8n is intentionally stopped on the server PC (`DESKTOP-9E3A4EC`, SSH user `messi`) and `n8n.jsangho.cloud` has no ingress route in `/etc/cloudflared/config.yml`. The user asked (2026-07-22) to turn it back on and add the route only when n8n is actually needed again — not proactively.

**Why:** During a DNS/tunnel cleanup, api.jsangho.cloud and ssh.jsangho.cloud were consolidated onto the single locally-managed tunnel `jsangho.cloud` (ID `97481026-a36b-4026-be61-fc06a4035893`). n8n was left out because the user said it's not currently in use.

**How to apply:** When the user asks to bring n8n back:
1. On the server PC (via `ssh messi@ssh.jsangho.cloud`, or the remote-desktop session if the tunnel is down): `docker compose up -d n8n` (container `cloudjsanghoall-n8n-1` already exists, just stopped) and confirm it listens on `localhost:5678`.
2. Add an ingress entry to `/etc/cloudflared/config.yml` for `n8n.jsangho.cloud` → `http://localhost:5678`, before the `http_status:404` catch-all. Validate first with `sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate`, then `sudo systemctl restart cloudflared`.
3. Editing that config file via copy-paste into nano on that remote-desktop session has repeatedly corrupted leading `- ` list markers and added stray leading-space indentation (nano autoindent) — see [[server_remote_access_jsangho]] for the working pattern (YAML flow-style `ingress: [...]` on one line avoids the dash-corruption issue; `sudo sed -i 's/^  //'` fixes stray indent after paste).
4. No DNS change needed — `n8n.jsangho.cloud` Tunnel-type DNS record already exists pointing at this same tunnel.
