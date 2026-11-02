"""커리어 세계의 실제 로스터 (`career_roster` · `career_divisions`).

**붙드는 것은 계약이다.**

1. **한 부만 들어온다** — 남자부 세계에 여자부 선수가 없고, 반대도 그렇다
2. **세 브랜드만** — Free Agent · Evolve · 방출 보존 선수는 빠진다
3. **전적은 0에서 시작한다** — 실제 경기 승패를 쓰지 않는다
4. **타이틀 이력이 인기도를 올린다** — 근거가 있는 추정치
5. **결정론** — 같은 입력이면 같은 선수
6. **명부가 모자라면 `None`** — 호출자가 기본 로스터로 돌아간다
7. **여자부 명단이 카탈로그와 맞는다** — 표기가 어긋나면 그 선수가 남자부로 샌다

인터랙터 배선(실제 명부로 세계 짓기 · 명부가 없으면 기본 세계)은
`tests/app/use_cases/test_career_sandbox_interactor.py` 끝에 있다 — 가짜 저장소가 거기 있다.
"""

from __future__ import annotations

from datetime import date

from kayfabe.app.services import career_roster
from kayfabe.app.services.career_divisions import WOMEN
from kayfabe.app.services.data_center_stats import TitleRow, WrestlerRow
from kayfabe.app.services.wwe_roster_catalog import ROSTER_BY_NAME, WWE_ROSTER

TODAY = date(2026, 11, 2)


def _rows() -> list[WrestlerRow]:
    out = []
    for brand, men, women in (
        ("RAW", ["Seth Rollins", "CM Punk", "Gunther"], ["Rhea Ripley", "Iyo Sky"]),
        ("SmackDown", ["Cody Rhodes", "Jacob Fatu"], ["Tiffany Stratton", "Nia Jax"]),
        ("NXT", ["Oba Femi", "Je'Von Evans"], ["Jaida Parker", "Thea Hail"]),
    ):
        out += [WrestlerRow(name=n, brand=brand, birth_date="1990-01-01") for n in men]
        out += [
            WrestlerRow(name=n, brand=brand, birth_date="1995-06-15") for n in women
        ]
    out.append(WrestlerRow(name="Paige", brand="Free Agent"))
    out.append(WrestlerRow(name="Some Evolve Guy", brand="Evolve"))
    out.append(WrestlerRow(name="Brock Lesnar", brand="RAW"))  # 방출 보존
    return out


def _build(division="men", acquisitions=()):
    return career_roster.build_roster(
        rows=_rows(),
        catalog=ROSTER_BY_NAME,
        acquisitions=acquisitions,
        division=division,
        today=TODAY,
    )


def test_men_world_has_no_women_and_only_three_brands():
    roster = _build("men")
    assert roster is not None
    names = {w.name for w in roster}
    assert names.isdisjoint(WOMEN)
    assert {w.brand for w in roster} == {"Raw", "SmackDown", "NXT"}
    assert "Brock Lesnar" not in names and "Some Evolve Guy" not in names


def test_women_world_has_only_women():
    roster = _build("women")
    assert roster is not None
    assert {w.name for w in roster} <= WOMEN
    assert "Paige" not in {w.name for w in roster}  # Free Agent


def test_everyone_starts_at_zero_record():
    for w in _build("men") or ():
        assert (w.wins, w.losses, w.reigns, w.held) == (0, 0, (), ())


def test_title_history_raises_popularity():
    plain = {w.name: w for w in _build("men") or ()}
    titled = {
        w.name: w
        for w in _build(
            "men",
            acquisitions=[
                TitleRow(
                    competitor_name="Gunther",
                    belt_name="World Heavyweight Championship",
                    won_at="x",
                ),
                TitleRow(
                    competitor_name="Gunther",
                    belt_name="Intercontinental Championship",
                    won_at="y",
                ),
            ],
        )
        or ()
    }
    assert titled["Gunther"].popularity > plain["Gunther"].popularity
    assert titled["Gunther"].ability.in_ring > plain["Gunther"].ability.in_ring
    assert titled["Seth Rollins"] == plain["Seth Rollins"]


def test_build_is_deterministic():
    assert _build("men") == _build("men")


def test_age_comes_from_birth_date():
    w = {x.name: x for x in _build("men") or ()}["Seth Rollins"]
    assert w.age == 36  # 1990-01-01 → 2026-11-02


def test_too_few_per_brand_returns_none():
    rows = [WrestlerRow(name="Seth Rollins", brand="RAW")]
    got = career_roster.build_roster(
        rows=rows, catalog=ROSTER_BY_NAME, acquisitions=(), division="men", today=TODAY
    )
    assert got is None


def test_women_list_matches_catalog_spelling():
    catalog = {e["name"] for e in WWE_ROSTER}
    assert WOMEN <= catalog, sorted(WOMEN - catalog)
    assert len(WOMEN) >= 40
