from heyman.adapter.outbound.repositories.juso_repository import JusoPgRepository
from heyman.app.ports.input.juso_use_case import JusoUseCase
from heyman.app.use_cases.juso_interactor import JusoInteractor


def get_juso_use_case() -> JusoUseCase:
    return JusoInteractor(repository=JusoPgRepository())
