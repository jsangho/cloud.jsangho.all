# 포인트 원장 · 상점 설계

작성 2026-07-29. 대상 앱 `kayfabe` (spoke).

## 1. 왜 원장이 필요한가

지금 포인트는 **파생값**이다. `PleMatchPickPgRepository._aggregated_subquery()`가 적중한
예측의 `PleMatchModel.point_value`를 `SUM`해서 `score`로 내보내고, 프론트는 그 값을 그대로
"보유 포인트"로 표시한다. 저장된 잔액도, 지출 기록도, 인벤토리도 없다(ORM 검색 0건).

즉 **구매라는 개념이 존재하지 않는다.** 상점의 선행 작업은 화면이 아니라 이 원장이다.

## 2. 핵심 제약 — 획득액은 사후에 변한다

`refresh_all_match_point_values()`가 저장된 `point_value`를 재계산한다. 배점 상수를 바꾸면
**과거 경기의 획득액이 소급 변경된다**(2026-07-29에 실제로 1~5 → 10~50으로 바꿨다).

여기서 두 가지가 따라온다.

1. **잔액을 컬럼에 저장하면 안 된다.** 획득액이 바뀌는 순간 어긋난다.
   → `보유 = 파생 획득액 + SUM(원장 금액)` 으로 매번 계산한다.

2. **획득액이 줄어들면 잔액이 음수가 될 수 있다.** 이미 쓴 포인트보다 획득액이 낮아지는
   경우다. 이걸 막으려면 배점 변경이 **의도적인 관리 작업**이어야 한다.

### 2-1. 선행 수정 (필수)

`refresh_all_match_point_values()`는 현재 `list_rankings()`에서 **순위표 조회마다** 호출된다
(`ple_match_pick_interactor.py:53`). 이 상태로 원장을 올리면 아무 때나 잔액이 흔들린다.

→ 이 호출을 순위표 경로에서 떼고, 관리자 액션 또는 배점 변경 시 1회 실행으로 옮긴다.
그 시점에 "획득액이 지출액보다 낮아지는 사용자"를 조회해 보정 항목을 넣을 수 있다.
전체 테이블 갱신을 매 요청에 하지 않게 되므로 성능 문제도 같이 해소된다.

## 3. 테이블

`ENTITY_RULE` 준수 — PK는 `id: int` autoincrement, FK는 `{테이블}_id: int`,
비즈니스 식별자는 `unique=True, index=True` 별도 컬럼.

### 3-1. `shop_items` — 상품 카탈로그

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `id` | int PK | |
| `code` | str unique index | `title_table_master` 등 안정 식별자 |
| `name` | str | 표시명 |
| `description` | str | |
| `price` | int | **서버가 유일한 가격 출처.** 클라이언트 값을 믿지 않는다 |
| `category` | str | `title` · `nickname_color` · `badge` · `report` · `hof` |
| `is_consumable` | bool | 소모성(여론 리포트) vs 영구(뱃지) |
| `is_active` | bool | 판매 중단을 삭제로 하지 않는다 (구매 이력이 FK로 남는다) |

카탈로그를 코드 상수가 아니라 테이블로 두는 이유: 가격 조정과 판매 중단을 배포 없이 하고,
구매 이력이 참조할 대상이 필요하다.

**`report`·`hof` 카테고리는 스키마에만 있고 카탈로그에는 없다** (2026-08-03 결정).
살 수는 있는데 아무 일도 일어나지 않는 상품을 두지 않기로 했다.

- `report`(여론 리포트)가 팔려던 **예측 분포는 이미 무료로 공개돼 있다.**
  `MatchBoardSchema.siteVotes`가 좌/우·다자 득표수를 그대로 내려주고 브라켓 UI가
  막대로 표시한다(`www/components/ple/ple-match-bracket.tsx`). 유료로 만들려면
  무료 분포에 **없는 것**(예: 점수 상위 사용자만의 선택)을 담아야 하는데, 그건 별도 설계다.
- `hof`(명예의 전당)는 구매 효과가 나타날 화면이 아직 없다. 헌액자를 보여주는 자리가
  생기면 그때 카탈로그에 넣는다.

소모성(`is_consumable`) 처리와 `context_key` 구매 경로는 **코드에 그대로 남겨 둔다** —
동작하고 테스트도 있으므로, 소모성 상품이 생기면 카탈로그 한 줄로 되살아난다.

