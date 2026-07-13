from heyman.adapter.outbound.repositories.judge_repository import JudgePgRepository
from heyman.app.ports.input.judge_use_case import JudgeUseCase
from heyman.app.use_cases.judge_interactor import JudgeInteractor


def get_judge_use_case() -> JudgeUseCase:
    return JudgeInteractor(repository=JudgePgRepository())
