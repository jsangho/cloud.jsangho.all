# 배포 파이프라인 복구 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `aws` 브랜치에 푸시하면 EC2의 `backend`·`auth`가 자동으로 재빌드·재기동되고, 실패 시 워크플로우가 빨간불로 알려주는 상태를 만든다.

**Architecture:** 현재 `deploy-backend.yml`은 세 가지 결함(러너 없음·존재하지 않는 경로·잘못된 브랜치)으로 한 번도 동작한 적이 없고, 배포는 수동 SSH가 유일한 경로다. 먼저 `aws` 브랜치에 커밋된 compose 오타를 고쳐 서버의 미커밋 드리프트를 없애고(자동화가 그 드리프트를 덮어쓰면 기동이 깨지므로 반드시 선행), 워크플로우를 서버 실체에 맞추고, EC2에 self-hosted 러너를 systemd 서비스로 등록한 뒤, 검증 단계를 워크플로우에 넣어 배포 성패가 CI 결과로 드러나게 한다.

**Tech Stack:** GitHub Actions (self-hosted runner) · Docker Compose v5.3.1 · Amazon Linux (systemd) · FastAPI · nginx

## Global Constraints

- 커밋 메시지: Conventional Commits, **한국어**, 제목 50자 이내 (`feat:` · `fix:` · `docs:` · `chore:`)
- 작업 브랜치는 `ho`. `main`·`messi`는 fast-forward로 맞춘다. **`aws`는 머지 대상이며 ff가 되지 않는다** (aws-only 커밋 15개 존재)
- 서버 접속: `ssh aws-ec2` / 계정 `ec2-user` / 배포 디렉터리 `/home/ec2-user/cloud.jsangho.all`
- 서버 체크아웃 브랜치는 `aws` (`main`이 아니다)
- 커밋·푸시는 사용자가 요청했을 때만 한다. 이 계획의 커밋 단계는 그 요청에 해당한다
- MD 문서는 `_docs/`에 둔다 (CLAUDE.md §0-4). 루트·앱 루트에 직접 두지 않는다
- 중첩 인용이 깨지므로 원격 명령은 **스크립트를 stdin으로** 넘긴다: `ssh aws-ec2 bash -s < /tmp/x.sh`
- WSL에서 실행할 때 `/tmp`는 WSL 파일시스템이어야 한다. Git Bash의 `/tmp`는 별개 경로다
- **`docker compose config -q`와 `docker compose up --dry-run`은 잘못된 `restart` 값을 검증하지 않는다** (둘 다 exit 0). 검증에 쓰지 않는다

## File Structure

| 파일 | 책임 | 변경 |
|------|------|------|
| `docker-compose.yaml` (`aws` 브랜치) | 서버 서비스 정의 10개(backend·nginx·certbot·auth·cloudflared·n8n·neo4j·redis·pgvector·pgadmin) | 29행 `restart: alwats` → `always` 수정 |
| `.github/workflows/deploy-backend.yml` | `aws` 푸시 → 서버 재배포 + 검증 | 트리거 브랜치·경로·스텝 전면 수정 |
| `/etc/systemd/system/actions.runner.*.service` (서버) | 러너 상시 구동 | 신규 (러너 스크립트가 생성) |
| `.claude/skills/deploy/SKILL.md` | 배포 런북 | "알려진 문제" 갱신, 자동 배포 절차 반영 |

`docker-compose.yaml`과 워크플로우는 함께 바뀌므로(경로·브랜치·서비스명 공유) 인접 태스크로 배치한다.

---

### Task 1: `aws` 브랜치 compose 오타 수정 및 서버 드리프트 제거

`aws` 브랜치 `docker-compose.yaml` 29행에 `restart: alwats`가 커밋돼 있고, 서버에서만 `always`로 고쳐 쓰는 미커밋 상태다. 자동 배포가 `git pull`로 이 파일을 덮어쓰면 nginx 재생성이 실패하므로 **다른 모든 태스크보다 먼저** 해결한다.

**Files:**
- Modify: `docker-compose.yaml:29` (`aws` 브랜치에서만)
- 서버: `/home/ec2-user/cloud.jsangho.all/docker-compose.yaml` (미커밋 수정을 커밋으로 승격)

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces: `origin/aws`의 `docker-compose.yaml`이 유효한 restart 정책을 가진다. 서버 워크트리의 `git status --short`가 **비어 있다**. Task 3의 러너가 `git pull --ff-only`로 안전하게 갱신할 수 있는 전제.

