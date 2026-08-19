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
from wwe_game.domain.services import seeded_roll, staff_scene
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

_ON_TOPIC: dict[NewsKind, tuple[str, ...]] = {
    NewsKind.TITLE_WON: (
        "벨트 바뀐 거 실화냐 방금 알림 보고 들어옴",
        "방어전 상대 벌써 예상 나오는데 좀 이르지 않나",
        "이 대관은 진짜 오래 기다렸다 축하한다",
        "솔직히 타이틀 매치 자체가 올해 본 것 중 제일 나았음",
        "벨트 들고 서 있는 그림 하나로 다음 주 방송 다 산 듯",
        "재위 얼마나 갈지 내기 걸자",
    ),
    NewsKind.TITLE_LOST: (
        "재도전 조항 있나요? 있으면 다음 대회에서 바로 붙을 텐데",
        "이렇게 끝날 재위는 아니었는데 아쉽다",
        "솔직히 마지막 몇 주 방어전이 너무 빡셌음",
        "벨트 없어도 이 선수는 이 선수지",
        "다음 챔피언 스토리는 어떻게 짤 생각인지 모르겠다",
    ),
    NewsKind.INJURY: (
        "복귀 언제쯤 될까요 시즌 통째로 날아가는 건 아니겠지",
        "잡혀 있던 대진 다 틀어지는 거 아님?",
        "이 스케줄로 안 다치는 게 이상하다 진짜",
        "부위가 어디인지도 안 나왔네 기다려 봐야지",
        "몸이 우선이다 천천히 돌아와도 된다",
    ),
    NewsKind.CALL_UP: (
        "드디어 올라오네 밑에서 볼 때부터 될 줄 알았다",
        "콜업하고 첫 몇 달이 진짜 중요한데 대진 잘 받았으면",
        "육성에서 하던 거 그대로 하면 금방 자리 잡을 듯",
        "메인 로스터는 관중 규모부터 다른데 적응이 관건",
        "이번 콜업 조는 유독 기대된다",
    ),
    NewsKind.BIG_WIN: (
        "이 무대에서 이긴 건 의미가 다르지",
        "다음 대진 어떻게 짜일지 궁금하다",
        "솔직히 오늘은 인정",
        "큰 경기에서 강한 타입인 듯",
    ),
    NewsKind.CROWN: (
        "세 밤 연속으로 이긴 거면 체력이 진짜 대단한 거임",
        "왕관은 벨트는 아닌데 다음 기회 앞당기는 건 확실하지",
        "토너먼트 대진운도 좀 있었다고 본다",
    ),
    NewsKind.CLASSIC: (
        "이건 다시보기 각이다 진심",
        "올해의 경기 후보 하나 나왔네",
        "끝나고 둘이 마주 보는 그림에서 소름 돋음",
        "니어폴에서 진짜 일어설 뻔했다",
    ),
    NewsKind.TURN: (
        "이거 예고된 수순이었나? 나만 몰랐나",
        "돌아선 이유가 아직 설명이 안 됐는데",
        "이 캐릭터가 더 어울리는 것 같기도 하다",
        "몇 주 지켜봐야 판단 되겠다",
    ),
    NewsKind.CURSED: (
        "이길 경기였는데 왜 저러지 진짜",
        "중계도 말 못 잇더라 나도 그랬음",
        "이런 밤이 오래 기억에 남는 법이지",
    ),
    NewsKind.TEAM: (
        "이 조합 의외인데 나쁘지 않을 듯",
        "태그 구도 슬슬 정리되려나",
        "팀 이름부터 좀 어떻게 안 되나",
        "둘이 스타일이 안 맞을 것 같은데 두고 보자",
    ),
}
"""**사건을 아는 댓글** (2026-08-14 사용자 지적: *"댓글들이 너무 대충 쓰여 있다"*).

분위기(`CrowdMood`)만 보고 뽑으면 대관에도 부상에도 같은 말이 달린다 — 그러면
댓글창이 아니라 배경 소음이다. 종류를 아는 줄을 절반 넘게 섞는다.

**여전히 새 판정이 아니다.** 사건의 종류는 §3-D31이 이미 정했고, 여기서는 그 종류를
읽어 문장을 고를 뿐이다.
"""

