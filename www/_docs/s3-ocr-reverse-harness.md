# HARNESS (프론트): 가계부 화면 — S3 영수증 역방향 판독 연동

> **범위:** `www/` (Next.js App Router) 전용. 백엔드 계약은 [`fastapi/_docs/s3-ocr-reverse-harness.md`](../../fastapi/_docs/s3-ocr-reverse-harness.md)에 있다. **그 문서를 먼저 읽는다** — 여기서 부르는 엔드포인트의 입력·권한 모델이 거기서 확정된다.
> **대상 저장소:** `cloud.jsangho.all`
> **작업 주체:** Claude Code
> **작성일:** 2026-08-04
> **상태:** 구현 완료 (2026-08-04) — T2~T6. 백엔드 T0·T1도 함께 끝나 `GET /api/receipts` · `POST /api/receipts/ocr`가 존재한다.
> 라우트는 §6의 `/ledger`가 아니라 **`/lesson/ledger`** 다(§13-Q5 결정).
> **상위 규칙:** [루트 CLAUDE.md](../../CLAUDE.md) · [www/.cursorrules](../.cursorrules) · [www/CLAUDE.md](../CLAUDE.md) · [`.claude/rules/typescript.md`](../../.claude/rules/typescript.md)

**"역방향(reverse)"의 뜻:** 정방향은 촬영 이미지를 **클라이언트 → 서버 → S3**로 밀어넣는 흐름이다.
이 파이프라인은 반대로 **S3 → 서버 → 클라이언트**로 이미 저장된 영수증을 꺼내 판독 결과를 화면에 올린다.
방향이 바뀌면 권한 검사도 반대로 필요해지는데, 그 검사는 전부 **서버 몫**이다(§2-D2).

---

## 0. 이 문서를 읽는 방법

- **§2 델타**는 원본 지시서와 이 저장소의 실제 코드가 어긋나는 지점이다. **구현 전에 반드시 읽는다.** 지시서를 문자 그대로 실행하면 브라우저에 AWS 자격증명을 심게 되고, 존재하지 않는 URL을 호출하며, 없는 상태 관리 라이브러리를 새로 들인다.
- **§3 결정사항**은 확정된 것이다. 재논의하지 말고 그대로 구현한다.
- **§4 금지사항**을 위반하는 코드는 작성 즉시 폐기 대상이다.
- **§10 작업 단위**는 순서대로 진행하며, 각 단위 종료 시 **§11 검증 기준**과 **§12 하네스 게이트**를 통과해야 다음으로 넘어간다.
- 판단이 필요한 지점이 생기면 **임의로 결정하지 말고 §13에 질문을 기록한 뒤 멈춘다.**

---

## 1. 현재 구현 실측 (2026-08-04, 코드 확인 결과)

> 추측이 아니라 아래 파일을 직접 읽고 정리한 것이다. 새 코드를 쓰기 전 이 표가 여전히 맞는지 확인한다.

| 구성요소 | 실제 위치 | 현재 상태 |
|---|---|---|
| API 베이스 URL | `lib/api.ts` | `apiBaseUrl = NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"`. 도메인별 상수를 여기 모아둔다 (`shopBaseUrl = ${apiBaseUrl}/api/shop` 식) |
| 공통 에러 처리 | `lib/api.ts` | `parseApiError(data, status)` · `isAbortError` · `getRequestTimeoutMessage` · `requestTimeoutMs = 20000` |
| API 클라이언트 패턴 | `lib/shop-api.ts` | `AbortController` + `setTimeout(requestTimeoutMs)` + `credentials: "include"`. 실패 시 `null`/`[]` 반환 |
| 인증 | `context/auth-context.tsx` | **액세스 토큰은 httpOnly 쿠키에만 있고 JS가 읽을 수 없다.** 컨텍스트가 들고 있는 건 표시용 프로필 캐시뿐이다 |
| `authHeader(token)` | `lib/api.ts` | **어드민 전용 Next.js Route Handler 호출용**이다. FastAPI 직접 호출에는 쓰지 않는다 |
| 이미지 업로드 UI 선례 | `components/titanic-vision-upload.tsx` | `useState` 판별 유니온 + `useCallback` + `FormData` + `parseApiError`. 상태 라이브러리 없음 |
| 상태 관리 | — | **전역은 `context/auth-context.tsx` 하나뿐.** Redux·Zustand·react-query·SWR **전부 없다** (`package.json` 확인) |
| 스택 버전 | `package.json` | `next@16.2.4` · `react@19` · Tailwind · Radix · `sonner`(토스트) · `zod` · `date-fns` |
| 이미지 최적화 | `next.config.mjs` | `images.unoptimized: true` — 원격 호스트를 `remotePatterns`에 등록하지 않아도 `next/image`가 통과한다 |
| **빌드 타입 검사** | `next.config.mjs` | `typescript.ignoreBuildErrors: true` — **`pnpm build`는 타입 오류를 잡지 못한다.** 실질 게이트는 `pnpm type-check`다 |
| **가계부 화면** | — | **전무하다.** `app/`에 해당 라우트 없음 |
| **영수증/사진 API 클라이언트** | — | **전무하다.** `lib/`에 `photos`·`receipt` 관련 파일 없음. www는 `lion_king`(`/api/photos`)을 **한 번도 호출한 적이 없다** |

