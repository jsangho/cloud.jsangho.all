# 로컬 개발 스택 — k3s

로컬 개발 스택은 **k3s**로 돈다. `docker-compose.yaml`은 제거됐다.

> **EC2 운영은 아직 docker compose다.** 이 문서는 로컬(WSL2)에만 적용된다.
> 서버 배포는 [`.claude/skills/deploy/SKILL.md`](../.claude/skills/deploy/SKILL.md)가 그대로 유효하다.

---

## 1. 구성

| 파일 | 역할 |
|------|------|
| `k8s/00-namespace.yaml` | 네임스페이스 `jsangho` |
| `k8s/10-storage.yaml` | PVC 3개 (pgadmin·n8n·hf-cache) |
| `k8s/2*.yaml` | 클러스터 안 도구 — pgadmin · n8n |
| `k8s/3*.yaml` | 앱 — backend · auth |
| `scripts/k3s-install.sh` | k3s 설치 + kubeconfig 병합 (최초 1회) |
| `scripts/k3s-up.sh` | 이미지 빌드 → 반입 → 시크릿 갱신 → apply |
| `fastapi/Dockerfile` | backend·auth 이미지. **k3s에서도 계속 필요하다** |
| `www/Dockerfile` | 프론트 이미지. compose 때도 쓰이지 않았고 지금도 스택 밖이다 |

**`kubectl apply -f k8s/…`를 직접 하지 않는다.** 매니페스트에 자리표시자가 있고 `k3s-up.sh`가 채운다.

| 자리표시자 | 채워지는 값 |
|---|---|
| `__REPO_ROOT__` | 저장소 절대경로 (backend·auth hostPath) |
| `__NODE_IP__` | k3s 노드 InternalIP (`host.docker.internal` hostAlias) |

자리표시자가 그대로 들어가면 hostPath가 없는 경로를 가리켜 파드가 뜨지 않는다.

**DB 주소를 채우는 자리표시자는 없다.** 상태 저장소는 외부 관리형 서비스(Neon)이고, 접속
주소는 전부 `fastapi/.env`의 URL이 정한다 (§4-2).

---

## 2. 최초 설치

Docker Desktop에서 건드릴 곳은 **정확히 두 군데**이고, 서로 반대 방향이다. 혼동하기 쉽다.

| 설정 | 위치 | 값 |
|---|---|---|
| Enable Kubernetes | Settings → **Kubernetes** | **끈다.** 켜면 6443 포트와 kubeconfig 컨텍스트가 k3s와 충돌한다 |
| WSL Integration | Settings → **Resources → WSL integration** | **켠다.** 이 배포판 토글을 켜야 `/var/run/docker.sock`이 생겨 `docker build`가 된다 |

둘은 무관하다 — WSL Integration을 켜도 Docker Desktop의 쿠버네티스는 켜지지 않는다.

```bash
scripts/k3s-install.sh   # systemd 확인 → k3s 설치 → 컨텍스트 'k3s' 등록
scripts/k3s-up.sh        # 첫 기동 (이미지 빌드 포함, 수 분 소요)
```

`--disable traefik`으로 설치한다. 이 스택은 Ingress를 쓰지 않고 `type: LoadBalancer`(k3s ServiceLB)로
노드 포트를 직접 잡아 compose의 `ports:` 매핑과 같은 결과를 낸다.

---

## 3. 일상 워크플로우

**원칙은 compose 때와 같다 — 코드 변경에 빌드는 필요 없다.** 저장소 전체가 hostPath로
`/app`에 마운트돼 있다(compose의 `.:/app`과 같은 자리).

| 무엇을 바꿨나 | 무엇을 하나 |
|---|---|
| 파이썬 코드 | `kubectl -n jsangho rollout restart deploy/backend` |
| `fastapi/.env` | `scripts/k3s-up.sh --no-build` (Secret은 파일에서 다시 만든다) |
| `pyproject.toml` · `uv.lock` | `scripts/k3s-up.sh` (이미지 재빌드) — **사용자가 요청할 때만** |
| 매니페스트 | `scripts/k3s-up.sh --no-build` |

`uvicorn`에 `--reload`가 없다. compose 때와 같은 이유로 **재기동해야 새 코드가 뜬다** —
`rollout restart`가 그 자리다. 붙이고 싶으면 `k8s/30-backend.yaml`의 `command`에 넣으면 되지만,
저장소가 커서 watcher가 CPU를 많이 먹는다.

### 새 패키지 임시 확인

`pyproject.toml`을 바로 고치지 말고 도는 파드에 먼저 넣어 본다. compose의 `exec` 자리다.

