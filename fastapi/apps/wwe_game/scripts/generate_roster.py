"""로스터 CSV → `domain/constants/roster.py` · `character_presets.py` 생성기 (하네스 §3-D13).

**런타임 import가 아니라 오프라인 생성이다.** `lint-imports` 계약이 막는 것은 스포크끼리의
import이고(§2-D3), 빌드 시점에 CSV 파일을 읽어 소스를 찍어 내는 것은 그 계약과 무관하다.

```
uv run python apps/wwe_game/scripts/generate_roster.py        # 미리보기
uv run python apps/wwe_game/scripts/generate_roster.py --write # 파일 갱신
```

## 원본은 두 파일이다

| 파일 | 주는 것 | 소유 |
|---|---|---|
| `kayfabe/_docs/wwe_active_roster_cleaned.csv` | 섹션·출생지·소개지 | kayfabe |
| `wwe_game/_docs/roster_game_data.csv` | **한글명·성별·등급·플레이스타일·생년월일** | 이 게임 |

**kayfabe CSV에 컬럼을 더할 수 없다** — 그쪽 적재 스크립트가 헤더를 정확히 대조해서
(`load_wrestlers_csv._read_rows`) 컬럼이 하나만 늘어도 멈춘다. 소유도 이쪽이 맞다:
한글 표기와 등급은 kayfabe의 사실이 아니라 이 게임의 값이다.

## 추정을 걷어 냈다 (2026-08-10 사용자가 데이터를 채워 옴)

한글 표기는 `KOREAN_NAMES` 표가, 성별은 섹션별 알파벳 되감김이, 플레이스타일은
피니셔 이름과 체중이 메우고 있었다. 사용자가 178명 전원의 한글명과 경기 유형을 채운
CSV를 가져오면서 **그 추정 경로가 전부 죽었다.**

죽은 추정을 남겨 두는 쪽이 더 위험하다 — 표에 있는 "토자와 아키라"와 CSV에 있는
"아키라 토자와"가 서로 다른데, 둘 중 어느 쪽이 쓰이는지가 칸이 비었는지에 달리게 된다.
그래서 **게임 데이터 CSV를 유일한 원본으로 삼고, 빠진 칸이 있으면 무엇이 빠졌는지
짚어서 멈춘다**(§3-D10-1의 "임의의 기본값을 채워 주지 않는다"와 같은 이유).

## 넣지 않는 것

- **권역** — 이 게임에서 아무 규칙도 읽지 않던 죽은 필드였다(2026-08-07 사용자 지적).
  선수는 어차피 다 미국 무대에 선다. 무대 권역은 서술이 따로 정한다(§3-D14-1).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import sys
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = APP_DIR.parents[0] / "kayfabe" / "_docs" / "wwe_active_roster_cleaned.csv"
OUT_PATH = APP_DIR / "domain" / "constants" / "roster.py"

GAME_DATA_PATH = APP_DIR / "_docs" / "roster_game_data.csv"
"""게임 전용 값 — **사용자가 직접 채우는 파일**이자 이제 유일한 원본이다.

`name`으로 kayfabe CSV와 잇는다. 아래 다섯 칸은 **반드시 채워져 있어야 한다.**

| 칸 | 뜻 |
|---|---|
| `korean_name` | 화면·서술에 쓰는 한글 표기 |
| `gender` | `male` · `female` |
| `tier` | `main_event` · `midcard` · `prospect` |
| `play_style` | 경기 유형 21종의 게임 키 (주 스타일) |
| `birth_date` | 은퇴 주차를 정한다. 미공개면 비워 두고 중앙값으로 간다 |

`sub_styles`·`claimed_styles`는 비어도 된다. 앞은 곁들이는 유형이고, 뒤는 **본인이
주장할 뿐인 유형**이다 — 댄하우젠의 `Showman(Monster)` 같은 괄호 표기가 여기로 온다
(2026-08-10 사용자 지시 4번).
"""

TODAY = datetime.date(2026, 8, 10)
WEEKS_PER_YEAR = 52
CAREER_WEEKS = 30 * WEEKS_PER_YEAR

NPC_RETIRE_AGE: dict[str, int] = {"male": 48, "female": 42}
"""실존 선수가 링을 떠나는 나이. **여성부가 여섯 해 이르다** (2026-08-10 사용자 지시 8번).

플레이어의 만기(50세, §3-D16)보다 남성부가 두 살 이른 것은 그대로다 — 플레이어는
인기도로 나이를 상쇄하는 주인공이고, 배경 선수는 평범한 커브를 탄다.

여성부를 따로 두는 이유는 사용자가 말한 그대로다: 실제로 은퇴가 이르다. 그 대가로
여성부 명부가 더 빨리 비므로 가상 여성 선수의 데뷔 수를 함께 올렸다
(`DEBUTS_PER_YEAR`). 한쪽만 고치면 `MIN_POOL` 검증이 임포트에서 터진다.
"""

LATE_CAREER_AGE = 50
LATE_CAREER_WINDOW = (1, 5)
"""오늘 쉰 살을 넘긴 선수는 **1~5년 안에 은퇴한다** (2026-08-10 사용자 지시 5번).

R-트루스(54) · 레이 미스테리오(51)처럼 나이만 넘긴 채 오늘 현역인 선수들이다. 0주차에
증발시키면 오늘 뛰고 있다는 사실과 어긋나고, 전부 같은 주차에 은퇴시키면 그 주에
명부가 한꺼번에 흔들린다. 이름 해시로 구간 안에 흩뿌린다.
"""

MIN_ACTIVE_WEEKS = 3 * WEEKS_PER_YEAR
"""은퇴 나이를 넘겼지만 아직 쉰은 안 된 선수의 최소 활동 기간."""

DEFAULT_AGE = 32
"""생년월일이 비어 있을 때 쓰는 나이. 명부 전체의 중앙값이다."""

FICTIONAL_CAREER_YEARS = 24
"""가상 선수의 활동 기간. 22세 데뷔 → 46세 은퇴에 해당한다."""

LATE_DEBUT_SECTIONS: dict[str, tuple[int, int]] = {"Evolve": (1, 4)}
"""나중에 데뷔하는 섹션 → (가장 이른 해, 가장 늦은 해).

Evolve는 NXT 아래 육성 단계다. 오늘 명부에 넣으면 유망주가 과밀해지고, 무엇보다
**이들이 메인 무대에 오르는 건 몇 년 뒤**라는 사실과 어긋난다 (2026-08-07 사용자 요청).
"""

REQUIRED_FIELDS = ("korean_name", "gender", "card", "play_style")
"""비어 있으면 생성기가 멈추는 칸.

**`tier`가 `card`로 바뀌었다** (§3-D95, 2026-08-19 사용자 표): 예전 값은 등급이자
브랜드였고(유망주 = NXT), 새 값은 **브랜드 안에서의 위상**이다(`upper`·`mid`·`low`).

`birth_date`와 `alignment`는 비워 둘 수 있다 — 앞은 미공개 정보이고, 뒤는 콜업 때
굴려서 정한다(Evolve의 열둘이 그 상태다).
"""

ARSENAL_FIELDS = ("signature_ko", "finisher_ko")
"""**비어도 되는** 칸 (2026-08-19 사용자 데이터). 없으면 그 선수는 이름 있는 수를 안 쓴다.

한글 표기만 읽는다 — 화면·서술이 전부 한국어라 영문을 그대로 실으면 문장에 섞인다
(§3-D88이 `korean_name`을 따로 받은 것과 같은 이유). 영문 `signature` 칸은 대조용으로
CSV에만 남는다.
"""

# `korean_name`의 `|` 규약 (2026-08-12 사용자 결정) — **앞이 처음 활동명, 뒤가 바꾼 뒤**.
#
# 로스 아메리카노스 셋(브라보·엘 그란데·라요)은 그 이름으로 뛰다가 본래 활동명으로
# 돌아가고, 내티는 내티로 뛰다가 나탈리아가 된다. 이름만 보고는 어느 쪽이 먼저인지 알 수
# 없어서 — 아메리카노가 앞인 행도 뒤인 행도 있었다 — **순서가 곧 규칙**이 되게 CSV를
# 맞췄다. 규칙을 이름에서 추측하면 새 행을 더할 때마다 그 추측이 틀린다.

RENAME_WINDOW = (2, 5)
"""활동명을 바꾸는 시점(연차) 구간 (2026-08-12 사용자 결정).

넷이 같은 주에 한꺼번에 이름을 바꾸면 그 주 인박스가 개명으로만 찬다. 이름 해시로
구간 안에 흩뿌린다 — `LATE_CAREER_WINDOW`가 은퇴에 쓰는 방식 그대로다.
"""

Row = tuple[
    str,
    str,
    str,
    int,
    int | None,
    int,
    str | None,
    str | None,
    int,
    str,
    int,
    bool,
    str,
]
"""명부 한 줄 — (한글명, 성별, **위상**, 데뷔, 은퇴, 경력, 메인 브랜드, 바꾼 이름,
개명 주차, 스테이블, 가상 슬롯, **육성 출발**, **성향**). 칸이 열셋이라 이름을 붙여 둔다."""

GENDER_ALIAS = {"male": "_M", "female": "_F"}
CARD_ALIAS = {"upper": "_UP", "mid": "_MID", "low": "_LOW"}
"""CSV의 위상 표기 → 명부의 별칭 (2026-08-19 사용자 표)."""

ALIGN_ALIAS = {"face": "_FACE", "tweener": "_TWEEN", "heel": "_HEEL"}
"""성향 표기 → 별칭. **빈 칸은 `None`이다** — 콜업 때 굴린다(§3-D95)."""

DEVELOPS: frozenset[str] = frozenset({"NXT", "Evolve"})
"""**육성 브랜드에서 시작하는 섹션** (§3-D95). 여기 사람들만 콜업을 지난다.

예전에는 위상(유망주)이 이 사실을 겸했다 — 그래서 NXT 안에 위상이 없었다.
"""

SECTION_HOME: dict[str, str | None] = {
    "RAW": "_RAW",
    "SmackDown": "_SD",
    "NXT": None,
    "Evolve": None,
    "Free Agent": None,
}
"""섹션 → **콜업되면 갈 메인 브랜드** (§3-D53).

