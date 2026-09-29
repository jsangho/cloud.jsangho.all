# Kayfabe 앱 행동 지침 (메인)

> **본 문서가 메인 규칙이다.** 충돌 시 `CLAUDE.md`가 우선한다.  
> `.cursorrules`는 보조 참고용이다.

상위 메인: `fastapi/CLAUDE.md` · `CLAUDE.md` (루트)

**패키지:** `kayfabe` · **API prefix:** `/ple`, `/rankings`, `/records`, `/title-history`, `/championship`

---

## 1–4. 행동 원칙 — Kayfabe 맥락 (요약)

- **구현 전:** 관련 기능 세트(`ple_*` / `ranking_*` / `records_*` / `championship_*` / `title_history_*`) Read · prefix·프론트 URL 확인
- **단순성:** 레이어 풀세트만 추가 · 아래 §네이밍 규칙 준수
- **정밀 수정:** 요청한 기능만 · `main.py`에 Kayfabe 로직 넣지 않음
- **목표 중심:** 본 문서 체크리스트 + curl 검증 + (해당 시) www Network 200

```text
1. router 등록 → /docs 경로 노출
2. interactor·repo → curl 200
3. www 연동 → 브라우저 Network 200
```

---

## 네이밍 규칙

| 구분 | 패턴 | 예시 |
|------|------|------|
| Router | `{도메인}_router.py` | `ple_events_router.py`, `title_acquisitions_router.py` |
| Interactor | `{기능}_interactor.py` | `ple_interactor.py` |
| Input port | `{기능}_use_case.py` | `ple_use_case.py` |
| Output port | `{기능}_repository.py` | `ple_repository.py` |
| PG adapter | `{기능}_pg_repository.py` | `ple_pg_repository.py` |
| Provider | `{기능}_provider.py` | `ple_provider.py` |
| Schema | `{기능}_schema.py` | `ple_schema.py` |
| DTO | `{기능}_dto.py` | `ple_dto.py` |
| Mapper | `{기능}_schema_mapper.py` | `ple_schema_mapper.py`, `ranking_schema_mapper.py` |

---

## 주요 설계 규칙

### 라우터 파일 구성 (4파일)

| 파일 | 포함 라우터 | 담당 엔드포인트 |
|------|-------------|----------------|
| `ple_events_router.py` | `ple_events_router` | PLE 이벤트 CRUD + SSE live |
| `ple_match_pick_router.py` | `ple_match_pick_router` + `ranking_router` | 예측 POST + 랭킹 GET |
| `ple_matches_router.py` | `ple_matches_router` + `records_router` | 경기결과 POST + 기록 GET |
| `title_acquisitions_router.py` | `title_acquisitions_router` + `championship_router` | 타이틀 히스토리 + 챔피언십 |

CQRS 분리는 **UseCase 레이어**에서 유지한다 (`PleUseCase` vs `PleInfoUseCase`). 라우터 파일은 도메인 개념으로 묶는다.

### DB 없는 기능
| 기능 | 출처 | 파일 |
|------|------|------|
| Championship | `championship_titles` 기준선 + 갱신 두 축(아래) | `adapter/outbound/pg/title_acquisitions_pg_repository.py` |
| Records | `ple_matches.card_json` 집계 | `app/services/records_scoring.py` |
| Title History | PostgreSQL (`title_history` 테이블) | `adapter/outbound/pg/title_history_pg_repository.py` |

### 챔피언 보드가 갱신되는 두 축

카탈로그(`app/services/current_championship_catalog.py`)는 **최초 시딩**만 한다. 사람이
고치지 않으면 보드가 낡으므로 갱신 경로가 둘 있고, 기준일(`championship_titles.as_of`)이
둘을 가른다.

| 축 | 재료 | 어디서 | 범위 |
|----|------|--------|------|
| 좁고 빠름 | PLE 경기 결과 | 읽기 경로(`get_board` → `domain/services/championship_succession.apply_results`) | PLE만 · 쓰기 없음 |
| 넓고 늦음 | 위키 현 챔피언 표 | `scripts/sync_champion_board_from_wiki.py`(사람이 실행) | Raw·하우스쇼까지 · 기준선을 쓴다 |