---

## 2. 원본 지시서와 이 저장소의 델타 (구현 전 필독)

### D-1. 이 문서 경로는 `www`(Next.js) 전용이다 — 지시서는 Flutter를 말한다

지시서 제목은 "Flutter 가계부 화면"이지만, 지정된 경로 `www/_docs/`는 루트 `CLAUDE.md` §0-4 표에서
**프론트엔드(Next.js) 전용**이다. Flutter 문서는 `flutter/_docs/`에 둔다.

→ **이 문서는 `www` 기준으로 옮겨 적는다.** 지시서 목표문의 "웹/앱 화면"도 웹 쪽을 다룬다.
Flutter 대응 문서가 필요하면 `flutter/_docs/`에 별도로 만든다 — 두 클라이언트는 인증 방식부터 다르다
(웹은 httpOnly 쿠키, 앱은 `Authorization: Bearer` + secure storage).

지시서의 Flutter 용어는 아래로 치환한다.

| 지시서 (Flutter) | 이 저장소 (www) |
|---|---|
| Domain Layer | `lib/receipt-api.ts`의 `export type` — 도메인 타입은 소유 모듈에서 export (typescript.md §2) |
| Data Layer / DataSource | `lib/receipt-api.ts` fetch 함수 (`lib/shop-api.ts` 패턴) |
| Presentation Layer | `app/ledger/page.tsx` + `components/ledger/*` |
| BLoC / Provider | **없음.** `useState` 판별 유니온 + `useCallback` (§2-D5) |

### D-2. 브라우저가 S3에 직접 접근하는 요구사항은 그대로 구현할 수 없다

지시서 §1: "S3 영수증 저장 폴더(`s3://.../receipts/`)에 접근하여 이미지 리스트 또는 URL을 가져온다."

브라우저에서 이걸 하려면 둘 중 하나다 — **AWS 자격증명을 번들에 심거나**(`NEXT_PUBLIC_*`은 클라이언트에 그대로 노출된다), **버킷을 퍼블릭으로 여는 것**. 둘 다 즉시 폐기 대상이다.
지시서가 스스로 내건 "**클라이언트는 중앙 서버를 통해 데이터 흐름을 제어**"라는 스타 토폴로지 원칙과도 정면으로 어긋난다.

→ 목록 조회는 **서버 엔드포인트를 통해서만** 한다. 그런데 **그 엔드포인트가 백엔드에 없다.**
백엔드 실측(백엔드 하네스 §1) 기준으로 `lion_king`에 존재하는 것은 `POST /api/photos`(업로드) **하나뿐**이고,
목록·조회·presigned URL 엔드포인트는 전부 미구현이다.

→ **§10-T0(백엔드 선행)이 끝나기 전에는 프론트 작업을 시작할 수 없다.**

### D-3. `POST /api/v1/receipts/ocr` → `POST /api/receipts/ocr`

이 저장소에서 `v1`은 백엔드의 패키지 디렉터리 이름일 뿐 URL 세그먼트가 아니다
(백엔드 하네스 §2-D1에서 확정). `/api/v1/...`을 호출하면 404다.

### D-4. 인증은 `Authorization` 헤더가 아니라 **httpOnly 쿠키**다

`context/auth-context.tsx`가 명시한다 — 액세스 토큰은 httpOnly 쿠키에만 있고 JS가 읽을 수 없다.