```bash
kubectl -n jsangho exec deploy/backend -- uv pip install <package>
```

**파드가 재생성되면 사라진다.** 그것을 이유로 먼저 빌드하지 않는다 (루트 `CLAUDE.md` Docker 워크플로우 §3~5와 같은 규칙).

### 자주 쓰는 명령 대응표

| compose | k3s |
|---|---|
| `docker compose ps` | `kubectl -n jsangho get pods` |
| `docker compose logs -f backend` | `kubectl -n jsangho logs -f deploy/backend` |
| `docker compose exec backend sh` | `kubectl -n jsangho exec -it deploy/backend -- sh` |
| `docker compose up -d` | `scripts/k3s-up.sh --no-build` |
| `docker compose restart backend` | `kubectl -n jsangho rollout restart deploy/backend` |
| `docker compose down` | `kubectl delete ns jsangho` (**PVC까지 지운다** — n8n·pgadmin·HF 캐시. Neon은 밖이라 무사하다) |
| `docker compose stop` | `kubectl -n jsangho scale deploy --all --replicas=0` |

데이터를 남기고 내리려면 `down`이 아니라 `scale --replicas=0`을 쓴다.

### 마이그레이션

```bash
kubectl -n jsangho exec deploy/backend -- sh -c 'cd /app/fastapi && alembic upgrade head'
```

자동 실행이 없는 것도 compose 때와 같다 — 엔트리포인트는 `uvicorn`뿐이다.

---

## 4. 포트

`type: LoadBalancer` 서비스가 노드 포트를 잡으므로 compose 때와 주소가 같다.

| 서비스 | 주소 | 비고 |
|---|---|---|
| backend | `localhost:8000` | |
| n8n | `localhost:5678` | |
| pgadmin | `localhost:5050` | |
| auth | 노출 안 함 | ClusterIP. `kubectl -n jsangho port-forward svc/auth 9000:9000` 로 본다 |
| PostgreSQL(Neon) | 클러스터 밖 인터넷 | 파드가 `.env`의 URL로 직접 붙는다. 로컬 포트가 없다 (§4-2) |

`auth`를 노출하지 않는 것은 compose와 같다. 서버의 고정 IP `172.28.0.2`(cloudflared 라우팅용)는
EC2 전용 구성이라 로컬로 옮기지 않았다.

### 4-2. 상태를 가진 것은 외부 관리형 서비스(Neon)에 있다

**k3s에는 앱만 올린다.** PostgreSQL은 **Neon**을 쓴다. 클러스터 안에도, 호스트 도커에도
DB가 없다 — 파드가 인터넷 너머의 Neon 엔드포인트로 직접 붙는다.

그래서 **DB용 Service도 EndpointSlice도 없다.** 이을 로컬 주소가 없기 때문이다. Neon은 DNS
이름과 TLS로 접속하므로 파드는 CoreDNS의 업스트림 해석만으로 닿는다. 접속 주소를 정하는
곳은 `fastapi/.env`의 URL 하나뿐이다.

```
파드 → CoreDNS(업스트림) → <ep>.neon.tech:5432 (TLS)
```

| 값 | 대상 | 비고 |
|---|---|---|
| `DATABASE_URL` · `PGVECTOR_URL` | Neon PostgreSQL | `sslmode=require` 필요 |
| `REDIS_URL` | 미정 | 코드는 `REDIS_HOST`/`REDIS_PORT`를 읽고 **호출 시점에** 접속한다 — 없어도 기동은 된다 |
| `NEO4J_URI` | 미정 | 드라이버가 지연 접속이라 없어도 기동은 된다 |

#### 더미 모드 — 지금 상태다

Neon URL이 아직 없어 네 값 모두 **빈 값**이다. 이게 의도된 통과 경로다:

```python
# core/matrix/grid_oracle_database_manager.py:107
engine = create_async_engine(...) if DATABASE_URL else None
# core/matrix/grid_oracle_database_manager.py:165
async def init_db(): 
    if engine is None:
        return
```

빈 값 → `engine is None` → `init_db()`가 즉시 return → **백엔드가 DB 없이 정상 기동한다.**
DB를 쓰는 엔드포인트만 503(`DATABASE_URL이 .env 등에 설정되지 않았습니다`)을 낸다.

URL을 받으면 `.env`에 채우고 `scripts/k3s-up.sh --no-build`로 Secret을 갱신한다.
`.env` 파일만 고치는 것으로는 반영되지 않는다.

#### 잘못된 URL이 왜 위험한가 — `create_all`은 기동만 해도 나간다

