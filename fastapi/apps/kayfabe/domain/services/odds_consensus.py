"""여러 북메이커의 배당을 **합의 확률 하나**로 모은다. 순수 함수다.

배당을 한 곳에서만 받던 때는 그 한 곳이 틀리면 오즈 축 전체가 틀렸다. 여러 곳을
모으면 두 가지가 생긴다 — **중앙값**(한 곳의 실수가 축을 흔들지 못한다)과
**분산**(북메이커들이 서로 다른 말을 하고 있다는 사실 자체가 정보다).

**왜 평균이 아니라 중앙값인가.** 북메이커 하나가 라인을 잘못 걸거나(스티브) 남들과
다른 시각에 관측된 값이 섞이면 평균은 그쪽으로 끌려간다. 중앙값은 그 한 곳을 무시한다.
둘뿐일 때는 두 값의 평균과 같으므로 잃는 것도 없다.

**여기서 배당을 가져오지 않는다.** 이 모듈은 이미 손에 있는 호가를 계산할 뿐이고,
어디서 오는지는 카드가 안다. WWE는 스포츠가 아니라 **엔터테인먼트 스페셜** 시장이라
공개 배당 API(The Odds API·SportsGameOdds 등)가 다루지 않는다 — 호가는 사람이
확인해 카드에 적는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median


@dataclass(frozen=True)
class BookmakerQuote:
    """북메이커 한 곳이 **한 시점에** 건 소수 배당 한 벌.

    `decimals`의 순서는 카드의 선택지 순서와 같다 — 단일전은 `(left, right)`,
    다인전은 참가자 순서.

    **`observed_at`이 값의 일부다.** 배당은 움직인다(실측: MITB 2026의 LA Knight가
    2026-09-26 +350에서 하루 만에 +600으로 밀렸다). 언제 본 값인지를 적지 않으면
    같은 북메이커의 두 관측이 서로 다른 북메이커처럼 세어져 분산을 부풀린다.
    """

    book: str
    decimals: tuple[float, ...]
    observed_at: date | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class OddsConsensus:
    """합의 결과. **재료가 무엇이었는지를 함께 들고 다닌다.**

    숫자만 돌려주면 화면도 감사도 "북메이커 몇 곳이 무엇을 말했는가"를 다시 만들 수
    없다. 이 저장소에서 근거 없는 숫자는 숫자가 아니다.
    """

    #: 오버라운드를 걷어낸 내재 확률. 합은 1이고 순서는 선택지 순서다.
    probabilities: tuple[float, ...]
    #: 합의에 실제로 쓰인 북메이커 이름 (관측 시각 순이 아니라 이름 순).
    books: tuple[str, ...]
    #: **favorite에 대한** 북메이커 간 내재 확률의 최대-최소 차 (0.0~1.0).
    #:
    #: 한 곳뿐이면 0.0이다 — 대조할 상대가 없는 것을 "의견이 일치한다"로 읽지
    #: 않기 위해, 이 값을 쓰는 쪽은 `len(books)`를 함께 본다.
    dispersion: float


def implied_probabilities(decimals: tuple[float, ...]) -> tuple[float, ...] | None:
    """소수 배당 → 오버라운드를 제거한 내재 확률.

    배당의 역수(1/d)는 북메이커 마진 때문에 합이 1을 넘는다. 그대로 쓰면 확신도가
    실제보다 부풀므로 합이 1이 되도록 정규화한다.
    """
    if not decimals or any(value <= 0 for value in decimals):
        return None
    raw = [1.0 / value for value in decimals]
    total = sum(raw)
    if total <= 0:
        return None
    return tuple(value / total for value in raw)


def latest_per_book(
    quotes: tuple[BookmakerQuote, ...],
) -> tuple[BookmakerQuote, ...]:
    """북메이커마다 **가장 최근 관측 하나만** 남긴다. 이름 순으로 돌려준다.

    같은 곳의 과거 호가는 라인 흐름을 말해 주지만 합의의 표본은 아니다 — 세 번
    적힌 북메이커가 세 표를 갖게 되면 그곳이 합의를 지배한다.

    **관측일이 없는 호가는 가장 오래된 것으로 본다.** 날짜를 적은 쪽이 적지 않은
    쪽보다 최신이라고 단정할 근거는 없지만, 반대로 두면 날짜를 적지 않은 값이
    적어 둔 값을 밀어내므로 기록이 쌓일수록 나빠진다.
    """
    newest: dict[str, BookmakerQuote] = {}
    for quote in quotes:
        current = newest.get(quote.book)
        if current is None or _observed_key(quote) >= _observed_key(current):
            newest[quote.book] = quote
    return tuple(newest[book] for book in sorted(newest))


def consensus(
    quotes: tuple[BookmakerQuote, ...], option_count: int
) -> OddsConsensus | None:
    """여러 북메이커의 호가 → 합의 확률. 쓸 호가가 없으면 `None`.

    **선택지 수와 어긋나는 호가는 버린다.** 카드가 바뀌어(참가자 추가) 옛 호가가
    남아 있는 경우가 있고, 길이가 다른 배당을 억지로 맞추면 엉뚱한 선수에게 확률이
    붙는다. 전부 버려지면 `None`이고 오즈 에이전트는 의견 없음을 낸다.
    """
    usable = [
        (quote, probabilities)
        for quote in latest_per_book(quotes)
        if len(quote.decimals) == option_count
        and (probabilities := implied_probabilities(quote.decimals)) is not None
    ]
    if not usable:
        return None

    merged = tuple(
        median([probabilities[index] for _, probabilities in usable])
        for index in range(option_count)
    )
    # 중앙값은 합이 1이라는 보장이 없다 — 선택지마다 따로 골랐기 때문이다.
    # 확률로 쓰려면 다시 정규화한다.
    total = sum(merged)
    if total <= 0:
        return None
    normalized = tuple(value / total for value in merged)

    favorite = max(range(option_count), key=lambda i: normalized[i])
    spread = [probabilities[favorite] for _, probabilities in usable]
    return OddsConsensus(
        probabilities=normalized,
        books=tuple(quote.book for quote, _ in usable),
        dispersion=max(spread) - min(spread),
    )


def confidence_from(consensus_result: OddsConsensus, index: int) -> float:
    """합의 확률 → 오즈 축의 확신도. **의견이 갈릴수록 무지(無知) 쪽으로 당긴다.**

    북메이커들이 서로 다른 값을 말하고 있다면 그 시장은 결과를 모르는 것이다.
    그래서 분산만큼 확률을 **0이 아니라 균등분포(1/n)** 쪽으로 당긴다 — 0으로 당기면
    "상대가 이긴다"는 다른 주장이 되어 버리고, 시장이 말한 적 없는 말이 된다.

    한 곳뿐이면 분산이 0이라 합의 확률이 그대로 나온다. 배당을 한 곳만 적던 때와
    같은 값이므로, 호가를 하나만 아는 경기의 판단은 바뀌지 않는다.
    """
    base = 1.0 / len(consensus_result.probabilities)
    share = consensus_result.probabilities[index]
    damping = max(0.0, 1.0 - consensus_result.dispersion)
    return base + (share - base) * damping


def _observed_key(quote: BookmakerQuote) -> date:
    return quote.observed_at or date.min
