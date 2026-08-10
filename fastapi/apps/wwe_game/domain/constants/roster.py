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
    # ── 남성부 · 0주차 명부 ────────────────────────────
    RosterMember("CM 펑크", _M, _ME, 0, 156, 25),
    RosterMember("LA 나이트", _M, _ME, 0, 260, 21),
    RosterMember("군터", _M, _ME, 0, 468, 17),
    RosterMember("데미안 프리스트", _M, _ME, 0, 260, 21),
    RosterMember("드류 맥킨타이어", _M, _ME, 0, 364, 19),
    RosterMember("랜디 오턴", _M, _ME, 0, 156, 24),
    RosterMember("레이 미스테리오", _M, _ME, 0, 104, 29),
    RosterMember("로건 폴", _M, _ME, 0, 884, 9),
    RosterMember("로만 레인즈", _M, _ME, 0, 364, 19),
    RosterMember("브록 레스너", _M, _ME, 0, 156, 27),
    RosterMember("브론 브레이커", _M, _ME, 0, 1040, 6),
    RosterMember("브론슨 리드", _M, _ME, 0, 572, 15),
    RosterMember("새미 제인", _M, _ME, 0, 312, 20),
    RosterMember("세스 롤린스", _M, _ME, 0, 416, 18),
    RosterMember("솔로 시코아", _M, _ME, 0, 780, 11),
    RosterMember("제이 우소", _M, _ME, 0, 416, 18),
    RosterMember("제이콥 파투", _M, _ME, 0, 728, 12),
    RosterMember("케빈 오웬스", _M, _ME, 0, 312, 20),
    RosterMember("코디 로즈", _M, _ME, 0, 364, 19),
    RosterMember("핀 밸러", _M, _ME, 0, 156, 23),
    RosterMember("JD 맥도나", _M, _MC, 0, 624, 14),
    RosterMember("R-트루스", _M, _MC, 0, 104, 32),
    RosterMember("그레이슨 월러", _M, _MC, 0, 624, 14),
    RosterMember("나카무라 신스케", _M, _MC, 0, 156, 24),
    RosterMember("네이선 프레이저", _M, _MC, 0, 1040, 6),
    RosterMember("댄 하우젠", _M, _MC, 0, 624, 14),
    RosterMember("도미닉 미스테리오", _M, _MC, 0, 988, 7),
    RosterMember("드래곤 리", _M, _MC, 0, 884, 9),
    RosterMember("레이 페닉스", _M, _MC, 0, 676, 13),
    RosterMember("로이스 키스", _M, _MC, 0, 364, 19),
    RosterMember("루세프", _M, _MC, 0, 364, 19),
    RosterMember("리키 세인츠", _M, _MC, 0, 624, 14),
    RosterMember("맷 카도나", _M, _MC, 0, 364, 19),
    RosterMember("몬테즈 포드", _M, _MC, 0, 624, 14),
    RosterMember("미즈", _M, _MC, 0, 156, 23),
    RosterMember("배런 코빈", _M, _MC, 0, 364, 19),
    RosterMember("베르토", _M, _MC, 0, 936, 8),
    RosterMember("브루투스 크리드", _M, _MC, 0, 936, 8),
    RosterMember("빅 캐스", _M, _MC, 0, 416, 18),
    RosterMember("아이바", _M, _MC, 0, 312, 20),
    RosterMember("아키라 토자와", _M, _MC, 0, 364, 19),
    RosterMember("안젤로 도킨스", _M, _MC, 0, 624, 14),
    RosterMember("액시옴", _M, _MC, 0, 988, 7),
    RosterMember("에단 페이지", _M, _MC, 0, 624, 14),
    RosterMember("에릭", _M, _MC, 0, 364, 19),
    RosterMember("엔젤", _M, _MC, 0, 780, 11),
    RosterMember("엘 그란데 아메리카노 | 루드비히 카이저", _M, _MC, 0, 676, 13),
    RosterMember("엘튼 프린스", _M, _MC, 0, 988, 7),
    RosterMember("오모스", _M, _MC, 0, 832, 10),
    RosterMember("오바 페미", _M, _MC, 0, 1040, 6),
    RosterMember("오스틴 씨어리", _M, _MC, 0, 988, 7),
    RosterMember("오티스", _M, _MC, 0, 728, 12),
    RosterMember("일리야 드라구노프", _M, _MC, 0, 832, 10),
    RosterMember("쟈니 가르가노", _M, _MC, 0, 468, 17),
    RosterMember("조 헨드리", _M, _MC, 0, 520, 16),
    RosterMember("줄리우스 크리드", _M, _MC, 0, 884, 9),
    RosterMember("지미 우소", _M, _MC, 0, 416, 18),
    RosterMember("지본 에반스", _M, _MC, 0, 1352, 0),
    RosterMember("채드 게이블", _M, _MC, 0, 624, 14),
    RosterMember("카멜로 헤이즈", _M, _MC, 0, 832, 10),
    RosterMember("크루즈 델 토로", _M, _MC, 0, 728, 12),
    RosterMember("킷 윌슨", _M, _MC, 0, 832, 10),
    RosterMember("타마 통가", _M, _MC, 0, 260, 21),
    RosterMember("타일러 베이트 | 브라보 아메리카노", _M, _MC, 0, 988, 7),
    RosterMember("탈라 통가", _M, _MC, 0, 676, 13),
    RosterMember("트릭 윌리엄스", _M, _MC, 0, 832, 10),
    RosterMember("펜타", _M, _MC, 0, 364, 19),
    RosterMember("피트 던 | 라요 아메리카노", _M, _MC, 0, 832, 10),
    RosterMember("호아킨 와일드", _M, _MC, 0, 468, 17),
    RosterMember("EK 프로스퍼", _M, _P, 0, 1196, 3),
    RosterMember("나라쿠", _M, _P, 0, 468, 17),
    RosterMember("노암 다르", _M, _P, 0, 780, 11),
    RosterMember("니코 밴스", _M, _P, 0, 1092, 5),
    RosterMember("도리안 반 덕스", _M, _P, 0, 936, 8),
    RosterMember("디온 레녹스", _M, _P, 0, 1040, 6),
    RosterMember("렉시스 킹", _M, _P, 0, 832, 10),
    RosterMember("로메오 모레노", _M, _P, 0, 1248, 2),
    RosterMember("루시엔 프라이스", _M, _P, 0, 988, 7),
    RosterMember("리키 스모크스", _M, _P, 0, 1144, 4),
    RosterMember("린세 도라도", _M, _P, 0, 468, 17),
    RosterMember("마일스 본", _M, _P, 0, 1092, 5),
    RosterMember("메이슨 룩", _M, _P, 0, 988, 7),
    RosterMember("브래드 베일러", _M, _P, 0, 1404, 0),
    RosterMember("브롱코 니마", _M, _P, 0, 1248, 2),
    RosterMember("브룩스 젠슨", _M, _P, 0, 1248, 2),
    RosterMember("샤일로 힐", _M, _P, 0, 1092, 5),
    RosterMember("세이콴 슈거스", _M, _P, 0, 1144, 4),
    RosterMember("숀 레거시", _M, _P, 0, 936, 8),
    RosterMember("숀 스피어스", _M, _P, 0, 156, 23),
    RosterMember("엘리오 르플뢰르", _M, _P, 0, 1092, 5),
    RosterMember("오시리스 그리핀", _M, _P, 0, 1040, 6),
    RosterMember("유라이어 코너스", _M, _P, 0, 1248, 2),
    RosterMember("재스퍼 트로이", _M, _P, 0, 1040, 6),
    RosterMember("잭슨 드레이크", _M, _P, 0, 1352, 0),
    RosterMember("조쉬 브릭스", _M, _P, 0, 780, 11),
    RosterMember("찰리 뎀프시", _M, _P, 0, 988, 7),
    RosterMember("채닝 로렌조", _M, _P, 0, 988, 7),
    RosterMember("캠 헨드릭스", _M, _P, 0, 988, 7),
    RosterMember("커틀러 제임스", _M, _P, 0, 1196, 3),
    RosterMember("케일 딕슨", _M, _P, 0, 1040, 6),
    RosterMember("크루즈 몬타나", _M, _P, 0, 676, 13),
    RosterMember("키아누 카버", _M, _P, 0, 1092, 5),
    RosterMember("탱크 레저", _M, _P, 0, 1144, 4),
    RosterMember("테비언 하이츠", _M, _P, 0, 988, 7),
    RosterMember("테이트 와일더", _M, _P, 0, 1040, 6),
    RosterMember("토니 디안젤로", _M, _P, 0, 884, 9),
    RosterMember("트리스탄 앤젤스", _M, _P, 0, 1300, 1),
    RosterMember("행크 워커", _M, _P, 0, 1040, 6),
    # ── 남성부 · 1년차 데뷔 ────────────────────────────
    RosterMember("디온 스파크", _M, _MC, 52, 1300, 6),
    RosterMember("아론 루크", _M, _P, 52, 988, 8),
    RosterMember("카일 머서", _M, _P, 52, 1300, 0),
    RosterMember("케이든 하트", _M, _P, 52, 1300, 0),
    RosterMember("할렘 루이스", _M, _P, 52, 1196, 4),
    # ── 남성부 · 2년차 데뷔 ────────────────────────────
    RosterMember("오스틴 파울러", _M, _MC, 104, 1352, 6),
    RosterMember("놀란 폭스", _M, _P, 104, 1352, 0),
    RosterMember("브랙스턴 콜", _M, _P, 104, 1248, 4),
    RosterMember("브랜든 서머스", _M, _P, 104, 1352, 0),
    RosterMember("잇츠 갤", _M, _P, 104, 1352, 2),
    # ── 남성부 · 3년차 데뷔 ────────────────────────────
    RosterMember("디온 프로스트", _M, _MC, 156, 1404, 6),
    RosterMember("데본 서머스", _M, _P, 156, 1404, 0),
    RosterMember("자비어 리버스", _M, _P, 156, 1404, 0),
    RosterMember("잭스 프레슬리", _M, _P, 156, 1300, 4),
    RosterMember("카푸치노 존스", _M, _P, 156, 1404, 2),
    # ── 남성부 · 4년차 데뷔 ────────────────────────────
    RosterMember("스타보이 찰리", _M, _P, 208, 1508, 1),
    RosterMember("실라스 폭스", _M, _P, 208, 1456, 0),
    RosterMember("웨이드 헌터", _M, _P, 208, 1456, 0),
    RosterMember("일라이자 홀리필드", _M, _P, 208, 1248, 6),
    RosterMember("트로이 프라이스", _M, _P, 208, 1456, 0),
    # ── 남성부 · 5년차 데뷔 ────────────────────────────
    RosterMember("브라이스 폭스", _M, _MC, 260, 1508, 6),
    RosterMember("네이트 리버스", _M, _P, 260, 1508, 0),
    RosterMember("디온 라이커", _M, _P, 260, 1508, 0),
    # ── 남성부 · 6년차 데뷔 ────────────────────────────
    RosterMember("케이든 벨", _M, _MC, 312, 1560, 6),
    RosterMember("웨이드 서머스", _M, _P, 312, 1560, 0),
    RosterMember("카일 바이퍼", _M, _P, 312, 1560, 0),
    # ── 남성부 · 7년차 데뷔 ────────────────────────────
    RosterMember("마커스 블레이즈", _M, _MC, 364, 1612, 6),
    RosterMember("오스틴 브릭스", _M, _P, 364, 1612, 0),
    RosterMember("트로이 폭스", _M, _P, 364, 1612, 0),
    # ── 남성부 · 8년차 데뷔 ────────────────────────────
    RosterMember("브랜든 헤이즈", _M, _P, 416, 1664, 0),
    RosterMember("웨이드 스파크", _M, _P, 416, 1664, 0),
    RosterMember("케이든 헌터", _M, _P, 416, 1664, 0),
    # ── 남성부 · 9년차 데뷔 ────────────────────────────
    RosterMember("오스틴 셰이드", _M, _MC, 468, 1716, 6),
    RosterMember("라이언 스파크", _M, _P, 468, 1716, 0),
    RosterMember("코너 하트", _M, _P, 468, 1716, 0),
    # ── 남성부 · 10년차 데뷔 ───────────────────────────
    RosterMember("타이슨 윈터스", _M, _MC, 520, 1768, 6),
    RosterMember("데릭 바이퍼", _M, _P, 520, 1768, 0),
    RosterMember("타이슨 서머스", _M, _P, 520, 1768, 0),
    # ── 남성부 · 11년차 데뷔 ───────────────────────────
    RosterMember("알렉 프로스트", _M, _MC, 572, 1820, 6),
    RosterMember("이선 리드", _M, _P, 572, 1820, 0),
    RosterMember("잭슨 브릭스", _M, _P, 572, 1820, 0),
    # ── 남성부 · 12년차 데뷔 ───────────────────────────
    RosterMember("개럿 스톰", _M, _P, 624, 1872, 0),
    RosterMember("놀란 윈터스", _M, _P, 624, 1872, 0),
    RosterMember("자비어 스틸", _M, _P, 624, 1872, 0),
    # ── 남성부 · 13년차 데뷔 ───────────────────────────
    RosterMember("타이슨 바이퍼", _M, _MC, 676, 1924, 6),
    RosterMember("루커스 라이커", _M, _P, 676, 1924, 0),
    RosterMember("카일 케이지", _M, _P, 676, 1924, 0),
    # ── 남성부 · 14년차 데뷔 ───────────────────────────
    RosterMember("알렉 퀸", _M, _MC, 728, 1976, 6),
    RosterMember("카터 윈터스", _M, _P, 728, 1976, 0),
    RosterMember("코너 셰이드", _M, _P, 728, 1976, 0),
    # ── 남성부 · 15년차 데뷔 ───────────────────────────
    RosterMember("메이슨 크로스", _M, _MC, 780, 2028, 6),
    RosterMember("자비어 헌터", _M, _P, 780, 2028, 0),
    RosterMember("콜 스톰", _M, _P, 780, 2028, 0),
    # ── 남성부 · 16년차 데뷔 ───────────────────────────
    RosterMember("라이언 라이커", _M, _P, 832, 2080, 0),
    RosterMember("카일 헌터", _M, _P, 832, 2080, 0),
    RosterMember("트로이 라이커", _M, _P, 832, 2080, 0),
    # ── 남성부 · 17년차 데뷔 ───────────────────────────
    RosterMember("실라스 블레이즈", _M, _MC, 884, 2132, 6),
    RosterMember("마커스 스톰", _M, _P, 884, 2132, 0),
    RosterMember("카터 바이퍼", _M, _P, 884, 2132, 0),
    # ── 남성부 · 18년차 데뷔 ───────────────────────────
    RosterMember("브레이든 스톤", _M, _MC, 936, 2184, 6),
    RosterMember("브레이든 리드", _M, _P, 936, 2184, 0),
    RosterMember("오스틴 크로스", _M, _P, 936, 2184, 0),
    # ── 남성부 · 19년차 데뷔 ───────────────────────────
    RosterMember("트로이 나이트", _M, _MC, 988, 2236, 6),
    RosterMember("이선 세이지", _M, _P, 988, 2236, 0),
    RosterMember("이선 크로스", _M, _P, 988, 2236, 0),
    # ── 남성부 · 20년차 데뷔 ───────────────────────────
    RosterMember("놀란 레인", _M, _P, 1040, 2288, 0),
    RosterMember("알렉 셰이드", _M, _P, 1040, 2288, 0),
    RosterMember("콜 나이트", _M, _P, 1040, 2288, 0),
    # ── 남성부 · 21년차 데뷔 ───────────────────────────
    RosterMember("마커스 나이트", _M, _MC, 1092, 2340, 6),
    RosterMember("데본 파울러", _M, _P, 1092, 2340, 0),
    RosterMember("타이슨 리드", _M, _P, 1092, 2340, 0),
    # ── 남성부 · 22년차 데뷔 ───────────────────────────
    RosterMember("브라이스 퀸", _M, _MC, 1144, 2392, 6),
    RosterMember("놀란 벨", _M, _P, 1144, 2392, 0),
    RosterMember("콜 헌터", _M, _P, 1144, 2392, 0),
    # ── 남성부 · 23년차 데뷔 ───────────────────────────
    RosterMember("카일 리버스", _M, _MC, 1196, 2444, 6),
    RosterMember("제러드 하트", _M, _P, 1196, 2444, 0),
    RosterMember("코너 스톰", _M, _P, 1196, 2444, 0),
    # ── 남성부 · 24년차 데뷔 ───────────────────────────
    RosterMember("개럿 레인", _M, _P, 1248, 2496, 0),
    RosterMember("제이든 세이지", _M, _P, 1248, 2496, 0),
    RosterMember("카터 브릭스", _M, _P, 1248, 2496, 0),
    # ── 남성부 · 25년차 데뷔 ───────────────────────────
    RosterMember("데본 울프", _M, _MC, 1300, 2548, 6),
    RosterMember("브라이스 리드", _M, _P, 1300, 2548, 0),
    RosterMember("자비어 크로스", _M, _P, 1300, 2548, 0),
    # ── 남성부 · 26년차 데뷔 ───────────────────────────
    RosterMember("루커스 블레이즈", _M, _MC, 1352, 2600, 6),
    RosterMember("자비어 벨", _M, _P, 1352, 2600, 0),
    RosterMember("카일 서머스", _M, _P, 1352, 2600, 0),
    # ── 남성부 · 27년차 데뷔 ───────────────────────────
    RosterMember("잭슨 밴스", _M, _MC, 1404, 2652, 6),
    RosterMember("마커스 프로스트", _M, _P, 1404, 2652, 0),
    RosterMember("맥스 프라이스", _M, _P, 1404, 2652, 0),
    # ── 남성부 · 28년차 데뷔 ───────────────────────────
    RosterMember("마커스 서머스", _M, _P, 1456, 2704, 0),
    RosterMember("실라스 헤이즈", _M, _P, 1456, 2704, 0),
    RosterMember("제이든 스틸", _M, _P, 1456, 2704, 0),
    # ── 남성부 · 29년차 데뷔 ───────────────────────────
    RosterMember("코너 파울러", _M, _MC, 1508, 2756, 6),
    RosterMember("개럿 헌터", _M, _P, 1508, 2756, 0),
    RosterMember("데본 프로스트", _M, _P, 1508, 2756, 0),
    # ── 남성부 · 30년차 데뷔 ───────────────────────────
    RosterMember("자비어 프라이스", _M, _MC, 1560, 2808, 6),
    RosterMember("데릭 벨", _M, _P, 1560, 2808, 0),
    RosterMember("마커스 윈터스", _M, _P, 1560, 2808, 0),
    # ── 여성부 · 0주차 명부 ────────────────────────────
    RosterMember("나오미", _F, _ME, 0, 208, 16),
    RosterMember("나이아 잭스", _F, _ME, 0, 156, 20),
    RosterMember("리브 모건", _F, _ME, 0, 520, 10),
    RosterMember("리아 리플리", _F, _ME, 0, 676, 7),
    RosterMember("베일리", _F, _ME, 0, 260, 15),
    RosterMember("베키 린치", _F, _ME, 0, 156, 17),
    RosterMember("비앙카 벨레어", _F, _ME, 0, 260, 15),
    RosterMember("샬럿 플레어", _F, _ME, 0, 156, 18),
    RosterMember("스테파니 바케르", _F, _ME, 0, 468, 11),
    RosterMember("아스카", _F, _ME, 0, 156, 22),
    RosterMember("알렉사 블리스", _F, _ME, 0, 364, 13),
    RosterMember("이요 스카이", _F, _ME, 0, 312, 14),
    RosterMember("제이드 카길", _F, _ME, 0, 416, 12),
    RosterMember("줄리아", _F, _ME, 0, 520, 10),
    RosterMember("티파니 스트랫턴", _F, _ME, 0, 780, 5),
    RosterMember("AJ 리", _F, _MC, 0, 156, 17),
    RosterMember("B-팹", _F, _MC, 0, 364, 13),
    RosterMember("나탈리아 | 내티", _F, _MC, 0, 156, 22),
    RosterMember("니키 벨라", _F, _MC, 0, 156, 20),
    RosterMember("라이라 발키리아", _F, _MC, 0, 676, 7),
    RosterMember("라켈 로드리게스", _F, _MC, 0, 364, 13),
    RosterMember("래쉬 레전드", _F, _MC, 0, 676, 7),
    RosterMember("레이니 리드", _F, _MC, 0, 780, 5),
    RosterMember("록샌 페레즈", _F, _MC, 0, 936, 2),
    RosterMember("맥신 듀프리", _F, _MC, 0, 676, 7),
    RosterMember("미친", _F, _MC, 0, 260, 15),
    RosterMember("브리 벨라", _F, _MC, 0, 156, 20),
    RosterMember("블레이크 먼로", _F, _MC, 0, 728, 6),
    RosterMember("솔 루카", _F, _MC, 0, 832, 4),
    RosterMember("아이비 나일", _F, _MC, 0, 416, 12),
    RosterMember("제이시 제인", _F, _MC, 0, 624, 8),
    RosterMember("조르딘 그레이스", _F, _MC, 0, 624, 8),
    RosterMember("첼시 그린", _F, _MC, 0, 364, 13),
    RosterMember("캔디스 르래", _F, _MC, 0, 156, 18),
    RosterMember("키아나 제임스", _F, _MC, 0, 676, 7),
    RosterMember("파이퍼 니븐", _F, _MC, 0, 364, 13),
    RosterMember("팰런 헨리", _F, _MC, 0, 572, 9),
    RosterMember("페이지", _F, _MC, 0, 416, 12),
    RosterMember("니키타 라이온스", _F, _P, 0, 780, 5),
    RosterMember("레이나 볼칸", _F, _P, 0, 676, 7),
    RosterMember("레일라 딕스", _F, _P, 0, 780, 5),
    RosterMember("렌 싱클레어", _F, _P, 0, 572, 9),
    RosterMember("롤라 바이스", _F, _P, 0, 728, 6),
    RosterMember("리지 레인", _F, _P, 0, 728, 6),
    RosterMember("마이카 락우드", _F, _P, 0, 884, 3),
    RosterMember("스카일라 레이", _F, _P, 0, 884, 3),
    RosterMember("아리아나 그레이스", _F, _P, 0, 572, 9),
    RosterMember("애드리아나 리조", _F, _P, 0, 780, 5),
    RosterMember("웬디 추", _F, _P, 0, 416, 12),
    RosterMember("이지 데임", _F, _P, 0, 780, 5),
    RosterMember("자리아", _F, _P, 0, 780, 5),
    RosterMember("제이다 파커", _F, _P, 0, 780, 5),
    RosterMember("카르멘 페트로비치", _F, _P, 0, 624, 8),
    RosterMember("칼리 암스트롱", _F, _P, 0, 520, 10),
    RosterMember("켄달 그레이", _F, _P, 0, 884, 3),
    RosterMember("켈라니 조던", _F, _P, 0, 780, 5),
    RosterMember("테이텀 팩슬리", _F, _P, 0, 676, 7),
    RosterMember("티아 헤일", _F, _P, 0, 1040, 0),
    # ── 여성부 · 1년차 데뷔 ────────────────────────────
    RosterMember("스칼렛 서머스", _F, _MC, 52, 1300, 6),
    RosterMember("아리아 베넷", _F, _P, 52, 624, 9),
    RosterMember("엠버 바이퍼", _F, _P, 52, 1300, 0),
    RosterMember("이든 폭스", _F, _P, 52, 1300, 0),
    RosterMember("이자벨 퀸", _F, _P, 52, 1300, 0),
    # ── 여성부 · 2년차 데뷔 ────────────────────────────
    RosterMember("마야 나이트", _F, _MC, 104, 1352, 6),
    RosterMember("델라니 스톰", _F, _P, 104, 1352, 0),
    RosterMember("샨텔 먼로", _F, _P, 104, 936, 4),
    RosterMember("케일라 레인", _F, _P, 104, 1352, 0),
    RosterMember("케일라 하트", _F, _P, 104, 1352, 0),
    # ── 여성부 · 3년차 데뷔 ────────────────────────────
    RosterMember("테사 리드", _F, _MC, 156, 1404, 6),
    RosterMember("PJ 바사", _F, _P, 156, 936, 5),
    RosterMember("마야 스톰", _F, _P, 156, 1404, 0),
    RosterMember("스칼렛 폭스", _F, _P, 156, 1404, 0),
    RosterMember("케일라 스파크", _F, _P, 156, 1404, 0),
    # ── 여성부 · 4년차 데뷔 ────────────────────────────
    RosterMember("케일라 헤이즈", _F, _MC, 208, 1456, 6),
    RosterMember("리아 파울러", _F, _P, 208, 1456, 0),
    RosterMember("이든 벨", _F, _P, 208, 1456, 0),
    RosterMember("제나 스털링", _F, _P, 208, 1248, 0),
    RosterMember("조이 크로스", _F, _P, 208, 1456, 0),
    # ── 여성부 · 5년차 데뷔 ────────────────────────────
    RosterMember("이자벨 블레이즈", _F, _MC, 260, 1508, 6),
    RosterMember("델라니 폭스", _F, _P, 260, 1508, 0),
    RosterMember("마야 크로스", _F, _P, 260, 1508, 0),
    RosterMember("브룩 블레이즈", _F, _P, 260, 1508, 0),
    # ── 여성부 · 6년차 데뷔 ────────────────────────────
    RosterMember("노바 리드", _F, _MC, 312, 1560, 6),
    RosterMember("시에나 나이트", _F, _P, 312, 1560, 0),
    RosterMember("아이비 헌터", _F, _P, 312, 1560, 0),
    RosterMember("카일라 레인", _F, _P, 312, 1560, 0),
    # ── 여성부 · 7년차 데뷔 ────────────────────────────
    RosterMember("이자벨 밴스", _F, _MC, 364, 1612, 6),
    RosterMember("노바 프라이스", _F, _P, 364, 1612, 0),
    RosterMember("미셸 헤이즈", _F, _P, 364, 1612, 0),
    RosterMember("하퍼 프로스트", _F, _P, 364, 1612, 0),
    # ── 여성부 · 8년차 데뷔 ────────────────────────────
    RosterMember("엠버 스틸", _F, _MC, 416, 1664, 6),
    RosterMember("리아 라이커", _F, _P, 416, 1664, 0),
    RosterMember("애슐리 윈터스", _F, _P, 416, 1664, 0),
    RosterMember("테사 케이지", _F, _P, 416, 1664, 0),
    # ── 여성부 · 9년차 데뷔 ────────────────────────────
    RosterMember("브리아나 레인", _F, _MC, 468, 1716, 6),
    RosterMember("리아 헤이즈", _F, _P, 468, 1716, 0),
    RosterMember("이든 울프", _F, _P, 468, 1716, 0),
    RosterMember("조던 리드", _F, _P, 468, 1716, 0),
    # ── 여성부 · 10년차 데뷔 ───────────────────────────
    RosterMember("조이 브릭스", _F, _MC, 520, 1768, 6),
    RosterMember("조이 셰이드", _F, _P, 520, 1768, 0),
    RosterMember("하퍼 서머스", _F, _P, 520, 1768, 0),
    RosterMember("하퍼 폭스", _F, _P, 520, 1768, 0),
    # ── 여성부 · 11년차 데뷔 ───────────────────────────
    RosterMember("리네아 폭스", _F, _MC, 572, 1820, 6),
    RosterMember("마야 레인", _F, _P, 572, 1820, 0),
    RosterMember("시에나 벨", _F, _P, 572, 1820, 0),
    RosterMember("페이 셰이드", _F, _P, 572, 1820, 0),
    # ── 여성부 · 12년차 데뷔 ───────────────────────────
    RosterMember("스칼렛 라이커", _F, _MC, 624, 1872, 6),
    RosterMember("리네아 나이트", _F, _P, 624, 1872, 0),
    RosterMember("엠버 밴스", _F, _P, 624, 1872, 0),
    RosterMember("조이 라이커", _F, _P, 624, 1872, 0),
    # ── 여성부 · 13년차 데뷔 ───────────────────────────
    RosterMember("노바 프로스트", _F, _MC, 676, 1924, 6),
    RosterMember("스칼렛 세이지", _F, _P, 676, 1924, 0),
    RosterMember("애슐리 스틸", _F, _P, 676, 1924, 0),
    RosterMember("이든 서머스", _F, _P, 676, 1924, 0),
    # ── 여성부 · 14년차 데뷔 ───────────────────────────
    RosterMember("애슐리 브릭스", _F, _MC, 728, 1976, 6),
    RosterMember("로렌 리버스", _F, _P, 728, 1976, 0),
    RosterMember("마야 하트", _F, _P, 728, 1976, 0),
    RosterMember("아이비 셰이드", _F, _P, 728, 1976, 0),
    # ── 여성부 · 15년차 데뷔 ───────────────────────────
    RosterMember("아이비 헤이즈", _F, _MC, 780, 2028, 6),
    RosterMember("미셸 벨", _F, _P, 780, 2028, 0),
    RosterMember("카일라 셰이드", _F, _P, 780, 2028, 0),
    RosterMember("하퍼 브릭스", _F, _P, 780, 2028, 0),
    # ── 여성부 · 16년차 데뷔 ───────────────────────────
    RosterMember("리아 프로스트", _F, _MC, 832, 2080, 6),
    RosterMember("브리아나 퀸", _F, _P, 832, 2080, 0),
    RosterMember("세라 케이지", _F, _P, 832, 2080, 0),
    RosterMember("조던 스틸", _F, _P, 832, 2080, 0),
    # ── 여성부 · 17년차 데뷔 ───────────────────────────
    RosterMember("로렌 크로스", _F, _MC, 884, 2132, 6),
    RosterMember("델라니 벨", _F, _P, 884, 2132, 0),
    RosterMember("미셸 스톤", _F, _P, 884, 2132, 0),
    RosterMember("미셸 파울러", _F, _P, 884, 2132, 0),
    # ── 여성부 · 18년차 데뷔 ───────────────────────────
    RosterMember("브리아나 나이트", _F, _MC, 936, 2184, 6),
    RosterMember("리아 하트", _F, _P, 936, 2184, 0),
    RosterMember("아이비 나이트", _F, _P, 936, 2184, 0),
    RosterMember("테사 밴스", _F, _P, 936, 2184, 0),
    # ── 여성부 · 19년차 데뷔 ───────────────────────────
    RosterMember("케일라 스톤", _F, _MC, 988, 2236, 6),
    RosterMember("브룩 서머스", _F, _P, 988, 2236, 0),
    RosterMember("이든 파울러", _F, _P, 988, 2236, 0),
    RosterMember("하퍼 세이지", _F, _P, 988, 2236, 0),
    # ── 여성부 · 20년차 데뷔 ───────────────────────────
    RosterMember("델라니 세이지", _F, _MC, 1040, 2288, 6),
    RosterMember("노바 스틸", _F, _P, 1040, 2288, 0),
    RosterMember("델라니 스틸", _F, _P, 1040, 2288, 0),
    RosterMember("로렌 프라이스", _F, _P, 1040, 2288, 0),
    # ── 여성부 · 21년차 데뷔 ───────────────────────────
    RosterMember("로렌 헌터", _F, _MC, 1092, 2340, 6),
    RosterMember("이자벨 스톤", _F, _P, 1092, 2340, 0),
    RosterMember("조던 리버스", _F, _P, 1092, 2340, 0),
    RosterMember("케일라 블레이즈", _F, _P, 1092, 2340, 0),
    # ── 여성부 · 22년차 데뷔 ───────────────────────────
    RosterMember("엠버 프라이스", _F, _MC, 1144, 2392, 6),
    RosterMember("마야 파울러", _F, _P, 1144, 2392, 0),
    RosterMember("브룩 나이트", _F, _P, 1144, 2392, 0),
    RosterMember("시에나 프라이스", _F, _P, 1144, 2392, 0),
    # ── 여성부 · 23년차 데뷔 ───────────────────────────
    RosterMember("엠버 크로스", _F, _MC, 1196, 2444, 6),
    RosterMember("스칼렛 하트", _F, _P, 1196, 2444, 0),
    RosterMember("아이비 프로스트", _F, _P, 1196, 2444, 0),
    RosterMember("애슐리 스톤", _F, _P, 1196, 2444, 0),
    # ── 여성부 · 24년차 데뷔 ───────────────────────────
    RosterMember("시에나 서머스", _F, _MC, 1248, 2496, 6),
    RosterMember("마야 밴스", _F, _P, 1248, 2496, 0),
    RosterMember("세라 크로스", _F, _P, 1248, 2496, 0),
    RosterMember("카일라 프로스트", _F, _P, 1248, 2496, 0),
    # ── 여성부 · 25년차 데뷔 ───────────────────────────
    RosterMember("브리아나 폭스", _F, _MC, 1300, 2548, 6),
    RosterMember("로렌 윈터스", _F, _P, 1300, 2548, 0),
    RosterMember("브리아나 리드", _F, _P, 1300, 2548, 0),
    RosterMember("페이 블레이즈", _F, _P, 1300, 2548, 0),
    # ── 여성부 · 26년차 데뷔 ───────────────────────────
    RosterMember("리아 울프", _F, _MC, 1352, 2600, 6),
    RosterMember("로렌 스틸", _F, _P, 1352, 2600, 0),
    RosterMember("시에나 블레이즈", _F, _P, 1352, 2600, 0),
    RosterMember("애슐리 울프", _F, _P, 1352, 2600, 0),
    # ── 여성부 · 27년차 데뷔 ───────────────────────────
    RosterMember("조이 스톰", _F, _MC, 1404, 2652, 6),
    RosterMember("미셸 윈터스", _F, _P, 1404, 2652, 0),
    RosterMember("이든 퀸", _F, _P, 1404, 2652, 0),
    RosterMember("카일라 나이트", _F, _P, 1404, 2652, 0),
    # ── 여성부 · 28년차 데뷔 ───────────────────────────
    RosterMember("마야 블레이즈", _F, _MC, 1456, 2704, 6),
    RosterMember("노바 레인", _F, _P, 1456, 2704, 0),
    RosterMember("리네아 벨", _F, _P, 1456, 2704, 0),
    RosterMember("시에나 프로스트", _F, _P, 1456, 2704, 0),
    # ── 여성부 · 29년차 데뷔 ───────────────────────────
    RosterMember("하퍼 프라이스", _F, _MC, 1508, 2756, 6),
    RosterMember("브리아나 밴스", _F, _P, 1508, 2756, 0),
    RosterMember("시에나 퀸", _F, _P, 1508, 2756, 0),
    RosterMember("조이 헌터", _F, _P, 1508, 2756, 0),
    # ── 여성부 · 30년차 데뷔 ───────────────────────────
    RosterMember("노바 라이커", _F, _MC, 1560, 2808, 6),
    RosterMember("리네아 셰이드", _F, _P, 1560, 2808, 0),
    RosterMember("조이 폭스", _F, _P, 1560, 2808, 0),
    RosterMember("테사 스톤", _F, _P, 1560, 2808, 0),
)


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