`fastapi/main.py`의 lifespan이 기동할 때마다 `init_db()`를 부르고, 그 안에서 이걸 돌린다:

```python
# core/matrix/grid_oracle_database_manager.py:192
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

**앱이 뜨기만 해도 DDL이 나간다.** 수동 단계가 없다. 그래서 URL을 잘못 넣으면 "확인 전에
테이블이 생기는" 사고가 그대로 재현된다 — Neon 프로젝트를 여러 개 쓰면 더 쉽다.

| | 언제 | 무엇을 하나 |
|---|---|---|
| `create_all` | **파드 기동 시 자동** | `CREATE TABLE IF NOT EXISTS`. 기존 테이블을 지우거나 바꾸지 않고 행도 안 건드린다 — 손실이 아니라 오염이다 |
| `alembic upgrade head` | 수동 | 컬럼 삭제·타입 변경이 섞이면 **파괴적** |

`k3s-up.sh`가 적용 전에 네 값의 **호스트만 뽑아** 검사하고, 제거된 로컬 컨테이너 이름
(`pgvector`·`redis`·`limbo`·`totem`·`neo4j`)이 남아 있으면 거기서 멈춘다. 빈 값은 통과시킨다.
(문자열 검색이 아니라 호스트 추출인 이유: `redis://` 스킴 자체가 걸려 오탐한다.)

**운영 DB를 로컬 `.env`에 넣지 않는다.** 로컬 backend가 뜨는 순간 그쪽에 DDL이 나간다.
Neon은 브랜치를 뜰 수 있으니 개발용 브랜치를 따로 만들어 그 URL을 쓴다.

#### 확인

```bash
kubectl -n jsangho exec deploy/backend -- \
  python -c "from core.matrix.grid_oracle_database_manager import engine; print(engine)"
```

`None`이면 더미 모드, 엔진 객체가 찍히면 URL이 들어간 상태다.

---

## 5. 환경 변수

`fastapi/.env` **한 파일 그대로다.** `k3s-up.sh`가 그 파일로 Secret `app-env`를 만들고,
compose의 `env_file`과 같은 워크로드들(backend·auth·pgadmin·n8n)에 `envFrom`으로 주입한다.

**`.env`의 DB 접속 문자열은 Neon 엔드포인트를 가리키거나, 비어 있어야 한다** (§4-2).
`k3s-up.sh`가 적용 전에 검사하고 제거된 로컬 컨테이너 이름이면 멈춘다.

자격증명은 이제 클러스터가 만드는 값이 아니라 **Neon 콘솔이 발급한 값**이다 — 이 스택은
PostgreSQL을 띄우지 않으므로 `.env`에서 비밀번호를 바꿔도 Neon 쪽은 바뀌지 않는다.
맞추는 방향이 반대다. `POSTGRES_PASSWORD`·`NEO4J_AUTH`처럼 컨테이너 이미지가 직접 읽던
키들은 이제 아무것도 구동하지 않는다.

`OLLAMA_HOST`의 `host.docker.internal`은 k8s에 없는 이름이라 backend 파드의 `hostAliases`로
노드 IP에 매핑한다. `k3s-up.sh`가 실행 시점에 IP를 읽어 채운다.

**감수한 트레이드오프는 compose 때와 같다**: Secret 하나를 통으로 주입하므로 n8n 파드에도
`JWT_PRIVATE_KEY`·`GEMINI_API_KEY` 같은 앱 비밀값이 들어간다. 특히 n8n 워크플로는 이 값들을
`$env`로 읽을 수 있다. 분리하자는 제안을 다시 꺼내기 전에 사용자에게 확인한다.

---

## 6. 이미지가 왜 `imagePullPolicy: Never` 인가

k3s는 도커가 아니라 **containerd**를 쓴다. `docker build`로 만든 이미지는 k3s에 보이지 않으므로
`k3s-up.sh`가 `docker save | sudo k3s ctr -n k8s.io images import --all-platforms -`로 직접 넣는다. 레지스트리에는 없는
태그(`jsangho/backend:dev`)라 pull을 시도하면 `ErrImagePull`로 죽는다 — 그래서 `Never`다.

`sudo`가 필요한 것은 `k3s ctr`가 루트 소켓(`/run/k3s/containerd/containerd.sock`, 모드 660
root:root)을 쓰기 때문이다. 그래서 **빌드 경로는 사람이 직접 실행해야 한다** — 비밀번호를
물어보므로 TTY 없이 돌릴 수 없다.

### 6-2. 도커 의존은 이 두 줄이 전부다

