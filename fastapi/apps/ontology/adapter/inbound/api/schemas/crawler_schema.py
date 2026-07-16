from pydantic import BaseModel


class CrawlResultResponse(BaseModel):
    website: str
    keyword: str
    status_code: int
    fetched_at: str
    content_length: int
    saved_path: str
