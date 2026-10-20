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

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

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
    #: 실제 출생지 (`Woodstock, Georgia, U.S.`).
    birth_place: str | None = None
    #: 방송이 부르는 연고지. `|`로 여럿일 수 있다 (`Atlanta, Georgia | Suplex City`).
    billed_from: str | None = None
    #: 길러 준 사람·학교. `|`로 여럿일 수 있다 (평균 2.3개).
    trainer: str | None = None
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
    """벨트별 획득 집계 (§9).

    **재위 기간은 세지 않는다**(2026-08-20 사용자 결정). 획득 **횟수**만 센다.
    이유가 둘이고, 2026-10-20에 **하나는 사라졌으니 섞지 말 것**:

    1. ~~`won_at`이 자유 텍스트라 날짜를 못 읽는다~~ → **풀렸다.**
       `domain/services/title_event_date`가 `"Payback — June 16, 2013"`을 갈라
       388/388(100%)을 읽는다.
    2. **끝난 날짜가 없다.** 재위는 시작과 끝이 있어야 하는데 이 표에는 **획득만**
       있다. 이쪽은 그대로 막혀 있다.

    **"다음 획득을 끝으로 보면 된다"는 안 된다.** 이 표는 완전한 계보가 아니라
    선수별 하이라이트 목록이다 — WWE Championship이 23년간 **45건**뿐이라 획득
    사이 간격(735일·896일)은 재위가 아니라 **기록 공백**이다. 그걸 재위로 적으면
    가짜 통계가 된다.
    """

    belt_name: str
    reigns: int
    holders: int
    top_holder: str | None
    top_holder_reigns: int
    #: 이 집계에 합쳐진 옛 이름 (`belt_lineage`). 없으면 빈 목록이다.
    former_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExcludedBelt:
    """현 벨트로 이어지지 않아 집계에서 뺀 이름."""

    belt_name: str
    reigns: int
    reason: str


@dataclass(frozen=True)
class CurrentBeltStats:
    belts: list[BeltStat]
    excluded: list[ExcludedBelt]


