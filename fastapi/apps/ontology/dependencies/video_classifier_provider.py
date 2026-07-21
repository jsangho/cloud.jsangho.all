from __future__ import annotations

from ontology.adapter.outbound.videomae_video_classifier import VideoMaeVideoClassifier
from ontology.app.ports.input.video_classifier_use_case import VideoClassifierUseCase
from ontology.app.use_cases.video_classifier_interactor import VideoClassifierInteractor


def get_video_classifier_use_case() -> VideoClassifierUseCase:
    return VideoClassifierInteractor(classifier=VideoMaeVideoClassifier())
