"""접두사 표가 **실제 픽스처와 어긋나지 않는지** 본다.

표는 폴백이다 — 경기가 0건이라 픽스처에서 접두사를 읽을 수 없을 때만 쓴다. 그래서
평소에는 쓰이지 않고, **쓰이지 않는 값은 조용히 낡는다.** 낡은 접두사로 만든 id는
기존 경기와 안 맞아서 동기화가 옛 행을 지운다.

이 테스트가 그 드리프트를 잡는다. 픽스처를 못 찾으면 건너뛴다 — 백엔드만 체크아웃한
환경에서 도는 일이 있다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kayfabe.app.services.ple_fixture_file import id_prefix_of, read_event_cards
from kayfabe.app.services.ple_match_id_prefixes import PLE_MATCH_ID_PREFIXES
from kayfabe.app.services.wiki_event_titles import EVENT_ARTICLE_TITLES

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


def test_the_table_agrees_with_every_fixture_that_has_matches(source: str) -> None:
    """픽스처가 정본이다. 하나라도 어긋나면 표가 낡은 것이다."""
    mismatched: list[str] = []
    for slug, expected in PLE_MATCH_ID_PREFIXES.items():
        cards = read_event_cards(source, slug)
        if not cards:
            continue
        actual = id_prefix_of(cards)
        if actual is not None and actual != expected:
            mismatched.append(f"{slug}: 표={expected} 픽스처={actual}")
    assert not mismatched, "접두사 표가 픽스처와 어긋난다 — " + " · ".join(mismatched)


def test_every_event_with_a_fixture_entry_is_in_the_table(source: str) -> None:
    """항목이 있는데 표에 없으면, 그 대회의 대진이 비는 날 도구가 멈춘다."""
    missing = [
        slug
        for slug in EVENT_ARTICLE_TITLES
        if read_event_cards(source, slug) is not None
        and slug not in PLE_MATCH_ID_PREFIXES
    ]
    assert not missing, f"표에 없는 대회: {', '.join(missing)}"


def test_the_unannounced_event_has_a_prefix_ready(source: str) -> None:
    """**이 표가 실제로 쓰이는 자리다.**

    `halloween-havoc`은 대진이 아직 없어 경기가 0건이고, 그래서 픽스처에서 접두사를
    읽을 수 없다. 표에 값이 없으면 대진이 발표되는 날 도구가 그냥 멈춘다.
    """
    cards = read_event_cards(source, "halloween-havoc")
    assert cards == (), (
        "이 테스트의 전제가 깨졌다 — 대진이 들어왔다면 위 검사로 충분하다"
    )
    assert id_prefix_of(cards) is None
    assert PLE_MATCH_ID_PREFIXES["halloween-havoc"] == "hh26"