- [ ] **Step 1: 실패하는 검증을 먼저 확인한다 (오타가 실재함을 증명)**

WSL 파일시스템에 스크립트를 만든다.

```bash
cat > /tmp/t1-before.sh <<'EOF'
cd /home/ho/projects/cloud.jsangho.all
git fetch -q origin aws
echo -n "origin/aws alwats count: "
git show origin/aws:docker-compose.yaml | grep -c 'restart: alwats'
EOF
bash /tmp/t1-before.sh
```

Expected: `origin/aws alwats count: 1` — 오타가 원격에 존재한다.

- [ ] **Step 2: 그 값이 실제로 치명적임을 증명한다**

`config -q`와 `--dry-run`은 통과시키므로 Docker 데몬 검증을 직접 쓴다. 컨테이너를 **생성만** 하고 시작하지 않으며, 실패 시 아무것도 남지 않는다.

```bash
cat > /tmp/t1-proof.sh <<'EOF'
docker create --restart alwats --name probe-restart-invalid nginx:1.27-alpine 2>&1 | tail -2
echo "exit=${PIPESTATUS[0]}"
docker rm -f probe-restart-invalid 2>/dev/null || true
EOF
ssh aws-ec2 bash -s < /tmp/t1-proof.sh
```

Expected:

```
Error response from daemon: invalid restart policy: unknown policy 'alwats'; use one of 'no', 'always', 'on-failure', or 'unless-stopped'
exit=1
```

- [ ] **Step 3: `aws` 브랜치에서 오타를 수정한다**

```bash
cd /home/ho/projects/cloud.jsangho.all
git switch aws
git pull --ff-only origin aws
sed -i 's/^    restart: alwats$/    restart: always/' docker-compose.yaml
git --no-pager diff -- docker-compose.yaml
```

Expected diff:

```diff
   nginx:
     image: nginx:1.27-alpine
     container_name: nginx
-    restart: alwats
+    restart: always
```

- [ ] **Step 4: 수정이 반영됐는지 검증한다**

```bash
grep -c 'restart: alwats' docker-compose.yaml || echo "0 (없음 - 정상)"
grep -A1 'container_name: nginx' docker-compose.yaml | grep 'restart: always'
```

Expected: `alwats` 0건, `restart: always` 1건 출력.

- [ ] **Step 5: 커밋·푸시**

```bash
git add docker-compose.yaml
git commit -m "fix: nginx restart 정책 오타 수정 (alwats → always)"
git push origin aws
git switch ho
```

- [ ] **Step 6: 서버 드리프트를 제거한다**

서버의 미커밋 수정과 방금 푸시한 커밋의 내용이 **같으므로**, `git stash`나 `reset --hard` 없이 체크아웃으로 안전하게 정리된다. 내용이 다르면 중단하고 사용자에게 보고한다.

```bash
cat > /tmp/t1-server.sh <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
git fetch origin aws
echo "=== 서버 수정본과 원격 커밋이 동일한가? ==="
if git diff --quiet origin/aws -- docker-compose.yaml; then
  echo "IDENTICAL - 안전하게 정리 가능"
else
  echo "DIFFERENT - 중단하고 사람이 확인해야 함"
  git --no-pager diff origin/aws -- docker-compose.yaml
  exit 1
fi
git checkout -- docker-compose.yaml
git merge --ff-only origin/aws
echo "=== 워크트리 상태 (비어 있어야 정상) ==="
git status --short
EOF
ssh aws-ec2 bash -s < /tmp/t1-server.sh
```

Expected: `IDENTICAL`, 이어서 `git status --short`가 **아무것도 출력하지 않음**.

- [ ] **Step 7: 서버 서비스가 정상인지 확인한다**

```bash
cat > /tmp/t1-verify.sh <<'EOF'
cd /home/ec2-user/cloud.jsangho.all
docker compose ps --format '{{.Service}} | {{.Status}}'
EOF
ssh aws-ec2 bash -s < /tmp/t1-verify.sh
curl -sS -o /dev/null -w 'api root = %{http_code}\n' https://api.jsangho.cloud/
```

