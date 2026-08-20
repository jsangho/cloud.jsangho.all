"""0주차의 챔피언들 — **판마다 같다** (하네스 §3-D94 · 2026-08-19 사용자 명단).

§3-D38이 배경 계보를 시드에서 되짚게 만들면서 **첫 챔피언까지 굴려 뽑았다.** 그래서
같은 세계를 새로 시작할 때마다 벨트의 주인이 달랐고, 오늘의 WWE와도 무관했다.

사용자가 열여덟 벨트의 **현 챔피언 명단**을 줬다 — *"무조건 시작할 때 이 명단인 걸로
해줘."* 여기가 그 명단이고, 계보의 첫 재위만 이걸 쓴다. **그 뒤는 그대로 굴린다** —
2년차의 챔피언까지 정해 두면 그건 계보가 아니라 각본이다.

## 태그 벨트는 둘이 든다

`title_scene.PARTNER_JOIN`(` & `)으로 이어 적는다 (§3-D57). 팀 이름(더 비전 · 더
통간스 · 페이탈 인플루언스)이 아니라 **사람 이름**으로 담는 이유: 계보가 사람을 다루고
(승계·부상·은퇴), 팀 이름은 `holder_label()`이 명부에서 되짚어 붙인다.

## 이름은 명부의 표기를 따른다

사용자 메시지의 *라켈 로드리게즈*는 명부에 **라켈 로드리게스**로 있다(사용자가 채운
`roster_game_data.csv` 기준 · §3-D91). 계보는 이름으로 사람을 찾으므로 표기가 어긋나면
그 벨트만 조용히 굴림으로 떨어진다 — 명부 쪽으로 맞춘다.
"""

from __future__ import annotations

from typing import Final

from wwe_game.domain.value_objects.title import Title

PARTNER_JOIN: Final = " & "
"""태그 벨트의 두 이름을 잇는 문자열. `title_scene`의 값과 같아야 한다 — 테스트가 잠근다."""

OPENING_CHAMPIONS: Final[dict[Title, str]] = {
    # ── RAW ──
    Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP: "로만 레인즈",
    Title.WOMENS_WORLD_CHAMPIONSHIP: "리브 모건",
    Title.INTERCONTINENTAL_CHAMPIONSHIP: "채드 게이블",
    Title.WWE_WOMENS_INTERCONTINENTAL_CHAMPIONSHIP: "라켈 로드리게스",
    Title.WORLD_TAG_TEAM_CHAMPIONSHIP: "브론 브레이커 & 오스틴 씨어리",
    # ── 스맥다운 ──
    Title.UNDISPUTED_WWE_CHAMPIONSHIP: "CM 펑크",
    Title.WWE_WOMENS_CHAMPIONSHIP: "첼시 그린",
    Title.UNITED_STATES_CHAMPIONSHIP: "배런 코빈",
    Title.WWE_WOMENS_UNITED_STATES_CHAMPIONSHIP: "제이시 제인",
    Title.WWE_TAG_TEAM_CHAMPIONSHIP: "타마 통가 & 탈라 통가",
    # ── NXT ──
    Title.NXT_CHAMPIONSHIP: "토니 디안젤로",
    Title.NXT_WOMENS_CHAMPIONSHIP: "켄달 그레이",
    Title.NXT_NORTH_AMERICAN_CHAMPIONSHIP: "마일스 본",
    Title.NXT_WOMENS_NORTH_AMERICAN_CHAMPIONSHIP: "자리아",
    Title.NXT_TAG_TEAM_CHAMPIONSHIP: "마일스 본 & 테비언 하이츠",
    Title.WWE_SPEED_CHAMPIONSHIP: "렉시스 킹",
    Title.WWE_WOMENS_SPEED_CHAMPIONSHIP: "렌 싱클레어",
    # ── 브랜드 공용 ──
    Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP: "팰런 헨리 & 레이니 리드",
}
"""벨트 → 0주차의 주인. **열여덟 전부 채운다** — 하나라도 비면 그 벨트만 굴림으로
시작해서, 새 판마다 주인이 달라지는 자리가 하나 남는다(테스트가 잠근다).

마일스 본이 두 번 나오는 것은 실제 그대로다 — 노스 아메리칸과 NXT 태그를 함께 들고 있다.
"""
