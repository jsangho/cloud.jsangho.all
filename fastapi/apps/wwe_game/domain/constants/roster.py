"""라이벌·챔피언으로 쓸 선수 명부 — **시간에 따라 바뀐다** (하네스 §3-D13).

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

from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache

from wwe_game.domain.constants.career_clock import CAREER_WEEKS, WEEKS_PER_YEAR
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import Brand
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
    home_brand: Brand = Brand.RAW
    """콜업된 뒤 설 메인 브랜드 (§3-D53). **지금 있는 브랜드가 아니다** — 그건
    `brand_at()`이 등급에서 읽는다.
    """
    renamed_to: str | None = None
    """바꾼 뒤의 활동명 (§3-D54). 안 바꾸면 None이다."""
    rename_week: int = 0
    """이 주차부터 `renamed_to`로 불린다. `renamed_to`가 있을 때만 뜻이 있다."""

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
_RAW, _SD = Brand.RAW, Brand.SMACKDOWN

ROSTER: tuple[RosterMember, ...] = (
    # ── 남성부 · 0주차 명부 ────────────────────────────
    RosterMember("CM 펑크", _M, _ME, 0, 156, 25, _SD),
    RosterMember("LA 나이트", _M, _ME, 0, 260, 21, _RAW),
    RosterMember("군터", _M, _ME, 0, 468, 17, _SD),
    RosterMember("데미안 프리스트", _M, _ME, 0, 260, 21, _SD),
    RosterMember("드류 맥킨타이어", _M, _ME, 0, 364, 19, _SD),
    RosterMember("랜디 오턴", _M, _ME, 0, 156, 24, _SD),
    RosterMember("레이 미스테리오", _M, _ME, 0, 104, 29, _RAW),
    RosterMember("로건 폴", _M, _ME, 0, 884, 9, _RAW),
    RosterMember("로만 레인즈", _M, _ME, 0, 364, 19, _RAW),
    RosterMember("브록 레스너", _M, _ME, 0, 156, 27, _RAW),
    RosterMember("브론 브레이커", _M, _ME, 0, 1040, 6, _RAW),
    RosterMember("브론슨 리드", _M, _ME, 0, 572, 15, _RAW),
    RosterMember("새미 제인", _M, _ME, 0, 312, 20, _SD),
    RosterMember("세스 롤린스", _M, _ME, 0, 416, 18, _RAW),
    RosterMember("솔로 시코아", _M, _ME, 0, 780, 11, _SD),
    RosterMember("제이 우소", _M, _ME, 0, 416, 18, _RAW),
    RosterMember("제이콥 파투", _M, _ME, 0, 728, 12, _RAW),
    RosterMember("케빈 오웬스", _M, _ME, 0, 312, 20, _SD),
    RosterMember("코디 로즈", _M, _ME, 0, 364, 19, _SD),
    RosterMember("핀 밸러", _M, _ME, 0, 156, 23, _SD),
    RosterMember("JD 맥도나", _M, _MC, 0, 624, 14, _RAW),
    RosterMember("R-트루스", _M, _MC, 0, 104, 32, _SD),
    RosterMember("그레이슨 월러", _M, _MC, 0, 624, 14, _RAW),
    RosterMember("나카무라 신스케", _M, _MC, 0, 156, 24, _SD),
    RosterMember("네이선 프레이저", _M, _MC, 0, 1040, 6, _SD),
    RosterMember("댄 하우젠", _M, _MC, 0, 624, 14, _SD),
    RosterMember("도미닉 미스테리오", _M, _MC, 0, 988, 7, _RAW),
    RosterMember("드래곤 리", _M, _MC, 0, 884, 9, _RAW),
    RosterMember("라요 아메리카노", _M, _MC, 0, 832, 10, _RAW, "피트 던", 156),
    RosterMember("레이 페닉스", _M, _MC, 0, 676, 13, _SD),
    RosterMember("로이스 키스", _M, _MC, 0, 364, 19, _SD),
    RosterMember("루세프", _M, _MC, 0, 364, 19, _RAW),
    RosterMember("리키 세인츠", _M, _MC, 0, 624, 14, _SD),
    RosterMember("맷 카도나", _M, _MC, 0, 364, 19, _SD),
    RosterMember("몬테즈 포드", _M, _MC, 0, 624, 14, _RAW),
    RosterMember("미즈", _M, _MC, 0, 156, 23, _SD),
    RosterMember("배런 코빈", _M, _MC, 0, 364, 19, _SD),
    RosterMember("베르토", _M, _MC, 0, 936, 8, _SD),
    RosterMember("브라보 아메리카노", _M, _MC, 0, 988, 7, _RAW, "타일러 베이트", 208),
    RosterMember("브루투스 크리드", _M, _MC, 0, 936, 8, _RAW),
    RosterMember("빅 캐스", _M, _MC, 0, 416, 18, _RAW),
    RosterMember("아이바", _M, _MC, 0, 312, 20, _RAW),
    RosterMember("아키라 토자와", _M, _MC, 0, 364, 19, _RAW),
    RosterMember("안젤로 도킨스", _M, _MC, 0, 624, 14, _RAW),
    RosterMember("액시옴", _M, _MC, 0, 988, 7, _SD),
    RosterMember("에단 페이지", _M, _MC, 0, 624, 14, _RAW),
    RosterMember("에릭", _M, _MC, 0, 364, 19, _RAW),
    RosterMember("엔젤", _M, _MC, 0, 780, 11, _SD),
    RosterMember(
        "엘 그란데 아메리카노", _M, _MC, 0, 676, 13, _RAW, "루드비히 카이저", 156
    ),
    RosterMember("엘튼 프린스", _M, _MC, 0, 988, 7, _SD),
    RosterMember("오모스", _M, _MC, 0, 832, 10, _RAW),
    RosterMember("오바 페미", _M, _MC, 0, 1040, 6, _RAW),
    RosterMember("오스틴 씨어리", _M, _MC, 0, 988, 7, _RAW),
    RosterMember("오티스", _M, _MC, 0, 728, 12, _RAW),
    RosterMember("일리야 드라구노프", _M, _MC, 0, 832, 10, _SD),
    RosterMember("쟈니 가르가노", _M, _MC, 0, 468, 17, _SD),
    RosterMember("조 헨드리", _M, _MC, 0, 520, 16, _RAW),
    RosterMember("줄리우스 크리드", _M, _MC, 0, 884, 9, _RAW),
    RosterMember("지미 우소", _M, _MC, 0, 416, 18, _RAW),
    RosterMember("지본 에반스", _M, _MC, 0, 1352, 0, _RAW),
    RosterMember("채드 게이블", _M, _MC, 0, 624, 14, _RAW),
    RosterMember("카멜로 헤이즈", _M, _MC, 0, 832, 10, _SD),
    RosterMember("크루즈 델 토로", _M, _MC, 0, 728, 12, _RAW),
    RosterMember("킷 윌슨", _M, _MC, 0, 832, 10, _SD),
    RosterMember("타마 통가", _M, _MC, 0, 260, 21, _SD),
    RosterMember("탈라 통가", _M, _MC, 0, 676, 13, _SD),
    RosterMember("트릭 윌리엄스", _M, _MC, 0, 832, 10, _SD),
    RosterMember("펜타", _M, _MC, 0, 364, 19, _RAW),
    RosterMember("호아킨 와일드", _M, _MC, 0, 468, 17, _RAW),
    RosterMember("EK 프로스퍼", _M, _P, 0, 1196, 3, _SD),
    RosterMember("나라쿠", _M, _P, 0, 468, 17, _RAW),
    RosterMember("노암 다르", _M, _P, 0, 780, 11, _SD),
    RosterMember("니코 밴스", _M, _P, 0, 1092, 5, _RAW),
    RosterMember("도리안 반 덕스", _M, _P, 0, 936, 8, _SD),
    RosterMember("디온 레녹스", _M, _P, 0, 1040, 6, _RAW),
    RosterMember("렉시스 킹", _M, _P, 0, 832, 10, _SD),
    RosterMember("로메오 모레노", _M, _P, 0, 1248, 2, _RAW),
    RosterMember("루시엔 프라이스", _M, _P, 0, 988, 7, _SD),
    RosterMember("리키 스모크스", _M, _P, 0, 1144, 4, _RAW),
    RosterMember("린세 도라도", _M, _P, 0, 468, 17, _SD),
    RosterMember("마일스 본", _M, _P, 0, 1092, 5, _RAW),
    RosterMember("메이슨 룩", _M, _P, 0, 988, 7, _SD),
    RosterMember("브래드 베일러", _M, _P, 0, 1404, 0, _RAW),
    RosterMember("브롱코 니마", _M, _P, 0, 1248, 2, _SD),
    RosterMember("브룩스 젠슨", _M, _P, 0, 1248, 2, _RAW),
    RosterMember("샤일로 힐", _M, _P, 0, 1092, 5, _SD),
    RosterMember("세이콴 슈거스", _M, _P, 0, 1144, 4, _RAW),
    RosterMember("숀 레거시", _M, _P, 0, 936, 8, _SD),
    RosterMember("숀 스피어스", _M, _P, 0, 156, 23, _RAW),
    RosterMember("엘리오 르플뢰르", _M, _P, 0, 1092, 5, _SD),
    RosterMember("오시리스 그리핀", _M, _P, 0, 1040, 6, _RAW),
    RosterMember("유라이어 코너스", _M, _P, 0, 1248, 2, _SD),
    RosterMember("재스퍼 트로이", _M, _P, 0, 1040, 6, _RAW),
    RosterMember("잭슨 드레이크", _M, _P, 0, 1352, 0, _SD),
    RosterMember("조쉬 브릭스", _M, _P, 0, 780, 11, _RAW),
    RosterMember("찰리 뎀프시", _M, _P, 0, 988, 7, _SD),
    RosterMember("채닝 로렌조", _M, _P, 0, 988, 7, _RAW),
    RosterMember("캠 헨드릭스", _M, _P, 0, 988, 7, _SD),
    RosterMember("커틀러 제임스", _M, _P, 0, 1196, 3, _RAW),
    RosterMember("케일 딕슨", _M, _P, 0, 1040, 6, _SD),
    RosterMember("크루즈 몬타나", _M, _P, 0, 676, 13, _RAW),
    RosterMember("키아누 카버", _M, _P, 0, 1092, 5, _SD),
    RosterMember("탱크 레저", _M, _P, 0, 1144, 4, _RAW),
    RosterMember("테비언 하이츠", _M, _P, 0, 988, 7, _SD),
    RosterMember("테이트 와일더", _M, _P, 0, 1040, 6, _RAW),
    RosterMember("토니 디안젤로", _M, _P, 0, 884, 9, _SD),
    RosterMember("트리스탄 앤젤스", _M, _P, 0, 1300, 1, _RAW),
    RosterMember("행크 워커", _M, _P, 0, 1040, 6, _SD),
    # ── 남성부 · 1년차 데뷔 ────────────────────────────
    RosterMember("디온 스파크", _M, _MC, 52, 1300, 6, _RAW),
    RosterMember("아론 루크", _M, _P, 52, 988, 8, _SD),
    RosterMember("카일 머서", _M, _P, 52, 1300, 0, _RAW),
    RosterMember("케이든 하트", _M, _P, 52, 1300, 0, _SD),
    RosterMember("할렘 루이스", _M, _P, 52, 1196, 4, _RAW),
    # ── 남성부 · 2년차 데뷔 ────────────────────────────
    RosterMember("오스틴 파울러", _M, _MC, 104, 1352, 6, _SD),
    RosterMember("놀란 폭스", _M, _P, 104, 1352, 0, _RAW),
    RosterMember("브랙스턴 콜", _M, _P, 104, 1248, 4, _SD),
    RosterMember("브랜든 서머스", _M, _P, 104, 1352, 0, _RAW),
    RosterMember("잇츠 갤", _M, _P, 104, 1352, 2, _SD),
    # ── 남성부 · 3년차 데뷔 ────────────────────────────
    RosterMember("디온 프로스트", _M, _MC, 156, 1404, 6, _RAW),
    RosterMember("데본 서머스", _M, _P, 156, 1404, 0, _SD),
    RosterMember("자비어 리버스", _M, _P, 156, 1404, 0, _RAW),
    RosterMember("잭스 프레슬리", _M, _P, 156, 1300, 4, _SD),
    RosterMember("카푸치노 존스", _M, _P, 156, 1404, 2, _RAW),
    # ── 남성부 · 4년차 데뷔 ────────────────────────────
    RosterMember("스타보이 찰리", _M, _P, 208, 1508, 1, _SD),
    RosterMember("실라스 폭스", _M, _P, 208, 1456, 0, _RAW),
    RosterMember("웨이드 헌터", _M, _P, 208, 1456, 0, _SD),
    RosterMember("일라이자 홀리필드", _M, _P, 208, 1248, 6, _RAW),
    RosterMember("트로이 프라이스", _M, _P, 208, 1456, 0, _SD),
    # ── 남성부 · 5년차 데뷔 ────────────────────────────
    RosterMember("브라이스 폭스", _M, _MC, 260, 1508, 6, _RAW),
    RosterMember("네이트 리버스", _M, _P, 260, 1508, 0, _SD),
    RosterMember("디온 라이커", _M, _P, 260, 1508, 0, _RAW),
    # ── 남성부 · 6년차 데뷔 ────────────────────────────
    RosterMember("케이든 벨", _M, _MC, 312, 1560, 6, _SD),
    RosterMember("웨이드 서머스", _M, _P, 312, 1560, 0, _RAW),
    RosterMember("카일 바이퍼", _M, _P, 312, 1560, 0, _SD),
    # ── 남성부 · 7년차 데뷔 ────────────────────────────
    RosterMember("마커스 블레이즈", _M, _MC, 364, 1612, 6, _RAW),
    RosterMember("오스틴 브릭스", _M, _P, 364, 1612, 0, _SD),
    RosterMember("트로이 폭스", _M, _P, 364, 1612, 0, _RAW),
    # ── 남성부 · 8년차 데뷔 ────────────────────────────
    RosterMember("브랜든 헤이즈", _M, _P, 416, 1664, 0, _SD),
    RosterMember("웨이드 스파크", _M, _P, 416, 1664, 0, _RAW),
    RosterMember("케이든 헌터", _M, _P, 416, 1664, 0, _SD),
    # ── 남성부 · 9년차 데뷔 ────────────────────────────
    RosterMember("오스틴 셰이드", _M, _MC, 468, 1716, 6, _RAW),
    RosterMember("라이언 스파크", _M, _P, 468, 1716, 0, _SD),
    RosterMember("코너 하트", _M, _P, 468, 1716, 0, _RAW),
    # ── 남성부 · 10년차 데뷔 ───────────────────────────
    RosterMember("타이슨 윈터스", _M, _MC, 520, 1768, 6, _SD),
    RosterMember("데릭 바이퍼", _M, _P, 520, 1768, 0, _RAW),
    RosterMember("타이슨 서머스", _M, _P, 520, 1768, 0, _SD),
    # ── 남성부 · 11년차 데뷔 ───────────────────────────
    RosterMember("알렉 프로스트", _M, _MC, 572, 1820, 6, _RAW),
    RosterMember("이선 리드", _M, _P, 572, 1820, 0, _SD),
    RosterMember("잭슨 브릭스", _M, _P, 572, 1820, 0, _RAW),
    # ── 남성부 · 12년차 데뷔 ───────────────────────────
    RosterMember("개럿 스톰", _M, _P, 624, 1872, 0, _SD),
    RosterMember("놀란 윈터스", _M, _P, 624, 1872, 0, _RAW),
    RosterMember("자비어 스틸", _M, _P, 624, 1872, 0, _SD),
    # ── 남성부 · 13년차 데뷔 ───────────────────────────
    RosterMember("타이슨 바이퍼", _M, _MC, 676, 1924, 6, _RAW),
    RosterMember("루커스 라이커", _M, _P, 676, 1924, 0, _SD),
    RosterMember("카일 케이지", _M, _P, 676, 1924, 0, _RAW),
    # ── 남성부 · 14년차 데뷔 ───────────────────────────
    RosterMember("알렉 퀸", _M, _MC, 728, 1976, 6, _SD),
    RosterMember("카터 윈터스", _M, _P, 728, 1976, 0, _RAW),
    RosterMember("코너 셰이드", _M, _P, 728, 1976, 0, _SD),
    # ── 남성부 · 15년차 데뷔 ───────────────────────────
    RosterMember("메이슨 크로스", _M, _MC, 780, 2028, 6, _RAW),
    RosterMember("자비어 헌터", _M, _P, 780, 2028, 0, _SD),
    RosterMember("콜 스톰", _M, _P, 780, 2028, 0, _RAW),
    # ── 남성부 · 16년차 데뷔 ───────────────────────────
    RosterMember("라이언 라이커", _M, _P, 832, 2080, 0, _SD),
    RosterMember("카일 헌터", _M, _P, 832, 2080, 0, _RAW),
    RosterMember("트로이 라이커", _M, _P, 832, 2080, 0, _SD),
    # ── 남성부 · 17년차 데뷔 ───────────────────────────
    RosterMember("실라스 블레이즈", _M, _MC, 884, 2132, 6, _RAW),
    RosterMember("마커스 스톰", _M, _P, 884, 2132, 0, _SD),
    RosterMember("카터 바이퍼", _M, _P, 884, 2132, 0, _RAW),
    # ── 남성부 · 18년차 데뷔 ───────────────────────────
    RosterMember("브레이든 스톤", _M, _MC, 936, 2184, 6, _SD),
    RosterMember("브레이든 리드", _M, _P, 936, 2184, 0, _RAW),
    RosterMember("오스틴 크로스", _M, _P, 936, 2184, 0, _SD),
    # ── 남성부 · 19년차 데뷔 ───────────────────────────
    RosterMember("트로이 나이트", _M, _MC, 988, 2236, 6, _RAW),
    RosterMember("이선 세이지", _M, _P, 988, 2236, 0, _SD),
    RosterMember("이선 크로스", _M, _P, 988, 2236, 0, _RAW),
    # ── 남성부 · 20년차 데뷔 ───────────────────────────
    RosterMember("놀란 레인", _M, _P, 1040, 2288, 0, _SD),
    RosterMember("알렉 셰이드", _M, _P, 1040, 2288, 0, _RAW),
    RosterMember("콜 나이트", _M, _P, 1040, 2288, 0, _SD),
    # ── 남성부 · 21년차 데뷔 ───────────────────────────
    RosterMember("마커스 나이트", _M, _MC, 1092, 2340, 6, _RAW),
    RosterMember("데본 파울러", _M, _P, 1092, 2340, 0, _SD),
    RosterMember("타이슨 리드", _M, _P, 1092, 2340, 0, _RAW),
    # ── 남성부 · 22년차 데뷔 ───────────────────────────
    RosterMember("브라이스 퀸", _M, _MC, 1144, 2392, 6, _SD),
    RosterMember("놀란 벨", _M, _P, 1144, 2392, 0, _RAW),
    RosterMember("콜 헌터", _M, _P, 1144, 2392, 0, _SD),
    # ── 남성부 · 23년차 데뷔 ───────────────────────────
    RosterMember("카일 리버스", _M, _MC, 1196, 2444, 6, _RAW),
    RosterMember("제러드 하트", _M, _P, 1196, 2444, 0, _SD),
    RosterMember("코너 스톰", _M, _P, 1196, 2444, 0, _RAW),
    # ── 남성부 · 24년차 데뷔 ───────────────────────────
    RosterMember("개럿 레인", _M, _P, 1248, 2496, 0, _SD),
    RosterMember("제이든 세이지", _M, _P, 1248, 2496, 0, _RAW),
    RosterMember("카터 브릭스", _M, _P, 1248, 2496, 0, _SD),
    # ── 남성부 · 25년차 데뷔 ───────────────────────────
    RosterMember("데본 울프", _M, _MC, 1300, 2548, 6, _RAW),
    RosterMember("브라이스 리드", _M, _P, 1300, 2548, 0, _SD),
    RosterMember("자비어 크로스", _M, _P, 1300, 2548, 0, _RAW),
    # ── 남성부 · 26년차 데뷔 ───────────────────────────
    RosterMember("루커스 블레이즈", _M, _MC, 1352, 2600, 6, _SD),
    RosterMember("자비어 벨", _M, _P, 1352, 2600, 0, _RAW),
    RosterMember("카일 서머스", _M, _P, 1352, 2600, 0, _SD),
    # ── 남성부 · 27년차 데뷔 ───────────────────────────
    RosterMember("잭슨 밴스", _M, _MC, 1404, 2652, 6, _RAW),
    RosterMember("마커스 프로스트", _M, _P, 1404, 2652, 0, _SD),
    RosterMember("맥스 프라이스", _M, _P, 1404, 2652, 0, _RAW),
    # ── 남성부 · 28년차 데뷔 ───────────────────────────
    RosterMember("마커스 서머스", _M, _P, 1456, 2704, 0, _SD),
    RosterMember("실라스 헤이즈", _M, _P, 1456, 2704, 0, _RAW),
    RosterMember("제이든 스틸", _M, _P, 1456, 2704, 0, _SD),
    # ── 남성부 · 29년차 데뷔 ───────────────────────────
    RosterMember("코너 파울러", _M, _MC, 1508, 2756, 6, _RAW),
    RosterMember("개럿 헌터", _M, _P, 1508, 2756, 0, _SD),
    RosterMember("데본 프로스트", _M, _P, 1508, 2756, 0, _RAW),
    # ── 남성부 · 30년차 데뷔 ───────────────────────────
    RosterMember("자비어 프라이스", _M, _MC, 1560, 2808, 6, _SD),
    RosterMember("데릭 벨", _M, _P, 1560, 2808, 0, _RAW),
    RosterMember("마커스 윈터스", _M, _P, 1560, 2808, 0, _SD),
    # ── 여성부 · 0주차 명부 ────────────────────────────
    RosterMember("나오미", _F, _ME, 0, 208, 16, _SD),
    RosterMember("나이아 잭스", _F, _ME, 0, 156, 20, _SD),
    RosterMember("리브 모건", _F, _ME, 0, 520, 10, _RAW),
    RosterMember("리아 리플리", _F, _ME, 0, 676, 7, _SD),
    RosterMember("베일리", _F, _ME, 0, 260, 15, _RAW),
    RosterMember("베키 린치", _F, _ME, 0, 156, 17, _RAW),
    RosterMember("비앙카 벨레어", _F, _ME, 0, 260, 15, _SD),
    RosterMember("샬럿 플레어", _F, _ME, 0, 156, 18, _SD),
    RosterMember("스테파니 바케르", _F, _ME, 0, 468, 11, _RAW),
    RosterMember("아스카", _F, _ME, 0, 156, 22, _RAW),
    RosterMember("알렉사 블리스", _F, _ME, 0, 364, 13, _SD),
    RosterMember("이요 스카이", _F, _ME, 0, 312, 14, _RAW),
    RosterMember("제이드 카길", _F, _ME, 0, 416, 12, _SD),
    RosterMember("줄리아", _F, _ME, 0, 520, 10, _SD),
    RosterMember("티파니 스트랫턴", _F, _ME, 0, 780, 5, _SD),
    RosterMember("AJ 리", _F, _MC, 0, 156, 17, _RAW),
    RosterMember("B-팹", _F, _MC, 0, 364, 13, _SD),
    RosterMember("내티", _F, _MC, 0, 156, 22, _RAW, "나탈리아", 260),
    RosterMember("니키 벨라", _F, _MC, 0, 156, 20, _RAW),
    RosterMember("라이라 발키리아", _F, _MC, 0, 676, 7, _RAW),
    RosterMember("라켈 로드리게스", _F, _MC, 0, 364, 13, _RAW),
    RosterMember("래쉬 레전드", _F, _MC, 0, 676, 7, _SD),
    RosterMember("레이니 리드", _F, _MC, 0, 780, 5, _SD),
    RosterMember("록샌 페레즈", _F, _MC, 0, 936, 2, _RAW),
    RosterMember("맥신 듀프리", _F, _MC, 0, 676, 7, _RAW),
    RosterMember("미친", _F, _MC, 0, 260, 15, _SD),
    RosterMember("브리 벨라", _F, _MC, 0, 156, 20, _RAW),
    RosterMember("블레이크 먼로", _F, _MC, 0, 728, 6, _SD),
    RosterMember("솔 루카", _F, _MC, 0, 832, 4, _RAW),
    RosterMember("아이비 나일", _F, _MC, 0, 416, 12, _RAW),
    RosterMember("제이시 제인", _F, _MC, 0, 624, 8, _SD),
    RosterMember("조르딘 그레이스", _F, _MC, 0, 624, 8, _SD),
    RosterMember("첼시 그린", _F, _MC, 0, 364, 13, _SD),
    RosterMember("캔디스 르래", _F, _MC, 0, 156, 18, _SD),
    RosterMember("키아나 제임스", _F, _MC, 0, 676, 7, _SD),
    RosterMember("파이퍼 니븐", _F, _MC, 0, 364, 13, _SD),
    RosterMember("팰런 헨리", _F, _MC, 0, 572, 9, _SD),
    RosterMember("페이지", _F, _MC, 0, 416, 12, _RAW),
    RosterMember("니키타 라이온스", _F, _P, 0, 780, 5, _SD),
    RosterMember("레이나 볼칸", _F, _P, 0, 676, 7, _RAW),
    RosterMember("레일라 딕스", _F, _P, 0, 780, 5, _SD),
    RosterMember("렌 싱클레어", _F, _P, 0, 572, 9, _RAW),
    RosterMember("롤라 바이스", _F, _P, 0, 728, 6, _SD),
    RosterMember("리지 레인", _F, _P, 0, 728, 6, _RAW),
    RosterMember("마이카 락우드", _F, _P, 0, 884, 3, _SD),
    RosterMember("스카일라 레이", _F, _P, 0, 884, 3, _RAW),
    RosterMember("아리아나 그레이스", _F, _P, 0, 572, 9, _SD),
    RosterMember("애드리아나 리조", _F, _P, 0, 780, 5, _RAW),
    RosterMember("웬디 추", _F, _P, 0, 416, 12, _SD),
    RosterMember("이지 데임", _F, _P, 0, 780, 5, _RAW),
    RosterMember("자리아", _F, _P, 0, 780, 5, _SD),
    RosterMember("제이다 파커", _F, _P, 0, 780, 5, _RAW),
    RosterMember("카르멘 페트로비치", _F, _P, 0, 624, 8, _SD),
    RosterMember("칼리 암스트롱", _F, _P, 0, 520, 10, _RAW),
    RosterMember("켄달 그레이", _F, _P, 0, 884, 3, _SD),
    RosterMember("켈라니 조던", _F, _P, 0, 780, 5, _RAW),
    RosterMember("테이텀 팩슬리", _F, _P, 0, 676, 7, _SD),
    RosterMember("티아 헤일", _F, _P, 0, 1040, 0, _SD),
    # ── 여성부 · 1년차 데뷔 ────────────────────────────
    RosterMember("스칼렛 서머스", _F, _MC, 52, 1300, 6, _RAW),
    RosterMember("아리아 베넷", _F, _P, 52, 624, 9, _SD),
    RosterMember("엠버 바이퍼", _F, _P, 52, 1300, 0, _RAW),
    RosterMember("이든 폭스", _F, _P, 52, 1300, 0, _SD),
    RosterMember("이자벨 퀸", _F, _P, 52, 1300, 0, _RAW),
    # ── 여성부 · 2년차 데뷔 ────────────────────────────
    RosterMember("마야 나이트", _F, _MC, 104, 1352, 6, _SD),
    RosterMember("델라니 스톰", _F, _P, 104, 1352, 0, _RAW),
    RosterMember("샨텔 먼로", _F, _P, 104, 936, 4, _SD),
    RosterMember("케일라 레인", _F, _P, 104, 1352, 0, _RAW),
    RosterMember("케일라 하트", _F, _P, 104, 1352, 0, _SD),
    # ── 여성부 · 3년차 데뷔 ────────────────────────────
    RosterMember("테사 리드", _F, _MC, 156, 1404, 6, _RAW),
    RosterMember("PJ 바사", _F, _P, 156, 936, 5, _SD),
    RosterMember("마야 스톰", _F, _P, 156, 1404, 0, _RAW),
    RosterMember("스칼렛 폭스", _F, _P, 156, 1404, 0, _SD),
    RosterMember("케일라 스파크", _F, _P, 156, 1404, 0, _RAW),
    # ── 여성부 · 4년차 데뷔 ────────────────────────────
    RosterMember("케일라 헤이즈", _F, _MC, 208, 1456, 6, _SD),
    RosterMember("리아 파울러", _F, _P, 208, 1456, 0, _RAW),
    RosterMember("이든 벨", _F, _P, 208, 1456, 0, _SD),
    RosterMember("제나 스털링", _F, _P, 208, 1248, 0, _RAW),
    RosterMember("조이 크로스", _F, _P, 208, 1456, 0, _SD),
    # ── 여성부 · 5년차 데뷔 ────────────────────────────
    RosterMember("이자벨 블레이즈", _F, _MC, 260, 1508, 6, _RAW),
    RosterMember("델라니 폭스", _F, _P, 260, 1508, 0, _SD),
    RosterMember("마야 크로스", _F, _P, 260, 1508, 0, _RAW),
    RosterMember("브룩 블레이즈", _F, _P, 260, 1508, 0, _SD),
    # ── 여성부 · 6년차 데뷔 ────────────────────────────
    RosterMember("노바 리드", _F, _MC, 312, 1560, 6, _RAW),
    RosterMember("시에나 나이트", _F, _P, 312, 1560, 0, _SD),
    RosterMember("아이비 헌터", _F, _P, 312, 1560, 0, _RAW),
    RosterMember("카일라 레인", _F, _P, 312, 1560, 0, _SD),
    # ── 여성부 · 7년차 데뷔 ────────────────────────────
    RosterMember("이자벨 밴스", _F, _MC, 364, 1612, 6, _RAW),
    RosterMember("노바 프라이스", _F, _P, 364, 1612, 0, _SD),
    RosterMember("미셸 헤이즈", _F, _P, 364, 1612, 0, _RAW),
    RosterMember("하퍼 프로스트", _F, _P, 364, 1612, 0, _SD),
    # ── 여성부 · 8년차 데뷔 ────────────────────────────
    RosterMember("엠버 스틸", _F, _MC, 416, 1664, 6, _RAW),
    RosterMember("리아 라이커", _F, _P, 416, 1664, 0, _SD),
    RosterMember("애슐리 윈터스", _F, _P, 416, 1664, 0, _RAW),
    RosterMember("테사 케이지", _F, _P, 416, 1664, 0, _SD),
    # ── 여성부 · 9년차 데뷔 ────────────────────────────
    RosterMember("브리아나 레인", _F, _MC, 468, 1716, 6, _RAW),
    RosterMember("리아 헤이즈", _F, _P, 468, 1716, 0, _SD),
    RosterMember("이든 울프", _F, _P, 468, 1716, 0, _RAW),
    RosterMember("조던 리드", _F, _P, 468, 1716, 0, _SD),
    # ── 여성부 · 10년차 데뷔 ───────────────────────────
    RosterMember("조이 브릭스", _F, _MC, 520, 1768, 6, _RAW),
    RosterMember("조이 셰이드", _F, _P, 520, 1768, 0, _SD),
    RosterMember("하퍼 서머스", _F, _P, 520, 1768, 0, _RAW),
    RosterMember("하퍼 폭스", _F, _P, 520, 1768, 0, _SD),
    # ── 여성부 · 11년차 데뷔 ───────────────────────────
    RosterMember("리네아 폭스", _F, _MC, 572, 1820, 6, _RAW),
    RosterMember("마야 레인", _F, _P, 572, 1820, 0, _SD),
    RosterMember("시에나 벨", _F, _P, 572, 1820, 0, _RAW),
    RosterMember("페이 셰이드", _F, _P, 572, 1820, 0, _SD),
    # ── 여성부 · 12년차 데뷔 ───────────────────────────
    RosterMember("스칼렛 라이커", _F, _MC, 624, 1872, 6, _RAW),
    RosterMember("리네아 나이트", _F, _P, 624, 1872, 0, _SD),
    RosterMember("엠버 밴스", _F, _P, 624, 1872, 0, _RAW),
    RosterMember("조이 라이커", _F, _P, 624, 1872, 0, _SD),
    # ── 여성부 · 13년차 데뷔 ───────────────────────────
    RosterMember("노바 프로스트", _F, _MC, 676, 1924, 6, _RAW),
    RosterMember("스칼렛 세이지", _F, _P, 676, 1924, 0, _SD),
    RosterMember("애슐리 스틸", _F, _P, 676, 1924, 0, _RAW),
    RosterMember("이든 서머스", _F, _P, 676, 1924, 0, _SD),
    # ── 여성부 · 14년차 데뷔 ───────────────────────────
    RosterMember("애슐리 브릭스", _F, _MC, 728, 1976, 6, _RAW),
    RosterMember("로렌 리버스", _F, _P, 728, 1976, 0, _SD),
    RosterMember("마야 하트", _F, _P, 728, 1976, 0, _RAW),
    RosterMember("아이비 셰이드", _F, _P, 728, 1976, 0, _SD),
    # ── 여성부 · 15년차 데뷔 ───────────────────────────
    RosterMember("아이비 헤이즈", _F, _MC, 780, 2028, 6, _RAW),
    RosterMember("미셸 벨", _F, _P, 780, 2028, 0, _SD),
    RosterMember("카일라 셰이드", _F, _P, 780, 2028, 0, _RAW),
    RosterMember("하퍼 브릭스", _F, _P, 780, 2028, 0, _SD),
    # ── 여성부 · 16년차 데뷔 ───────────────────────────
    RosterMember("리아 프로스트", _F, _MC, 832, 2080, 6, _RAW),
    RosterMember("브리아나 퀸", _F, _P, 832, 2080, 0, _SD),
    RosterMember("세라 케이지", _F, _P, 832, 2080, 0, _RAW),
    RosterMember("조던 스틸", _F, _P, 832, 2080, 0, _SD),
    # ── 여성부 · 17년차 데뷔 ───────────────────────────
    RosterMember("로렌 크로스", _F, _MC, 884, 2132, 6, _RAW),
    RosterMember("델라니 벨", _F, _P, 884, 2132, 0, _SD),
    RosterMember("미셸 스톤", _F, _P, 884, 2132, 0, _RAW),
    RosterMember("미셸 파울러", _F, _P, 884, 2132, 0, _SD),
    # ── 여성부 · 18년차 데뷔 ───────────────────────────
    RosterMember("브리아나 나이트", _F, _MC, 936, 2184, 6, _RAW),
    RosterMember("리아 하트", _F, _P, 936, 2184, 0, _SD),
    RosterMember("아이비 나이트", _F, _P, 936, 2184, 0, _RAW),
    RosterMember("테사 밴스", _F, _P, 936, 2184, 0, _SD),
    # ── 여성부 · 19년차 데뷔 ───────────────────────────
    RosterMember("케일라 스톤", _F, _MC, 988, 2236, 6, _RAW),
    RosterMember("브룩 서머스", _F, _P, 988, 2236, 0, _SD),
    RosterMember("이든 파울러", _F, _P, 988, 2236, 0, _RAW),
    RosterMember("하퍼 세이지", _F, _P, 988, 2236, 0, _SD),
    # ── 여성부 · 20년차 데뷔 ───────────────────────────
    RosterMember("델라니 세이지", _F, _MC, 1040, 2288, 6, _RAW),
    RosterMember("노바 스틸", _F, _P, 1040, 2288, 0, _SD),
    RosterMember("델라니 스틸", _F, _P, 1040, 2288, 0, _RAW),
    RosterMember("로렌 프라이스", _F, _P, 1040, 2288, 0, _SD),
    # ── 여성부 · 21년차 데뷔 ───────────────────────────
    RosterMember("로렌 헌터", _F, _MC, 1092, 2340, 6, _RAW),
    RosterMember("이자벨 스톤", _F, _P, 1092, 2340, 0, _SD),
    RosterMember("조던 리버스", _F, _P, 1092, 2340, 0, _RAW),
    RosterMember("케일라 블레이즈", _F, _P, 1092, 2340, 0, _SD),
    # ── 여성부 · 22년차 데뷔 ───────────────────────────
    RosterMember("엠버 프라이스", _F, _MC, 1144, 2392, 6, _RAW),
    RosterMember("마야 파울러", _F, _P, 1144, 2392, 0, _SD),
    RosterMember("브룩 나이트", _F, _P, 1144, 2392, 0, _RAW),
    RosterMember("시에나 프라이스", _F, _P, 1144, 2392, 0, _SD),
    # ── 여성부 · 23년차 데뷔 ───────────────────────────
    RosterMember("엠버 크로스", _F, _MC, 1196, 2444, 6, _RAW),
    RosterMember("스칼렛 하트", _F, _P, 1196, 2444, 0, _SD),
    RosterMember("아이비 프로스트", _F, _P, 1196, 2444, 0, _RAW),
    RosterMember("애슐리 스톤", _F, _P, 1196, 2444, 0, _SD),
    # ── 여성부 · 24년차 데뷔 ───────────────────────────
    RosterMember("시에나 서머스", _F, _MC, 1248, 2496, 6, _RAW),
    RosterMember("마야 밴스", _F, _P, 1248, 2496, 0, _SD),
    RosterMember("세라 크로스", _F, _P, 1248, 2496, 0, _RAW),
    RosterMember("카일라 프로스트", _F, _P, 1248, 2496, 0, _SD),
    # ── 여성부 · 25년차 데뷔 ───────────────────────────
    RosterMember("브리아나 폭스", _F, _MC, 1300, 2548, 6, _RAW),
    RosterMember("로렌 윈터스", _F, _P, 1300, 2548, 0, _SD),
    RosterMember("브리아나 리드", _F, _P, 1300, 2548, 0, _RAW),
    RosterMember("페이 블레이즈", _F, _P, 1300, 2548, 0, _SD),
    # ── 여성부 · 26년차 데뷔 ───────────────────────────
    RosterMember("리아 울프", _F, _MC, 1352, 2600, 6, _RAW),
    RosterMember("로렌 스틸", _F, _P, 1352, 2600, 0, _SD),
    RosterMember("시에나 블레이즈", _F, _P, 1352, 2600, 0, _RAW),
    RosterMember("애슐리 울프", _F, _P, 1352, 2600, 0, _SD),
    # ── 여성부 · 27년차 데뷔 ───────────────────────────
    RosterMember("조이 스톰", _F, _MC, 1404, 2652, 6, _RAW),
    RosterMember("미셸 윈터스", _F, _P, 1404, 2652, 0, _SD),
    RosterMember("이든 퀸", _F, _P, 1404, 2652, 0, _RAW),
    RosterMember("카일라 나이트", _F, _P, 1404, 2652, 0, _SD),
    # ── 여성부 · 28년차 데뷔 ───────────────────────────
    RosterMember("마야 블레이즈", _F, _MC, 1456, 2704, 6, _RAW),
    RosterMember("노바 레인", _F, _P, 1456, 2704, 0, _SD),
    RosterMember("리네아 벨", _F, _P, 1456, 2704, 0, _RAW),
    RosterMember("시에나 프로스트", _F, _P, 1456, 2704, 0, _SD),
    # ── 여성부 · 29년차 데뷔 ───────────────────────────
    RosterMember("하퍼 프라이스", _F, _MC, 1508, 2756, 6, _RAW),
    RosterMember("브리아나 밴스", _F, _P, 1508, 2756, 0, _SD),
    RosterMember("시에나 퀸", _F, _P, 1508, 2756, 0, _RAW),
    RosterMember("조이 헌터", _F, _P, 1508, 2756, 0, _SD),
    # ── 여성부 · 30년차 데뷔 ───────────────────────────
    RosterMember("노바 라이커", _F, _MC, 1560, 2808, 6, _RAW),
    RosterMember("리네아 셰이드", _F, _P, 1560, 2808, 0, _SD),
    RosterMember("조이 폭스", _F, _P, 1560, 2808, 0, _RAW),
    RosterMember("테사 스톤", _F, _P, 1560, 2808, 0, _SD),
)


def active_at(week: int) -> tuple[RosterMember, ...]:
    """그 주차에 현역인 선수들."""
    return tuple(m for m in ROSTER if m.is_active_at(week))


_BY_NAME: dict[str, RosterMember] = {}
for _m in ROSTER:  # pragma: no cover - 임포트 시 색인
    _BY_NAME[_m.name] = _m
    if _m.renamed_to is not None:
        _BY_NAME[_m.renamed_to] = _m


def member_of(name: str) -> RosterMember | None:
    """이름으로 명부 한 줄. **플레이어는 명부에 없으므로 None이 정상이다.**

    **바꾸기 전 이름으로도 찾힌다** (§3-D54). 로그와 대립에 남은 옛 이름이 그대로
    없는 사람이 되면, 개명이 곧 실종이 된다.
    """
    return _BY_NAME.get(name)


def name_at(member: RosterMember, week: int) -> str:
    """그 주차에 불리던 활동명 (§3-D54).

    **명부의 시간 축에 이름이 하나 더 붙었다.** 로스 아메리카노스 셋은 그 이름으로
    뛰다가 본래 활동명으로 돌아가고, 내티는 나탈리아가 된다 — 원본 CSV가 `|`로 병기해
    둔 것이 곧 그 이력이다.
    """
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
    for tier in (RivalTier.MIDCARD, RivalTier.MAIN_EVENT)
)
"""드래프트가 집을 수 있는 칸. **유망주는 없다** — 그들은 육성 브랜드에 있다(§3-D53)."""


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
        member = member_of(title_scene.champion_at(seed, week, title) or "")
        if member is not None:
            held.add(member.name)
    return frozenset(held)


@lru_cache(maxsize=4096)
def _draft_flips(seed: int, year: int) -> frozenset[str]:
    """그 해 연말까지 브랜드가 뒤집힌 사람들 (§3-D54).

    **커리어마다 다른 드래프트가 돈다** (2026-08-12 사용자 요청). 명부 자체는 모든
    커리어가 공유하는 상수이지만, *누가 어느 브랜드에 서 있는가*는 시드를 탄다 —
    배경 세계를 시드에서 되짚는 다른 층들과 같은 규약이다(§3-D38·D44·D52).

    **앞 해를 다시 걷지 않는다.** 재귀 + 캐시라 한 해치 일만 새로 한다. 그냥 1년부터
    다시 세면 `pool_for` 한 번이 30년을 걷고, 그게 주차마다 반복된다.
    """
    if year <= 0:
        return frozenset()
    flipped = set(_draft_flips(seed, year - 1))
    week = year * WEEKS_PER_YEAR + DRAFT_WEEK
    roll = SeededRoll(seed, year, seeded_roll.DRAFT)
    for _ in range(DRAFT_PAIRS):
        gender, tier = roll.pick(_DRAFT_CELLS)
        guarded = _champions_at(seed, week - 1, gender)
        pools = {
            brand: [
                m
                for m in ROSTER
                if m.gender is gender
                and m.is_active_at(week)
                and tier_at(m, week) is tier
                and _home_at(m, flipped) is brand
                and m.name not in guarded
            ]
            for brand in (Brand.RAW, Brand.SMACKDOWN)
        }
        if not all(pools.values()):
            continue
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            chosen = roll.pick(pools[brand]).name
            flipped.symmetric_difference_update({chosen})
    return frozenset(flipped)


def _home_at(member: RosterMember, flipped: frozenset[str] | set[str]) -> Brand:
    if member.name not in flipped:
        return member.home_brand
    return Brand.SMACKDOWN if member.home_brand is Brand.RAW else Brand.RAW


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


def brand_at(member: RosterMember, week: int, seed: int = 0) -> Brand:
    """그 주차에 이 사람이 선 브랜드 (§3-D53). **승급이 곧 콜업이다.**

    명부의 등급이 이미 브랜드를 말하고 있다 — 원본에서 NXT·Evolve 70명은 **전원
    유망주**이고 RAW·SmackDown은 전원 미드카드 이상이다. 그래서 축을 새로 만들지 않고
    있는 축을 읽는다: 유망주면 육성 브랜드, 올라갔으면 자기 메인 브랜드다.
    """
    if tier_at(member, week) is RivalTier.PROSPECT:
        return Brand.NXT
    year = (week - DRAFT_WEEK) // WEEKS_PER_YEAR
    return _home_at(member, _draft_flips(seed, max(0, year)))


def call_up_week(member: RosterMember) -> int | None:
    """육성 브랜드를 떠나는 주차 (§3-D53). **처음부터 메인 로스터면 None이다.**

    승급이 곧 콜업이므로(`brand_at`) 유망주가 미드카드로 올라서는 주차가 그대로
    NXT를 떠나는 주차다. 벨트 계보가 이걸 읽는다 — 콜업된 사람은 NXT 벨트를 들고
    갈 수 없다(§3-D38).
    """
    if member.start_tier is not RivalTier.PROSPECT:
        return None
    return member.debut_week + _wait_for(member, 0)


def tier_in(brand: Brand, tier: RivalTier) -> RivalTier:
    """그 브랜드에 **실제로 있는** 등급으로 접는다.

    육성 브랜드에는 유망주만 살고 메인 로스터에는 유망주가 없다(`brand_at`). 접지 않고
    물으면 빈 명단이 돌아오고, 그러면 벨트에 주인이 사라지거나(§3-D38) 대립 상대가
    없어진다 — **없는 칸을 묻지 않게 하는 것이 이 함수의 일이다.**
    """
    if brand is Brand.NXT:
        return RivalTier.PROSPECT
    return max(tier, RivalTier.MIDCARD)


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
        name_at(m, week)
        for m in ROSTER
        if m.gender is gender
        and m.is_active_at(week)
        and tier_at(m, week) is tier
        and (brand is None or brand_at(m, week, seed) is brand)
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

for _g in Gender:  # pragma: no cover - 브랜드 칸 검증 (§3-D53)
    for _b in Brand:
        _t = tier_in(_b, RivalTier.MAIN_EVENT)
        for _w in range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR):
            if len(pool_for(_g, _t, _w, _b)) < MIN_BRAND_POOL:
                raise RuntimeError(
                    f"{_g}/{_b} 정상급이 {_w // WEEKS_PER_YEAR}년차에 "
                    f"너무 얇습니다: {pool_for(_g, _t, _w, _b)}"
                )
