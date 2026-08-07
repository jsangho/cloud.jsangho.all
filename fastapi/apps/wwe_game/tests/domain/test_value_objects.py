"""T2 값 객체 — 스탯 범위 · 이름 검증 · 나이 계산 · 모드 틱 산술.

DB·네트워크를 쓰지 않는다. 실행:
    cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/wwe_game/tests -q
"""

from __future__ import annotations

import pytest
from wwe_game.domain.constants.career_clock import (
    CAREER_WEEKS,
    RETIREMENT_AGE,
    START_AGE,
)
from wwe_game.domain.constants.countries import (
    COUNTRY_REGION,
    Country,
    Region,
    region_of,
)
from wwe_game.domain.exceptions import (
    InvalidConditionError,
    InvalidRingNameError,
    InvalidStatsError,
    UnknownGameModeError,
)
from wwe_game.domain.value_objects.condition import (
    WEAR_MAX,
    Condition,
    InjuryGrade,
)
from wwe_game.domain.value_objects.game_mode import (
    GAME_MODES,
    GameModeCode,
    game_mode_of,
    guest_modes,
)
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

# ── 스탯 범위 ────────────────────────────────────────────────


class TestWrestlerStats:
    def test_defaults_are_the_starting_stats(self) -> None:
        s = WrestlerStats()
        assert (s.popularity, s.in_ring, s.mic_work, s.backstage, s.alignment) == (
            10,
            20,
            10,
            50,
            0,
        )

    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            ("popularity", -1),
            ("popularity", 101),
            ("in_ring", 101),
            ("mic_work", -5),
            ("backstage", 200),
            ("alignment", -101),
            ("alignment", 101),
        ],
    )
    def test_out_of_range_values_are_rejected(
        self, field_name: str, value: int
    ) -> None:
        with pytest.raises(InvalidStatsError):
            WrestlerStats(**{field_name: value})

    def test_only_alignment_allows_negatives(self) -> None:
        assert WrestlerStats(alignment=-100).alignment == -100

    def test_bool_is_not_accepted_as_int(self) -> None:
        # True는 파이썬에서 int 하위형이라 조용히 1로 들어간다. 체험판 JSON에서 오면 곤란하다.
        with pytest.raises(InvalidStatsError):
            WrestlerStats(popularity=True)  # type: ignore[arg-type]

    def test_apply_clamps_at_the_bounds(self) -> None:
        s = WrestlerStats(popularity=95)
        assert s.apply({"popularity": 20}).popularity == 100
        assert s.apply({"popularity": -200}).popularity == 0

    def test_apply_can_flip_alignment_sign(self) -> None:
        s = WrestlerStats(alignment=20)
        assert s.apply({"alignment": -60}).alignment == -40

    def test_apply_rejects_unknown_keys(self) -> None:
        # 덱 JSON의 오타가 "아무 일도 안 일어나는 선택지"로 바뀌는 게 가장 잡기 어렵다.
        with pytest.raises(InvalidStatsError, match="모르는 스탯 키"):
            WrestlerStats().apply({"wear": 10})

    def test_apply_returns_a_new_object(self) -> None:
        s = WrestlerStats()
        assert s.apply({"popularity": 5}) is not s
        assert s.popularity == 10

    def test_heel_and_face_thresholds(self) -> None:
        assert WrestlerStats(alignment=-20).is_heel
        assert not WrestlerStats(alignment=-19).is_heel
        assert WrestlerStats(alignment=20).is_face
        assert not WrestlerStats(alignment=19).is_face


# ── 이름 검증 ────────────────────────────────────────────────


