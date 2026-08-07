"""kayfabe 로스터 CSV → `domain/constants/roster.py` 생성기 (하네스 §3-D13).

**런타임 import가 아니라 오프라인 생성이다.** `lint-imports` 계약이 막는 것은 스포크끼리의
import이고(§2-D3), 빌드 시점에 CSV 파일을 읽어 소스를 찍어 내는 것은 그 계약과 무관하다.
손으로 베끼는 것보다 이쪽이 맞다 — §3-D13이 감수하기로 한 "이중 관리" 비용이 재생성
한 번으로 줄어든다.

```
uv run python apps/wwe_game/scripts/generate_roster.py        # 미리보기
uv run python apps/wwe_game/scripts/generate_roster.py --write # 파일 갱신
```

## CSV가 주지 않는 두 가지

`gender`와 `tier` 컬럼이 원본에 없다. 각각 이렇게 채운다.

- **성별** — CSV는 섹션마다 남자를 알파벳순으로 늘어놓은 뒤 여자를 다시 알파벳순으로
  잇는다. 그 경계를 `FIRST_WOMAN`에 **이름으로 박아 둔다.** 되감김을 자동 탐지하지 않는
  이유: 남자 구간 안에도 순서가 어긋난 이름이 몇 개 있어("Austin Theory → Tyler Bate")
  탐지가 조용히 틀린다. 사람이 읽고 고칠 수 있는 상수가 낫고, 섹션 인원수로 교차 검증된다.
- **등급** — NXT는 육성 브랜드이므로 통째로 `PROSPECT`, 메인 로스터는 `MIDCARD`,
  그중 `MAIN_EVENTERS`에 적힌 이름만 `MAIN_EVENT`로 올린다.

## 넣지 않는 것

- **권역** — 이 게임에서 아무 규칙도 읽지 않던 죽은 필드였다(2026-08-07 사용자 지적).
  선수는 어차피 다 미국 무대에 선다. 무대 권역은 서술이 따로 정한다(§3-D14-1).
- **Evolve 브랜드** — kayfabe 카탈로그와 같은 기준으로 제외한다. 유망주 풀은 NXT 57명만으로
  충분하고, 두 목록의 기준이 갈리면 어느 쪽이 맞는지 매번 확인해야 한다.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = APP_DIR.parents[0] / "kayfabe" / "_docs" / "wwe_active_roster_cleaned.csv"
OUT_PATH = APP_DIR / "domain" / "constants" / "roster.py"

TODAY = datetime.date(2026, 8, 7)
WEEKS_PER_YEAR = 52
CAREER_WEEKS = 30 * WEEKS_PER_YEAR

NPC_RETIRE_AGE = 48
"""실존 선수가 링을 떠나는 나이.

플레이어의 만기(50세, §3-D16)보다 두 살 이르다 — 플레이어는 인기도로 나이를 상쇄하는
주인공이고, 배경 선수는 평범한 커브를 탄다. 45로 낮추면 시작 5년 만에 정상급이 반쯤
비고, 55로 올리면 30년 뒤에도 오늘의 얼굴이 남아 사용자가 지적한 문제가 그대로다.
"""

MIN_ACTIVE_WEEKS = 3 * WEEKS_PER_YEAR
"""이미 은퇴 나이를 넘긴 노장도 이만큼은 뛴다.

R-트루스(54) · 레이 미스테리오(51)처럼 오늘 현역인데 나이만 넘긴 선수가 있다. 0주차에
증발시키면 시작하자마자 명부가 흔들리고, 무엇보다 **오늘 뛰고 있다는 사실과 어긋난다.**
"""

DEFAULT_AGE = 32
"""생년월일이 비어 있는 12명에 쓰는 나이. 명부 전체의 중앙값이다."""

FICTIONAL_CAREER_YEARS = 24
"""가상 선수의 활동 기간. 22세 데뷔 → 46세 은퇴에 해당한다."""

LATE_DEBUT_SECTIONS: dict[str, tuple[int, int]] = {"Evolve": (1, 4)}
"""나중에 데뷔하는 섹션 → (가장 이른 해, 가장 늦은 해).

Evolve는 NXT 아래 육성 단계다. 오늘 명부에 넣으면 유망주가 과밀해지고, 무엇보다
**이들이 메인 무대에 오르는 건 몇 년 뒤**라는 사실과 어긋난다 (2026-08-07 사용자 요청).
"""

FIRST_WOMAN: dict[str, str] = {
    "RAW": "AJ Lee",
    "SmackDown": "Alexa Bliss",
    "Free Agent": "Paige",
    "NXT": "Adriana Rizzo",
}
"""섹션마다 **여자 구간이 시작되는 이름**. 이 이름부터 끝까지가 여성부다."""

EXPLICIT_WOMEN: dict[str, frozenset[str]] = {
    "Evolve": frozenset(
        {"Zena Sterling", "Kai Kavari", "Aria Bennett", "Chantel Monroe"}
    ),
}
"""알파벳 되감김이 없는 섹션은 **여성부를 이름으로 적는다.**