_DISSENT: tuple[str, ...] = (
    "다들 너무 띄우는 거 아님? 냉정하게 보면 아직 멀었다",
    "이게 그렇게 대단한 일인가 싶은데 나만 그런가",
    "여기 댓글 분위기 좀 이상한데 팬만 모인 듯",
    "과대평가라고 본다 다음 몇 주 보면 알겠지",
    "솔직히 이 정도로 기사까지 날 일인가",
    "반응이 과한 것 같아서 한마디 남긴다",
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
    byline: str = ""
    """**취재한 사람** (§3-D93 규칙 5). 백스테이지 인터뷰어가 곧 기자다 — 그가 물어본
    말이 기사가 되므로, 누가 물었는지가 남아야 한다."""
    quote: str = ""
    """그 사건에 대해 **링 밖의 누군가가 한 말** (§3-D93).

    말하는 사람은 사건이 정한다 — 회사의 발표는 집행부가, 대진과 이적은 GM이, 판정
    시비는 심판이, 그리고 매니저를 둔 선수의 일은 매니저가 말한다.

    **새 사실을 만들지 않는다.** 인용은 이미 일어난 일에 대한 태도이지 사건이 아니다.
    """


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


_ANGLE: dict[NewsKind, tuple[str, ...]] = {
    NewsKind.TITLE_WON: (
        "챔피언이 바뀐 밤은 다음 주 방송의 첫 그림부터 달라진다. 벨트를 든 사람이 링 한가운데 서고, 나머지 대진이 그 주위로 다시 짜인다.",
        "대관 자체보다 그 뒤가 어렵다는 말이 이 바닥에는 오래 있었다. 도전자 줄이 생기는 순간부터 방어전 일정이 몸을 갉는다.",
        "링 위에서 벨트를 들어 올리는 장면은 짧았지만, 그 한 장면을 위해 쌓아 온 몇 달이 있었다는 것을 현장은 알고 있었다.",
    ),
    NewsKind.TITLE_LOST: (
        "벨트를 내려놓은 선수가 다음에 어디로 갈지는 아직 정해지지 않았다. 재도전 조항이 있는지도 확인되지 않았다.",
        "한 시대가 닫혔다는 평가와 아직 이르다는 평가가 함께 나왔다. 재위 기간을 두고도 해석이 갈린다.",
        "링을 내려오는 뒷모습이 오래 잡혔다. 중계는 그 장면에 말을 얹지 않았다.",
    ),
    NewsKind.INJURY: (
        "복귀 시점은 미정이다. 부위와 정도에 따라 몇 주가 될 수도, 몇 달이 될 수도 있다.",
        "잡혀 있던 일정은 조정이 불가피해 보인다. 대진이 걸려 있던 상대들도 함께 자리를 옮기게 된다.",
        "무리한 일정이 원인이라는 지적이 다시 나왔다. 같은 자리에서 같은 이야기가 반복된다는 것이 이 종목의 오래된 문제다.",
    ),
    NewsKind.CALL_UP: (
        "메인 로스터의 주간 방송은 관중 규모부터 다르다. 육성 브랜드에서의 평가가 그대로 이어질지가 관건이다.",
        "콜업 이후 첫 몇 달이 자리를 정한다는 것이 이 바닥의 통설이다. 초반 대진이 곧 그 선수의 위치가 된다.",
        "올라오는 것과 남는 것은 다른 일이다. 명단에 이름을 올린 뒤가 진짜 시작이라는 말이 괜히 있는 것이 아니다.",
    ),
    NewsKind.BIG_WIN: (
        "큰 무대에서의 승리는 다음 자리를 앞당긴다. 상위권 구도가 이 결과로 다시 짜일 전망이다.",
        "같은 승리라도 어느 밤에 거뒀는지가 무게를 가른다. 이 밤은 그 무게가 있는 쪽이었다.",
    ),
    NewsKind.CROWN: (
        "세 밤을 이어 이긴 선수에게 주어지는 자리다. 왕관은 벨트가 아니지만 다음 기회를 앞당기는 이력이 된다.",
        "토너먼트는 한 번의 승리로 끝나지 않는다. 몸이 남아 있는 쪽이 마지막에 선다.",
    ),
    NewsKind.CLASSIC: (
        "경기 뒤 두 선수는 링 중앙에서 서로를 마주 봤다. 관중은 한동안 자리를 뜨지 않았다.",
        "올해의 경기 후보로 벌써 거론된다. 이런 밤은 한 해에 몇 번 나오지 않는다.",
    ),
    NewsKind.TURN: (
        "돌아선 이유를 두고 해석이 엇갈린다. 예고된 수순이었다는 쪽과 즉흥이었다는 쪽이 나뉜다.",
        "이 결정이 앞으로의 대진에 어떤 영향을 줄지는 몇 주 지나야 보인다.",
    ),
    NewsKind.CURSED: (
        "설명하기 어려운 밤이었다는 반응이 많았다. 중계진도 결과를 두고 한동안 말을 아꼈다.",
        "이길 경기였다는 데에는 이견이 없었다. 그래서 더 오래 회자될 밤이 됐다.",
    ),
    NewsKind.TEAM: (
        "팀이 만들어지는 자리는 대개 조용하다. 그 조합이 무엇을 할 수 있는지는 몇 주 뒤에야 드러난다.",
        "태그 구도는 한 팀이 생기면 나머지가 함께 움직인다. 이 조합도 그 흐름 위에 있다.",
    ),
}
"""종류마다 붙는 **기사다운 한 단락**. 새 사실이 아니라 그 일이 놓인 자리다.

`_CONTEXT`(짧은 한 줄)를 대신한다 — 사용자 요청이 *"내용을 더 길고 자세하게"*였고,
한 줄로는 제목을 되풀이하는 것 이상이 되지 않았다.
"""


def body_for(item: NewsItem) -> str:
    """기사 본문 — **이미 일어난 일만** 다시 말한다.

    무엇(`headline`) · 언제(연차·월) · 그 자리의 소리(`crowd_line`) · 그 일이 놓인
    자리(`_ANGLE`). 새 사건은 하나도 더하지 않는다.

    **리드가 먼저다.** 시점을 앞에 두면 *"…주차, 장상호, …"*로 쉼표가 겹쳐 기사가
    아니라 메모처럼 읽힌다 — 실제 기사도 무슨 일인지를 먼저 말한다.
    """
    _, month, week_of_month = date_of(item.week)
    when = f"{item.year}년차 {month}월 {week_of_month}주차"
    angle = _ANGLE.get(item.kind, _GENERIC_CONTEXT)
    return "\n\n".join(
        (
            f"{item.headline.rstrip()} {when}의 일이다.",
            f"현장의 반응은 분명했다. {item.crowd_line}.",
            angle[item.week % len(angle)],
        )
    )


def comments_for(item: NewsItem, seed: int) -> tuple[NewsComment, ...]:
    """그 기사의 댓글 다섯 (§3-D87).

    **`CrowdMood`를 다시 읽을 뿐이다** — 새 판정이 아니다. 넷은 그 밤의 소리를 따르고
    하나는 반대편에 선다.

    표 수는 **분위기를 따르는 쪽이 더 받는다.** 반대 의견이 늘 미움받는다는 뜻은
    아니고, 그 자리에 모인 사람들이 대체로 같은 것을 보러 왔다는 뜻이다.
    """
    roll = _roll(item, seed)
    # **사건을 아는 줄이 먼저다.** 분위기만 보고 뽑으면 대관에도 부상에도 같은 말이
    # 달린다 — 종류별 풀을 앞에 두고, 모자란 만큼만 분위기 풀에서 채운다.
    on_topic = list(_ON_TOPIC.get(item.kind, ()))
    ambient = list(_COMMENTS[item.mood])
    picked: list[NewsComment] = []
    dissent_at = roll.between(1, COMMENT_COUNT - 1)
    for slot in range(COMMENT_COUNT):
        if slot == dissent_at and _DISSENT:
            text = _DISSENT[(item.week + slot) % len(_DISSENT)]
            agrees = False
        elif on_topic:
            text = roll.pick(tuple(on_topic))
            on_topic.remove(text)
            agrees = True
        elif ambient:
            text = roll.pick(tuple(ambient))
            ambient.remove(text)
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


_GM_KINDS: frozenset[NewsKind] = frozenset(
    {NewsKind.CALL_UP, NewsKind.CALL_UP_SCENE, NewsKind.MOVED, NewsKind.SCENE}
)
"""GM이 말하는 사건들 — **대진과 자리를 정하는 사람**이기 때문이다 (§3-D93 규칙 3)."""

_REFEREE_KINDS: frozenset[NewsKind] = frozenset({NewsKind.CURSED})
"""심판이 말하는 사건 (§3-D93 규칙 6). 저주로 진 밤은 **판정이 도마에 오르는 밤**이다."""

_MANAGER_KINDS: frozenset[NewsKind] = frozenset(
    {NewsKind.TITLE_WON, NewsKind.TITLE_LOST, NewsKind.BIG_WIN, NewsKind.TURN}
)
"""매니저가 대신 말하는 사건 (§3-D93 규칙 7) — **매니저를 둔 선수는 말을 덜 한다.**"""

_LINES: dict[str, tuple[str, ...]] = {
    "executive": (
        "회사가 다음 분기에 무엇을 걸었는지는 곧 알게 될 겁니다.",
        "우리가 보는 것은 한 주가 아니라 한 해입니다.",
    ),
    "gm": (
        "다음 주 대진은 이 밤이 정해 줬습니다.",
        "제 일은 이 이야기가 어디로 갈지 자리를 잡아 주는 겁니다.",
    ),
    "referee": (
        "제가 본 대로 셌습니다. 그 이상도 이하도 아닙니다.",
        "규칙 안에서 끝난 경기입니다.",
    ),
    "manager": (
        "내 선수는 대답할 필요가 없습니다. 링에서 이미 답했으니까.",
        "이 사람 옆에 서 있는 이유가 오늘 밤에 있습니다.",
    ),
}


def quote_for(item: NewsItem, seed: int, *, brand: str = "", manager: str = "") -> str:
    """그 사건에 붙는 한 마디. **없으면 빈 문자열이다** — 억지로 말시키지 않는다."""
    if item.kind is NewsKind.ANNOUNCEMENT:
        # 발표는 헤드라인이 이미 말한 사람을 담고 있다 — 여기서는 태도만 더한다.
        speaker, voice = "", "executive"
    elif item.kind in _REFEREE_KINDS:
        speaker, voice = staff_scene.referee_of(brand, item.week, seed), "referee"
    elif manager and item.kind in _MANAGER_KINDS:
        speaker, voice = manager, "manager"
    elif item.kind in _GM_KINDS:
        speaker, voice = staff_scene.gm_of(brand), "gm"
    else:
        return ""
    lines = _LINES[voice]
    line = lines[item.week % len(lines)]
    return f"{speaker} — “{line}”" if speaker else f"“{line}”"


def build(
    item: NewsItem, seed: int, *, brand: str = "", manager: str = ""
) -> NewsArticle:
    """뉴스 한 줄 → 기사 한 꼭지. **되짚기다** — 같은 세이브면 같은 기사다(§3-D4).

    `brand`·`manager`가 오면 링 밖의 사람들이 함께 선다 (§3-D93) — 안 와도 기사는
    그대로 서므로 옛 호출부가 깨지지 않는다.
    """
    return NewsArticle(
        outlet=outlet_for(item, seed),
        title=title_for(item),
        body=body_for(item),
        comments=comments_for(item, seed),
        byline=staff_scene.interviewer_of(brand, item.week, seed),
        quote=quote_for(item, seed, brand=brand, manager=manager),
    )
