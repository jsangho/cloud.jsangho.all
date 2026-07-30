---
name: arch-hexagonal-layers
description: Backend layering is Hexagonal + Clean + DDD — domain must not import framework/infra; app dir shape and the two FastAPI entrypoints
metadata:
  type: project
---

`fastapi/apps/<앱>/` 은 헥사고날 구조를 따른다. 의존성은 **항상 안쪽(도메인)** 을 향한다.

```
fastapi/apps/<앱명>/
├── domain/              # 순수 도메인. 프레임워크·인프라 import 금지
├── app/use_cases/       # 유스케이스
├── adapter/
│   ├── inbound/         # FastAPI 라우터
│   └── outbound/        # repositories, mappers
└── tests/               # 위 구조를 그대로 미러링
```

- 도메인 레이어가 프레임워크·인프라를 import하면 **즉시 거부**한다. 리뷰에서 가장 먼저 보는 항목.
- 도메인 로직은 인바운드(API/CLI)·아웃바운드(DB/외부 서비스) 어댑터에 의존하지 않는다.
- 바운디드 컨텍스트·애그리거트·도메인 이벤트를 명시적으로 모델링하고, 유비쿼터스 언어를 코드에 반영한다.
- 레이어별 파일·클래스 명명 규칙은 `fastapi/CLAUDE.md` §4 표를 따른다.
- 새 앱을 만들 때는 `fastapi/apps/titanic/` 을 구조 템플릿으로 삼는다.

**엔트리포인트가 둘이다:** `main.py`(포트 8000, 공개 API) · `auth_main.py`(포트 9000, 인증 게이트웨이, **외부 미노출**).

관련: [[arch-star-topology]] · [[arch-path-convention]] · [[pattern-test-conftest]]
