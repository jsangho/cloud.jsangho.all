---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

# TypeScript 규칙

`www/` (Next.js App Router · React · Tailwind · Radix)에서 실제로 쓰이는 패턴을 기준으로 한다.
**규칙에 없는 패턴을 추측으로 도입하지 않는다.** 판단이 서지 않으면 같은 도메인의 기존 파일을 먼저 Read한다.

---

## 1. 컴파일러·린트 기준 (강제)

- `strict: true` 필수 — [`www/tsconfig.json`](../../www/tsconfig.json). 옵션을 끄거나 완화하지 않는다.
- 경로 별칭은 `@/*` 하나만 쓴다. 상대 경로 `../../lib/...`로 올라가지 않는다.
- ESLint 위반은 **에러** — [`www/eslint.config.mjs`](../../www/eslint.config.mjs)
  - `@typescript-eslint/no-explicit-any`
  - `no-console`
  - `@typescript-eslint/no-unused-vars` (예외: `^_` 접두 인자·변수)
- `eslint-disable`는 대안이 없을 때만, **한 줄 범위 + 사유 주석**으로 붙인다.
  ```tsx
  {/* eslint-disable-next-line @next/next/no-img-element -- 로컬 blob URL 미리보기 */}
  ```

---

## 2. 타입 선언 — 인터페이스보다 타입 별칭

- **`type` 별칭을 기본으로 쓴다.** 현재 코드베이스는 `type` 131건 / `interface` 4건이며, 남은 `interface`(`ChatMessage` 등)는 레거시다. 새 선언은 전부 `type`으로 쓰고, 기존 `interface`를 요청 없이 `type`으로 바꾸지 않는다(정밀한 수정 원칙).
- 확장은 `extends`가 아니라 **교차 타입**으로 조립한다 — [`www/lib/wwe-ple-matches.ts:16`](../../www/lib/wwe-ple-matches.ts)

  ```ts
  type PleMatchBase = { id: string; title: string; cardVariant: "sideA" | "sideB" };

  export type PleMatchCardSingles = PleMatchBase & { format: "singles"; left: PleCompetitor };
  ```

- 도메인 타입은 그 도메인을 소유한 모듈에서 `export`하고, 소비자는 다시 정의하지 않고 import한다. 재수출이 필요하면 `export type { ... } from`을 쓴다 — [`www/lib/ple-api.ts:37`](../../www/lib/ple-api.ts)

---

## 3. `any` 금지 — `unknown`으로 받고 좁힌다

`any`는 코드베이스에 **0건**이다. 이 상태를 유지한다.

- 외부 입력(`JSON.parse`, `catch (e)`, `localStorage`)은 `unknown`으로 받는다.
- 좁히기는 **타입 서술어(type predicate)** 로 함수화한다 — [`www/context/auth-context.tsx:40`](../../www/context/auth-context.tsx)

  ```ts
  function isAuthUser(value: unknown): value is AuthUser {
    if (!value || typeof value !== "object") return false;
    const u = value as Partial<AuthUser>;
    return typeof u.id === "number" && typeof u.token === "string" && u.token.length > 0;
  }
  ```

- 판별 유니온에는 `match is PleMatchCardMulti` 형태의 가드를 둔다 — [`www/lib/wwe-ple-matches.ts:44`](../../www/lib/wwe-ple-matches.ts)
- 단언(`as`)은 **좁은 인라인 형태**만 허용한다. 값 전체를 `as SomeType`으로 덮지 않는다.
  ```ts
  const data = (await res.json()) as { names?: string[] };
  throw new Error((err as { detail?: string }).detail ?? res.statusText);
  ```
- 에러는 `unknown`으로 받고 `instanceof`로 판별한다 — [`www/lib/api.ts:56`](../../www/lib/api.ts)
  ```ts
  export function isAbortError(error: unknown): boolean {
    return error instanceof DOMException && error.name === "AbortError";
  }
  ```

---

## 4. 리터럴 유니온 · `as const` · 파생 타입

- 열거값은 `enum`이 아니라 **문자열 리터럴 유니온**으로 쓴다.
  ```ts
  status: "upcoming" | "live" | "finished";
  format: "singles" | "multi";
  ```
- 상수 테이블은 `as const`로 고정하고, 타입은 **테이블에서 파생**시킨다 — [`www/lib/wwe-ple.ts:125`](../../www/lib/wwe-ple.ts)
  ```ts
  export const WWE_PLE_MONTHLY_ORDER: readonly PleEvent[] = [ /* ... */ ] as const;
  export type PleSlug = (typeof WWE_PLE_MONTHLY_ORDER)[number]["slug"];
  ```
  값과 타입을 각각 손으로 적어 두 곳을 동기화하는 방식은 금지한다.
- 읽기 전용 배열 파라미터는 `readonly T[]`로 받는다 — [`www/lib/wwe-ple.ts:220`](../../www/lib/wwe-ple.ts)

