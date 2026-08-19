"""링 밖의 사람들 — 집행부 · GM · 해설 · 링 아나운서 · 인터뷰어 · 심판 · 매니저.

**이 파일은 생성물이다.** 손으로 고치지 말고 `scripts/generate_staff.py`를 다시 돌린다.
원본은 사용자가 채운 `kayfabe/_docs/wwe_non_wrestler.csv`다 (하네스 §3-D93).

## 이 사람들이 하는 일

| 역할 | 어디에 나오나 |
|---|---|
| `EXECUTIVE` | 중대 발표 뉴스 · **재계약 협상의 상대** (§3-D84) |
| `GM` | 브랜드의 스토리 총괄 — 경기 정보와 대립 기사에 이름이 선다 |
| `COMMENTATOR` | 경기 전 정보창 · 경기 중 해설 (§3-D81-5) |
| `RING_ANNOUNCER` | **챔피언십 경기의 소개** — 공은 그 뒤에 울린다 |
| `INTERVIEWER` | 백스테이지 인터뷰가 곧 기사다 — 기사에 이름이 남는다 (§3-D87) |
| `REFEREE` | 경기 정보창 · 가끔 기사에 인용된다 |
| `MANAGER` | 담당 선수의 경기 정보에 `w/`로 붙는다 |

**판정에 닿지 않는다.** 여기 있는 누구도 승패·별점·부상을 건드리지 않는다 — 바뀌는
것은 그 밤이 어떻게 보이고 어떻게 적히는가뿐이다(§3-D88·D91과 같은 선).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.value_objects.wrestler_identity import Gender


class StaffRole(StrEnum):
    EXECUTIVE = "executive"
    GM = "gm"
    COMMENTATOR = "commentator"
    RING_ANNOUNCER = "ring_announcer"
    INTERVIEWER = "interviewer"
    REFEREE = "referee"
    MANAGER = "manager"


@dataclass(frozen=True)
class StaffMember:
    """링 밖의 한 사람. **이름은 한글 표기다** — 화면과 기사가 그대로 쓴다."""

    name: str
    roles: tuple[StaffRole, ...]
    """한 사람이 둘을 겸한다 — 윌리엄 리갈은 집행부이면서 매니저다."""
    brand: str
    """`raw` · `smackdown` · `nxt` · `evolve`. **집행부는 빈 문자열**이다."""
    gender: Gender
    title: str = ""
    """원본의 직함 그대로. 집행부 발표에 "○○ ○○○" 하고 붙일 때 쓴다."""
    manages: str = ""
    """매니저가 맡은 선수 또는 스테이블 이름 (원본 `Wrestler&Team&Stable`)."""
    senior: bool = False
    """시니어 심판인가. **타이틀전에는 이쪽이 선다.**"""

    def has(self, role: StaffRole) -> bool:
        return role in self.roles


_M, _F = Gender.MALE, Gender.FEMALE
_EXEC = StaffRole.EXECUTIVE
_GM = StaffRole.GM
_COM = StaffRole.COMMENTATOR
_ANN = StaffRole.RING_ANNOUNCER
_INT = StaffRole.INTERVIEWER
_REF = StaffRole.REFEREE
_MAN = StaffRole.MANAGER

STAFF: tuple[StaffMember, ...] = (
    # ── Executives ──────────────────────────────
    StaffMember(
        "닉 칸", (_EXEC,), "", _M, "President & Chief Revenue Officer", "", False
    ),
    StaffMember("트리플 H", (_EXEC,), "", _M, "Chief Commercial Officer", "", False),
    StaffMember("브루스 프리차드", (_EXEC,), "", _M, "Executive", "", False),
    StaffMember(
        "숀 마이클스",
        (_EXEC,),
        "",
        _M,
        "Senior Vice President of Talent Development & Creative | NXT Creative Director",
        "",
        True,
    ),
    StaffMember(
        "윌리엄 리갈",
        (_EXEC, _MAN),
        "",
        _M,
        "Vice President of Talent Development & Head of Global Recruiting | Manager",
        "Birthright",
        False,
    ),
    # ── RAW ─────────────────────────────────────
    StaffMember(
        "애덤 피어스", (_GM,), "raw", _M, "RAW GM | Trainer | Producer", "", False
    ),
    StaffMember(
        "마이클 콜",
        (_COM,),
        "raw",
        _M,
        "Commentator | Vice President of Announcing",
        "",
        False,
    ),
    StaffMember("코리 그레이브스", (_COM,), "raw", _M, "Commnetator", "", False),
    StaffMember("알리시아 테일러", (_ANN,), "raw", _F, "Ring Announcer", "", False),
    StaffMember("캐시 켈리", (_INT,), "raw", _F, "Back Interviewer", "", False),
    StaffMember(
        "사라 슈라이버", (_INT,), "raw", _F, "Backstage Interviewer", "", False
    ),
    StaffMember("재키 레드몬드", (_INT,), "raw", _F, "Backstage Inerviewer", "", False),
    StaffMember(
        "폴 헤이먼", (_MAN,), "raw", _M, "Manager | Producer", "The Vision", False
    ),
    # ── Raw Referee ─────────────────────────────
    StaffMember("채드 패튼", (_REF,), "raw", _M, "Senior", "", True),
    StaffMember("다닐로 안피비오", (_REF,), "raw", _M, "", "", False),
    StaffMember("에디 오렝고", (_REF,), "raw", _M, "", "", False),
    StaffMember("제시카 카", (_REF,), "raw", _F, "", "", False),
    StaffMember(
        "존 콘", (_REF,), "raw", _M, "Vice President of Talent Relations", "", False
    ),
    StaffMember("로드 자파타", (_REF,), "raw", _M, "", "", False),
    StaffMember("숀 베넷", (_REF,), "raw", _M, "", "", False),
    # ── Smackdown ───────────────────────────────
    StaffMember(
        "닉 알디스", (_GM,), "smackdown", _M, "Smackdown GM | Producer", "", False
    ),
    StaffMember("웨이드 바렛", (_COM,), "smackdown", _M, "Commentator", "", False),
    StaffMember("조 테시토레", (_COM,), "smackdown", _M, "Commentator", "", False),
    StaffMember(
        "릴리안 가르시아", (_ANN,), "smackdown", _F, "Ring Announcer", "", False
    ),
    StaffMember("마크 내쉬", (_ANN,), "smackdown", _M, "Ring Announcer", "", False),
    StaffMember(
        "바이런 색스턴", (_INT,), "smackdown", _M, "Backstage Interviewer", "", False
    ),
    StaffMember(
        "메간 모란트",
        (_INT,),
        "smackdown",
        _F,
        "Backstage Interviewer | WWE Youtube Host",
        "",
        False,
    ),
    StaffMember("하쿠", (_MAN,), "smackdown", _M, "Manager", "The Tongans", False),
    StaffMember("릴 야티", (_MAN,), "smackdown", _M, "Manager", "트릭 윌리엄스", False),
    # ── Smackdown Referee ───────────────────────
    StaffMember("찰스 로빈슨", (_REF,), "smackdown", _M, "Senior", "", True),
    StaffMember("댄 엥글러", (_REF,), "smackdown", _M, "", "", False),
    StaffMember("다파니 로숀", (_REF,), "smackdown", _F, "", "", False),
    StaffMember("개리 윌슨", (_REF,), "smackdown", _M, "", "", False),
    StaffMember("제이슨 에이어스", (_REF,), "smackdown", _M, "", "", False),
    StaffMember("라이언 트란", (_REF,), "smackdown", _M, "", "", False),
    # ── NXT ─────────────────────────────────────
    StaffMember("로버트 스톤", (_GM,), "nxt", _M, "NXT GM | Producer", "", False),
    StaffMember("부커 T", (_COM,), "nxt", _M, "Commentator", "", False),
    StaffMember("빅 조셉", (_COM,), "nxt", _M, "Commentator", "", False),
    StaffMember("블레이크 하워드", (_ANN,), "nxt", _M, "Ring Announcer", "", False),
    StaffMember("마이크 롬", (_ANN,), "nxt", _M, "Ring Announcer", "", False),
    StaffMember("핀레이", (_MAN,), "nxt", _M, "Manager", "Birthright", False),
    # ── NXT Referee ─────────────────────────────
    StaffMember("아드리안 버틀러", (_REF,), "nxt", _M, "Senior | Producer", "", True),
    StaffMember("칩 대닝", (_REF,), "nxt", _M, "", "", False),
    StaffMember("댈러스 어빈", (_REF,), "nxt", _M, "", "", False),
    StaffMember("데렉 샌더스", (_REF,), "nxt", _M, "", "", False),
    StaffMember("펠릭스 페르난데즈", (_REF,), "nxt", _M, "", "", False),
    StaffMember("제레미 마커스", (_REF,), "nxt", _M, "", "", False),
    StaffMember("조이 곤잘레즈", (_REF,), "nxt", _M, "", "", False),
    StaffMember("케이티 레이놀즈", (_REF,), "nxt", _F, "", "", False),
    StaffMember("빅토리아 디에리코", (_REF,), "nxt", _F, "", "", False),
    # ── Evolve ──────────────────────────────────
    StaffMember("티모시 대처", (_GM,), "evolve", _M, "Evolve GM", "", False),
    StaffMember(
        "츄이 마르티네즈", (_INT,), "evolve", _M, "Backstage Interviewer", "", False
    ),
    StaffMember("피터 로젠버그", (_COM,), "evolve", _M, "Commentator", "", False),
    StaffMember(
        "라이언 카츠", (_ANN,), "evolve", _M, "Ring Announcer | Producer", "", False
    ),
)


def for_brand(brand: str, role: StaffRole) -> tuple[StaffMember, ...]:
    """그 브랜드의 그 역할들. **정확히 일치하는 브랜드만** — Evolve는 안 섞인다."""
    return tuple(m for m in STAFF if m.brand == brand and m.has(role))


def executives() -> tuple[StaffMember, ...]:
    """회사의 사람들. 브랜드가 없다."""
    return tuple(m for m in STAFF if m.has(StaffRole.EXECUTIVE))


def managers() -> tuple[StaffMember, ...]:
    """매니저 전부 — **브랜드를 안 가린다.** 담당 선수를 따라다니기 때문이다."""
    return tuple(m for m in STAFF if m.has(StaffRole.MANAGER))