Expected: `nginx`·`backend`·`auth` 모두 `Up`, `/docs`가 `200`.

---

### Task 2: 워크플로우를 서버 실체에 맞게 수정

**Files:**
- Modify: `.github/workflows/deploy-backend.yml` (전체 재작성, 24행)

**Interfaces:**
- Consumes: Task 1이 만든 유효한 `origin/aws` compose 파일과 깨끗한 서버 워크트리
- Produces: `aws` 푸시에 트리거되고 `/home/ec2-user/cloud.jsangho.all`에서 동작하는 워크플로우 정의. Task 3의 러너가 이 잡을 집어간다. 잡 이름은 `deploy`, 러너 라벨은 `self-hosted`.

- [ ] **Step 1: 현재 파일의 결함 3개를 기록으로 확인한다**

```bash
cd /home/ho/projects/cloud.jsangho.all
cat .github/workflows/deploy-backend.yml
```

Expected — 아래 세 줄이 모두 잘못돼 있다.

```
branches: [main]                      # 서버는 aws 브랜치를 쓴다
runs-on: self-hosted                  # 러너가 존재하지 않는다
cd ~/project/cloud.jsangho.all        # project 세그먼트가 없다. 실제: /home/ec2-user/cloud.jsangho.all
```

- [ ] **Step 2: 워크플로우를 재작성한다**

```yaml
name: Deploy backend

on:
  push:
    branches: [aws]
    paths:
      - "fastapi/**"
      - "docker-compose.yaml"
  workflow_dispatch: {}

concurrency:
  group: deploy-backend
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: self-hosted
    timeout-minutes: 20
    steps:
      - name: Pull latest aws branch
        run: |
          set -euo pipefail
          cd /home/ec2-user/cloud.jsangho.all
          git fetch origin aws
          git merge --ff-only origin/aws

      - name: Rebuild and restart backend
        run: |
          set -euo pipefail
          cd /home/ec2-user/cloud.jsangho.all
          docker compose build backend
          docker compose up -d backend auth
```

바뀐 점: 트리거 `main` → `aws`, `cd` 경로를 절대 경로로, `git checkout main`·`git pull` → `merge --ff-only`(드리프트가 있으면 조용히 덮어쓰지 않고 실패), 중복이던 `docker compose restart backend` 제거(`up -d`가 이미 재생성한다), `concurrency`로 동시 배포 차단, `timeout-minutes`로 무한 대기 방지.

- [ ] **Step 3: YAML 문법을 검증한다**

> **함정:** YAML 1.1에서 `on:`은 boolean으로 파싱되므로 `yaml.safe_load` 결과의 키는 문자열 `'on'`이 아니라 `True`다. `d['on']`으로 접근하면 `KeyError`가 난다 (이 저장소에서 실측 확인).

```bash
cd /home/ho/projects/cloud.jsangho.all
uv run python - <<'PY'
import yaml
d = yaml.safe_load(open('.github/workflows/deploy-backend.yml'))
trigger = d.get('on', d.get(True))          # 'on' 키는 True로 파싱된다
print('branches:', trigger['push']['branches'])
print('runs-on:', d['jobs']['deploy']['runs-on'])
print('steps:', len(d['jobs']['deploy']['steps']))
PY
```

Expected:

```
branches: ['aws']
runs-on: self-hosted
steps: 2
```

- [ ] **Step 4: 경로가 서버에 실재하는지 교차 검증한다**

워크플로우에 적은 경로가 실제로 존재해야 한다.

```bash
cat > /tmp/t2-path.sh <<'EOF'
ls -d /home/ec2-user/cloud.jsangho.all && echo "PATH OK"
cd /home/ec2-user/cloud.jsangho.all && git branch --show-current
EOF
ssh aws-ec2 bash -s < /tmp/t2-path.sh
```

Expected: `PATH OK`, 이어서 `aws`.

- [ ] **Step 5: 커밋·푸시**

`ho`에 커밋한 뒤 `aws`로 머지한다. 이 시점에는 러너가 없어 워크플로우가 실행되지 않는다(Task 3에서 등록).

```bash
cd /home/ho/projects/cloud.jsangho.all
git switch ho
git add .github/workflows/deploy-backend.yml
git commit -m "fix: 배포 워크플로우 경로·브랜치 수정"
git push origin ho
git switch aws && git merge ho && git push origin aws
git switch ho
```

