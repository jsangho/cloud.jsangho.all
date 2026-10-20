"""**장난감** 경기 시뮬레이터. 두 선수를 받아 승자를 뽑는다.

## 이것은 예측이 아니다

실제 예측은 AI Lab(`ai_prediction_interactor`)이 하고, 거기에는 서사·루머·배당
세 축과 누수 탐지·재현 검사가 붙어 있다. 여기 있는 것은 **공식 하나와 난수**다.
그래서 라우터도 `/sandbox` 아래 따로 두고, 화면이 "장난감" 이라고 말한다.
그 둘이 유일한 방어선이다 — 숫자만 떼어 놓으면 진짜처럼 보인다.

## 승률을 쓰지 않는 이유

쓰고 싶었지만 **표본이 없다.** 2026-10-20 실측 — 현 로스터 169명의 '결과 있는
경기' 출전 수가 0경기 80명 · 1경기 34명 · 2경기 23명이고 **5경기 이상이 11명**
뿐이다. 그 승률로 세우면 `1승 0패` 가 `1승 1패` 를 이기는 잡음이 된다.

그래서 쓰는 것은 **전원이 가진 두 칸**이다.

    타이틀 획득 수   66명이 1회 이상 (최대 21회) · 103명은 0회
    나이            169/169 (생일 전원 보유)

103명이 0회라 신인끼리는 나이만으로 갈린다. **그게 이 장난감의 한계이고 숨기지
않는다** — 응답이 두 입력을 그대로 돌려주므로 화면이 적을 수 있다.

## 안 만드는 것 (이 목록이 이 파일의 절반이다)

이전 커리어 시뮬레이터는 38,326줄·테스트 2,062개로 불어나 **버려졌다**
(`f7a678f`, 2026-09-28). 불어난 원인은 기능이 아니라 **저장**이었다 —
`career_runs` 테이블이 생기자 세이브·불러오기·버전 호환·진행도·트로피가 전부
따라왔고, 거기에 이벤트 카드 덱 21개가 얹혔다.

그래서 여기에 **없고, 더하지 않는다**:

- **저장** — DB도 세션도 쓰지 않는다. 순수 함수 하나다
- 세이브/불러오기 · 시즌 · 커리어 진행 · 부상 · 계약 · 스태미나 · 카드 덱
- 경기 흐름(무브 교환) · 관중 반응 · 등급 평가

더하고 싶은 것이 생기면 **이 목록에 왜 없는지 먼저 적는다.**
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

#: 확률이 0·1 로 가지 못하게 누르는 계수. `0.7` 이면 결과가 **15%~85%** 안에 머문다.
#: 업셋이 없는 시뮬레이터는 돌릴 이유가 없고, 100% 를 말하는 장난감은 거짓이다.
UPSET_DAMPING = 0.7

#: 나이 보정의 정점. 이 나이에서 0이고 멀어질수록 음수가 된다.
PEAK_AGE = 27

#: 나이 보정의 완만함. 숫자가 크면 나이가 덜 중요해진다.
#:
#: **의도: 정점에서 14년 벗어나면 타이틀 약 1회 분량의 손해.** `(41-27)^2 / 280
#: = 0.70` 이고 `log1p(1) = 0.693` 이라 거의 같다. 즉 **커리어가 나이를 이긴다.**
#:
#: 처음에 `100` 으로 뒀다가 고쳤다. 그러면 41세 벌점이 `1.96` = 타이틀 **6.1회**
#: 분량이 되어, 10회 챔피언(41세)이 2회 신인(21세)에게 언더독이 됐다(실측
#: p=0.448). 장난감이라도 그건 재미가 아니라 고장으로 읽힌다.
AGE_SPREAD = 280.0


@dataclass(frozen=True)
class Contender:
    """시뮬레이터가 보는 선수. **이 세 칸뿐이다.**"""

    name: str
    #: 통산 타이틀 획득 수. 모르면 0.
    titles: int
    #: 나이. 생일을 모르면 `None` — 그때는 나이 보정이 0이다.
    age: int | None


@dataclass(frozen=True)
class SimVerdict:
    """결과. **입력을 그대로 돌려준다** — 화면이 근거를 적을 수 있어야 한다."""

    winner: str
    #: `a` 가 이길 확률. `0.15`~`0.85`.
    probability_a: float
    score_a: float
    score_b: float
    #: 뽑기에 쓴 값(0~1). 같은 쌍이면 항상 같다.
    roll: float


def contender_score(contender: Contender) -> float:
    """타이틀과 나이로 만든 점수. **단조롭고 경계가 없다.**

    타이틀은 `log1p` 로 누른다 — 21회가 1회의 21배로 세면 베테랑이 무조건 이긴다.
    `log1p(21) ≈ 3.09`, `log1p(1) ≈ 0.69` 이라 4.5배쯤 차이다.
    """
    score = math.log1p(max(contender.titles, 0))
    if contender.age is not None:
        score -= ((contender.age - PEAK_AGE) ** 2) / AGE_SPREAD
    return score


def _canonical_pair(a: str, b: str) -> tuple[str, str]:
    """두 이름을 **항상 같은 순서**로 눕힌다. 시드와 뽑기의 기준이 된다."""
    first, second = sorted((a.strip().casefold(), b.strip().casefold()))
    return first, second


def _roll(a: str, b: str) -> float:
    """두 이름에서 0~1 을 만든다. **순서가 바뀌어도 같은 값**이다.

    `hash()` 를 쓰면 안 된다 — 파이썬 문자열 해시는 프로세스마다 달라지므로
    (`PYTHONHASHSEED`) 같은 쌍이 재기동 뒤 다른 승자를 낸다. 그러면 "또 돌려 봐"
    가 되고 테스트도 못 쓴다. 그래서 `sha256` 으로 고정한다.
    """
    key = "\x00".join(_canonical_pair(a, b))
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def simulate(a: Contender, b: Contender) -> SimVerdict:
    """승자를 뽑는다. **같은 쌍이면 항상 같은 결과다**(시드가 이름에서 나온다).

    확률은 두 점수 차의 로지스틱이고, `UPSET_DAMPING` 으로 0.5 쪽으로 누른다.
    뽑기는 `_roll` 이 주는 값과의 비교다 — 확률이 70% 라도 30% 는 진다.
    """
    score_a = contender_score(a)
    score_b = contender_score(b)
    skill = 1.0 / (1.0 + math.exp(-(score_a - score_b)))
    probability_a = 0.5 + UPSET_DAMPING * (skill - 0.5)

    roll = _roll(a.name, b.name)
    # **뽑기는 정본 순서로 한다.** `roll < probability_a` 로 바로 비교하면 같은 두
    # 선수인데 인수 순서만 바꿔도 승자가 뒤집힌다(실측: roll 0.252 · p_a 0.547 일 때
    # `(a,b)` 는 a 가, `(b,a)` 는 b 가 이겼다). 확률은 대칭인데 **부등호가 대칭이
    # 아니라서** 생기는 일이라, 비교 기준을 이름 정렬로 고정한다.
    first, _second = _canonical_pair(a.name, b.name)
    a_is_first = a.name.strip().casefold() == first
    probability_first = probability_a if a_is_first else 1.0 - probability_a
    first_wins = roll < probability_first
    winner = a.name if first_wins == a_is_first else b.name
    return SimVerdict(
        winner=winner,
        probability_a=probability_a,
        score_a=score_a,
        score_b=score_b,
        roll=roll,
    )
