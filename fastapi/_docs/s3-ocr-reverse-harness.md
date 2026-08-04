# HARNESS (백엔드): 영수증 OCR — S3 역방향 판독 및 가계부 데이터 파이프라인

> **범위:** `fastapi/` 백엔드 전용. 클라이언트(Flutter/웹)는 이미 S3에 이미지를 올리는 경로를 갖고 있다(§1).
> **대상 저장소:** `cloud.jsangho.all`
> **작업 주체:** Claude Code
> **작성일:** 2026-08-04
> **상태:** 미착수 — 설계 계약만 확정. §13에 미해결 질문 4건이 남아 있고, **Q1(앱 소속)이 정해지기 전에는 T1을 시작하지 않는다.**
> **상위 규칙:** [루트 CLAUDE.md](../../CLAUDE.md) · [fastapi/CLAUDE.md](../CLAUDE.md) · 참조 구현 [`apps/lion_king/`](../apps/lion_king/)

**"역방향(reverse)"의 뜻:** 기존 `lion_king`은 촬영 이미지를 **서버 → S3**로 밀어넣는 정방향이다.
이 파이프라인은 그 반대로 **S3 → 서버**로 이미 저장된 객체를 꺼내 판독한다. 같은 버킷을 쓰지만
데이터 흐름과 권한 검사 방향이 반대라서, 정방향에서 안전했던 가정이 여기서는 그대로 성립하지 않는다(§2-D2).

---

## 0. 이 문서를 읽는 방법

이 문서는 "무엇을 만들 것인가"에 대한 계약(contract)이다.

- **§2 델타**는 원본 지시서와 이 저장소의 실제 코드가 어긋나는 지점이다. **구현 전에 반드시 읽는다.** 지시서를 문자 그대로 실행하면 URL 규약·토폴로지 계약·권한 모델 세 곳이 깨진다.
- **§3 결정사항**은 확정된 것이다. 재논의하지 말고 그대로 구현한다.
- **§4 금지사항**을 위반하는 코드는 작성 즉시 폐기 대상이다.
- **§10 작업 단위**는 순서대로 진행하며, 각 단위 종료 시 **§11 검증 기준**과 **§12 하네스 게이트**를 통과해야 다음으로 넘어간다.
- 판단이 필요한 지점이 생기면 **임의로 결정하지 말고 §13에 질문을 기록한 뒤 멈춘다.**

---

## 1. 현재 구현 실측 (2026-08-04, 코드 확인 결과)

> 추측이 아니라 아래 파일을 직접 읽고 정리한 것이다. 새 코드를 쓰기 전 이 표가 여전히 맞는지 확인한다.

| 구성요소 | 실제 위치 | 현재 동작 |
|---|---|---|
| S3 클라이언트 | `core/matrix/s3_manager.py` | 프로세스당 싱글톤. `Keymaker`가 읽은 `AWS_ACCESS_KEY_ID`·`AWS_SECRET_ACCESS_KEY`·`AWS_REGION`(기본 `ap-northeast-2`)·`AWS_S3_BUCKET`으로 boto3 `s3` 클라이언트를 만든다. **자격증명이 없으면 `get_client()`가 `None`을 돌려준다** — 예외가 아니다 |
| 이미지 업로드(정방향) | `apps/lion_king/` | `POST /api/photos`. 인증 필수, 키는 `photos/{jwt.sub}/{uuid}{ext}` |
| 업로드 응답 | `photo_schema.py` | `photoId`·`key`·`sizeBytes`·`contentType` (camelCase 별칭). **버킷 이름은 의도적으로 안 준다** |
| 허용 포맷·용량 | `lion_king/domain/value_objects/photo_content.py` | `image/jpeg`·`image/png`만, 상한 10 MiB. 순수 파이썬 |
| 인증 | `core/security/dependencies.py` | `get_current_user` → `TokenPayload`. `Authorization: Bearer` 또는 `access_token` 쿠키. Redis 블랙리스트(`auth:blacklist:{jti}`) 확인 |
| LLM 어댑터 선례 | `apps/ontology/adapter/outbound/gemini_generator.py` | `google-genai` 클라이언트를 출력 포트(`GeminiGenerationPort`) 뒤에 숨긴다. 모델 `gemini-3.5-flash` |
| 토폴로지 계약 | `fastapi/.importlinter` | 계약 4개. `root_packages`에 등재된 앱만 검사 대상 |
| 라우터 마운트 | `main.py:120~132` | 앱별 라우터를 전부 `prefix="/api"`로 include |
| 의존성 | 루트 `pyproject.toml` | `boto3==1.43.40` · `pillow==12.3.0` · `opencv-python-headless` · `google-genai==2.11.0` 이미 있음 |
| **영수증 / 가계부 도메인** | — | **전무하다.** 엔티티·라우터·테이블 어느 것도 없다. `kayfabe`의 shop/포인트 원장은 WWE 포인트라 무관하다 |
| OCR 코드 | — | **전무하다.** `ontology`의 vision은 얼굴 인식이고 텍스트 판독이 아니다 |