class TestRingName:
    @pytest.mark.parametrize("raw", ["장상호", "  존 시나  ", "AB", "가" * 20])
    def test_accepts_valid_names(self, raw: str) -> None:
        assert RingName(raw).value == raw.strip()

    @pytest.mark.parametrize(
        "raw", ["", " ", "   ", "A", "가" * 21, "a\nb", "a\tb", "a\x00b"]
    )
    def test_rejects_invalid_names(self, raw: str) -> None:
        with pytest.raises(InvalidRingNameError):
            RingName(raw)

    def test_surrounding_whitespace_is_stripped(self) -> None:
        assert RingName("  더 락  ").value == "더 락"

    def test_duplicates_are_allowed(self) -> None:
        assert RingName("같은이름") == RingName("같은이름")

    def test_rejects_non_strings(self) -> None:
        with pytest.raises(InvalidRingNameError):
            RingName(123)  # type: ignore[arg-type]


# ── 나이 계산 ────────────────────────────────────────────────


class TestAge:
    @pytest.fixture
    def identity(self) -> WrestlerIdentity:
        return WrestlerIdentity(
            name=RingName("장상호"),
            gender=Gender.MALE,
            country=Country.KR,
            play_style=PlayStyle.TECHNICIAN,
        )

    def test_starts_at_twenty(self, identity: WrestlerIdentity) -> None:
        assert identity.age_at(0) == START_AGE == 20

    def test_one_year_every_fifty_two_weeks(self, identity: WrestlerIdentity) -> None:
        assert identity.age_at(51) == 20
        assert identity.age_at(52) == 21
        assert identity.age_at(103) == 21
        assert identity.age_at(104) == 22

    def test_exactly_fifty_at_week_1560(self, identity: WrestlerIdentity) -> None:
        assert identity.age_at(CAREER_WEEKS) == RETIREMENT_AGE == 50

    def test_age_rises_by_one_thirty_times_over_the_career(
        self, identity: WrestlerIdentity
    ) -> None:
        ages = [identity.age_at(w) for w in range(CAREER_WEEKS + 1)]
        assert ages[0] == 20 and ages[-1] == 50
        pairs = list(zip(ages[:-1], ages[1:], strict=True))
        assert all(b - a in (0, 1) for a, b in pairs)
        assert sum(1 for a, b in pairs if b > a) == 30

    def test_negative_week_is_rejected(self, identity: WrestlerIdentity) -> None:
        with pytest.raises(ValueError, match="음수"):
            identity.age_at(-1)


# ── 모드 틱 산술 ─────────────────────────────────────────────


class TestGameMode:
    def test_all_four_modes_exist(self) -> None:
        assert set(GAME_MODES) == set(GameModeCode)

    @pytest.mark.parametrize(
        ("code", "weeks_per_tick", "total_ticks", "budget"),
        [
            (GameModeCode.YEARLY, 52, 30, 30),
            (GameModeCode.QUARTERLY, 13, 120, 160),
            (GameModeCode.MONTHLY, 4, 390, 200),
            (GameModeCode.WEEKLY, 1, 1560, 320),
        ],
    )
    def test_tick_arithmetic(
        self, code: GameModeCode, weeks_per_tick: int, total_ticks: int, budget: int
    ) -> None:
        m = GAME_MODES[code]
        assert m.weeks_per_tick == weeks_per_tick
        assert m.total_ticks == total_ticks
        assert m.event_budget == budget

    def test_every_mode_spans_exactly_1560_weeks(self) -> None:
        for m in GAME_MODES.values():
            assert m.total_ticks * m.weeks_per_tick == CAREER_WEEKS

    def test_shorter_tick_means_more_events(self) -> None:
        ordered = sorted(GAME_MODES.values(), key=lambda m: -m.weeks_per_tick)
        budgets = [m.event_budget for m in ordered]
        assert budgets == sorted(budgets)

    def test_guests_get_yearly_and_quarterly_only(self) -> None:
        assert {m.code for m in guest_modes()} == {
            GameModeCode.YEARLY,
            GameModeCode.QUARTERLY,
        }

    def test_unknown_mode_is_rejected(self) -> None:
        with pytest.raises(UnknownGameModeError):
            game_mode_of("biweekly")

    def test_lookup_by_code(self) -> None:
        assert game_mode_of("weekly").total_ticks == CAREER_WEEKS


