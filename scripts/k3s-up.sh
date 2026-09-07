#!/usr/bin/env bash
# 로컬 k3s에 개발 스택을 올린다. compose 시절의 `docker compose up -d` 자리다.
#
#   scripts/k3s-up.sh              이미지 빌드 + 시크릿 갱신 + 매니페스트 적용
#   scripts/k3s-up.sh --no-build   이미지는 그대로 두고 나머지만
#
# 상태를 가진 것(PostgreSQL 등)은 클러스터 밖 **외부 관리형 서비스**(Neon)에 있다.
# 호스트 도커에 DB 컨테이너를 두지 않으므로, 이 스크립트는 도커를 이미지 빌드에만 쓴다.
# 접속 주소는 전부 fastapi/.env 의 URL이 정한다 — 매니페스트에는 DB 주소가 없다.
#
# 코드만 고쳤다면 빌드가 필요 없다 — 저장소가 hostPath로 마운트돼 있다.
# 그때는 `kubectl -n jsangho rollout restart deploy/backend` 한 줄이면 된다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS=jsangho
IMAGE=jsangho/backend:dev
ENV_FILE="$REPO_ROOT/fastapi/.env"
BUILD=1
[[ "${1:-}" == "--no-build" ]] && BUILD=0

# --- 사전 확인 -------------------------------------------------------------
[[ -f "$ENV_FILE" ]] || { echo "fastapi/.env 가 없다. .env.example 를 보고 채운다." >&2; exit 1; }

# k3s의 kubectl 심볼릭 링크는 KUBECONFIG가 비어 있으면 /etc/rancher/k3s/k3s.yaml 을 먼저 읽는다.
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

ctx="$(kubectl config current-context)"
if [[ "$ctx" != "k3s" ]]; then
  echo "현재 kubectl 컨텍스트가 '$ctx' 다. 'kubectl config use-context k3s' 후 다시 실행한다." >&2
  exit 1
fi

# hostAliases에 넣을 노드 IP. fastapi/.env 의 OLLAMA_HOST(host.docker.internal)가 이걸 탄다.
NODE_IP="$(kubectl get node -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')"
[[ -n "$NODE_IP" ]] || { echo "노드 InternalIP를 못 읽었다. k3s가 떠 있는지 확인한다." >&2; exit 1; }

echo "REPO_ROOT=$REPO_ROOT"
echo "NODE_IP=$NODE_IP"

# --- .env 접속 대상 확인 ---------------------------------------------------
# 왜 경고가 아니라 중단인가: main.py 의 lifespan 이 기동마다 create_all 을 돌린다
# (core/matrix/grid_oracle_database_manager.py:192). 즉 앱이 뜨기만 해도 DDL이 나간다.
# 제거된 컨테이너 이름이 남아 있으면 파드가 DNS에서 죽고 크래시루프가 된다.
#
# 빈 값은 통과시킨다 — engine 이 None 이 되어 init_db() 가 즉시 return 하므로
# DB 없이 기동되고, DB를 쓰는 엔드포인트만 503을 낸다 (더미 모드).
echo "==> .env 접속 대상 확인"

# URL에서 호스트만 뽑는다. 정규식으로 'pgvector|redis'를 찾으면 redis:// 스킴 자체가 걸려 오탐한다.
url_host() {
  local v="${1#*://}"   # 스킴 제거
  v="${v##*@}"          # 자격증명 제거 (없으면 그대로)
  v="${v%%[:/]*}"       # 포트·경로 제거
  printf '%s' "$v"
}

stale=0
for key in DATABASE_URL PGVECTOR_URL REDIS_URL NEO4J_URI; do
  val="$(grep -m1 -E "^${key}=" "$ENV_FILE" | cut -d= -f2-)"
  if [[ -z "$val" ]]; then
    echo "  skip $key 비어 있음 — 해당 기능은 503으로 뜬다"
    continue
  fi
  host="$(url_host "$val")"
  case "$host" in
    # 로컬 도커에 있던 컨테이너 이름들. 이제 어느 쪽에도 존재하지 않는다.
    pgvector | redis | limbo | totem | neo4j)
      echo "  FAIL $key -> $host (존재하지 않는 로컬 컨테이너 이름)" >&2
      stale=1
      ;;
    *)
      echo "  ok   $key -> $host"
      ;;
  esac
