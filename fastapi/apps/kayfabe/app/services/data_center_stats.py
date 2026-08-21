"""데이터 센터 집계 — **순수 함수**. DB도 네트워크도 모른다 (Phase 2).

리포지토리가 읽어 온 행을 받아 세는 일만 한다. 그래서 이 파일은 DB 없이 테스트되고,
집계 규칙이 바뀔 때 고칠 자리가 한 곳이다.

**세는 것 말고는 아무것도 하지 않는다.** 없는 값을 추정하지 않고, 표본이 모자라면
`None`을 돌려 화면이 그 칸을 비우게 한다 — 0으로 채우면 "0%"라는 거짓이 된다.

기존 `records_scoring`을 그대로 쓴다. 선수 한 명의 전적을 내는 규칙(태그팀 이름을
개인으로 펼치고, `winner_pick`에서 승자를 되짚고, 승자를 못 정하면 무효로 접는 것)이
이미 거기 있고, **화면마다 다른 규칙으로 세면 같은 선수의 승률이 두 개가 된다.**
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from kayfabe.app.services.title_match_classifier import is_championship_match

# **`records_scoring`은 함수 안에서 임포트한다.** 그 모듈이 인바운드 스키마를
# 끌어오는데, 그러면 `kayfabe.adapter.inbound.api` 패키지 초기화가 돌면서 라우터
# 전체가 깨어나고 — 그 라우터가 프로바이더·인터랙터를 거쳐 다시 이 파일을 부른다
# (순환 임포트). 이 파일이 **아무것도 깨우지 않는 잎**으로 남아야 그 고리가 끊긴다.
# `records_scoring`이 `json`을 함수 안에서 부르는 것과 같은 자리다.

MIN_MATCHES_FOR_RATE = 3
"""승률 순위에 오르는 최소 경기 수.