원본 CSV가 섹션으로 브랜드를 이미 들고 있다 — 추정할 것이 없다. None은 "아직 정해지지
않았다"는 뜻이고, 그때만 두 메인 브랜드에 번갈아 넣는다. 육성 브랜드(NXT·Evolve)와
프리에이전트가 거기 해당한다: **그들의 미래는 어차피 이 게임이 지어내는 것**이라,
지어내되 규칙으로 지어내고 그 규칙을 여기 적어 둔다.
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

**은퇴 나이는 디비전마다 다르다** — 남성부 48세, 여성부 42세(2026-08-10 사용자 지시).
오늘 쉰을 넘긴 선수는 1~5년 안에 떠난다. 여성부가 빨리 비는 만큼 가상 여성 선수를
해마다 더 많이 데뷔시킨다.

가상 선수가 필요한 이유가 여기 있다 — 실존 선수만으로는 커리어 후반의 대립 상대가
바닥난다. 이름은 조합으로 만들되 실존 이름과 겹치지 않게 걸렀다.

**kayfabe의 로스터를 import할 수 없다** — 스포크끼리는 못 붙는다(§2-D3). 원본은
`_docs/wwe_active_roster_cleaned.csv`이고, 베끼는 일은 생성기가 한다.

실존 인물이므로 **서술이 사실 주장처럼 읽히지 않아야** 한다 — 게임 내 가상 전개임을
생성 화면과 로그 하단에 표시한다(§3-D13).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import cache, lru_cache

from wwe_game.domain.constants.career_clock import CAREER_WEEKS, WEEKS_PER_YEAR
from wwe_game.domain.constants.teams import (
    FICTIONAL_TEAM_HEADS,
    FICTIONAL_TEAM_TAILS,
)
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import Gender


class RivalTier(IntEnum):
    """**카드에서의 위상** (§3-D95, 2026-08-19 사용자 표).

    브랜드 안에서 어디쯤 서는 사람인가다 — 대립 상대와 도전할 벨트가 여기서 갈린다.

    **예전에는 이 축이 브랜드를 겸했다**(유망주 = NXT). 그러면 육성 브랜드 안에 위상이
    없어서, NXT 챔피언이 그 주의 신인과 같은 확률로 뽑혔다 — 사용자가 *"비정상적인
    챔피언들이 속출한다"*고 짚은 자리다. 이제 브랜드는 `develops`가 따로 든다.
    """

    LOW_CARD = 1
    MID_CARD = 2
    UPPER_CARD = 3


class Alignment(StrEnum):
    """페이스 · 트위너 · 힐 (§3-D95, 2026-08-19 사용자 표).

    **정해진 사람과 아직 안 정해진 사람이 있다.** Evolve의 열둘과 가상 선수는 콜업될
    때 굴려서 정하고(사용자 결정), 그 뒤에도 바뀔 수 있다 — 실제로도 성향은 커리어
    중에 몇 번 뒤집힌다(§3-D39가 플레이어에게 이미 그렇게 해 두었다).
    """

    FACE = "face"
    TWEENER = "tweener"
    HEEL = "heel"


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
    home_brand: Brand = Brand.RAW
    """콜업된 뒤 설 메인 브랜드 (§3-D53). **지금 있는 브랜드가 아니다** — 그건
    `brand_at()`이 답한다.
    """
    renamed_to: str | None = None
    """바꾼 뒤의 활동명 (§3-D54). 안 바꾸면 None이다."""
    rename_week: int = 0
    """이 주차부터 `renamed_to`로 불린다. `renamed_to`가 있을 때만 뜻이 있다."""
    slot: int = -1
    """가상 선수의 자리 번호 (§3-D59). 실존 선수는 -1이다.

    **이름이 판마다 바뀌기 때문에** 자리로 식별한다 — 명부의 크기·데뷔·은퇴는 상수이고
    거기 서는 사람의 이름만 시드를 탄다. `name_at()`이 그 판의 이름을 답한다.
    """
    stable: str = ""
    """속한 스테이블 (§3-D58). 빈 문자열이면 **독립 선수**다.

    태그 벨트는 여기서 갈린다 — 스테이블 소속은 **같은 스테이블 안에서만** 짝을 짜고,
    독립은 독립끼리 짠다.
    """
    develops: bool = False
    """**육성 브랜드에서 시작하는가** (§3-D95). NXT·Evolve 사람들이 참이다.

    예전에는 위상(`start_tier`)이 브랜드를 겸했다 — 유망주면 NXT였다. 그러면 NXT 안에
    위상이 없어서 신인과 챔피언이 같은 칸에 섰다. 축을 나누고 나서야 *"NXT 어퍼카드"*가
    말이 된다.
    """
    alignment: Alignment | None = None
    """페이스 · 트위너 · 힐 (§3-D95). **`None`이면 아직 안 정해졌다** — 콜업 때 굴린다.

    Evolve의 열둘과 가상 선수가 그 상태다(사용자 결정). 정해진 뒤에도 `alignment_at()`이
    커리어 중에 몇 번 뒤집는다.
    """

    def is_active_at(self, week: int) -> bool:
        if week < self.debut_week:
            return False
        return self.retire_week is None or week < self.retire_week


PROMOTION_WEEKS: tuple[int, int] = (6 * WEEKS_PER_YEAR, 14 * WEEKS_PER_YEAR)
"""(로우 → 미드, 미드 → 어퍼) 위상이 오르는 데 걸리는 **누적 경력**.

**위상을 고정하면 두 번 틀린다.** 오늘의 신인이 서른 해 뒤에도 신인으로 남고, 은퇴로
빠져나간 어퍼카드 자리를 아무도 채우지 않는다. 데뷔 6년 · 15년을 지나면 올라간다 —
사용자가 말한 *"시뮬 도중에 위상이 바뀌기도 한다"*가 이 자리다.
"""


PROMOTION_STEP = 3 * WEEKS_PER_YEAR
"""위상을 다시 굴리는 간격 (§3-D95). 세 해에 한 번이면 서른 해에 열 번이다."""

RISE_CHANCE: dict[RivalTier, float] = {
    RivalTier.LOW_CARD: 0.40,
    RivalTier.MID_CARD: 0.25,
}
"""한 번의 굴림에서 위상이 오를 확률.

**어퍼카드로 가는 문이 훨씬 좁다.** 로우 → 미드는 흔한 일이지만 미드 → 어퍼는 커리어에
한 번 있을까 말까다 — 사용자 표에서도 어퍼는 서른 명뿐이고 미드가 백여섯이다.
"""

FALL_CHANCE: dict[RivalTier, float] = {
    RivalTier.UPPER_CARD: 0.30,
    RivalTier.MID_CARD: 0.10,
}
"""한 번의 굴림에서 위상이 **내려갈** 확률 (§3-D95).

**오르기만 하면 서른 해 뒤 로스터가 통째로 어퍼카드가 된다** — 실측에서 브랜드당 어퍼가
스물넷까지 부풀었고, 그 세계에서는 챔피언이 아무 뜻도 없다. 위에서 내려오는 사람이
있어야 아래에서 올라오는 사람에게 자리가 생긴다.

**어퍼가 미드보다 세 배 빨리 내려온다.** 정상은 붙어 있기 어려운 자리다.

이 네 값(오름 둘 · 내림 둘)으로 브랜드·디비전당 어퍼 5~12명이 유지된다 — 사용자 표의
0주차 분포(브랜드당 7~8)와 같은 크기다.
"""

DECLINE_BEFORE = 2 * WEEKS_PER_YEAR
"""은퇴 몇 주 앞에서 한 칸 더 내려오는가 (§3-D95).

굴림과 별개로 **마지막 두 해는 무조건 한 칸 아래**다. 실제로도 그 구간은 후배를 올려
주는 자리다.
"""

NXT_RISE_CHANCE: dict[RivalTier, float] = {
    RivalTier.LOW_CARD: 0.60,
    RivalTier.MID_CARD: 0.45,
}
"""**육성 브랜드 안에서는 빨리 오른다** (§3-D95).

메인 로스터의 확률로 굴리면 육성에서 정상까지 스무 해가 걸리는데, 거기 머무는 기간은
길어야 열 해다 — 실측에서 5년차부터 **NXT 어퍼카드가 0명**이었고, 그러면 그 브랜드의
챔피언을 뽑을 자리가 없다. 육성은 사람을 올리는 곳이라 실제로도 빠르다.

**내려가는 굴림은 육성에 없다.** 거기서 내려갈 자리가 없다 — 안 되면 올라가지 못한 채
콜업되거나 명부에서 사라진다.
"""

NXT_DWELL_YEARS: tuple[int, int] = (1, 3)
"""육성 브랜드 정상에 오른 뒤 **머무는 기간** (§3-D95). 이름 해시로 흩뿌린다.

**꼭대기에 서자마자 올려 보내면 NXT의 어퍼카드가 늘 비어 있다** — 실측에서 5년차부터
0명이었다. 그 브랜드의 챔피언이 될 자리가 없다는 뜻이라, 사용자가 짚은 *"비정상적인
챔피언"*이 이쪽에서 다시 생긴다.

**기간을 한 값으로 두면 다 같이 올라간다.** 실측에서 5년차에 NXT 어퍼카드 열다섯이
같은 주에 통째로 콜업돼 그 브랜드가 한 번에 비었다 — `_spread`가 은퇴·개명에 쓰는
흩뿌리기와 같은 자리다.
"""

MAX_NXT_WEEKS = 10 * WEEKS_PER_YEAR
"""정상에 못 올라도 이만큼 지나면 콜업된다. **육성에 눌러앉는 사람을 만들지 않는다.**"""


MIN_PROMOTION_WEEKS = 4 * WEEKS_PER_YEAR
"""경력이 아무리 길어도 등장 후 이만큼은 지나야 올라간다. 0주차 명부를 지키는 바닥이다."""


_M, _F = Gender.MALE, Gender.FEMALE
_LOW, _MID, _UP = RivalTier.LOW_CARD, RivalTier.MID_CARD, RivalTier.UPPER_CARD
_FACE, _TWEEN, _HEEL = Alignment.FACE, Alignment.TWEENER, Alignment.HEEL
_RAW, _SD = Brand.RAW, Brand.SMACKDOWN

