---
name: workflow-docker-dev
description: Never run docker build unless the user literally says "빌드해줘" — code changes need no build (volume mount), and new packages get tested via `docker compose exec` first
metadata:
  type: feedback
---

Docker 빌드는 **사용자가 "빌드해줘"라고 직접 말했을 때만** 실행한다.

**Why:** 저장소 루트 전체가 볼륨 마운트(`.:/app`)되어 있어 코드 변경은 빌드 없이 즉시 반영된다.
패키지가 추가됐거나 `pyproject.toml`/`uv.lock` 이 바뀌었다는 이유로 AI가 임의로 빌드를 실행하거나
제안하지 않는다. 빌드 시점은 사용자가 결정한다.

**How to apply:**
- `docker build` / `docker compose build` / `--build` 옵션 → 명시적 요청 시에만.
- 새 패키지는 실행 중인 컨테이너에 먼저 설치해서 확인한다:
  ```bash
  docker compose exec <service> uv pip install <package>
  ```
- `pyproject.toml`/`uv.lock` 수정(`uv add` 등)은 해도 되지만, 그 직후 **자동으로 빌드까지 이어가지 않는다.**
- 컨테이너를 내렸다 올리면 exec로 설치한 패키지는 사라진다. 필요할 때 한 번 알려줘도 되지만,
  **그것을 이유로 먼저 빌드하지 않는다.**

자주 쓰는 기동 명령:
```bash
docker compose up -d backend            # http://127.0.0.1:8000/docs
docker compose up -d pgvector redis neo4j
cd www && pnpm dev                      # http://localhost:3000
```

관련: [[server-remote-access-jsangho]] · [[workflow-harness-gates]]