---

### Task 3: EC2에 self-hosted 러너 등록

저장소가 **private**이고 fork가 아니므로(확인: `gh repo view` → `visibility=PRIVATE`, `isFork=false`) 외부 fork PR이 러너에서 코드를 실행하는 공개 저장소 위험은 해당하지 않는다. 그래서 러너 설치를 택한다.

> **기각한 대안:** 워크플로우를 삭제하고 수동 SSH 배포만 유지하는 방안. 이미 문서화된 경로가 있어 안전하지만, "푸시하면 배포된다"는 목표를 달성하지 못한다. GitHub-hosted 러너에서 SSH로 접속하는 방안도 기각했다 — 보안 그룹에 GitHub IP 범위를 열고 배포 키를 시크릿으로 넣어야 해서 표면이 더 넓어진다.

**Files:**
- Create (서버): `/home/ec2-user/actions-runner/` (러너 배포본)
- Create (서버): `/etc/systemd/system/actions.runner.jsangho-cloud.jsangho.all.<name>.service` (`svc.sh install`이 생성)

**Interfaces:**
- Consumes: Task 2가 푸시한 `runs-on: self-hosted` 잡 정의
- Produces: `Idle` 상태의 러너. 이후 `aws` 푸시가 자동 배포된다. 러너는 `ec2-user`로 실행되며 `docker` 그룹 권한을 상속한다(`docker ps`가 sudo 없이 동작함을 확인).

- [ ] **Step 1: 러너가 없음을 확인한다 (실패 상태 기록)**

```bash
cat > /tmp/t3-before.sh <<'EOF'
ls -d /home/*/actions-runner /opt/actions-runner 2>/dev/null || echo "no actions-runner (expected)"
systemctl list-units --type=service --all --no-pager 2>/dev/null | grep -ciE 'actions.runner' || echo "no runner service (expected)"
id -nG ec2-user | tr ' ' '\n' | grep -x docker && echo "docker group OK"
EOF
ssh aws-ec2 bash -s < /tmp/t3-before.sh
```

Expected: `no actions-runner (expected)`, `no runner service (expected)`, `docker group OK`.

- [ ] **Step 2: 등록 토큰을 발급받는다 (사용자 작업)**

현재 PAT에는 `actions` 스코프가 없어 API로 발급할 수 없다(`gh run list` → HTTP 403). 브라우저에서 받는다.

`https://github.com/jsangho/cloud.jsangho.all/settings/actions/runners/new?arch=x64&os=linux`

페이지의 `./config.sh --token AAAA...` 값에서 토큰만 복사한다. **토큰은 1시간 후 만료되고 1회용이다.** 스크립트나 커밋에 남기지 않는다.

PAT를 고쳐서 CLI로 받고 싶다면 `actions:read`+`administration:write` 스코프를 추가한 뒤:

```bash
gh api -X POST repos/jsangho/cloud.jsangho.all/actions/runners/registration-token -q .token
```

- [ ] **Step 3: 러너를 설치·등록한다**

토큰을 환경변수로 전달해 스크립트 본문에 남지 않게 한다.

```bash
cat > /tmp/t3-install.sh <<'EOF'
set -euo pipefail
cd /home/ec2-user
mkdir -p actions-runner && cd actions-runner
VER="2.336.0"   # 2026-07-29 기준 최신
curl -sSLO "https://github.com/actions/runner/releases/download/v${VER}/actions-runner-linux-x64-${VER}.tar.gz"
tar xzf "actions-runner-linux-x64-${VER}.tar.gz"
rm -f "actions-runner-linux-x64-${VER}.tar.gz"
./config.sh --unattended --replace \
  --url https://github.com/jsangho/cloud.jsangho.all \
  --token "$RUNNER_TOKEN" \
  --name ec2-jsangho-cloud \
  --labels self-hosted,linux,x64 \
  --work _work
sudo ./svc.sh install ec2-user
sudo ./svc.sh start
EOF
ssh aws-ec2 "RUNNER_TOKEN=<붙여넣은토큰> bash -s" < /tmp/t3-install.sh
```