Evolve는 정렬돼 있지 않아 경계를 잡을 구조 신호가 없다. 억지로 위치로 자르면 조용히
틀리므로, 짧은 섹션은 손으로 적는 쪽이 정직하다.
"""

PROSPECT_SECTIONS = frozenset({"NXT"})
"""육성 브랜드. 통째로 유망주 등급이 된다."""

MAIN_EVENTERS: frozenset[str] = frozenset(
    {
        # 남성부
        "Roman Reigns",
        "Cody Rhodes",
        "CM Punk",
        "Seth Rollins",
        "Drew McIntyre",
        "Gunther",
        "Randy Orton",
        "Bron Breakker",
        "Jey Uso",
        "LA Knight",
        "Damian Priest",
        "Kevin Owens",
        "Solo Sikoa",
        "Brock Lesnar",
        "Jacob Fatu",
        "Finn Bálor",
        "Sami Zayn",
        "Logan Paul",
        "Rey Mysterio",
        "Bronson Reed",
        # 여성부
        "Rhea Ripley",
        "Bianca Belair",
        "Becky Lynch",
        "Charlotte Flair",
        "Liv Morgan",
        "Iyo Sky",
        "Bayley",
        "Tiffany Stratton",
        "Jade Cargill",
        "Asuka",
        "Nia Jax",
        "Naomi",
        "Alexa Bliss",
        "Giulia",
        "Stepahnie Vaquer",
    }
)
"""정상급으로 올릴 이름. **여기 없는 메인 로스터는 전부 미드카드다.**

인기도 60 이상인 플레이어가 만나는 상대라 풀이 너무 얇으면 같은 얼굴만 나온다(§3-D13).
"""

KOREAN_NAMES: dict[str, str] = {
    # ── 남성부 ────────────────────────────────────────────────
    "Brock Lesnar": "브록 레스너",
    "Bron Breakker": "브론 브레이커",
    "Bronson Reed": "브론슨 리드",
    "CM Punk": "CM 펑크",
    "Cody Rhodes": "코디 로즈",
    "Damian Priest": "데미언 프리스트",
    "Drew McIntyre": "드류 매킨타이어",
    "Finn Bálor": "핀 밸러",
    "Gunther": "군터",
    "Jacob Fatu": "제이콥 파투",
    "Jey Uso": "제이 우소",
    "Kevin Owens": "케빈 오웬스",
    "LA Knight": "LA 나이트",
    "Logan Paul": "로건 폴",
    "Randy Orton": "랜디 오턴",
    "Rey Mysterio": "레이 미스테리오",
    "Roman Reigns": "로만 레인즈",
    "Sami Zayn": "사미 제인",
    "Seth Rollins": "세스 롤린스",
    "Solo Sikoa": "솔로 시코아",
    "Akira Tozawa": "토자와 아키라",
    "Angel": "에인절",
    "Angelo Dawkins": "안젤로 도킨스",
    "Austin Theory": "오스틴 시어리",
    "Axiom": "액시엄",
    "Baron Corbin": "배런 코빈",
    "Berto": "베르토",
    "Big Cass": "빅 캐스",
    "Brutus Creed": "브루터스 크리드",
    "Carmelo Hayes": "카멜로 헤이스",
    "Chad Gable": "채드 게이블",
    "Cruz Del Toro": "크루즈 델 토로",
    "Danhausen": "댄하우젠",
    "Dominik Mysterio": "도미닉 미스테리오",
    "Dragon Lee": "드래곤 리",
    "Elton Prince": "엘튼 프린스",
    "Erik": "에릭",
    "Ethan Page": "이선 페이지",
    "Grayson Waller": "그레이슨 월러",
    "Ilja Dragunov": "일리야 드라구노프",
    "Ivar": "아이바",
    "JD McDonagh": "JD 맥도너",
    "Je'Von Evans": "제본 에번스",
    "Jimmy Uso": "지미 우소",
    "Joaquin Wilde": "호아킨 와일드",
    "Joe Hendry": "조 헨드리",
    "Johnny Gargano": "조니 가르가노",
    "Julius creed": "줄리어스 크리드",
    "Kit Wilson": "키트 윌슨",
    "Ludwig Kaiser": "루트비히 카이저",
    "Matt Cardona": "맷 카도나",
    "Montez Ford": "몬테즈 포드",
    "Nathan Frazer": "네이선 프레이저",
    "Oba Femi": "오바 페미",
    "Omos": "오모스",
    "Otis": "오티스",
    "Penta": "펜타",
    "Pete Dunne": "피트 던",
    "R-Truth": "R-트루스",
    "Rey Fénix": "레이 페닉스",
    "Ricky Saints": "리키 세인츠",
    "Royce Keys": "로이스 키스",
    "Rusev": "루세프",
    "Shinsuke Nakamura": "나카무라 신스케",
    "Talla Tonga": "탈라 통가",
    "Tama Tonga": "타마 통가",
    "The Miz": "더 미즈",
    "Trick Williams": "트릭 윌리엄스",
    "Tyler Bate": "타일러 베이트",
    "Brad Baylor": "브래드 베일러",
    "Bronco Nima": "브롱코 니마",
    "Brooks Jensen": "브룩스 젠슨",
    'Channing "Stacks" Lorenzo': "채닝 로렌조",
    "Charlie Dempsey": "찰리 뎀프시",
    "Cutler James": "커틀러 제임스",
    "Dion Lennox": "디온 레녹스",
    "Dorian Van Dux": "도리안 반 덕스",
    "EK Prosper": "EK 프로스퍼",
    "Elio LeFleur": "엘리오 르플뢰르",
    "Hank Walker": "행크 워커",
    "Jackson Drake": "잭슨 드레이크",
    "Jasper Troy": "재스퍼 트로이",
    "Josh Briggs": "조시 브릭스",
    "Kale Dixon": "케일 딕슨",
    "Kam Hendrix": "캠 헨드릭스",
    "Keanu Carver": "키아누 카버",
    "Lexis King": "렉시스 킹",
    "Lince Dorado": "린세 도라도",
    "Lucien Price": "루시엔 프라이스",
    "Mason Rook": "메이슨 룩",
    "Myles Borne": "마일스 본",
    "NARAKU": "나라쿠",
    "Niko Vance": "니코 밴스",
    "Noam Dar": "노엄 다르",
    "Osiris Griffin": "오시리스 그리핀",
    "Ricky Smokes": "리키 스모크스",
    "Romeo Moreno": "로미오 모레노",
    "Saquon Shugars": "세이콴 슈거스",
    "Sean Legacy": "션 레거시",
    "Shawn Spears": "숀 스피어스",
    "Shiloh Hill": "샤일로 힐",
    "Tank Ledger": "탱크 레저",
    "Tavion Heights": "테이비언 하이츠",
    "Tony D'Angelo": "토니 단젤로",
    "Tristan Angels": "트리스탄 에인절스",
    "Uriah Connors": "유라이어 코너스",
    # ── 여성부 ────────────────────────────────────────────────
    "Alexa Bliss": "알렉사 블리스",
    "Asuka": "아스카",
    "Bayley": "베일리",
    "Becky Lynch": "베키 린치",
    "Bianca Belair": "비앙카 벨레어",
    "Charlotte Flair": "샬럿 플레어",
    "Giulia": "줄리아",
    "Iyo Sky": "이요 스카이",
    "Jade Cargill": "제이드 카길",
    "Liv Morgan": "리브 모건",
    "Naomi": "나오미",
    "Nia Jax": "니아 잭스",
    "Rhea Ripley": "레아 리플리",
    "Stepahnie Vaquer": "스테파니 바케르",
    "Tiffany Stratton": "티파니 스트래튼",
    "AJ Lee": "AJ 리",
    "B-Fab": "B-팹",
    "Blake Monroe": "블레이크 먼로",
    "Brie Bella": "브리 벨라",
    "Candice LeRae": "캔디스 르레이",
    "Chelsea Green": "첼시 그린",
    "Fallon Henley": "팰런 헨리",
    "Ivy Nile": "아이비 나일",
    "Jacy Jayne": "제이시 제인",
    "Jordynne Grace": "조딘 그레이스",
    "Kiana James": "키아나 제임스",
    "Lainey Reid": "레이니 리드",
    "Lash Legend": "래시 레전드",
    "Lyra Valkyria": "라이라 발키리아",
    "Maxxine Dupri": "맥신 듀프리",
    "Michin": "미친",
    "Nattie": "내티",
    "Nikki Bella": "니키 벨라",
    "Paige": "페이지",
    "Piper Niven": "파이퍼 니븐",
    "Raquel Rodriguez": "라켈 로드리게스",
    "Roxanne Perez": "록산 페레즈",
    "Sol Ruca": "솔 루카",
    "Adriana Rizzo": "아드리아나 리조",
    "Arianna Grace": "아리아나 그레이스",
    "Izzi Dame": "이지 데임",
    "Jaida Parker": "자이다 파커",
    "Kali Armstrong": "칼리 암스트롱",
    "Karmen Petrovic": "카르멘 페트로비치",
    "Kelani Jordan": "켈라니 조던",
    "Kendal Grey": "켄달 그레이",
    "Layla Diggs": "레일라 딕스",
    "Lizzy Rain": "리지 레인",
    "Lola Vice": "롤라 바이스",
    "Myka Lockwood": "마이카 록우드",
    "Nikkita Lyons": "니키타 라이온스",
    "Reina Volcán": "레이나 볼칸",
    "Skylar Raye": "스카일라 레이",
    "Tatum Paxley": "테이텀 팩슬리",
    "Thea Hail": "시아 헤일",
    "Wendy Choo": "웬디 추",
    "Wren Sinclair": "렌 싱클레어",
    "Zaria": "자리아",
    # ── Evolve (나중 데뷔) ─────────────────────────────────────
    "Aaron Rourke": "에런 루크",
    "Cappuccino Jones": "카푸치노 존스",
    "Starboy Charlie": "스타보이 찰리",
    "Elijah Holyfield": "일라이자 홀리필드",
    "It's GAL": "잇츠 갈",
    "Braxton Cole": "브랙스턴 콜",
    "Harlem Lewis": "할렘 루이스",
    "PJ Vasa": "PJ 바사",
    "Jax Preslay": "잭스 프레슬리",
    "Zena Sterling": "지나 스털링",
    "Kai Kavari": "카이 카바리",
    "Aria Bennett": "아리아 베넷",
    "Chantel Monroe": "샹텔 먼로",
}
"""영문 링네임 → 한국어 표기.

