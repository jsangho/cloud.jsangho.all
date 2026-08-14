"""기사 — 뉴스 한 줄을 신문 한 꼭지로 (하네스 §3-D87).

§3-D31이 만든 것은 **사건 한 줄**이었다. 헤드라인과 군중 반응 한 마디. 되돌아볼 만한
사건만 골라 세운다는 뜻은 맞았는데, 서른 해를 훑어도 읽을 거리가 두 줄뿐이었다.

여기서 하는 일은 그 한 줄을 **매체 · 제목 · 본문 · 댓글**로 펼치는 것이다.

## 저장하지 않는다 · 판정에 닿지 않는다

`title_scene`(§3-D38) · 별점(§3-D56)과 **같은 자리**다. 기사는 값이 아니라 **보는
방식**이라, 그 사건의 재료(주차 · 종류 · 군중 반응 · 시드)로 매번 되짚는다. 저장하면
세이브가 커지기만 하고, 손댄 세이브와 규칙이 갈린다.

**굴림 채널을 완전히 나눠 뒀다**(`seeded_roll.NEWS`). 댓글을 한 줄 더하는 것만으로
그 주차의 경기 결과가 밀리면 안 된다.

## 사실을 지어내지 않는다

본문은 **이미 일어난 일만** 다시 말한다 — 언제(연차·월), 무엇(`headline`), 그리고
그 자리의 소리(`crowd_line`). 여기서 새 사건을 만들면 로그와 뉴스가 서로 다른 세계를
말하게 되고, 그때 플레이어는 무엇을 믿어야 할지 모른다(§3-D31이 나레이터와 우선순위를
맞춘 것과 같은 이유).

그래서 제목도 **`headline`을 그대로 쓰되 매체의 말투만 입힌다.** 새 문장을 만들어
붙이면 그 문장이 거짓이 될 수 있다.

## 댓글은 반응이지 판정이 아니다

`CrowdMood`가 이미 그 밤의 소리를 정해 뒀다(§3-D31). 댓글은 **그 축을 다시 읽는
것**이지 새 축이 아니다 — 새 판정을 더하면 "댓글이 좋으면 인기가 오르는" 고리가
생기고, 그건 §13-Q13이 막아 온 종류의 지름길이다.

**한 명은 늘 반대편에 선다.** 다섯 줄이 전부 같은 말이면 그건 댓글창이 아니라 합창이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.constants.ple_calendar import date_of
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.news_feed import CrowdMood, NewsItem, NewsKind
from wwe_game.domain.services.seeded_roll import SeededRoll

COMMENT_COUNT = 5
"""기사 한 꼭지에 붙는 댓글 수 (2026-08-14 사용자 요청).

