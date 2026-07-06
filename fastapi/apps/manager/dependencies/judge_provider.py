from manager.adapter.outbound.repositories.judge_repository import JudgePgRepository
from manager.app.ports.input.judge_use_case import JudgeUseCase
from manager.app.use_cases.judge_interactor import JudgeInteractor


def get_judge_use_case() -> JudgeUseCase:
    return JudgeInteractor(repository=JudgePgRepository())
