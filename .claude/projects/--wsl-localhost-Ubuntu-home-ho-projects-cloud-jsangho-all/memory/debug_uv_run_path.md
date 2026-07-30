---
name: debug-uv-run-path
description: Running ruff/lint-imports without `uv run` picks up a global Anaconda Python from PATH — wrong version, or `ontology` package not found
metadata:
  type: feedback
---

Python 명령은 **항상 `uv run`** 을 붙인다.

**Why:** `uv run` 없이 `ruff` / `lint-imports` / `pytest` 를 그냥 실행하면 PATH상 다른
Python(예: Anaconda)의 전역 설치가 먼저 잡힌다. 그러면 잘못된 버전이 돌거나 `ontology` 패키지를
못 찾아 실패한다. 실패 메시지가 코드 문제처럼 보여서 헛다리를 짚기 쉽다.

**How to apply:**
```bash
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports
uv run pytest fastapi/apps/titanic/tests
cd fastapi && uv run alembic upgrade head
```

ruff/lint-imports가 이상한 결과를 낼 때 제일 먼저 `uv run` 이 빠졌는지 확인한다.

관련: [[workflow-harness-gates]] · [[arch-star-topology]]
