"""챔피언 자동 승계 규칙 테스트.

**여기 쓰인 경기 제목·승자는 전부 운영 DB 실측값이다**(2026-09-28). 지어낸 예시가
아니라 SummerSlam(8/1)·Worlds Collide(9/26)에 실제로 있던 줄이다.

고정하는 계약 여섯:

1. 벨트 이름이 **정확히** 같아야 반영한다 — `— No.1 Contender`는 다른 경기다
2. 방어는 `won_at`을 바꾸지 않는다
3. 보드에 없는 벨트(AAA·잠정)는 건너뛰고, 건너뛴 사실을 남긴다
4. 기준일 이전 경기는 이미 카탈로그에 있으므로 다시 얹지 않는다
5. 같은 벨트가 여러 번 걸리면 **가장 늦은** 경기가 이긴다
6. 보드의 줄 순서는 기준선 그대로다

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from kayfabe.app.services.title_match_classifier import is_championship_match
from kayfabe.domain.services.championship_succession import (
    FinishedTitleMatch,
    SkipReason,
    TitleReign,
    apply_results,
)

AS_OF = "2026-07-12"

_BASELINE = (
    TitleReign(
        belt_name="World Heavyweight Championship",
        champions=("Roman Reigns",),
        won_at="2026-04-19",
        won_event="WrestleMania 42",
    ),
    TitleReign(
        belt_name="WWE Intercontinental Championship",
        champions=("Penta",),
        won_at="2026-03-02",
    ),
    TitleReign(
        belt_name="WWE United States Championship",
        champions=("Trick Williams",),
        won_at="2026-04-19",
    ),
    TitleReign(
        belt_name="Undisputed WWE Championship",
        champions=("CM Punk",),
        won_at="2026-07-06",
    ),
    TitleReign(
        belt_name="World Tag Team Championship",
        champions=("Bron Breakker", "Austin Theory"),
        team_name="The Vision",
        won_at="2026-07-06",
    ),
    TitleReign(
        belt_name="NXT Tag Team Championship",
        champions=("Brad Baylor", "Ricky Smokes"),
        team_name="The Vanity Project",
        won_at="2026-02-24",
    ),
)


def _match(title: str, winner: str, *, date: str = "2026-08-01", key: str = "m1"):
    return FinishedTitleMatch(
        match_title=title,
        match_key=key,
        winner=winner,
        event_label="SummerSlam 2026",
        event_date=date,
    )


def _apply(*matches, baseline=_BASELINE, as_of=AS_OF):
    return apply_results(
        baseline, matches, baseline_as_of=as_of, is_title_match=is_championship_match
    )


def _reign(result, belt: str) -> TitleReign:
    return next(r for r in result.reigns if r.belt_name == belt)


class TestTitleChange:
    def test_new_champion_is_applied(self) -> None:
        """실측: SummerSlam에서 Chad Gable이 IC 벨트를 땄는데 보드는 Penta였다."""
        result = _apply(_match("WWE Intercontinental Championship", "Chad Gable"))
        reign = _reign(result, "WWE Intercontinental Championship")

        assert reign.champions == ("Chad Gable",)
        assert reign.won_at == "2026-08-01"
        assert reign.won_event == "SummerSlam 2026"

    def test_as_of_moves_to_the_applied_event(self) -> None:
        result = _apply(_match("WWE United States Championship", "Baron Corbin"))

        assert result.as_of == "2026-08-01"

    def test_change_is_reported(self) -> None:
        result = _apply(_match("WWE United States Championship", "Baron Corbin"))

        assert len(result.changes) == 1
        change = result.changes[0]
        assert change.before == ("Trick Williams",)
        assert change.after == ("Baron Corbin",)
        assert change.members_unknown is False

    def test_latest_match_wins(self) -> None:
        """같은 벨트가 두 번 걸리면 나중 것이 현재다."""
        result = _apply(
            _match(
                "WWE Intercontinental Championship", "Chad Gable", date="2026-08-01"
            ),
            _match(
                "WWE Intercontinental Championship",
                "Bron Breakker",
                date="2026-08-30",
                key="m2",
            ),
        )

        assert _reign(result, "WWE Intercontinental Championship").champions == (
            "Bron Breakker",
        )
        assert result.as_of == "2026-08-30"

    def test_board_order_is_preserved(self) -> None:
        result = _apply(_match("WWE Intercontinental Championship", "Chad Gable"))

        assert [r.belt_name for r in result.reigns] == [r.belt_name for r in _BASELINE]


class TestRetention:
    def test_successful_defense_keeps_the_reign_date(self) -> None:
        """실측: Roman Reigns가 4/19에 따고 8/1에 방어했다. 보드는 4/19여야 한다."""
        result = _apply(_match("World Heavyweight Championship", "Roman Reigns"))
        reign = _reign(result, "World Heavyweight Championship")

        assert reign.won_at == "2026-04-19"
        assert reign.won_event == "WrestleMania 42"
        assert result.changes == ()

    def test_defense_still_advances_as_of(self) -> None:
        """방어도 "그날까지 확인했다"는 사실이다 — 기준일은 움직인다."""
        result = _apply(_match("Undisputed WWE Championship", "CM Punk"))

        assert result.as_of == "2026-08-01"
        assert result.changes == ()

    def test_team_name_counts_as_the_same_champions(self) -> None:
        """카드가 구성원 대신 팀명만 적는 일이 있다(`The Vanity Project`).

        이름만 대조하면 방어가 재위로 둔갑해 `won_at`이 갈아 끼워진다.
        """
        result = _apply(
            _match("NXT Tag Team Championship", "The Vanity Project", date="2026-08-30")
        )
        reign = _reign(result, "NXT Tag Team Championship")

        assert reign.won_at == "2026-02-24"
        assert reign.champions == ("Brad Baylor", "Ricky Smokes")
        assert result.changes == ()

    def test_member_order_does_not_matter(self) -> None:
        result = _apply(
            _match("World Tag Team Championship", "Austin Theory & Bron Breakker")
        )

        assert result.changes == ()
        assert _reign(result, "World Tag Team Championship").won_at == "2026-07-06"


class TestGates:
    def test_number_one_contender_does_not_crown_anyone(self) -> None:
        """**실측으로 뚫렸을 자리.** 벨트 이름을 품지만 타이틀은 안 걸렸다.

        부분 일치나 `extract_belt_name`을 쓰면 케빈 오웬스가 챔피언이 된다.
        """
        result = _apply(
            _match("Undisputed WWE Championship — No.1 Contender", "Kevin Owens")
        )

        assert _reign(result, "Undisputed WWE Championship").champions == ("CM Punk",)
        assert result.changes == ()
        assert result.skipped[0].reason is SkipReason.BELT_NOT_ON_BOARD

    def test_belt_outside_the_board_is_skipped(self) -> None:
        """실측: Worlds Collide의 AAA 타이틀. 우리 보드의 벨트가 아니다."""
        result = _apply(
            _match(
                "AAA Reina de Reinas Championship",
                "La Catalina",
                date="2026-09-26",
                key="wc26-reina",
            )
        )

        assert result.changes == ()
        assert result.skipped[0].reason is SkipReason.BELT_NOT_ON_BOARD

    def test_interim_title_is_skipped(self) -> None:
        result = _apply(
            _match("Interim WWE Women's Championship — Ladder Match", "Chelsea Green")
        )

        assert result.changes == ()
        assert result.skipped[0].reason is SkipReason.BELT_NOT_ON_BOARD

    def test_non_title_match_is_not_reported_as_skipped(self) -> None:
        """`Single Match`·`Tag Team Match`는 챔피언십처럼 보이지도 않는다 — 조용히 지나간다."""
        result = _apply(
            _match("Single Match", "Gunther"),
            _match("Tag Team Match", "Lucha Brothers", key="m2"),
        )

        assert result.changes == ()
        assert result.skipped == ()

    def test_mitb_ladder_is_skipped_loudly(self) -> None:
        """래더전은 서류를 따는 것이지 벨트를 따는 것이 아니다."""
        result = _apply(
            _match(
                "Women's Money in the Bank Ladder Match for a Championship",
                "Rhea Ripley",
                key="mitb26-women",
            )
        )

        assert result.changes == ()
        assert result.skipped[0].reason is SkipReason.NOT_A_TITLE_MATCH

    def test_empty_winner_is_skipped(self) -> None:
        """카드에서 승자를 못 읽은 경우 — 추측으로 챔피언을 바꾸지 않는다."""
        result = _apply(_match("WWE Intercontinental Championship", ""))

        assert result.changes == ()
        assert result.skipped[0].reason is SkipReason.NO_WINNER

    def test_matches_before_the_baseline_are_ignored(self) -> None:
        """기준일 이전은 이미 카탈로그에 반영돼 있다 — 다시 얹으면 중복이다."""
        result = _apply(
            _match("WWE Intercontinental Championship", "Chad Gable", date="2026-03-02")
        )

        assert result.changes == ()
        assert result.as_of == AS_OF
        assert _reign(result, "WWE Intercontinental Championship").champions == (
            "Penta",
        )

    def test_nothing_to_apply_keeps_the_baseline(self) -> None:
        result = _apply()

        assert result.reigns == _BASELINE
        assert result.as_of == AS_OF


class TestWinnerParsing:
    def test_team_and_members_are_split(self) -> None:
        """카드가 `팀 — A & B`로 적는 형식(실측: `Lucha Brothers — Penta & Rey Fénix`)."""
        result = _apply(
            _match("World Tag Team Championship", "Lucha Brothers — Penta & Rey Fénix")
        )
        reign = _reign(result, "World Tag Team Championship")

        assert reign.team_name == "Lucha Brothers"
        assert reign.champions == ("Penta", "Rey Fénix")
        assert result.changes[0].members_unknown is False

    def test_ampersand_only_gives_members(self) -> None:
        result = _apply(_match("World Tag Team Championship", "Jey Uso & Jimmy Uso"))
        reign = _reign(result, "World Tag Team Championship")

        assert reign.champions == ("Jey Uso", "Jimmy Uso")
        assert reign.team_name is None

    def test_team_name_only_is_flagged_for_a_human(self) -> None:
        """구성원을 알 길이 없다. 지어내지 않고 사람에게 알린다."""
        result = _apply(_match("World Tag Team Championship", "Los Americanos"))

        assert _reign(result, "World Tag Team Championship").champions == (
            "Los Americanos",
        )
        assert result.changes[0].members_unknown is True
