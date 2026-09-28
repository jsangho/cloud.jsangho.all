"""승률을 만든 합성 산식의 판본 (v2 전환)

**승률 산식을 바꾸면서 생긴 칸이다.** 지금까지 `_averaged_distribution`은 **의견을 낸
리포트만** 평균했다. 그래서 셋 중 하나만 답하고 그 하나가 확신 1.0이면 **6인 래더에도
승률 100%** 가 나왔다(`mitb26-women`이 실제로 그랬다). 약함을 말하는 칸은 `confidence`
하나뿐이라, 승률만 읽는 화면과 집계는 그것을 확정으로 받아들인다.

`v2`는 기권을 "모르겠다" = **균등분포**로 세고 `agent_count`로 나눈다. 전원이 답하면
`v1`과 값이 같고, 답한 수가 줄수록 균등 쪽으로 끌려간다.

**운영 20건 실측**: 승률이 바뀌는 예측 16건 · 그대로 4건(3/3이 답한 것) ·
**`pick`은 한 건도 바뀌지 않는다** → 채점·적중률·자격 판정은 전부 불변이다.

## 이 칼럼이 없으면 재현이 거짓말을 한다

`ai_lab_replay`는 저장된 승률과 **지금 산식으로 다시 계산한 값**을 오차 없이 견준다.
산식만 바꾸면 그 16건이 전부 `diverged`로 뜨는데, 화면은 그것을 "값이 드리프트했다"로
읽는다 — 실제로는 우리가 함수를 바꾼 것이다. 그래서 판본을 행에 남기고, 재현은 그
값으로 그때의 산식을 골라 부른다. `v1` 코드는 지우지 않고 남겼다.

**`NULL`은 `v1`이라는 뜻이다.** 이 칼럼이 `v2`와 **함께** 생겼으므로, 기록이 없는 행은
전부 `v1`이 만들었다 — 추정이 아니라 시간 순서가 보장하는 사실이다. 그래서 백필하지
않는다(백필해도 같은 값이고, 읽는 쪽이 `NULL`을 `v1`로 해석하면 된다).

폴백 예측(`bookmaker_fallback`)은 합성을 지나지 않으므로 앞으로도 `NULL`이다.

**판정 규칙은 이 칸을 보지 않는다.** 산식은 자격이 아니라 숫자의 출처다.

`ADD COLUMN ... NULL` 하나뿐이라 테이블 재작성이 없고 옛 코드가 도는 중에 올려도
안전하다. 되돌릴 때는 코드만 되돌리고 칼럼은 남겨도 된다 — 옛 코드는 이 칸을 읽지
않는다.

Revision ID: a3f61c2d9e48
Revises: e7d2b5a91c46
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f61c2d9e48"
down_revision: str | Sequence[str] | None = "e7d2b5a91c46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ple_agent_predictions",
        sa.Column("synthesis_version", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ple_agent_predictions", "synthesis_version")
