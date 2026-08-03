from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from kayfabe.adapter.outbound.pg.shop_pg_repository import ShopPgRepository
from kayfabe.app.ports.input.shop_use_case import ShopUseCase
from kayfabe.app.ports.output.shop_repository import ShopRepository
from kayfabe.app.use_cases.shop_interactor import ShopInteractor


def get_shop_repository(db: AsyncSession = Depends(get_db)) -> ShopRepository:
    return ShopPgRepository(db=db)


def get_shop_use_case(
    repository: ShopRepository = Depends(get_shop_repository),
) -> ShopUseCase:
    return ShopInteractor(repository=repository)