> 최신 러너 버전은 `https://github.com/actions/runner/releases/latest`에서 확인해 `VER`를 맞춘다. 버전이 오래되면 러너가 자체 업데이트를 시도한다.

Expected 마지막 부분:

```
√ Connected to GitHub
√ Runner successfully added
√ Runner connection is good
√ Settings Saved.
```

- [ ] **Step 4: 러너가 살아 있는지 검증한다**

```bash
cat > /tmp/t3-verify.sh <<'EOF'
cd /home/ec2-user/actions-runner
sudo ./svc.sh status | head -12
EOF
ssh aws-ec2 bash -s < /tmp/t3-verify.sh
```

Expected: `Active: active (running)` 및 `Listening for Jobs`.

GitHub 쪽에서도 확인한다.

```
https://github.com/jsangho/cloud.jsangho.all/settings/actions/runners
```

Expected: `ec2-jsangho-cloud` 가 **Idle**.

- [ ] **Step 5: 재부팅 후에도 살아남는지 확인한다**

```bash
ssh aws-ec2 'systemctl is-enabled "actions.runner.*" 2>/dev/null || sudo systemctl is-enabled $(systemctl list-units --type=service --all --no-pager | grep -o "actions\.runner\.[^ ]*service" | head -1)'
```

Expected: `enabled`. `disabled`면 `sudo systemctl enable <서비스명>`을 실행한다.

- [ ] **Step 6: 러너 디렉터리가 저장소에 섞이지 않는지 확인한다**

러너는 `/home/ec2-user/actions-runner`(저장소 밖)에 있으므로 영향이 없어야 한다.

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && git status --short && echo "(위가 비어 있으면 정상)"'
```

Expected: 출력 없음.

---

### Task 4: 배포 검증을 워크플로우에 넣고 자동 배포를 E2E로 확인

지금 워크플로우는 `docker compose up -d`가 성공하면 초록불이 된다. 컨테이너가 기동 직후 크래시해도 배포 성공으로 보인다. 검증 단계를 추가한다.

**Files:**
- Modify: `.github/workflows/deploy-backend.yml` (검증 스텝 추가)

**Interfaces:**
- Consumes: Task 3의 동작하는 러너, Task 2의 워크플로우 정의
- Produces: 배포 실패 시 워크플로우가 실패하는 파이프라인. 검증 기준은 `docker compose ps`의 `backend`·`auth` 상태와 `https://api.jsangho.cloud/`의 HTTP 200.

- [ ] **Step 1: 검증 스텝을 추가한다**

`Rebuild and restart backend` 스텝 **뒤에** 붙인다.

```yaml
      - name: Verify deployment
        run: |
          set -euo pipefail
          cd /home/ec2-user/cloud.jsangho.all

          for svc in backend auth; do
            status=$(docker compose ps --format '{{.Service}} {{.State}}' | awk -v s="$svc" '$1==s {print $2}')
            echo "$svc state: ${status:-MISSING}"
            [ "$status" = "running" ] || { echo "::error::$svc is not running"; exit 1; }
          done

          for i in $(seq 1 12); do
            code=$(curl -sS -o /dev/null -w '%{http_code}' https://api.jsangho.cloud/ || echo 000)
            echo "attempt $i: api root -> $code"
            [ "$code" = "200" ] && exit 0
            sleep 5
          done
          echo "::error::api.jsangho.cloud did not return 200 within 60s"
          docker compose logs --tail 50 backend
          exit 1
```

기동에 시간이 걸리므로 최대 60초까지 재시도하고, 실패 시 로그를 남긴다.

- [ ] **Step 2: 검증 로직을 서버에서 단독 실행해 본다**

워크플로우를 돌리기 전에 같은 명령이 현재 상태에서 통과하는지 본다.

```bash
cat > /tmp/t4-verify.sh <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
for svc in backend auth; do
  status=$(docker compose ps --format '{{.Service}} {{.State}}' | awk -v s="$svc" '$1==s {print $2}')
  echo "$svc state: ${status:-MISSING}"
  [ "$status" = "running" ] || { echo "FAIL: $svc"; exit 1; }
done
code=$(curl -sS -o /dev/null -w '%{http_code}' https://api.jsangho.cloud/ || echo 000)
echo "api root -> $code"
[ "$code" = "200" ] || exit 1
echo "VERIFY OK"
EOF
ssh aws-ec2 bash -s < /tmp/t4-verify.sh
```