DB가 Neon으로 나간 뒤, 이 스택이 도커를 쓰는 곳은 `k3s-up.sh`의 빌드 블록뿐이다.

```bash
docker build -t jsangho/backend:dev -f fastapi/Dockerfile .
docker save jsangho/backend:dev | sudo k3s ctr -n k8s.io images import --all-platforms -
```

`scripts/k3s-up.sh --no-build`은 이 블록을 건너뛰므로 **도커 없이 돈다.** 일상 작업
(코드 수정 → `rollout restart`, `.env` 수정 → `--no-build`)은 전부 도커가 필요 없다.

**도커에 새 의존을 추가하지 않는다.** 없앨 수도 있다 — nerdctl + buildkit을 k3s containerd에
직접 붙이면 `docker build`/`save`/`import`가 통째로 사라진다. 다만 nerdctl·buildkitd 설치가
새로 생기므로, 지금은 도커 쪽이 더 싸다고 보고 두 줄을 남겼다.

---

## 7. 중복 생성 금지

컨테이너 시절 규칙이 그대로 유효하다. 새 DB·백엔드 워크로드를 만들어 달라는 요청을 받아도
**곧바로 만들지 않는다.**

1. `kubectl -n jsangho get pods,svc,pvc` 로 같은 역할이 이미 있는지 확인
2. `k8s/` 매니페스트에 같은 이름·같은 이미지의 워크로드가 정의돼 있는지 확인
3. 겹치면 — 기존 것을 쓸지 / 내리고 새로 만들지 / 이름을 바꿔 별개로 둘지 사용자에게 묻는다
4. 겹치는 게 없을 때만 만든다

과거에 확인 없이 반복 생성해 `my-fastapi`·`my-www` 같은 정체불명 중복 컨테이너와, 서로 다른
자격증명으로 같은 도메인을 가리키는 중복 cloudflared 터널이 쌓였다. 전부 뒤늦게 정리해야 했다.

---

## 8. `ho` → `aws` 머지 주의 (중요)

**`aws` 브랜치에는 `docker-compose.yaml`이 살아 있어야 한다.** EC2 운영이 그 파일로 돌아간다
(서버 전용 `nginx`·`certbot`·`cloudflared` 포함).

이번에 `ho`에서 그 파일을 지웠으므로, `.claude/skills/deploy/SKILL.md` 절차대로
`git switch aws && git merge ho` 하면 **modify/delete 충돌**이 난다. 옳은 해결은 **서버 파일을
남기는 것**이다:

```bash
git checkout --ours docker-compose.yaml   # aws 쪽 파일을 되살린다
git add docker-compose.yaml
```

`git rm`으로 충돌을 "해결"하면 서버 스택이 통째로 내려간다.

---

## 9. WSL2에서 막힐 때

| 증상 | 원인·조치 |
|---|---|
| `k3s는 systemd가 필요하다` | `/etc/wsl.conf`에 `[boot] systemd=true` → PowerShell `wsl --shutdown` |
| `no context exists with the name: "k3s"` | `/usr/local/bin/kubectl`은 k3s 심볼릭 링크라 `KUBECONFIG`가 비면 `/etc/rancher/k3s/k3s.yaml`(컨텍스트 `default`)을 먼저 읽는다. `~/.bashrc`에 `export KUBECONFIG=$HOME/.kube/config` |
| `docker`가 `/var/run/docker.sock` 없다고 한다 | Docker Desktop → Resources → WSL integration 에서 이 배포판 토글이 꺼져 있다 (§2). Kubernetes 토글과 헷갈리지 않는다 |
| API 서버가 안 뜬다 | Docker Desktop의 Kubernetes가 켜져 있는지 확인 (6443 충돌) |
| `localhost:8000`이 안 열린다 | `kubectl -n jsangho get svc backend` 에 `EXTERNAL-IP`가 붙었는지 본다. `<pending>`이면 ServiceLB(klipper) 파드를 `kubectl -n kube-system get pods` 로 확인 |
| 파드가 `ErrImageNeverPull` | 이미지가 containerd에 없다. `sudo k3s ctr -n k8s.io images ls \| grep jsangho` 로 먼저 확인한다. **`-n k8s.io` 없이 반입하면 exit 0 로 끝나고도 아무것도 안 들어간다** — 실제로 한 번 겪었다 (§6). `--all-platforms`도 함께 필요하다 |
| `wsl --shutdown` 후 스택이 안 뜬다 | k3s는 systemd 서비스라 자동 기동한다. `sudo systemctl status k3s` 로 확인 |
