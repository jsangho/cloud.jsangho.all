"""상점 카탈로그 초기 데이터를 넣는다 (`shop-point-ledger.md` §9).

카탈로그를 코드 상수가 아니라 테이블로 둔 구조이므로(§3-1), 상품이 하나도 없으면
상점 화면은 빈 목록이고 순위표 치장 아이템도 살 수 없다. 이 스크립트가 그 초기 행을 만든다.

**이미 있는 `code`는 건드리지 않는다.** 운영에서 가격을 조정했거나 판매를 중단해 둔
상품을 재실행이 되돌리면 안 된다. 없는 것만 넣으므로 여러 번 실행해도 안전하다.
가격 변경·판매 중단은 이 스크립트가 아니라 DB에서 직접 한다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/seed_shop_items.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import select  # noqa: E402

from kayfabe.adapter.outbound.orm.shop_orm import (  # noqa: E402
    ShopItemCategory,
    ShopItemModel,
)

# 가격 기준: 적중 1건이 10~50점이다(`ple_scoring.py`). PLE 한 대회가 7경기 안팎이므로
# 꾸준히 맞히는 사용자의 한 대회 획득액은 100~250점 수준이다. 그 감각에 맞춰
# 입문 아이템은 대회 1회, 상위 아이템은 여러 대회를 모아야 닿도록 잡았다.
# 배점이 5의 배수라 가격도 5의 배수로 맞춘다.


def _catalog() -> list[ShopItemModel]:
    """초기 카탈로그 — 순위표에 실제로 표시되는 치장 아이템만 넣는다.

    `nickname_color_*` 코드는 프론트 `www/components/ranking-cosmetics.tsx`의
    색상 표에 있는 것과 **정확히 같아야** 한다. 어긋나면 구매는 되는데 순위표에
    색이 안 붙는다. 새 색상을 추가하려면 양쪽을 함께 고친다.
    """
    return [
        # 칭호 — 순위표 닉네임 앞에 붙는다
        ShopItemModel(
            code="title_rookie",
            name="루키",
            description="첫 칭호. 예측을 시작한 사람의 표식입니다.",
            price=100,
            category=ShopItemCategory.TITLE,
        ),
        ShopItemModel(
            code="title_main_eventer",
            name="메인 이벤터",
            description="메인 이벤트를 읽어내는 사람에게.",
            price=300,
            category=ShopItemCategory.TITLE,
        ),
        ShopItemModel(
            code="title_table_master",
            name="테이블의 지배자",
            description="순위표 상단을 오래 지킨 사람의 칭호.",
            price=500,
            category=ShopItemCategory.TITLE,
        ),
        ShopItemModel(
            code="title_rumble_prophet",
            name="럼블의 예언자",
            description="30인의 혼돈 속에서 승자를 짚어내는 눈.",
            price=800,
            category=ShopItemCategory.TITLE,
        ),
        # 닉네임 색상 — 순위표 닉네임 색을 덮는다
        ShopItemModel(
            code="nickname_color_gold",
            name="골드 닉네임",
            description="순위표에서 이름을 금색으로 표시합니다.",
            price=400,
            category=ShopItemCategory.NICKNAME_COLOR,
        ),
        ShopItemModel(
            code="nickname_color_crimson",
            name="크림슨 닉네임",
            description="순위표에서 이름을 붉은색으로 표시합니다.",
            price=250,
            category=ShopItemCategory.NICKNAME_COLOR,
        ),
        ShopItemModel(
            code="nickname_color_azure",
            name="애저 닉네임",
            description="순위표에서 이름을 하늘색으로 표시합니다.",
            price=250,
            category=ShopItemCategory.NICKNAME_COLOR,
        ),
        ShopItemModel(
            code="nickname_color_emerald",
            name="에메랄드 닉네임",
            description="순위표에서 이름을 초록색으로 표시합니다.",
            price=250,
            category=ShopItemCategory.NICKNAME_COLOR,
        ),
        ShopItemModel(
            code="nickname_color_violet",
            name="바이올렛 닉네임",
            description="순위표에서 이름을 보라색으로 표시합니다.",
            price=250,
            category=ShopItemCategory.NICKNAME_COLOR,
        ),
        # 뱃지 — 순위표 닉네임 뒤에 붙는다
        ShopItemModel(
            code="badge_day_one",
            name="데이 원",
            description="처음부터 함께한 사람의 뱃지.",
            price=150,
            category=ShopItemCategory.BADGE,
        ),
        ShopItemModel(
            code="badge_underdog",
            name="언더독 헌터",
            description="역배를 노리는 사람의 뱃지.",
            price=350,
            category=ShopItemCategory.BADGE,
        ),
        ShopItemModel(
            code="badge_perfect_card",
            name="퍼펙트 카드",
            description="한 대회를 통째로 맞힌 사람의 뱃지.",
            price=600,
            category=ShopItemCategory.BADGE,
        ),
        # `report`·`hof` 카테고리 상품은 넣지 않는다 — 이유는 `shop-point-ledger.md` §3-1.
        # 요약: 여론 리포트가 팔려던 예측 분포는 이미 `siteVotes`로 무료 공개돼 있고,
        # 명예의 전당은 구매 효과가 나타날 화면이 아직 없다. 살 수 있는데 아무 일도
        # 일어나지 않는 상품을 카탈로그에 두지 않는다.
    ]


async def main() -> None:
    catalog = _catalog()

    async with AsyncSessionLocal() as session:
        existing = set(
            (await session.execute(select(ShopItemModel.code))).scalars().all()
        )
        added = [item for item in catalog if item.code not in existing]
        session.add_all(added)
        await session.commit()

    skipped = len(catalog) - len(added)
    print(
        f"상점 카탈로그 시드 완료 — 추가 {len(added)}건, 이미 있어 건너뜀 {skipped}건"
    )
    for item in added:
        print(f"  + {item.code} ({item.category}) {item.price}P")


if __name__ == "__main__":
    asyncio.run(main())