셋이면 댓글창으로 안 읽히고, 열이면 기사보다 길어진다.
"""

OUTLETS: tuple[str, ...] = (
    "링사이드 리포트",
    "스쿼드 데일리",
    "케이블 스포츠",
    "매트 위클리",
    "프로레슬링 저널",
    "골든벨트 뉴스",
)
"""가상의 매체들. **실존 매체를 쓰지 않는다** — §3-D13(전개는 가상이다)의 연장이고,
실제 언론사 이름을 넣으면 그 매체가 하지 않은 말을 한 것이 된다."""

_PREFIX: dict[NewsKind, str] = {
    NewsKind.TITLE_WON: "[속보]",
    NewsKind.TITLE_LOST: "[속보]",
    NewsKind.INJURY: "[현장]",
    NewsKind.CALL_UP: "[단독]",
    NewsKind.CROWN: "[속보]",
    NewsKind.CLASSIC: "[리뷰]",
    NewsKind.TURN: "[해설]",
    NewsKind.CURSED: "[현장]",
    NewsKind.RETIRE: "[부고]",
}
"""종류마다 앞머리. **없으면 안 붙인다** — 배경 소식까지 전부 [속보]면 속보가 아니다."""

_CONTEXT: dict[NewsKind, tuple[str, ...]] = {
    NewsKind.TITLE_WON: (
        "벨트가 손에 들어온 밤은 대개 그 뒤가 더 어렵다. 방어전 일정이 곧 잡힌다.",
        "타이틀 하나가 커리어의 방향을 바꾼 사례는 이 바닥에 흔하다.",
        "챔피언의 자리는 지키는 쪽이 늘 더 무겁다는 말이 다시 나왔다.",
    ),
    NewsKind.TITLE_LOST: (
        "벨트를 내려놓은 선수의 다음 행보에 관심이 쏠린다.",
        "재도전 기회가 언제 올지는 아직 정해지지 않았다.",
        "한 시대가 닫혔다는 평가와 아직 이르다는 평가가 함께 나온다.",
    ),
    NewsKind.INJURY: (
        "복귀 시점은 미정이다. 부상 부위와 정도에 따라 달라질 수 있다.",
        "일정에 잡혀 있던 경기들은 조정이 불가피해 보인다.",
        "몸 상태를 두고 무리한 일정이 원인이라는 지적도 나온다.",
    ),
    NewsKind.CALL_UP: (
        "메인 로스터의 주간 방송은 무대의 크기가 다르다.",
        "육성 브랜드에서의 평가가 그대로 이어질지가 관건이다.",
        "콜업 이후 첫 몇 달이 자리를 정한다는 것이 이 바닥의 통설이다.",
    ),
    NewsKind.CROWN: (
        "세 밤을 이어 이긴 선수에게 주어지는 자리다.",
        "왕관은 벨트가 아니지만, 다음 기회를 앞당기는 이력이 된다.",
    ),
    NewsKind.CLASSIC: (
        "올해의 경기 후보로 벌써 거론된다.",
        "경기 뒤 두 선수는 링 중앙에서 서로를 마주 봤다.",
    ),
    NewsKind.TURN: (
        "돌아선 이유를 두고 해석이 엇갈린다.",
        "이 결정이 앞으로의 대진에 어떤 영향을 줄지 지켜볼 일이다.",
    ),
    NewsKind.CURSED: (
        "설명하기 어려운 밤이었다는 반응이 많았다.",
        "중계진도 결과를 두고 한동안 말을 아꼈다.",
    ),
    NewsKind.BIG_WIN: (
        "큰 무대에서의 승리는 다음 자리를 앞당긴다.",
        "이 결과로 상위권 구도가 다시 짜일 전망이다.",
    ),
}
"""종류마다 붙는 맥락 한 문장. **새 사실이 아니라 해석이다** — 무슨 일이 있었는지는
`headline`이 이미 말했고, 여기 있는 것은 그 일이 놓인 자리다."""

_GENERIC_CONTEXT: tuple[str, ...] = (
    "이 소식은 주간 방송을 통해 확인됐다.",
    "관련해 추가로 확인된 내용은 없다.",
    "현장에 있던 취재진의 전언이다.",
)
"""표에 없는 종류가 쓰는 문장. 배경 소식은 대개 여기로 온다."""

_COMMENTS: dict[CrowdMood, tuple[str, ...]] = {
    CrowdMood.ROAR: (
        "이 순간을 몇 년을 기다렸다",
        "생중계로 봤는데 소름 돋았음",
        "진짜 이 사람은 큰 경기에서 다르다",
        "오늘은 인정할 수밖에 없다",
        "표 값 아깝지 않은 밤이었다",
        "다음 방송 벌써 기다려진다",
        "현장에 있었는데 소리가 미쳤음",
        "이런 게 보고 싶어서 본다",
    ),
    CrowdMood.JEER: (
        "인정하기 싫은데 잘하긴 함",
        "야유받는 게 목적이면 성공했다",
        "볼 때마다 화가 나는데 채널을 못 돌리겠음",
        "이 사람 나오면 음소거한다",
        "짜증나는데 그게 실력이라는 게 더 짜증남",
        "관중 반응이 다 말해준다",
        "이번엔 좀 심했다고 본다",
        "미워하는데 눈은 못 뗀다",
    ),
    CrowdMood.SPLIT: (
        "이걸 좋아해야 하는지 모르겠다",
        "댓글 반응이 반반인 게 웃기다",
        "판단 보류. 다음 방송 보고 정하겠음",
        "옆자리는 환호하고 나는 야유했다",
        "애매한데 그래서 더 궁금하다",
        "호불호 갈릴 만하다",
        "아직은 잘 모르겠음",
    ),
    CrowdMood.HUSH: (
        "이건 진짜 마음이 안 좋다",
        "회복만 잘 했으면 좋겠다",
        "보다가 조용해졌다",
        "무리한 일정 문제 아니냐",
        "몸이 우선이다. 천천히 돌아오길",
        "이런 소식은 볼 때마다 익숙해지지가 않는다",
        "다치지 말라고 몇 번을 말했는데",
    ),
    CrowdMood.CHANT: (
        "떼창 소리 들었냐 진짜",
        "이름 부르는 소리가 방송에 다 잡혔다",
        "이 정도면 그냥 이 바닥 얼굴이지",
        "구호가 안 끊기더라",
        "현장 갔던 사람들 부럽다",
        "이게 스타의 크기다",
        "오늘 주인공은 확실했다",
    ),
}
"""반응마다 댓글 후보. 30년이면 기사가 70꼭지 남짓이고 꼭지마다 다섯 줄이라,
같은 줄이 겹치지 않게 여덟 언저리씩 둔다(§11-6의 다양성 기준과 같은 결)."""

_DISSENT: tuple[str, ...] = (
    "다들 너무 띄우는 거 아님?",
    "솔직히 과대평가라고 본다",
    "저는 반대 의견입니다",
    "이게 그렇게 대단한 일인가",
    "냉정하게 보면 아직 멀었다",
    "여기 댓글 분위기가 이상한데",
)
"""**한 명은 늘 반대편에 선다.** 다섯 줄이 전부 같은 말이면 댓글창이 아니라 합창이다."""

_NICKS: tuple[str, ...] = (
    "링사이드석",
    "케이페이브",
    "목요일밤팬",
    "벨트수집가",
    "top로프",
    "중계석옆자리",
    "20년째시청",
    "카운트투",
    "하드캠",
    "관중석3열",
    "테마곡중독",
    "슈퍼플렉스",
)
"""댓글 닉네임. **실존 인물을 쓰지 않는다** — 명부의 선수 이름도 여기 오지 않는다."""


@dataclass(frozen=True)
class NewsComment:
    """댓글 한 줄과 그에 달린 표.

    **표는 사실이 아니라 반응이다.** 판정에 쓰이지 않으므로 §11-14가 막는 내부 수치가
    아니다 — 이 숫자로는 아무것도 계산되지 않는다.
    """

    author: str
    text: str
    up: int
    down: int


@dataclass(frozen=True)
class NewsArticle:
    """뉴스 한 줄을 펼친 기사 한 꼭지."""

    outlet: str
    title: str
    body: str
    comments: tuple[NewsComment, ...]


def _roll(item: NewsItem, seed: int, salt: int = 0) -> SeededRoll:
    """그 기사 전용 굴림. **주차와 종류가 함께 들어간다** — 같은 주차에 두 꼭지가
    서면(내 일 + 배경 소식) 둘의 댓글이 똑같아지면 안 된다."""
    return SeededRoll(seed + salt + len(item.kind.value), item.week, seeded_roll.NEWS)


def outlet_for(item: NewsItem, seed: int) -> str:
    return OUTLETS[(seed + item.week + len(item.kind.value)) % len(OUTLETS)]


def title_for(item: NewsItem) -> str:
    """신문 제목. **`headline`을 그대로 쓰고 말투만 입힌다.**

    새 문장을 지어 붙이지 않는 이유: 그 문장이 거짓이 될 수 있다. 여기서 더하는 것은
    앞머리와 마침표를 떼는 것뿐이다.
    """
    core = item.headline.rstrip().rstrip(".")
    prefix = _PREFIX.get(item.kind)
    return f"{prefix} {core}" if prefix else core


def body_for(item: NewsItem) -> str:
    """기사 본문 — **이미 일어난 일만** 다시 말한다.

    언제(연차·월) · 무엇(`headline`) · 그 자리의 소리(`crowd_line`) · 그 일이 놓인
    자리(`_CONTEXT`). 새 사건은 하나도 더하지 않는다.
    """
    _, month, week_of_month = date_of(item.week)
    when = f"{item.year}년차 {month}월 {week_of_month}주차"
    context = _CONTEXT.get(item.kind, _GENERIC_CONTEXT)
    # **리드가 먼저다.** 시점을 앞에 두면 "…주차, 장상호, …"로 쉼표가 겹쳐
    # 기사가 아니라 메모처럼 읽힌다 — 실제 기사도 무슨 일인지를 먼저 말한다.
    return " ".join(
        (
            item.headline.rstrip(),
            f"{when}의 일이다.",
            f"{item.crowd_line}.",
            context[item.week % len(context)],
        )
    )


def comments_for(item: NewsItem, seed: int) -> tuple[NewsComment, ...]:
    """그 기사의 댓글 다섯 (§3-D87).

    **`CrowdMood`를 다시 읽을 뿐이다** — 새 판정이 아니다. 넷은 그 밤의 소리를 따르고
    하나는 반대편에 선다.

    표 수는 **분위기를 따르는 쪽이 더 받는다.** 반대 의견이 늘 미움받는다는 뜻은
    아니고, 그 자리에 모인 사람들이 대체로 같은 것을 보러 왔다는 뜻이다.
    """
    pool = _COMMENTS[item.mood]
    roll = _roll(item, seed)
    picked: list[NewsComment] = []
    remaining = list(pool)
    dissent_at = roll.between(1, COMMENT_COUNT - 1)
    for slot in range(COMMENT_COUNT):
        if slot == dissent_at and _DISSENT:
            text = _DISSENT[(item.week + slot) % len(_DISSENT)]
            agrees = False
        elif remaining:
            text = roll.pick(tuple(remaining))
            remaining.remove(text)
            agrees = True
        else:
            break
        up = roll.between(3, 240) if agrees else roll.between(0, 40)
        down = roll.between(0, 30) if agrees else roll.between(5, 90)
        picked.append(
            NewsComment(
                author=_NICKS[(seed + item.week + slot * 7) % len(_NICKS)],
                text=text,
                up=up,
                down=down,
            )
        )
    return tuple(picked)


def build(item: NewsItem, seed: int) -> NewsArticle:
    """뉴스 한 줄 → 기사 한 꼭지. **되짚기다** — 같은 세이브면 같은 기사다(§3-D4)."""
    return NewsArticle(
        outlet=outlet_for(item, seed),
        title=title_for(item),
        body=body_for(item),
        comments=comments_for(item, seed),
    )
