---
name: deploy
description: |
  jsangho.cloud 백엔드를 AWS EC2에 배포합니다.
  aws 브랜치를 갱신하고 backend·auth 컨테이너를 재빌드·재기동합니다.
  "배포해줘" · "서버에 반영해줘" · "deploy" 요청 시 사용합니다.
allowed-tools:
  - Bash
  - Read
---

## 배포 대상 (2026-07-29 실측)

| 항목 | 값 |
|------|-----|
| 호스트 | AWS EC2, `ssh aws-ec2` (Windows·WSL 공용 alias) |
| 계정 | `ec2-user` (`ho`가 아니다) |
| 배포 디렉터리 | `/home/ec2-user/cloud.jsangho.all` |
| 체크아웃 브랜치 | **`aws`** (`main`이 아니다) |
| compose 파일 | 같은 디렉터리의 `docker-compose.yaml` — 로컬 파일과 **다르다** |
| 공개 진입점 | `https://api.jsangho.cloud` → cloudflared 터널 → `backend:8000` |
| apex 도메인 | `https://jsangho.cloud` · `www.jsangho.cloud` 는 **Vercel**(프론트)이 서비스한다. EC2가 아니다 |

서버 compose에만 있는 서비스: `nginx` · `certbot` · `cloudflared`.
로컬 `docker-compose.yaml`에는 이 셋이 없으므로, 로컬 파일로 서버 상태를 판단하지 않는다.

> 서버 nginx는 `server_name jsangho.cloud www.jsangho.cloud`로 설정돼 있지만 그 두 이름의 DNS는 Vercel을 가리킨다. 즉 이 nginx 블록은 사실상 도달하지 않는 죽은 설정이고, 백엔드 트래픽은 cloudflared 터널로 들어온다. nginx 설정을 근거로 공개 URL을 추론하지 않는다.

## 시작 전 필수 확인

**서버 `fastapi/.env` 에 인프라 키 5개가 있어야 한다.** compose 는 명령 대상이
`backend`·`auth` 뿐이어도 파일 전체를 먼저 검증한다. pgvector·neo4j·pgadmin·n8n 이
모두 `./fastapi/.env` 를 `env_file` 로 읽으므로, 키가 없으면 빈 값으로 기동해 인증이 깨진다.

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all/fastapi && grep -cE "^(POSTGRES_PASSWORD|NEO4J_AUTH|PGADMIN_DEFAULT_EMAIL|PGADMIN_DEFAULT_PASSWORD|N8N_ENCRYPTION_KEY)=" .env'
```

`5` 가 나와야 한다. 그보다 적으면 배포를 멈추고 사용자에게 알린다 — `.env` 는 git 제외라
로컬에서 채워 줄 수 없다. `POSTGRES_PASSWORD` 는 `DATABASE_URL` 의 비밀번호와,
`NEO4J_AUTH` 는 `neo4j/<NEO4J_PASSWORD>` 와 값이 같아야 한다.

서버에 예전 `fastapi/.env.infra` 가 남아 있으면 지금은 아무도 읽지 않는다. 지워도 되지만
배포 흐름에서 건드리지 않는다.

**서버 `docker-compose.yaml`에 커밋되지 않은 수정이 있다.** `aws` 브랜치에 `restart: alwats` 오타가 커밋돼 있고, 서버에서만 `always`로 고쳐 쓰는 상태다.

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && git status --short'
```

`M docker-compose.yaml`이 보이면 **`git checkout -- .` · `git reset --hard` · `git stash`를 쓰지 않는다.** 오타가 되살아나면 유효하지 않은 restart 정책으로 기동에 실패한다. 근본 해결은 오타 수정을 `aws` 브랜치에 커밋하는 것이고, 그 전까지는 `git pull`이 이 파일을 건드리지 않게 한다.

배포는 운영 환경을 바꾸는 되돌리기 어려운 작업이다. 아래를 실행하기 전에 **무엇을 배포하는지 요약해 사용자 확인을 받는다.** 이 스킬의 `allowed-tools`가 Bash를 미리 승인하므로 개별 명령에는 권한 프롬프트가 뜨지 않는다 — 확인 절차를 건너뛰면 안 되는 이유다.

이 스킬 호출은 CLAUDE.md Docker 워크플로우 §3 "빌드 금지"의 예외에 해당하되, 범위는 서버의 `backend`·`auth`로 한정한다.

## 절차

### 1. 로컬 게이트 통과

```bash
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports
```

실패하면 여기서 멈춘다. 배포하지 않는다.

