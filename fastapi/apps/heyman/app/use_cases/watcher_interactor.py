from __future__ import annotations

from heyman.app.dtos.receiver_dto import ReceiverCommand
from heyman.app.dtos.watcher_dto import (
    WatcherFilterResult,
    WatcherQuery,
    WatcherResponse,
)
from heyman.app.ports.input.watcher_use_case import WatcherUseCase
from heyman.app.ports.output.receiver_repository import ReceiverRepository
from heyman.app.ports.output.watcher_repository import WatcherRepository
from ontology.app.ports.input.spam_classifier_use_case import SpamClassifierUseCase
from ontology.domain.enums.spam_classes import SpamLabel


class WatcherInteractor(WatcherUseCase):
    def __init__(
        self,
        repository: WatcherRepository,
        spam_classifier: SpamClassifierUseCase,
        receiver_repository: ReceiverRepository,
    ) -> None:
        self._repository = repository
        self._spam_classifier = spam_classifier
        self._receiver_repository = receiver_repository

    async def introduce_myself(self, query: WatcherQuery) -> WatcherResponse:
        return await self._repository.introduce_myself(query)

    async def filter_and_forward(self, cmd: ReceiverCommand) -> WatcherFilterResult:
        """KcELECTRA로 1차 분류한다. ham이 아니면 저장 자체를 하지 않는다."""
        classification = await self._spam_classifier.classify(cmd.subject, cmd.body)
        if classification.label != SpamLabel.HAM.value:
            return WatcherFilterResult(
                id=None,
                label=classification.label,
                confidence=classification.confidence,
                forwarded=False,
            )
        item_id = await self._receiver_repository.save(
            cmd, classification.label, classification.confidence
        )
        return WatcherFilterResult(
            id=item_id,
            label=classification.label,
            confidence=classification.confidence,
            forwarded=True,
        )
