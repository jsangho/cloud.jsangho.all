"""링 밖의 사람들을 명부로 찍어 낸다 (하네스 §3-D93).

원본은 kayfabe의 `_docs/wwe_non_wrestler.csv`(사용자가 채운 63행)이고, 산출물은
`wwe_game/domain/constants/staff.py`다. **스포크끼리 import하지 않는다**(§2-D3) —
`generate_roster.py`가 선수 명부를 베껴 오는 것과 같은 자리다.

## 역할은 첫 칸이 아니라 목록이다

`role` 칸은 `|`로 여러 직함이 온다 (`RAW GM | Trainer | Producer`). 게임이 쓰는 역할만
골라 담고 나머지(프로듀서·트레이너)는 버린다 — **쓰지 않는 값을 들고 있으면 언젠가
그것으로 규칙을 짜게 된다.**

원본에 오타가 있다(`Commnetator` · `Backstage Inerviewer` · `Back Interviewer`).
**고쳐서 읽되 원본은 안 고친다** — 사용자가 채운 파일이 유일한 원본이고, 여기서 고치면
다음에 받는 파일과 어긋난다.

## Evolve는 담되 쓰지 않는다

게임의 브랜드 축은 셋뿐이다(`Brand`). Evolve 사람들은 `brand="evolve"`로 담기지만
`for_brand()`가 정확히 일치하는 브랜드만 돌려주므로 화면에는 안 나온다 — 게임에
Evolve 방송이 생기면 그때 이미 데이터가 있다.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = APP_DIR.parents[0] / "kayfabe" / "_docs" / "wwe_non_wrestler.csv"
GAME_DATA_PATH = APP_DIR / "_docs" / "roster_game_data.csv"
"""선수의 한글 표기를 여기서 가져온다 (§3-D91의 그 파일).

**매니저의 담당이 영문 이름으로 적혀 있다**(`Trick Williams`). 게임의 명부는 한글이라
(§3-D13) 그대로 두면 영영 안 맞는다 — 찍어 낼 때 옮긴다.
"""
OUT_PATH = APP_DIR / "domain" / "constants" / "staff.py"

SECTION_BRAND: dict[str, str] = {
    "Executives": "",
    "RAW": "raw",
    "Raw Referee": "raw",
    "Smackdown": "smackdown",
    "Smackdown Referee": "smackdown",
    "NXT": "nxt",
    "NXT Referee": "nxt",
    "Evolve": "evolve",
    "Producer (M)": "",
    "Producer (W)": "",
}
"""섹션 → 브랜드. **집행부는 브랜드가 없다** — 회사의 사람이지 방송의 사람이 아니다."""

ROLE_ALIAS: dict[str, str] = {
    "commentator": "COMMENTATOR",
    "commnetator": "COMMENTATOR",  # 원본 오타
    "ring announcer": "RING_ANNOUNCER",
    "backstage interviewer": "INTERVIEWER",
    "backstage inerviewer": "INTERVIEWER",  # 원본 오타
    "back interviewer": "INTERVIEWER",  # 원본 축약
    "manager": "MANAGER",
    "producer": "PRODUCER",
}
"""직함 → 게임이 쓰는 역할. 여기 없는 직함(프로듀서·트레이너·부사장)은 버린다."""

GENDER_ALIAS = {"M": "_M", "W": "_F"}
"""**`W`가 여성이다** (2026-08-19 사용자 표기). 선수 명부는 `female`을 쓰는데 이 파일은
한 글자라, 여기서 맞춰 준다."""

HEADER = '''"""링 밖의 사람들 — 집행부 · GM · 해설 · 링 아나운서 · 인터뷰어 · 심판 · 매니저.

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
    PRODUCER = "producer"
    """경기를 기획한 사람 (§3-D94). **리포트의 별점 뒤에 이름이 남는다.**"""


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
_PRO = StaffRole.PRODUCER

STAFF: tuple[StaffMember, ...] = (
'''

FOOTER = ''')


def for_brand(brand: str, role: StaffRole) -> tuple[StaffMember, ...]:
    """그 브랜드의 그 역할들. **정확히 일치하는 브랜드만** — Evolve는 안 섞인다."""
    return tuple(m for m in STAFF if m.brand == brand and m.has(role))


def executives() -> tuple[StaffMember, ...]:
    """회사의 사람들. 브랜드가 없다."""
    return tuple(m for m in STAFF if m.has(StaffRole.EXECUTIVE))


def managers() -> tuple[StaffMember, ...]:
    """매니저 전부 — **브랜드를 안 가린다.** 담당 선수를 따라다니기 때문이다."""
    return tuple(m for m in STAFF if m.has(StaffRole.MANAGER))


