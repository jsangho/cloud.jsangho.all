"""결과 판정 관문 테스트 — 에이전트의 안전이 전부 여기 걸려 있다.

**모델도 DB도 부르지 않는다.** 순수 함수라 주장과 본문을 손으로 만들어 넣는다.

여기서 고정하는 계약:

1. 지어낸 인용은 이름이 맞아도 쓰이지 않는다 (관문 2가 관문 3보다 앞이다)
2. 카드에 없는 이름·두 선택지에 걸리는 이름은 보류다
3. `winner_name: null`은 파손이 아니라 "승자 없음"이다
4. 쓰는 이름은 **카드의 표기**다, 모델이 적어 보낸 표기가 아니다
5. 위치·순서를 근거로 **승자를 고르지** 않는다 (위키 서술 순서가 카드와 반대일 수 있다)
6. **인용이 패자로 적은 사람은 쓰지 않는다** — 관문 1~4를 다 통과해도 막는다.
   `TestDirection`이 그 자리다. 이 구멍은 2026-09-28에 실제 위키 본문으로 발견됐다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from kayfabe.domain.entities.result_verification import (
    Evidence,
    HoldReason,
    MatchUnderReview,
    ResultClaim,
    ReviewOption,
)
from kayfabe.domain.services.result_adjudication import adjudicate

_SINGLES = MatchUnderReview(
    event_slug="summerslam",
    event_label="SummerSlam 2026",
    match_key="ss26-whc",
    title="World Heavyweight Championship",
    options=(
        ReviewOption(pick="left", name="Roman Reigns"),
        ReviewOption(pick="right", name="Cody Rhodes"),
    ),
)

_LADDER = MatchUnderReview(
    event_slug="money-in-the-bank",
    event_label="Money in the Bank 2026",
    match_key="mitb26-women",
    title="Women's Money in the Bank Ladder Match",
    options=(
        ReviewOption(pick="0", name="Rhea Ripley"),
        ReviewOption(pick="1", name="Iyo Sky"),
        ReviewOption(pick="2", name="Jey Uso"),
        ReviewOption(pick="3", name="Jimmy Uso"),
    ),
)

_ARTICLE = Evidence(
    text=(
        "== Results ==\n"
        "{| class=wikitable\n"
        "! No. ! Results ! Stipulation\n"
        "|-\n"
        "| 1 | Reigns defeated Rhodes by pinfall after a spear "
        "| Singles match for the World Heavyweight Championship\n"
        "|}"
    ),
    source_title="SummerSlam (2026)",
    revision_id="1234567",
)


def _verdict(claim, match=_SINGLES, evidence=(_ARTICLE,)):
    return adjudicate(match, claim, evidence)


class TestWritable:
    def test_matching_quote_and_name_is_writable(self) -> None:
        verdict = _verdict(
            ResultClaim(winner_name="Roman Reigns", quote="Reigns defeated Rhodes")
        )

        assert verdict.writable
        assert verdict.pick == "left"
        assert verdict.hold is None

    def test_provenance_comes_from_evidence(self) -> None:
        """출처와 개정본을 모델이 아니라 우리가 건넨 본문에서 얻는다."""
        verdict = _verdict(
            ResultClaim(winner_name="Roman Reigns", quote="Reigns defeated Rhodes")
        )

        assert verdict.source_title == "SummerSlam (2026)"
        assert verdict.source_revision_id == "1234567"

    def test_written_name_is_the_card_spelling(self) -> None:
        """모델이 성만 적어 보내도 화면에 나가는 것은 카드의 철자다."""
        verdict = _verdict(
            ResultClaim(winner_name="Reigns", quote="Reigns defeated Rhodes")
        )

        assert verdict.writable
        assert verdict.winner_name == "Roman Reigns"

    def test_whitespace_differences_are_absorbed(self) -> None:
        """위키텍스트에는 줄바꿈이 흔하다. 공백만 흡수한다."""
        verdict = _verdict(
            ResultClaim(
                winner_name="Roman Reigns",
                quote="Reigns   defeated\n  Rhodes by pinfall",
            )
        )

        assert verdict.writable

    def test_multi_match_yields_index_pick(self) -> None:
        ladder = Evidence(
            text="Ripley won the match after retrieving the briefcase.",
            source_title="Money in the Bank (2026)",
            revision_id="999",
        )
        verdict = _verdict(
            ResultClaim(winner_name="Rhea Ripley", quote="Ripley won the match"),
            match=_LADDER,
            evidence=(ladder,),
        )

        assert verdict.writable
        assert verdict.pick == "0"

    def test_reversed_narration_still_picks_by_name(self) -> None:
        """위키가 오른쪽 선수를 먼저 적어도 판정은 흔들리지 않는다."""
        reversed_text = Evidence(
            text="Rhodes was defeated by Reigns after a spear.",
            source_title="SummerSlam (2026)",
        )
        verdict = _verdict(
            ResultClaim(
                winner_name="Roman Reigns", quote="Rhodes was defeated by Reigns"
            ),
            evidence=(reversed_text,),
        )

        assert verdict.writable
        assert verdict.pick == "left"


class TestHold:
    def test_absent_claim_holds(self) -> None:
        assert _verdict(None).hold is HoldReason.NO_CLAIM

    def test_null_winner_is_not_breakage(self) -> None:
        """무승부·노컨테스트에서 이것이 정답이다."""
        verdict = _verdict(
            ResultClaim(winner_name=None, quote="The match ended in a draw")
        )

        assert verdict.hold is HoldReason.NO_WINNER
        assert not verdict.writable

    def test_empty_quote_holds(self) -> None:
        verdict = _verdict(ResultClaim(winner_name="Roman Reigns", quote="   "))

        assert verdict.hold is HoldReason.QUOTE_MISSING

    def test_fabricated_quote_holds_even_with_right_name(self) -> None:
        """관문 2가 관문 3보다 앞이라는 계약. 이 순서가 뒤집히면 위조가 통과한다."""
        verdict = _verdict(
            ResultClaim(
                winner_name="Roman Reigns",
                quote="Reigns retained the title in a classic",
            )
        )

        assert verdict.hold is HoldReason.QUOTE_NOT_FOUND
        assert verdict.pick is None

    def test_recased_quote_is_rejected(self) -> None:
        """공백은 흡수하지만 글자는 흡수하지 않는다."""
        verdict = _verdict(
            ResultClaim(winner_name="Roman Reigns", quote="REIGNS DEFEATED RHODES")
        )

        assert verdict.hold is HoldReason.QUOTE_NOT_FOUND

    def test_name_absent_from_card_holds(self) -> None:
        verdict = _verdict(
            ResultClaim(winner_name="Seth Rollins", quote="Reigns defeated Rhodes")
        )

        assert verdict.hold is HoldReason.NAME_NOT_ON_CARD

    def test_name_matching_two_options_holds(self) -> None:
        """`Uso`는 형제 둘에 걸린다 — 어느 쪽인지 모르므로 쓰지 않는다."""
        usos = Evidence(
            text="Uso won the ladder match.", source_title="Money in the Bank (2026)"
        )
        verdict = _verdict(
            ResultClaim(winner_name="Uso", quote="Uso won the ladder match"),
            match=_LADDER,
            evidence=(usos,),
        )

        assert verdict.hold is HoldReason.AMBIGUOUS_NAME

    def test_exact_match_beats_sibling_containment(self) -> None:
        """`Jey Uso`는 정확히 하나다 — 부분 일치까지 모으면 모호해진다."""
        usos = Evidence(
            text="Jey Uso won the ladder match.",
            source_title="Money in the Bank (2026)",
        )
        verdict = _verdict(
            ResultClaim(winner_name="Jey Uso", quote="Jey Uso won the ladder match"),
            match=_LADDER,
            evidence=(usos,),
        )

        assert verdict.writable
        assert verdict.pick == "2"

    def test_quote_without_winner_holds(self) -> None:
        """인용은 본문에 있지만 그 구절에 승자 이름이 없는 경우."""
        verdict = _verdict(
            ResultClaim(
                winner_name="Roman Reigns",
                quote="Singles match for the World Heavyweight Championship",
            )
        )

        assert verdict.hold is HoldReason.NAME_NOT_IN_QUOTE

    def test_no_evidence_holds(self) -> None:
        """도구를 한 번도 못 쓴 채 답한 경우 — 대조할 기준이 없다."""
        verdict = _verdict(
            ResultClaim(winner_name="Roman Reigns", quote="Reigns defeated Rhodes"),
            evidence=(),
        )

        assert verdict.hold is HoldReason.QUOTE_NOT_FOUND


class TestNameMatching:
    def test_partial_word_does_not_match(self) -> None:
        """`uso`가 `carouso`에 걸리면 안 된다."""
        match = MatchUnderReview(
            event_slug="x",
            event_label="X",
            match_key="x1",
            title="Singles",
            options=(
                ReviewOption(pick="left", name="Uso"),
                ReviewOption(pick="right", name="Nakamura"),
            ),
        )
        evidence = (Evidence(text="Carouso defeated Nakamura.", source_title="X"),)
        verdict = adjudicate(
            match,
            ResultClaim(winner_name="Uso", quote="Carouso defeated Nakamura"),
            evidence,
        )

        assert verdict.hold is HoldReason.NAME_NOT_IN_QUOTE

    def test_punctuated_name_matches(self) -> None:
        """`L.A. Knight`가 `la knight`로 정규화되며 단어 경계를 지킨다."""
        match = MatchUnderReview(
            event_slug="x",
            event_label="X",
            match_key="x2",
            title="Singles",
            options=(
                ReviewOption(pick="left", name="L.A. Knight"),
                ReviewOption(pick="right", name="Solo Sikoa"),
            ),
        )
        evidence = (Evidence(text="LA Knight defeated Solo Sikoa.", source_title="X"),)
        verdict = adjudicate(
            match,
            ResultClaim(
                winner_name="L.A. Knight", quote="LA Knight defeated Solo Sikoa"
            ),
            evidence,
        )

        assert verdict.writable
        assert verdict.pick == "left"


class TestDirection:
    """관문 5 — 인용의 승패 방향.

    앞의 관문 넷은 **출처**를 검증한다. 출처가 참이어도 방향은 틀릴 수 있고, 그 구멍이
    2026-09-28 `SummerSlam (2026)` 실측에서 드러났다. 여기 있는 인용문들은 그 문서에서
    그대로 가져온 것이다.
    """

    def _match(self, *names: str) -> MatchUnderReview:
        return MatchUnderReview(
            event_slug="summerslam",
            event_label="SummerSlam 2026",
            match_key="ss26-n1",
            title="Singles match",
            options=tuple(
                ReviewOption(pick=str(i), name=name) for i, name in enumerate(names)
            ),
        )

    def _judge(self, quote: str, winner: str, *names: str):
        return adjudicate(
            self._match(*names),
            ResultClaim(winner_name=winner, quote=quote),
            (Evidence(text=quote, source_title="SummerSlam (2026)"),),
        )

    def test_active_voice_loser_is_rejected(self) -> None:
        """실측으로 뚫린 그 경우. 관문 1~4를 전부 통과하는 주장이다."""
        verdict = self._judge(
            "Liv Morgan (c) defeated Iyo Sky by pinfall",
            "Iyo Sky",
            "Liv Morgan",
            "Iyo Sky",
        )

        assert verdict.hold is HoldReason.CONTRADICTED_BY_QUOTE
        assert verdict.pick is None

    def test_active_voice_winner_is_accepted(self) -> None:
        verdict = self._judge(
            "Liv Morgan (c) defeated Iyo Sky by pinfall",
            "Liv Morgan",
            "Liv Morgan",
            "Iyo Sky",
        )

        assert verdict.writable
        assert verdict.pick == "0"

    def test_passive_voice_is_read_the_other_way(self) -> None:
        """`B was defeated by A`는 **뒤쪽이** 이긴 쪽이다."""
        accepted = self._judge(
            "Rhodes was defeated by Reigns after a spear",
            "Roman Reigns",
            "Roman Reigns",
            "Cody Rhodes",
        )
        rejected = self._judge(
            "Rhodes was defeated by Reigns after a spear",
            "Cody Rhodes",
            "Roman Reigns",
            "Cody Rhodes",
        )

        assert accepted.writable
        assert rejected.hold is HoldReason.CONTRADICTED_BY_QUOTE

    def test_passive_is_checked_before_active(self) -> None:
        """`was defeated by`가 `defeated`를 품고 있다 — 순서가 뒤집히면 거꾸로 읽는다."""
        verdict = self._judge(
            "Iyo Sky was defeated by Liv Morgan",
            "Liv Morgan",
            "Liv Morgan",
            "Iyo Sky",
        )

        assert verdict.writable

    def test_lost_to_is_read(self) -> None:
        verdict = self._judge(
            "Aldis lost to Gunther by submission",
            "Nick Aldis",
            "Gunther",
            "Nick Aldis",
        )

        assert verdict.hold is HoldReason.CONTRADICTED_BY_QUOTE

    def test_loser_inside_a_defeated_team_is_rejected(self) -> None:
        """다인전. 진 팀 안의 이름을 승자라고 주장하는 경우."""
        quote = (
            "LA Knight, Solo Sikoa, and Royce Keys defeated The Bloodline "
            "(Jacob Fatu, Jey Uso, and Jimmy Uso) by pinfall"
        )
        verdict = self._judge(quote, "Jey Uso", "LA Knight", "Jey Uso")

        assert verdict.hold is HoldReason.CONTRADICTED_BY_QUOTE

    def test_winner_inside_a_winning_team_is_accepted(self) -> None:
        quote = (
            "LA Knight, Solo Sikoa, and Royce Keys defeated The Bloodline "
            "(Jacob Fatu, Jey Uso, and Jimmy Uso) by pinfall"
        )
        verdict = self._judge(quote, "LA Knight", "LA Knight", "Jey Uso")

        assert verdict.writable

    def test_unreadable_relation_is_not_a_contradiction(self) -> None:
        """승패 동사가 없으면 모순이라고 말할 수 없다 — 관문 5는 통과시킨다."""
        verdict = self._judge(
            "Ripley retrieved the briefcase to win the ladder match",
            "Rhea Ripley",
            "Rhea Ripley",
            "Iyo Sky",
        )

        assert verdict.writable

    def test_name_on_both_sides_is_not_a_contradiction(self) -> None:
        """양쪽에 다 있으면 어느 쪽인지 모른다. 모르는 것은 모순이 아니다."""
        verdict = self._judge(
            "Jey Uso defeated Jey Uso's former partner",
            "Jey Uso",
            "Jey Uso",
            "Jimmy Uso",
        )

        assert verdict.writable

    def test_beat_does_not_match_inside_beaten(self) -> None:
        """`beat`이 `beaten`에 걸리면 수동태가 능동으로 읽힌다."""
        verdict = self._judge(
            "Iyo Sky was beaten by Liv Morgan",
            "Liv Morgan",
            "Liv Morgan",
            "Iyo Sky",
        )

        assert verdict.writable

    def test_def_abbreviation_is_read(self) -> None:
        """위키 표에는 `def.`로 줄여 적힌 줄이 있다."""
        verdict = self._judge(
            "Gunther def. Nick Aldis by submission",
            "Nick Aldis",
            "Gunther",
            "Nick Aldis",
        )

        assert verdict.hold is HoldReason.CONTRADICTED_BY_QUOTE
