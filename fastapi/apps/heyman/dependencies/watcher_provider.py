from heyman.adapter.outbound.repositories.receiver_repository import (
    ReceiverPgRepository,
)
from heyman.adapter.outbound.repositories.watcher_repository import WatcherPgRepository
from heyman.app.ports.input.watcher_use_case import WatcherUseCase
from heyman.app.use_cases.watcher_interactor import WatcherInteractor
from ontology.dependencies.spam_classifier_provider import (
    get_kcelectra_spam_classifier_use_case,
)


def get_watcher_use_case() -> WatcherUseCase:
    return WatcherInteractor(
        repository=WatcherPgRepository(),
        spam_classifier=get_kcelectra_spam_classifier_use_case(),
        receiver_repository=ReceiverPgRepository(),
    )