→ 모든 요청에 **`credentials: "include"`**. `lib/api.ts`의 `authHeader()`는 어드민 Route Handler 전용이므로 여기서 쓰지 않는다.
백엔드 `get_current_user`는 `Authorization: Bearer`와 `access_token` 쿠키를 **둘 다** 받으므로 쿠키만으로 충분하다.

### D-5. 상태 관리 라이브러리를 새로 들이지 않는다

지시서는 "BLoC / Provider 등"을 말하지만, www에는 상태 관리 라이브러리도 데이터 페칭 라이브러리도 **하나도 없다**(§1).
여기서 react-query를 넣는 건 요청받지 않은 의존성 추가다(루트 `CLAUDE.md` §2 단순성 우선).

→ `components/titanic-vision-upload.tsx`가 쓰는 방식을 따른다: `useState` 판별 유니온 + `useCallback` + `AbortController`.

### D-6. "이미지를 다운로드해서 서버로 전송"하지 않는다

지시서 §2: "S3에서 가져온 영수증 이미지 데이터(또는 경로)를 서버로 전송한다."

바이트를 보내면 S3 → 브라우저 → 서버 → (다시) S3로 같은 이미지가 두 번 왕복한다. 모바일 회선에서 낭비고,
무엇보다 백엔드 계약이 **`key` 문자열 하나만** 받는다(백엔드 하네스 §3-D1). 바이너리 입구는 존재하지 않는다.

→ 브라우저는 **`key`만 넘긴다.** 화면에 썸네일을 띄우는 것은 별개 경로(presigned URL)로 처리한다.

### D-7. `www/_claude/REACT_RULES.md`가 실재하지 않는다

`www/.cursorrules` §0과 `www/CLAUDE.md`가 이 파일을 "구현 전 필수 Read"로 가리키는데, `www/_claude/` 디렉터리 자체가 없다.
착수 전 확인이 필요하다 → §13-Q3.

---

## 3. 확정된 결정사항 (변경 금지)

### D-1. 화면 진입 시에는 **목록만** 부른다. OCR은 사용자가 고른 한 장에만 돌린다
진입과 동시에 N장을 판독하면 Textract/Gemini 호출이 목록 길이만큼 곱해진다. 비용도 지연도 사용자가 원한 적 없는 값이다.
→ 진입: `GET` 목록 1회. OCR: 카드 클릭 시 `POST` 1회.

### D-2. 인증은 `credentials: "include"` 하나로 통일한다
토큰을 JS로 읽어 헤더에 넣으려 시도하지 않는다 — 읽을 수 없다(§2-D4).

### D-3. OCR 요청은 **별도 타임아웃 상수**를 쓴다
`lib/api.ts`의 `requestTimeoutMs = 20000`은 일반 조회 기준이다. OCR은 이미지 다운로드 + 엔진 왕복이라 이보다 오래 걸릴 수 있다.
→ `lib/receipt-api.ts`에 `ocrTimeoutMs = 60000`을 따로 두고 사유를 주석으로 남긴다. **기존 `requestTimeoutMs`를 키우지 않는다** — 다른 화면 전체의 응답 기준이 함께 늘어난다.

### D-4. `needsReview`를 화면에서 반드시 드러낸다
백엔드는 확정 내역이 아니라 **초안(draft)** 을 돌려준다(백엔드 하네스 §3-D6).
`needsReview: true`면 "확인 필요" 배지를 붙이고, 사용자 확인 없이 확정된 값처럼 보이게 하지 않는다.
`totalAmount`가 `null`인 자리에 `0`을 채워 넣지 않는다 — 미판독과 0원은 다르다.

### D-5. 상태는 판별 유니온 하나로 든다
`loading`·`error`·`data` 불리언 3개를 각각 두면 "로딩 중인데 에러도 있는" 표현 불가능한 상태가 만들어진다.

```ts
type OcrState =
  | { kind: "idle" }
  | { kind: "loading"; key: string }
  | { kind: "done"; key: string; draft: ReceiptDraft }
  | { kind: "error"; key: string; message: string };
```

### D-6. 금액은 정수 원 단위로 받아 표시할 때만 포맷한다
백엔드가 `int`(KRW)로 준다(백엔드 하네스 §3-D5). 클라이언트에서 `parseFloat`·나눗셈을 하지 않는다.
표시는 `toLocaleString("ko-KR")`.

### D-7. 목록·OCR 응답 타입은 `lib/receipt-api.ts`가 소유하고 `export`한다
컴포넌트에서 같은 타입을 다시 선언하지 않는다 (`.claude/rules/typescript.md` §2).

