---
name: convention-code-style
description: Per-stack style rules — ruff line-length 88/py313, TS 2-space/printWidth 100/semicolons/no-any, dart format; and the async-vs-def rule
metadata:
  type: project
---

| 스택 | 규칙 |
|------|------|
| Python | 들여쓰기 4칸(PEP8). ruff `line-length = 88`, `target-version = py313`, 룰셋 `E,F,I,N,UP,B,C4`. 포매터는 `ruff format` |
| TS/TSX | 들여쓰기 2칸, `printWidth 100`, LF, **세미콜론 사용**(Prettier 기본값). `any` 금지, `type` 별칭 우선 → `.claude/rules/typescript.md` |
| Dart | `dart format` 결과가 정답. `avoid_print` 위반은 **에러** |
| JSON/YAML | 들여쓰기 2칸 |

**async / def 선택 기준:** `await` 할 대상이 없으면 `async` 를 붙이지 않는다. 상세는 `fastapi/CLAUDE.md` §9.

**ESLint:** `no-console` · `no-explicit-any` 위반은 에러다.

**커밋 메시지:** Conventional Commits 형식(`feat:` `fix:` `docs:` `refactor:`), 제목 50자 이내, **한국어로 작성**.
예: `feat: 사용자 로그인 기능 추가`

관련: [[workflow-harness-gates]]
