"""검색 질의와 읽은 본문 스냅샷 (Phase 3)

**예측 하나를 집어 "그때 무엇을 읽었는가"를 DB만으로 재구성하려 했더니 두 군데가
비어 있었다.**

1. `ple_agent_predictions.knowledge_query` — 지식 검색에 실제로 던진 질의.
   경기 제목과 선택지 이름에서 만들어지므로 **파생값처럼 보이지만**, 카드가 바뀌면
   재료가 사라진다. 실제로 경기 행이 없어진 예측(`withdrawn_match`)이 이미 하나
   있고, 그 예측의 질의는 지금 어디에서도 복원되지 않는다. 파생 가능성은 재료가
   남아 있을 때만 성립한다.

2. `ple_prediction_retrievals.content` — 그때 프롬프트에 들어간 본문 그대로.
   지금까지는 `content_hash`만 남겼는데, 해시는 **같은 글인지 대조**만 해 줄 뿐
   무엇을 읽었는지는 복원하지 못한다. 재수집이 그 URL의 옛 청크를 통째로 지우므로
   (`replace_document_chunks`), 원문은 그 순간 세상에서 사라진다. 나머지 칸과 똑같은
   이유로 값을 베껴 둔다 — **증거가 필요한 시점에 증거가 있어야 한다.**

   저장 대상은 수집 허용 도메인(§3-D10)의 글뿐이다. 코퍼스에 넣을 수 없는 글은
   애초에 검색되지 않으므로 하네스 §4-8(유료 기사 본문 저장 금지)을 새로 건드리지
   않는다. 지금 코퍼스는 100% 위키다.

**둘 다 nullable이고 백필하지 않는다.** 기존 20건은 질의도 본문도 기록된 적이 없고,
지금 값으로 채우면 "그때 읽은 것"이 아니라 "지금 검색되는 것"을 적는 것이 된다 —
Phase 3-13이 검색 기록을 비워 둔 것과 같은 이유다. NULL이 정직한 상태다.

**판정 규칙은 이 칸들을 보지 않는다.** `ai_lab_evaluation.py`가 읽는 것은 여전히
`source_url`·`source_revised_at`뿐이므로 **기존 예측의 자격 판정은 한 건도 움직이지
않는다.**

Revision ID: e7d2b5a91c46
Revises: c1a9e4d8f523
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7d2b5a91c46"
down_revision: str | Sequence[str] | None = "c1a9e4d8f523"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ple_agent_predictions",
        sa.Column("knowledge_query", sa.Text(), nullable=True),
    )
    op.add_column(
        "ple_prediction_retrievals",
        sa.Column("content", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ple_prediction_retrievals", "content")
    op.drop_column("ple_agent_predictions", "knowledge_query")