### D-8. 실패는 `parseApiError`를 거쳐 한국어 문구로만 노출한다
상태 코드·스택·백엔드 원문을 화면에 그대로 찍지 않는다.

---

## 4. 금지사항

위반하는 코드는 작성 즉시 폐기 대상이다.

1. `NEXT_PUBLIC_AWS_*` 등 **AWS 자격증명을 프론트 환경변수에 넣기** — `NEXT_PUBLIC_*`은 번들에 그대로 박힌다
2. 브라우저에서 AWS SDK 사용 · S3 버킷 직접 호출
3. 버킷 이름·전체 `s3://` URI를 프론트 코드에 하드코딩 (서버가 응답에도 담지 않는다)
4. `any` 사용 — 코드베이스에 0건이다. 외부 응답은 `unknown`으로 받고 타입 서술어로 좁힌다
5. `console.*` — ESLint `no-console`가 에러다
6. react-query·SWR·Zustand 등 **요청받지 않은 의존성 추가**
7. 화면 진입 시 목록 전체를 자동 OCR
8. `lib/api.ts`의 공용 `requestTimeoutMs` 값 변경
9. `eslint-disable` 광범위 적용 — 한 줄 범위 + 사유 주석만 허용
10. 다른 유저의 `key`를 추측해 호출하는 UI 경로 (서버가 404로 막지만 클라이언트도 만들지 않는다)

---

## 5. 화면 사양

### 라우트

`app/ledger/page.tsx` — 가계부. 로그인 필수 화면이므로 비로그인 시 로그인 유도를 보여준다
(`context/auth-context.tsx`의 `user`·`isReady` 사용. `isReady` 이전에는 판단하지 않는다).

### 화면 흐름

```
진입
 └─ isReady 대기 (스켈레톤)
     ├─ user 없음 → 로그인 안내
     └─ user 있음 → GET 영수증 목록
         ├─ 로딩    → 카드 스켈레톤
         ├─ 빈 목록 → "촬영한 영수증이 없습니다" + 안내
         ├─ 실패    → 에러 문구 + [다시 시도]
         └─ 성공    → 썸네일 그리드
             └─ 카드 클릭 → POST OCR (해당 카드만 로딩)
                 ├─ 성공 → 내역 패널 (상호/일시/합계/품목)
                 │          needsReview면 "확인 필요" 배지
                 └─ 실패 → 카드 안에 문구 + [다시 시도]
```

### 렌더링 규칙

- 목록 로딩은 **스켈레톤**, OCR 로딩은 **해당 카드 안에서만** 표시한다. OCR 한 건 때문에 화면 전체를 로딩으로 덮지 않는다.
- 품목 표는 `overflow-x: auto` 컨테이너 안에 둔다 — 좁은 화면에서 페이지 본문이 가로로 밀리지 않게 한다.
- 썸네일은 presigned URL을 `next/image`로 쓴다. `images.unoptimized: true`라 `remotePatterns` 등록은 불필요하다(§1).
- 토스트가 필요하면 이미 있는 `sonner`를 쓴다.

---

## 6. 파일 배치

```
www/
├── app/ledger/page.tsx                      # "use client" — 목록 상태 보유
├── components/ledger/
│   ├── receipt-card.tsx                     # 썸네일 + 카드별 OCR 상태
│   ├── receipt-draft-panel.tsx              # 판독 내역 렌더링
│   └── receipt-review-badge.tsx             # needsReview 배지
└── lib/
    ├── api.ts                               # receiptsBaseUrl 상수 추가 (기존 패턴)
    └── receipt-api.ts                       # 타입 + fetch 함수 (lib/shop-api.ts 패턴)
```

`lib/api.ts`에 붙이는 줄은 딱 하나다 — 기존 `shopBaseUrl` 형태를 그대로 따른다.

```ts
export const receiptsBaseUrl = `${apiBaseUrl}/api/receipts`;
```

---

## 7. API 계약 (프론트가 호출하는 것)

### 7.1 목록 — **백엔드 미구현 (§10-T0)**

```
GET {apiBaseUrl}/api/receipts        credentials: "include"
```

```json
{
  "items": [
    {
      "key": "photos/42/9f3c1a8b7e2d4f60a1b2c3d4e5f60718.jpg",
      "thumbnailUrl": "https://...presigned...",
      "capturedAt": "2026-08-04T19:32:00"
    }
  ]
}
```

