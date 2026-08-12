"""배경 벨트가 주인을 바꾼다 — 인박스가 읽는 계보 (하네스 §3-D65).

§3-D38이 벨트에 주인을 만들었고 §3-D52가 그 밤의 카드를 세웠지만, **인박스만 보면 30년
내내 세계의 벨트는 멈춰 있었다.** RAW 남성부만 30년에 146번 주인이 바뀌는데 뉴스는
`TITLE_WON`·`TITLE_LOST` 둘 다 **내 벨트만** 봤다.

## 계보가 이미 안다

새 규칙이 없다 — `title_scene.reigns_upto()`가 돌려주는 재위 연대기를 읽어 줄로 만들 뿐이다
(§3-D45의 "리포트는 값이 아니라 보는 방식"과 같은 자리). 저장할 것도, 굴릴 것도 없다.

## 세 갈래를 나눈다

재위가 끝난 이유(`ReignEnd`)가 그대로 문장이 된다 — 졌으면 뺏긴 것이고, 비웠으면 결정전이
있었고, 이어받았으면 스테이블이 자리를 지킨 것이다. 그 셋을 한 줄로 뭉치면 §3-D52·D58이
나눠 놓은 것이 화면에서 도로 합쳐진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.services import title_scene
from wwe_game.domain.value_objects.josa import josa_for
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, titles_of
from wwe_game.domain.value_objects.wrestler_identity import Gender


class TitleBeat(StrEnum):
    WON = "won"
    """경기에서 뺏었다."""
    FILLED = "filled"
    """빈 벨트를 결정전으로 채웠다 (§3-D52)."""
    INHERITED = "inherited"
    """스테이블이 이어받았다 (§3-D58)."""


@dataclass(frozen=True)
class TitleNews:
    """배경 벨트에서 일어난 일 하나."""

    week: int
    beat: TitleBeat
    title: str
    holder: str
    headline: str


def chronicle(
    seed: int,
    upto_week: int,
    gender: Gender,
    brand: Brand,
    *,
    exclude: str = "",
    skip: frozenset[Title] = frozenset(),
) -> tuple[TitleNews, ...]:
    """0주부터 그 주차까지, 이 브랜드 벨트들의 주인이 바뀐 기록.

    `exclude`는 플레이어의 링네임이다 — 계보는 플레이어가 없는 세계를 그린다(§3-D38).

    `skip`은 **내가 지금 감고 있는 벨트**다. 배경 계보에서는 그 벨트도 남이 들고 있고
    (§3-D38의 "내가 아니었다면 누구였을까"), 그걸 그대로 흘리면 같은 인박스에 내 대관과
    남의 대관이 함께 뜬다. 지금 내 것인 벨트만 빼면 그 모순이 사라진다 — 지나간 시절의
    계보는 남겨 둔다: 그때는 실제로 남의 벨트였다.
    """
    news: list[TitleNews] = []
    for title in titles_of(brand, gender):
        if title in skip:
            continue
        display = TITLES[title].display_name
        reigns = title_scene.reigns_upto(seed, upto_week, title, exclude=exclude)
        for previous, reign in zip(reigns, reigns[1:], strict=False):
            holder = title_scene.holder_label(reign.holder, seed)
            news.append(
                TitleNews(
                    week=reign.start,
                    beat=_beat_of(previous, reign),
                    title=display,
                    holder=holder,
                    headline=_headline(previous, reign, display, holder, seed),
                )
            )
    return tuple(sorted(news, key=lambda item: item.week))


def _beat_of(previous: title_scene.Reign, reign: title_scene.Reign) -> TitleBeat:
    """이 재위가 **어떻게 시작했는지**.

    `Reign.vacated`는 그 재위가 *어떻게 끝났는지*라, 시작을 알려면 **앞 재위**를 봐야
    한다. `inherited`만 시작을 말한다 — 한 자료형이 시작과 끝을 함께 들고 있어서
    한 번 헷갈렸다.
    """
    if reign.inherited:
        return TitleBeat.INHERITED
    return TitleBeat.FILLED if previous.vacated else TitleBeat.WON


def _headline(
    previous: title_scene.Reign,
    reign: title_scene.Reign,
    title: str,
    holder: str,
    seed: int,
) -> str:
    """그 줄의 문장. **앞 재위가 끝난 이유가 곧 이 줄의 문장이다.**"""
    subject = f"{holder}{josa_for(holder, '가')}"
    stake = f"{title}{josa_for(title, '을')}"
    if reign.inherited:
        return f"{subject} {stake} 이어받았다."
    if previous.vacated:
        return f"{subject} 빈 {stake} 가져갔다."
    loser = title_scene.holder_label(previous.holder, seed)
    return f"{subject} {loser}에게서 {stake} 뺏었다."