def producers(gender: Gender | None = None) -> tuple[StaffMember, ...]:
    """프로듀서 전부 (§3-D94). **브랜드를 안 가린다** — 회사의 제작진이다.

    `gender`를 주면 그쪽만 — 여성 제작진이 여성부에 더 자주 붙게 하는 자리다.
    """
    found = tuple(m for m in STAFF if m.has(StaffRole.PRODUCER))
    if gender is None:
        return found
    return tuple(m for m in found if m.gender is gender)
'''

ROLE_CONST = {
    "EXECUTIVE": "_EXEC",
    "GM": "_GM",
    "COMMENTATOR": "_COM",
    "RING_ANNOUNCER": "_ANN",
    "INTERVIEWER": "_INT",
    "REFEREE": "_REF",
    "MANAGER": "_MAN",
    "PRODUCER": "_PRO",
}


def read_rows() -> list[tuple[str, dict[str, str]]]:
    """(섹션, 행). **`skipinitialspace`가 필요하다** — 원본에 따옴표 앞 빈칸이 있다."""
    text = CSV_PATH.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), skipinitialspace=True))
    header, *body = rows
    section = ""
    out: list[tuple[str, dict[str, str]]] = []
    for row in body:
        if not row or not row[0].strip():
            continue
        if row[0].startswith("#"):
            section = row[0].lstrip("# ").strip()
            if section not in SECTION_BRAND:
                raise SystemExit(f"모르는 섹션 {section!r} — SECTION_BRAND에 넣으세요")
            continue
        padded = row + [""] * (len(header) - len(row))
        out.append((section, dict(zip(header, padded, strict=False))))
    return out


def korean_names() -> dict[str, str]:
    """영문 이름 → 한글 표기. 선수 이름만 담는다 — 스테이블은 영문 그대로 쓴다."""
    rows = csv.DictReader(io.StringIO(GAME_DATA_PATH.read_text(encoding="utf-8-sig")))
    found: dict[str, str] = {}
    for row in rows:
        name = (row.get("name") or "").strip()
        korean = (row.get("korean_name") or "").strip()
        if name and korean:
            # `|`는 활동명 이력이다 (§3-D54) — **처음 활동명**으로 잡는다.
            found[name] = korean.split("|")[0].strip()
    return found


def roles_of(section: str, raw: str) -> tuple[str, ...]:
    """그 사람이 게임에서 맡는 역할들.

    **섹션이 먼저 말한다** — 심판 섹션의 `Senior`는 직함이지 역할이 아니고, 집행부
    섹션의 긴 직함도 마찬가지다. 그 위에 `role` 칸에서 알아보는 역할을 더한다.
    """
    found: list[str] = []
    if section.endswith("Referee"):
        found.append("REFEREE")
    elif section == "Executives":
        found.append("EXECUTIVE")
    for part in raw.split("|"):
        token = part.strip().lower()
        if token.endswith(" gm"):
            found.append("GM")
            continue
        alias = ROLE_ALIAS.get(token)
        if alias is not None:
            found.append(alias)
    return tuple(dict.fromkeys(found))


def render(members: list[tuple[str, dict[str, str]]]) -> str:
    korean = korean_names()
    lines: list[str] = []
    seen = ""
    for section, row in members:
        roles = roles_of(section, row["role"])
        if not roles:
            # 역할이 없으면 게임이 쓸 자리가 없다 — 담지 않는다.
            continue
        if section != seen:
            seen = section
            lines.append(f"    # ── {section} " + "─" * max(1, 40 - len(section)))
        name = row["korean_ring_name"].strip()
        gender = GENDER_ALIAS.get(row["gender"].strip())
        if gender is None:
            raise SystemExit(f"{name}: 모르는 성별 {row['gender']!r}")
        title = row["role"].strip().replace('"', '\\"')
        manages = row["Wrestler&Team&Stable"].strip()
        # 선수면 한글로 옮기고, 스테이블이면 그대로 둔다 — 명부의 `stable`이 영문이다.
        manages = korean.get(manages, manages).replace('"', '\\"')
        senior = "Senior" in row["role"]
        listed = ", ".join(ROLE_CONST[r] for r in roles)
        tail = f"({listed},)" if len(roles) == 1 else f"({listed})"
        lines.append(
            f'    StaffMember("{name}", {tail}, "{SECTION_BRAND[section]}", {gender},'
            f' "{title}", "{manages}", {senior}),'
        )
    return HEADER + "\n".join(lines) + "\n" + FOOTER


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="파일에 쓴다")
    args = parser.parse_args()

    rows = read_rows()
    text = render(rows)
    kept = text.count("StaffMember(")
    print(f"원본 {len(rows)}행 → 명부 {kept}명")
    counts: dict[str, int] = {}
    for section, row in rows:
        for role in roles_of(section, row["role"]):
            counts[role] = counts.get(role, 0) + 1
    print("  역할:", " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if args.write:
        OUT_PATH.write_text(text, encoding="utf-8")
        print(f"\n{OUT_PATH.relative_to(APP_DIR.parents[1])} 갱신")
    else:
        print("\n(미리보기 — 쓰려면 --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
