"""규칙 기반 서술 생성기 (하네스 §3-D3 · T6).

**LLM을 부르지 않는다.** 게임 루프에 네트워크 호출이 0회여야 하고(§11-13), 자동 진행은
주차마다 한 줄을 만들기 때문에 지연을 감당할 수도 없다. 문장은 템플릿 뱅크와 슬롯
조합에서 나온다.

이 파일에는 **문장이 한 줄도 없다** — 전부 `templates.py`에 있다(§6). 여기 있는 것은 셋뿐이다.

1. **어떤 사건을 이야기할지** 고른다 (`_beat_of`, 한 주차에 한 줄이므로 우선순위가 필요하다)
2. **슬롯을 채운다** (국가·플레이스타일·인기도·대립에서)
3. **템플릿을 고른다** (시드 파생 — 같은 세이브는 같은 문장, §11-4)

조사는 `_JosaFormatter`가 받침을 보고 고른다. `"{player:이}"`처럼 포맷 스펙 자리에 조사를
적으면 된다.
"""

from __future__ import annotations

from string import Formatter
from typing import Final

from wwe_game.adapter.outbound.narration.templates import (
    CROWDS,
    MOVES,
    REACTION_BANDS,
    TEMPLATES,
    VENUES,
    Beat,
)
from wwe_game.app.ports.output.narration_port import NarrationPort
from wwe_game.domain.constants.countries import Region
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import rivalry_engine, seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import TITLES
from wwe_game.domain.value_objects.week_report import (
    CallUpReason,
    OutcomeKind,
    WeekKind,
    WeekReport,
)

# ── 조사 ─────────────────────────────────────────────────────

_JOSA: Final[dict[str, tuple[str, str]]] = {
    # 스펙: (받침 있음, 받침 없음)
    "은": ("은", "는"),
    "는": ("은", "는"),
    "이": ("이", "가"),
    "가": ("이", "가"),
    "을": ("을", "를"),
    "를": ("을", "를"),
    "과": ("과", "와"),
    "와": ("과", "와"),
    "과의": ("과의", "와의"),
    "으로": ("으로", "로"),
    "이었다": ("이었다", "였다"),
}

_HANGUL_START, _HANGUL_END = 0xAC00, 0xD7A3
_JONG_COUNT = 28
_JONG_RIEUL = 8
_ASCII_VOWELS = frozenset("aeiouyAEIOUY")


def _ends_with_batchim(word: str) -> tuple[bool, bool]:
    """(받침이 있는가, 그 받침이 ㄹ인가).

    한글 음절이면 정확히 계산하고, 아니면 마지막 글자로 어림한다 — 링 네임은 사용자
    자유 입력이라 영문이 들어올 수 있다(§3-D12). 어림이 틀려도 문장이 어색해질 뿐이다.
    """
    if not word:
        return False, False
    last = word[-1]
    code = ord(last)
    if _HANGUL_START <= code <= _HANGUL_END:
        jong = (code - _HANGUL_START) % _JONG_COUNT
        return jong != 0, jong == _JONG_RIEUL
    if last.isascii() and last.isalpha():
        return last not in _ASCII_VOWELS, last in "lLrR"
    return True, False


def josa_for(word: str, spec: str) -> str:
    """받침에 맞는 조사. `으로`만 ㄹ 받침을 예외로 둔다 — '칼로', '서울로'."""
    with_batchim, is_rieul = _ends_with_batchim(word)
    if spec == "으로" and is_rieul:
        return "로"
    hard, soft = _JOSA[spec]
    return hard if with_batchim else soft


class _JosaFormatter(Formatter):
    """포맷 스펙을 조사로 해석한다. 모르는 스펙은 원래 `format`에 넘긴다."""

    def format_field(self, value: object, format_spec: str) -> str:
        text = str(value)
        if format_spec in _JOSA:
            return text + josa_for(text, format_spec)
        return super().format_field(value, format_spec)


_FORMATTER: Final = _JosaFormatter()


# ── 템플릿이 요구하는 슬롯 ───────────────────────────────────


def _fields_of(template: str) -> frozenset[str]:
    return frozenset(
        name for _, name, _, _ in Formatter().parse(template) if name is not None
    )


_REQUIRED: Final[dict[str, frozenset[str]]] = {
    template: _fields_of(template)
    for templates in TEMPLATES.values()
    for template in templates
}

OPTIONAL_SLOTS: Final = frozenset({"rival", "title", "show"})
"""주차에 따라 비어 있을 수 있는 슬롯. 비면 그 슬롯을 쓰는 템플릿이 후보에서 빠진다."""

TITLE_BEATS: Final = frozenset({Beat.TITLE_WON, Beat.TITLE_DEFENDED, Beat.TITLE_LOST})

