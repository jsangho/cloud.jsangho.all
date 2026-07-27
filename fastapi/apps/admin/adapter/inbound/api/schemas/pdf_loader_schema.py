from pydantic import BaseModel, Field


class PdfLoaderResponseSchema(BaseModel):
    document_id: str = Field(..., description="Neo4j Document 노드 id")
    filename: str = Field(..., description="업로드한 원본 파일명")
    text: str = Field(..., description="PDF에서 추출한 전체 텍스트")
    char_count: int = Field(..., description="추출된 텍스트 길이(문자 수)")