done
if [[ "$stale" == "1" ]]; then
  cat >&2 <<'MSG'

fastapi/.env 가 로컬 도커 컨테이너 이름을 가리킨다. 그런 컨테이너는 없다.
DB는 외부 관리형 서비스(Neon)를 쓰기로 했으므로 둘 중 하나로 고친다:

  1) Neon URL 을 채운다
     DATABASE_URL=postgresql+psycopg://<user>:<pw>@<ep>.neon.tech/<db>?sslmode=require
  2) 아직 URL이 없으면 빈 값으로 둔다 (더미 모드 — DB 없이 기동)
     DATABASE_URL=

.env 를 고쳤으면 이 스크립트를 다시 돌려야 Secret 에 반영된다.
MSG
  exit 1
fi

# --- 1. 이미지 빌드 후 containerd로 반입 -----------------------------------
# k3s는 도커가 아니라 containerd를 쓴다. 도커로 빌드한 이미지는 보이지 않으므로
# save → ctr import 로 직접 넣고, 매니페스트는 imagePullPolicy: Never 로 pull을 막는다.
#
# 도커(Docker Desktop)가 필요한 곳은 여기뿐이다. --no-build 로 돌리면 도커 없이도 된다.
if [[ "$BUILD" == "1" ]]; then
  echo "==> 이미지 빌드: $IMAGE"
  docker build -t "$IMAGE" -f "$REPO_ROOT/fastapi/Dockerfile" "$REPO_ROOT"

  # 반입에 두 플래그가 **둘 다** 필요하다. 빠뜨리면 exit 0 로 끝나고도 아무것도 안 들어가서,
  # 파드가 ErrImageNeverPull 로 죽고 나서야 드러난다 (실제로 한 번 겪었다).
  #
  #   -n k8s.io        kubelet이 보는 containerd 네임스페이스. 기본값으로 두면 다른 곳에 들어간다.
  #   --all-platforms  Docker Desktop이 containerd 이미지 스토어(io.containerd.snapshotter.v1)를
  #                    쓰므로 빌드 결과가 단일 이미지가 아니라 manifest list + attestation이다.
  #                    플랫폼을 전부 받지 않으면 언팩되지 않는다.
  echo "==> k3s containerd 로 반입"
  docker save "$IMAGE" | sudo k3s ctr -n k8s.io images import --all-platforms -

  # 반입이 조용히 비는 경우가 있어 여기서 확인하고 끊는다.
  if ! sudo k3s ctr -n k8s.io images ls -q | grep -q "${IMAGE##*/}"; then
    echo "반입 후에도 containerd에 $IMAGE 가 없다. 아래로 직접 확인한다:" >&2
    echo "  sudo k3s ctr -n k8s.io images ls | grep jsangho" >&2
    exit 1
  fi
fi

# --- 2. 네임스페이스 · 시크릿 ----------------------------------------------
kubectl apply -f "$REPO_ROOT/k8s/00-namespace.yaml"

# compose의 env_file 을 그대로 옮긴 것이다. .env 는 git 제외라 매니페스트에 넣을 수 없어
# 적용 시점에 파일에서 만든다. .env 를 고쳤으면 이 스크립트를 다시 돌려야 반영된다.
echo "==> Secret/app-env 갱신 (fastapi/.env, $(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE")개 키)"
kubectl create secret generic app-env \
  --namespace "$NS" \
  --from-env-file="$ENV_FILE" \
  --dry-run=client -o yaml | kubectl apply -f -

# --- 3. 매니페스트 적용 -----------------------------------------------------
# 자리표시자를 채워서 넘긴다. 없는 파일에는 sed가 아무 일도 하지 않는다.
echo "==> 매니페스트 적용"
for f in "$REPO_ROOT"/k8s/[1-9]*.yaml; do
  sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
      -e "s|__NODE_IP__|$NODE_IP|g" \
      "$f" | kubectl apply -f -
done

# --- 4. 기동 대기 -----------------------------------------------------------
echo "==> rollout 대기"
for d in pgadmin n8n backend auth; do
  kubectl -n "$NS" rollout status "deploy/$d" --timeout=10m
done

kubectl -n "$NS" get pods,svc
echo
echo "backend  http://localhost:8000"
echo "n8n      http://localhost:5678"
echo "pgadmin  http://localhost:5050"
