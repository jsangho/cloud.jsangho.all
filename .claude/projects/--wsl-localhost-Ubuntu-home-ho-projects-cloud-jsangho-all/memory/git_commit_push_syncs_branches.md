---
name: git-commit-push-syncs-branches
description: "커밋하고 푸시해줘" always means commit/push to ho, then fast-forward sync main+messi, then merge ho into aws too
metadata:
  type: feedback
---

When the user says "커밋하고 푸시해줘" (commit and push), always: commit to the `ho` branch, push to `origin/ho`, then fast-forward `origin/main` and `origin/messi` to match (`git push origin ho:main` and `git push origin ho:messi`), and fast-forward the local `main` branch too.

**Why:** Confirmed explicitly 2026-07-21 after doing a one-off sync of main/messi to ho — the user wants this bundled into the routine commit/push request every time, not just on request.

**How to apply:**
- `ho` is this machine's working branch; `messi` is another machine's (ssh remote) branch; `main` is the shared main branch. All three are expected to stay in lockstep.
- Only fast-forward — if `origin/main` or `origin/messi` has diverged (has commits not in `ho`), stop and ask the user rather than force-pushing or merging automatically.
- This applies to `\\wsl.localhost\Ubuntu\home\ho\projects\cloud.jsangho.all` (repo `jsangho/cloud.jsangho.all`). The Bash tool needs `safe.directory` registered for the UNC path — already added to global git config as of 2026-07-21.

**`aws` branch is different — merge, not fast-forward (confirmed 2026-07-28):** `aws` carries its own deployment-only commits (`docker-compose.yaml`, `nginx.conf`, `cloudflared/config.yml` for the [[server_remote_access_jsangho|AWS EC2 box]]) that never belong on `ho`/`main`. Don't fast-forward-push over it — instead `git checkout aws && git merge ho -m "Merge branch 'ho' into aws" && git push origin aws && git checkout ho`. This is now the routine step after every `ho` push in this repo (done repeatedly 2026-07-28 alongside deploying each fix to the EC2 box), not a one-off — extend the "commit and push" routine to include it unless the user says otherwise.
