---
name: workflow-harness-gates
description: Lint/format/type gates that MUST run after writing code, per stack — fix errors before reporting done, never report completion with a failing gate
metadata:
  type: feedback
---

코드를 작성한 뒤 해당 스택의 게이트를 **반드시 실행**한다.

**Why:** `CLAUDE.md` §5. "작동하게 만들기"는 완료 기준이 아니다. 에러는 무시하지 않고
**수정한 뒤** 완료 보고한다. 게이트가 깨진 채로 "다 됐습니다"라고 말하지 않는다.

**How to apply:**

```bash
# Python
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports   # 스타 토폴로지 계약

# Next.js
cd www && pnpm lint         # no-console, no-explicit-any 위반 시 에러
cd www && pnpm type-check   # TS strict
cd www && pnpm format       # Prettier

# Flutter
dart analyze                # avoid_print 위반 시 에러
dart format .

# 전체 (pre-commit)
pre-commit run --all-files
```

- `uv run` 을 빠뜨리면 엉뚱한 인터프리터가 잡힌다 → [[debug-uv-run-path]]
- `lint-imports` 는 스포크↔스포크 import를 차단한다 → [[arch-star-topology]]
- 최초 1회만: `pip install pre-commit && pre-commit install`

관련: [[convention-code-style]] · [[pattern-test-conftest]]
