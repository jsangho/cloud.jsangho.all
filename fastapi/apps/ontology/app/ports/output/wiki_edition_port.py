"""문서가 **어느 해 회차를 다루는가**를 묻는 출력 포트 (Phase 3-13 Stage 7).

포트 셋이 한 줄로 이어진다. `WikiTitlePort`가 "이 이름에 해당하는 문서가 있기는
한가"를 묻고, 이 포트는 그다음 — **"있기는 한데, 그게 우리가 말하는 그 회차인가"**
를 묻는다. `RevisionMetadataPort`는 더 뒤에서 "그 본문이 어느 개정본인가"를 묻는다.

**왜 한 걸음이 더 필요한가.** Stage 5의 관문은 문서의 실재만 본다. 그런데 대회
문서는 실재 여부와 무관하게 두 종류다 — 시리즈 전체를 다루는 **총론**과 한 회차를
다루는 **회차 문서**다. 둘 다 200으로 돌아온다.

    Royal Rumble          총론 — 1988년부터의 모든 회차를 요약한다
    Royal Rumble (2026)   회차 — 2026년 1월 31일 그 대회만 다룬다

총론이 근거 자리에 들어가면 **과거 회차의 결과가 적힌 문서**가 검색에 잡힌다.
Phase 3-5가 SummerSlam에서 본 "두 LLM이 언제나 1.0"이 바로 그 모양이었다 — 결과가
적힌 문서를 읽고 맞히는 것은 예측이 아니다. 실재 여부만 보는 관문은 이걸 못 가린다.

## 왜 제목이 아니라 카테고리인가

제목 규칙으로 가리려 했다면 세 갈래에서 전부 깨진다(2026-09-22 실측):

    WrestleMania 42            회차인데 **제목에 연도가 없다**
    WWE Backlash (2026)        없다. 회차 문서는 `Backlash (2026)`다 — 접두사가 빠진다
    Survivor Series (2026)     `Survivor Series: WarGames (2026)`로 넘어간다

카테고리는 이 셋을 모두 통과한다. 위키가 회차 문서에만 **연도가 앞에 붙은
카테고리**를 달기 때문이다(`Category:2026 WWE pay-per-view events`).

## 연도가 "포함"이 아니라 "선두"여야 하는 이유

총론에도 연도가 있다 — 다만 시리즈가 시작된 해다.

    Royal Rumble    Category:Recurring events established in 1988
    WWE Bad Blood   Category:Recurring events established in 1997 · disestablished in 2004

"연도가 들어 있는가"로 보면 지금은 우연히 갈리지만(총론의 창설 연도가 대회 연도와
다르므로), **그해에 창설된 대회에서는 총론이 통과한다.** 선두 연도로 보면 그 구멍이
닫힌다 — 창설 연도는 문장 끝에 오고 회차 카테고리는 연도로 시작한다.

2026-09-22에 회차 10건·총론 7건·엉뚱한 회차 3건으로 전수 검증했고 오판 0건이었다.

**모르면 멈춘다.** 조회가 실패하거나 카테고리 목록이 잘리면 `None`이다. 잘림을
`years=frozenset()`으로 돌려주면 회차 문서가 조용히 거짓 거부되므로, 잘린 응답은
답이 아니라 실패로 본다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class WikiEdition:
    """문서 하나가 어느 해들에 걸려 있는가.

    집합인 이유는 회차 문서가 연도 카테고리를 여럿 달기 때문이다
    (`2026 WWE pay-per-view events` · `2026 in Houston` · …). 하나만 골라 두면
    어느 것을 고를지가 또 하나의 추측이 된다.
    """

    #: 물어본 제목. 응답을 되짚는 열쇠다.
    title: str
    #: 카테고리 **맨 앞**에 놓인 연도들. 없으면 빈 집합이다.
    years: frozenset[int] = frozenset()

    def covers(self, year: int) -> bool:
        """그해 회차를 다루는 문서인가.

        **빈 집합은 "아니다"이지 "모른다"가 아니다.** 모른다는 포트가 `None`으로
        말한다 — 조회 실패와 잘린 응답이 그 자리다.
        """
        return year in self.years


class WikiEditionPort(ABC):
    """제목 여러 개가 각각 어느 해 회차인지 한 번에 묻는다."""

    @abstractmethod
    async def editions(self, titles: Sequence[str]) -> dict[str, WikiEdition] | None:
        """물어본 제목을 열쇠로 하는 표. **조회가 실패하면 `None`이다.**

        부르는 쪽은 **대회 문서만** 넘긴다. 선수 문서에는 회차가 없을뿐더러
        연도 카테고리를 엉뚱한 뜻으로 갖는다(`Rhea Ripley` → `Category:1996 births`).
        목록을 통째로 넘기면 카테고리 응답이 `cllimit`에 걸려 잘린다.
        """
        ...
