# 🎭 Kayfabe App: 라우터 캐스팅 명세

> **도메인:** WWE PLE 예측·결과·기록·랭킹·챔피언십  
> **캐릭터 = 라우터 파일명** (`adapter/inbound/api/v1/`)

라우터 파일 6개를 캐릭터로 삼아 각 역할을 정의합니다.

---

## 1. ple_router

- **파일:** `ple_router.py`
- **prefix:** `/ple`
- **HTTP 메서드:** POST (쓰기 전용)
- **역할:** PLE 이벤트·경기 동기화, 예측 저장, 경기 결과 확정
- **접근 테이블:** PLE_EVENTS, PLE_MATCHES, PLE_MATCH_PICK
- **엔드포인트:**
  - `POST /ple/{slug}/sync-from-client` — PLE 카드 전체 동기화
  - `POST /ple/{slug}/predictions/batch` — 예측 배치 저장 (userId 필수)
  - `POST /ple/{slug}/matches/{match_key}/predict` — 단건 예측 저장 (userId 필수)
  - `POST /ple/{slug}/results/batch` — 경기 결과 일괄 확정
  - `POST /ple/{slug}/matches/{match_key}/result` — 단건 경기 결과 확정
  - `POST /ple/link-predictions` — 예측 연결 (**410** 폐기)
- **의존:** `PleUseCase` → `PleInteractor` → `PlePgRepository`
- **검증 규칙:** `userId` 미제공 → **422**, 존재하지 않는 id → **401**

---

## 2. pleinfo_router

- **파일:** `pleinfo_router.py`
- **prefix:** `/ple`
- **HTTP 메서드:** GET (읽기 전용) + SSE
- **역할:** PLE 보드 조회, 이벤트 목록, AI 통계, 실시간 스트림
- **접근 테이블:** PLE_EVENTS, PLE_MATCHES, PLE_MATCH_PICK (읽기)
- **엔드포인트:**
  - `GET /ple/events` — 전체 PLE 이벤트 목록
  - `GET /ple/ai-stats` — AI 예측 적중률 통계
  - `GET /ple/results` — 연도별 PLE 결과 목록 (`?year=`)
  - `GET /ple/{slug}` — PLE 전체 보드 (`?client_id=`, `?user_id=` → myPick)
  - `GET /ple/{slug}/live` — SSE 실시간 보드 스트림 (`client_id` 필수)
- **의존:** `PleInfoUseCase` → `PleInfoInteractor` → `PleInfoPgRepository`
- **CQRS 쌍:** `ple_router`(쓰기) ↔ `pleinfo_router`(읽기) — 동일 `/ple` prefix, 메서드로 분리

---

## 3. championship_router

- **파일:** `championship_router.py`
- **prefix:** `/championship`
- **HTTP 메서드:** GET
- **역할:** 브랜드별 현역 WWE 챔피언 보드 제공
- **접근 테이블:** 없음 (카탈로그 전용 · Neon 미사용)
- **엔드포인트:**
  - `GET /championship` — 브랜드별 현역 챔피언 (메인·2선·태그·기타)
- **의존:** `ChampionshipUseCase` → `ChampionshipInteractor` → `CurrentChampionshipCatalogRepository`
- **데이터 출처:** `app/services/current_championship_catalog.py` 정적 카탈로그

---

## 4. ranking_router

- **파일:** `ranking_router.py`
- **prefix:** `/rankings`
- **HTTP 메서드:** GET
- **역할:** 예측 점수 기반 사용자 순위표 집계
- **접근 테이블:** PLE_MATCH_PICK (picks 집계), USERS (nickname 조회)
- **엔드포인트:**
  - `GET /rankings` — 예측 점수 순위표 (`?limit=`, `?nickname=`)
- **의존:** `RankingUseCase` → `RankingInteractor` → `RankingPgRepository`, `PlePgRepository`

---

## 5. records_router

- **파일:** `records_router.py`
- **prefix:** `/records`
- **HTTP 메서드:** GET
- **역할:** 선수별 PLE 경기 기록·승패 집계 (별도 테이블 없음)
- **접근 테이블:** PLE_MATCHES (card_json + winner 필드 파싱)
- **엔드포인트:**
  - `GET /records/competitors` — 전체 출전 선수 목록 (`?q=` 검색)
  - `GET /records/competitors/{name}` — 선수별 경기 기록·승패 프로필
- **의존:** `RecordsUseCase` → `RecordsInteractor` → `RecordsPgRepository`
- **판정 서비스:** `app/services/records_scoring.py` — `win · loss · no-contest · pending`

---

## 6. title_history_router

- **파일:** `title_history_router.py`
- **prefix:** `/title-history`
- **HTTP 메서드:** GET, POST
- **역할:** 선수별 실제 WWE 타이틀 획득 이력 조회·동기화
- **접근 테이블:** TITLE_ACQUISITIONS (`title_acquisitions` · FK → PLE_MATCHES)
- **엔드포인트:**
  - `GET /title-history/competitors/{name}` — 선수별 실제 타이틀 획득 이력
  - `POST /title-history/sync` — 실제 WWE 타이틀 카탈로그로 Neon 재생성
- **의존:** `TitleHistoryUseCase` → `TitleHistoryInteractor` → `TitleHistoryPgRepository`

---

## 라우터 요약표

| 파일 | prefix | 메서드 | 테이블 | DB |
|------|--------|--------|--------|-----|
| `ple_router` | `/ple` | POST | PLE_EVENTS, PLE_MATCHES, PLE_MATCH_PICK | Neon |
| `pleinfo_router` | `/ple` | GET, SSE | PLE_EVENTS, PLE_MATCHES, PLE_MATCH_PICK | Neon |
| `championship_router` | `/championship` | GET | — | Catalog |
| `ranking_router` | `/rankings` | GET | PLE_MATCH_PICK, USERS | Neon |
| `records_router` | `/records` | GET | PLE_MATCHES | Neon |
| `title_history_router` | `/title-history` | GET, POST | TITLE_ACQUISITIONS | Neon |

---

## /myself 엔드포인트 계획

타이타닉 패턴 참조 — 각 라우터 파일이 캐릭터로서 자기소개하는 엔드포인트.

| 라우터 | 경로 |
|--------|------|
| `ple_router` | `GET /ple/myself` |
| `pleinfo_router` | `GET /ple/info/myself` |
| `championship_router` | `GET /championship/myself` |
| `ranking_router` | `GET /rankings/myself` |
| `records_router` | `GET /records/myself` |
| `title_history_router` | `GET /title-history/myself` |

> `ple_router`와 `pleinfo_router`는 동일 prefix `/ple`를 공유하므로  
> `pleinfo_router`의 `/myself`는 `/ple/info/myself` 경로로 분리합니다.
