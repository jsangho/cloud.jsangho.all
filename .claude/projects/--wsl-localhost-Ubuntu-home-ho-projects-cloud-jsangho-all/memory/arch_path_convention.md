---
name: arch-path-convention
description: Package path notation — apps drop `jsangho`/`apps` and start at the app name, but core MUST start with `jsangho.core.`; stop and ask if notation mismatches
metadata:
  type: project
---

패키지 경로 표기는 위치에 따라 다르다. 헷갈리면 **코드를 쓰기 전에 멈추고 사용자에게 확인한다.**

| 실제 경로 | 표기 |
|-----------|------|
| `fastapi/apps/titanic/domain/...` | `titanic.domain....` — `jsangho` 와 `apps` 를 **생략**하고 앱명부터 |
| `fastapi/core/shared/...` | `jsangho.core.shared....` — **반드시** `jsangho.core.` 로 시작 |

- 이 규칙은 `CLAUDE.md` §0-3이며 하위 `.cursorrules`·`CLAUDE.md` 보다 우선한다.
- 경로 표기가 어긋난 코드를 그대로 이어서 작성하지 않는다. 멈추고 확인하는 쪽이 정답.

관련: [[arch-hexagonal-layers]] · [[arch-star-topology]]
