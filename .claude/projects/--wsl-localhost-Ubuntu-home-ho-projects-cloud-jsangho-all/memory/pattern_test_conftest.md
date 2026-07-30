---
name: pattern-test-conftest
description: Per-app tests/conftest.py injects apps/ into sys.path so `titanic.*` imports work — copy it verbatim when adding tests to a new app
metadata:
  type: project
---

앱별 `tests/conftest.py` 가 `apps/` 를 `sys.path` 에 넣어 `titanic.*` 형태의 import를 활성화한다.
**새 앱에 테스트를 추가할 때 이 conftest 패턴을 그대로 복사한다.** 없으면 import가 깨진다.

```
fastapi/apps/<앱>/tests/
├── conftest.py                  # sys.path에 apps/ 추가
├── domain/
├── app/use_cases/
└── adapter/outbound/mappers/    # 헥사고날 레이어를 그대로 미러링
```

- 프레임워크: pytest + pytest-asyncio (`[dependency-groups] dev`)
- 파일 패턴: `test_*.py`
- 마커 `ollama` — 로컬 Ollama가 필요한 통합 테스트. 기본 실행에서 뺄 수 있게 표시한다.
- 실행: `uv run pytest fastapi/apps/titanic/tests`
- 참고 구현: `fastapi/apps/titanic/tests/` — 구조 템플릿으로 삼는다.
- **`www` 에는 테스트 러너가 없다.** `pnpm lint` + `pnpm type-check` 가 그 자리를 대신한다.
- Flutter는 `flutter/test/` (현재 `widget_test.dart` 하나).

관련: [[arch-hexagonal-layers]] · [[workflow-harness-gates]]