---

## 5. 상태는 판별 유니온 또는 단일 객체 타입

- 서로 배타적인 화면 상태는 **판별 유니온**으로 만들어 불가능한 조합을 타입에서 제거한다 — [`www/components/weather-widget.tsx:7`](../../www/components/weather-widget.tsx)
  ```ts
  type WeatherState =
    | { status: "loading" }
    | { status: "ok"; emoji: string; temp: number; place: string }
    | { status: "error" };
  ```
- 한 흐름에 묶인 여러 `useState`는 `type XxxState`를 정의해 하나로 압축한다. 갱신은 `setState((s) => ({ ...s, field }))`, 소비는 구조 분해. 상세 규칙은 [`agent.md`](../../agent.md).
- `useState`에는 제네릭을 명시한다: `useState<PleAiStats | null>(null)`, `useState<Record<string, PleStatusBadge>>({})`.

---

## 6. 컴포넌트 Props 타입

- Props는 컴포넌트 바로 위에 `type XxxProps = { ... }`로 선언한다 — [`www/components/ple-event-grid.tsx:17`](../../www/components/ple-event-grid.tsx)
- 필드가 1~2개면 인라인으로 충분하다: `{ className }: { className?: string }`.
- `React.FC` / `FunctionComponent`는 쓰지 않는다. 일반 함수 선언 + 구조 분해 매개변수.
- DOM 요소를 감싸는 컴포넌트는 `React.ComponentProps<"button">`로 네이티브 props를 상속하고, variant는 `VariantProps<typeof xxxVariants>`와 교차한다 — [`www/components/ui/button.tsx:39`](../../www/components/ui/button.tsx)
- App Router 페이지의 동적 파라미터는 **Promise**다.
  ```ts
  type Props = { params: Promise<{ slug: string }> };
  export default async function PleEventPage({ params }: Props) { /* await params */ }
  ```
- 값이 아닌 타입만 가져올 때는 `import type` 또는 인라인 `type` 지정자를 쓴다 (`isolatedModules: true`).
  ```ts
  import type { PleSlug } from "@/lib/wwe-ple";
  import { useAuth, type AuthUser } from "@/context/auth-context";
  ```

---

## 7. API 클라이언트 시그니처

새 fetch를 만들기 전에 [`www/lib/api.ts`](../../www/lib/api.ts)와 기존 `lib/*-api.ts`를 Read하고 그 패턴을 따른다.

- 베이스 URL은 `lib/api.ts`의 `apiBaseUrl` 계열 상수만 쓴다. 컴포넌트에서 `process.env.NEXT_PUBLIC_*`를 직접 읽지 않는다.
- **반환 타입을 항상 명시**한다: `Promise<PleBoard>`, `Promise<CompetitorProfile | null>`, `Promise<string[]>`.
- "없음"은 예외가 아니라 `null` / 빈 배열로 표현하고, 진짜 실패만 `throw`한다.
- 타임아웃은 `AbortController` + `requestTimeoutMs`, 정리는 `finally` — [`www/lib/records-api.ts:43`](../../www/lib/records-api.ts)
  ```ts
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
  ```
- 응답 파싱은 `(await res.json()) as { … }`로 **필요한 필드만** 좁게 선언한 뒤 런타임 검사로 확정한다.
- 사용자에게 보이는 에러 문구는 `parseApiError` / `getRequestTimeoutMessage`를 거친다. API 원문·입력 echo를 그대로 노출하지 않는다.

---

## 8. Route Handler (`app/api/**/route.ts`)

- 요청 본문은 `(await request.json()) as { field?: T }` — 모든 필드를 **옵셔널**로 두고 직접 검증한다.
- 응답은 `NextResponse.json({ ... }, { status })`. 에러 → 클라이언트 메시지 변환은 `toClientError(error: unknown): { message: string; status: number }` 형태로 분리한다 — [`www/app/api/chat/route.ts:36`](../../www/app/api/chat/route.ts)
- `runtime` / `maxDuration` 등 세그먼트 설정은 파일 상단에 모은다.

---

## 9. 하네스 게이트 (작성 후 필수)

```bash
cd www && pnpm lint        # ESLint — no-console · no-explicit-any 위반 시 에러
cd www && pnpm type-check  # tsc --noEmit (strict)
cd www && pnpm format      # Prettier
```

에러를 남긴 채 완료 보고하지 않는다.

---

## 관련 문서

| 문서 | 역할 |
|------|------|
| [`www/.cursorrules`](../../www/.cursorrules) | **메인** — 저장소 구조·API 연동·UI 컨벤션 |
| [`www/CLAUDE.md`](../../www/CLAUDE.md) | 프론트 행동 지침 (보조) |
| [`agent.md`](../../agent.md) | useState 객체 압축 규칙 |
| [루트 `CLAUDE.md`](../../CLAUDE.md) | 아키텍처 원칙·하네스 |
