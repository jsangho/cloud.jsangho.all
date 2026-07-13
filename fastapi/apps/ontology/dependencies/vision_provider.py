from ontology.adapter.outbound.repositories.vision_s3_repository import VisionS3Repository
from ontology.app.ports.input.vision_use_case import VisionUseCase
from ontology.app.use_cases.vision_interactor import VisionInteractor


def get_vision_use_case() -> VisionUseCase:
    return VisionInteractor(repository=VisionS3Repository())