**서술이 한국어라 이름도 한국어여야 한다.** 영문을 그대로 두면 "Brock Lesnar가 난입해"가
되고, 조사 판정도 어긋난다 — `_ends_with_batchim`은 한글 종성을 보는데 영문은 마지막
글자로 어림할 뿐이라 "레스너가"(맞음) 대신 "Lesnar이"(틀림)가 된다.

표에 없는 이름은 **영문 그대로 두고 경고한다.** 조용히 섞이면 화면에서야 발견된다.
"""


HEADER = '''"""라이벌·챔피언으로 쓸 선수 명부 — **시간에 따라 바뀐다** (하네스 §3-D13).

**이 파일은 생성물이다.** 손으로 고치지 말고 `scripts/generate_roster.py`를 다시 돌린다.

## 30년이면 로스터가 통째로 갈린다 (2026-08-07 사용자 지적)

커리어는 30년이고 실존 선수의 현재 나이 중앙값은 32세다. 은퇴 나이를 48세로 두면
**30년 뒤 남아 있는 실존 선수가 0명**이다. 명부를 오늘의 스냅샷으로 고정하면 로만
레인즈가 일흔에 현역인 세계가 된다.

그래서 명부에 **시간 축**을 넣었다.

| 필드 | 뜻 |
|---|---|
| `debut_week` | 이 주차부터 등장한다. 실존 선수는 0, Evolve는 1~4년 뒤, 가상 신인은 흩뿌려진다 |
| `retire_week` | 이 주차부터 사라진다. 실존 선수는 **생년월일에서 계산**하고, 가상 선수는 데뷔 + 경력 길이 |
| `start_tier` | 등장 시점의 등급. 여기서 **경력 연차만큼 올라간다** (`tier_at`) |