def current_belt_stats(rows: Sequence[TitleRow]) -> CurrentBeltStats:
    """**현존하는 벨트만** 집계한다 (2026-10-07 사용자 결정).

    옛 이름의 획득은 `belt_lineage.BELT_LINEAGE`를 따라 후신 벨트로 합친다 — 그러지
    않으면 `WWE Championship` 45회가 "없는 벨트"로 빠지고 `Undisputed WWE
    Championship`은 개명 이후 몇 회만 든 채로 보인다.

    **합치지 못한 이름은 `excluded`로 돌려준다.** 화면이 몇 종을 왜 뺐는지 적을 수
    있어야 집계가 조용히 줄어드는 일이 없다.

    보드에 있지만 획득 기록이 없는 벨트(Evolve·ID 넷)도 `reigns=0`으로 **남긴다** —
    "0회 획득"이 아니라 이력 카탈로그에 행이 없다는 뜻이고, 화면이 그렇게 적는다.
    """
    from kayfabe.app.services import belt_lineage
    from kayfabe.app.services.records_scoring import normalize_name

    order = belt_lineage.current_belt_names()
    per_belt: dict[str, Counter[str]] = {belt: Counter() for belt in order}
    dropped: dict[str, int] = defaultdict(int)

    for row in rows:
        current = belt_lineage.resolve_belt(row.belt_name)
        if current is None:
            dropped[row.belt_name] += 1
            continue
        per_belt[current][normalize_name(row.competitor_name)] += 1

    belts: list[BeltStat] = []
    for belt in order:
        holders = per_belt[belt]
        top_name, top_count = holders.most_common(1)[0] if holders else (None, 0)
        belts.append(
            BeltStat(
                belt_name=belt,
                reigns=sum(holders.values()),
                holders=len(holders),
                top_holder=top_name,
                top_holder_reigns=top_count,
                former_names=tuple(belt_lineage.former_names(belt)),
            )
        )

    excluded = [
        ExcludedBelt(
            belt_name=name,
            reigns=count,
            reason=belt_lineage.retirement_reason(name),
        )
        for name, count in sorted(dropped.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return CurrentBeltStats(
        belts=sorted(belts, key=lambda s: (-s.reigns, s.belt_name)),
        excluded=excluded,
    )


@dataclass(frozen=True)
class BeltReign:
    """벨트 하나의 획득 한 건. `belt_name`은 **그때 불리던 이름**이다."""

    competitor_name: str
    belt_name: str
    won_at: str


@dataclass(frozen=True)
class HolderReigns:
    """한 사람이 그 벨트를 든 기록. `reigns`는 목록 길이와 같다."""

    name: str
    reigns: int
    history: list[BeltReign]


@dataclass(frozen=True)
class BeltDetail:
    belt_name: str
    former_names: tuple[str, ...]
    reigns: int
    holders: list[HolderReigns]


def belt_detail(rows: Sequence[TitleRow], belt_name: str) -> BeltDetail | None:
    """현 벨트 하나의 획득 이력. 현존하지 않는 이름이면 `None`.

    **옛 이름으로 들어온 획득도 포함하고, 그 이름을 지우지 않는다** — 각 건은 그때
    불리던 이름을 그대로 들고 간다. 그래야 "WWE Championship 시절 획득"임이 화면에
    남는다.

    **시간순으로 늘어놓지 않는다.** `won_at`이 자유 텍스트라 정렬하면 틀린 순서가
    된다(§9). 보유자를 획득 횟수 순으로 세운다.
    """
    from kayfabe.app.services import belt_lineage
    from kayfabe.app.services.records_scoring import normalize_name

    if belt_name not in set(belt_lineage.current_belt_names()):
        return None

    per_person: dict[str, list[BeltReign]] = defaultdict(list)
    for row in rows:
        if belt_lineage.resolve_belt(row.belt_name) != belt_name:
            continue
        name = normalize_name(row.competitor_name)
        per_person[name].append(
            BeltReign(competitor_name=name, belt_name=row.belt_name, won_at=row.won_at)
        )

    holders = sorted(
        (
            HolderReigns(name=name, reigns=len(history), history=history)
            for name, history in per_person.items()
        ),
        key=lambda h: (-h.reigns, h.name),
    )
    return BeltDetail(
        belt_name=belt_name,
        former_names=tuple(belt_lineage.former_names(belt_name)),
        reigns=sum(h.reigns for h in holders),
        holders=holders,
    )


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


#: 생일 칸이 이 형식일 때만 읽는다. `wrestlers.birth_date`는 `String(50)`이라
#: 무엇이든 들어갈 수 있고, 실제로 로스터 CSV에는 `1974-??-??`처럼 월·일을 모르는
#: 행이 있다. **모르는 날짜를 1월 1일로 접지 않는다** — 그 순간 생일이 아닌 사람이
#: 생일인 것처럼 뜬다.
#: 연도는 `????`일 수 있다 — **월·일만 알아도 달력에 올릴 수 있다.** 그때 나이는
#: `None`이고 화면이 그 칸을 비운다. 반대로 `1974-??-??`처럼 월·일을 모르면 올릴
#: 자리가 없으므로 건너뛴다. 실측(2026-10-12): 전자 1명·후자 2명.
_BIRTH_DATE = re.compile(r"^(\d{4}|\?{4})-(\d{2})-(\d{2})$")


@dataclass(frozen=True)
class BirthdayPerson:
    """생일을 셀 사람 하나. **표가 아니라 이 모양을 받는다.**

    선수(`wrestlers`)와 비선수(`wwe_staff`)는 칼럼이 다른 표인데 생일 계산에
    필요한 것은 이름·날짜·소속뿐이다. 두 표를 각각 받는 함수를 두면 규칙이
    둘로 갈라지므로, 인터랙터가 여기로 접어서 넘긴다.
    """

    name: str
    birth_date: str | None
    #: 화면에 적을 소속. 선수는 브랜드, 비선수는 CSV 구역(`Executives` 등)이다.
    group: str | None = None
    #: `"wrestler"` | `"staff"`.
    kind: str = "wrestler"
    #: 비선수만 있다 — `Commentator` · `Ring Announcer` 등.
    role: str | None = None


@dataclass(frozen=True)
class Birthday:
    """다가오는 생일 한 건.

    `age`는 **그 생일에 맞이할 나이**다(오늘이 생일이면 오늘 기준). 출처가
    `birth_date` 칼럼 하나뿐이라 위키처럼 개정본으로 되짚을 계보가 없다 —
    화면이 "N/M명 기준"이라고 함께 적어야 하는 이유다.
    """

    name: str
    group: str | None
    kind: str
    role: str | None
    #: `MM-DD`. 연도를 빼는 이유는 이 값이 "다가오는 날짜"라서다.
    month_day: str
    birth_date: str
    #: **`None`은 태어난 해를 모른다는 뜻**이다. 그 사람도 생일은 있으므로 목록에
    #: 서되 나이 칸만 비운다 — 모르는 값을 0이나 추정치로 채우지 않는다.
    age: int | None
    #: 오늘부터 며칠 뒤인가. 오늘이면 0이다.
    days_away: int


def to_birthday_people(
    rows: Iterable[WrestlerRow],
) -> list[BirthdayPerson]:
    """선수 행 → 생일 입력. 브랜드가 소속 칸이 된다."""
    return [
        BirthdayPerson(
            name=row.name,
            birth_date=row.birth_date,
            group=(row.brand or "").strip() or None,
            kind="wrestler",
        )
        for row in rows
    ]


def upcoming_birthdays(
    rows: Iterable[BirthdayPerson],
    *,
    today: date,
    limit: int = 5,
) -> list[Birthday]:
    """오늘부터 가까운 순으로 생일 `limit`건.

    **창(窓)이 아니라 개수로 자른다.** 로스터 165명의 생일을 실측하면 1년 중
    **239일이 0명**이다(2026-10-12 기준). "앞으로 30일" 같은 창으로 끊으면 화면이
    자주 통째로 비는데, 개수로 끊으면 날짜가 멀어질 뿐 빈 칸이 되지 않는다.

    **연말을 넘어 감는다** — 12월 말에 1월 생일이 다음 차례로 와야 한다.

    `2월 29일`은 평년에 `days_away`가 한 해 뒤로 밀릴 뿐 사라지지 않는다. 그 날을
    3월 1일로 당기지 않는 이유는 위와 같다 — 아닌 날을 생일로 만들지 않는다.
    """
    found: list[Birthday] = []
    for row in rows:
        matched = _BIRTH_DATE.match((row.birth_date or "").strip())
        if matched is None:
            continue
        raw_year, raw_month, raw_day = matched.groups()
        year = None if raw_year.startswith("?") else int(raw_year)
        month, day = int(raw_month), int(raw_day)
        try:
            this_year = date(today.year, month, day)
        except ValueError:
            # 2월 29일이고 올해가 평년이다. 다음 윤년까지 밀어 둔다.
            this_year = None
        if this_year is not None and this_year >= today:
            next_birthday = this_year
        else:
            next_birthday = _next_anniversary(month, day, after=today)
            if next_birthday is None:
                continue
        found.append(
            Birthday(
                name=row.name,
                group=row.group,
                kind=row.kind,
                role=row.role,
                month_day=f"{month:02d}-{day:02d}",
                birth_date=matched.group(0),
                age=None if year is None else next_birthday.year - year,
                days_away=(next_birthday - today).days,
            )
        )
    return sorted(found, key=lambda b: (b.days_away, b.name))[:limit]


def _next_anniversary(month: int, day: int, *, after: date) -> date | None:
    """`after` 다음에 오는 `month-day`. 윤년이라 몇 해 건너뛸 수 있다."""
    for offset in range(1, 9):
        try:
            return date(after.year + offset, month, day)
        except ValueError:
            continue
    return None


#: 지명 대조용 — 마침표·쉼표를 지워 `U.S.`와 `US`를 같게 만든다.
_PLACE_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def _place_city(value: str) -> str:
    """지명 한 덩이에서 **도시만** 남긴다. `Woodstock, Georgia, U.S.` → `woodstock`."""
    head = value.split(",")[0]
    folded = unicodedata.normalize("NFKD", head)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return _PLACE_NON_WORD.sub(" ", folded).strip().casefold()


def hometown_differs(birth_place: str | None, billed_from: str | None) -> bool | None:
    """방송이 말하는 연고지가 실제 출생지와 다른가. **모르면 `None`이다.**

    ## 왜 문자열을 그대로 비교하지 않는가

    단순 비교는 **나라 접미사만 빠진 경우를 전부 "다름"으로 센다** —
    `Woodstock, Georgia, U.S.`(출생)와 `Woodstock, Georgia`(연고지)는 같은 동네다.
    운영 175명 실측에서 단순 비교는 114명을 "다름"이라 했지만, 도시로 보면
    **61명**이다. 나머지 53명은 표기 차이였을 뿐이다.

    ## 규칙

    도시(첫 쉼표 앞)만 비교하고, `billed_from`은 `|`로 여럿일 수 있으므로
    **그중 하나라도 출생 도시와 같으면 "같다"**로 본다 — 방송이 두 곳을 함께
    부르는 선수가 있다(`Atlanta, Georgia | Woodstock, Georgia`).

    ## 이 규칙이 못 잡는 것

    `Kansas, U.S.`(출생)와 `Kansas City`(연고지)는 글자가 달라 "다름"이 된다.
    부분 일치로 넓히면 `York`와 `New York`이 같아지므로 **일부러 좁게 뒀다.**
    경계에 있는 값은 사람이 보고 판단할 수 있게 화면이 두 지명을 **함께** 적는다.
    """
    birth = (birth_place or "").strip()
    billed = (billed_from or "").strip()
    if not birth or not billed:
        return None
    city = _place_city(birth)
    if not city:
        return None
    parts = [part for part in billed.split("|") if part.strip()]
    if city in {_place_city(part) for part in parts}:
        return False
    # **출생지에 도시가 없고 주만 적힌 행이 있다** (`Florida, U.S.`). 그때는
    # 연고지의 어느 칸이든 그 주와 같으면 같은 곳으로 본다 — Roman Reigns의
    # `Florida, U.S.` ↔ `Pensacola, Florida`를 간극으로 세면 거짓이다. 실측
    # 4건이 이 모양이고 그중 둘이 그랬다(나머지 둘은 주 자체가 다르다).
    if birth.count(",") <= 1:
        segments = {
            _place_city(segment) for part in parts for segment in part.split(",")
        }
        if city in segments:
            return False
    return True


#: 미국 주 50개 + DC. **닫힌 목록이라 코드에 둔다** — 브랜드처럼 DB가 정하는 값이
#: 아니라 바깥 세계의 상수다. `birth_place`가 `Phoenix, Arizona`처럼 나라를 빼고
#: 끝나는 행이 있어서, 마지막 칸이 주면 그 사람은 미국 사람이다.
_US_STATES = frozenset(
    {
        "Alabama",
        "Alaska",
        "Arizona",
        "Arkansas",
        "California",
        "Colorado",
        "Connecticut",
        "Delaware",
        "District of Columbia",
        "Florida",
        "Georgia",
        "Hawaii",
        "Idaho",
        "Illinois",
        "Indiana",
        "Iowa",
        "Kansas",
        "Kentucky",
        "Louisiana",
        "Maine",
        "Maryland",
        "Massachusetts",
        "Michigan",
        "Minnesota",
        "Mississippi",
        "Missouri",
        "Montana",
        "Nebraska",
        "Nevada",
        "New Hampshire",
        "New Jersey",
        "New Mexico",
        "New York",
        "North Carolina",
        "North Dakota",
        "Ohio",
        "Oklahoma",
        "Oregon",
        "Pennsylvania",
        "Rhode Island",
        "South Carolina",
        "South Dakota",
        "Tennessee",
        "Texas",
        "Utah",
        "Vermont",
        "Virginia",
        "Washington",
        "West Virginia",
        "Wisconsin",
        "Wyoming",
    }
)

#: 데이터가 미국을 적는 여러 방식. 표준 이름은 `United States`로 모은다.
_US_NAMES = frozenset(
    {"u.s.", "us", "usa", "united states", "united states of america"}
)

UNITED_STATES = "United States"


@dataclass(frozen=True)
class OriginGroup:
    """한 지역과 **거기 출신이 누구인지**. 화면이 눌렀을 때 이름을 보여 준다."""

    name: str
    count: int
    members: list[str]


@dataclass(frozen=True)
class OriginDistribution:
    """출신 분포. **나라와 미국 주를 따로 센다.**

    둘을 한 축에 섞으면 미국이 62%라 다른 나라가 안 보이고, 미국만 보면 바깥
    67명이 사라진다. 화면이 지도 둘을 나란히 세우는 이유와 같다.
    """

    #: 나라별. 인원 내림차순.
    countries: list[OriginGroup]
    #: 미국 주별. 인원 내림차순.
    us_states: list[OriginGroup]
    #: 미국 사람인데 주를 모르는 수 (`Florida, U.S.`처럼 주가 적힌 경우는 센다).
    us_state_unknown: int
    #: 출신지를 아는 사람 수 / 전체.
    located: int
    total: int


def _origin_of(birth_place: str | None) -> tuple[str, str | None] | None:
    """`birth_place` → `(나라, 주)`. 못 읽으면 `None`.

    마지막 칸이 나라다. 다만 **마지막 칸이 미국 주면 나라가 생략된 것**이고
    (`Phoenix, Arizona`), 그 경우 그 칸이 곧 주다. 실측 6명이 이 모양이라
    그냥 두면 Arizona·California가 "나라"로 집계된다.
    """
    parts = [p.strip() for p in (birth_place or "").split(",") if p.strip()]
    if not parts:
        return None
    last = parts[-1]
    if last.casefold() in _US_NAMES:
        state = parts[-2] if len(parts) >= 2 and parts[-2] in _US_STATES else None
        return UNITED_STATES, state
    if last in _US_STATES:
        return UNITED_STATES, last
    return last, None


def origin_distribution(rows: Iterable[WrestlerRow]) -> OriginDistribution:
    """출신 나라·미국 주 분포. **없는 값을 추정하지 않는다** — 모르면 안 센다."""
    countries: defaultdict[str, list[str]] = defaultdict(list)
    states: defaultdict[str, list[str]] = defaultdict(list)
    unknown_state = 0
    total = 0
    located = 0
    for row in rows:
        total += 1
        origin = _origin_of(row.birth_place)
        if origin is None:
            continue
        located += 1
        country, state = origin
        countries[country].append(row.name)
        if country == UNITED_STATES:
            if state:
                states[state].append(row.name)
            else:
                unknown_state += 1

    def grouped(source: dict[str, list[str]]) -> list[OriginGroup]:
        return sorted(
            (
                OriginGroup(name=name, count=len(members), members=sorted(members))
                for name, members in source.items()
            ),
            key=lambda g: (-g.count, g.name),
        )

    return OriginDistribution(
        countries=grouped(countries),
        us_states=grouped(states),
        us_state_unknown=unknown_state,
        located=located,
        total=total,
    )


#: 트레이너 칸에 섞여 있는 **기관** 표기. 사람과 같은 줄에 세우되 화면이 갈라
#: 보여 줄 수 있게 표시만 해 둔다 — 실측 245개 중 소수지만 1위가 여기 있다
#: (`WWE Performance Center` 73명). 판정은 낱말로 한다: 이름에 아래가 들어가면
#: 기관이다. **사람 이름을 기관으로 잘못 잡는 쪽보다 그 반대가 안전하므로** 좁게 둔다.
_INSTITUTION_WORDS = (
    "center",
    "centre",
    "school",
    "academy",
    "dojo",
    "institute",
    "university",
    "wrestling inc",
)


def is_training_institution(name: str) -> bool:
    """사람이 아니라 학교·시설인가. 애매하면 **사람으로 본다**."""
    lowered = name.casefold()
    return any(word in lowered for word in _INSTITUTION_WORDS)


@dataclass(frozen=True)
class TrainerDistribution:
    """누가 누구를 길렀나.

    **그래프로 그리지 않는다.** 실측 245개 표기 중 203개(83%)가 제자 한 명뿐이고
    1위 `WWE Performance Center`가 73명을 쥔다 — 허브 하나에 잎이 매달린 모양이라
    노드-엣지로 그리면 덩어리 하나와 먼지밖에 안 보인다. 순위 목록이 정확하다.
    """

    #: (트레이너, 제자 수, 제자들) 내림차순.
    groups: list[OriginGroup]
    #: 트레이너를 아는 선수 수 / 전체.
    known: int
    total: int


#: 괄호 안에 **사람이 따로 적힌** 표기를 가른다 —
#: `WWE Performance Center (Sara Amato)` 는 센터 한 건이 아니라 **센터 + 사람**이다.
#: 이 규칙이 없으면 같은 센터가 괄호 내용마다 다른 트레이너로 갈라진다(실측 3갈래).
_PAREN = re.compile(r"^(?P<outer>[^(]+?)\s*\((?P<inner>[^)]+)\)$")

#: **같은 사람의 다른 이름.** 링네임과 본명이 섞여 들어와 한 사람이 둘로 갈린다.
#: 벨트 별칭표(`belt_lineage`)와 같은 자리이고, 같은 이유로 **확실한 것만** 적는다.
_TRAINER_ALIASES = {
    # Sara Del Rey 의 본명이 Sara Amato 다. 실측 5건 + 4건이 같은 사람이었다.
    "Sara Amato": "Sara Del Rey",
}


def trainer_names(raw: str | None) -> list[str]:
    """`trainer` 칸 한 줄 → 트레이너 이름들. `|`로 가르고 괄호를 푼다."""
    out: list[str] = []
    for part in (raw or "").split("|"):
        name = part.strip()
        if not name:
            continue
        matched = _PAREN.match(name)
        if matched:
            # `A (B & C)` → A · B · C
            out.append(matched.group("outer").strip())
            out.extend(
                piece.strip()
                for piece in re.split(r"&|,", matched.group("inner"))
                if piece.strip()
            )
        else:
            out.append(name)
    return [_TRAINER_ALIASES.get(n, n) for n in out]


def trainer_distribution(rows: Iterable[WrestlerRow]) -> TrainerDistribution:
    """`trainer` 칸을 갈라 트레이너별로 제자를 모은다.

    한 선수가 여러 트레이너를 갖는다(평균 2.3명·최대 9명). 그래서 제자 수의 합은
    선수 수보다 크다 — 화면이 "몇 명을 길렀나"로 읽히게 두고 비율을 만들지 않는다.
    """
    by_trainer: defaultdict[str, list[str]] = defaultdict(list)
    known = 0
    total = 0
    for row in rows:
        total += 1
        parts = trainer_names(row.trainer)
        if not parts:
            continue
        known += 1
        for part in dict.fromkeys(parts):  # 같은 줄에 두 번 나오면 한 번만 센다
            by_trainer[part].append(row.name)
    groups = sorted(
        (
            OriginGroup(name=name, count=len(members), members=sorted(members))
            for name, members in by_trainer.items()
        ),
        key=lambda g: (-g.count, g.name),
    )
    return TrainerDistribution(groups=groups, known=known, total=total)


@dataclass(frozen=True)
class StaffRow:
    """`wwe_staff` 한 행. 생일 말고 다른 화면이 쓰기 시작해서 넓혔다."""

    name: str
    group_label: str | None = None
    role: str | None = None
    korean_ring_name: str | None = None
    #: `No` · `Wrestler` · `Wrestler | Trainer` 등 자유 텍스트. 빈 값이 13건이다.
    wrestling_experience: str | None = None
    birth_date: str | None = None


def is_former_wrestler(experience: str | None) -> bool:
    """링에 섰던 사람인가.

    `wrestling_experience`는 자유 텍스트라 `Wrestler | Trainer`처럼 역할이 붙는다.
    **낱말 `wrestler`가 들어 있는지로만** 본다 — `ECW Promoter | Commentator`
    (폴 헤이먼)처럼 레슬링 업계지만 선수는 아닌 경우를 끌어들이지 않기 위해서다.
    """
    return "wrestler" in (experience or "").casefold()


@dataclass(frozen=True)
class StaffDirectory:
    """관계자 명부. **구역은 브랜드가 아니다** — `Executives`·`Raw Referee`가 섞여 있다."""

    rows: list[StaffRow]
    #: 구역별 인원 (목록 순서대로). 화면이 필터 칩을 이 값으로 만든다.
    groups: list[tuple[str, int]]
    former_wrestlers: int
    total: int


def staff_directory(rows: Iterable[StaffRow]) -> StaffDirectory:
    """관계자 명부. 정렬은 **구역 등장 순서 → 이름**이다.

    구역을 인원순으로 재정렬하지 않는 이유는 CSV가 적어 둔 순서가 조직도이기
    때문이다 — 경영진이 먼저고 브랜드별 인원이 뒤따른다.
    """
    listed = list(rows)
    order: dict[str, int] = {}
    counts: Counter[str] = Counter()
    for row in listed:
        key = (row.group_label or "").strip() or "미지정"
        order.setdefault(key, len(order))
        counts[key] += 1
    return StaffDirectory(
        rows=sorted(
            listed,
            key=lambda r: (
                order.get((r.group_label or "").strip() or "미지정", 999),
                r.name,
            ),
        ),
        groups=sorted(counts.items(), key=lambda kv: order[kv[0]]),
        former_wrestlers=sum(
            1 for r in listed if is_former_wrestler(r.wrestling_experience)
        ),
        total=len(listed),
    )


#: `????-07-16` 꼴을 걸러낸다. 연도를 모르면 나이를 못 센다.
_FULL_BIRTH_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class FirstBeltAge:
    """어떤 선수가 **첫 벨트를 몇 살에** 들었나."""

    name: str
    age: int
    won_on: str
    belt_name: str


#: 이 축의 분모. 화면이 함께 적지 않으면 "66명 중 최연소"가 "전체 최연소"로 읽힌다.
@dataclass(frozen=True)
class FirstBeltAgeBoard:
    entries: tuple[FirstBeltAge, ...]
    #: 계산된 사람 수.
    sample: int
    #: 타이틀 이력이 있는 사람 수(분모).
    title_holders: int


def first_belt_ages(
    wrestlers: Sequence[WrestlerRow], titles: Sequence[TitleRow]
) -> FirstBeltAgeBoard:
    """첫 타이틀 획득 당시 나이. **추론이 없다** — 양쪽 다 기록된 값이다.

    생일(`wrestlers.birth_date`)과 첫 획득일(`title_acquisitions.won_at` 파싱) 둘 다
    있어야 센다. 2026-10-20 실측으로 **66명**이고 타이틀 보유자는 81명이다 — 나머지
    15명은 현 로스터에 없어서 생일을 모른다(레전드·방출자).

    **생일이 `????-07-16` 꼴이면 건너뛴다.** 연도를 모르면 나이를 못 센다 —
    생일 보드가 그 꼴을 날짜로만 쓰는 것과 같은 자리다.
    """
    from kayfabe.domain.services.title_event_date import parse_won_at

    first: dict[str, tuple[date, str]] = {}
    for row in titles:
        on = parse_won_at(row.won_at).won_on
        if on is None:
            continue
        current = first.get(row.competitor_name)
        if current is None or on < current[0]:
            first[row.competitor_name] = (on, row.belt_name)

    births: dict[str, date] = {}
    for w in wrestlers:
        raw = (w.birth_date or "").strip()
        if not _FULL_BIRTH_DATE.match(raw):
            continue
        try:
            births[w.name] = date.fromisoformat(raw)
        except ValueError:
            continue

    entries = []
    for name, (on, belt) in first.items():
        born = births.get(name)
        if born is None:
            continue
        age = on.year - born.year - ((on.month, on.day) < (born.month, born.day))
        entries.append(
            FirstBeltAge(name=name, age=age, won_on=on.isoformat(), belt_name=belt)
        )
    entries.sort(key=lambda e: (e.age, e.won_on, e.name))
    return FirstBeltAgeBoard(
        entries=tuple(entries), sample=len(entries), title_holders=len(first)
    )
