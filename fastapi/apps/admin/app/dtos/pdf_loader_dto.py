from dataclasses import dataclass


@dataclass(frozen=True)
class PdfLoaderCommand:
    filename: str
    content: bytes


@dataclass(frozen=True)
class PdfLoaderResult:
    document_id: str
    filename: str
    text: str
    char_count: int
