from manager.adapter.outbound.repositories.juso_repository import JusoPgRepository
from manager.app.ports.input.juso_use_case import JusoUseCase
from manager.app.use_cases.juso_interactor import JusoInteractor


def get_juso_use_case() -> JusoUseCase:
    return JusoInteractor(repository=JusoPgRepository())