---

## 2. 원본 지시서와 이 저장소의 델타 (구현 전 필독)

원본 지시서를 문자 그대로 실행하면 아래에서 어긋난다.

### D-1. URL에 `/v1`이 들어가지 않는다

지시서: `POST /api/v1/receipts/ocr`

이 저장소에서 `v1`은 **패키지 디렉터리 이름일 뿐 URL 세그먼트가 아니다.**
`adapter/inbound/api/v1/photo_router.py`의 라우터는 `prefix="/photos"`이고 `main.py`가 `prefix="/api"`로
붙여 최종 경로는 `/api/photos`다. 전 앱(`/api/shop`·`/api/vision`·`/api/soccer-chat` …)이 예외 없이 같다.

→ **확정 경로는 `POST /api/receipts/ocr`.** 파일은 `adapter/inbound/api/v1/receipt_router.py`에 둔다.

### D-2. "S3 경로(URI) 또는 이미지 바이너리"를 그대로 받으면 안 된다

지시서는 요청 본문으로 둘 중 하나를 받으라고 한다. 이 저장소에서는 둘 다 문제가 있다.

- **임의 S3 URI 수신은 취약점이다.** 서버 자격증명으로 호출자가 지정한 객체를 읽어주는 꼴이라, 다른 유저의 `photos/{남의_sub}/…`나 이 계정의 아무 버킷이나 읽어낼 수 있다(IDOR + SSRF 성격). 정방향 업로드에서는 `user_id`를 JWT에서 뽑아 **쓰기** 경로를 고정했기 때문에 안전했지만, **읽기** 방향에서는 그 방어가 자동으로 따라오지 않는다.
- **바이너리 입구는 중복이다.** `POST /api/photos`가 이미 검증·저장을 다 한다. OCR용 업로드 입구를 하나 더 만들면 허용 포맷·용량 상한이 두 곳으로 갈라진다.

→ **입력은 `POST /api/photos`가 돌려준 `key` 문자열 하나로 고정한다.** 버킷·리전은 서버가 정한다(§3-D1).

### D-3. OCR 엔진은 아직 정해지지 않았다

지시서의 "예: AWS Textract 등"은 예시일 뿐이다. 이 저장소에는 실현 가능한 후보가 둘 있고, 둘 다 새 의존성이 필요 없다.

| 후보 | 근거 | 걸림돌 |
|---|---|---|
| **AWS Textract `AnalyzeExpense`** | 영수증 전용 API. 상호/합계/품목을 구조화해서 돌려준다. `boto3`에 클라이언트가 이미 포함돼 있다 | `AnalyzeExpense`의 **`ap-northeast-2`(서울) 지원 여부를 확인하지 않았다**(§13-Q2). 미지원이면 리전을 따로 잡아야 하는데, `S3Manager`는 S3 전용이라 Textract 클라이언트를 만들 자리가 없다 |
| **Gemini 멀티모달** | `GEMINI_API_KEY`·`google-genai==2.11.0`이 이미 있고, `gemini_generator.py`라는 어댑터 선례가 있다. 이미지 → 구조화 JSON을 한 번에 뽑아 §3-D4의 파싱 단계가 얇아진다 | 출력이 확률적이라 스키마 강제·재시도가 필요하다. 이미지가 외부 API로 나간다 |

→ **엔진 선택은 §13-Q2로 넘기되, 출력 포트(`ReceiptOcrPort`)는 지금 확정한다.** 포트가 있으면 어느 쪽을 골라도 유스케이스는 그대로다.

### D-4. 앱 소속이 정해지지 않았고, 스타 토폴로지가 선택지를 제약한다

영수증/가계부 도메인은 존재하지 않는다(§1). 둘 중 하나다.