### 3-2. `point_ledger_entries` — 원장 (지출·환급·보정)

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `id` | int PK | |
| `user_id` | int FK → `users.id` | index |
| `amount` | int | **부호 있음.** 지출 음수, 환급·지급 양수 |
| `entry_type` | str | `purchase` · `refund` · `admin_grant` · `reconcile` |
| `shop_item_id` | int FK nullable | 구매/환급일 때만 |
| `memo` | str | 보정 사유 등 |
| `created_at` | datetime | server_default |

**획득(earn)은 원장에 넣지 않는다.** 획득의 단일 출처는 예측 × 배점 집계다. 원장에
복제하면 두 정의가 갈라진다.

부호 있는 단일 테이블로 한 이유: 환급은 사실상 확정된 요구(구매 실패·관리자 정정)이고,
지출 전용 테이블로 두면 곧바로 스키마를 다시 고쳐야 한다. 테이블을 늘리는 대신 부호로 푼다.

**원장은 추가 전용(append-only)이다.** 수정·삭제하지 않고 반대 부호 항목을 넣는다.

### 3-3. `user_shop_items` — 보유·장착

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `id` | int PK | |
| `user_id` | int FK → `users.id` | index |
| `shop_item_id` | int FK → `shop_items.id` | index |
| `context_key` | str, default `""` | 소모성 아이템의 사용 대상 (예: `match:123`) |
| `is_equipped` | bool | 장착 상태 |
| `acquired_at` | datetime | server_default |

제약: `UniqueConstraint(user_id, shop_item_id, context_key)`

> **Postgres 함정:** `context_key`를 nullable로 두면 안 된다. Postgres는 `NULL != NULL`로
> 취급해서 유니크 제약이 중복을 막지 못한다. 영구 아이템은 빈 문자열 `""`을 쓴다.

이 제약이 **멱등성**을 준다. 같은 뱃지 두 번 구매 불가, 같은 경기 여론 리포트 두 번 결제 불가.
`PlePredictionModel`이 `UniqueConstraint(match_id, user_id)`로 중복 예측을 막는 것과 같은 방식이다.

**장착은 카테고리당 하나다.** 순위표가 칭호·닉네임 색상·뱃지를 각각 한 자리에만 그리므로
(`COSMETIC_CATEGORIES`), 장착 시 같은 카테고리의 다른 장착을 서버가 함께 내린다. 사용자에게
해제를 먼저 시키지 않는 이유는, 그러면 둘 다 "장착 중"인데 순위표에는 하나만 나오는 상태가
생기기 때문이다. 소모성 리포트·명예의 전당은 순위표에 자리가 없어 이 규칙에서 뺀다.

DB 제약이 아니라 쓰기 경로의 규칙으로 둔 것은, 부분 유니크 인덱스
(`WHERE is_equipped`)로 막으면 교체가 "해제 후 장착" 2단계가 되어 중간 상태에서
실패하면 아무것도 장착되지 않은 채로 남기 때문이다.

원장과 보유를 나눈 이유: 원장은 불변 기록이고, 장착 상태는 계속 바뀐다. 한 테이블에 섞으면
불변성이 깨진다.

## 4. 잔액 계산

```
보유 = 파생_획득액(적중 배점 합계) + COALESCE(SUM(point_ledger_entries.amount), 0)
```

`파생_획득액`은 순위표가 쓰는 것과 **같은 집계**여야 한다. 지금 그 로직은
`PleMatchPickPgRepository._aggregated_subquery()` 안에 있다. 상점이 별도로 다시 구현하면
"포인트"의 정의가 둘로 갈라진다 — 프론트가 이미 `score == 보유 포인트`를 전제로 표시하고
있으므로 특히 위험하다.

→ 획득액 집계를 재사용 가능한 형태로 분리하고 두 경로가 같은 것을 쓴다.

## 5. 동시성 — 이중 결제 방지

잔액 확인과 원장 삽입 사이에 다른 요청이 끼면 잔액을 초과해 쓸 수 있다. 유니크 제약은
같은 아이템 중복만 막고, **서로 다른 아이템 두 개를 동시에 사는 경우**는 막지 못한다.

→ 구매 트랜잭션 시작에서 해당 사용자 행을 잠근다.

```sql
SELECT id FROM users WHERE id = :user_id FOR UPDATE;
```

그 다음 잔액 계산 → 가격 비교 → 원장 삽입 → 보유 삽입을 **한 트랜잭션**에서 수행한다.
사용자별 잠금이므로 다른 사용자의 구매를 막지 않는다.

