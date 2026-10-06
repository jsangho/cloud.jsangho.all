"""위키 대회 문서로 **프론트 대진표 픽스처**를 갱신한다.

## 왜 DB가 아니라 프론트 파일인가

대진표의 원본은 `www/lib/wwe-ple-matches.ts`다. `ple-match-bracket.tsx`의
`needsStaticResync`가 경기 id 집합을 비교해 다르면 정적 카드로
`sync-from-client`를 POST하고, 그 API는 **페이로드에 없는 경기를 지운다.** DB에만
경기를 더하면 다음 방문자가 페이지를 여는 순간 되돌아가고 그 경기의 예측이 CASCADE로
사라진다. 그래서 이 스크립트는 픽스처를 고치고, 반영은 기존 경로가 한다:

    위키 → [이 스크립트] → wwe-ple-matches.ts → 사람이 diff 확인 → 커밋
         → Vercel 배포 → 방문자 접속 → sync-from-client → DB

**커밋과 배포는 사람이 한다.** 이 스크립트는 거기까지 가지 않는다.

## 기본이 드라이런이다

`--apply` 없이는 무엇을 쓸지만 출력한다. 챔피언 보드 동기화와 같은 규칙이다.

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/sync_ple_cards_from_wiki.py
    ... --apply                    # 파일을 고친다
    ... --event money-in-the-bank  # 한 대회만

**고친 뒤 `cd www && pnpm format`을 돌린다** — 이 스크립트의 서식은 prettier 흉내다.

## 배당·주석이 있는 대회는 손으로 고친다

`--apply`는 그 대회 블록을 **통째로 새로 찍는다.** 위키는 배당을 모르므로 입력에
없고, 그래서 `bookmakerDecimal`·`mq` 호가·손으로 쓴 주석은 덮어쓰기와 함께 사라진다.
2026-10-06부터 그런 블록은 **쓰지 않고 멈춘다** — 계획은 그대로 출력하니 보고
사람이 옮긴다. 자동 보존 대신 멈추기를 고른 이유는 `unreproducible_in_event`
독스트링에 적었다.

## 끝난 대회는 건드리지 않는다

위키는 같은 `matchN` 키에 두 종류를 담는다.

    |match1 = Roman Reigns (c) vs. LA Knight     ← 카드형: 아직 안 열렸다
    |match1 = Gunther defeated Seth Rollins      ← 결과형: 끝났다

결과형을 대진으로 옮기면 승자가 적힌 문자열이 "예정된 경기"로 둔갑한다. 파서가
둘을 갈라 주고 이 스크립트는 **카드형만** 쓴다. 끝난 대회는 `결과형`으로 보고되고
넘어간다.

## 위키가 429를 잘 낸다

실측(2026-09-29): 17개 대회를 병렬로 물으면 12개가 429로 실패하고, 1.2초 간격
순차도 같았다. 그래서 대회 사이에 넉넉히 쉰다 — 느린 대신 한 번에 끝난다.

종료 코드: 0 정상 · 1 위키 읽기 실패 **또는 사람 손이 필요한 대회가 있음** ·
2 픽스처 파일을 못 찾음

읽기 실패는 대개 **요청 제한**이고 다시 돌리면 통과한다. 실패한 대회만 `--event`로
좁혀 다시 부르면 된다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from kayfabe.app.services.ple_fixture_file import (  # noqa: E402
    id_prefix_of,
    read_event_cards,
    render_event_block,
    replace_event_block,
    unreproducible_in_event,
)
from kayfabe.app.services.ple_match_id_prefixes import (  # noqa: E402
    id_prefix_for,
)
from kayfabe.app.services.ple_match_titles import (  # noqa: E402
    title_from_stipulation,
)
from kayfabe.app.services.wiki_event_titles import (  # noqa: E402
    EVENT_ARTICLE_TITLES,
)
from kayfabe.domain.services.ple_card_parser import (  # noqa: E402
    card_matches,
    parse_results_tables,
)
from kayfabe.domain.services.ple_card_plan import (  # noqa: E402
    CardPlan,
    ExistingCard,
    plan_cards,
)
from ontology.app.ports.output.wiki_article_port import WikiArticlePort  # noqa: E402
from ontology.dependencies.wiki_article_provider import (  # noqa: E402
    get_wiki_article_port,
)

#: 저장소 루트 기준 픽스처 경로. `fastapi/apps/kayfabe/scripts` 에서 넷 위가 루트다.
FIXTURE_PATH = _APPS_DIR.parents[1] / "www" / "lib" / "wwe-ple-matches.ts"

#: 대진이 실리는 절 이름. 문서마다 `Matches`(예정)·`Results`(종료)로 갈린다.
_CARD_SECTIONS = ("matches", "results")

#: 대회 사이 간격(초). 429를 피하려고 넉넉히 둔다 — §위키가 429를 잘 낸다.
_COURTESY_DELAY = 4.0


async def read_cards(
    port: WikiArticlePort, slug: str, title: str
) -> tuple[str, tuple, str | None]:
    """한 대회의 카드형 경기들. `(사유, 경기들, 개정본)`.

    사유는 사람이 읽을 한 낱말이다 — `ok` · `목차실패` · `절없음` · `결과형` · `본문실패`.

    **`목차실패`는 "없는 문서"와 "요청 제한"을 구별하지 못한다.** 포트가 둘 다
    `None`으로 주기 때문이다(위키 API가 429에 본문을 안 준다). 실측에서 같은
    문서가 한 번은 읽히고 한 번은 실패했으므로, 이 사유가 뜨면 **다시 돌려 본다.**
    """
    sections = await port.sections(title)
    if sections is None:
        return "목차실패", (), None
    hit = next(
        (s for s in sections if s.line.casefold() in _CARD_SECTIONS),
        None,
    )
    if hit is None:
        return "절없음", (), None

    await asyncio.sleep(_COURTESY_DELAY)
    section = await port.read_section(title, hit.index)
    if section is None:
        return "본문실패", (), None

    tables = parse_results_tables(section.text)
    rows = card_matches(tables)
    if not rows:
        # 표는 있는데 카드가 없다 = 전부 결과형이다(끝난 대회).
        has_any = any(table.matches for table in tables)
        return ("결과형" if has_any else "표없음"), (), section.revision_id
    return "ok", rows, section.revision_id


def print_plan(plan: CardPlan, revision: str | None) -> None:
    print(f"\n== {plan.slug}  (rev {revision})")
    for card in plan.cards:
        mark = "  " if card.id_inherited else "신규"
        names = " vs. ".join(
            f"{c.name}{' (c)' if c.is_champion else ''}"
            + ("  ※미정" if c.undetermined else "")
            for c in card.row.competitors
        )
        print(f"  {mark} {card.id:24} {names}")
        print(f"       제목: {title_from_stipulation(card.row.stipulation)}")
    if plan.only_in_fixture:
        print(f"  [위키 대진에 없음 — 지우지 않는다] {', '.join(plan.only_in_fixture)}")
    print(
        f"  보존 {plan.kept} · 신규 {len(plan.added)} · 픽스처 전용 {len(plan.only_in_fixture)}"
    )


def build_block(plan: CardPlan) -> str:
    """계획 → 픽스처에 넣을 TS. `cardVariant`는 번갈아 둔다(장식이다)."""
    cards = []
    for index, card in enumerate(plan.cards):
        title = title_from_stipulation(card.row.stipulation) or "Single Match"
        people = [(c.name, c.is_champion, c.undetermined) for c in card.row.competitors]
        cards.append((card.id, title, "sideB" if index % 2 == 0 else "sideA", people))
    return render_event_block(cards)


async def main(*, apply: bool, only: str | None) -> int:
    if not FIXTURE_PATH.exists():
        print(f"[fail] 픽스처를 찾지 못했다: {FIXTURE_PATH}")
        return 2

    source = FIXTURE_PATH.read_text(encoding="utf-8")
    port = get_wiki_article_port()
    targets = {
        slug: title
        for slug, title in EVENT_ARTICLE_TITLES.items()
        if only is None or slug == only
    }
    if not targets:
        print(f"[fail] 모르는 대회다: {only}")
        return 2

    failures = 0
    manual = 0
    changed: list[str] = []
    new_ids: list[tuple[str, str]] = []

    for index, (slug, title) in enumerate(targets.items()):
        if index:
            await asyncio.sleep(_COURTESY_DELAY)

        existing = read_event_cards(source, slug)
        if existing is None:
            print(f"{slug:22} 픽스처에 항목이 없다 — 먼저 사람이 넣는다")
            continue

        reason, rows, revision = await read_cards(port, slug, title)
        if reason != "ok":
            if reason in {"목차실패", "본문실패"}:
                failures += 1
            print(f"{slug:22} {reason}")
            continue

        # **픽스처가 정본이고 표는 폴백이다.** 경기가 0건인 대회(대진 미발표)는
        # 읽을 id가 없어서 표를 본다 — 그 자리가 `halloween-havoc`이다.
        prefix = id_prefix_of(existing) or id_prefix_for(slug)
        if prefix is None:
            print(
                f"{slug:22} 경기 {len(rows)}건이 발표됐는데 id 접두사를 모른다 "
                "— `ple_match_id_prefixes.py`에 한 줄 더한다"
            )
            continue

        plan = plan_cards(
            slug,
            rows,
            tuple(ExistingCard(c.id, c.names) for c in existing),
            id_prefix=prefix,
        )
        if (
            not plan.added
            and not plan.only_in_fixture
            and len(plan.cards) == len(existing)
        ):
            print(f"{slug:22} 그대로 ({len(plan.cards)}경기)")
            continue

        print_plan(plan, revision)
        new_ids.extend((slug, card.id) for card in plan.added)

        # **덮어쓰면 잃는 것이 있으면 쓰지 않는다.** 블록을 통째로 새로 찍으므로
        # 배당·호가·주석은 입력에 없는 값이라 조용히 사라진다. 계획은 이미 위에
        # 찍었으니 사람이 그것을 보고 손으로 옮기면 된다.
        blockers = unreproducible_in_event(source, slug)
        if apply and blockers:
            print(f"  [멈춤] 덮어쓰면 잃는다: {' · '.join(blockers)}")
            print("         위 계획을 보고 픽스처를 손으로 고친다.")
            manual += 1
            continue

        if apply:
            updated = replace_event_block(source, slug, build_block(plan))
            if updated is None:
                print(f"  [fail] 항목을 갈아 끼우지 못했다: {slug}")
                failures += 1
                continue
            source = updated
            changed.append(slug)

    if manual:
        print(f"\n{manual}개 대회는 **손으로** 고친다 — 덮어쓰기가 배당·주석을 지운다.")

    if apply and changed:
        FIXTURE_PATH.write_text(source, encoding="utf-8")
        print(f"\n{FIXTURE_PATH}: {len(changed)}개 대회 갱신 — {', '.join(changed)}")
        print("다음: cd www && pnpm format && git diff 로 확인한 뒤 커밋한다")
    elif apply:
        print("\n바뀐 것이 없다 — 파일을 쓰지 않았다")
    else:
        print("\n드라이런이다 — 쓰지 않았다. 반영하려면 --apply")

    if new_ids:
        print("\n새 경기 id는 **초안이다.** 커밋 전에 기존 작명과 맞는지 본다:")
        for slug, card_id in new_ids:
            print(f"  {slug:22} {card_id}")

    return 1 if failures or manual else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    apply_flag = "--apply" in args
    event: str | None = None
    if "--event" in args:
        position = args.index("--event")
        if position + 1 >= len(args):
            print("--event 뒤에 대회 슬러그가 필요하다")
            raise SystemExit(2)
        event = args[position + 1]
        args = args[:position] + args[position + 2 :]
    unknown = set(args) - {"--apply"}
    if unknown:
        print(f"모르는 인자: {' '.join(sorted(unknown))}")
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(apply=apply_flag, only=event)))