| 안 | 내용 | 판정 |
|---|---|---|
| **A. `lion_king`에 넣는다** | 사진 보관 앱이 자기가 쓴 키를 자기가 읽는다 | 키 접두사 상수(`photos`)와 소유권 규칙이 **한 앱 안에** 있다. 토폴로지 계약을 건드리지 않는다. **권장** |
| B. 새 스포크 앱을 만든다 | 가계부는 사진 보관과 다른 바운디드 컨텍스트다 | DDD상 더 맞지만, **`no_spoke_to_spoke` 계약 때문에 `lion_king`의 키 규칙을 import할 수 없다.** 상수를 복제하거나(두 곳이 어긋나는 순간 소유권 검사가 뚫린다) 규칙을 `ontology` 허브로 올려야 한다 |

→ 최종 결정은 §13-Q1. **B를 고른다면 키 접두사·소유권 검증을 `ontology`로 올리는 작업이 T0으로 선행한다.**

### D-5. 커스텀 예외 계층은 만들지 않는다

지시서는 "커스텀 예외 처리"를 요구한다. 이 저장소에는 전용 `AppError` 계층이 **없다**(루트 `CLAUDE.md`).
`lion_king`이 쓰는 방식이 정답이다 — **도메인/포트가 평범한 `Exception` 서브클래스를 던지고,
라우터에서만 `HTTPException`으로 변환한다.** 도메인이 HTTP 상태 코드를 아는 순간 계층이 깨진다.

### D-6. 포트는 `Protocol`이 아니라 `ABC`로 쓴다

`fastapi/CLAUDE.md` §4 표는 UseCase 포트를 `Protocol`이라고 적었지만, 실제 코드
(`lion_king/app/ports/input/photo_use_case.py`)는 `ABC` + `@abstractmethod`다.
**가장 가까운 참조 구현을 따른다 — `ABC`.**

---

## 3. 확정된 결정사항 (변경 금지)

### D-1. 요청 입력은 S3 **키 하나**다
버킷 이름·리전·전체 URI를 클라이언트에서 받지 않는다. 버킷은 `S3Manager.get_bucket_name()`이 정한다.
응답에도 버킷을 담지 않는다(`photo_schema.py`와 같은 이유).

### D-2. 소유권은 **JWT `sub` 기준 접두사 매칭**으로 검증한다
`key`가 `photos/{claims.sub}/`로 시작하지 않으면 S3를 **호출하기 전에** 거절한다.
존재 여부를 알려주지 않기 위해 `403`이 아니라 **`404`**를 돌려준다 — 남의 키를 찔러 존재를 탐색하는 걸 막는다.

### D-3. OCR 엔진은 출력 포트 뒤에 숨긴다
유스케이스는 Textract도 Gemini도 모른다. 포트가 돌려주는 것은 **엔진 중립 DTO**(원본 텍스트 + 선택적 구조화 필드 + 신뢰도)이지, 벤더 응답 원형이 아니다.

### D-4. 파싱은 `domain`의 순수 로직이다
OCR 텍스트 → 가계부 항목 변환은 프레임워크·boto3·HTTP를 모르는 순수 파이썬 함수다.
테스트도 고정 텍스트 문자열만으로 돌아가야 한다(AWS 호출 없이).

### D-5. 금액은 `int`(원 단위), 통화는 `KRW` 고정
원화는 소수점이 없다. `float`를 쓰면 합계 검산에서 오차가 난다.
금액은 `fastapi/CLAUDE.md` §8 기준 **ratio(비율) 척도**다.

### D-6. 결과는 확정 내역이 아니라 **초안(draft)** 이다
OCR은 틀린다. 응답 이름을 `ReceiptDraft`로 하고 **필드별 신뢰도와 `needs_review` 플래그**를 함께 돌려준다.
사용자 확인 없이 가계부에 확정 반영하는 경로는 이번 범위에 넣지 않는다.

### D-7. 인증 필수
`Depends(get_current_user)`. 무인증 엔드포인트는 우리 자격증명으로 S3를 읽고 OCR 비용을 태우는 입구가 된다.

### D-8. boto3 호출은 `asyncio.to_thread`로 감싼다
boto3는 동기다. 그대로 부르면 다운로드·OCR 내내 이벤트 루프가 멈춘다
(`photo_s3_repository.py`가 같은 이유로 이미 그렇게 한다).

---

## 4. 금지사항

위반하는 코드는 작성 즉시 폐기 대상이다.

