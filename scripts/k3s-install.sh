#!/usr/bin/env bash
# WSL2에 k3s를 설치하고 kubeconfig를 병합한다. 최초 1회만 실행한다.
#
# 사전 조건: Docker Desktop 설정 > Kubernetes 의 "Enable Kubernetes" 가 꺼져 있어야 한다.
#            켜져 있으면 6443 포트와 kubeconfig 컨텍스트가 충돌한다.
set -euo pipefail

if [[ "$(ps -p 1 -o comm=)" != "systemd" ]]; then
  echo "k3s는 systemd가 필요하다. /etc/wsl.conf 에 [boot] systemd=true 를 넣고" >&2
  echo "PowerShell에서 'wsl --shutdown' 후 다시 들어온다." >&2
  exit 1
fi

if command -v k3s >/dev/null 2>&1; then
  echo "k3s가 이미 설치돼 있다: $(k3s --version | head -1)"
else
  # traefik은 끈다 — 이 스택은 Ingress를 쓰지 않고 LoadBalancer(ServiceLB)로 호스트 포트를 잡는다.
  # servicelb·local-path는 그 LoadBalancer와 PVC에 필요하므로 남긴다.
  curl -sfL https://get.k3s.io \
    | INSTALL_K3S_EXEC="--disable traefik --write-kubeconfig-mode 644" sh -
fi

sudo systemctl enable --now k3s
until sudo k3s kubectl get nodes >/dev/null 2>&1; do
  echo "k3s API 대기 중..."
  sleep 3
done

# k3s.yaml의 cluster/user/context 이름이 전부 'default'라 그대로 병합하면 뭘 가리키는지 알 수 없다.
mkdir -p "$HOME/.kube"
tmp_k3s="$(mktemp)"
tmp_merged="$(mktemp)"
trap 'rm -f "$tmp_k3s" "$tmp_merged"' EXIT

# cluster/user/context/current-context 가 모두 '<키>: default' 형태라 한 줄로 전부 잡힌다.
sudo cat /etc/rancher/k3s/k3s.yaml | sed 's/: default$/: k3s/' > "$tmp_k3s"
KUBECONFIG="$HOME/.kube/config:$tmp_k3s" kubectl config view --flatten > "$tmp_merged"
cp "$tmp_merged" "$HOME/.kube/config"
chmod 600 "$HOME/.kube/config"

# /usr/local/bin/kubectl 은 k3s 심볼릭 링크다. KUBECONFIG가 비어 있으면 ~/.kube/config 가
# 아니라 /etc/rancher/k3s/k3s.yaml(컨텍스트 이름이 'default')을 먼저 읽는다. 명시적으로 잡는다.
export KUBECONFIG="$HOME/.kube/config"
kubectl config use-context k3s
kubectl get nodes -o wide

echo
echo "셸에 다음 줄을 넣는다 (없으면 kubectl이 k3s.yaml을 직접 읽어 컨텍스트가 'default'로 보인다):"
echo "  echo 'export KUBECONFIG=\$HOME/.kube/config' >> ~/.bashrc"
echo
echo "완료. 다음: scripts/k3s-up.sh"