`thumbnailUrl`은 **서버가 발급한 단명 presigned URL**이다. 버킷 이름은 담기지 않는다.
만료 시간·페이지네이션 유무는 §13-Q1에서 정한다.

### 7.2 OCR

```
POST {apiBaseUrl}/api/receipts/ocr   credentials: "include"
Content-Type: application/json

{ "key": "photos/42/9f3c1a8b7e2d4f60a1b2c3d4e5f60718.jpg" }
```

응답 본문은 백엔드 하네스 §7과 동일하다 (camelCase). 프론트 타입:

```ts
export type ReceiptLineItem = {
  name: string;
  quantity: number;
  unitPrice: number | null;
  amount: number;
};

export type ReceiptDraft = {
  merchantName: string | null;
  businessNo: string | null;
  transactedAt: string | null;   // ISO 문자열. Date 변환은 표시 직전에만
  totalAmount: number | null;    // KRW 정수
  vatAmount: number | null;
  currency: "KRW";
  lineItems: ReceiptLineItem[];
  confidence: number;
  needsReview: boolean;
};
```

`null` 가능 필드를 `number`로 좁혀 선언하지 않는다 — 백엔드가 실제로 `null`을 준다.

---

## 8. 에러 → 사용자 문구

백엔드 `detail`을 `parseApiError`로 뽑되, 아래는 화면 동작이 달라지므로 상태 코드로 분기한다.

| 상태 | 상황 | 화면 동작 |
|---|---|---|
| 401 | 세션 만료 | 로그인 유도로 전환. `auth-context`의 `refresh()`를 한 번 시도한 뒤에도 실패하면 안내 |
| 404 | 없는 키 / 남의 키 | "영수증 이미지를 찾을 수 없습니다." 카드를 목록에서 제거하고 목록을 다시 부른다 |
| 422 | 영수증이 아님 | "영수증을 인식하지 못했습니다. 다시 촬영해 주세요." — **재시도 버튼을 주지 않는다** (같은 이미지로 다시 해도 같다) |
| 503 | 보관소·OCR 일시 장애 | 문구 + **[다시 시도]** 버튼 |
| 타임아웃 | `AbortError` | `isAbortError`로 판별 후 `getRequestTimeoutMessage()` |

---

## 9. 환경 변수

**새로 추가할 키가 없다.** 기존 `www/.env.local`로 충분하다.

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

AWS 관련 키를 프론트에 추가하려는 시도가 나오면 그 설계가 틀린 것이다(§4-1).

---

## 10. 작업 단위

| # | 작업 | 산출물 | 완료 판정 |
|---|---|---|---|
| **T0** | **백엔드 선행 — 목록 엔드포인트** | `fastapi/` 쪽 작업 | `GET /api/receipts`가 `/docs`에 뜨고 presigned URL을 돌려준다. **§13-Q1·Q2가 먼저 결정돼야 한다.** 미결이면 여기서 멈춘다 |
| **T1** | 백엔드 OCR 엔드포인트 | `fastapi/` 쪽 작업 | 백엔드 하네스 §11 DoD 통과 |
| **T2** | API 클라이언트 | `lib/api.ts`(1줄) · `lib/receipt-api.ts` | `credentials: "include"`, `AbortController`, `ocrTimeoutMs` 별도 상수. 실패 시 throw가 아니라 결과 타입으로 표현 |
| **T3** | 카드·패널 컴포넌트 | `components/ledger/*` | 백엔드 없이 고정 목 데이터로 렌더링 확인. `needsReview` 배지 포함 |
| **T4** | 페이지 조립 | `app/ledger/page.tsx` | `isReady`·`user` 분기, 목록 4상태(로딩/빈/실패/성공) 전부 화면에 존재 |
| **T5** | OCR 연동 | 카드 클릭 → `POST` | 카드별 로딩. §8 표의 상태 코드 분기 구현 |
| **T6** | 내비 진입점 | `components/navbar.tsx` | 기존 링크 패턴을 따라 추가. **요청 범위 밖 리팩터 금지** |

---

## 11. 검증 기준 (Definition of Done)

