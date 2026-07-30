---
name: debug-nano-yaml-corruption
description: Pasting YAML into nano on the remote box eats `- ` list markers and adds autoindent — use flow style, sed the indent, and validate before restarting cloudflared
metadata:
  type: project
---

**증상:** 원격 세션의 nano로 `/etc/cloudflared/config.yml` 을 복붙 편집하면 리스트 마커 `- ` 가 사라지고
앞쪽에 불필요한 들여쓰기가 붙는다 (nano autoindent). 반복해서 당했다.

**해결 패턴:**

1. YAML flow 스타일로 한 줄에 쓴다 — `ingress: [...]` → 대시 깨짐 자체를 회피
2. 붙여넣기 후 들여쓰기 정리: `sudo sed -i 's/^  //' /etc/cloudflared/config.yml`
3. 적용 전 검증: `sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate`
4. 그 다음 `sudo systemctl restart cloudflared`

검증(3번)을 건너뛰고 restart하면 터널 전체가 죽는다. 순서를 지킨다.

관련: [[server-remote-access-jsangho]] · [[project-n8n-route-pending]]
