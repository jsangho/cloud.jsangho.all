# Titanic 앱 행동 지침 (메인)

> **본 문서가 메인 규칙이다.** 충돌 시 이 문서가 우선한다.

상위 메인: `fastapi/CLAUDE.md` · `CLAUDE.md` (루트)

**패키지:** `titanic` (`fastapi/apps/titanic/`)  
**API prefix:** `/titanic` — `adapter/inbound/api/__init__.py`

> **시블링 템플릿:** kayfabe 등 새 앱은 동일한 헥사고날 폴더 구조를 복제한다.  
> 앱마다 router prefix · 도메인 네이밍 · ERD만 바꾼다.

---

## 0. 구현 전

1. `fastapi/CLAUDE.md` — 백엔드 공통 원칙
2. `_claude/ENTITY_RULE.md` — DB 엔티티 규칙
3. 기존 **가장 가까운 형제 리소스**를 Read한다. (예: crew 추가 시 `crew_smith_captain_*` 세트 복제)

---

## 1. 디렉터리 구조

```
titanic/
├── adapter/
│   ├── inbound/api/
│   │   ├── __init__.py          # titanic_router (prefix="/titanic")
│   │   ├── schemas/             # Pydantic *Schema
│   │   └── v1/                  # *_router.py
│   └── outbound/
│       ├── pg/                  # *_pg_repository.py
│       ├── orm/                 # SQLAlchemy/SQLModel ORM
│       └── mappers/             # ORM ↔ DTO
├── app/
│   ├── dtos/                    # *Dto, *Query, *Response
│   ├── ports/input/             # *UseCase (Protocol)
│   ├── ports/output/            # *Repository (Protocol)
│   └── use_cases/               # *_interactor.py
├── dependencies/                # get_* provider (FastAPI Depends)
├── domain/                      # (필요 시) 엔티티·값 객체
├── tests/                       # adapter·app 미러 구조
└── _docs/
    └── CLAUDE.md                # 본 파일
```

---

## 2. 네이밍 규칙

리소스는 **역할군_인물_직함** 형태로 통일한다.

| 접두 | 예 | 라우터 prefix |
|------|-----|--------------|
| `crew_` | `crew_smith_captain` | `/smith` |
| `passenger_` | `passenger_rose_model` | `/rose` |

파일·클래스 접미사:

| 종류 | 패턴 |
|------|------|
| Router | `*_router.py` · `APIRouter(prefix="/...")` |
| Schema | `*_schema.py` · `*Schema` |
| UseCase port | `*_use_case.py` · `*UseCase` (Protocol) |
| Interactor | `*_interactor.py` · `*Interactor` |
| Repository port | `*_repository.py` · `*Repository` (Protocol) |
| PG repo | `*_pg_repository.py` · `*PgRepository` |
| Provider | `*_provider.py` · `get_*` |
| DTO | `*_dto.py` · `*Dto` |

새 캐릭터 추가 시 위 세트를 **한 세트로** 추가하고 `__init__.py`에 router를 등록한다.

---

## 3. 레이어 책임

- **Router:** HTTP 입출력만. `Depends(get_<resource>)`로 UseCase 주입.
- **Interactor:** 비즈니스 흐름. Repository port에만 의존.
- **PgRepository:** SQL·ORM. inbound schema가 아닌 DTO로 변환.
- **Provider:** `get_db` → Repository → Interactor 조립.

```
POST /titanic/smith/chat
  → crew_smith_captain_router
  → SmithCaptainInteractor.chat()
  → SmithCaptainPgRepository.chat()
```

---

## 4. 등록 체크리스트 (새 리소스)

- [ ] `adapter/inbound/api/v1/<name>_router.py`
- [ ] `adapter/inbound/api/schemas/<name>_schema.py`
- [ ] `app/ports/input/<name>_use_case.py`
- [ ] `app/ports/output/<name>_repository.py`
- [ ] `app/use_cases/<name>_interactor.py`
- [ ] `adapter/outbound/pg/<name>_pg_repository.py`
- [ ] `dependencies/<name>_provider.py`
- [ ] `adapter/inbound/api/__init__.py`에 `include_router`
- [ ] 프론트(`www`) API 경로가 `/titanic/...`와 일치하는지 확인

---

## 5. 프론트 연동

- Titanic UI: `www/app/lesson/titanic/`, `www/components/smith-captain-chat.tsx`
- API base: `www/lib/api.ts` — Titanic 전용 URL 사용 시 백엔드 prefix와 맞출 것

---

## 6. 형제 앱

| 앱 | prefix | 규칙 위치 |
|----|--------|-----------|
| **titanic** | `/titanic` | 본 파일 |
| kayfabe | `/ple` 등 | `kayfabe/_docs/CLAUDE.md` |

---

## 7. 도메인 문서 연결

- 타이타닉 피처 정리: [[titanic-features]]
- 타이타닉 머신러닝: [[titanic-machine-learning]]
- 타이타닉 ERD: [[titanic-erd]]
- 타이타닉 NF: [[titanic-nf]]
- 타이타닉 알고리즘: [[titanic-algorithm]]
- 타이타닉 월터: [[titanic-walter]]