지금 명부에는 한 경기만 뛴 선수가 수두룩하다. 그들을 섞으면 순위표 위쪽이 전부
1승 0패 100%가 되어 **순위가 아무것도 말하지 않는다.** 값을 상수로 두는 이유는
화면이 "3경기 이상"이라고 함께 적어야 하기 때문이다.
"""


@dataclass(frozen=True)
class MatchRow:
    """`ple_matches` 한 행 + 그 대회 정보. 리포지토리가 채운다."""

    event_slug: str
    event_label: str
    month: int | None
    year: int
    event_status: str
    match_key: str
    title: str
    format: str
    card_json: str
    winner_pick: str | None
    winner_name: str | None
    status: str


@dataclass(frozen=True)
class WrestlerRow:
    """`wrestlers` 한 행."""

    name: str
    brand: str | None = None
    real_name: str | None = None
    birth_date: str | None = None
    finisher: str | None = None
    stable_team: str | None = None


@dataclass(frozen=True)
class TitleRow:
    """`title_acquisitions` 한 행. `won_at`은 자유 텍스트다 — 날짜로 파싱하지 않는다."""

    competitor_name: str
    belt_name: str
    won_at: str


@dataclass(frozen=True)
class MatchFact:
    """집계하기 좋게 편 경기 하나."""

    event_slug: str
    event_label: str
    month: int | None
    year: int
    match_key: str
    title: str
    format: str
    status: str
    participants: tuple[str, ...]
    """개인 링네임. 태그팀 이름은 사람으로 펼쳐진다."""
    winner_name: str | None
    is_title_match: bool

    @property
    def is_finished(self) -> bool:
        return self.status.strip().lower() == "finished"


@dataclass(frozen=True)
class RecordCount:
    wins: int = 0
    losses: int = 0
    no_contest: int = 0
    pending: int = 0

    @property
    def total(self) -> int:
        return self.wins + self.losses + self.no_contest + self.pending

    @property
    def decided(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float | None:
        """승 / (승+패). **한 판도 안 끝났으면 None이다** — 0.0이 아니다."""
        if self.decided == 0:
            return None
        return round(self.wins / self.decided, 4)


def normalize(name: str) -> str:
    """이름 정규화 창구.

    **밖에서는 `records_scoring`을 직접 부르지 않는다.** 그 모듈이 인바운드 스키마를
    끌어와 라우터 그래프를 깨우기 때문이다(위 주석). 인터랙터가 쓰는 것은 이 함수뿐이다.
    """
    from kayfabe.app.services.records_scoring import normalize_name

    return normalize_name(name)


def to_fact(row: MatchRow) -> MatchFact:
    from kayfabe.app.services.records_scoring import (
        derive_match_record_from_orm,
        names_from_card_json,
    )

    participants = tuple(names_from_card_json(row.card_json)) if row.card_json else ()
    # 승자 이름은 한 번만 되짚는다 — 아무 참가자나 넣어도 같은 값이 나온다.
    probe = participants[0] if participants else ""
    derived = derive_match_record_from_orm(
        event_slug=row.event_slug,
        event_label=row.event_label,
        match_key=row.match_key,
        title=row.title,
        format=row.format,
        card_json=row.card_json,
        winner_pick=row.winner_pick,
        winner_name=row.winner_name,
        status=row.status,
        name=probe,
    )
    return MatchFact(
        event_slug=row.event_slug,
        event_label=row.event_label,
        month=row.month,
        year=row.year,
        match_key=row.match_key,
        title=row.title,
        format="multi" if row.format == "multi" else "singles",
        status=row.status,
        participants=participants,
        winner_name=derived.winner_name,
        is_title_match=is_championship_match(row.title, row.match_key),
    )


def to_facts(rows: Iterable[MatchRow]) -> list[MatchFact]:
    return [to_fact(row) for row in rows]


def records_by_wrestler(rows: Sequence[MatchRow]) -> dict[str, RecordCount]:
    """선수 이름 → 전적. **경기를 한 번만 훑는다.**

    선수 한 명씩 프로필 API를 부르면 그 안에서 매번 전체 경기를 다시 스캔한다
    (`get_competitor_profile`). 목록 화면은 178명이라 그 방식이 178배가 된다.
    """
    from kayfabe.app.services.records_scoring import (
        derive_match_record_from_orm,
        names_from_card_json,
        normalize_name,
    )

    tally: dict[str, dict[str, int]] = defaultdict(
        lambda: {"win": 0, "loss": 0, "no-contest": 0, "pending": 0}
    )
    for row in rows:
        if not row.card_json:
            continue
        for individual in names_from_card_json(row.card_json):
            record = derive_match_record_from_orm(
                event_slug=row.event_slug,
                event_label=row.event_label,
                match_key=row.match_key,
                title=row.title,
                format=row.format,
                card_json=row.card_json,
                winner_pick=row.winner_pick,
                winner_name=row.winner_name,
                status=row.status,
                name=individual,
            )
            tally[normalize_name(individual)][record.result] += 1

    return {
        name: RecordCount(
            wins=counts["win"],
            losses=counts["loss"],
            no_contest=counts["no-contest"],
            pending=counts["pending"],
        )
        for name, counts in tally.items()
    }


def titles_by_wrestler(rows: Iterable[TitleRow]) -> dict[str, int]:
    """선수 이름 → 벨트 획득 횟수."""
    from kayfabe.app.services.records_scoring import normalize_name

    counter: Counter[str] = Counter()
    for row in rows:
        counter[normalize_name(row.competitor_name)] += 1
    return dict(counter)


@dataclass(frozen=True)
class BeltStat:
    belt_name: str
    reigns: int
    holders: int
    top_holder: str | None
    top_holder_reigns: int


def belt_stats(rows: Sequence[TitleRow]) -> list[BeltStat]:
    """벨트별 획득 집계 (§9).

    **재위 기간은 세지 않는다.** `won_at`이 `"Payback — June 16, 2013"` 같은 자유
    텍스트이고 끝난 날짜가 없어서, 최장 재위는 지금 데이터로 만들 수 없다 — 날짜를
    추정해 넣으면 그건 가짜 통계다(2026-08-20 사용자 결정). 획득 **횟수**만 센다.
    """
    from kayfabe.app.services.records_scoring import normalize_name

    per_belt: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        per_belt[row.belt_name][normalize_name(row.competitor_name)] += 1

    stats: list[BeltStat] = []
    for belt, holders in per_belt.items():
        top_name, top_count = holders.most_common(1)[0]
        stats.append(
            BeltStat(
                belt_name=belt,
                reigns=sum(holders.values()),
                holders=len(holders),
                top_holder=top_name,
                top_holder_reigns=top_count,
            )
        )
    return sorted(stats, key=lambda s: (-s.reigns, s.belt_name))


@dataclass(frozen=True)
class HolderStat:
    name: str
    reigns: int
    belts: int


def top_holders(rows: Sequence[TitleRow], limit: int = 10) -> list[HolderStat]:
    from kayfabe.app.services.records_scoring import normalize_name

    per_person: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        per_person[normalize_name(row.competitor_name)][row.belt_name] += 1

    stats = [
        HolderStat(name=name, reigns=sum(belts.values()), belts=len(belts))
        for name, belts in per_person.items()
    ]
    return sorted(stats, key=lambda s: (-s.reigns, -s.belts, s.name))[:limit]


@dataclass(frozen=True)
class EventStat:
    slug: str
    label: str
    month: int | None
    year: int
    matches: int
    finished: int
    title_matches: int
    multi_matches: int


def event_stats(facts: Sequence[MatchFact]) -> list[EventStat]:
    grouped: dict[str, list[MatchFact]] = defaultdict(list)
    for fact in facts:
        grouped[fact.event_slug].append(fact)

    stats = [
        EventStat(
            slug=slug,
            label=items[0].event_label,
            month=items[0].month,
            year=items[0].year,
            matches=len(items),
            finished=sum(1 for f in items if f.is_finished),
            title_matches=sum(1 for f in items if f.is_title_match),
            multi_matches=sum(1 for f in items if f.format == "multi"),
        )
        for slug, items in grouped.items()
    ]
    # 달이 없는 대회(미정)는 뒤로 보낸다 — 날짜를 지어내지 않는다.
    return sorted(stats, key=lambda s: (s.year, s.month is None, s.month or 0, s.slug))


def brand_distribution(rows: Iterable[WrestlerRow]) -> list[tuple[str, int]]:
    """브랜드별 선수 수. **실제 DB 값만** 쓴다 — 목록을 코드에 박지 않는다 (§2)."""
    counter: Counter[str] = Counter()
    for row in rows:
        counter[(row.brand or "").strip() or "미지정"] += 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def known_brands(rows: Iterable[WrestlerRow]) -> list[str]:
    return [brand for brand, _ in brand_distribution(rows) if brand != "미지정"]


@dataclass(frozen=True)
class RatedWrestler:
    name: str
    wins: int
    losses: int
    win_rate: float


def top_win_rates(
    records: dict[str, RecordCount],
    *,
    limit: int = 10,
    min_matches: int = MIN_MATCHES_FOR_RATE,
) -> list[RatedWrestler]:
    """승률 순위. **표본이 얇은 선수는 아예 안 올린다** (`MIN_MATCHES_FOR_RATE`)."""
    rated: list[RatedWrestler] = []
    for name, record in records.items():
        rate = record.win_rate
        if rate is None or record.decided < min_matches:
            continue
        rated.append(
            RatedWrestler(
                name=name, wins=record.wins, losses=record.losses, win_rate=rate
            )
        )
    return sorted(rated, key=lambda r: (-r.win_rate, -r.wins, r.name))[:limit]