Expected:

```
backend state: running
auth state: running
/docs -> 200
VERIFY OK
```

- [ ] **Step 3: YAML 문법을 재검증한다**

```bash
cd /home/ho/projects/cloud.jsangho.all
uv run python -c "import yaml; d=yaml.safe_load(open('.github/workflows/deploy-backend.yml')); print('steps:', [s['name'] for s in d['jobs']['deploy']['steps']])"
```

Expected:

```
steps: ['Pull latest aws branch', 'Rebuild and restart backend', 'Verify deployment']
```

- [ ] **Step 4: 커밋·푸시 (첫 자동 배포가 트리거된다)**

`docker-compose.yaml`이나 `fastapi/**`가 아닌 워크플로우 파일만 바뀌므로 `paths` 필터에 걸리지 않는다. 그래서 푸시 후 `workflow_dispatch`로 수동 기동해 E2E를 확인한다.

```bash
cd /home/ho/projects/cloud.jsangho.all
git switch ho
git add .github/workflows/deploy-backend.yml
git commit -m "feat: 배포 워크플로우에 기동 검증 단계 추가"
git push origin ho
git switch aws && git merge ho && git push origin aws
git switch ho
```

- [ ] **Step 5: 워크플로우를 수동 실행해 E2E를 확인한다**

`gh run list`는 PAT 스코프 부족으로 403이 난다. 웹 UI로 확인한다.

```
https://github.com/jsangho/cloud.jsangho.all/actions/workflows/deploy-backend.yml
```

`Run workflow` → 브랜치 `aws` 선택 → 실행.

Expected: 잡이 `ec2-jsangho-cloud` 러너에 배정되고 세 스텝 모두 초록불. `Verify deployment` 로그에 `/docs -> 200`.

실패하면 여기서 멈추고 로그를 보고한다. 러너가 잡을 집어가지 않으면 라벨 불일치(`runs-on: self-hosted` vs 러너 라벨)를 먼저 확인한다.

- [ ] **Step 6: 배포 후 서버 상태를 재확인한다**

```bash
ssh aws-ec2 bash -s < /tmp/t4-verify.sh
```

Expected: `VERIFY OK`.

---

### Task 5: 배포 런북(`deploy` 스킬) 갱신

`.claude/skills/deploy/SKILL.md`는 "워크플로우는 동작하지 않는다 · 수동 절차가 유일한 경로"라고 단정한다. Task 1~4가 끝나면 사실과 어긋나므로 갱신한다. 런북이 현실과 다르면 다음 배포에서 잘못된 판단을 유도한다.

**Files:**
- Modify: `.claude/skills/deploy/SKILL.md`

**Interfaces:**
- Consumes: Task 1~4의 결과 (동작하는 자동 배포, 드리프트 없는 서버)
- Produces: 자동 배포를 1차 경로로, 수동 SSH를 fallback으로 기술한 런북

- [ ] **Step 1: 갱신 대상 문장을 확인한다**

```bash
cd /home/ho/projects/cloud.jsangho.all
grep -n "동작하지 않는다\|유일한 경로\|alwats\|커밋되지 않은 수정" .claude/skills/deploy/SKILL.md
```

Expected: "알려진 문제" 절과 "시작 전 필수 확인" 절의 해당 줄들이 잡힌다.

- [ ] **Step 2: "시작 전 필수 확인" 절을 교체한다**

`restart: alwats` 드리프트 경고 전체를 아래로 바꾼다. Task 1에서 해소됐으므로 경고가 아니라 확인 절차로 남긴다.

````markdown
## 시작 전 필수 확인