1. `domain/`에서 `boto3`·`fastapi`·`sqlalchemy`·`google.genai` import
2. 클라이언트가 보낸 버킷명·전체 S3 URI·`user_id` 신뢰
3. 소유권 검증 전에 S3/OCR 호출
4. 도메인·포트에서 `HTTPException` 발생
5. 스포크 ↔ 스포크 직접 import (§2-D4)
6. OCR 원본 응답(JSON 전문)을 그대로 API로 흘려보내기 — 벤더가 응답에 담는 내부 식별자까지 노출된다
7. 실패를 조용히 삼키고 빈 결과 반환 — 판독 실패와 "영수증에 품목이 없음"은 다른 상태다
8. `.env`·자격증명·버킷명을 코드나 로그에 하드코딩
9. 이미지 원본 바이트를 로그에 남기기

---

## 5. 도메인 모델 (핵심 산출물)

```
ReceiptDraft                      # 애그리거트 루트 (초안)
├── merchant_name : str | None    # 상호명
├── business_no   : str | None    # 사업자등록번호 (10자리, 하이픈 제거 후 보관)
├── transacted_at : datetime|None # 거래일시
├── total_amount  : int | None    # 합계 (KRW, 원 단위 정수)
├── vat_amount    : int | None    # 부가세
├── line_items    : list[ReceiptLineItem]
├── confidence    : float         # 0.0 ~ 1.0
├── needs_review  : bool          # 아래 규칙으로 계산
└── raw_text      : str           # OCR 원문 (디버깅·재파싱용)

ReceiptLineItem
├── name       : str
├── quantity   : int   # 미기재 시 1
├── unit_price : int | None
└── amount     : int
```

### 파싱 규칙 (순수 함수)

| 항목 | 규칙 |
|---|---|
| 금액 | 천단위 구분자(`,`)·통화기호(`₩`·`원`) 제거 후 정수 변환. 실패 시 `None`, 예외 아님 |
| 날짜 | `YYYY-MM-DD` · `YYYY/MM/DD` · `YY.MM.DD` · `YYYY년 M월 D일` + 선택적 `HH:MM(:SS)`. 두 자리 연도는 2000년대로 해석 |
| 사업자등록번호 | `\d{3}-?\d{2}-?\d{5}` 매칭 후 하이픈 제거 |
| 합계 | `합계` · `총액` · `받을금액` · `승인금액` 라벨 우선. 없으면 품목 `amount` 합 |
| 상호명 | 사업자등록번호 라인 위쪽 첫 비어있지 않은 줄 (한국 영수증의 통상 배치) |

### `needs_review = True` 조건 (하나라도 해당)

- `total_amount`가 `None`
- `transacted_at`이 `None`
- 품목 `amount` 합이 `total_amount`와 다름 (부가세 별도 표기 감안 후에도)
- OCR `confidence < 0.80`

---

## 6. 레이어 배치 (`fastapi/CLAUDE.md` §4 네이밍 적용)

> 아래는 §13-Q1이 **안 A(`lion_king`)** 로 결정된 경우다. 안 B면 앱 루트만 바뀐다.

```
apps/lion_king/
├── domain/
│   ├── entities/receipt_draft.py          # ReceiptDraft · ReceiptLineItem
│   ├── services/receipt_parser.py         # OCR 텍스트 → ReceiptDraft (순수 함수)
│   └── value_objects/receipt_key.py       # ReceiptKey.validated(key, owner_sub)
├── app/
│   ├── dtos/receipt_dto.py                # OcrReceiptCommand · ReceiptDraftDto · OcrRawResult
│   ├── ports/input/receipt_use_case.py    # ReceiptUseCase (ABC)
│   ├── ports/output/
│   │   ├── receipt_image_repository.py    # ReceiptImageRepository — S3 읽기 + ObjectNotFoundError
│   │   └── receipt_ocr_port.py            # ReceiptOcrPort — 이미지 바이트 → OcrRawResult
│   └── use_cases/receipt_interactor.py    # ReceiptInteractor
├── adapter/
│   ├── inbound/api/
│   │   ├── v1/receipt_router.py           # receipt_router = APIRouter(prefix="/receipts")
│   │   └── schemas/receipt_schema.py      # ReceiptDraftResponse (camelCase 별칭)
│   └── outbound/
│       ├── repositories/receipt_image_s3_repository.py
│       └── textract_ocr_reader.py         # 또는 gemini_ocr_reader.py (§13-Q2)
├── dependencies/receipt_provider.py       # get_receipt_use_case()
└── tests/test_receipt_parser.py · test_receipt_interactor.py · test_receipt_router.py
```

