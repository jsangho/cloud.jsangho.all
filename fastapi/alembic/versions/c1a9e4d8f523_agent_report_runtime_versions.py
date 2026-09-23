"""에이전트 리포트 실행 조건 (Phase 4)

**지금까지 예측은 무엇이 만들었는지를 남기지 않았다.** 어떤 모델이 답했는지, 어떤
지시문이었는지, 어느 판의 에이전트 로직이었는지가 어디에도 없다. 그래서 프롬프트를
고친 뒤 같은 경기의 예측이 달라져도 **왜 달라졌는지 물을 수 없다** — 코퍼스가 바뀐
것인지 우리가 질문을 바꾼 것인지 구분되지 않는다.

세 칸을 `ple_agent_reports`에 둔다. 예측 행이 아니라 리포트 행인 이유는, 모델과
지시문이 **에이전트마다 다르기** 때문이다(무료 등급 한도가 모델 단위라 서사와 루머가
서로 다른 모델을 쓴다). 예측에 한 벌만 두면 둘 중 하나는 거짓이 된다.

셋 다 nullable이고 이유가 서로 다르다:

* `model_version` — LLM을 쓰지 않는 오즈 에이전트는 영구히 NULL이다. 모델을 고정하지
  않고 허브 기본값(`GEMINI_MODEL`)에 맡긴 호출도 NULL이다 — **"모른다"가 아니라
  "우리가 고정하지 않았다"** 는 사실이다.
* `prompt_version` — 모델을 부르지 않은 리포트(자료 없음·배당 없음)는 NULL이다.
  값이 있을 때는 지시문 sha256 앞 16자리이고, **프롬프트 원문은 저장하지 않는다**
  (하네스 §11-6).
* `agent_version` — 기록된 리포트에는 항상 있다. 읽는 쪽은 이 칸으로 "기록이 있는
  행"을 가린다.

**기존 행은 백필하지 않는다.** 그때 어떤 모델·지시문이었는지는 아무도 모르고, 지금
값을 적으면 없던 사실을 만드는 것이 된다. NULL이 정직한 상태다. 판정 규칙
(`ai_lab_evaluation.py`)은 이 칸들을 보지 않으므로 **기존 예측의 자격 판정은 한 건도
움직이지 않는다.**

Revision ID: c1a9e4d8f523
Revises: b3f7d21c905e
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1a9e4d8f523"
down_revision: str | Sequence[str] | None = "b3f7d21c905e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ple_agent_reports",
        sa.Column("model_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "ple_agent_reports",
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ple_agent_reports",
        sa.Column("agent_version", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ple_agent_reports", "agent_version")
    op.drop_column("ple_agent_reports", "prompt_version")
    op.drop_column("ple_agent_reports", "model_version")