서버 워크트리는 깨끗한 상태를 유지해야 한다. 자동 배포가 `git merge --ff-only`를 쓰므로 미커밋 변경이 있으면 배포가 **실패**한다(조용히 덮어쓰지 않는다).

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && git status --short'
```

출력이 있으면 서버에서 직접 수정한 내역이다. 내용을 확인해 `aws` 브랜치에 커밋으로 승격시킨 뒤 배포한다. `git reset --hard`·`git stash`로 지우지 않는다 — 과거 `restart: alwats` 오타처럼 서버에만 있는 핫픽스일 수 있다.
````

- [ ] **Step 3: 자동 배포를 1차 경로로 기술한다**

"절차" 절 맨 앞에 추가한다.

````markdown
### 0. 자동 배포 (기본 경로)

`aws` 브랜치에 `fastapi/**` 또는 `docker-compose.yaml` 변경이 푸시되면 EC2의 self-hosted 러너가 재빌드·재기동·검증까지 수행한다.

```bash
git switch ho && git push origin ho
git switch aws && git merge ho && git push origin aws
git switch ho
```

진행 상황: https://github.com/jsangho/cloud.jsangho.all/actions/workflows/deploy-backend.yml
(`gh run list`는 PAT에 `actions` 스코프가 없어 403이 난다.)

워크플로우가 초록불이면 배포 완료다. 아래 수동 절차는 러너가 죽었거나 워크플로우가 실패했을 때의 fallback이다.
````

- [ ] **Step 4: "알려진 문제" 절을 갱신한다**

워크플로우 결함 3개 항목을 삭제하고 아래로 교체한다.

````markdown
- **러너 장애 시 배포가 조용히 멈춘다.** 러너가 죽으면 잡이 큐에 남아 대기한다. 상태 확인:

  ```bash
  ssh aws-ec2 'cd /home/ec2-user/actions-runner && sudo ./svc.sh status | head -5'
  ```

  `active (running)`이 아니면 `sudo ./svc.sh start`로 되살리고, 그동안은 아래 수동 절차로 배포한다.
````

- [ ] **Step 5: 프론트·n8n 항목은 그대로 두고 문서를 검증한다**

```bash
cd /home/ho/projects/cloud.jsangho.all
grep -c "alwats" .claude/skills/deploy/SKILL.md
grep -n "자동 배포 (기본 경로)" .claude/skills/deploy/SKILL.md
```

Expected: `alwats` 언급은 1건(드리프트 사례 설명), "자동 배포 (기본 경로)" 1건.

- [ ] **Step 6: 커밋·푸시**

```bash
git add .claude/skills/deploy/SKILL.md
git commit -m "docs: 배포 런북에 자동 배포 경로 반영"
git push origin ho
git switch main && git merge --ff-only ho && git push origin main
git switch messi && git merge --ff-only ho && git push origin messi
git switch ho
```

---

## 실측 근거 (2026-07-29)

이 계획의 사실 관계는 EC2에 SSH로 접속해 읽기 전용으로 확인했다.

| 확인 항목 | 결과 |
|-----------|------|
| 서버 계정·경로 | `ec2-user` / `/home/ec2-user/cloud.jsangho.all` (compose 라벨 `com.docker.compose.project.working_dir`로 확정) |
| 체크아웃 브랜치 | `aws` (HEAD `d1a4f76` "Merge branch 'ho' into aws") |
| 서버 compose 서비스 | 10개 (로컬 `main`에 없는 `nginx`·`certbot`·`cloudflared` 포함) |
| 미커밋 드리프트 | `docker-compose.yaml` 1줄 (`alwats` → `always`) |
| `origin/aws` 오타 | 29행에 `restart: alwats` 잔존 |
| 브랜치 분기 | `origin/aws`에만 15커밋, `origin/ho`에만 5커밋 |
| self-hosted 러너 | 없음 (디렉터리·서비스 모두 미발견) |
| 저장소 공개 범위 | PRIVATE, fork 아님 |
| nginx 라우팅 | `server_name jsangho.cloud www.jsangho.cloud` → `proxy_pass http://backend:8000` — **단 그 두 이름의 DNS는 Vercel을 가리켜 이 블록은 도달하지 않는 죽은 설정이다.** 백엔드는 cloudflared 터널로 들어온다 |
| 공개 헬스체크 | `https://api.jsangho.cloud/` = **200**. `/docs`는 auth 게이트웨이 뒤라 **307 → `/docs/login?next=/docs`가 정상**이며 200이 아니다. `curl -I`(HEAD)는 405를 돌려주므로 쓰지 않는다 |
| Docker Compose | v5.3.1 |
| `restart` 값 검증 | `docker compose config -q`·`up --dry-run` 모두 exit 0(통과). `docker create --restart alwats`만 거부: `invalid restart policy: unknown policy 'alwats'` |
| `gh run list` | HTTP 403 (PAT에 `actions` 스코프 없음) |
