---
name: repo-submodules
description: fastapi/, www/, _docs/ are git submodules — commit inside them first, then commit the pointer at root; plus the never-commit list
metadata:
  type: project
---

`fastapi/` · `www/` · `_docs/` 는 **git 서브모듈**(각각 별도 저장소)이다.

- 이 디렉터리 안의 변경은 **해당 서브모듈에서 먼저 커밋**한 뒤, **루트에서 포인터를 커밋**해야 반영된다.
  루트에서만 커밋하면 변경이 사라진 것처럼 보인다.
- 커밋/푸시 루틴([[git-commit-push-syncs-branches]])을 돌릴 때 서브모듈 쪽을 빠뜨리지 않는지 확인한다.

**커밋 금지 대상** (`.gitignore` 기준): `.env` · `*.pem` · `data/` · `.venv/` · `pytorch_env/`.
키·비밀번호를 코드나 문서에 하드코딩하지 않는다.

**`alembic/` 은 ruff 검사 제외 대상**이다. 자동 생성 파일을 임의로 손보지 않는다.

관련: [[git-commit-push-syncs-branches]] · [[arch-docs-placement]]
