from __future__ import annotations

from lion_king.adapter.outbound.repositories.photo_s3_repository import (
    PhotoS3Repository,
)
from lion_king.app.ports.input.photo_use_case import PhotoUseCase
from lion_king.app.use_cases.photo_interactor import PhotoInteractor


def get_photo_use_case() -> PhotoUseCase:
    return PhotoInteractor(PhotoS3Repository())
