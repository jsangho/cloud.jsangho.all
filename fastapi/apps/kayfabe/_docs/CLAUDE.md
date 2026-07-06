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
| Championship | 정적 카탈로그 | `app/services/current_championship_catalog.py` |
| Records | `ple_matches.card_json` 집계 | `app/services/records_scoring.py` |
| Title History | Neon DB (`title_history` 테이블) | `adapter/outbound/pg/title_history_pg_repository.py` |

### UserModel 출처
`from superstar.domain.entities.user_model import UserModel`  
(구 `friday13th` → `superstar` 앱으로 이전됨)

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
adapter/outbound/pg/           ← PG Repository (Neon)
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
