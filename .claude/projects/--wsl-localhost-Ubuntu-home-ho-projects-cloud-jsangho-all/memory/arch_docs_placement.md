---
name: arch-docs-placement
description: Where new .md files go — `_docs/` per stack, never at repo root or app root (except CLAUDE.md / agent.md)
metadata:
  type: project
---

새 MD 파일을 만들거나 옮길 때의 위치 규칙. 범위가 겹치면 **더 좁은 쪽**을 우선한다.

| 위치 | 대상 |
|------|------|
| `_docs/` | 프로젝트 전체 공통 (설정, 운영, 온보딩 등) |
| `fastapi/_docs/` | 백엔드 전용 (API 설계, DB 스키마, 아키텍처) |
| `www/_docs/` | 프론트엔드 전용 (컴포넌트, 라우팅, 상태 관리) |
| `flutter/_docs/` | Flutter 전용 (위젯, 상태, 플랫폼 설정) |

- 특정 스택에 귀속되지 않는 문서는 `_docs/` 에.
- **루트나 각 앱 루트에 MD를 직접 두지 않는다.** 예외는 `CLAUDE.md` · `agent.md` 같은 LLM 지침 파일뿐.
- `_docs/` 는 서브모듈이다 — [[repo-submodules]] 참조.

관련: [[repo-submodules]]
