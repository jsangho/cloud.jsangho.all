---
name: arch-star-topology
description: Apps form a star topology around the `ontology` hub — spoke-to-spoke imports are banned and blocked by lint-imports
metadata:
  type: project
---

`fastapi/apps/` 는 허브(`ontology`)를 중심으로 한 **스타 토폴로지**다.

앱 목록: `admin` `auth` `heyman` `kayfabe` `lion_king` **`ontology`(허브)** `sample` `soccer` `superstar` `titanic`

- **스포크 ↔ 스포크 직접 import 금지.** 앱 간 의존은 반드시 허브 `ontology` 를 통한다.
- 위반은 import-linter가 차단한다:
  ```bash
  cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports
  ```
  `uv run` 을 빼면 안 된다 — [[debug-uv-run-path]] 참조.
- 새 앱을 추가할 때 다른 스포크의 코드를 재사용하고 싶어지면, 그 코드를 `ontology` 로 올릴지부터 판단한다.
  스포크에서 바로 끌어다 쓰는 선택지는 없다.
- 앱별 API prefix와 허브/스포크 관계 상세는 `fastapi/CLAUDE.md` §6.

관련: [[arch-hexagonal-layers]] · [[workflow-harness-gates]]
