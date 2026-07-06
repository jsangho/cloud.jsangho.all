# 프론트엔드 행동 지침 (보조)

> **메인 규칙:** [`www/.cursorrules`](.cursorrules)를 먼저 Read한다.
> 본 문서는 [루트 CLAUDE.md](../CLAUDE.md)에 정리된 Karpathy 원칙의 **프론트 적용 보조**다. 충돌 시 `.cursorrules`가 우선한다.

**스택:** Next.js (App Router) · React · TypeScript · Tailwind CSS · Radix UI

---

## 1. 구현 전 사고 — 프론트 적용

- 새 fetch 전 → `lib/api.ts`, `lib/*-api.ts`, [`fastapi/.cursorrules`](../fastapi/.cursorrules) prefix 확인
- 같은 도메인 UI 패턴 먼저 Read (예: PLE 컴포넌트)
- `NEXT_PUBLIC_*` · `"use client"` 여부는 기존 페이지와 맞춤
- 공통 React·Next.js 패턴은 [`_claude/REACT_RULES.md`](./_claude/REACT_RULES.md)를 따른다.

---

## 2. 단순성 · 3. 정밀한 수정 · 4. 목표 중심 실행

상세는 [루트 CLAUDE.md](../CLAUDE.md) §2–4 및 `.cursorrules` §2–5를 따른다.

---

## 5. 하네스 강제 실행

```bash
cd www && pnpm lint        # ESLint (no-console, no-explicit-any 위반 시 에러)
cd www && pnpm type-check  # TypeScript strict 검사
cd www && pnpm format      # Prettier
```

---

## 관련 문서

| 문서                                                | 역할                                      |
| --------------------------------------------------- | ----------------------------------------- |
| `.cursorrules`                                      | **메인** — 저장소 구조·API 연동·UI 컨벤션 |
| `CLAUDE.md` (본 문서)                               | 보조 — Karpathy 원칙의 프론트 적용        |
| [\_claude/REACT_RULES.md](./_claude/REACT_RULES.md) | React·Next.js 공통 패턴                   |
