from dataclasses import dataclass


@dataclass(frozen=True)
class VisionQuery:
    id: int
    name: str


@dataclass
class VisionResponse:
    id: int
    name: str
    description: str


@dataclass
class VisionImageUploadResult:
    filename: str
    content_type: str
    size_bytes: int
    saved_path: str
