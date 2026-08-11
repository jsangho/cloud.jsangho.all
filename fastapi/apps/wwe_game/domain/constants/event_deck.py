"""이벤트 덱 로더 (하네스 §3-D19).

**JSON을 읽는 코드는 이 파일 하나뿐이다**(§4-13). 카드 내용은 데이터에, 판정은 코드에 둔다.

임포트 시점에 스키마를 전부 검증한다 — 덱은 콘텐츠라 자주 손대는데, 오타 하나가
"조건이 안 맞아 영영 안 뜨는 카드"로 조용히 남는 게 가장 잡기 어렵다. 그래서 로드가
실패하면 앱이 뜨지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum
from itertools import combinations
from pathlib import Path

from wwe_game.domain.constants.countries import Region
from wwe_game.domain.entities.career_run import RivalryStage
from wwe_game.domain.value_objects.condition import InjuryGrade
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle, StyleFamily
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

CARDS_DIR = Path(__file__).parent / "cards"
"""`data/`가 아니라 `cards/`인 이유: 저장소 `.gitignore`가 `data/`를 통째로 무시한다.

덱은 데이터셋이 아니라 **소스 콘텐츠**다 — 커밋돼야 한다. 부모 디렉터리가 제외되면
하위 예외(`!`)가 먹지 않으므로 이름을 바꾸는 쪽이 깔끔하다.
"""

_STAT_KEYS = {
    "popularity": "popularity",
    "inRing": "in_ring",
    "micWork": "mic_work",
    "backstage": "backstage",
    "alignment": "alignment",
    "wear": "wear",
}
"""JSON은 camelCase, 도메인은 snake_case. 변환은 이 경계에서만 일어난다."""

_CLAMPABLE = set(WrestlerStats.__dataclass_fields__)
BODY_SIMILARITY_LIMIT = 0.55


class Arena(StrEnum):
    IN_RING = "in_ring"
    BACKSTAGE = "backstage"
    BROADCAST = "broadcast"
    PUBLIC = "public"


class CardKind(StrEnum):
    MAIN = "main"
    SUB = "sub"


class Risk(StrEnum):
    SAFE = "safe"
    BOLD = "bold"
    RECKLESS = "reckless"


@dataclass(frozen=True)
class EventRequirement:
    """생략한 조건은 "무관"이다. 모든 조건은 AND, 리스트 안은 OR."""

    acts: frozenset[int] = frozenset()
    brands: frozenset[Brand] = frozenset()
    """소속 제한. NXT 전용 카드처럼 무대가 정해진 사건에만 쓴다."""
    min_week: int = 0
    max_week: int | None = None
    min_age: int | None = None
    max_age: int | None = None
    stats: tuple[tuple[str, int, int], ...] = ()
    alignment: tuple[int, int] | None = None
    regions: frozenset[Region] = frozenset()
    style_families: frozenset[StyleFamily] = frozenset()
    """계열 제한. **스타일 카드의 기본 조건이다** (§3-D27).

    21종에 값마다 5장을 주면 스타일 카드만 105장이 되어 §3-D14가 국가에서 겪은 문제를
    그대로 반복한다. 계열 6종에 붙이면 30장으로 같은 약속을 지킨다.
    """
    play_styles: frozenset[PlayStyle] = frozenset()
    """스타일 하나만 겪는 사건에 쓴다. 계열로 묶으면 뜻이 사라지는 카드만 여기 온다."""
    rivalry_stages: frozenset[RivalryStage] = frozenset()
    condition_grades: frozenset[InjuryGrade] = frozenset()
    flags: frozenset[str] = frozenset()
    holds_briefcase: bool = False
    """머니 인 더 뱅크 가방을 들고 있어야 뜨는 카드 (§3-D36).

    **표식이 아니라 상태를 읽는 유일한 조건이다.** 가방은 규칙이 주는 것이라
    `flags`로 표현할 수 없다 — 표식은 카드가 남기고 규칙이 읽는다는 약속(§3-D26)의
    반대 방향이다.
    """


@dataclass(frozen=True)
class Choice:
    code: str
    label: str
    risk: Risk
    effects: tuple[tuple[str, int], ...]
    """`(도메인 스탯명, 델타)`. dict가 아니라 튜플인 이유는 카드가 불변이어야 해서다."""
    injury_risk: float = 0.0
    heat: int = 0
    flags: frozenset[str] = frozenset()
    career_ending: bool = False

    def stat_deltas(self) -> dict[str, int]:
        """`WrestlerStats.apply()`가 받는 형태. `wear`는 여기서 빠진다 — 컨디션 소관."""
        return {k: v for k, v in self.effects if k in _CLAMPABLE}

    @property
    def wear_delta(self) -> int:
        return dict(self.effects).get("wear", 0)


@dataclass(frozen=True)
class EventCard:
    code: str
    kind: CardKind
    arena: Arena
    title: str
    bodies: tuple[str, ...]
    weight: int
    once: bool
    requires: EventRequirement
    choices: tuple[Choice, ...]
    source: str = field(compare=False, default="")

    def body_at(self, index: int) -> str:
        return self.bodies[index % len(self.bodies)]

    def choice(self, code: str) -> Choice | None:
        return next((c for c in self.choices if c.code == code), None)


class DeckError(RuntimeError):
    """덱 데이터가 스키마를 어겼을 때. 임포트 시점에 터진다."""


def _requirement(raw: dict[str, object]) -> EventRequirement:
    stats = tuple(
        (_STAT_KEYS[k], lo, hi)
        for k, (lo, hi) in dict(raw.get("stats", {})).items()  # type: ignore[misc]
    )
    alignment = raw.get("alignment")
    return EventRequirement(
        acts=frozenset(raw.get("acts", ())),  # type: ignore[arg-type]
        brands=frozenset(Brand(b) for b in raw.get("brands", ())),  # type: ignore[arg-type]
        min_week=int(raw.get("minWeek", 0)),  # type: ignore[arg-type]
        max_week=raw.get("maxWeek"),  # type: ignore[arg-type]
        min_age=raw.get("minAge"),  # type: ignore[arg-type]
        max_age=raw.get("maxAge"),  # type: ignore[arg-type]
        stats=stats,
        alignment=(alignment[0], alignment[1]) if alignment else None,  # type: ignore[index]
        regions=frozenset(Region(r) for r in raw.get("regions", ())),  # type: ignore[arg-type]
        style_families=frozenset(
            StyleFamily(f)
            for f in raw.get("styleFamily", ())  # type: ignore[arg-type]
        ),
        play_styles=frozenset(PlayStyle(p) for p in raw.get("playStyles", ())),  # type: ignore[arg-type]
        rivalry_stages=frozenset(
            RivalryStage(s)
            for s in raw.get("rivalryStage", ())  # type: ignore[arg-type]
        ),
        condition_grades=frozenset(
            InjuryGrade(g)
            for g in raw.get("conditionGrades", ())  # type: ignore[arg-type]
        ),
        flags=frozenset(raw.get("flags", ())),  # type: ignore[arg-type]
        holds_briefcase=bool(raw.get("holdsBriefcase", False)),
    )


def _choice(raw: dict[str, object], card_code: str) -> Choice:
    effects_raw: dict[str, int] = raw["effects"]  # type: ignore[assignment]
    unknown = set(effects_raw) - set(_STAT_KEYS)
    if unknown:
        raise DeckError(f"{card_code}/{raw['code']}: 모르는 스탯 {sorted(unknown)}")
    if "popularity" not in effects_raw or "inRing" not in effects_raw:
        raise DeckError(
            f"{card_code}/{raw['code']}: 인기도·경기력이 둘 다 있어야 합니다"
        )
    if effects_raw["popularity"] == effects_raw["inRing"]:
        raise DeckError(f"{card_code}/{raw['code']}: 인기도와 경기력이 같습니다")
    return Choice(
        code=str(raw["code"]),
        label=str(raw["label"]),
        risk=Risk(raw["risk"]),  # type: ignore[arg-type]
        effects=tuple((_STAT_KEYS[k], v) for k, v in effects_raw.items()),
        injury_risk=float(raw.get("injuryRisk", 0.0)),  # type: ignore[arg-type]
        heat=int(raw.get("heat", 0)),  # type: ignore[arg-type]
        flags=frozenset(raw.get("flags", ())),  # type: ignore[arg-type]
        career_ending=bool(raw.get("careerEnding", False)),
    )


def _card(raw: dict[str, object], source: str) -> EventCard:
    code = str(raw["code"])
    once = bool(raw.get("once", False))
    if once:
        if "bodies" in raw or not raw.get("body"):
            raise DeckError(f"{code}: once 카드는 `body` 하나여야 합니다")
        bodies = (str(raw["body"]),)
    else:
        if "body" in raw or len(raw.get("bodies", ())) < 3:  # type: ignore[arg-type]
            raise DeckError(f"{code}: 반복 카드는 `bodies` 3개 이상이어야 합니다")
        bodies = tuple(str(b) for b in raw["bodies"])  # type: ignore[union-attr]
        for a, b in combinations(bodies, 2):
            if SequenceMatcher(None, a, b).ratio() > BODY_SIMILARITY_LIMIT:
                raise DeckError(
                    f"{code}: 변주가 서로 너무 비슷합니다 — 원문 축약은 변주가 아닙니다"
                )
    choices = tuple(_choice(c, code) for c in raw["choices"])  # type: ignore[union-attr]
    if not 2 <= len(choices) <= 3:
        raise DeckError(f"{code}: 선택지는 2~3개여야 합니다")
    return EventCard(
        code=code,
        kind=CardKind(raw["kind"]),  # type: ignore[arg-type]
        arena=Arena(raw["arena"]),  # type: ignore[arg-type]
        title=str(raw["title"]),
        bodies=bodies,
        weight=int(raw["weight"]),  # type: ignore[arg-type]
        once=once,
        requires=_requirement(raw.get("requires", {})),  # type: ignore[arg-type]
        choices=choices,
        source=source,
    )


def _load() -> tuple[EventCard, ...]:
    cards: list[EventCard] = []
    for path in sorted(CARDS_DIR.glob("events_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cards.extend(_card(c, path.name) for c in payload["cards"])

    seen: dict[str, str] = {}
    for card in cards:
        if card.code in seen:
            raise DeckError(
                f"코드 중복: {card.code} ({seen[card.code]} ↔ {card.source})"
            )
        seen[card.code] = card.source

    produced = {f for c in cards for ch in c.choices for f in ch.flags}
    required = {f for c in cards for f in c.requires.flags}
    if orphan := required - produced:
        raise DeckError(f"아무도 남기지 않는 플래그를 요구합니다: {sorted(orphan)}")

    if not cards:
        raise DeckError(f"덱이 비었습니다: {CARDS_DIR}")
    return tuple(cards)


DECK: tuple[EventCard, ...] = _load()
BY_CODE: dict[str, EventCard] = {c.code: c for c in DECK}

ROLLING_FLAGS: frozenset[str] = frozenset(
    f for c in DECK for ch in c.choices for f in ch.flags
)
"""덱이 남길 수 있는 모든 플래그. `career_rules`가 읽는 것들이 여기 섞여 있다."""
