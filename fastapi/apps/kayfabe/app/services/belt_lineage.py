"""현존 벨트와 그 옛 이름 (계보표).

## 왜 필요한가

`real_title_catalog`의 획득 이력은 **그때 그 벨트가 불리던 이름**으로 적혀 있고
(`WWE Championship`·`Raw Women's Championship`), 현 챔피언 보드
(`current_championship_catalog`)는 **지금 이름**으로 적혀 있다
(`Undisputed WWE Championship`·`Women's World Championship`). 이름만으로 맞추면
WWE 챔피언십 45회가 "없는 벨트"로 빠지고, 현 벨트는 개명 이후 몇 회만 든 채로 보인다.

## 세 갈래로 분류한다 — 조용히 버리는 이름이 없게

- `BELT_LINEAGE` — 개명·통합으로 **현 벨트가 이어받은** 이름. 획득 횟수를 합친다.
- `RETIRED_BELTS` — 폐지됐거나 보드에 없는 벨트. 사유를 함께 적고 집계에서 뺀다.
- 그 외 — 현 벨트 이름 그대로.

`test_belt_lineage.py`가 `REAL_TITLE_ACQUISITIONS`의 모든 벨트 이름이 셋 중 하나에
들어가는지 검사한다. 카탈로그에 새 이름이 들어오면 **테스트가 먼저 깨진다.**

## 현존의 기준은 현 챔피언 보드다

"지금 있는 벨트"는 `WWE_BRAND_CHAMPIONS` 20행이 정한다 — 그 표는 위키
`List of current champions in WWE`와 대조해 맞춰 둔 것이다(`wiki_belt_names` 참조).
여기서 벨트를 늘리거나 줄이지 않는다. 보드에 없는 벨트는 보드를 고쳐서 넣는다.

## 합치지 않은 것

같은 자리를 물려받았다고 볼 여지가 있어도 **계보가 하나로 좁혀지지 않으면 합치지
않는다.** `Undisputed WWE Tag Team Championship`이 그렇다 — Raw·SmackDown 태그
벨트를 하나로 묶었다가 다시 둘로 갈라졌으므로 어느 쪽 후신이라고 단정할 수 없다.
`WWE Divas Championship`·`NXT UK Women's Championship`도 위키가 별개 계보로 센다.
"""

from __future__ import annotations

from kayfabe.app.services.current_championship_catalog import WWE_BRAND_CHAMPIONS

#: 옛 이름 → 지금 이름. 값은 반드시 `current_belt_names()` 안에 있어야 한다.
BELT_LINEAGE: dict[str, str] = {
    # 표기만 다르다 — 보드가 `WWE` 접두사를 붙여 부른다.
    "Intercontinental Championship": "WWE Intercontinental Championship",
    "United States Championship": "WWE United States Championship",
    "Women's Tag Team Championship": "WWE Women's Tag Team Championship",
    # 개명·통합.
    "WWE Championship": "Undisputed WWE Championship",  # 2022 통합 후 개명
    "Universal Championship": "Undisputed WWE Championship",  # 2022 통합되며 소멸
    "Raw Women's Championship": "Women's World Championship",  # 2023 개명
    "SmackDown Women's Championship": "WWE Women's Championship",  # 2023 개명
    "Raw Tag Team Championship": "World Tag Team Championship",  # 2024 개명
    "SmackDown Tag Team Championship": "WWE Tag Team Championship",  # 2024 개명
}

#: 집계에서 빼는 벨트 → 사유. 화면이 이 사유를 그대로 보여 준다.
RETIRED_BELTS: dict[str, str] = {
    "ECW Championship": "2010년 ECW 브랜드와 함께 폐지",
    "WWE Divas Championship": "2016년 폐지 — 위키도 별개 계보로 센다",
    "NXT Cruiserweight Championship": "2022년 폐지",
    "NXT UK Women's Championship": "2022년 NXT UK 종료 — 별개 계보로 둔다",
    "NXT Heritage Cup": "현 챔피언 보드에 없다",
    "WWE Crown Jewel Championship": "현 챔피언 보드에 없다",
    "Undisputed WWE Tag Team Championship": (
        "Raw·SmackDown 태그 벨트를 묶었다가 다시 갈라져 후신을 하나로 못 정한다"
    ),
}


def current_belt_names() -> list[str]:
    """현 챔피언 보드 순서 그대로의 벨트 이름."""
    return [
        title["belt_name"] for brand in WWE_BRAND_CHAMPIONS for title in brand["titles"]
    ]


def resolve_belt(belt_name: str) -> str | None:
    """획득 이력의 벨트 이름 → 현 벨트 이름. 현존하지 않으면 `None`."""
    current = set(current_belt_names())
    if belt_name in current:
        return belt_name
    successor = BELT_LINEAGE.get(belt_name)
    if successor in current:
        return successor
    return None


def former_names(belt_name: str) -> list[str]:
    """그 벨트가 물려받은 옛 이름 (가나다/알파벳 순)."""
    return sorted(old for old, new in BELT_LINEAGE.items() if new == belt_name)


def retirement_reason(belt_name: str) -> str:
    """집계에서 빠진 사유. 표에 없는 이름이면 분류되지 않았다는 뜻이다."""
    return RETIRED_BELTS.get(belt_name, "계보표에 분류되지 않은 이름")
