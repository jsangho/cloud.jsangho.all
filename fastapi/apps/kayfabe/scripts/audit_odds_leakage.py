"""운영 예측 중 **증명되지 않은 배당**을 근거로 쓴 것을 센다. 읽기 전용.

2026-11-12에 카드의 배당 대부분이 관측일·출처 없이 적혀 있고, SummerSlam 2026 배당은
대회 사흘 뒤 커밋으로 들어온 것을 확인했다. 그 배당으로 만든 예측이 적중률에 섞였는지
보려고 만든 점검이다.

각 예측을 셋으로 나눈다.

- ``proven``: 오즈 축이 의견을 냈고, 카드의 호가 중 대회 전 관측이 증명된 것이 있다
- ``unproven``: 오즈 축이 의견을 냈지만 증명된 호가가 없다 — 누수 가능
- ``no_odds``: 오즈 축이 기권했다

그리고 결과가 기록된 예측만 골라 묶음별 적중을 센다.

실행 (백엔드 컨테이너 안):

    python /app/fastapi/apps/kayfabe/scripts/audit_odds_leakage.py

세션을 읽기 전용으로 열기 때문에 쓰기를 시도하면 DB가 거부한다.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date

import psycopg


def _proven_quote(card_json: str, event_day: date | None) -> bool:
    try:
        card = json.loads(card_json)
    except (TypeError, ValueError):
        return False
    for quote in card.get("bookmakerQuotes") or []:
        if not isinstance(quote, dict):
            continue
        try:
            observed = date.fromisoformat(str(quote.get("observedAt", "")).strip())
        except ValueError:
            continue
        if event_day is None or observed < event_day:
            return True
    return False


def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        # pooler가 접속 options를 버리므로 세션 단위로 읽기 전용을 건다.
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        rows = conn.execute(
            """
            SELECT e.slug, e.start_date, p.match_key, p.pick, p.generated_at,
                   m.winner_pick, m.card_json,
                   (SELECT r.pick FROM ple_agent_reports r
                     WHERE r.prediction_id = p.id AND r.agent = 'odds' LIMIT 1)
            FROM ple_agent_predictions p
            JOIN ple_events e ON e.id = p.event_id
            LEFT JOIN ple_matches m
              ON m.event_id = p.event_id AND m.match_key = p.match_key
            ORDER BY e.start_date, e.slug, p.match_key
            """
        ).fetchall()

    tally: Counter[tuple[str, str]] = Counter()
    for slug, day, key, pick, generated, winner, card, odds_pick in rows:
        if odds_pick is None:
            group = "no_odds"
        elif _proven_quote(card or "", day):
            group = "proven"
        else:
            group = "unproven"
        after = generated is not None and day is not None and generated.date() >= day
        if winner:
            tally[(group, "hit" if pick == winner else "miss")] += 1
        print(
            f"{slug:24s} {day} {key:28s} {group:9s} "
            f"{'AFTER' if after else '     '} pick={pick} winner={winner} odds={odds_pick}"
        )

    print("\n묶음별 적중 (결과가 기록된 예측만)")
    for group in ("proven", "unproven", "no_odds"):
        hit, miss = tally[(group, "hit")], tally[(group, "miss")]
        if hit + miss:
            print(f"  {group:9s} {hit}/{hit + miss}")
    total_hit = sum(v for (_, r), v in tally.items() if r == "hit")
    total = sum(tally.values())
    print(f"  전체      {total_hit}/{total}")


if __name__ == "__main__":
    main()