위키 동기화가 기준일을 읽은 날로 올리므로 그 이전 PLE는 `apply_results`의 기준일
관문이 건너뛴다. 스크립트는 **기본이 드라이런**이고 `--apply`로만 쓴다.

### UserModel 출처
`from core.entities.user_model import UserModel`

**앱이 아니라 공유 커널(`fastapi/core/`)에 있다.** `friday13th` → `superstar`를 거쳐
`core`로 내려왔다(`superstar` 앱은 2026-09-29에 삭제). `auth`에 두지 않은 이유가 규칙이다:
`kayfabe`가 FK 때문에 이걸 참조하는데 `auth`는 **아무도 import할 수 없는** 앱이라
(`.importlinter` `auth_isolation`) 거기 두면 계약이 즉시 깨진다.

### Provider 멱등성 패턴
```python
def get_X_repository(db: AsyncSession = Depends(get_db)) -> XRepository:
    return XPgRepository(db)

def get_X(repository: XRepository = Depends(get_X_repository)) -> XUseCase:
    return XInteractor(repository=repository)
```
하나의 함수에 repository + interactor 생성을 합치지 않는다.

---

## 레이어 구조

```
adapter/inbound/api/v1/        ← Router (HTTP 진입, 4파일)
adapter/inbound/api/schemas/   ← Pydantic 스키마 (Request/Response)
adapter/outbound/mappers/      ← Schema ↔ DTO 변환 (HTTP 경계)
dependencies/                  ← Provider (DI 조립)
app/ports/input/               ← UseCase 인터페이스 (*_use_case.py만 유지)
app/use_cases/                 ← Interactor (비즈니스 로직)
app/ports/output/              ← Repository 인터페이스
app/dtos/                      ← DTO
app/services/                  ← 도메인 서비스 (scoring, catalog)
adapter/outbound/pg/           ← PG Repository (PostgreSQL)
adapter/outbound/catalog/      ← Catalog Repository (정적 데이터)
adapter/outbound/orm/          ← SQLAlchemy ORM 모델
```

---

## HTTP API 요약

| 메서드  | 경로                                        | 라우터 파일                                            |
| ---- | ----------------------------------------- | ------------------------------------------------- |
| GET  | `/ple/events`                             | `ple_events_router`                               |
| GET  | `/ple/ai-stats`                           | `ple_events_router`                               |
| GET  | `/ple/results`                            | `ple_events_router`                               |
| GET  | `/ple/{slug}`                             | `ple_events_router`                               |
| GET  | `/ple/{slug}/live`                        | `ple_events_router` (SSE)                         |
| POST | `/ple/{slug}/sync-from-client`            | `ple_events_router`                               |
| POST | `/ple/{slug}/predictions/batch`           | `ple_match_pick_router`                           |
| POST | `/ple/{slug}/matches/{match_key}/predict` | `ple_match_pick_router`                           |
| POST | `/ple/{slug}/results/batch`               | `ple_matches_router`                              |
| POST | `/ple/{slug}/matches/{match_key}/result`  | `ple_matches_router`                              |
| GET  | `/rankings`                               | `ple_match_pick_router` (ranking_router)          |
| GET  | `/records/competitors`                    | `ple_matches_router` (records_router)             |
| GET  | `/records/competitors/{name}`             | `ple_matches_router` (records_router)             |
| GET  | `/title-history/competitors/{name}`       | `title_acquisitions_router`                       |
| POST | `/title-history/sync`                     | `title_acquisitions_router`                       |
| GET  | `/championship`                           | `title_acquisitions_router` (championship_router) |

> 예측 POST 시 body `userId` 필수 · 미제공 → **422** · DB에 없는 id → **401**

---

## ERD 참조

→ `KAYFABE_ERD.md`

---

## 형제 앱 (메인 규칙 위치)

| 앱 | CLAUDE.md |
|----|-----------|
| titanic | `titanic/_docs/CLAUDE.md` |
| **kayfabe** | 본 파일 |
| user | `user/_docs/CLAUDE.md` (추가 예정) |
