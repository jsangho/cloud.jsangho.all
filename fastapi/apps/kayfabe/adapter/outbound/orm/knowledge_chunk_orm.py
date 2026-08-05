"""예측 근거 지식 청크 — `_docs/ai-match-predictions-harness.md` §6.

`wrestlers.embedding`과 **같은 좌표계**를 쓴다(bge-m3 · `normalize_embeddings=True` ·
`EMBEDDING_DIM`). 벡터 DB를 새로 도입하지 않는 이유는 §2-D3.

`source_url`을 `nullable=False`로 둔 것은 실수를 막는 장치다 — 출처를 못 붙이는 지식은
근거로 쓰지 않는다(§3-D6). 애플리케이션 검증만으로는 수집 스크립트가 우회할 수 있다.
"""

from __future__ import annotations

from datetime import datetime

from core.matrix.grid_oracle_database_manager import Base
from core.matrix.vault_keymaker_secret_manager import EMBEDDING_DIM
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class KnowledgeChunkModel(Base):
    """수집한 공개 소스 한 조각."""

    __tablename__ = "ple_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_knowledge_chunk_content"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    #: 출처 주소. 화면에 그대로 노출되므로 축약·리다이렉트 주소를 넣지 않는다.
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    #: 허용 도메인 목록(§3-D10) 대조와 사후 감사를 위해 따로 둔다.
    #: ToS가 바뀐 도메인의 청크만 골라 지울 수 있어야 한다.
    source_domain: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: 원문 게시 시각. 알 수 없으면 NULL — 수집 시각으로 대체하지 않는다.
    #: 6개월 전 부상 소식을 오늘 것으로 둔갑시키면 예측이 통째로 틀어진다.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    #: 본문 sha256. 재수집 시 같은 글이 여러 벌 쌓여 검색 결과를 독식하는 것을 막는다.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 임베딩 실패·지연 적재를 허용해 NULL을 둔다. 검색은 NULL 행을 건너뛴다.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
