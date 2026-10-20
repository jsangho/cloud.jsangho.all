"""미확정 경기 표가 **아직 사실인지** 본다.

이 표는 자동 예측을 건너뛰게 만든다. 위키가 실명을 채우고 픽스처가 갱신되면 그
항목은 더 이상 사실이 아닌데, 그때도 스크립트는 계속 건너뛴다 — 그 대회는 영영
예측이 안 생기고 아무도 이유를 모른다. **건너뛰는 규칙은 조용히 낡으면 안 된다.**

픽스처를 못 찾으면 건너뛴다 — 백엔드만 체크아웃한 환경에서 도는 일이 있다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kayfabe.app.services.ple_fixture_file import read_event_cards
from kayfabe.app.services.unconfirmed_match_cards import (
    UNCONFIRMED_MATCH_CARDS,
    unconfirmed_match_keys,
)

_FIXTURE = (
    Path(__file__).resolve().parents[4].parents[1]
    / "www"
    / "lib"
    / "wwe-ple-matches.ts"
)


@pytest.fixture(scope="module")
def source() -> str:
    if not _FIXTURE.exists():
        pytest.skip(f"프론트 픽스처가 없다: {_FIXTURE}")
    return _FIXTURE.read_text(encoding="utf-8")


def test_every_listed_match_still_exists_in_the_fixture(source: str) -> None:
    """경기가 사라졌으면 표가 낡은 것이다."""
    missing: list[str] = []
    for slug, matches in UNCONFIRMED_MATCH_CARDS.items():
        cards = read_event_cards(source, slug)
        assert cards is not None, f"픽스처에 항목이 없는 대회: {slug}"
        present = {card.id for card in cards}
        missing += [f"{slug}/{key}" for key in matches if key not in present]
    assert not missing, "픽스처에서 사라진 경기: " + " · ".join(missing)


def test_the_names_are_still_the_placeholders_we_recorded(source: str) -> None:
    """**이 테스트가 표를 낡지 않게 하는 장치다.**

    위키가 실명을 채우면 픽스처의 이름이 달라진다. 그 순간 여기가 빨개지고, 사람이
    표에서 그 줄을 지워야 자동 예측이 다시 그 경기를 본다.
    """
    drifted: list[str] = []
    for slug, matches in UNCONFIRMED_MATCH_CARDS.items():
        cards = {card.id: card for card in read_event_cards(source, slug) or ()}
        for key, recorded in matches.items():
            actual = cards[key].names if key in cards else ()
            if actual != recorded:
                drifted.append(f"{slug}/{key}: 표={recorded} 픽스처={actual}")
    assert not drifted, (
        "참가자 이름이 달라졌다 — 확정됐다면 표에서 지운다: " + " · ".join(drifted)
    )


def test_unknown_events_have_no_unconfirmed_matches() -> None:
    """표에 없는 대회를 물으면 빈 집합이다 — 부르는 쪽이 존재 여부를 안 물어도 된다."""
    assert unconfirmed_match_keys("money-in-the-bank") == frozenset()
    assert unconfirmed_match_keys("존재하지-않는-대회") == frozenset()


def test_the_table_is_empty_for_now() -> None:
    """**표가 비어 있는 것이 지금의 사실이다** (2026-10-20).

    하나뿐이던 항목 Crown Jewel 둘은 2026-10-12에 위키가 실명을 채워 졸업했다.
    여기 있던 `test_crown_jewel_is_covered`가 그 사실을 박아 두고 있었는데, 그것은
    **지나가는 사실**이라 픽스처가 갱신된 날 깨졌다. 이 파일의 다른 세 테스트는
    표에 든 항목이 **무엇이든** 검사하므로, 새 항목이 들어오면 자동으로 지켜진다.

    이 줄이 실패하면 누군가 항목을 더한 것이다 — 그것 자체는 정상이니 숫자를
    고치지 말고 **왜 더했는지 모듈 주석에 적혔는지** 보고 이 테스트를 지운다.
    """
    assert UNCONFIRMED_MATCH_CARDS == {}


def test_keys_come_from_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """**장치 자체**를 본다 — 표에 든 대회를 물으면 그 경기 id들이 나온다.

    실제 데이터로 고정하지 않는 이유는 위와 같다. 표는 대회가 끝나면 비므로,
    살아 있는 값으로 쓴 테스트는 전부 시한부다.
    """
    monkeypatch.setitem(
        UNCONFIRMED_MATCH_CARDS,
        "some-event",
        {"se26-a": ("Raw's Champion", "SmackDown's Champion"), "se26-b": ("TBD",)},
    )
    assert unconfirmed_match_keys("some-event") == {"se26-a", "se26-b"}