## 6. 레이어 구성

`fastapi/CLAUDE.md` §2 의존성 방향(`adapter → app → domain`)과 §4 네이밍을 따른다.
경로 표기는 `kayfabe.` 로 시작한다 (루트 §0-3).

```
kayfabe/
  domain/
    value_objects/point_balance.py      # 순수 계산: 잔액, 구매 가능 판정
  app/
    dtos/shop_dto.py
    ports/input/shop_use_case.py        # ShopUseCase (Protocol)
    ports/output/shop_repository.py     # ShopRepository (Protocol)
    use_cases/shop_interactor.py        # ShopInteractor
  adapter/
    inbound/api/v1/shop_router.py       # prefix="/shop"
    inbound/api/schemas/shop_schema.py
    outbound/orm/shop_orm.py            # ShopItemModel, PointLedgerEntryModel, UserShopItemModel
    outbound/pg/shop_pg_repository.py   # ShopPgRepository
    outbound/mappers/shop_schema_mapper.py
  dependencies/shop_provider.py         # get_shop_use_case()
```

도메인에 두는 것은 프레임워크 없이 판단 가능한 규칙뿐이다 — 잔액 산술, 가격 비교,
소모성/영구 구분에 따른 중복 보유 판정. SQLAlchemy·FastAPI를 import하면 즉시 위반이다.

## 7. API

인증은 기존 RS256 게이트웨이를 쓴다. **사용자 식별은 토큰에서만** 얻는다 —
요청 본문의 `user_id`를 신뢰하면 남의 포인트를 쓸 수 있다.

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/shop/items` | 카탈로그 (`is_active`만) |
| GET | `/shop/wallet` | `{earned, spent, balance}` |
| POST | `/shop/purchases` | 구매 — 본문 `{itemCode, contextKey?}` |
| GET | `/shop/inventory` | 보유 + 장착 상태 |
| PATCH | `/shop/inventory/{id}` | 장착·해제 |

구매 실패 응답은 사유를 구분한다 — 잔액 부족(402/409), 중복 보유(409),
판매 중단(404/410). 프론트가 문구를 다르게 보여줄 수 있어야 한다.

## 8. 프론트 후속 작업

현재 `www/lib/rankings-api.ts`의 `fetchMyPoints()`는 순위표 `score`를 보유 포인트로 쓴다.
지출이 생기면 이 값은 **획득액**이 되어 실제 잔액과 어긋난다.

→ 원장이 올라가면 `fetchMyPoints()`를 `GET /shop/wallet`의 `balance`로 교체한다.
내비 칩(`components/user-nav-badge.tsx`)과 내 정보의 "획득 포인트" 표기도 함께 정리한다.
"획득 포인트"와 "보유 포인트"를 구분해 보여줄지는 그때 결정한다.

## 9. 마이그레이션

`alembic revision --autogenerate` → `upgrade head`. 지출 이력이 없으므로 **백필이 없다.**
카탈로그 초기 데이터만 넣는다. `alembic/`은 ruff 검사 제외 대상이니 생성 파일을 손보지 않는다.

카탈로그 시드는 마이그레이션이 아니라 별도 스크립트다 —
`kayfabe/scripts/seed_shop_items.py`. 마이그레이션에 넣지 않은 이유는, 상품 목록이
스키마가 아니라 **운영 중 바뀌는 데이터**이기 때문이다. 가격 조정·판매 중단을 마이그레이션
이력에 남기면 되돌리기가 어려워진다. 스크립트는 없는 `code`만 넣으므로 여러 번 실행해도
운영 값을 덮지 않는다.

```bash
cd fastapi
PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/seed_shop_items.py
```

## 10. 구현 순서

1. §2-1 선행 수정 — `refresh_all_match_point_values()`를 순위표 경로에서 분리
2. 획득액 집계 분리 (순위표·상점 공용)
3. ORM 3개 + alembic 마이그레이션
4. `ShopPgRepository` — 잔액 조회, 구매(잠금 포함), 보유 조회
5. `ShopInteractor` + 라우터 + provider
6. 프론트: `/shop/wallet` 연결, 카탈로그·구매 UI
7. 상품 3종(칭호·닉네임 컬러·뱃지)을 순위표 렌더링에 붙이기
8. 카탈로그 시드 투입 (§9) — 이걸 하기 전까지 상점은 빈 목록이다

1·2번을 먼저 하는 이유는 그것 없이 원장을 올리면 잔액이 임의로 흔들리기 때문이다.
