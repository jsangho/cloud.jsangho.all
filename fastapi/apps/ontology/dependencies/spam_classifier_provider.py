from __future__ import annotations

from ontology.adapter.outbound.kcelectra_spam_classifier import KcElectraSpamClassifier
from ontology.adapter.outbound.ollama_spam_classifier import OllamaSpamClassifier
from ontology.app.ports.input.spam_classifier_use_case import SpamClassifierUseCase
from ontology.app.use_cases.spam_classifier_interactor import SpamClassifierInteractor


def get_spam_classifier_use_case() -> SpamClassifierUseCase:
    return SpamClassifierInteractor(classifier=OllamaSpamClassifier())


def get_kcelectra_spam_classifier_use_case() -> SpamClassifierUseCase:
    return SpamClassifierInteractor(classifier=KcElectraSpamClassifier())