### 2. `ho` → `aws` 반영

`ho`에서 작업하고 `main`·`messi`는 fast-forward로 맞추지만, **`aws`는 머지 대상이다** (서버 전용 compose 차이 때문에 ff가 되지 않는다).

```bash
git switch ho && git push origin ho
git switch aws && git merge ho && git push origin aws
git switch ho
```

`docker-compose.yaml`에서 충돌이 나면 서버 전용 서비스(nginx·certbot·cloudflared)를 **지우지 않고** 양쪽을 합친다.

### 3. 서버 갱신

중첩 인용이 자주 깨지므로 스크립트를 stdin으로 넘긴다.

```bash
cat > /tmp/deploy.sh <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
git fetch origin
git merge --ff-only origin/aws        # 서버 로컬 수정을 보존한다
docker compose build backend
docker compose up -d backend auth
EOF
ssh aws-ec2 bash -s < /tmp/deploy.sh
```

`--ff-only`가 거부되면 서버에 커밋되지 않은 변경이 더 있다는 뜻이다. 임의로 덮어쓰지 말고 사용자에게 보고한다.

> WSL에서 실행할 때 `/tmp`는 WSL 파일시스템이어야 한다. Git Bash의 `/tmp`는 별개 경로라 `ssh ... < /tmp/deploy.sh`가 파일을 찾지 못한다.

### 4. 검증

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && docker compose ps --format "{{.Service}} | {{.Status}}"'
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && docker compose logs --tail 40 backend'
curl -sS -o /dev/null -w 'api root: %{http_code}\n' https://api.jsangho.cloud/
```

`backend`·`auth`가 `Up`이고 `https://api.jsangho.cloud/`가 **200**이어야 완료다. 로그에 트레이스백이 있으면 배포 실패로 보고한다.

`/docs`로 확인하려면 인증을 거친다 — `/docs`는 auth 게이트웨이 뒤에 있어 **307 → `/docs/login?next=/docs`가 정상 응답**이다. 200을 기대하면 안 된다.

```bash
curl -sS -L -o /dev/null -w 'docs(리다이렉트 후): %{http_code}  %{url_effective}\n' https://api.jsangho.cloud/docs
```

컨테이너 내부에서 직접 확인하는 방법(터널·인증 우회):

```bash
ssh aws-ec2 "cd /home/ec2-user/cloud.jsangho.all && docker compose exec -T backend python -c \"import urllib.request;print(urllib.request.urlopen('http://localhost:8000/docs',timeout=10).status)\""
```

> `curl -I`(HEAD)는 쓰지 않는다. FastAPI가 이 라우트에서 HEAD를 허용하지 않아 **405**가 돌아오고, 상태를 오판하게 만든다.

### 5. 롤백

```bash
# 머지 이전 SHA를 미리 기록해 둔다
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && git log --oneline -5'
```

```bash
cat > /tmp/rollback.sh <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
git switch --detach <이전SHA>
docker compose build backend
docker compose up -d backend auth
EOF
ssh aws-ec2 bash -s < /tmp/rollback.sh
```

DB 마이그레이션을 포함한 배포라면 코드 롤백만으로 복구되지 않는다. 스키마 변경이 있었는지 먼저 확인한다.

## 알려진 문제

- **`.github/workflows/deploy-backend.yml`은 동작하지 않는다.** 결함 세 가지:
  1. `runs-on: self-hosted` — EC2에 러너가 없다 (`actions-runner` 디렉터리·서비스 모두 미발견)
  2. `cd ~/project/cloud.jsangho.all` — 실제 경로는 `/home/ec2-user/cloud.jsangho.all` (`project` 세그먼트 자체가 없다)
  3. 트리거가 `push: branches: [main]`인데 서버는 `aws` 브랜치를 쓴다

  배포는 위 수동 절차가 유일한 경로다. 워크플로우를 신뢰하지 않는다.
  실행 이력은 현재 PAT에 `actions` 스코프가 없어 확인할 수 없다 (`gh run list` → 403).

- **프론트(`www`)는 Vercel에 배포된다 — 이 스킬의 범위가 아니다.** `jsangho.cloud`·`www.jsangho.cloud` 응답 헤더가 `server: Vercel`이다. EC2의 `www` 디렉터리는 어떤 컨테이너도 쓰지 않는다. 프론트 배포 요청을 받으면 이 절차가 아니라 Vercel 쪽을 확인한다.

- `n8n` 컨테이너는 서버에서 계속 실행 중이다 (2026-07-27 기동).