FICTIONAL_NAMES: dict[Gender, tuple[str, ...]] = {
{POOL}
}
"""가상 선수 이름 후보 (§3-D59). **판마다 여기서 골라 쓴다.**

명부의 크기·데뷔·은퇴는 상수이고 이름만 시드를 탄다 — "새 판마다 다른 신인이 올라온다"는
감각은 이름에서 오지, 명부 구조에서 오지 않는다. 구조까지 시드에 태우면 `MIN_POOL`
검증이 시드마다 성립해야 하고, 그건 훨씬 큰 이야기다.
"""

ROSTER: tuple[RosterMember, ...] = (
'''

FOOTER = ''')

SIGNATURES: dict[str, tuple[str, ...]] = {
{SIGNATURES}}
"""선수별 시그니처 — **그 사람의 무기고** (§3-D91, 2026-08-19 사용자 데이터).

빈 선수는 아예 안 들어온다. 그래서 `signatures_of()`가 빈 튜플을 돌려주고, 그 선수는
이름 있는 수를 쓰지 않는다 — 데이터가 오기 전과 같은 동작이다.

**개수가 곧 빈도다**(`match_flow.signature_chance`). 아홉 개를 가진 선수는 한 개인
선수보다 자주 자기 기술로 간다 — 실제로도 대표 기술이 많은 선수가 경기 중에 더 자주
그것들을 꺼낸다.
"""

FINISHER_NAMES: dict[str, tuple[str, ...]] = {
{FINISHERS}}
"""선수별 피니셔 이름 (§3-D91). 하나 이상인 선수가 실제로 있다.

플레이어의 피니셔는 여기 없다 — 그건 §3-D88이 고르게 하는 값이고, 이쪽은 **상대가
나를 끝낼 때** 그 기술에 이름이 붙게 하는 자리다.
"""


def signatures_of(name: str) -> tuple[str, ...]:
    """그 선수의 시그니처들. 데이터가 없으면 빈 튜플이다."""
    return SIGNATURES.get(name, ())


def finishers_of(name: str) -> tuple[str, ...]:
    """그 선수의 피니셔들. 데이터가 없으면 빈 튜플이다."""
    return FINISHER_NAMES.get(name, ())


def active_at(week: int) -> tuple[RosterMember, ...]:
    """그 주차에 현역인 선수들."""
    return tuple(m for m in ROSTER if m.is_active_at(week))


@lru_cache(maxsize=256)
def cast_for(seed: int) -> dict[int, str]:
    """그 판의 가상 선수 배역 — 슬롯 번호 → 이름 (§3-D59).

    **명부는 그대로고 이름만 바뀐다.** 누가 언제 데뷔하고 은퇴하는지는 모든 판이 같고,
    그 자리에 서는 사람의 이름을 판마다 다시 뽑는다.

    시드 0은 생성기가 찍어 둔 이름을 그대로 쓴다 — 검증과 테스트가 기준으로 삼는 세계다.
    """
    if seed == 0:
        return {}
    picked: dict[int, str] = {}
    for gender, pool in FICTIONAL_NAMES.items():
        slots = tuple(m.slot for m in ROSTER if m.slot >= 0 and m.gender is gender)
        names = list(pool)
        roll = SeededRoll(seed, len(slots), seeded_roll.ROSTER_CAST)
        for slot in slots:
            if not names:
                break
            picked[slot] = names.pop(roll.between(0, len(names) - 1))
    return picked


STABLE_SIZE: tuple[int, int] = (2, 3)
"""가상 스테이블의 크기 (§3-D64). 둘이면 태그팀, 셋이면 스테이블이다(§3-D30)."""

STABLE_SHARE = 0.35
"""가상 선수가 스테이블에 묶일 확률.

전원을 묶으면 독립 선수가 사라져 태그 벨트의 짝이 늘 같은 무리에서 나온다(§3-D58).
아무도 안 묶으면 실존 팀이 은퇴로 사라진 뒤 30년째 명부에 팀이 하나도 없다.
"""


@lru_cache(maxsize=256)
def stables_for(seed: int) -> dict[int, str]:
    """그 판의 가상 스테이블 — 슬롯 번호 → 팀 이름 (§3-D64).

    **가상 선수와 이어진다**(2026-08-12 사용자 요청). 실존 팀은 30년 안에 전부 은퇴로
    사라지는데(§3-D13-1) 새로 생기는 팀이 없어서, 후반의 태그 벨트는 늘 독립 둘이 들었다.

    **같은 디비전·같은 메인 브랜드에서 묶는다** — 그래야 그 둘이 실제로 한 카드에 설 수
    있다(§3-D53). 앞말은 겹치지 않게 하나씩만 쓴다: 앞말이 열둘뿐이라 그냥 뽑으면 한
    판에 "새비지 브리게이드 · 새비지 커넥션"이 함께 서고, 그러면 다른 팀으로 안 읽힌다
    (§3-D44가 겪은 것).
    """
    roll = SeededRoll(seed, 0, seeded_roll.ROSTER_STABLE)
    # **앞말 목록에 같은 말이 두 번 들어 있다**("새비지") — 접지 않으면 한 판에
    # 같은 앞말의 팀이 둘 선다.
    heads = list(dict.fromkeys(FICTIONAL_TEAM_HEADS))
    picked: dict[int, str] = {}
    for gender in Gender:
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            slots = [
                m
                for m in ROSTER
                if m.slot >= 0 and m.gender is gender and m.home_brand is brand
            ]
            index = 0
            while index < len(slots) and heads:
                if not roll.chance(STABLE_SHARE):
                    index += 1
                    continue
                size = roll.between(*STABLE_SIZE)
                group = slots[index : index + size]
                index += size
                if len(group) < 2:
                    continue
                head = heads.pop(roll.between(0, len(heads) - 1))
                name = f"{head} {roll.pick(FICTIONAL_TEAM_TAILS)}"
                for member in group:
                    picked[member.slot] = name
    return picked


def stable_at(member: RosterMember, seed: int = 0) -> str:
    """그 판에서 속한 스테이블. 없으면 빈 문자열이다 (§3-D58·D64).

    실존 선수는 원본 CSV가 정하고(시드와 무관하다), 가상 선수는 판마다 다시 묶인다.
    """
    if member.slot >= 0:
        return stables_for(seed).get(member.slot, "")
    return member.stable


@lru_cache(maxsize=256)
def _index(seed: int) -> dict[str, RosterMember]:
    """그 판의 이름 → 명부 한 줄.

    **가상 선수는 그 판의 이름만 담는다** (§3-D59). 생성기가 찍어 둔 이름까지 담았더니
    한 이름이 두 사람을 가리켰다 — 배역이 같은 후보 풀에서 나오므로, A의 기본 이름이
    B의 이번 판 이름일 수 있다. 실측에서 아직 데뷔도 안 한 선수가 챔피언으로 나왔다.

    실존 선수는 **개명 전 이름도 함께** 담는다(§3-D54) — 그쪽은 한 사람의 두 이름이라
    충돌하지 않고, 로그에 남은 옛 이름이 없는 사람이 되면 그 기록이 깨진다.
    """
    found: dict[str, RosterMember] = {}
    cast = cast_for(seed)
    for member in ROSTER:
        if member.slot >= 0:
            found[cast.get(member.slot, member.name)] = member
            continue
        for name in (member.name, member.renamed_to):
            if name:
                found[name] = member
    return found


def member_of(name: str, seed: int = 0) -> RosterMember | None:
    """이름으로 명부 한 줄. **플레이어는 명부에 없으므로 None이 정상이다.**"""
    return _index(seed).get(name)


def name_at(member: RosterMember, week: int, seed: int = 0) -> str:
    """그 주차에 불리던 이름.

    가상 선수는 **판마다 다른 이름**을 쓰고(§3-D59), 실존 선수는 활동명 변경을 따른다
    (§3-D54) — 로스 아메리카노스 셋은 그 이름으로 뛰다가 본래 활동명으로 돌아가고,
    내티는 나탈리아가 된다.
    """
    if member.slot >= 0:
        return cast_for(seed).get(member.slot, member.name)
    if member.renamed_to is not None and week >= member.rename_week:
        return member.renamed_to
    return member.name


DRAFT_WEEK = 50
"""연말 드래프트가 서는 주차 (2026-08-12 사용자 결정).

52주차가 아니라 50주차인 이유: 마지막 두 주에 두면 해가 바뀌는 경계와 겹쳐, 로그에서
"몇 년차의 일인가"가 흐려진다.
"""

DRAFT_PAIRS = 2
"""해마다 자리를 맞바꾸는 **쌍**의 수 — 한 해에 네 명이 브랜드를 옮긴다 (사용자: 3~4명).

**맞바꾸는 이유는 균형이다.** 한쪽으로만 보내면 30년 동안 브랜드 하나가 말라 벨트에
주인이 없어진다(§3-D53의 `MIN_BRAND_POOL`). 같은 디비전·같은 등급끼리 바꾸므로 어느
칸의 인원수도 드래프트로 변하지 않는다 — 바뀌는 것은 **누가 어디 있는가**뿐이다.

쌍은 (디비전 × 등급) 네 칸을 **해마다 돌아가며** 집는다. 칸마다 두 쌍씩 돌리면 한 해에
열여섯 명이 움직여 "연말에 몇 명 오간다"가 아니라 명부 재편이 된다(실측 14.6명).
"""


_DRAFT_CELLS: tuple[tuple[Gender, RivalTier], ...] = tuple(
    (gender, tier)
    for gender in Gender
    for tier in (RivalTier.MID_CARD, RivalTier.UPPER_CARD)
)
"""드래프트가 집을 수 있는 칸.

**로우카드는 없다** — 연말 드래프트는 방송의 얼굴을 맞바꾸는 자리이지 명부 아래쪽을
흔드는 자리가 아니다. 육성에 있는 사람도 빠진다(`_swaps`의 `develops` 조건, §3-D95).
"""


