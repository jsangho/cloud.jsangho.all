from pydantic import BaseModel


class ScrapeResultResponse(BaseModel):
    website: str
    keyword: str
    title: str | None
    meta_description: str | None
    body_text: str
    keyword_found: bool
    scraped_at: str
    saved_path: str
