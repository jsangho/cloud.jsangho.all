"""링 밖의 사람들 (하네스 §3-D93).

사용자가 준 일곱 규칙을 그대로 잠근다.

1. 성별 표기는 `M`·`W`다 — **`W`가 여성**
2. 집행부가 발표하고, **재계약 자리에는 회장이 안 나온다**
3. GM은 브랜드당 하나 · 해설은 지정석
4. 챔피언십에는 링 아나운서가 붙는다 — **그때만**
5. 백스테이지 인터뷰어가 곧 기자다
6. 심판은 해설처럼 표기되고 가끔 인용된다
7. 매니저는 담당 선수 옆에 선다
"""

from __future__ import annotations

from wwe_game.domain.constants import roster, staff
from wwe_game.domain.constants.staff import StaffRole
from wwe_game.domain.services import staff_scene
from wwe_game.domain.services.news_article import build
from wwe_game.domain.services.news_feed import CrowdMood, NewsItem, NewsKind
from wwe_game.domain.value_objects.wrestler_identity import Gender

BRANDS = ("raw", "smackdown", "nxt")


class TestTheRosterOfPeopleOutsideTheRing:
    def test_every_brand_has_the_seats_filled(self) -> None:
        for brand in BRANDS:
            assert staff_scene.gm_of(brand), f"{brand}: GM이 없다"
            assert staff_scene.commentators_of(brand), f"{brand}: 해설이 없다"
            assert staff.for_brand(brand, StaffRole.REFEREE), f"{brand}: 심판이 없다"
            assert staff.for_brand(brand, StaffRole.RING_ANNOUNCER)
            assert staff.for_brand(brand, StaffRole.INTERVIEWER) or brand == "nxt"

    def test_w_is_a_woman(self) -> None:
        """원본은 `M`·`W`로 적혀 있다 (2026-08-19 사용자 표기)."""
        women = [m.name for m in staff.STAFF if m.gender is Gender.FEMALE]
        assert "알리시아 테일러" in women
        assert "릴리안 가르시아" in women

    def test_evolve_is_carried_but_not_used(self) -> None:
        """게임의 브랜드 축은 셋뿐이다 — Evolve는 담기되 안 섞인다."""
        assert any(m.brand == "evolve" for m in staff.STAFF)
        for brand in BRANDS:
            assert all(m.brand == brand for m in staff.for_brand(brand, StaffRole.GM))

    def test_the_draft_week_matches_the_roster(self) -> None:
        """값을 두 곳에 뒀으므로 여기서 잠근다 (§3-D93)."""
        assert staff_scene.DRAFT_WEEK == roster.DRAFT_WEEK


class TestTheOneWhoSitsAcross:
    """규칙 2 — *"재계약할 때도 President 말고 나랑 대화하는 거야"*."""

    def test_the_president_never_shows_up(self) -> None:
        for brand in BRANDS:
            for week in range(1, 60):
                person = staff_scene.negotiator_for(brand, week, 7)
                assert person is not None
                assert not person.title.startswith("President")

    def test_nxt_is_handled_by_talent_development(self) -> None:
        person = staff_scene.negotiator_for("nxt", 100, 7)
        assert person is not None
        assert "Talent Development" in person.title

    def test_the_same_offer_meets_the_same_person(self) -> None:
        """되짚기가 결정적이다 (§3-D4) — 새로고침한다고 상대가 바뀌지 않는다."""
        first = staff_scene.negotiator_for("raw", 300, 42)
        assert first == staff_scene.negotiator_for("raw", 300, 42)


class TestTheCompanySpeaks:
    """규칙 2 — 집행부의 중대 발표."""

    def test_two_a_year(self) -> None:
        notices = staff_scene.announcements(7, 52 * 3)
        assert len(notices) == 6

    def test_every_notice_has_a_speaker(self) -> None:
        for notice in staff_scene.announcements(7, 200):
            assert notice.speaker
            assert notice.speaker in notice.headline


