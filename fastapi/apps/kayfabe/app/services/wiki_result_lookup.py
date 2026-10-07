"""위키 결과 표에서 승자를 **직접 읽는다. 모델을 부르지 않는다.**

## 왜 모델이 필요 없는가

위키의 결과 절은 산문이 아니라 `{{Pro wrestling results table}}` 템플릿이고, 승자가
파라미터 안에 들어 있다.

    |match5 = Drew McIntyre (c) defeated Sami Zayn by pinfall
    |match3 = Liv Morgan won by last eliminating Tiffany Stratton

2026-10-07 전수 실측: 2026년 대회 12개 · 83경기 **전부** 이 문법을 따랐고, 운영 DB에
이미 확정돼 있던 **63건을 100% 재현**했다(승자 불일치 0 · 짝 못 지음 0).

## 판정은 그대로 `adjudicate`가 한다

이 서비스가 내는 것은 `ResultClaim`과 `Evidence`뿐이다 — 모델이 내던 것과 **같은
모양**이다. 인용이 본문에 있는지, 이름이 카드에 있는지, 모호하지 않은지는 전부
기존 관문이 그대로 본다. 결정론이라고 관문을 건너뛰지 않는다.

`quote`로 `matchN` 원문 줄을 그대로 쓴다. 본문에서 잘라 온 것이라 인용 대조는
반드시 통과하고, 사람이 보고를 읽을 때도 그 줄이 곧 근거다.

## 못 읽으면 조용히 빈손으로 돌아온다

문서 이름을 모르거나(`EVENT_ARTICLE_TITLES`에 없다) · `Results` 절이 없거나(실측:
`wrestlepalooza`가 그렇다) · 짝이 애매하면 그 경기를 **빼고** 돌려준다. 부르는 쪽은
빠진 경기를 모델에게 넘기면 된다 — 이 서비스는 "모른다"를 "없다"로 바꾸지 않는다.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from kayfabe.app.services.wiki_event_titles import article_title_for
from kayfabe.domain.entities.result_verification import (
    Evidence,
    MatchUnderReview,
    ResultClaim,
)
from kayfabe.domain.services.ple_card_parser import parse_results_tables
from kayfabe.domain.services.wiki_result_pairing import MatchCandidate, pair_results
from kayfabe.domain.services.winner_name_match import names_agree
from ontology.app.ports.output.wiki_article_port import WikiArticlePort

logger = logging.getLogger(__name__)

#: 결과가 실리는 절 이름. 위키 WWE 대회 문서는 전수 실측에서 전부 이 이름이었다.
_RESULTS_SECTION = "results"


@dataclass(frozen=True)
class WikiResultFinding:
    """결정론으로 읽은 한 경기. 모델이 내던 것과 같은 모양이다."""

    claim: ResultClaim
    evidence: tuple[Evidence, ...]


class WikiResultLookup:
    """`WikiArticlePort` 하나만 쓴다 — 문서 이름은 사람이 적은 표에서 온다."""

    def __init__(self, articles: WikiArticlePort) -> None:
        self._articles = articles

    async def find(
        self, event_slug: str, matches: Sequence[MatchUnderReview]
    ) -> dict[str, WikiResultFinding]:
        """대회 하나를 **한 번 읽고** 그 안의 경기들을 한꺼번에 짝짓는다.

        경기마다 따로 읽지 않는 이유 둘: 같은 문서를 N번 받는 낭비를 없애고, 한 줄이
        두 경기에 쓰이는 일을 `pair_results`가 막을 수 있게 하기 위해서다.
        """
        if not matches:
            return {}

        title = article_title_for(event_slug)
        if title is None:
            logger.info("[kayfabe.wiki_result] 문서 이름 모름 | event=%s", event_slug)
            return {}

        sections = await self._articles.sections(title)
        if not sections:
            logger.info("[kayfabe.wiki_result] 목차 못 받음 | title=%s", title)
            return {}

        index = next(
            (
                s.index
                for s in sections
                if s.line.strip().casefold() == _RESULTS_SECTION
            ),
            None,
        )
        if index is None:
            logger.info("[kayfabe.wiki_result] Results 절 없음 | title=%s", title)
            return {}

        section = await self._articles.read_section(title, index)
        if section is None or not section.text.strip():
            logger.info("[kayfabe.wiki_result] 본문 못 받음 | title=%s", title)
            return {}

        tables = parse_results_tables(section.text)
        candidates = [
            MatchCandidate(
                key=match.match_key,
                title=match.title,
                participants=tuple(option.name for option in match.options),
            )
            for match in matches
        ]
        paired, unpaired = pair_results(candidates, tables)

        by_key = {match.match_key: match for match in matches}
        evidence = (
            Evidence(
                text=section.text,
                source_title=section.title,
                revision_id=section.revision_id,
            ),
        )

        found: dict[str, WikiResultFinding] = {}
        for result in paired:
            match = by_key[result.candidate.key]
            option_name = _option_name_for(result.winner.names, match)
            if option_name is None:
                # 카드의 어느 이름과도 못 맞췄거나 둘 이상에 걸렸다. 고르지 않는다 —
                # `adjudicate`의 모호성 관문이 할 일을 여기서 미리 가로채지 않는다.
                logger.info(
                    "[kayfabe.wiki_result] 카드 이름과 못 맞춤 | match=%s | 위키=%s",
                    match.match_key,
                    result.winner.names,
                )
                continue
            found[match.match_key] = WikiResultFinding(
                claim=ResultClaim(winner_name=option_name, quote=result.row.raw),
                evidence=evidence,
            )

        logger.info(
            "[kayfabe.wiki_result] %s | 대상 %d · 읽음 %d · 짝 못 지음 %d",
            event_slug,
            len(matches),
            len(found),
            len(unpaired),
        )
        return found


def _option_name_for(
    winner_names: Sequence[str], match: MatchUnderReview
) -> str | None:
    """위키가 읽은 승자에 걸리는 **카드 선택지 이름**. 정확히 하나일 때만 돌려준다.

    카드가 적은 철자를 그대로 주장하는 이유: `adjudicate`가 완전 일치를 먼저 보므로
    여기서 카드 철자를 쓰면 관문이 흔들릴 일이 없고, 화면에 나가는 승자명도 카드와
    같은 철자가 된다.
    """
    hits = [
        option for option in match.options if names_agree(winner_names, option.name)
    ]
    return hits[0].name if len(hits) == 1 else None