MIN_RIVAL_FREE_TEMPLATES: Final = 3
"""대립이 없는 커리어도 이만큼은 고를 수 있어야 한다.

**후보가 마르면 다양성 기준(§11-6)이 먼저 깨진다.** 커리어 초반에는 대립이 아예 없고,
그 구간이 30주를 훌쩍 넘는다 — `{rival}`을 쓰는 문장만 잔뜩 두면 그 구간 내내 같은
몇 줄이 돌아간다.
"""

VARYING_SLOTS: Final = frozenset({"venue", "crowd", "move", "reaction"})
"""한 커리어 안에서도 값이 바뀌는 슬롯. `player`는 고정이라 여기 없다.

**모든 템플릿이 이 중 하나는 써야 한다.** 처음엔 비트마다 8~12줄을 두고 슬롯 없는
문장을 섞었는데, 30주를 돌리자 같은 줄이 **최대 6회**까지 나와 §11-6이 깨졌다. 12줄을
30번 뽑으면 비둘기집으로 5~6회가 나오는 게 당연했다 — 줄 수를 60개로 늘리는 대신
줄마다 5~7가지 값을 물려 조합을 60~84개로 벌렸다. 덱의 본문 변주와 같은 처방이다.
"""


def _validate_bank() -> None:
    """뱅크의 구조 불변식을 **임포트 시점에** 터뜨린다 (덱 로더와 같은 방침, §3-D19).

    런타임에는 "어쩌다 문장이 겹친다"로 나타나서, 어느 비트가 말랐는지 알기 어렵다.
    """
    for beat, templates in TEMPLATES.items():
        if not templates:
            raise RuntimeError(f"{beat}: 템플릿이 비어 있습니다")
        rival_free = [t for t in templates if "rival" not in _REQUIRED[t]]
        if len(rival_free) < MIN_RIVAL_FREE_TEMPLATES:
            raise RuntimeError(
                f"{beat}: 대립 없이 쓸 수 있는 템플릿이 "
                f"{len(rival_free)}개뿐입니다 (최소 {MIN_RIVAL_FREE_TEMPLATES})"
            )
        for template in templates:
            if not VARYING_SLOTS & _REQUIRED[template]:
                raise RuntimeError(
                    f"{beat}: 변주 슬롯이 없는 문장은 그대로 반복된다 — {template!r}"
                )
        uses_title = any("title" in _REQUIRED[t] for t in templates)
        if uses_title and beat not in TITLE_BEATS:
            raise RuntimeError(
                f"{beat}: 벨트가 걸리지 않는 주차에 {{title}}을 썼습니다"
            )


_validate_bank()


# ── 무대 (§3-D14-1) ──────────────────────────────────────────

HOME_REGION = Region.NA
"""단체의 안방. **주간 투어는 미국을 돈다.**

처음엔 선수 국적의 권역을 그대로 무대로 썼는데, 그러면 한국 선수의 30년 커리어가
**전부 한국에서** 열린다. 국적은 선수의 출신이지 단체의 소재지가 아니다.
"""

TOUR_CHANCE = 0.12
"""한 주차가 해외 투어일 확률. 나머지 88%는 북미다.

연 52주 중 6주쯤이 해외가 된다 — 실제 투어 빈도에 가깝고, 서술로 봐도 "가끔 나가는"
정도로 읽힌다. 0.3까지 올려 봤더니 격주로 대륙을 옮겨 다녀 투어가 특별하지 않았다.
"""

HOMECOMING_SHARE = 0.40
"""해외 투어 중 **선수의 고향 권역**으로 가는 비율.

국가는 이벤트 조건이 아니라 서술 슬롯으로 쓰기로 했고(§3-D14), 개선 경기는 그 결정이
화면에 드러나는 몇 안 되는 자리다. 균등하게 뿌리면 한국 선수가 한국에 서는 일이
30년에 두어 번뿐이라 국적을 고른 의미가 사라진다. 북미 출신은 이 가중이 없다 —
그쪽은 매주가 개선 경기다.
"""

_AWAY_REGIONS: Final = tuple(r for r in Region if r is not HOME_REGION)


def stage_region(home: Region, roll: SeededRoll) -> Region:
    """이번 주 무대의 권역. 평소 북미, 가끔 해외, 그중 얼마간은 선수의 고향."""
    if not roll.chance(TOUR_CHANCE):
        return HOME_REGION
    if home is not HOME_REGION and roll.chance(HOMECOMING_SHARE):
        return home
    return roll.pick(_AWAY_REGIONS)


# ── 나레이터 ─────────────────────────────────────────────────