def _champions_at(seed: int, week: int, gender: Gender) -> frozenset[str]:
    """그 주차에 벨트를 들고 있던 사람들 — **드래프트가 건드리지 않는다**
    (2026-08-12 사용자 결정).

    챔피언이 옮겨 가면 벨트가 남의 브랜드에서 걸린다. §3-D53이 "벨트는 자기 브랜드에
    있다"로 잡아 놓은 것을 드래프트가 도로 깨는 셈이다.

    **드래프트 직전 주차로 묻는다.** 그 주차로 물으면 계보가 그 해의 드래프트 결과를
    알아야 하고, 드래프트는 계보를 알아야 해서 둘이 서로를 부르며 돈다. 한 주 앞은
    이미 정해진 세계라 그 고리가 끊긴다 — 뜻도 그쪽이 맞다: *드래프트 당시* 챔피언이다.

    `title_scene`을 함수 안에서 부르는 이유도 같다. 모듈 맨 위에서 부르면 그쪽이 이
    파일을 임포트하는 순간 순환이 된다.
    """
    from wwe_game.domain.services import title_scene
    from wwe_game.domain.value_objects.title import TITLES

    held: set[str] = set()
    for title, spec in TITLES.items():
        if spec.gender is not gender:
            continue
        # 태그 벨트는 둘이 든다 (§3-D57) — **둘 다** 보호해야 팀이 갈라지지 않는다.
        holder = title_scene.champion_at(seed, week, title) or ""
        for name in title_scene.members_of(holder):
            member = member_of(name, seed)
            if member is not None:
                held.add(member.name)
    return frozenset(held)


TRADES_PER_YEAR: tuple[int, int] = (0, 2)
"""시즌 중 트레이드 수 (§3-D63). 연말 드래프트와 **별개로** 선다.

세계가 연말에만 움직이면 나머지 쉰한 주는 명부가 굳어 있다. 다만 잦으면 연말 드래프트가
무엇 때문에 있는지가 사라진다 — 해마다 0~2건이면 "가끔 한 명씩 오간다"로 읽힌다.

트레이드도 **맞바꿈이다**(§3-D54). 한쪽으로만 보내면 브랜드가 마른다.
"""

TRADE_WINDOW: tuple[int, int] = (4, DRAFT_WEEK - 4)
"""트레이드가 설 수 있는 주차 구간. 연초와 드래프트 직전은 비운다 — 드래프트에 붙어
일어나면 그냥 드래프트가 길어진 것으로 읽힌다."""


def _swaps(
    seed: int,
    schedule: list[int],
    state: set[str],
    roll: SeededRoll,
    guard_week: int,
) -> list[tuple[int, str]]:
    """정해진 주차마다 한 쌍씩 맞바꾼다 (§3-D54).

    `guard_week`는 **챔피언을 어느 시점으로 볼지**다 — 그 주차의 벨트 주인은 자리를
    옮기지 않는다(2026-08-12 사용자 결정).
    """
    moves: list[tuple[int, str]] = []
    for week in schedule:
        gender, tier = roll.pick(_DRAFT_CELLS)
        guarded = _champions_at(seed, guard_week, gender)
        pools = {
            brand: [
                m
                for m in ROSTER
                if m.gender is gender
                and m.is_active_at(week)
                and tier_at(m, week, seed) is tier
                # **육성에 있는 사람은 드래프트 대상이 아니다** (§3-D95). 위상이
                # 브랜드를 겸하던 때에는 이 조건이 필요 없었다 — 미드카드 이상이면
                # 곧 메인 로스터였다.
                and not (m.develops and week < (call_up_week(m, seed) or 0))
                and _home_at(m, state) is brand
                and m.name not in guarded
            ]
            for brand in (Brand.RAW, Brand.SMACKDOWN)
        }
        if not all(pools.values()):
            continue
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            chosen = roll.pick(pools[brand]).name
            state.symmetric_difference_update({chosen})
            moves.append((week, chosen))
    return moves


@lru_cache(maxsize=4096)
def _trades(seed: int, year: int) -> tuple[tuple[int, str], ...]:
    """그 해 시즌 중 트레이드 (§3-D63).

    **챔피언은 그 해 초로 본다.** 트레이드가 선 그 주의 계보를 물으면 계보가 브랜드를,
    브랜드가 이 함수를 다시 불러 서로를 부르며 돈다 — 연말 드래프트는 그 고리를 피할
    수 있어(트레이드가 이미 정해진 뒤라) 정확한 시점으로 본다.
    """
    if year <= 0:
        return ()
    state = set(_flips_upto(seed, year - 1))
    roll = SeededRoll(seed, year, seeded_roll.TRADE)
    start = year * WEEKS_PER_YEAR
    when = sorted(
        roll.between(*TRADE_WINDOW) for _ in range(roll.between(*TRADES_PER_YEAR))
    )
    return tuple(_swaps(seed, [start + o for o in when], state, roll, start - 1))


@lru_cache(maxsize=4096)
def _draft(seed: int, year: int) -> tuple[tuple[int, str], ...]:
    """그 해 연말 드래프트 (§3-D54). **그 주 직전의 챔피언은 옮기지 않는다.**

    트레이드를 먼저 반영한 상태 위에서 짠다 — 그래야 한 해에 두 번 옮기는 사람이 나오지
    않는다. 고리가 안 도는 이유는 `_flips_at`이 드래프트 주차 **전**의 주차를 물을 때
    이 함수를 부르지 않기 때문이다.
    """
    if year <= 0:
        return ()
    state = set(_flips_upto(seed, year - 1))
    for _, name in _trades(seed, year):
        state.symmetric_difference_update({name})
    week = year * WEEKS_PER_YEAR + DRAFT_WEEK
    roll = SeededRoll(seed, year, seeded_roll.DRAFT)
    return tuple(_swaps(seed, [week] * DRAFT_PAIRS, state, roll, week - 1))


@lru_cache(maxsize=4096)
def _flips_upto(seed: int, year: int) -> frozenset[str]:
    """그 해 **끝**까지 브랜드가 뒤집힌 사람들.

    **앞 해를 다시 걷지 않는다.** 재귀 + 캐시라 한 해치 일만 새로 한다 — 그냥 1년부터
    다시 세면 `pool_for` 한 번이 30년을 걷고, 그게 주차마다 반복된다.
    """
    if year < 0:
        return frozenset()
    flipped = set(_flips_upto(seed, year - 1))
    for _, name in (*_trades(seed, year), *_draft(seed, year)):
        flipped.symmetric_difference_update({name})
    return frozenset(flipped)


