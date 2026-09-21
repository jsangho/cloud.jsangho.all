"""조립한 문서 이름이 **실제로 무엇을 가리키는지** 묻는 출력 포트 (Phase 3-13 Stage 5).

`RevisionMetadataPort`가 "이 주소의 본문이 어느 개정본인가"를 묻는다면, 이 포트는
그보다 한 걸음 앞 — **"이 이름에 해당하는 문서가 있기는 한가"** 를 묻는다.

**왜 필요한가.** 수집기는 경기 카드의 선수 이름으로 위키 주소를 조립한다
(`ingest_event_knowledge.py`). 그 조립은 추측이고, 빗나가면 404로 걸러진다고 믿어
왔는데 **실측이 그 믿음을 깼다.** 빗나간 이름은 세 갈래로 흩어진다.

    Rhea Ripley   → Rhea Ripley          맞는 문서
    Royce Keys    → Powerhouse Hobbs     리다이렉트 — 본문은 맞고 주소만 어긋난다
    Penta         → Penta                **동음이의** — 본문이 "Penta may refer to:"다
    Clash in Italy→ (없음)                404

가운데 둘이 조용한 사고다. 동음이의 문서는 200으로 돌아와 청크가 되고, 검색에
잡히면 아무 내용도 없는 목록이 근거 자리를 차지한다(운영 코퍼스에 `Paige`·`Penta`
두 문서 4청크가 실제로 그렇게 들어 있었다). 리다이렉트는 본문이 맞아서 더 늦게
드러난다 — 나중에 누가 정규 이름으로 같은 문서를 넣으면 `content_hash` 유니크에
막혀 **저장 0건이 조용히 성공으로 보고된다.**

**모르면 멈춘다.** 조회가 실패하면 `None`이고, 부르는 쪽은 추측한 주소로 수집을
이어가는 대신 그 자리에서 멈춘다. 여기서 `None`은 `RevisionMetadataPort`의 `None`과
성격이 다르다 — 저쪽은 "계보만 비고 본문은 산다"지만, 이쪽은 **애초에 어디를
받아 올지 모른다**는 뜻이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class WikiTitle:
    """이름 하나가 가리키는 실제 문서.

    세 상태를 구분한다 — 쓸 수 있는 문서 · 동음이의 · 없는 문서. 동음이의를
    "없는 문서"로 뭉뚱그리지 않는 이유는 보고가 달라지기 때문이다. 없는 문서는
    이름이 틀린 것이고, 동음이의는 **이름이 모호한 것**이라 카드 쪽 표기를 고쳐야
    한다(`Penta` → `Penta El Zero M`).
    """

    #: 부르는 쪽이 물어본 이름. 응답을 되짚는 열쇠다.
    requested: str
    #: 위키가 말하는 정규 제목. 문서가 없으면 `None`.
    canonical: str | None
    #: 본문이 아니라 **같은 이름의 문서 목록**인가.
    is_disambiguation: bool = False

    @property
    def is_usable(self) -> bool:
        """근거로 쓸 수 있는 본문 문서인가."""
        return self.canonical is not None and not self.is_disambiguation

    @property
    def is_renamed(self) -> bool:
        """물어본 이름과 정규 제목이 다른가 — 리다이렉트거나 표기가 다른 것이다."""
        if self.canonical is None:
            return False
        return _normalized(self.canonical) != _normalized(self.requested)


def _normalized(title: str) -> str:
    """제목 비교용 정규화 — 밑줄과 앞뒤 공백만 흡수한다.

    **대소문자는 흡수하지 않는다.** `IYO SKY` → `Iyo Sky`는 위키에서 실제로 다른
    표기이고, 그 차이를 흘리면 주소를 고쳐야 한다는 사실이 보고에서 사라진다.
    """
    return title.replace("_", " ").strip()


class WikiTitlePort(ABC):
    """이름 여러 개가 가리키는 문서를 한 번에 묻는다."""

    @abstractmethod
    async def resolve(self, titles: Sequence[str]) -> dict[str, WikiTitle] | None:
        """물어본 이름을 열쇠로 하는 표. **조회가 실패하면 `None`이다.**

        하나씩이 아니라 목록으로 받는 이유는 이 조회가 수집 전체에 대해 한 번이기
        때문이다. 문서마다 따로 물으면 요청 수가 문서 수만큼 늘어 계보 조회와 같은
        429를 부른다.
        """
        ...
