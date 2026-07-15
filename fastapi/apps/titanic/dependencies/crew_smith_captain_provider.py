from core.matrix.grid_oracle_database_manager import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from titanic.adapter.outbound.repositories.crew_smith_captain_repository import (
    SmithCaptainRepository,
)
from titanic.app.ports.input.crew_andrews_architect_use_case import (
    AndrewsArchitectUseCase,
)
from titanic.app.ports.input.crew_hartley_violin_use_case import HartleyViolinUseCase
from titanic.app.ports.input.crew_lowe_boat_use_case import LoweBoatUseCase
from titanic.app.ports.input.crew_smith_captain_use_case import SmithCaptainUseCase
from titanic.app.ports.input.crew_walter_roaster_use_case import WalterRoasterUseCase
from titanic.app.ports.input.passenger_cal_tester_use_case import CalTesterUseCase
from titanic.app.ports.input.passenger_jack_trainer_use_case import JackTrainerUseCase
from titanic.app.ports.input.passenger_rose_model_use_case import RoseModelUseCase
from titanic.app.ports.output.crew_smith_captain_port import SmithCaptainPort
from titanic.app.use_cases.crew_smith_captain_interactor import SmithCaptainInteractor
from titanic.dependencies.crew_andrews_architect_provider import get_andrews_architect
from titanic.dependencies.crew_hartley_violin_provider import get_hartley_violin
from titanic.dependencies.crew_lowe_boat_provider import get_lowe_boat
from titanic.dependencies.crew_walter_roaster_provider import get_walter_roaster
from titanic.dependencies.passenger_cal_tester_provider import get_cal_tester
from titanic.dependencies.passenger_jack_trainer_provider import get_jack_trainer
from titanic.dependencies.passenger_rose_model_provider import get_rose_model


def get_smith_captain_repository(
    db: AsyncSession = Depends(get_db),
) -> SmithCaptainPort:
    return SmithCaptainRepository(session=db)


def get_smith_captain(
    repository: SmithCaptainPort = Depends(get_smith_captain_repository),
    andrews: AndrewsArchitectUseCase = Depends(get_andrews_architect),
    jack: JackTrainerUseCase = Depends(get_jack_trainer),
    rose: RoseModelUseCase = Depends(get_rose_model),
    cal: CalTesterUseCase = Depends(get_cal_tester),
    walter: WalterRoasterUseCase = Depends(get_walter_roaster),
    lowe: LoweBoatUseCase = Depends(get_lowe_boat),
    hartley: HartleyViolinUseCase = Depends(get_hartley_violin),
) -> SmithCaptainUseCase:
    return SmithCaptainInteractor(
        repository=repository,
        andrews=andrews,
        jack=jack,
        rose=rose,
        cal=cal,
        walter=walter,
        lowe=lowe,
        hartley=hartley,
    )