class TestTheNightCrew:
    def test_a_title_match_gets_an_announcer(self) -> None:
        """규칙 4 — 벨트가 걸린 밤에는 소개가 먼저다."""
        crew = staff_scene.crew_for("raw", 300, 7, title_match=True)
        assert crew.ring_announcer

    def test_an_ordinary_night_does_not(self) -> None:
        """매주 소개를 세우면 그건 그냥 오프닝이다."""
        assert not staff_scene.crew_for("raw", 300, 7).ring_announcer

    def test_a_title_match_gets_a_senior_referee(self) -> None:
        senior = {m.name for m in staff.for_brand("raw", StaffRole.REFEREE) if m.senior}
        assert staff_scene.referee_of("raw", 300, 7, title_match=True) in senior

    def test_the_crew_is_the_same_night_after_night(self) -> None:
        assert staff_scene.crew_for("nxt", 77, 3) == staff_scene.crew_for("nxt", 77, 3)

    def test_the_commentary_seats_never_shuffle(self) -> None:
        """규칙 3 — 원본에 적힌 차례가 곧 지정석이다."""
        assert staff_scene.commentators_of("raw") == ("마이클 콜", "코리 그레이브스")


class TestTheManagerStandsBeside:
    """규칙 7 — 폴 헤이먼 등은 `w/`로 붙는다."""

    def test_a_stable_brings_its_manager(self) -> None:
        assert staff_scene.manager_of("아무개", "The Vision") == "폴 헤이먼"

    def test_a_single_wrestler_can_have_one(self) -> None:
        assert staff_scene.manager_of("트릭 윌리엄스") == "릴 야티"

    def test_most_people_have_none(self) -> None:
        assert staff_scene.manager_of("장상호") == ""


def _item(kind: NewsKind, week: int = 120) -> NewsItem:
    return NewsItem(
        week=week,
        kind=kind,
        headline="테스트",
        mood=CrowdMood.ROAR,
        crowd_line="환호가 터졌다",
    )


class TestTheArticleNamesWhoSpoke:
    def test_the_interviewer_signs_the_article(self) -> None:
        """규칙 5 — 백스테이지 인터뷰가 곧 기사이고, 누가 물었는지가 남는다."""
        article = build(_item(NewsKind.BIG_WIN), 7, brand="raw")
        assert article.byline
        assert article.byline in {
            m.name for m in staff.for_brand("raw", StaffRole.INTERVIEWER)
        }

    def test_the_gm_talks_about_the_card(self) -> None:
        """규칙 3 — 대진과 자리를 정하는 사람이 그 일을 말한다."""
        assert (
            staff_scene.gm_of("raw")
            in build(_item(NewsKind.CALL_UP), 7, brand="raw").quote
        )

    def test_the_referee_talks_when_the_call_is_questioned(self) -> None:
        """규칙 6 — 저주로 진 밤은 판정이 도마에 오르는 밤이다."""
        quote = build(_item(NewsKind.CURSED), 7, brand="raw").quote
        assert quote
        assert staff_scene.referee_of("raw", 120, 7) in quote

    def test_the_manager_answers_for_his_wrestler(self) -> None:
        """규칙 7 — 매니저를 둔 선수는 말을 덜 한다."""
        quote = build(
            _item(NewsKind.TITLE_WON), 7, brand="raw", manager="폴 헤이먼"
        ).quote
        assert "폴 헤이먼" in quote

    def test_a_quiet_event_gets_no_quote(self) -> None:
        """**억지로 말시키지 않는다.** 할 말이 없는 사건도 있다."""
        assert build(_item(NewsKind.INJURY), 7, brand="raw").quote == ""

    def test_an_article_without_a_brand_still_stands(self) -> None:
        """옛 호출부가 깨지지 않는다 — 브랜드가 없으면 이름만 안 붙는다."""
        article = build(_item(NewsKind.BIG_WIN), 7)
        assert article.title
        assert article.byline == ""