# ── 부상·마모 ────────────────────────────────────────────────


class TestCondition:
    def test_starts_healthy(self) -> None:
        c = Condition()
        assert not c.is_injured and c.wear == 0

    def test_grade_and_weeks_left_must_agree(self) -> None:
        with pytest.raises(InvalidConditionError):
            Condition(grade=InjuryGrade.HEALTHY, weeks_left=3)
        with pytest.raises(InvalidConditionError):
            Condition(grade=InjuryGrade.MINOR, weeks_left=0)

    def test_wear_bounds(self) -> None:
        with pytest.raises(InvalidConditionError):
            Condition(wear=-1)
        with pytest.raises(InvalidConditionError):
            Condition(wear=101)

    def test_recovery_also_heals_the_grade(self) -> None:
        c = Condition().injured(InjuryGrade.MINOR, 6)
        assert c.recover(2).weeks_left == 4
        assert not c.recover(6).is_injured
        assert c.recover(99).grade is InjuryGrade.HEALTHY

    def test_career_ending_injury_never_recovers(self) -> None:
        c = Condition().injured(InjuryGrade.CAREER_ENDING, 99)
        assert c.recover(999) == c

    def test_wear_is_clamped(self) -> None:
        assert Condition(wear=95).with_wear(20).wear == WEAR_MAX
        assert Condition(wear=5).with_wear(-50).wear == 0

    def test_injury_does_not_reset_wear(self) -> None:
        c = Condition(wear=40).injured(InjuryGrade.SERIOUS, 12)
        assert c.wear == 40

    def test_injury_without_recovery_weeks_is_rejected(self) -> None:
        with pytest.raises(InvalidConditionError):
            Condition().injured(InjuryGrade.MINOR, 0)


# ── 국가·권역 ────────────────────────────────────────────────


class TestCountries:
    def test_at_least_twenty_countries(self) -> None:
        assert len(Country) >= 20

    def test_every_country_maps_to_a_region(self) -> None:
        assert set(COUNTRY_REGION) == set(Country)

    def test_every_region_has_at_least_one_country(self) -> None:
        assert set(COUNTRY_REGION.values()) == set(Region)

    def test_korea_is_its_own_region(self) -> None:
        assert region_of(Country.KR) is Region.KR
        assert [c for c, r in COUNTRY_REGION.items() if r is Region.KR] == [Country.KR]


class TestEventDiminishing:
    """이벤트 이득은 체감한다 — 기본 성장에만 걸고 이벤트에 안 걸면 균형이 깨진다."""

    def test_gains_shrink_as_the_stat_climbs(self) -> None:
        low = WrestlerStats(popularity=20).apply_event({"popularity": 16})
        high = WrestlerStats(popularity=90).apply_event({"popularity": 16})
        assert (low.popularity - 20) > (high.popularity - 90)

    def test_losses_are_not_diminished(self) -> None:
        # 정상에 가까울수록 얻기 어렵고 잃기는 쉬워야 한다.
        for start in (20, 50, 95):
            after = WrestlerStats(popularity=start).apply_event({"popularity": -10})
            assert after.popularity == start - 10

    def test_a_gain_never_rounds_away_to_nothing(self) -> None:
        after = WrestlerStats(popularity=99).apply_event({"popularity": 16})
        assert after.popularity > 99

    def test_alignment_diminishes_toward_the_bound_it_moves_to(self) -> None:
        near = WrestlerStats(alignment=90).apply_event({"alignment": 20})
        far = WrestlerStats(alignment=-90).apply_event({"alignment": 20})
        assert (near.alignment - 90) < (far.alignment + 90)

    def test_plain_apply_stays_raw(self) -> None:
        # 주당 ±1 성장은 이미 자체 체감을 가지므로 두 번 깎으면 안 된다.
        assert WrestlerStats(popularity=90).apply({"popularity": 16}).popularity == 100