가상 선수가 필요한 이유가 여기 있다 — 실존 선수만으로는 커리어 후반의 대립 상대가
바닥난다. 이름은 조합으로 만들되 실존 이름과 겹치지 않게 걸렀다.

**kayfabe의 로스터를 import할 수 없다** — 스포크끼리는 못 붙는다(§2-D3). 원본은
`_docs/wwe_active_roster_cleaned.csv`이고, 베끼는 일은 생성기가 한다.

실존 인물이므로 **서술이 사실 주장처럼 읽히지 않아야** 한다 — 게임 내 가상 전개임을
생성 화면과 로그 하단에 표시한다(§3-D13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from wwe_game.domain.constants.career_clock import CAREER_WEEKS, WEEKS_PER_YEAR
from wwe_game.domain.value_objects.wrestler_identity import Gender


class RivalTier(IntEnum):
    """대략적 등급. 대립 상대를 고를 때 플레이어 인기도와 맞춘다."""

    PROSPECT = 1
    MIDCARD = 2
    MAIN_EVENT = 3


@dataclass(frozen=True)
class RosterMember:
    name: str
    gender: Gender
    start_tier: RivalTier
    debut_week: int = 0
    retire_week: int | None = None
    """None이면 커리어 끝까지 현역이다."""
    experience_years: int = 0
    """등장 시점에 **이미 쌓아 온 경력**. 승급은 이걸 포함해 센다.

    오늘의 미드카더는 대개 10년 차다. 게임 안에서 흐른 시간만 세면 그가 정상급이 되는 데
    15년이 더 걸리고 그때는 은퇴 나이다 — 실측에서 10년차 정상급 풀이 5명까지 말랐다.
    """

    def is_active_at(self, week: int) -> bool:
        if week < self.debut_week:
            return False
        return self.retire_week is None or week < self.retire_week


PROMOTION_WEEKS: tuple[int, int] = (6 * WEEKS_PER_YEAR, 14 * WEEKS_PER_YEAR)
"""(유망주 → 미드카드, 미드카드 → 정상급) 승급에 걸리는 **누적 경력**.

**등급을 고정하면 두 번 틀린다.** 오늘의 NXT 유망주가 서른 해 뒤에도 유망주로 남고,
은퇴로 빠져나간 정상급 자리를 아무도 채우지 않는다. 데뷔 6년 · 15년을 지나면 올라간다 —
실제 승급 서사와 크게 다르지 않고, 규칙 하나로 두 구멍을 함께 막는다.
"""


MIN_PROMOTION_WEEKS = 4 * WEEKS_PER_YEAR
"""경력이 아무리 길어도 등장 후 이만큼은 지나야 올라간다. 0주차 명부를 지키는 바닥이다."""


_M, _F = Gender.MALE, Gender.FEMALE
_P, _MC, _ME = RivalTier.PROSPECT, RivalTier.MIDCARD, RivalTier.MAIN_EVENT

ROSTER: tuple[RosterMember, ...] = (
'''

FOOTER = ''')


def active_at(week: int) -> tuple[RosterMember, ...]:
    """그 주차에 현역인 선수들."""
    return tuple(m for m in ROSTER if m.is_active_at(week))


def tier_at(member: RosterMember, week: int) -> RivalTier:
    """경력 연차만큼 올라간 등급. **내려가지는 않는다.**"""
    elapsed = week - member.debut_week
    tier = member.start_tier
    if tier is RivalTier.PROSPECT and elapsed >= _wait_for(member, 0):
        tier = RivalTier.MIDCARD
    if tier is RivalTier.MIDCARD and elapsed >= _wait_for(member, 1):
        tier = RivalTier.MAIN_EVENT
    return tier


def _wait_for(member: RosterMember, step: int) -> int:
    """승급까지 **등장 시점부터** 기다리는 주차.

    쌓아 온 경력은 기다림을 줄이지만 **0으로 만들지는 않는다.** 그대로 빼면 14년 차
    미드카더가 0주차에 곧바로 정상급이 되어 오늘의 분류를 덮어쓴다 — 실측에서 0년차
    남자 정상급이 20명에서 47명으로 부풀었다.
    """
    earned = member.experience_years * WEEKS_PER_YEAR
    return max(MIN_PROMOTION_WEEKS, PROMOTION_WEEKS[step] - earned)


def pool_for(gender: Gender, tier: RivalTier, week: int = 0) -> tuple[str, ...]:
    """그 주차에 현역이면서 디비전·등급이 맞는 이름들 (§3-D11)."""
    return tuple(
        m.name
        for m in ROSTER
        if m.gender is gender and m.is_active_at(week) and tier_at(m, week) is tier
    )


def tier_for_popularity(popularity: int) -> RivalTier:
    """인기도에 맞는 상대 등급. **급이 맞아야 대립이 성립한다.**

    무명이 월드 챔피언과 대립하는 것도, 정상급이 유망주와 몇 달을 싸우는 것도
    이야기가 되지 않는다.
    """
    if popularity >= 60:
        return RivalTier.MAIN_EVENT
    if popularity >= 30:
        return RivalTier.MIDCARD
    return RivalTier.PROSPECT


MIN_POOL = 6
"""어느 (디비전 × 등급) 칸도 **커리어 어느 시점에서도** 이보다 얇으면 안 된다.

주차를 넣기 전에는 임포트 시점에 한 번만 셌다. 그때는 명부가 안 변했으니 그걸로 충분했다 —
지금은 20년 차에 정상급이 비는 일이 생길 수 있어 전 구간을 훑는다.
"""

for _g in Gender:  # pragma: no cover - 임포트 시 구조 검증
    for _t in RivalTier:
        for _w in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
            if len(pool_for(_g, _t, _w)) < MIN_POOL:
                raise RuntimeError(
                    f"{_g}/{_t} 라이벌 풀이 {_w // WEEKS_PER_YEAR}년차에 "
                    f"너무 얇습니다: {pool_for(_g, _t, _w)}"
                )
'''


def read_sections(path: Path) -> dict[str, list[tuple[str, int]]]:
    """섹션 이름 → [(선수 이름, 나이)]. 등장 순서를 그대로 지킨다."""
    rows = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    sections: dict[str, list[tuple[str, int]]] = {}
    current: str | None = None
    for row in rows:
        cell = (row.get("name") or "").strip()
        if not cell:
            continue
        if cell.startswith("#"):
            current = cell[1:]
            sections[current] = []
        elif current is not None:
            sections[current].append((cell, _age_of(row)))
    return sections


def _age_of(row: dict[str, str | None]) -> int:
    """생년월일에서 오늘 나이. 비어 있으면 명부 중앙값을 쓴다."""
    raw = (row.get("birth_date") or "").strip()
    try:
        born = datetime.date.fromisoformat(raw)
    except ValueError:
        return DEFAULT_AGE
    return (TODAY - born).days // 365


DEBUT_AGE = 22
"""프로 데뷔 나이의 어림값. 나이에서 경력을 되짚는 데만 쓴다."""


def experience_of(age: int) -> int:
    return max(0, age - DEBUT_AGE)


def retire_week_for(age: int) -> int:
    """그 나이의 선수가 링을 떠나는 주차. 노장에게도 최소 활동 기간을 준다."""
    return max(MIN_ACTIVE_WEEKS, (NPC_RETIRE_AGE - age) * WEEKS_PER_YEAR)


def split_by_gender(
    section: str, entries: list[tuple[str, int]]
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """(남성부, 여성부). 경계 이름이 목록에 없으면 CSV가 바뀐 것이므로 멈춘다."""
    explicit = EXPLICIT_WOMEN.get(section)
    if explicit is not None:
        unknown = explicit - {n for n, _ in entries}
        if unknown:
            raise SystemExit(f"{section}: 명단에 없는 이름 {sorted(unknown)}")
        return (
            [e for e in entries if e[0] not in explicit],
            [e for e in entries if e[0] in explicit],
        )
    marker = FIRST_WOMAN.get(section)
    if marker is None:
        raise SystemExit(f"{section}: 여성부 시작 이름이 정의돼 있지 않습니다")
    names = [n for n, _ in entries]
    if marker not in names:
        raise SystemExit(
            f"{section}: 경계 이름 {marker!r}이 CSV에 없습니다 — "
            "로스터가 갱신됐다면 FIRST_WOMAN을 함께 고치세요"
        )
    cut = names.index(marker)
    return entries[:cut], entries[cut:]


FICTIONAL_MALE_FIRST = (
    "제이든",
    "메이슨",
    "카터",
    "라이언",
    "콜",
    "데릭",
    "트로이",
    "잭슨",
    "브레이든",
    "오스틴",
    "카일",
    "마커스",
    "데본",
    "자비어",
    "실라스",
    "개럿",
    "놀란",
    "웨이드",
    "알렉",
    "브랜든",
    "디온",
    "케이든",
    "맥스",
    "네이트",
    "루커스",
    "타이슨",
    "코너",
    "제러드",
    "이선",
    "브라이스",
)
FICTIONAL_FEMALE_FIRST = (
    "리아",
    "애슐리",
    "브리아나",
    "케일라",
    "시에나",
    "노바",
    "엠버",
    "하퍼",
    "델라니",
    "이든",
    "스칼렛",
    "마야",
    "조이",
    "리네아",
    "아이비",
    "세라",
    "조던",
    "페이",
    "로렌",
    "테사",
    "미셸",
    "카일라",
    "브룩",
    "이자벨",
)
FICTIONAL_LAST = (
    "크로스",
    "하트",
    "스톤",
    "블레이즈",
    "스틸",
    "케이지",
    "나이트",
    "울프",
    "프로스트",
    "헌터",
    "스톰",
    "라이커",
    "세이지",
    "밴스",
    "리버스",
    "머서",
    "브릭스",
    "파울러",
    "폭스",
    "레인",
    "퀸",
    "셰이드",
    "벨",
    "프라이스",
    "헤이즈",
    "서머스",
    "윈터스",
    "스파크",
    "바이퍼",
    "리드",
)
"""가상 선수의 이름 조각. 앞뒤를 곱해 900가지가 나온다 — 필요한 수의 몇 배다.

**손으로 쓰지 않는 이유는 분량이다.** 30년을 채우려면 100명이 넘게 필요하고, 그만큼을
직접 쓰면 뒤로 갈수록 성의가 떨어진다. 실존 이름과 겹치는 조합은 걸러 낸다.
"""

DEBUTS_PER_YEAR = {"_M": 3, "_F": 2}
"""해마다 데뷔시킬 가상 선수 수.

승급이 6년·15년이므로 한 기수는 유망주로 6년, 미드카드로 9년을 산다. 남자 3명이면
유망주 18명·미드카드 27명이 늘 차 있다는 계산이고, 실측도 그 근처다.
"""

FICTIONAL_MIDCARD_EVERY = 4
"""이만큼마다 한 명은 **미드카드로 데뷔**시킨다 — 다른 단체에서 온 즉시 전력이다.

전원을 유망주로 넣으면 실존 미드카드가 빠져나가는 10~15년 구간이 얇아진다.
"""


def fictional_members(
    taken: set[str],
) -> list[tuple[str, str, str, int, int | None, int]]:
    """가상 선수 명부. 해마다 정해진 수를 데뷔시킨다."""
    members: list[tuple[str, str, str, int, int | None, int]] = []
    for gender, firsts in (
        ("_M", FICTIONAL_MALE_FIRST),
        ("_F", FICTIONAL_FEMALE_FIRST),
    ):
        pairs = [f"{first} {last}" for first in firsts for last in FICTIONAL_LAST]
        # 중첩 루프 순서대로 쓰면 "… 크로스"가 연달아 데뷔한다. 이름값 해시로 섞되
        # blake2b라 프로세스가 바뀌어도 순서가 같다 (도메인의 시드 규약과 같은 이유).
        combos = sorted(
            pairs, key=lambda n: hashlib.blake2b(n.encode(), digest_size=8).digest()
        )
        made = 0
        for name in combos:
            if made >= DEBUTS_PER_YEAR[gender] * 30:
                break
            if name in taken:
                continue
            taken.add(name)
            year = 1 + made // DEBUTS_PER_YEAR[gender]
            debut = year * WEEKS_PER_YEAR
            tier = "_MC" if made % FICTIONAL_MIDCARD_EVERY == 0 else "_P"
            retire = debut + FICTIONAL_CAREER_YEARS * WEEKS_PER_YEAR
            experience = 6 if tier == "_MC" else 0
            members.append((name, gender, tier, debut, retire, experience))
            made += 1
    return members


def build_presets() -> list[tuple[str, str, str, str]]:
    """(한국어 이름, 성별, 플레이스타일, 국가코드). 실존 선수만 대상이다."""
    presets: list[tuple[str, str, str, str]] = []
    for section, entries in read_sections(CSV_PATH).items():
        men, women = split_by_gender(section, entries)
        raw = {
            row["name"].strip(): row
            for row in csv.DictReader(
                io.StringIO(CSV_PATH.read_text(encoding="utf-8-sig"))
            )
            if (row.get("name") or "").strip()
        }
        for gender, group in (("MALE", men), ("FEMALE", women)):
            for name, _ in group:
                row = raw.get(name, {})
                presets.append(
                    (
                        KOREAN_NAMES.get(name, name),
                        gender,
                        preset_style(
                            name,
                            (row.get("finisher") or ""),
                            (row.get("weight") or ""),
                            gender,
                        ),
                        preset_country(
                            (row.get("birth_place") or ""),
                            (row.get("billed_from") or ""),
                        ),
                    )
                )
    return presets


def build() -> list[tuple[str, str, str, int, int | None, int]]:
    """(이름, 성별, 시작 등급, 데뷔 주차, 은퇴 주차). 디비전 → 등급 순으로 정렬한다."""
    members: list[tuple[str, str, str, int, int | None, int]] = []
    for section, entries in read_sections(CSV_PATH).items():
        men, women = split_by_gender(section, entries)
        window = LATE_DEBUT_SECTIONS.get(section)
        for gender_alias, group in (("_M", men), ("_F", women)):
            for index, (name, age) in enumerate(group):
                if section in PROSPECT_SECTIONS or window is not None:
                    tier = "_P"
                elif name in MAIN_EVENTERS:
                    tier = "_ME"
                else:
                    tier = "_MC"
                if window is None:
                    debut = 0
                else:
                    low, high = window
                    span = high - low + 1
                    debut = (low + index % span) * WEEKS_PER_YEAR
                retire = debut + retire_week_for(age)
                members.append(
                    (name, gender_alias, tier, debut, retire, experience_of(age))
                )

    missing = [n for n, _, _, _, _, _ in members if n not in KOREAN_NAMES]
    if missing:
        print(
            f"경고: 한국어 표기가 없는 이름 {len(missing)}개 — {missing}",
            file=sys.stderr,
        )
    members = [(KOREAN_NAMES.get(n, n), g, t, d, r, e) for n, g, t, d, r, e in members]
    members += fictional_members({n for n, _, _, _, _, _ in members})

    order = {"_ME": 0, "_MC": 1, "_P": 2}
    members.sort(key=lambda m: (m[1] != "_M", m[3], order[m[2]], m[0]))
    return members


def render(members: list[tuple[str, str, str, int, int | None, int]]) -> str:
    lines: list[str] = []
    seen: tuple[str, int] | None = None
    for name, gender, tier, debut, retire, experience in members:
        mark = (gender, debut)
        if mark != seen:
            seen = mark
            division = "남성부" if gender == "_M" else "여성부"
            when = "0주차 명부" if debut == 0 else f"{debut // WEEKS_PER_YEAR}년차 데뷔"
            title = f"{division} · {when}"
            lines.append(f"    # ── {title} " + "─" * max(1, 40 - len(title)))
        escaped = name.replace('"', '\\"')
        retire_arg = "None" if retire is None else str(retire)
        lines.append(
            f'    RosterMember("{escaped}", {gender}, {tier}, '
            f"{debut}, {retire_arg}, {experience}),"
        )
    return HEADER + "\n".join(lines) + "\n" + FOOTER


# ── 캐릭터 생성 프리셋 (§3-D10-1) ─────────────────────────────

PRESET_OUT_PATH = APP_DIR / "domain" / "constants" / "character_presets.py"

COUNTRY_BY_PLACE: dict[str, str] = {
    "U.S.": "US",
    "US": "US",
    "United States": "US",
    "Arizona": "US",
    "California": "US",
    "Colorado": "US",
    "Florida": "US",
    "Georgia": "US",
    "Illinois": "US",
    "North Carolina": "US",
    "Canada": "CA",
    "England": "GB",
    "Scotland": "GB",
    "Ireland": "IE",
    "West Germany": "DE",
    "France": "FR",
    "Spain": "ES",
    "Russia": "RU",
    "Japan": "JP",
    "Mexico": "MX",
    "Chile": "CL",
    "Puerto Rico": "PR",
    "Dominican Republic": "DO",
    "Australia": "AU",
    "Tonga": "TO",
}
"""출생지 마지막 토큰 → 게임의 국가 코드. **미국 주 이름은 그대로 미국이다.**

여기 없는 나라(오스트리아·나이지리아·이스라엘 등)는 **`Country.OTHER`로 뭉친다.**
게임의 권역은 다섯 개뿐이라(§3-D14) 아프리카·중동을 담을 자리가 없고, 가까운 나라로
밀어 넣으면 데이터를 조작하는 셈이다.
"""

STYLE_BY_FINISHER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "TECHNICIAN",
        (
            "lock",
            "hold",
            "sleeper",
            "clutch",
            "stretch",
            "crossface",
            "armbar",
            "submission",
            "ankle",
            "cloverleaf",
            "crab",
        ),
    ),
    (
        "HIGH_FLYER",
        (
            "senton",
            "moonsault",
            "450",
            "splash",
            "dive",
            "frog",
            "shooting star",
            "swanton",
            "phoenix",
            "corkscrew",
            "diving",
        ),
    ),
    (
        "POWERHOUSE",
        (
            "bomb",
            "slam",
            "driver",
            "spear",
            "suplex",
            "press",
            "powerbomb",
            "chokeslam",
            "buster",
        ),
    ),
    (
        "BRAWLER",
        (
            "punch",
            "kick",
            "lariat",
            "clothesline",
            "knee",
            "elbow",
            "stunner",
            "ddt",
            "headbutt",
            "cutter",
            "fist",
        ),
    ),
)
"""피니셔 이름에서 플레이스타일을 읽는 순서. **먼저 걸린 것이 이긴다.**

기술 이름은 그 선수가 무엇으로 먹고사는지를 가장 잘 드러내는 한 줄이다. 체중보다 앞에
두는 이유: 120kg 테크니션과 70kg 브롤러가 실제로 있다.
"""

HEAVY_KG = 120
LIGHT_KG_BY_GENDER = {"MALE": 75, "FEMALE": 55}
"""피니셔로 못 가른 선수를 체중으로 가른다. 그 사이는 쇼맨으로 둔다.

**가벼움의 기준은 디비전마다 다르다.** 75kg 하나로 재면 여성부는 대부분이 그 아래라
32명이 통째로 하이플라이어가 됐다 — 체급 분포가 다른 두 집단에 같은 자를 댄 탓이다.
"""

STYLE_OVERRIDES: dict[str, str] = {
    # 남성부
    "Roman Reigns": "POWERHOUSE",
    "Cody Rhodes": "SHOWMAN",
    "CM Punk": "TECHNICIAN",
    "Seth Rollins": "SHOWMAN",
    "Drew McIntyre": "POWERHOUSE",
    "Gunther": "BRAWLER",
    "Randy Orton": "SHOWMAN",
    "Bron Breakker": "POWERHOUSE",
    "Jey Uso": "SHOWMAN",
    "LA Knight": "SHOWMAN",
    "Damian Priest": "BRAWLER",
    "Kevin Owens": "BRAWLER",
    "Solo Sikoa": "POWERHOUSE",
    "Brock Lesnar": "POWERHOUSE",
    "Jacob Fatu": "POWERHOUSE",
    "Finn Bálor": "HIGH_FLYER",
    "Sami Zayn": "TECHNICIAN",
    "Logan Paul": "SHOWMAN",
    "Rey Mysterio": "HIGH_FLYER",
    "Bronson Reed": "POWERHOUSE",
    "Shinsuke Nakamura": "BRAWLER",
    "Ilja Dragunov": "BRAWLER",
    "Pete Dunne": "TECHNICIAN",
    "Chad Gable": "TECHNICIAN",
    "The Miz": "SHOWMAN",
    "R-Truth": "SHOWMAN",
    # 여성부
    "Rhea Ripley": "POWERHOUSE",
    "Bianca Belair": "POWERHOUSE",
    "Becky Lynch": "TECHNICIAN",
    "Charlotte Flair": "TECHNICIAN",
    "Liv Morgan": "SHOWMAN",
    "Iyo Sky": "HIGH_FLYER",
    "Bayley": "TECHNICIAN",
    "Tiffany Stratton": "SHOWMAN",
    "Jade Cargill": "POWERHOUSE",
    "Asuka": "TECHNICIAN",
    "Nia Jax": "POWERHOUSE",
    "Naomi": "HIGH_FLYER",
    "Alexa Bliss": "SHOWMAN",
    "Giulia": "BRAWLER",
    "Stepahnie Vaquer": "TECHNICIAN",
}
"""손으로 지정하는 플레이스타일. **피니셔 한 줄로는 못 읽는 선수들이다.**

군터는 서브미션을 쓰지만 그를 정의하는 것은 하드히팅이고, 브록 레스너의 키무라는
그래플러의 기술이지 그의 스타일 전부가 아니다. 알려진 선수일수록 어긋남이 눈에 띄므로
정상급 명단을 중심으로 덮어쓴다.
"""


def _weight_kg(raw: str) -> int | None:
    digits = "".join(c for c in raw if c.isdigit())
    return int(digits) if digits else None


def preset_style(name: str, finisher: str, weight: str, gender: str) -> str:
    if name in STYLE_OVERRIDES:
        return STYLE_OVERRIDES[name]
    low = finisher.lower()
    for style, keywords in STYLE_BY_FINISHER:
        if any(word in low for word in keywords):
            return style
    kg = _weight_kg(weight)
    if kg is not None and kg >= HEAVY_KG:
        return "POWERHOUSE"
    if kg is not None and kg <= LIGHT_KG_BY_GENDER[gender]:
        return "HIGH_FLYER"
    return "SHOWMAN"


def preset_country(birth_place: str, billed_from: str) -> str:
    """출생지·소개지에서 국가 코드. 목록 밖이면 **기타**로 뭉친다 (2026-08-07 사용자 결정)."""
    for source in (birth_place, billed_from):
        token = source.split(",")[-1].strip()
        if token in COUNTRY_BY_PLACE:
            return COUNTRY_BY_PLACE[token]
    return "OTHER"


PRESET_HEADER = '''"""캐릭터 생성 프리셋 — 실존 선수를 바탕으로 내 선수를 만든다 (하네스 §3-D10-1).

**이 파일은 생성물이다.** `scripts/generate_roster.py`가 로스터와 함께 찍어 낸다.

프리셋을 고르면 그 선수의 데이터가 **기본값으로** 들어오고, 원하는 값은 덮어쓸 수 있다
(2026-08-07 사용자 요청). 이름은 언제나 사용자가 정한다 — 실존 인물의 이름을 그대로
쓰는 캐릭터를 만들 수 있게 두면 §3-D13의 고지가 무의미해진다.

목록 밖 출신은 `Country.OTHER`(기타)로 뭉친다 — 게임의 권역이 다섯 개뿐이라(§3-D14)
아프리카·중동을 담을 자리가 없기 때문이다. 그래도 국적은 언제든 덮어쓸 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.constants.countries import Country
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle


@dataclass(frozen=True)
class CharacterPreset:
    """실존 선수 한 명이 캐릭터 생성에 건네주는 값."""

    source: str
    """바탕이 된 실존 선수의 이름. 화면에 "○○를 바탕으로"라고 밝히는 데 쓴다."""
    gender: Gender
    play_style: PlayStyle
    country: Country


PRESETS: tuple[CharacterPreset, ...] = (
'''

PRESET_FOOTER = ''')

BY_SOURCE: dict[str, CharacterPreset] = {p.source: p for p in PRESETS}


def preset_for(source: str) -> CharacterPreset | None:
    """이름으로 프리셋을 찾는다. 없으면 None — 프리셋 없이도 캐릭터는 만들 수 있다."""
    return BY_SOURCE.get(source)
'''


def render_presets(presets: list[tuple[str, str, str, str]]) -> str:
    lines = []
    for source, gender, style, country in presets:
        escaped = source.replace('"', '\\"')
        lines.append(
            f'    CharacterPreset("{escaped}", Gender.{gender}, '
            f"PlayStyle.{style}, Country.{country}),"
        )
    return PRESET_HEADER + "\n".join(lines) + "\n" + PRESET_FOOTER


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="파일에 쓴다")
    args = parser.parse_args()

    members = build()
    counts: dict[tuple[str, str], int] = {}
    for _, gender, tier, _, _, _ in members:
        counts[(gender, tier)] = counts.get((gender, tier), 0) + 1
    real = sum(1 for _, _, _, d, _, _ in members if d == 0)

    print(f"원본: {CSV_PATH.name}")
    print(f"총 {len(members)}명 — 0주차 명부 {real} · 나중 데뷔 {len(members) - real}")
    for gender in ("_M", "_F"):
        row = " · ".join(
            f"{tier} {counts.get((gender, tier), 0):>3}"
            for tier in ("_ME", "_MC", "_P")
        )
        print(f"  {'남성부' if gender == '_M' else '여성부'} 시작 등급: {row}")

    presets = build_presets()
    styles: dict[str, int] = {}
    for _, _, style, _ in presets:
        styles[style] = styles.get(style, 0) + 1
    other = sum(1 for _, _, _, c in presets if c == "OTHER")
    print(f"프리셋 {len(presets)}개 · 기타 국가 {other}명")
    print("  스타일:", " · ".join(f"{k} {v}" for k, v in sorted(styles.items())))

    if args.write:
        OUT_PATH.write_text(render(members), encoding="utf-8")
        PRESET_OUT_PATH.write_text(render_presets(presets), encoding="utf-8")
        print(f"\n{OUT_PATH.relative_to(APP_DIR.parents[1])} 갱신")
        print(f"{PRESET_OUT_PATH.relative_to(APP_DIR.parents[1])} 갱신")
    else:
        print("\n(미리보기 — 쓰려면 --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