_MATCH_BEATS: Final[dict[tuple[bool, OutcomeKind], Beat]] = {
    (True, OutcomeKind.WIN): Beat.PLE_WIN,
    (True, OutcomeKind.LOSS): Beat.PLE_LOSS,
    (True, OutcomeKind.DRAW): Beat.PLE_DRAW,
    (False, OutcomeKind.WIN): Beat.SHOW_WIN,
    (False, OutcomeKind.LOSS): Beat.SHOW_LOSS,
    (False, OutcomeKind.DRAW): Beat.SHOW_DRAW,
}


def beat_of(report: WeekReport) -> Beat:
    """한 주차에 여러 사건이 겹치면 **더 오래 남을 쪽**을 고른다.

    리포트만 보는 순수 함수다 — 어떤 사건을 이야기할지는 세이브 상태와 무관하고,
    따로 떼어 두면 우선순위를 문장 없이 검증할 수 있다.

    순서를 정한 근거: 소속이 바뀌는 것은 커리어의 장이 바뀌는 일이라 가장 앞이고,
    **벨트의 주인이 바뀌는 것**이 부상보다 앞선다 — 부상은 다음 주 결장 문장에서
    어차피 이어지지만, 벨트가 오가는 장면은 그 주에만 있다. 방어 성공은 상태가
    그대로라 가장 뒤다.
    """
    if report.call_up is CallUpReason.EMERGENCY:
        return Beat.CALL_UP_EMERGENCY
    if report.call_up is CallUpReason.EARNED:
        return Beat.CALL_UP_EARNED
    if report.is_title_match and report.result is OutcomeKind.WIN:
        return Beat.TITLE_DEFENDED if report.title_defended else Beat.TITLE_WON
    if report.title_defended:
        return Beat.TITLE_LOST
    if report.injury is not None:
        return Beat.INJURY
    if report.draft_night:
        return Beat.DRAFT
    # 저주로 진 경기는 평범한 패배와 다르게 읽혀야 한다. 벨트가 오간 주차에는 그쪽이
    # 먼저다 — 저주는 다음에도 걸 수 있지만 벨트가 넘어가는 장면은 그 주에만 있다.
    if report.cursed:
        return Beat.CURSED_LOSS
    if report.kind is WeekKind.OFF:
        return Beat.OFF
    if report.kind is WeekKind.PROMO:
        return Beat.PROMO_HIT if report.promo_hit else Beat.PROMO
    # 특별 방송(SNME)도 대회 문구를 쓴다 — 경기가 보장된 밤이고, `{show}`가 이름을
    # 채워 주므로 "주간 방송 중반 경기"가 아니라 그 방송의 이름으로 읽힌다 (§3-D21-2).
    return _MATCH_BEATS[(report.is_big_match_night, report.result)]


class RuleNarrator(NarrationPort):
    """주차 리포트 한 건을 한 줄로 옮긴다.

    `NarrationPort`의 유일한 구현이다(§3-D9). LLM 어댑터 자리는 비워 두되 만들지 않는다.
    """

    def narrate(self, run: CareerRun, report: WeekReport) -> str:
        """`run`은 이 리포트를 **만들어 낸** 상태다 — `simulate_week(run) -> report`.

        반영된 뒤의 상태를 넘기면 승리 문장에 이미 오른 인기도가 반영돼 온도가 어긋난다.
        """
        roll = SeededRoll(run.seed, report.week, seeded_roll.NARRATION)
        slots = self._slots(run, report, roll)
        available = {k for k, v in slots.items() if v is not None}
        pool = tuple(t for t in TEMPLATES[beat_of(report)] if _REQUIRED[t] <= available)
        return _FORMATTER.vformat(roll.pick(pool), (), slots)

    def _slots(
        self, run: CareerRun, report: WeekReport, roll: SeededRoll
    ) -> dict[str, str | None]:
        stage = stage_region(run.identity.region, roll)
        rival = rivalry_engine.top_rivalry(run)
        title = report.title_at_stake
        return {
            "player": run.identity.name.value,
            "venue": roll.pick(VENUES[stage]),
            "crowd": roll.pick(CROWDS[stage]),
            "move": roll.pick(MOVES[run.identity.play_style]),
            "reaction": roll.pick(self._reactions(run.stats.popularity)),
            "show": report.show.name if report.show is not None else None,
            "rival": rival.rival_name if rival is not None else None,
            "title": TITLES[title].display_name if title is not None else None,
        }

    def _reactions(self, popularity: int) -> tuple[str, ...]:
        for ceiling, bank in REACTION_BANDS:
            if popularity < ceiling:
                return bank
        raise AssertionError("인기도 구간이 비어 있습니다")  # pragma: no cover