def moves_upto(seed: int, week: int) -> tuple[tuple[int, str], ...]:
    """그 주차까지 브랜드를 옮긴 (주차, 이름) 전부 (§3-D65).

    **인박스가 읽는다.** 드래프트와 트레이드로 해마다 서넛이 자리를 옮기는데(§3-D54·D63)
    그 사실이 화면 어디에도 없었다 — 명부는 이미 알고 있었다.
    """
    found: list[tuple[int, str]] = []
    for year in range(week // WEEKS_PER_YEAR + 1):
        for at, name in (*_trades(seed, year), *_draft(seed, year)):
            if at <= week:
                found.append((at, name))
    return tuple(sorted(found))


@lru_cache(maxsize=8192)
def _flips_at(seed: int, week: int) -> frozenset[str]:
    """그 주차까지 뒤집힌 사람들. **주 단위로 본다** — 트레이드는 연중에 선다(§3-D63)."""
    year = week // WEEKS_PER_YEAR
    flipped = set(_flips_upto(seed, year - 1))
    for at, name in _trades(seed, year):
        if at <= week:
            flipped.symmetric_difference_update({name})
    if week % WEEKS_PER_YEAR >= DRAFT_WEEK:
        for _, name in _draft(seed, year):
            flipped.symmetric_difference_update({name})
    return frozenset(flipped)


def _home_at(member: RosterMember, flipped: frozenset[str] | set[str]) -> Brand:
    if member.name not in flipped:
        return member.home_brand
    return Brand.SMACKDOWN if member.home_brand is Brand.RAW else Brand.RAW


def _phase(name: str, span: int, low: int = 0) -> int:
    """이름으로 정해지는 어긋냄 (§3-D95). `low`부터 `low + span - 1` 사이 한 값.

    **명부가 한 주에 통째로 흔들리지 않게 하는 장치다.** 생성기의 `_spread`가 은퇴·개명을
    흩뿌리는 것과 같은 자리이고, 여기서는 위상 굴림의 시점과 육성 체류 기간을 흩뿌린다.

    blake2b라 프로세스가 바뀌어도 같은 값이 나온다 — 시드 규약과 같은 이유다(§3-D4).
    """
    digest = hashlib.blake2b(name.encode(), digest_size=8).digest()
    return low + int.from_bytes(digest, "big") % max(1, span)


@cache
def tier_at(member: RosterMember, week: int, seed: int = 0) -> RivalTier:
    """그 주차의 위상 (§3-D95). **오르기도 하고 내려가기도 한다.**

    *"물론 이 선수들도 시뮬 도중에 위상이 바뀌기도 해"* (2026-08-19 사용자).

    | 층 | |
    |---|---|
    | 오름 | `PROMOTION_STEP`마다 한 번씩 굴린다 — **자동이 아니다** |
    | 내림 | 은퇴가 `DECLINE_BEFORE` 앞으로 다가오면 한 칸 내려온다 |

    **예전에는 시계만으로 올랐다.** 그러면 서른 해 뒤 메인 로스터가 통째로 어퍼카드가
    되고(실측: 브랜드당 36명), 그 세계에서는 챔피언이 아무 뜻도 없다 — 사용자가 짚은
    *"비정상적인 챔피언"*의 다른 얼굴이다.
    """
    elapsed = week - member.debut_week
    if elapsed < 0:
        return member.start_tier
    # **사람마다 굴리는 주가 다르다.** 다 같이 3년마다 굴리면 명부가 한 주에 통째로
    # 흔들린다 — 실측에서 5년차에 NXT가 한 번에 비었다.
    elapsed -= _phase(member.name, PROMOTION_STEP)
    tier = member.start_tier
    for step in range(1, elapsed // PROMOTION_STEP + 1):
        # **채널에 이름을 싣는다.** 안 그러면 같은 주차에 데뷔한 사람들이 한 번의
        # 굴림을 나눠 가져 **다 같이 오르거나 다 같이 제자리**다 — 실측에서 0주차
        # NXT 미드카드 서른다섯이 한 명도 안 올라갔다.
        roll = SeededRoll(
            seed, member.debut_week + step * PROMOTION_STEP, f"status:{member.name}"
        )
        # **육성에 있는 동안은 다른 표를 쓴다** (§3-D95). `call_up_week()`를 부르면
        # 서로를 부르게 되므로, 육성에 머물 수 있는 최대 기간으로 가른다.
        in_developmental = member.develops and step * PROMOTION_STEP <= MAX_NXT_WEEKS
        table = NXT_RISE_CHANCE if in_developmental else RISE_CHANCE
        rise = table.get(tier, 0.0)
        fall = 0.0 if in_developmental else FALL_CHANCE.get(tier, 0.0)
        # **한 번의 굴림에 한 방향만.** 오름을 먼저 묻는 이유는 이 게임이 커리어를
        # 올라가는 이야기이기 때문이고, 내림은 그 다음 자리다.
        if rise and roll.chance(rise):
            tier = RivalTier(tier + 1)
        elif fall and roll.chance(fall):
            tier = RivalTier(tier - 1)
    if member.retire_week is not None and week >= member.retire_week - DECLINE_BEFORE:
        # **황혼에는 한 칸 내려온다** — 자리를 비워 줘야 아래가 올라온다.
        tier = RivalTier(max(RivalTier.LOW_CARD, tier - 1))
    return tier


def _wait_for(member: RosterMember, step: int) -> int:
    """승급까지 **등장 시점부터** 기다리는 주차.

    쌓아 온 경력은 기다림을 줄이지만 **0으로 만들지는 않는다.** 그대로 빼면 14년 차
    미드카더가 0주차에 곧바로 정상급이 되어 오늘의 분류를 덮어쓴다 — 실측에서 0년차
    남자 정상급이 20명에서 47명으로 부풀었다.
    """
    earned = member.experience_years * WEEKS_PER_YEAR
    return max(MIN_PROMOTION_WEEKS, PROMOTION_WEEKS[step] - earned)


@cache
def brand_at(member: RosterMember, week: int, seed: int = 0) -> Brand:
    """그 주차에 이 사람이 선 브랜드 (§3-D53 · §3-D95).

    **위상이 아니라 `develops`가 답한다** (2026-08-19 개정). 예전에는 유망주면 NXT였고,
    그래서 NXT 안에 위상이 없었다 — 신인과 챔피언이 한 칸에 섰다. 이제 육성 브랜드에서
    시작한 사람만 NXT에 있고, `call_up_week`을 지나면 자기 메인 브랜드로 올라간다.
    """
    if member.develops and week < (call_up_week(member, seed) or 0):
        return Brand.NXT
    return _home_at(member, _flips_at(seed, week))


@cache
def call_up_week(member: RosterMember, seed: int = 0) -> int | None:
    """육성 브랜드를 떠나는 주차 (§3-D53 · §3-D95). **메인에서 시작하면 None이다.**

    **위상이 높을수록 빨리 올라간다** (2026-08-19): NXT 어퍼카드는 이미 그 브랜드에서
    할 일을 끝낸 사람이고, 로우카드는 몇 해를 더 쌓는다. 예전에는 위상이 곧 브랜드라
    이 시계가 하나뿐이었다.

    벨트 계보가 이걸 읽는다 — 콜업된 사람은 NXT 벨트를 들고 갈 수 없다(§3-D38).
    """
    if not member.develops:
        return None
    low, high = NXT_DWELL_YEARS
    dwell = _phase(f"dwell:{member.name}", high - low + 1, low) * WEEKS_PER_YEAR
    for step in range(0, MAX_NXT_WEEKS // PROMOTION_STEP + 1):
        week = member.debut_week + step * PROMOTION_STEP
        if tier_at(member, week, seed) is RivalTier.UPPER_CARD:
            # **정상에 선 뒤 한두 해를 더 있는다** — 그 사이 NXT의 꼭대기가 비지 않는다.
            return min(week + dwell, member.debut_week + MAX_NXT_WEEKS)
    return member.debut_week + MAX_NXT_WEEKS


ROLLED_ALIGNMENT: tuple[Alignment, ...] = (
    Alignment.FACE,
    Alignment.FACE,
    Alignment.HEEL,
    Alignment.HEEL,
    Alignment.TWEENER,
)
"""아직 안 정해진 사람이 콜업될 때 뽑는 통 (§3-D95, 2026-08-19 사용자 결정).

*"Evolve는 아직 페이스·트위너·힐이 안 정해져 있는데, 얘네는 콜업될 때 랜덤으로 정해져서
올라오게 해줘."* 가상 선수도 같다.

**트위너가 드문 것은 표를 따른 것이다** — 사용자가 정해 준 179명 중 트위너는 여섯이다.
둘 중 하나를 고르는 것이 대부분이고, 어느 쪽도 아닌 사람은 드물다.
"""

TURN_EVERY: int = 6 * WEEKS_PER_YEAR
"""성향이 뒤집힐 수 있는 간격 (§3-D95).

*"물론 계속 유지가 아니라 변경이 가능해"* (사용자). 여섯 해마다 한 번 굴려 그중
`TURN_CHANCE`만 실제로 뒤집는다 — 커리어에 한두 번이면 사건이고, 해마다면 소음이다.
"""

TURN_CHANCE: float = 0.35


@cache
def alignment_at(member: RosterMember, week: int, seed: int = 0) -> Alignment:
    """그 주차의 성향 (§3-D95).

    세 층이다.

    1. **표에 있으면 그것으로 시작한다** (사용자가 정해 준 179명)
    2. **없으면 콜업 때 굴린다** — Evolve와 가상 선수
    3. **여섯 해마다 뒤집힐 수 있다** — 정해진 사람도 예외가 아니다

    시드와 주차로만 굴리므로 **같은 밤을 다시 열면 같은 성향**이다(§3-D4).
    """
    start = member.alignment
    if start is None:
        # 이름을 실어야 한 해에 올라온 신인들이 **같은 성향으로 몰리지 않는다.**
        roll = SeededRoll(seed, member.debut_week, f"align:{member.name}")
        start = roll.pick(ROLLED_ALIGNMENT)
    turns = max(0, (week - member.debut_week) // TURN_EVERY)
    now = start
    for index in range(turns):
        roll = SeededRoll(
            seed, member.debut_week + index * TURN_EVERY, f"turn:{member.name}"
        )
        if roll.chance(TURN_CHANCE):
            now = _turned(now, roll)
    return now


def _turned(now: Alignment, roll: SeededRoll) -> Alignment:
    """뒤집힌 성향. **트위너는 양쪽 어디로든 간다** — 그게 트위너의 자리다."""
    if now is Alignment.TWEENER:
        return roll.pick((Alignment.FACE, Alignment.HEEL))
    other = Alignment.HEEL if now is Alignment.FACE else Alignment.FACE
    return roll.pick((other, other, Alignment.TWEENER))


def tier_in(brand: Brand, tier: RivalTier) -> RivalTier:
    """그 브랜드에 **실제로 있는** 위상으로 접는다.

    **이제 접을 것이 거의 없다** (§3-D95). 세 브랜드 모두 어퍼·미드·로우가 다 있으므로
    (사용자 표) 위상을 그대로 쓴다 — 예전에는 NXT에 유망주만 살아서 모든 물음을
    유망주로 접어야 했고, 그것이 NXT 챔피언을 신인 중에서 뽑던 원인이었다.

    함수를 남겨 두는 이유: 부르는 자리가 열 곳이 넘고, 앞으로 브랜드마다 없는 칸이
    생기면 **그 판단이 다시 여기 한 곳에 모여야** 한다.
    """
    return tier


@lru_cache(maxsize=8192)
def pool_for(
    gender: Gender,
    tier: RivalTier,
    week: int = 0,
    brand: Brand | None = None,
    seed: int = 0,
) -> tuple[str, ...]:
    """그 주차에 현역이면서 디비전·등급이 맞는 이름들 (§3-D11).

    `brand`를 주면 그 브랜드에 선 사람만 남는다 (§3-D53). **등급은 접어서 넣어야 한다** —
    `tier_in(brand, tier)`을 거치지 않고 부르면 빈 명단이 나올 수 있다.

    `seed`는 드래프트를 태운다 (§3-D54). 드래프트는 같은 디비전·같은 등급끼리 맞바꾸므로
    **그 순간에는** 칸의 인원수가 변하지 않는다 — 다만 표식이 사람을 따라다녀, 그가 나중에
    승급하면 다른 칸으로 넘어가 한 명쯤 기운다. 아래 임포트 검증은 시드 0만 보고, 다른
    세계의 바닥은 테스트가 시드 넷으로 잰다.

    **캐시한다.** 명부는 상수이고 이 함수는 순수하다. 벨트 계보가 30년을 걸을 때마다
    재위 경계에서 이걸 부르고, 벨트가 열둘이라 같은 칸을 수십 번 다시 센다.
    """
    return tuple(
        name_at(m, week, seed)
        for m in ROSTER
        if m.gender is gender
        and m.is_active_at(week)
        and tier_at(m, week, seed) is tier
        and (brand is None or brand_at(m, week, seed) is brand)
    )


REACH_UP_CHANCE = 0.18
"""**한 칸 위를 넘보는 확률** (§3-D95, 2026-08-19 사용자 요청).

*"가끔씩 미드카드가 어퍼카드 챔피언십을 노리고, 로우카드가 미드카드 챔피언십을 노리는
등 이런 일들이 있었으면 해. 대립도 같이."*

다섯에 한 번쯤이면 **사건**이고, 절반이면 위상이 없는 것과 같다. 어퍼카드는 더 갈 곳이
없으므로 이 굴림을 지나치고, 아래로 내려가는 굴림은 두지 않았다 — 위를 보는 이야기가
아래를 보는 이야기보다 훨씬 자주 쓰인다.
"""


def reaching_tier(tier: RivalTier, week: int, seed: int = 0) -> RivalTier:
    """그 주차에 **넘보는** 위상 (§3-D95). 대개는 제 위상 그대로다.

    주차와 시드로만 굴리므로 같은 주를 다시 열면 같은 답이다(§3-D4).
    """
    if tier is RivalTier.UPPER_CARD:
        return tier
    roll = SeededRoll(seed, week, "reach")
    return RivalTier(tier + 1) if roll.chance(REACH_UP_CHANCE) else tier


def tier_for_popularity(popularity: int) -> RivalTier:
    """인기도에 맞는 상대 등급. **급이 맞아야 대립이 성립한다.**

    무명이 월드 챔피언과 대립하는 것도, 정상급이 유망주와 몇 달을 싸우는 것도
    이야기가 되지 않는다.
    """
    if popularity >= 60:
        return RivalTier.UPPER_CARD
    if popularity >= 30:
        return RivalTier.MID_CARD
    return RivalTier.LOW_CARD


MIN_POOL = 6
"""어느 (디비전 × 등급) 칸도 **커리어 어느 시점에서도** 이보다 얇으면 안 된다.

주차를 넣기 전에는 임포트 시점에 한 번만 셌다. 그때는 명부가 안 변했으니 그걸로 충분했다 —
지금은 20년 차에 정상급이 비는 일이 생길 수 있어 전 구간을 훑는다.
"""

MIN_BRAND_POOL = 3
"""브랜드까지 나눈 칸의 바닥 (§3-D53). 전체 바닥(`MIN_POOL`)보다 낮게 잡는다.

세 브랜드로 나누면 칸이 3분의 1이 된다. 실측 최저는 여성부 정상급 RAW의 4명이고,
그 밑을 허용하면 챔피언을 뽑을 때 현 챔피언과 플레이어를 빼고 나서 아무도 안 남는다.
"""

for _g in Gender:  # pragma: no cover - 임포트 시 구조 검증
    for _t in RivalTier:
        for _w in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
            if len(pool_for(_g, _t, _w)) < MIN_POOL:
                raise RuntimeError(
                    f"{_g}/{_t} 라이벌 풀이 {_w // WEEKS_PER_YEAR}년차에 "
                    f"너무 얇습니다: {pool_for(_g, _t, _w)}"
                )

# **브랜드 칸 검증은 여기서 하지 않는다** (§3-D65).
#
# 브랜드를 물으면 드래프트를 물어야 하고(§3-D54), 드래프트는 그 시점 챔피언을 물어야
# 하고(사용자 규칙), 챔피언은 계보 — 즉 `title_scene` — 를 물어야 한다. 그런데
# `title_scene`은 이 파일을 임포트한다. **임포트 시점에 그 고리를 돌리면 순서에 따라
# 터진다**: 계보를 먼저 임포트한 프로세스에서는 아직 정의되지 않은 함수를 부르게 된다.
#
# 지금까지는 진입점이 명부를 먼저 임포트해서 가려져 있었다. 브랜드 칸의 바닥은
# `MIN_BRAND_POOL`과 함께 **테스트가 시드 넷으로 검사한다**(`test_draft_and_names.py`).
'''


def read_game_data() -> dict[str, dict[str, str]]:
    """사용자가 채운 게임 데이터. **이 파일이 유일한 원본이라 없으면 멈춘다.**"""
    if not GAME_DATA_PATH.exists():
        raise SystemExit(f"{GAME_DATA_PATH}가 없습니다 — 게임 값의 원본입니다")
    rows = csv.DictReader(io.StringIO(GAME_DATA_PATH.read_text(encoding="utf-8-sig")))
    return {
        (row.get("name") or "").strip(): {
            k: (v or "").strip() for k, v in row.items() if k
        }
        for row in rows
        if (row.get("name") or "").strip()
    }


GAME_DATA: dict[str, dict[str, str]] = {}
"""`main()`이 채운다. 아래 해석 함수들이 읽는다."""

ARSENALS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
"""한글 이름 → (시그니처들, 피니셔들). `build()`가 채우고 `render()`가 찍는다.

가상 선수는 안 들어온다 — 이름이 판마다 바뀌는 자리라(§3-D59) 고정된 기술을 붙일
수 없다. 그쪽은 계열 기술로 간다.
"""


def given(name: str, field: str) -> str:
    return GAME_DATA.get(name, {}).get(field, "")


def require(name: str, field: str) -> str:
    """빠진 칸은 **조용히 메우지 않고 무엇이 빠졌는지 짚어서 멈춘다** (§3-D10-1)."""
    value = given(name, field)
    if not value:
        raise SystemExit(
            f"{GAME_DATA_PATH.name}: {name!r}의 {field} 칸이 비었습니다 — "
            "새 선수를 kayfabe CSV에 넣었다면 이 파일에도 같은 name으로 행을 더하세요"
        )
    return value


def arsenal_of(name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """그 선수의 (시그니처들, 피니셔들) — 한글 표기 (2026-08-19 사용자 데이터).

    **둘 다 `|`로 여러 개가 온다.** 피니셔가 하나 이상인 선수가 실제로 있고
    (`타임 밤 | 캐나디언 디스트로이어`), 시그니처는 아홉 개인 선수까지 있다.

    빈 칸은 빈 튜플이다 — **생성기가 대신 지어내지 않는다**(§3-D10-1의 원칙 그대로).
    이름이 없는 선수는 계열 기술만 쓰고, 그건 이 데이터가 오기 전의 동작과 같다.
    """
    signatures, finishers = (given(name, field) for field in ARSENAL_FIELDS)
    return _split(signatures), _split(finishers)


def _split(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split("|") if part.strip())


def read_stables(path: Path) -> dict[str, str]:
    """선수 이름 → 스테이블 (§3-D58). 없으면 빈 문자열이다.

    원본의 `Stable&Team` 열이 그대로 답이다 — 추정할 것이 없다. `|`로 둘이 적힌 행
    ("Bloodline | The Usos")은 **앞을 스테이블로 본다**: 뒤는 그 안의 태그팀 이름이라,
    둘을 따로 세면 한 스테이블이 두 개로 갈린다.
    """
    rows = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    found: dict[str, str] = {}
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name or name.startswith("#"):
            continue
        stable = (row.get("Stable&Team") or "").strip()
        found[name] = stable.split("|")[0].strip()
    return found


def read_sections(path: Path) -> dict[str, list[str]]:
    """섹션 이름 → 선수 이름. 등장 순서를 그대로 지킨다."""
    rows = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for row in rows:
        cell = (row.get("name") or "").strip()
        if not cell:
            continue
        if cell.startswith("#"):
            current = cell[1:]
            sections[current] = []
        elif current is not None:
            sections[current].append(cell)
    return sections


def age_of(name: str) -> int:
    """생년월일에서 오늘 나이. 미공개면 중앙값을 쓴다.

    **연도만 아는 값도 받는다** — 원본에 `1999-04-??`처럼 일자를 모르는 행이 있다.
    아는 만큼의 정밀도로 세는 편이, 모른다고 중앙값으로 뭉개는 것보다 낫다.
    """
    raw = given(name, "birth_date")
    for text, fmt in ((raw, "%Y-%m-%d"), (raw[:7], "%Y-%m"), (raw[:4], "%Y")):
        try:
            born = datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        return (TODAY - born).days // 365
    return DEFAULT_AGE


DEBUT_AGE = 22
"""프로 데뷔 나이의 어림값. 나이에서 경력을 되짚는 데만 쓴다."""


def experience_of(age: int) -> int:
    return max(0, age - DEBUT_AGE)


def names_of(korean: str) -> tuple[str, str | None]:
    """`korean_name` → (처음 활동명, 바꾼 뒤 이름). 안 바꾸면 뒤가 None이다.

    **`|`의 앞이 처음, 뒤가 나중이다** (§3-D54). 셋 이상 적혀 있으면 앞의 둘만 쓴다 —
    한 커리어에 이름을 세 번 바꾸는 사람까지 그리기 시작하면 명부가 이야기를 갖는다.
    """
    parts = [part.strip() for part in korean.split("|") if part.strip()]
    if len(parts) < 2:
        return korean.strip(), None
    return parts[0], parts[1]


def rename_week_for(korean: str) -> int:
    """활동명을 바꾸는 주차. 이름 해시로 `RENAME_WINDOW` 안에 흩뿌린다."""
    return _spread(korean, *RENAME_WINDOW) * WEEKS_PER_YEAR


def _spread(name: str, low: int, high: int) -> int:
    """이름 해시로 [low, high] 안에 흩뿌린다. blake2b라 실행마다 같은 값이 나온다."""
    span = high - low + 1
    digest = hashlib.blake2b(name.encode(), digest_size=8).digest()
    return low + int.from_bytes(digest, "big") % span


def retire_week_for(name: str, age: int, gender: str) -> int:
    """그 선수가 링을 떠나는 주차 (2026-08-10 사용자 지시 5·8번).

    나이대마다 다른 규칙을 받는다.

    | 나이 | 규칙 |
    |---|---|
    | 50세 이상 | 1~5년 안에 은퇴 — 이름으로 흩뿌려 한꺼번에 빠지지 않게 한다 |
    | 은퇴 나이~49세 | 최소 3년은 더 뛴다 |
    | 그 아래 | `(은퇴 나이 − 나이) × 52` |
    """
    if age >= LATE_CAREER_AGE:
        return _spread(name, *LATE_CAREER_WINDOW) * WEEKS_PER_YEAR
    remaining = (NPC_RETIRE_AGE[gender] - age) * WEEKS_PER_YEAR
    return max(MIN_ACTIVE_WEEKS, remaining)


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
"""가상 선수의 이름 조각 — **북미 계열**. 앞뒤를 곱해 900가지가 나온다.

**손으로 쓰지 않는 이유는 분량이다.** 30년을 채우려면 100명이 넘게 필요하고, 그만큼을
직접 쓰면 뒤로 갈수록 성의가 떨어진다. 실존 이름과 겹치는 조합은 걸러 낸다.
"""


@dataclass(frozen=True)
class NameOrigin:
    """가상 선수 이름의 출신 (2026-08-19 사용자 요청).

    **앞뒤를 같은 출신에서 뽑는다.** 하나의 큰 통에서 섞으면 "제이든 타나카"처럼 어느
    쪽도 아닌 이름이 나온다 — 다채로움이 아니라 뒤죽박죽이다.
    """

    key: str
    male: tuple[str, ...]
    female: tuple[str, ...]
    last: tuple[str, ...]
    share: int
    """뽑히는 비율. 북미가 가장 크다 — 무대가 북미이기 때문이다 (§3-D14-1)."""
    surname_first: bool = False
    """성이 앞에 붙고 띄어쓰기가 없는 표기 — **한국만 그렇다.**

    일본 이름은 띄어 쓰고 이름을 앞에 둔다: 실존 명부가 이미 *"아키라 토자와"*·
    *"신스케 나카무라"*로 적혀 있고, 가상 선수만 다른 규칙을 쓰면 한 화면에서 두 표기가
    부딪힌다.
    """


NAME_ORIGINS: tuple[NameOrigin, ...] = (
    NameOrigin(
        "북미", FICTIONAL_MALE_FIRST, FICTIONAL_FEMALE_FIRST, FICTIONAL_LAST, share=5
    ),
    NameOrigin(
        "유럽",
        (
            "마테오",
            "루카",
            "니클라스",
            "세바스티안",
            "요한",
            "안드레아스",
            "피오트르",
            "빅토르",
            "라이너",
            "도미닉",
            "에밀",
            "구스타프",
        ),
        (
            "엘레나",
            "소피아",
            "잉그리드",
            "카밀라",
            "아넬리",
            "마르타",
            "레나",
            "비앙카",
            "요한나",
            "클라라",
        ),
        (
            "뮐러",
            "슈미트",
            "로시",
            "코바치",
            "노박",
            "라르손",
            "뒤부아",
            "베르크",
            "얀센",
            "모레티",
            "카민스키",
            "린드퀴스트",
        ),
        share=2,
    ),
    NameOrigin(
        "일본",
        ("하야토", "렌", "카이토", "소라", "타쿠마", "리쿠", "다이치", "슌"),
        ("유키", "아야", "리나", "미사키", "카에데", "나오", "히카루"),
        ("타나카", "사토", "쿠로다", "미야모토", "이시카와", "아사노", "후지타"),
        share=1,
    ),
    NameOrigin(
        "라틴아메리카",
        (
            "디에고",
            "하비에르",
            "라파엘",
            "알레한드로",
            "마티아스",
            "엔리케",
            "산티아고",
        ),
        ("카르멘", "이사벨", "루시아", "발렌티나", "파울라", "레지나", "다니엘라"),
        ("라모스", "델가도", "에레라", "바르가스", "카스티요", "모랄레스", "듀란"),
        share=1,
    ),
    NameOrigin(
        "한국",
        ("태준", "민혁", "도현", "지훈", "선우", "재현", "우진"),
        ("하은", "서연", "다인", "예린", "채원", "소민", "지아"),
        ("강", "서", "유", "한", "임", "노", "천"),
        share=1,
        surname_first=True,
    ),
)
"""이름의 출신 다섯 — **게임의 권역과 같은 결이다** (§3-D14).

*"가상선수명은 미국사람 이외에도 아시안, 유럽인 등 다채롭게"* (2026-08-19 사용자 요청).
서른 해 동안 데뷔하는 220명이 전부 "카터 스톤" 같은 이름이면 그 세계엔 한 나라만 있다.

**북미가 여전히 절반이다.** 무대가 북미이고(§3-D14-1) 실존 명부도 그렇게 기울어 있다 —
비율까지 고르게 만들면 이번엔 실제 로스터와 어긋난다.
"""

DEBUTS_PER_YEAR = {"_M": 3, "_F": 4}
"""해마다 데뷔시킬 가상 선수 수.

승급이 6년·15년이므로 한 기수는 유망주로 6년, 미드카드로 9년을 산다. 남자 3명이면
유망주 18명·미드카드 27명이 늘 차 있다는 계산이고, 실측도 그 근처다.

**여성부만 둘에서 넷으로 올렸다** (2026-08-10 사용자 지시 8번). 은퇴 나이를 42세로
내리자 실존 여성 선수가 남성부보다 훨씬 빨리 빠져나간다 — 데뷔 수를 그대로 두면
`MIN_POOL` 검증이 중반 구간에서 터진다. **가상 선수가 빨리 나오게 해 달라는 요청과
같은 방향이다.**
"""

FICTIONAL_MIDCARD_EVERY = 4
"""이만큼마다 한 명은 **미드카드로 데뷔**시킨다 — 다른 단체에서 온 즉시 전력이다.

전원을 유망주로 넣으면 실존 미드카드가 빠져나가는 10~15년 구간이 얇아진다.
"""


def fictional_members(
    taken: set[str],
) -> list[Row]:
    """가상 선수 명부. 해마다 정해진 수를 데뷔시킨다.

    **유망주는 육성에서 데뷔하고, 이적생은 메인에서 데뷔한다** (2026-08-12 사용자 결정).
    `FICTIONAL_MIDCARD_EVERY`마다 한 명씩 나오는 미드카드가 곧 "다른 단체에서 온 즉시
    전력"이라, 그들만 처음부터 메인 로스터에 선다. 나머지는 NXT를 거쳐 올라온다.
    """
    members: list[Row] = []
    slots: list[str] = []
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
            tier = "_MID" if made % FICTIONAL_MIDCARD_EVERY == 0 else "_LOW"
            retire = debut + FICTIONAL_CAREER_YEARS * WEEKS_PER_YEAR
            experience = 6 if tier == "_MID" else 0
            members.append(
                (
                    name,
                    gender,
                    tier,
                    debut,
                    retire,
                    experience,
                    None,
                    None,
                    0,
                    "",
                    len(slots),
                    # **가상 선수는 육성에서 올라온다** (§3-D95) — 그러지 않으면
                    # 10년차부터 NXT가 빈다(실측: 남성부 어퍼 0명). 이적생(_MID)은
                    # 다른 단체에서 온 즉시 전력이라 메인에서 데뷔한다(§3-D59).
                    tier == "_LOW",
                    # **성향은 안 정해져 있다** (§3-D95, 사용자 결정) — 데뷔할 때
                    # 굴려서 정하고, 그 뒤에도 뒤집힐 수 있다.
                    "None",
                )
            )
            slots.append(name)
            made += 1
    return members


def fictional_pool(taken: set[str]) -> dict[str, list[str]]:
    """가상 선수 이름 후보 **전부** (§3-D59).

    판마다 여기서 골라 쓴다 — 명부의 크기·데뷔·은퇴는 상수이고 **이름만 시드를 탄다.**
    실존 이름과 겹치는 조합은 뺀다(같은 세계에 같은 사람이 둘 있을 수 없다).
    """
    pools: dict[str, list[str]] = {}
    for gender in ("_M", "_F"):
        by_origin: list[tuple[int, list[str]]] = []
        for origin in NAME_ORIGINS:
            firsts = origin.male if gender == "_M" else origin.female
            pairs = [
                f"{last}{first}" if origin.surname_first else f"{first} {last}"
                for first in firsts
                for last in origin.last
                # **같은 글자가 겹치는 조합은 뺀다** — "서서연"처럼 성과 이름 첫
                # 글자가 같으면 읽을 때 말이 더듬는다.
                if not (origin.surname_first and first.startswith(last))
            ]
            # 중첩 루프 순서대로 쓰면 "… 크로스"가 연달아 데뷔한다. 이름 해시로 섞되
            # blake2b라 프로세스가 바뀌어도 순서가 같다 (도메인의 시드 규약과 같은 결).
            combos = sorted(
                pairs, key=lambda n: hashlib.blake2b(n.encode(), digest_size=8).digest()
            )
            by_origin.append((origin.share, [n for n in combos if n not in taken]))
        pools[gender] = _interleave(by_origin)
    return pools


def _interleave(groups: list[tuple[int, list[str]]]) -> list[str]:
    """출신별 목록을 비율대로 번갈아 엮는다 (2026-08-19 사용자 요청).

    **앞쪽 순서가 곧 데뷔 순서다** — `cast_for()`가 이 목록을 앞에서부터 꺼내 쓴다.
    출신별로 이어 붙이면 처음 서른 명이 전부 북미이고 일본 이름은 20년째에야 처음
    나온다. 한 바퀴마다 비율만큼 꺼내 **어느 구간을 잘라도 섞여 있게** 한다.
    """
    picked: list[str] = []
    cursors = [0] * len(groups)
    while True:
        before = len(picked)
        for index, (share, names) in enumerate(groups):
            end = min(cursors[index] + share, len(names))
            picked.extend(names[cursors[index] : end])
            cursors[index] = end
        if len(picked) == before:
            return picked


def build() -> list[Row]:
    """(한글명, 성별, 등급, 데뷔, 은퇴, 경력, 메인 브랜드, 바꾼 이름, 개명 주차, 스테이블).

    디비전 → 등급 순 정렬.
    """
    members: list[Row] = []
    stables = read_stables(CSV_PATH)
    ARSENALS.clear()
    for section, names in read_sections(CSV_PATH).items():
        if section not in SECTION_HOME:
            raise SystemExit(f"모르는 섹션 {section!r} — SECTION_HOME에 넣으세요")
        window = LATE_DEBUT_SECTIONS.get(section)
        for index, name in enumerate(names):
            gender = require(name, "gender")
            if gender not in GENDER_ALIAS:
                raise SystemExit(f"{name}: 모르는 성별 {gender!r}")
            card = CARD_ALIAS.get(require(name, "card"))
            if card is None:
                raise SystemExit(f"{name}: 모르는 위상 {given(name, 'card')!r}")
            # **성향은 비어도 된다** — Evolve와 명단 밖 사람은 콜업 때 굴린다(§3-D95).
            raw_align = given(name, "alignment")
            alignment = ALIGN_ALIAS.get(raw_align, "None") if raw_align else "None"
            if raw_align and alignment == "None":
                raise SystemExit(f"{name}: 모르는 성향 {raw_align!r}")
            if window is None:
                debut = 0
            else:
                low, high = window
                debut = (low + index % (high - low + 1)) * WEEKS_PER_YEAR
            age = age_of(name)
            korean, renamed = names_of(require(name, "korean_name"))
            # **활동명을 바꿔도 기술은 그대로다** (§3-D54) — 두 이름이 같은 무기고를
            # 가리킨다. 이름으로 찾는 자리라 한쪽만 넣으면 개명 뒤 조용히 비어 버린다.
            arsenal = arsenal_of(name)
            if any(arsenal):
                ARSENALS[korean] = arsenal
                if renamed:
                    ARSENALS[renamed] = arsenal
            members.append(
                (
                    korean,
                    GENDER_ALIAS[gender],
                    card,
                    debut,
                    debut + retire_week_for(name, age, gender),
                    experience_of(age),
                    SECTION_HOME[section],
                    renamed,
                    rename_week_for(korean) if renamed else 0,
                    stables.get(name, ""),
                    -1,
                    section in DEVELOPS,
                    alignment,
                )
            )

    members += fictional_members({m[0] for m in members})

    order = {"_UP": 0, "_MID": 1, "_LOW": 2}
    members.sort(key=lambda m: (m[1] != "_M", m[3], order[m[2]], m[0]))
    return _assign_homes(members)


def _assign_homes(
    members: list[Row],
) -> list[Row]:
    """아직 갈 곳이 없는 사람에게 메인 브랜드를 준다 — **두 브랜드에 번갈아**.

    디비전마다 따로 돌린다. 한 줄로 돌리면 남성부가 홀수로 끝나는 해에 여성부가
    통째로 한쪽으로 쏠린다.
    """
    turn: dict[str, int] = {}
    filled: list[Row] = []
    for (
        name,
        gender,
        tier,
        debut,
        retire,
        experience,
        home,
        renamed,
        rename_at,
        stable,
        slot,
        develops,
        alignment,
    ) in members:
        if home is None:
            index = turn.get(gender, 0)
            turn[gender] = index + 1
            home = "_RAW" if index % 2 == 0 else "_SD"
        filled.append(
            (
                name,
                gender,
                tier,
                debut,
                retire,
                experience,
                home,
                renamed,
                rename_at,
                stable,
                slot,
                develops,
                alignment,
            )
        )
    return filled


def render(members: list[Row], pools: dict[str, list[str]]) -> str:
    pool_lines = "\n".join(
        f"    {alias}: (\n"
        + "".join(f'        "{name}",\n' for name in pools[alias])
        + "    ),"
        for alias in ("_M", "_F")
    )
    lines: list[str] = []
    seen: tuple[str, int] | None = None
    for (
        name,
        gender,
        tier,
        debut,
        retire,
        experience,
        home,
        renamed,
        rename_at,
        stable,
        slot,
        develops,
        alignment,
    ) in members:
        mark = (gender, debut)
        if mark != seen:
            seen = mark
            division = "남성부" if gender == "_M" else "여성부"
            when = "0주차 명부" if debut == 0 else f"{debut // WEEKS_PER_YEAR}년차 데뷔"
            title = f"{division} · {when}"
            lines.append(f"    # ── {title} " + "─" * max(1, 40 - len(title)))
        escaped = name.replace('"', '\\"')
        retire_arg = "None" if retire is None else str(retire)
        tail = "" if renamed is None else f', "{renamed}", {rename_at}'
        if slot >= 0:
            tail = (tail or ", None, 0") + f", {slot}"
        elif stable:
            tail = (tail or ", None, 0") + f', -1, "{stable}"'
        # **새 칸 둘은 키워드로 붙인다** (§3-D95). 자리 인자로 이으면 앞의 선택적
        # 칸(개명·슬롯·스테이블)을 전부 채워야 해서, 한 줄이 두 배로 길어진다.
        if develops:
            tail += ", develops=True"
        if alignment != "None":
            tail += f", alignment={alignment}"
        lines.append(
            f'    RosterMember("{escaped}", {gender}, {tier}, '
            f"{debut}, {retire_arg}, {experience}, {home}{tail}),"
        )
    body = HEADER.replace("{POOL}", pool_lines) + "\n".join(lines) + "\n"
    return body + (
        FOOTER.replace("{SIGNATURES}", _arsenal_lines(0)).replace(
            "{FINISHERS}", _arsenal_lines(1)
        )
    )


LINE_LIMIT = 88
"""찍어 내는 줄의 길이 한도. **포매터와 같은 값이다** — 넘으면 `ruff format`이 다시
쪼개고, 그러면 생성물이 생성기와 어긋나 다음 실행마다 diff가 난다."""


def _literal(move: str) -> str:
    """따옴표를 escape한 문자열 리터럴.

    **`"예스!" 킥스`처럼 이름 안에 따옴표를 든 기술이 실제로 있다.** 그대로 찍으면
    생성물이 문법 오류라 임포트조차 안 된다.
    """
    escaped = move.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _arsenal_lines(index: int) -> str:
    """무기고 한 벌을 사전 리터럴로. 이름 순으로 찍어 **판마다 같은 파일**이 나온다."""
    lines = []
    for name in sorted(ARSENALS):
        moves = ARSENALS[name][index]
        if not moves:
            continue
        quoted = [_literal(move) for move in moves]
        tail = "," if len(moves) == 1 else ""
        one_line = f'    "{name}": ({", ".join(quoted)}{tail}),\n'
        if len(one_line.rstrip("\n")) <= LINE_LIMIT:
            lines.append(one_line)
            continue
        # 포매터가 쪼개는 모양 그대로 — 한 줄에 하나씩, 끝에 쉼표.
        listed = "".join(f"        {move},\n" for move in quoted)
        lines.append(f'    "{name}": (\n{listed}    ),\n')
    return "".join(lines)


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


def preset_country(birth_place: str, billed_from: str) -> str:
    """출생지·소개지에서 국가 코드. 목록 밖이면 **기타**로 뭉친다 (2026-08-07 사용자 결정)."""
    for source in (birth_place, billed_from):
        token = source.split(",")[-1].strip()
        if token in COUNTRY_BY_PLACE:
            return COUNTRY_BY_PLACE[token]
    return "OTHER"


def build_presets() -> list[tuple[str, str, str, str]]:
    """(한국어 이름, 성별, 플레이스타일, 국가코드). 실존 선수만 대상이다."""
    raw = {
        row["name"].strip(): row
        for row in csv.DictReader(io.StringIO(CSV_PATH.read_text(encoding="utf-8-sig")))
        if (row.get("name") or "").strip()
    }
    presets: list[tuple[str, str, str, str]] = []
    for names in read_sections(CSV_PATH).values():
        for name in names:
            row = raw.get(name, {})
            first, renamed = names_of(require(name, "korean_name"))
            presets.append(
                (
                    # "○○를 바탕으로"는 **알아보는 이름**이어야 한다 — 개명 전 링네임보다
                    # 본래 활동명이 그 자리에 맞는다 (§3-D54).
                    renamed or first,
                    require(name, "gender").upper(),
                    require(name, "play_style").upper(),
                    preset_country(
                        (row.get("birth_place") or ""),
                        (row.get("billed_from") or ""),
                    ),
                )
            )
    return presets


PRESET_HEADER = '''"""캐릭터 생성 프리셋 — 실존 선수를 바탕으로 내 선수를 만든다 (하네스 §3-D10-1).

**이 파일은 생성물이다.** `scripts/generate_roster.py`가 로스터와 함께 찍어 낸다.

프리셋을 고르면 그 선수의 데이터가 **기본값으로** 들어오고, 원하는 값은 덮어쓸 수 있다
(2026-08-07 사용자 요청). 이름은 언제나 사용자가 정한다 — 실존 인물의 이름을 그대로
쓰는 캐릭터를 만들 수 있게 두면 §3-D13의 고지가 무의미해진다.

플레이스타일은 로스터 CSV의 `style` 첫 값이다 — **추정이 아니라 사용자가 적은 값**
(2026-08-10). 곁들이는 유형(`sub_styles`)은 프리셋이 물려주지 않는다: 캐릭터의
플레이스타일은 하나이고, 나머지는 그 선수를 설명하는 말이지 게임의 값이 아니다.

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

    global GAME_DATA  # noqa: PLW0603 - 파일 하나를 읽어 모듈 전역에 둔다
    GAME_DATA = read_game_data()
    blank = [
        (name, field)
        for name, row in GAME_DATA.items()
        for field in REQUIRED_FIELDS
        if not row.get(field)
    ]
    if blank:
        raise SystemExit(f"{GAME_DATA_PATH.name}: 비어 있는 칸 {blank}")
    print(f"게임 데이터 {len(GAME_DATA)}행 — 필수 칸 전부 채워짐")
    no_birth = [n for n, r in GAME_DATA.items() if not r.get("birth_date")]
    if no_birth:
        print(
            f"  생년월일 미공개 {len(no_birth)}명 — {DEFAULT_AGE}세로 셉니다: {no_birth}"
        )

    members = build()
    counts: dict[tuple[str, str], int] = {}
    homes: dict[str, int] = {}
    for _, gender, tier, _, _, _, home, *_rest in members:
        counts[(gender, tier)] = counts.get((gender, tier), 0) + 1
        homes[home or "?"] = homes.get(home or "?", 0) + 1
    real = sum(1 for m in members if m[3] == 0)

    print(f"원본: {CSV_PATH.name}")
    print(f"총 {len(members)}명 — 0주차 명부 {real} · 나중 데뷔 {len(members) - real}")
    for gender in ("_M", "_F"):
        row = " · ".join(
            f"{tier} {counts.get((gender, tier), 0):>3}"
            for tier in ("_UP", "_MID", "_LOW")
        )
        print(f"  {'남성부' if gender == '_M' else '여성부'} 시작 등급: {row}")
    print(
        "  콜업되면 갈 메인 브랜드:",
        " · ".join(f"{k} {v}" for k, v in sorted(homes.items())),
    )

    presets = build_presets()
    styles: dict[str, int] = {}
    for _, _, style, _ in presets:
        styles[style] = styles.get(style, 0) + 1
    other = sum(1 for _, _, _, c in presets if c == "OTHER")
    print(f"프리셋 {len(presets)}개 · 기타 국가 {other}명")
    print("  스타일:", " · ".join(f"{k} {v}" for k, v in sorted(styles.items())))

    if args.write:
        pools = fictional_pool({m[0] for m in members if m[10] < 0})
        OUT_PATH.write_text(render(members, pools), encoding="utf-8")
        PRESET_OUT_PATH.write_text(render_presets(presets), encoding="utf-8")
        print(f"\n{OUT_PATH.relative_to(APP_DIR.parents[1])} 갱신")
        print(f"{PRESET_OUT_PATH.relative_to(APP_DIR.parents[1])} 갱신")
    else:
        print("\n(미리보기 — 쓰려면 --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