---

## 7. API 계약

### `POST /api/receipts/ocr`

**요청** (`Authorization: Bearer <access_token>` 또는 `access_token` 쿠키)

```json
{ "key": "photos/42/9f3c1a8b7e2d4f60a1b2c3d4e5f60718.jpg" }
```

**응답 200**

```json
{
  "merchantName": "이마트 성수점",
  "businessNo": "1234567890",
  "transactedAt": "2026-08-04T19:32:00",
  "totalAmount": 23400,
  "vatAmount": 2127,
  "currency": "KRW",
  "lineItems": [
    { "name": "우유 1L", "quantity": 2, "unitPrice": 3200, "amount": 6400 },
    { "name": "계란 30구", "quantity": 1, "unitPrice": 8500, "amount": 8500 }
  ],
  "confidence": 0.91,
  "needsReview": false
}
```

`rawText`는 응답에 넣지 않는다 — 디버깅용이라 서버 로그(DEBUG)까지만 남긴다.

---

## 8. 예외 → HTTP 상태 코드 매핑

| 상황 | 발생 지점 | 예외 | 상태 | 사용자 문구 |
|---|---|---|---|---|
| 키 형식이 틀림 / 남의 접두사 | `ReceiptKey.validated` | `ReceiptKeyNotOwnedError` | **404** | 영수증 이미지를 찾을 수 없습니다. |
| S3에 객체 없음 | S3 어댑터 (`NoSuchKey`) | `ObjectNotFoundError` | 404 | 영수증 이미지를 찾을 수 없습니다. |
| 자격증명·버킷 미설정 | S3 어댑터 (`get_client() is None`) | `PhotoStorageUnavailableError` 재사용 | 503 | 사진 보관소를 사용할 수 없습니다. |
| S3 통신 실패 | S3 어댑터 (`BotoCoreError`) | `PhotoStorageUnavailableError` | 503 | 사진 보관소를 사용할 수 없습니다. |
| OCR 엔진 오류·한도 초과 | OCR 어댑터 | `OcrUnavailableError` | 503 | 영수증 판독을 잠시 사용할 수 없습니다. |
| 판독은 됐으나 영수증이 아님 | 파서 | `ReceiptNotRecognizedError` | 422 | 영수증을 인식하지 못했습니다. 다시 촬영해 주세요. |
| 인증 없음/만료 | `get_current_user` | `HTTPException` | 401 | (기존 문구) |

**원칙:** 내부 사정(버킷명·AWS 오류 코드·엔진 이름)은 `detail`에 노출하지 않고 로그에만 남긴다.
403을 쓰지 않는 이유는 §3-D2에 있다.

---

## 9. 환경 변수

기존 키로 충분하다 (`fastapi/.env.example`).

```bash
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-northeast-2
AWS_S3_BUCKET=
```

엔진 선택 결과에 따라 **둘 중 하나만** 추가한다. 추가 시 `.env.example`에도 키를 반영한다.

```bash
# Textract를 고르고 ap-northeast-2 미지원인 경우에만
AWS_TEXTRACT_REGION=

# Gemini를 고른 경우 — GEMINI_API_KEY는 이미 있음. 신규 키 없음
```

**IAM 권한:** 현재 자격증명에 `textract:AnalyzeExpense`가 없을 가능성이 높다. Textract를 고르면 정책 추가가 선행된다.
S3 쪽은 이번에 **`s3:GetObject`가 새로 필요하다** — 정방향은 `PutObject`만 썼다.

---

## 10. 작업 단위

각 단위가 끝날 때마다 §12 하네스 게이트를 통과시킨다.

