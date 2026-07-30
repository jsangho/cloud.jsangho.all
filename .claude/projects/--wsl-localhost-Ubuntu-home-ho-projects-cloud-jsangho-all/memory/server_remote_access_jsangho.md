---
name: server-remote-access-jsangho
description: "Where the jsangho.cloud stack actually runs now (AWS EC2, not the old home-PC theory), SSH access path/keys, and how to reach pgAdmin/pgvector from the dev PC"
metadata: 
  node_type: memory
  type: project
  originSessionId: ed9c96cf-9fff-4705-bda5-645c56d2ced0
  modified: 2026-07-28T05:57:57.230Z
---

**Current truth (confirmed 2026-07-28 by SSH'ing in and running `docker ps`):** the jsangho.cloud docker-compose stack (nginx, auth, backend, n8n, certbot, cloudflared, pgadmin, redis, pgvector, neo4j — all under the `cloudjsanghoall-*` container name prefix) runs on an **AWS EC2 instance** in `ap-northeast-2` (Seoul), internal hostname `ip-10-0-0-178.ap-northeast-2.compute.internal`.

- SSH: `ssh aws-ec2` — alias unified on 2026-07-28 across **both** `C:\Users\hi\.ssh\config` (Windows/Git Bash) and WSL Ubuntu's `~/.ssh/config` (was `AWS-Ubuntu` on Windows, `aws` on WSL; now both `aws-ec2`). → `HostName 3.35.176.41` (Windows side) / `ec2-3-35-176-41.ap-northeast-2.compute.amazonaws.com` (WSL side, same IP), `User ec2-user`, key at `~/.ssh/jsangho-keypair.pem` (WSL) or `C:\Users\hi\.ssh\jsangho-keypair.pem` (Windows). Plain and working, no ProxyCommand/Cloudflare Access needed for this host.
- `docker ps` on that box shows `cloudjsanghoall-pgadmin-1` mapped `5050:80` and `cloudjsanghoall-pgvector-1` mapped `5432:5432`, both healthy — these are **not exposed to the internet** (no public URL/subdomain routes them), so `localhost:5050` on the dev PC only works while an SSH tunnel is open.
- **To view pgAdmin/pgvector from the dev PC**: `ssh -N -L 5050:localhost:5050 -L 5432:localhost:5432 aws-ec2`, then browse `http://localhost:5050` (login = `PGADMIN_EMAIL`/`PGADMIN_PASSWORD` from the EC2's `.env`; if those keys are absent the pgAdmin image default applies) or point a local Postgres client straight at `localhost:5432` (db `vectordb`, user `postgres`, password = `PGVECTOR_PASSWORD` from the EC2's `.env`). **자격 증명은 이 파일에 적지 않는다** — 이 디렉터리는 git에 커밋된다. 값이 필요하면 `ssh aws-ec2` 후 `.env` 에서 직접 읽는다. The tunnel is a normal foreground/background ssh process — it dies when that terminal/session closes; just re-open it when needed.
- `https://api.jsangho.cloud` (the actual API) is served through a separate Cloudflare Tunnel route and works independently of the above — confirmed reachable (307) even at times when `ssh.jsangho.cloud` was failing.

**Superseded (kept for context, do not trust as current):** an earlier memory claimed the stack ran on a second physical Windows PC (`DESKTOP-9E3A4EC`) with `dockerd`/`cloudflared`/`sshd` inside its own `Ubuntu` WSL2 distro, reached via `ssh messi@ssh.jsangho.cloud` (Cloudflare Access ProxyCommand). That path was hit-or-miss in this session (`websocket: bad handshake`) and, per the user, is **not** where things run — the EC2 box above is authoritative. If `ssh.jsangho.cloud` / `DESKTOP-9E3A4EC` comes up again, verify fresh with the user rather than assuming either old memory or this one is still accurate; infra clearly moved at least once already.

**How to apply:** If asked to fix/inspect jsangho.cloud infra or view pgvector data, SSH to `aws-ec2` first and run `docker ps`/`docker compose logs` there rather than assuming anything about a local Windows PC being "the server." The dev PC (`DESKTOP-2HAMSV3`, where Claude Code normally runs) has no Docker at all — but it does have a WSL2 Ubuntu distro (`wsl -d Ubuntu`) with its own separate `~/.ssh/config`, kept in sync with the Windows one for host aliases.