1. 비로그인 상태로 `/ledger` 진입 → 로그인 안내 (빈 화면이나 에러가 아니다)
2. 로그인 상태 진입 → 목록 1회 호출. **네트워크 탭에 OCR 요청이 0건**
3. 카드 클릭 → 그 카드만 로딩. 다른 카드는 그대로
4. `needsReview: true` 응답 → 배지가 보이고, `totalAmount: null`이 `0`으로 표시되지 않음
5. 백엔드를 끈 상태 → 타임아웃 문구 + 재시도 버튼 (흰 화면이나 미처리 예외가 아니다)
6. 422 응답 → 재시도 버튼이 **없다**
7. 번들에서 `AWS`·`s3://`·버킷명 문자열이 검색되지 않는다
8. 좁은 화면(360px)에서 페이지 본문이 가로로 스크롤되지 않는다
9. `pnpm type-check` 무오류 — `next build`는 `ignoreBuildErrors: true`라 검사하지 않는다(§1)
10. §12 게이트 전부 통과

---

## 12. 하네스 게이트 (코드 작성 후 필수)

```bash
cd www && pnpm lint        # no-console · no-explicit-any 위반 시 에러
cd www && pnpm type-check  # 실질 타입 게이트 (build는 타입 오류를 무시한다)
cd www && pnpm format      # Prettier
```

www에는 테스트 러너가 없다 — 위 세 명령이 그 자리를 대신한다(루트 `CLAUDE.md`).

---

## 13. 미해결 질문 (구현 중 발견 시 여기에 기록하고 중단)

- [x] **Q1. 목록 엔드포인트 사양** → 백엔드 §7.1로 확정. `LastModified` 내림차순, **최대 100장·페이지네이션 없음**, presigned URL **수명 300초**, `capturedAt`은 S3 `LastModified`(= 업로드 시각에 가깝다).
- [x] **Q2. 영수증과 일반 사진의 구분** → **구분하지 않는다** (백엔드 §13-Q4와 동일 결정). `photos/{sub}/` 아래 모든 이미지가 목록에 뜨고, 사용자가 그중 영수증을 골라 판독한다. 촬영 화면(Flutter)은 건드리지 않았다.
- [ ] **Q3. `www/_claude/REACT_RULES.md` 부재** — `.cursorrules` §0이 구현 전 필수로 가리키는데 디렉터리가 없다(§2-D7). **여전히 미해결이다.** 삭제된 것인지 이동한 것인지 확인이 필요하다.
- [x] **Q4. 판독 결과의 보관 주체** → 백엔드가 **저장하지 않기로** 했다(백엔드 §13-Q3). 클라이언트 캐시도 두지 않았다 — 화면 상태(`OcrState`)는 한 번에 한 장만 들고, 다른 카드를 판독하면 이전 결과는 사라진다. **재진입·카드 전환마다 OCR이 다시 돈다.** 비용이 문제가 되면 그때 캐시나 저장을 넣는다.
- [x] **Q5. 라우트 이름** → **`/lesson/ledger`.** §6이 제안한 `/ledger`가 아니라 레슨 섹션 아래에 두고, 진입점은 `app/lesson/layout.tsx`의 사이드바다(§10-T6이 말한 `components/navbar.tsx`가 아니다).
- [ ] **Q6. Flutter 대응 문서** — 원본 지시서는 Flutter를 대상으로 쓰였다(§2-D1). `flutter/_docs/`에 별도 하네스를 만들지, 웹만 진행할지. **미해결.**

---

## 14. 작업 로그

| 날짜 | 단위 | 내용 | 검증 |
|---|---|---|---|
| 2026-08-04 | — | 원본 지시서(Flutter 대상)를 `www` 맥락으로 옮겨 하네스 계약 작성. `lib/api.ts`·`lib/shop-api.ts`·`context/auth-context.tsx`·`components/titanic-vision-upload.tsx`·`package.json`·`next.config.mjs` 실측 후 델타 7건(§2)·미해결 질문 6건(§13) 도출. **목록 엔드포인트 부재로 프론트 단독 착수 불가**를 확인 | 문서만 작성, 코드 변경 없음 |
| 2026-08-04 | T2~T6 | `lib/api.ts`에 `receiptsBaseUrl` 1줄 · `lib/receipt-api.ts`(타입 + 목록/OCR 호출) · `components/ledger/*` 3종 · `app/lesson/ledger/page.tsx`. 상태는 판별 유니온, OCR 타임아웃은 `ocrTimeoutMs = 60000` 별도 상수. FastAPI 기본 영문 detail(`Not Found` 등)은 걸러 한국어 문구로 대체 | `pnpm type-check` 무오류 · `pnpm lint` 에러 0 · Prettier 적용 · `/lesson/ledger` 200 렌더 |