| # | 작업 | 산출물 | 완료 판정 |
|---|---|---|---|
| **T0** | §13-Q1·Q2 결정 | 이 문서 §13 갱신 | 앱 소속·OCR 엔진이 확정됐다. **미결이면 여기서 멈춘다** |
| **T1** | 도메인 — 엔티티 + 파서 | `receipt_draft.py` · `receipt_parser.py` · `receipt_key.py` | 고정 텍스트 픽스처로 파서 단위 테스트 통과. AWS 호출 0회 |
| **T2** | 포트 정의 | `receipt_use_case.py` · `receipt_image_repository.py` · `receipt_ocr_port.py` | 전부 `ABC`. 구현체 없이도 import 된다 |
| **T3** | 유스케이스 | `receipt_interactor.py` | 포트 페이크 2개로 테스트. **소유권 위반 시 S3 어댑터가 호출되지 않음**을 페이크 호출 카운트로 검증 |
| **T4** | S3 읽기 어댑터 | `receipt_image_s3_repository.py` | `asyncio.to_thread` 사용, `NoSuchKey` → `ObjectNotFoundError` 변환 |
| **T5** | OCR 어댑터 | `textract_ocr_reader.py` 또는 `gemini_ocr_reader.py` | 벤더 응답 → `OcrRawResult` 변환. 벤더 타입이 포트 시그니처에 새어나오지 않음 |
| **T6** | 라우터 + 스키마 + 프로바이더 | `receipt_router.py` · `receipt_schema.py` · `receipt_provider.py` | `main.py`에 include. `/docs`에 노출 |
| **T7** | 토폴로지 계약 등록 | `fastapi/.importlinter` | 안 B로 갔다면 새 앱을 `root_packages`와 **계약 4개 전부**에 추가. 빠뜨리면 그 앱만 검사에서 제외된다 |

---

## 11. 검증 기준 (Definition of Done)

1. `POST /api/receipts/ocr`에 **무인증** 요청 → `401`
2. 다른 유저의 `key` → `404`, 그리고 **S3 접근 로그가 없다**
3. 없는 `key` → `404`
4. 정상 영수증 → `200` + `totalAmount`가 실제 금액과 일치
5. 흐릿한 이미지 → `200` + `needsReview: true` (500이 아니다)
6. 영수증이 아닌 사진 → `422`
7. `AWS_S3_BUCKET`을 비운 상태 → `503` (스택트레이스 노출 없음)
8. 응답 어디에도 버킷명·AWS 오류 코드가 없다
9. `Swagger UI`(`http://127.0.0.1:8000/docs`)에 스키마가 정상 노출
10. §12 게이트 전부 통과

---

## 12. 하네스 게이트 (코드 작성 후 필수)

```bash
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports
cd fastapi && PYTHONPATH=apps uv run pytest apps/lion_king/tests -q
```

> `uv run` 없이 실행하면 PATH상 다른 Python이 잡혀 잘못된 버전이 돌거나 앱 패키지를 못 찾는다.

새 앱을 만들었다면 `tests/conftest.py`는 `apps/lion_king/tests/conftest.py` 패턴을 복사한다
(`apps/`와 `fastapi/`를 각각 `sys.path`에 넣는다).

---

## 13. 미해결 질문 (구현 중 발견 시 여기에 기록하고 중단)

- [ ] **Q1. 앱 소속** — `lion_king` 확장(안 A) vs 신규 스포크(안 B). §2-D4 참조. **T1 착수 전에 결정해야 한다.** 권장은 안 A.
- [ ] **Q2. OCR 엔진** — Textract `AnalyzeExpense` vs Gemini 멀티모달. §2-D3 참조. Textract를 고르면 **`ap-northeast-2` 지원 여부를 먼저 확인**한다 — 미지원이면 `S3Manager`가 S3 전용이라 Textract용 클라이언트 관리자를 따로 만들어야 하고, 이미지가 리전을 넘어간다.
- [ ] **Q3. 영속화 범위** — 지시서는 "파싱 및 반환"까지다. 가계부는 결국 저장이 필요한데, 이번 범위에 테이블을 넣을지. 넣는다면 `_docs/ENTITY_RULE.md`를 먼저 읽고 `id: int` auto-increment 규칙을 따른다. **넣지 않기로 하면 클라이언트가 초안을 들고 있어야 하므로 앱/웹 쪽 계약이 달라진다.**
- [ ] **Q4. 키 접두사** — 영수증을 기존 `photos/` 아래 그대로 둘지, `receipts/{sub}/`로 분리할지. 분리하면 수명 정책(lifecycle rule)과 OCR 비용을 접두사 단위로 끊을 수 있지만, 업로드 경로(`POST /api/photos`)에 접두사 선택 파라미터가 생긴다.

---

## 14. 작업 로그

| 날짜 | 단위 | 내용 | 검증 |
|---|---|---|---|
| 2026-08-04 | — | 원본 지시서를 이 저장소 맥락으로 옮겨 하네스 계약 작성. `lion_king`·`s3_manager`·`core.security`·`.importlinter` 실측 후 델타 6건(§2)·미해결 질문 4건(§13) 도출 | 문서만 작성, 코드 변경 없음 |
