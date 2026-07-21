from __future__ import annotations

from ontology.adapter.outbound.convnext_image_classifier import ConvNextImageClassifier
from ontology.app.ports.input.image_classifier_use_case import ImageClassifierUseCase
from ontology.app.use_cases.image_classifier_interactor import ImageClassifierInteractor


def get_image_classifier_use_case() -> ImageClassifierUseCase:
    return ImageClassifierInteractor(classifier=ConvNextImageClassifier())
