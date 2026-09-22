"""PLE 하나에 필요한 지식을 카드에서 뽑아 적재한다 (하네스 §10-T3).

**대회마다 URL을 손으로 찾지 않기 위한 스크립트다.** 저장된 카드에서 대회명과 출전
선수를 읽어 위키백과 주소를 만들고, 허용 도메인 목록을 통과한 것만 수집한다.

서사 에이전트가 의견을 내려면 그 경기에 대한 자료가 검색돼야 한다. 대회 문서만
넣으면 경기마다 같은 문단이 뽑히므로, **선수 문서까지 넣어 경기별로 다른 근거**가
잡히게 한다.

**조립한 이름은 추측이라 보내기 전에 확인한다** (Phase 3-13 Stage 5). 예전에는
빗나간 이름이 404로 걸러진다고 믿고 그대로 보냈는데, 실측이 그 믿음을 깼다 —
`Penta`는 동음이의 문서("Penta may refer to:")로 200을 돌려주고, `Royce Keys`는
`Powerhouse Hobbs`로 넘어간다. 앞은 내용 없는 목록이 근거 자리를 차지하게 하고,
뒤는 정규 주소가 아닌 자리에 본문을 쌓아 **나중에 정규 이름으로 다시 넣을 때
`content_hash` 유니크에 막혀 저장 0건이 조용히 성공으로 보고되게** 한다.

그래서 위키에 먼저 한 번 묻는다. 정규 제목으로 바꿔 수집하고, 동음이의와 없는
문서는 요청조차 보내지 않는다. **확인에 실패하면 추측으로 이어가지 않고 멈춘다.**

**대회 문서는 회차까지 본다** (Phase 3-13 Stage 7). Stage 5의 관문은 "문서가
실재하는가"만 보므로 시리즈 **총론**이 그대로 통과했다 — `Royal Rumble`·
`Survivor Series`·`WWE Bad Blood`가 실제로 그렇게 들어가고 있었다. 총론은 과거
회차의 **결과가 적힌 문서**라 근거가 아니라 오염이다(Phase 3-5가 SummerSlam에서
본 "두 LLM이 언제나 1.0"이 그 모양이었다). 그래서 대회 문서 하나에 대해서만
`WikiEditionPort`로 "이게 그해 회차인가"를 한 번 더 묻는다.

**선수 문서에는 걸지 않는다.** 회차 개념이 없을뿐더러 연도 카테고리를 엉뚱한 뜻으로
갖는다 — `Rhea Ripley`의 연도는 `Category:1996 births`, 곧 출생 연도다.

`--max-chunks`로 문서당 청크 수를 제한한다. 위키 인물 문서는 대부분이 타이틀 이력과
각주라, 앞부분(요약·최근 활동)만 담아도 예측 근거로는 충분하고 임베딩 시간이 크게 준다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/ingest_event_knowledge.py money-in-the-bank
    ... --dry-run    # 확인만 하고 수집 요청은 보내지 않는다

종료 코드: 0 정상 · 1 카드 없음/수집 0건 · 2 사용법 · **3 주소·회차 확인 실패**
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
from collections.abc import Sequence  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from urllib.parse import quote  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

from kayfabe.app.dtos.knowledge_ingestion_dto import (  # noqa: E402
    IngestKnowledgeCommand,
)
from kayfabe.dependencies.knowledge_ingestion_provider import (  # noqa: E402
    get_knowledge_ingestion_use_case,
)
from ontology.app.ports.output.wiki_edition_port import (  # noqa: E402
    WikiEdition,
    WikiEditionPort,
)
from ontology.app.ports.output.wiki_title_port import (  # noqa: E402
    WikiTitle,
    WikiTitlePort,
)
from ontology.dependencies.wiki_edition_provider import (  # noqa: E402
    get_wiki_edition_port,
)
from ontology.dependencies.wiki_title_provider import (  # noqa: E402
    get_wiki_title_port,
)

_WIKI = "https://en.wikipedia.org/wiki/"

#: 대회 문서 제목. **주소가 아니라 제목이고, 총론이 아니라 회차다.**
#: 인코딩은 `_wiki_url`이 하고, 실재 여부와 회차는 위키에 물어 확인한다.
#:
#: 값은 2026-09-22에 전수 실측한 것이다. 위키의 회차 문서 명명은 세 갈래로 갈려서
#: 규칙으로 생성할 수 없다 — `WrestleMania 42`는 연도를 안 쓰고, `Backlash (2026)`은
#: `WWE ` 접두사가 빠지며, `Survivor Series (2026)`은 `Survivor Series: WarGames
#: (2026)`으로 넘어간다. 그래서 사람이 확인한 제목을 적고 관문이 검증한다.
#:
#: **다음 시즌에 이 표가 낡으면 관문이 소리를 낸다** — 연도가 어긋난 회차 문서는
#: 조용히 통과하지 않고 `wrong_edition`으로 보고된다.
_EVENT_TITLES: dict[str, str] = {
    "royal-rumble": "Royal Rumble (2026)",
    "elimination-chamber": "Elimination Chamber (2026)",
    # NXT 계열은 문서 제목에 `NXT ` 접두사가 붙는다 — 단, `Worlds Collide`는
    # 세 브랜드 합동이라 붙지 않는다. 앱 슬러그에는 접두사를 쓰지 않으므로
    # 여기서만 갈린다.
    "vengeance-day": "NXT Vengeance Day (2026)",
    "stand-and-deliver": "NXT Stand & Deliver (2026)",
    "great-american-bash": "NXT The Great American Bash (2026)",
    "heatwave": "NXT Heatwave (2026)",
    "worlds-collide": "Worlds Collide (2026)",
    "halloween-havoc": "NXT Halloween Havoc (2026)",
    "wrestlemania": "WrestleMania 42",
    "backlash": "Backlash (2026)",
    # **연도 접미사가 없다.** 첫 회차라 문서 제목이 대회 이름 그대로다
    # (2026-05-31 · 토리노 Inalpi Arena, rev 1368715233). `WWE Clash in Italy`로
    # 물으면 `missing`이 나온다 — 그래서 한때 "없는 대회"로 잘못 뺐던 자리다.
    # 회차 관문은 선두 연도 카테고리로 보므로 이 제목도 그대로 통과한다.
    "clash-in-italy": "Clash in Italy",
    "night-of-champions": "Night of Champions (2026)",
    "summerslam": "SummerSlam (2026)",
    "money-in-the-bank": "Money in the Bank (2026)",
    "crown-jewel": "Crown Jewel (2026)",
    "survivor-series": "Survivor Series (2026)",
    "wrestlepalooza": "Wrestlepalooza (2026)",
    # `bad-blood`는 2026 회차가 **없다**(총론 회차 표는 2003·2004·2024 셋뿐).
    # 총론(`WWE Bad Blood`)을 대신 넣지 않는다 — 과거 회차 결과가 적힌 문서라
    # 근거가 아니라 오염이고, 그게 이 관문이 막으려는 바로 그것이다.
    #
    # `king-queen-of-the-ring`은 **`night-of-champions`에 흡수됐다.** 2026년에는
    # 독립 PLE가 아니라 6/1~6/27 토너먼트였고 결승이 거기서 열렸다. 그 경기의
    # 근거 문서는 `Night of Champions (2026)` 하나면 된다 — 토너먼트 문서를 따로
    # 넣으면 같은 경기가 두 문서로 검색된다.
}


def _wiki_url(title: str) -> str:
    """제목을 위키 주소로 바꾼다.

    `&`·`%`를 그대로 두지 않는다 — `NXT Stand & Deliver`의 실제 주소는
    `NXT_Stand_%26_Deliver`이고, 인코딩을 건너뛰면 경로가 그 자리에서 끊긴다.
    괄호는 남긴다: `Money_in_the_Bank_(2026)`이 위키가 쓰는 모양이다.

    **콜론도 남긴다** (Phase 3-13 Stage 7). 회차 문서에 처음으로 콜론이 들어간
    제목이 나왔다 — `Survivor Series: WarGames (2026)`. 2026-09-22 실측에서
    `%3A`와 `:` 둘 다 200이지만 **서로 정규화되지 않는다**:

        …/Survivor_Series:_WarGames_(2026)     200, 주소 그대로
        …/Survivor_Series%3A_WarGames_(2026)   200, 주소 그대로

    같은 문서가 두 주소로 남을 수 있다는 뜻이고, 그러면 나중에 정규 주소로 넣을 때
    `content_hash` 유니크에 막혀 **저장 0건이 조용히 성공으로 보고된다** — Stage 5가
    리다이렉트에서 막은 바로 그 사고를 인코딩으로 다시 내는 것이다.
    """
    return _WIKI + quote(title.replace(" ", "_"), safe="_(),:")


def _competitor_names(card_json: str) -> list[str]:
    """카드에서 사람 이름만 뽑는다. 팀 표기(`A & B`)는 각각으로 나눈다."""
    card = json.loads(card_json or "{}")
    raw: list[str] = []
    if card.get("format") == "multi":
        raw = [c.get("name", "") for c in card.get("competitors", [])]
    else:
        raw = [
            card.get("left", {}).get("name", ""),
            card.get("right", {}).get("name", ""),
        ]

    names: list[str] = []
    for entry in raw:
        for part in entry.replace(" and ", " & ").split("&"):
            name = part.strip()
            # 팀 이름·스테이블은 인물 문서가 없을 때가 많다. 없는 문서는 위키
            # 확인 단계에서 걸러지고 요청은 나가지 않는다.
            if name and name not in names:
                names.append(name)
    return names


async def _titles_for(slug: str) -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "select m.card_json from ple_matches m "
                    "join ple_events e on e.id = m.event_id where e.slug = :slug "
                    "order by m.sort_order, m.id"
                ),
                {"slug": slug},
            )
        ).all()

    titles: list[str] = []
    event_title = _EVENT_TITLES.get(slug)
    if event_title:
        titles.append(event_title)
    for (card_json,) in rows:
        for name in _competitor_names(card_json):
            if name not in titles:
                titles.append(name)
    return titles


async def _event_year(slug: str) -> int | None:
    """대회 시작일의 연도. 날짜를 모르면 `None`이다.

    **카탈로그가 아니라 DB를 읽는다.** 시간 게이트(`_corpus`)가 판정에 쓰는 값이
    `ple_events.start_date`이므로, "어느 회차를 읽었나"와 "무엇과 비교하나"가
    같은 값에서 나와야 둘이 어긋나지 않는다. (카탈로그 →DB 반영은
    `apply_event_schedule.py`가 한다.)
    """
    async with AsyncSessionLocal() as session:
        start = (
            await session.execute(
                text("select start_date from ple_events where slug = :slug"),
                {"slug": slug},
            )
        ).scalar_one_or_none()
    return start.year if start is not None else None


@dataclass(frozen=True)
class WrongEdition:
    """그해 회차가 아니라서 버린 대회 문서."""

    title: str
    canonical: str
    expected_year: int
    #: 문서가 실제로 걸려 있는 해들. 총론이면 대개 비어 있다.
    years: tuple[int, ...]


@dataclass(frozen=True)
class IngestionPlan:
    """무엇을 수집하고 무엇을 왜 버렸는지."""

    urls: tuple[str, ...] = ()
    #: `(물어본 이름, 정규 제목)` — 리다이렉트거나 표기가 다른 것.
    renamed: tuple[tuple[str, str], ...] = ()
    #: 본문이 아니라 같은 이름의 문서 목록이라 버린 것.
    disambiguation: tuple[str, ...] = ()
    #: 위키에 없어서 버린 것.
    missing: tuple[str, ...] = ()
    #: 실재하지만 **그해 회차가 아니라서** 버린 대회 문서 (총론 포함).
    wrong_edition: tuple[WrongEdition, ...] = ()
    #: 대회 날짜를 몰라 회차를 **판정하지 못해** 보류한 대회 문서.
    undated: tuple[str, ...] = ()


def plan_for(
    titles: Sequence[str],
    resolved: dict[str, WikiTitle],
    *,
    event_title: str | None = None,
    event_year: int | None = None,
    edition: WikiEdition | None = None,
) -> IngestionPlan:
    """확인 결과를 수집 계획으로 옮긴다. **DB도 네트워크도 모르는 순수 함수다.**

    표에 없는 이름은 **없는 문서로 본다.** 확인되지 않은 이름을 수집으로 넘기면
    이 관문이 하는 일이 없어진다.

    정규 제목이 겹치면 한 번만 수집한다 — `IYO SKY`와 `Iyo Sky`가 같은 문서라
    둘 다 보내면 두 번째는 `content_hash`에 막혀 저장 0건으로 돌아온다.

    `event_title`이 주어지면 그 하나에만 **회차 관문**이 걸린다. 날짜를 모르면
    (`event_year is None`) 통과가 아니라 **보류**다 — 어느 해 회차를 기대하는지
    모르는 채로 총론과 회차를 가릴 방법이 없고, 모르는 것을 통과로 읽는 순간
    이 관문이 없던 것이 된다. `PLE_EVENT_SCHEDULE`이 날짜를 "모른다"로 비워 두는
    관행과 같은 읽기다.
    """
    urls: list[str] = []
    renamed: list[tuple[str, str]] = []
    disambiguation: list[str] = []
    missing: list[str] = []
    wrong_edition: list[WrongEdition] = []
    undated: list[str] = []
    seen: set[str] = set()

    for title in titles:
        entry = resolved.get(title)
        if entry is None or entry.canonical is None:
            missing.append(title)
            continue
        if entry.is_disambiguation:
            disambiguation.append(title)
            continue
        if event_title is not None and title == event_title:
            if event_year is None:
                undated.append(title)
                continue
            if edition is None or not edition.covers(event_year):
                wrong_edition.append(
                    WrongEdition(
                        title=title,
                        canonical=entry.canonical,
                        expected_year=event_year,
                        years=tuple(sorted(edition.years)) if edition else (),
                    )
                )
                continue
        if entry.is_renamed:
            renamed.append((title, entry.canonical))
        if entry.canonical in seen:
            continue
        seen.add(entry.canonical)
        urls.append(_wiki_url(entry.canonical))

    return IngestionPlan(
        urls=tuple(urls),
        renamed=tuple(renamed),
        disambiguation=tuple(disambiguation),
        missing=tuple(missing),
        wrong_edition=tuple(wrong_edition),
        undated=tuple(undated),
    )


def _report(plan: IngestionPlan) -> None:
    print(f"수집 대상 {len(plan.urls)}건")
    for url in plan.urls:
        print(f"  {url}")
    for requested, canonical in plan.renamed:
        print(f"  정규 주소로 바꿈: {requested} → {canonical}")
    for title in plan.disambiguation:
        print(f"  동음이의라 버림: {title}")
    for title in plan.missing:
        print(f"  위키에 없어 버림: {title}")
    for wrong in plan.wrong_edition:
        actual = ", ".join(str(y) for y in wrong.years) or "없음"
        print(
            f"  {wrong.expected_year}년 회차가 아니라 버림: {wrong.title}"
            f" (→ {wrong.canonical}, 문서가 걸린 해: {actual})"
        )
    for title in plan.undated:
        print(f"  대회 날짜를 몰라 회차를 못 가려 보류: {title}")


async def main(
    slug: str,
    *,
    dry_run: bool,
    max_chunks: int | None,
    titles_port: WikiTitlePort | None = None,
    editions_port: WikiEditionPort | None = None,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    titles = await _titles_for(slug)
    if not titles:
        print(f"카드를 찾지 못했습니다: {slug}")
        return 1

    resolved = await (titles_port or get_wiki_title_port()).resolve(titles)
    if resolved is None:
        # 추측한 주소로 이어가지 않는다. 확인이 막혔다면 뒤따를 문서별 요청은
        # 더 심하게 막힌다 — 잠시 뒤 다시 돌리는 것이 맞다.
        print("위키에 문서를 확인하지 못했습니다. 수집하지 않고 멈춥니다.")
        return 3

    # 회차는 **대회 문서 하나**에만 묻는다. 실재하지 않는 문서에는 물을 것이 없고,
    # 날짜를 모르면 비교할 기준이 없어 요청 자체가 낭비다.
    event_title = _EVENT_TITLES.get(slug)
    event_entry = resolved.get(event_title) if event_title else None
    event_year: int | None = None
    edition: WikiEdition | None = None
    if event_entry is not None and event_entry.is_usable:
        event_year = await _event_year(slug)
        if event_year is not None:
            canonical = event_entry.canonical
            assert canonical is not None  # is_usable이 이미 보장한다
            table = await (editions_port or get_wiki_edition_port()).editions(
                [canonical]
            )
            if table is None:
                # 잘린 카테고리나 실패한 조회로 판정하면 회차 문서가 거짓 거부된다.
                print("대회 문서의 회차를 확인하지 못했습니다. 수집하지 않고 멈춥니다.")
                return 3
            edition = table.get(canonical)

    plan = plan_for(
        titles,
        resolved,
        event_title=event_title,
        event_year=event_year,
        edition=edition,
    )
    _report(plan)
    if not plan.urls:
        print("수집할 문서가 없습니다.")
        return 1
    if dry_run:
        return 0

    async with AsyncSessionLocal() as session:
        use_case = get_knowledge_ingestion_use_case(session, max_chunks=max_chunks)
        summary = await use_case.ingest(IngestKnowledgeCommand(urls=plan.urls))
        await session.commit()

    print(
        f"요청 {summary.requested} · 수집 {summary.collected} · 청크 {summary.chunks} "
        f"· 저장 {summary.stored} · 중복 {summary.duplicates} · 실패 {summary.failed}"
    )
    return 0 if summary.collected else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    positional = [a for a in argv if not a.startswith("--")]
    if not positional:
        print("사용법: ingest_event_knowledge.py <slug> [--dry-run] [--max-chunks=N]")
        raise SystemExit(2)

    limit_arg = next((a for a in argv if a.startswith("--max-chunks=")), None)
    raise SystemExit(
        asyncio.run(
            main(
                positional[0],
                dry_run="--dry-run" in argv,
                max_chunks=int(limit_arg.split("=")[1]) if limit_arg else 25,
            )
        )
    )
